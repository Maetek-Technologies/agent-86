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
from agent86.tools.mcp_client import (
    MCPManager,
    MCPServerUnavailable,
    MCPTimeout,
    MCPTool,
    build_mcp,
)
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
    tool = MCPTool(_FakeManager(result="ok"), "srv", "mytool", "does a thing", schema)
    spec = tool.spec()
    assert spec.name == "mcp__srv__mytool"
    # ADR 0003: the schema is deferred until first use — a never-called tool advertises the
    # stub, not the server's real schema.
    assert spec.parameters == {"type": "object", "properties": {}}

    tool.run(ToolCall(id="1", name=tool.name, arguments={"x": "v"}), ctx=None)

    spec = tool.spec()
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
def test_stdio_start_failure_note_carries_child_stderr():
    """Plan 12-08 Task 2, end to end: a real stdio child's stderr reaches the start-failure note.

    A start failure used to render as the SDK's bare `unhandled errors in a TaskGroup (1
    sub-exception)` — the real reason (here, the child's own stderr) went to the terminal,
    invisible under the TUI. `describe_start_failure` names the leaf cause AND quotes the
    child's captured stderr tail.
    """
    cfg = MCPServerConfig(
        command=sys.executable,
        args=["-c", "import sys; print('boom-marker', file=sys.stderr); sys.exit(3)"],
    )
    manager = MCPManager({"live": cfg})
    try:
        manager.start()
        joined = "\n".join(manager.notes)
        assert "MCP server 'live' failed to start" in joined
        assert "boom-marker" in joined
        assert "unhandled errors in a TaskGroup" not in joined
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


# --- Plan 13-05: real-stdio proof of per-server timeouts, the result cap, and non-text ---- #
# --- content blocks (SC1-SC3, MCP-21/MCP-22/MCP-25) --------------------------------------- #


