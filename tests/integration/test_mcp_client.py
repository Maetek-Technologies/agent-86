"""v0.5 — MCP client surfaces that don't need the `mcp` package or a live server.

Covers MCPTool (spec from the server schema, run success/failure) and the MCPManager /
build_mcp degradation paths — the previously thin `tools/mcp_client.py`.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest

from agent86.config import MCPServerConfig, load_config
from agent86.tools.mcp_client import MCPManager, MCPTool, build_mcp
from agent86.types import ToolCall

# The stdio lifecycle tests below drive the real `live_mcp_server.py`, which is built on the
# SDK's own server API. This probed `mcp.server.fastmcp` until mcp 2.0 removed it (FastMCP
# moved out of the SDK), which skipped them even where the extra WAS installed.
try:
    import mcp.server.mcpserver  # noqa: F401

    _HAS_MCP_SERVER = True
except ImportError:
    _HAS_MCP_SERVER = False


class _FakeManager:
    def __init__(self, result: str | None = None, error: Exception | None = None):
        self._result = result
        self._error = error

    def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        if self._error is not None:
            raise self._error
        return self._result or ""


def test_mcp_tool_spec_uses_server_schema():
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    tool = MCPTool(_FakeManager(), "srv", "mytool", "does a thing", schema)
    spec = tool.spec()
    assert spec.name == "mcp__srv__mytool"
    assert spec.parameters["properties"] == {"x": {"type": "string"}}
    assert spec.side_effecting is True  # external effects -> approval-gated


def test_mcp_tool_run_returns_server_content():
    tool = MCPTool(_FakeManager(result="hello from server"), "srv", "mytool", "d", {})
    res = tool.run(ToolCall(id="1", name=tool.name, arguments={"x": "y"}), ctx=None)  # ctx unused
    assert res.ok and res.content == "hello from server"


def test_mcp_tool_run_wraps_failures_as_soft_error():
    tool = MCPTool(_FakeManager(error=RuntimeError("boom")), "srv", "mytool", "d", {})
    res = tool.run(ToolCall(id="1", name=tool.name, arguments={}), ctx=None)
    assert not res.ok and "boom" in (res.error or "")


def test_mcp_manager_no_servers_is_noop():
    manager = MCPManager({})
    manager.start()  # early-returns; must not import mcp or raise
    assert manager.tools() == []
    assert manager.note is None


def test_build_mcp_returns_none_without_servers():
    # Default config declares no MCP servers -> nothing to manage.
    assert build_mcp(load_config()) is None


# --- Wave 0 scaffold for plan 04-04: real-stdio per-server lifecycle (D-23 regression guard) - #
#
# Requires the `mcp` extra (its server API). Guarded by a module-level boolean + skipif, never a
# module-level `pytest.importorskip` — that would skip the mock-only tests above.

_SERVER = Path(__file__).with_name("live_mcp_server.py")


def _stdio_cfg() -> MCPServerConfig:
    return MCPServerConfig(command=sys.executable, args=[str(_SERVER), "stdio", "0"])


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_per_server_start_lists_real_tools():
    manager = MCPManager({})
    try:
        tools = manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        remote = {t._tool for t in tools if isinstance(t, MCPTool)}
        assert remote == {"add", "shout", "get_env"}
        names = {t.name for t in tools}
        assert {
            "mcp__alpha__list_resources",
            "mcp__alpha__read_resource",
            "mcp__alpha__list_resource_templates",
            "mcp__alpha__list_prompts",
            "mcp__alpha__get_prompt",
            "mcp__alpha__complete",
        } <= names
        # The fixture's MCPServer declares resources.subscribe = False and cannot declare it
        # True, so the subscribe gate must hold here (plan 11-01, Task 1).
        assert "mcp__alpha__subscribe_resource" not in names
        assert all(t.name.startswith("mcp__alpha__") for t in tools)
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_per_server_call_tool_round_trip():
    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        result = manager.call_tool("alpha", "add", {"a": 2, "b": 3})
        assert "5" in result
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_independent_teardown_leaves_other_server_intact():
    """The highest-value test in the phase (D-23): stopping one server must not tear down
    another server's session via a cross-task cancel scope."""
    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        manager.start_server("beta", _stdio_cfg(), timeout=30.0)

        try:
            manager.stop_server("alpha")
        except RuntimeError as exc:
            text = str(exc)
            assert "cancel scope" not in text
            assert "different task" not in text
            raise

        assert manager.tools_for("alpha") == []
        assert "alpha" not in manager._sessions

        assert "2" in manager.call_tool("beta", "add", {"a": 1, "b": 1})

        with pytest.raises(RuntimeError):
            manager.call_tool("alpha", "add", {"a": 1, "b": 1})
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_close_after_partial_stop_is_clean():
    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        manager.start_server("beta", _stdio_cfg(), timeout=30.0)
        manager.stop_server("alpha")
    finally:
        manager.close()
    assert manager._loop is None


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_start_server_failure_does_not_break_manager():
    manager = MCPManager({})
    try:
        bad_cfg = MCPServerConfig(command=sys.executable, args=["-c", "import sys; sys.exit(1)"])
        # A server that exits immediately can surface as any of several transport errors
        # (McpError, an anyio ExceptionGroup, a closed-pipe OSError), so bind the failure to a
        # name rather than asserting one blind `Exception` type.
        failure: BaseException | None = None
        try:
            manager.start_server("bad", bad_cfg, timeout=30.0)
        except Exception as exc:
            failure = exc
        assert failure is not None, "a server whose process exits must raise, not return tools"
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_stdio_server_gets_scrubbed_env(monkeypatch):
    """SEC-04, end to end: the stdio subprocess gets scrubbed_env(), not os.environ.

    Asserted only by unit test until now (`stdio_env()` returns the right dict); this drives a
    real subprocess over a real stdio transport and reads back what it actually received.
    """
    monkeypatch.setenv("AGENT86_TEST_HOST_SECRET", "leaked-if-you-see-this")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    manager = MCPManager({})
    try:
        manager.start_server("envsrv", _stdio_cfg(), timeout=30.0)
        raw = manager.call_tool("envsrv", "get_env", {})
    finally:
        manager.close()

    # Negative: neither the name nor the value of a host-only variable crosses the boundary.
    assert "AGENT86_TEST_HOST_SECRET" not in raw
    assert "leaked-if-you-see-this" not in raw
    assert "ANTHROPIC_API_KEY" not in raw
    assert "sk-ant-not-a-real-key" not in raw
    # Positive: the allowlist actually arrived, so the assertion above is not vacuous.
    env = json.loads(raw)
    assert "PATH" in env


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_list_resources_then_read_resource_round_trip():
    """MCP-14 end to end over real stdio: list, then read, with the text reaching the caller."""
    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        listing, _ = manager.list_resources("alpha")
        assert "res://agent86/greeting.txt" in listing
        body, meta = manager.read_resource("alpha", "res://agent86/greeting.txt")
        assert body.strip() == "hello from the agent86 live test server"
        assert meta["uri"] == "res://agent86/greeting.txt"

        templates, _ = manager.list_resource_templates("alpha")
        assert "res://agent86/echo/{word}" in templates

        binary, binary_meta = manager.read_resource("alpha", "res://agent86/blob.bin")
        assert "not inlined" in binary
        assert "agent86-binary-probe" not in binary
        assert binary_meta["binary"][0]["base64_len"] > 0
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_list_prompts_then_get_prompt_round_trip():
    """MCP-15 end to end over real stdio: the prompt list, then a rendered prompt."""
    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        listing, meta = manager.list_prompts("alpha")
        assert "review_code" in listing
        assert meta["count"] >= 1

        body, body_meta = manager.get_prompt(
            "alpha", "review_code", {"path": "a.py", "style": "concise"}
        )
        assert "Review the file at a.py in a concise style." in body
        assert body.lstrip().startswith("Review") or "[user]:" in body
        assert body_meta["prompt"] == "review_code"
        assert "non_text_blocks" not in body_meta
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_complete_returns_argument_suggestions():
    """CAP-COMPLETION end to end: the server's own completion handler answers."""
    from tests.integration.live_mcp_server import STYLE_COMPLETIONS  # noqa: PLC0415

    manager = MCPManager({})
    try:
        manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        every, meta = manager.complete("alpha", "prompt", "review_code", "style", "")
        assert set(every.splitlines()) == set(STYLE_COMPLETIONS)
        assert meta["count"] == len(STYLE_COMPLETIONS)

        filtered, _ = manager.complete("alpha", "prompt", "review_code", "style", "s")
        assert filtered.splitlines() == ["security-focused"]
    finally:
        manager.close()


