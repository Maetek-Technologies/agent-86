"""Plan 12-08 Task 3 — `/tools` non-connected server state and the plain loop's note drain.

Headless (no TUI, no real MCP transport): a real `MCPManager` with its private state dicts set
directly stands in for a server that is reconnecting/disconnected, matching
`tests/integration/test_repl.py`'s own `_repl` pattern.
"""

from __future__ import annotations

from agent86.config import load_config
from agent86.orchestration.loop import Harness
from agent86.tools.mcp_client import MCPManager
from agent86.ui.repl import _Repl
from tests.support import make_text_provider


def _repl(tmp_path):
    cfg = load_config()
    harness = Harness(cfg, provider=make_text_provider("hi there"), memory=None, workspace=tmp_path)
    return _Repl(cfg, resume=None, harness=harness), harness


# ---- `/tools` non-connected server state ------------------------------------------------- #


def test_tools_command_shows_non_connected_server_state(tmp_path):
    from agent86.tui.commands import handle_command

    repl, harness = _repl(tmp_path)
    manager = MCPManager({})
    manager._server_state["live"] = "reconnecting"
    manager._reconnect_attempt["live"] = 2
    manager._disconnect_cause["live"] = "boom"
    harness.mcp = manager

    render = handle_command(repl, "/tools").render
    assert "mcp live: reconnecting (attempt 2 of 5): boom" in render


def test_tools_command_unchanged_without_mcp(tmp_path):
    from agent86.tui.commands import _tools_render, handle_command

    repl, harness = _repl(tmp_path)
    harness.mcp = None

    render = handle_command(repl, "/tools").render
    assert render == _tools_render(repl)
    assert render.startswith("tools: ")
    assert "\n" not in render


# ---- `_Repl.pending_mcp_notes` ------------------------------------------------------------ #


def test_pending_mcp_notes_skips_startup_and_surfaces_repeats(tmp_path):
    manager = MCPManager({})
    manager._add_note("MCP server 'live' failed to start: boom")  # before _Repl construction

    cfg = load_config()
    harness = Harness(cfg, provider=make_text_provider("hi"), memory=None, workspace=tmp_path)
    harness.mcp = manager
    repl = _Repl(cfg, resume=None, harness=harness)

    # The pre-existing note is startup's job (`startup_notes`), not this cursor's.
    assert repl.pending_mcp_notes() == []

    manager._add_note("MCP server 'live' disconnected (x); reconnecting (attempt 1 of 5).")
    assert repl.pending_mcp_notes() == [
        "mcp: MCP server 'live' disconnected (x); reconnecting (attempt 1 of 5)."
    ]
    assert repl.pending_mcp_notes() == []  # drained

    # A repeat of the exact same text is surfaced again, not swallowed by the notes dedup.
    manager._add_note("MCP server 'live' disconnected (x); reconnecting (attempt 1 of 5).")
    assert repl.pending_mcp_notes() == [
        "mcp: MCP server 'live' disconnected (x); reconnecting (attempt 1 of 5)."
    ]


def test_pending_mcp_notes_resets_on_manager_swap(tmp_path):
    repl, harness = _repl(tmp_path)

    old = MCPManager({})
    harness.mcp = old
    old._add_note("old note")
    assert repl.pending_mcp_notes() == ["mcp: old note"]

    new = MCPManager({})
    harness.mcp = new
    new._add_note("new note")
    # A stale cursor from `old` must not be read against `new`'s (unrelated) sequence numbers.
    assert repl.pending_mcp_notes() == ["mcp: new note"]


# ---- plain loop drain --------------------------------------------------------------------- #


def test_plain_loop_prints_pending_mcp_note_before_prompt(tmp_path, monkeypatch):
    import io

    from rich.console import Console

    from agent86.ui import repl as repl_mod

    repl, harness = _repl(tmp_path)
    manager = MCPManager({})
    harness.mcp = manager
    manager._add_note("MCP server 'live' disconnected (x); reconnecting (attempt 1 of 5).")

    # Redirect the module's own console to a StringIO: Rich's output does not always flush
    # through pytest's `capsys` reliably, and this is what the plain loop actually prints to.
    buf = io.StringIO()
    monkeypatch.setattr(repl_mod, "console", Console(file=buf, width=200))

    def _raise_eof(prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    repl.plain_loop()  # prints the pending note, then exits on the immediate EOFError

    assert "mcp: MCP server 'live' disconnected" in buf.getvalue()