def _extra_cfg(**limits: object) -> MCPServerConfig:
    """A stdio cfg for `alpha`-style servers with Task 1's opt-in extra tools mounted.

    ``pid_file`` (if passed) is popped and routed to AGENT86_LIVE_MCP_PID_FILE so a caller can
    combine the extra-tools probe with the existing kill/reconnect helpers; every remaining
    keyword is forwarded straight to MCPServerConfig (e.g. call_timeout_s, max_result_chars).
    """
    env = {"AGENT86_LIVE_MCP_EXTRA_TOOLS": "1"}
    pid_file = limits.pop("pid_file", None)
    if pid_file is not None:
        env["AGENT86_LIVE_MCP_PID_FILE"] = str(pid_file)
    return MCPServerConfig(
        command=sys.executable,
        args=[str(_SERVER), "stdio", "0"],
        env=env,
        **limits,  # type: ignore[arg-type]
    )


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_call_timeout_is_per_server():
    """SC1: a tool slower than call_timeout_s fails naming the server and the field, and the
    same server answers the next call — the cancelled call didn't take the session down."""
    manager = MCPManager({})
    try:
        manager.start_server("slow", _extra_cfg(call_timeout_s=1.0), timeout=30.0)
        t0 = time.monotonic()
        with pytest.raises(MCPTimeout) as excinfo:
            manager.call_tool("slow", "sleep_for", {"seconds": 10})
        elapsed = time.monotonic() - t0
        assert elapsed < 6
        message = str(excinfo.value)
        assert "'slow'" in message
        assert "call_timeout_s" in message
        assert "2" in manager.call_tool("slow", "add", {"a": 1, "b": 1})
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_call_under_budget_succeeds():
    """A call that finishes inside call_timeout_s is unaffected by the budget existing."""
    manager = MCPManager({})
    try:
        manager.start_server("slow2", _extra_cfg(call_timeout_s=10.0), timeout=30.0)
        assert manager.call_tool("slow2", "sleep_for", {"seconds": 0.5}) == "slept"
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_call_during_reconnect_backoff_names_reconnecting(tmp_path, monkeypatch):
    """A call issued mid-backoff gets 'is reconnecting' (MCPServerUnavailable), not a timeout —
    even with a very short call_timeout_s, precedence must not race the reconnect state."""
    import agent86.tools.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "_reconnect_backoff", lambda attempt: 4.0)
    cfg = _extra_cfg(pid_file=str(tmp_path / "r.pid"), call_timeout_s=0.5)
    manager = MCPManager({})
    try:
        manager.start_server("r", cfg, timeout=30.0)
        pid = _read_pid(tmp_path / "r.pid")
        _kill(pid)

        assert _wait_until(lambda: manager._server_state.get("r") == "reconnecting", 20.0)

        t0 = time.monotonic()
        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("r", "add", {"a": 1, "b": 1})
        elapsed = time.monotonic() - t0
        assert not isinstance(excinfo.value, MCPTimeout)
        assert "is reconnecting" in str(excinfo.value)
        assert elapsed < 1.0

        assert _wait_until(lambda: "r" in manager._sessions, 30.0)
        assert "2" in manager.call_tool("r", "add", {"a": 1, "b": 1})
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_oversized_result_truncates_at_max_result_chars():
    """SC2: an oversized result is cut at the configured max_result_chars with a visible marker."""
    manager = MCPManager({})
    try:
        manager.start_server("cap", _extra_cfg(max_result_chars=100), timeout=30.0)
        out = manager.call_tool("cap", "big_text", {"n": 5000})
        assert out.startswith("x" * 100)
        assert "…[truncated 4900 chars" in out
        # The visible body (before the marker line) is exactly the 100-char cut — not the whole
        # output, which also contains a few 'x's inside "max_result_chars" in the marker text.
        assert out.split("\n", 1)[0] == "x" * 100
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_default_cap_is_8000():
    """SC2's default: no max_result_chars configured still caps at 8000 (ADR 0004)."""
    manager = MCPManager({})
    try:
        manager.start_server("cap2", _extra_cfg(), timeout=30.0)
        out = manager.call_tool("cap2", "big_text", {"n": 9000})
        assert "…[truncated 1000 chars" in out
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_image_content_block_renders_marker():
    """SC3: a real ImageContent block renders as a marker, never inlined base64 or a repr."""
    import base64

    from tests.integration.live_mcp_server import IMAGE_BYTES

    manager = MCPManager({})
    try:
        manager.start_server("blocks", _extra_cfg(), timeout=30.0)
        out = manager.call_tool("blocks", "tiny_image", {})
        assert out.startswith("[image content: mime_type=image/png base64_len=")
        assert base64.b64encode(IMAGE_BYTES).decode() not in out
        assert "ImageContent(" not in out
        assert "data=" not in out
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_audio_content_block_renders_marker():
    """SC3, the audio analogue of the image test above."""
    import base64

    from tests.integration.live_mcp_server import AUDIO_BYTES

    manager = MCPManager({})
    try:
        manager.start_server("blocks3", _extra_cfg(), timeout=30.0)
        out = manager.call_tool("blocks3", "tiny_audio", {})
        assert out.startswith("[audio content: mime_type=audio/wav base64_len=")
        assert base64.b64encode(AUDIO_BYTES).decode() not in out
        assert "AudioContent(" not in out
        assert "data=" not in out
    finally:
        manager.close()


@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_real_stdio_embedded_and_link_blocks_render_markers():
    """SC3: a real EmbeddedResource (binary) and a real ResourceLink both render as markers,
    mixed in the same result alongside plain text."""
    import base64

    manager = MCPManager({})
    try:
        manager.start_server("blocks2", _extra_cfg(), timeout=30.0)
        out = manager.call_tool("blocks2", "mixed_blocks", {})
        lines = out.splitlines()
        assert lines[0] == "before"
        assert (
            "[embedded resource uri=res://agent86/blob.bin "
            "mime_type=application/octet-stream base64_len=" in out
        )
        assert "— not inlined]" in out
        assert (
            "[resource link uri=res://agent86/greeting.txt name=greeting mime_type=text/plain"
            in out
        )
        assert base64.b64encode(b"agent86-embedded-probe").decode() not in out
        assert "EmbeddedResource(" not in out
    finally:
        manager.close()