# --- Plan 12-05: real-stdio kill-mid-session test (MCP-26 SC1 + SC2, the research's own probe) - #


def _pid_cfg(pid_file: Path) -> MCPServerConfig:
    return MCPServerConfig(
        command=sys.executable,
        args=[str(_SERVER), "stdio", "0"],
        env={"AGENT86_LIVE_MCP_PID_FILE": str(pid_file)},
    )


def _read_pid(pid_file: Path, timeout: float = 10.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pid_file.exists():
            text = pid_file.read_text(encoding="utf-8").strip()
            if text:
                return int(text)
        time.sleep(0.05)
    raise AssertionError(f"{pid_file} never received a pid within {timeout}s")


def _kill(pid: int) -> None:
    # On Windows, signal.SIGTERM maps to TerminateProcess (a hard kill, the research's own
    # `Stop-Process -Force` equivalent); on POSIX, prefer the real SIGKILL when available.
    sig = getattr(signal, "SIGKILL", signal.SIGTERM)
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, sig)


def _wait_until(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_mid_session_kill_unregisters_tools_and_names_server(tmp_path, monkeypatch):
    """The research's own empirical repro, pinned as a CI test (MCP-26 SC1 + SC2).

    `_MAX_RECONNECT_ATTEMPTS` is monkeypatched to 0 so this test asserts the same "dead and
    gone" outcome regardless of whether plan 12-03's reconnect loop has landed yet — the
    reconnect-after-real-kill case is plan 12-06.
    """
    import agent86.tools.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", 0)

    manager = MCPManager({})
    try:
        alpha_tools = manager.start_server("alpha", _pid_cfg(tmp_path / "alpha.pid"), timeout=30.0)
        manager.start_server("beta", _stdio_cfg(), timeout=30.0)

        pid = _read_pid(tmp_path / "alpha.pid")
        _kill(pid)

        assert _wait_until(
            lambda: manager.tools_for("alpha") == [] and manager._tasks["alpha"].done(),
            20.0,
        )
        assert "alpha" not in manager._sessions
        assert not any(t.name.startswith("mcp__alpha__") for t in manager.tools())

        with pytest.raises(RuntimeError) as excinfo:
            manager.call_tool("alpha", "add", {"a": 1, "b": 1})
        assert "'alpha'" in str(excinfo.value)

        add_tool = next(t for t in alpha_tools if isinstance(t, MCPTool) and t._tool == "add")
        call = ToolCall(id="1", name=add_tool.name, arguments={"a": 1, "b": 1})
        res = add_tool.run(call, ctx=None)
        assert res.ok is False
        assert "'alpha'" in (res.error or "")

        assert "2" in manager.call_tool("beta", "add", {"a": 1, "b": 1})

        assert any("MCP server 'alpha' disconnected" in note for note in manager.notes)
    finally:
        manager.close()


# --- Plan 12-06: real-stdio reconnect after a kill (SC3 end-to-end, MCP-23) --------------- #


def _pid_changed(path: Path, old: int) -> bool:
    """Tolerant check: a new pid has been written to `path`, distinct from `old`.

    Returns False (never raises) on a missing file, an empty/partial write mid-flush, or any
    value that doesn't parse as an int — the writer (`live_mcp_server.py`) truncates then writes,
    so a reader can observe a transient empty/partial file while the new process is starting.
    """
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return False
    try:
        new = int(text)
    except ValueError:
        return False
    return new != old


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_mid_session_kill_reconnects_with_fresh_tools(tmp_path):
    """A real killed stdio server comes back on its own (MCP-23, SC3), not just `stop_server`.

    Does NOT monkeypatch the reconnect constants — this exercises the shipped defaults
    (`_MAX_RECONNECT_ATTEMPTS = 5`), unlike plan 12-05's sibling test which pins 0 to stay a pure
    no-retry SC1 regression guard.
    """
    manager = MCPManager({})
    try:
        pid_file = tmp_path / "alpha.pid"
        manager.start_server("alpha", _pid_cfg(pid_file), timeout=30.0)
        first = _read_pid(pid_file)

        _kill(first)

        assert _wait_until(
            lambda: (
                _pid_changed(pid_file, first)
                and "alpha" in manager._sessions
                and manager.tools_for("alpha")
            ),
            30.0,
        )

        assert "2" in manager.call_tool("alpha", "add", {"a": 1, "b": 1})

        assert {t._tool for t in manager.tools_for("alpha") if isinstance(t, MCPTool)} == {
            "add",
            "shout",
            "get_env",
        }

        assert any("MCP server 'alpha' reconnected" in n for n in manager.notes)
        assert not manager._tasks["alpha"].done()
    finally:
        manager.close()
