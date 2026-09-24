"""Live MCP transport test — connects agent86 to a real MCP server over HTTP and SSE.

Unlike ``test_mcp_client.py`` (which mocks the manager), this spins up an actual MCP server in
a subprocess (``live_mcp_server.py``) and drives ``MCPManager`` against it end-to-end: connect,
``list_tools``, and a real ``call_tool`` round trip. It exercises the remote-transport code
(``_streamable_http`` / ``sse_client``) that unit tests cannot reach.

This module was permanently skipped for a while: it probed ``mcp.server.fastmcp``, which mcp
2.0 removed when FastMCP moved out of the SDK, so the skip fired on every machine including
ones with the extra installed. It now probes what it actually needs — the SDK's own
``MCPServer`` and the uvicorn it serves its ASGI apps with — so it runs wherever the ``mcp``
extra is present, and still skips cleanly on CI's minimal ``.[dev]`` install.
"""

from __future__ import annotations

import contextlib
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

_EXTRA = "requires the 'mcp' extra (MCP server + uvicorn)"
pytest.importorskip("mcp.server.mcpserver", reason=_EXTRA)
pytest.importorskip("uvicorn", reason=_EXTRA)

from agent86.config import Config, MCPServerConfig  # noqa: E402
from agent86.tools.mcp_client import build_mcp  # noqa: E402

_SERVER = Path(__file__).with_name("live_mcp_server.py")

# Each case is a single (server transport, URL path, explicit agent86 transport) tuple —
# passed whole to the indirect `live_server` fixture. Streamable HTTP is inferred from the
# URL; SSE has to be named.
_CASES = [
    pytest.param(("streamable-http", "/mcp", None), id="http"),
    pytest.param(("sse", "/sse", "sse"), id="sse"),
]


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.2)
    raise RuntimeError(f"server on port {port} did not come up within {timeout}s")


@pytest.fixture
def live_server(request, tmp_path):
    """Launch the live MCP server subprocess for a transport; yield its endpoint URL."""
    server_transport, path, _ = request.param
    port = _free_port()
    # Kept rather than devnull'd: when the SDK's server API shifts again, the traceback in
    # here is the difference between "did not come up within 15s" and an actionable error.
    log = tmp_path / f"live-mcp-{server_transport}.log"
    with log.open("wb") as sink:
        proc = subprocess.Popen(
            [sys.executable, str(_SERVER), server_transport, str(port)],
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        try:
            try:
                _wait_for_port(port)
            except RuntimeError as exc:
                output = log.read_text(encoding="utf-8", errors="replace").strip()
                raise RuntimeError(f"{exc}\n--- server output ---\n{output}") from exc
            yield f"http://127.0.0.1:{port}{path}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _build_ready_manager(cfg: Config, tries: int = 15):
    """Build the manager, retrying briefly for the ASGI app to finish starting up."""
    last = None
    for _ in range(tries):
        mgr = build_mcp(cfg)
        assert mgr is not None
        if mgr.tools():
            return mgr
        last = mgr.note
        mgr.close()
        time.sleep(0.3)
    raise AssertionError(f"no tools discovered from live server (last note: {last})")


@pytest.mark.parametrize("live_server", _CASES, indirect=True)
def test_live_transport_lists_and_calls_tools(live_server, request):
    _, _, explicit_transport = request.node.callspec.params["live_server"]
    cfg = Config(
        mcp_servers={
            "live": MCPServerConfig(url=live_server, transport=explicit_transport),
        }
    )
    # The transport is inferred to "http" for the streamable-HTTP case, explicit for SSE.
    assert cfg.mcp_servers["live"].transport == (explicit_transport or "http")

    mgr = _build_ready_manager(cfg)
    try:
        names = {t.name for t in mgr.tools()}
        assert {"mcp__live__add", "mcp__live__shout", "mcp__live__get_env"} <= names
        assert {"mcp__live__list_resources", "mcp__live__read_resource"} <= names
        # resources.subscribe is False on an MCPServer-hosted fixture — the gate must hold.
        assert "mcp__live__subscribe_resource" not in names

        # Real call round trips over the live transport.
        assert mgr.call_tool("live", "add", {"a": 40, "b": 2}).strip() == "42"
        assert mgr.call_tool("live", "shout", {"text": "it works"}).strip() == "IT WORKS"
    finally:
        mgr.close()


# --- Plan 12-06: SSE / streamable-HTTP kill-mid-session (research Open Question 4, MCP-26) - #


@contextlib.contextmanager
def _spawn_live_server(server_transport: str, path: str, tmp_path: Path):
    """Launch the live MCP server subprocess for a transport; yield (url, proc).

    Same launch/wait/log logic as the `live_server` fixture, but hands back the process handle
    so the caller can kill it mid-session (the fixture itself is left unchanged).
    """
    port = _free_port()
    log = tmp_path / f"live-mcp-kill-{server_transport}.log"
    with log.open("wb") as sink:
        proc = subprocess.Popen(
            [sys.executable, str(_SERVER), server_transport, str(port)],
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        try:
            try:
                _wait_for_port(port)
            except RuntimeError as exc:
                output = log.read_text(encoding="utf-8", errors="replace").strip()
                raise RuntimeError(f"{exc}\n--- server output ---\n{output}") from exc
            yield f"http://127.0.0.1:{port}{path}", proc
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@pytest.mark.parametrize("case", _CASES)
def test_live_transport_mid_session_kill_is_detected(case, tmp_path, monkeypatch):
    """A killed SSE/streamable-HTTP server is detected — passively or on the next call.

    `_MAX_RECONNECT_ATTEMPTS` is pinned to 0: nothing will be listening on the killed port to
    reconnect to, so this test asserts pure death-detection (MCP-26), not MCP-23's retry loop
    (already proven against real stdio in plan 12-06's stdio test).
    """
    import agent86.tools.mcp_client as mcp_client

    server_transport, path, explicit = case
    monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", 0)

    with _spawn_live_server(server_transport, path, tmp_path) as (url, proc):
        cfg = Config(mcp_servers={"live": MCPServerConfig(url=url, transport=explicit)})
        mgr = _build_ready_manager(cfg)
        try:
            assert mgr.call_tool("live", "add", {"a": 1, "b": 1}).strip() == "2"

            proc.kill()
            proc.wait(timeout=5)

            detected = _wait_until(lambda: mgr.tools_for("live") == [], 10.0)
            phase = "passively"

            if not detected:
                phase = "on next call"
                call_error: list[BaseException] = []

                def _call() -> None:
                    try:
                        mgr.call_tool("live", "add", {"a": 1, "b": 1})
                    except BaseException as exc:  # noqa: BLE001 - recorded, not raised, cross-thread
                        call_error.append(exc)

                caller = threading.Thread(target=_call, daemon=True)
                caller.start()
                caller.join(timeout=25.0)

                detected = _wait_until(lambda: mgr.tools_for("live") == [], 20.0)

            print(f"{server_transport}: detected {phase}")
            assert detected

            with pytest.raises(RuntimeError, match="'live'"):
                mgr.call_tool("live", "add", {"a": 1, "b": 1})
        finally:
            mgr.close()
