"""Plan 12-08 Task 3 — MCP notes push live into the TUI transcript.

A note added to the live `MCPManager` after mount (a disconnect, a reconnect, a repeat outage)
must reach the transcript on its own — even while the app is otherwise idle — via
`Harness.on_mcp_note` -> `Agent86App._post_mcp_note` -> `App.post_message(McpNote(...))`.
"""

from __future__ import annotations

import asyncio
import threading

from textual.widgets import RichLog

from agent86.config import load_config
from agent86.orchestration.loop import Harness
from agent86.tui.app import Agent86App
from agent86.ui.repl import _Repl
from tests.support import make_text_provider


def _make_repl(tmp_path):
    cfg = load_config()
    harness = Harness(cfg, provider=make_text_provider("hi there"), memory=None, workspace=tmp_path)
    return _Repl(cfg, resume=None, harness=harness)


async def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.02) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition not met within timeout")


def _transcript_lines(app) -> str:
    transcript = app.query_one("#transcript", RichLog)
    return "\n".join(str(line) for line in transcript.lines)


async def test_mcp_note_from_another_thread_appears_in_transcript(tmp_path):
    repl = _make_repl(tmp_path)
    manager = repl.harness.ensure_mcp()  # starts no background loop — no real transport needed
    app = Agent86App(repl)
    async with app.run_test() as pilot:
        await pilot.pause()

        note = "MCP server 'live' disconnected ([x]); reconnecting (attempt 1 of 5)."

        def _emit() -> None:
            manager._add_note(note)
            manager._add_note(note)

        threading.Thread(target=_emit, daemon=True).start()

        await _wait_until(
            lambda: _transcript_lines(app).count(
                "mcp: MCP server 'live' disconnected ([x]); reconnecting (attempt 1 of 5)."
            )
            == 2
        )


async def test_mcp_note_listener_detached_on_unmount(tmp_path):
    repl = _make_repl(tmp_path)
    repl.harness.ensure_mcp()
    app = Agent86App(repl)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert repl.harness.on_mcp_note is not None

    assert repl.harness.on_mcp_note is None
