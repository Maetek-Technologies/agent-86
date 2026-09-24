---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
verified: 2026-09-24T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 12: Fix the zombie-tool desync and add reconnect Verification Report

**Phase Goal:** A server that dies mid-session has its tools unregistered rather than left
callable-but-broken, and a dropped transport reconnects instead of ending the task permanently.
**Verified:** 2026-09-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | A server death (real end-of-stream, not the unreachable `except BaseException` path research corrected for) pops `_sessions[name]` and `_server_tools[name]` in the same `finally` | ✓ VERIFIED | `src/agent86/tools/mcp_client.py:956-976` — `_serve_once`'s single `finally` pops both dicts on every exit path; `_EOFWatchStream` (line 348) is the death signal, wired at `read = _EOFWatchStream(streams[0], died.set)` (line 889) |
| 2 | `tools_for()`/`tools()` stop listing a dead server's tools, including Phase 11 capability tools | ✓ VERIFIED | Same pop clears `_server_tools[name]`; `tools()` (line 1080-1083) reads only `_server_tools`; capability tools are appended into the same `tools` list before mounting (line 912-914), so they die with it. Proven live: `test_death_clears_capability_tools_too` and the real-process `test_mid_session_kill_unregisters_tools_and_names_server` (tests/integration/test_mcp_client.py:336) both pass |
| 3 | The desync also extends to `Harness.registry` — the tools the model is actually offered | ✓ VERIFIED | `Harness._on_mcp_tools_changed` (loop.py:398) + `_wire_mcp` (loop.py:369, wired at both `__init__` and `ensure_mcp`) route every drop/reconnect through `ToolRegistry.unregister_tool`/`try_register`. 6 tests in `test_loop.py::test_mcp_tools_changed_*` all pass, including collision-safety and never-raise |
| 4 | A model calling a tool of a dead server receives a message naming the dead server, not a generic "MCP session not available" | ✓ VERIFIED | `grep -rn "MCP session not available"` across `src/` and `tests/` returns zero matches. `_unavailable_error` (mcp_client.py:1105) is the single source of every such message, and always includes `'{server}'` in quotes. 4 `test_named_server_*` tests pass |
| 5 | `_serve` retries a dropped transport a bounded number of times with backoff before giving up | ✓ VERIFIED | `_serve` (mcp_client.py:979) loops with `attempt`/`_MAX_RECONNECT_ATTEMPTS=5`, sleeping via `asyncio.wait_for(close_event.wait(), timeout=_reconnect_backoff(attempt))` — never `time.sleep`, so a `stop_server()` mid-backoff wakes immediately. 11 `test_reconnect_*` unit tests plus real-process `test_mid_session_kill_reconnects_with_fresh_tools` and the SSE/streamable-HTTP `test_live_transport_mid_session_kill_is_detected` all pass |
| 6 | A successful reconnect re-populates `_server_tools` from a fresh `list_tools()` and a fresh `server_capabilities` read | ✓ VERIFIED | `_serve_once` re-runs the entire connect body (including `session.list_tools()` and `getattr(session, "server_capabilities", None)`) on every attempt, `reconnecting` flag included (mcp_client.py:895-927). `test_reconnect_repopulates_from_fresh_list_tools_and_capabilities` passes |
| 7 | Every existing test, mypy, and ruff stay green (compatibility, lazy imports, scripting contract) | ✓ VERIFIED | `pytest -q` (isolated HOME/USERPROFILE) → 1319 passed, 0 failed; `mypy src/agent86` clean (93 files); `ruff check .` clean; `tests/integration/test_scripting_contract.py` 19/19 passed |
| 8 | A human watched a real server death and reconnect in the interactive TUI, including the notes appearing live | ✓ VERIFIED (documented) | `12-07-SUMMARY.md` "Task 3 verification history" records three attempts, the second surfacing a genuine gap (notes only rendered at mount) closed by plan 12-08, and the third approved by the user 2026-09-24. This is asserted, not independently re-run by this verifier — see Human Verification note below |

**Score:** 8/8 truths verified (7 by direct code/test inspection, 1 — human TUI approval — accepted on the documented record per the phase's own sign-off, not independently re-executed)

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/agent86/tools/mcp_client.py::_EOFWatchStream` | Transport-agnostic end-of-stream death signal | ✓ VERIFIED | Line 348, wraps the read stream one layer above `ClientSession` |
| `src/agent86/tools/mcp_client.py::MCPServerUnavailable` | Named RuntimeError subclass | ✓ VERIFIED | Line 81, `self.server` attribute, subclasses RuntimeError |
| `src/agent86/tools/mcp_client.py::_serve_once`/`_serve` split | One-connection-attempt vs. lifetime-owning task | ✓ VERIFIED | Lines 839 / 979 |
| `src/agent86/tools/mcp_client.py::_reconnect_backoff` | Bounded jittered backoff | ✓ VERIFIED | Line 67; `_MAX_RECONNECT_ATTEMPTS = 5` at line 44 |
| `src/agent86/tools/mcp_client.py::on_tools_changed`/note-listener API | Registry-sync + live-note hooks | ✓ VERIFIED | `add_note_listener`/`remove_note_listener`/`notes_since`/`server_status`/`server_statuses` all present (lines 705-762) |
| `src/agent86/tools/registry.py::unregister_tool` | RLock-guarded identity-checked removal | ✓ VERIFIED | Line 88; `self._lock = threading.RLock()` at line 53; lock never held during `tool.run()` (dispatch at line 115-128 releases before `.run`) |
| `src/agent86/orchestration/loop.py::_on_mcp_tools_changed`/`_wire_mcp` | Harness registry sync wiring | ✓ VERIFIED | Lines 369, 398; wired at `__init__` (204) and `ensure_mcp` (328) |
| `tests/unit/test_mcp.py` | Fake-transport death/named_server/reconnect tests | ✓ VERIFIED | `_DyingTransport` present; 6 death + 4 named_server + 11 reconnect + note-listener/start-failure tests, all pass |
| `tests/integration/test_mcp_client.py` | Real-process kill/reconnect tests | ✓ VERIFIED | `test_mid_session_kill_unregisters_tools_and_names_server`, `test_mid_session_kill_reconnects_with_fresh_tools` — both pass against a real subprocess |
| `tests/integration/test_mcp_live.py` | Real SSE/streamable-HTTP kill detection | ✓ VERIFIED | `test_live_transport_mid_session_kill_is_detected` passes |
| `tests/tui/test_mcp_notes.py`, `tests/integration/test_mcp_note_surfaces.py` | Live-note surfacing (gap closure) | ✓ VERIFIED | 7/7 pass |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `_serve_once` | `ClientSession(..., message_handler=...)` | read stream wrapped in `_EOFWatchStream` | ✓ WIRED | Line 889-893 |
| `call_tool`/`_on_session` | `MCPManager._unavailable_error` | guard + except path | ✓ WIRED | `call_tool` at ~1136 raises `self._unavailable_error(server)` on no session, and on exception when state != "connected" or connection-closed |
| `_serve` | `_serve_once` | while-loop with attempt counter + `asyncio.wait_for(close_event.wait(), timeout=...)` | ✓ WIRED | Line 1034 |
| `_serve_once` | `on_tools_changed` | `_emit_tools_changed(name, [], tools)` after reconnect | ✓ WIRED | Line 927 |
| `Harness.__init__` | `MCPManager.on_tools_changed` | `self._wire_mcp(self.mcp)` after `self.registry` built | ✓ WIRED | Line 204 |
| `Harness._on_mcp_tools_changed` | `ToolRegistry.unregister_tool`/`try_register` | identity-checked removal, lenient add | ✓ WIRED | Line 408 (`unregister_tool`), matching `try_register` for additions |
| `ToolRegistry.dispatch` | `tool.run` | lookup under lock, run outside it | ✓ WIRED | Line 115-128, confirmed `tool.run(call, ctx)` executes unindented from `with self._lock` |
| `MCPManager._add_note` | `Harness._forward_mcp_note` | `manager.add_note_listener(...)` in `_wire_mcp` | ✓ WIRED | Line 379 |
| `Harness.on_mcp_note` | `Agent86App.on_mcp_note` | `post_message(McpNote(text))` | ✓ WIRED | `tui/app.py:239-262` |
| `_Repl.pending_mcp_notes` | plain loop prompt | drained each iteration before `input("agent86> ")` | ✓ WIRED | `ui/repl.py:394` |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense (no dashboard/component consuming a fetched value); the
equivalent check here is "does a real death/reconnect actually flow through the wiring end to end,"
which is exactly what the real-process integration tests (`test_mid_session_kill_*`,
`test_live_transport_mid_session_kill_is_detected`) prove — a real subprocess is killed, a real SDK
transport ends, and the assertions read the manager's live state afterward. All pass.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite green with isolated HOME (no live user MCP server touched) | `USERPROFILE=$TEMP/a86home HOME=$TEMP/a86home python -m pytest -q` | 1319 passed, 14 deselected | ✓ PASS |
| Real stdio kill unregisters tools + names server | `pytest -q tests/integration/test_mcp_client.py -k mid_session_kill` | 2 passed | ✓ PASS |
| Real reconnect + SSE/HTTP kill detection | `pytest -q tests/integration/test_mcp_live.py -k mid_session_kill` | 2 passed (part of the 4 above) | ✓ PASS |
| Lint | `ruff check .` | All checks passed | ✓ PASS |
| Type-check | `mypy src/agent86` | Success: no issues found in 93 source files | ✓ PASS |
| Scripting contract / cold start unaffected | `pytest -q tests/integration/test_scripting_contract.py` | 19 passed | ✓ PASS |
| No lingering generic error string | `grep -rn "MCP session not available" src/ tests/` | 0 matches | ✓ PASS |
| Lazy-import constraint (Textual not imported by `run`/`--plain`) | inspected `cli.py`/`ui/repl.py`/`tui/commands.py` import sites | `textual`/`agent86.tui.app` imported only inside `run_repl`'s TUI branch (`ui/repl.py:488`, commented "lazy: textual imported only here"); `startup_notes`/`expand_mentions` imports from `agent86.tui.*` are explicitly commented "textual-free" | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | --------------- | ------------ | ------ | -------- |
| MCP-26 | 12-01, 12-02, 12-04, 12-05, 12-08 | Session/registry desync on server death fixed | ✓ SATISFIED | Death detection, both-dicts pop, named errors, real-process kill test, registry sync, live notes |
| MCP-23 | 12-03, 12-04, 12-06, 12-08 | Reconnect after a dropped transport | ✓ SATISFIED | Bounded backoff retry loop, real-process reconnect test, registry re-add, live reconnect notes |

REQUIREMENTS.md traceability table lists both `MCP-23 | Phase 12 | Complete` and
`MCP-26 | Phase 12 | Complete`; no requirement ID declared in any 12-0x plan frontmatter is missing
from REQUIREMENTS.md, and no requirement mapped to Phase 12 in REQUIREMENTS.md is absent from a
plan's `requirements` field. No orphaned requirements found.

### Anti-Patterns Found

None. Grep for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not yet implemented"/"not available" across the
phase's modified production files (`mcp_client.py`, `loop.py`, `registry.py`, `tui/app.py`,
`tui/messages.py`, `tui/commands.py`, `ui/repl.py`) returns only unrelated legitimate uses (a
docstring about session naming, and a `placeholder=` kwarg on a Textual widget).

### Human Verification Required

None outstanding. The one item that needed a human (TUI-live server death/reconnect, including
notes appearing without user interaction) is recorded as already completed and approved by the user
on 2026-09-24 in `12-07-SUMMARY.md`'s "Task 3 verification history" — including the honest account
of a first-attempt config issue and a second-attempt genuine gap (notes not live) that was closed by
plan 12-08 before the third, approved attempt. This verifier did not re-run that manual TUI session
(a live human-interaction verification cannot be re-executed by an automated pass), but the
documented trail is specific, dated, and consistent with the code inspected above (the
`add_note_listener`/`post_message(McpNote(...))` wiring that the second-attempt gap required does
exist in the current codebase, matching the fix described).

### Gaps Summary

None. All 8 derived observable truths (from ROADMAP success criteria + the phase's own
must_haves across 8 plans) are verified against the actual codebase, not just plan/SUMMARY claims:
death detection uses the correct signal (end-of-stream via `_EOFWatchStream`, matching the research
correction the phase directive called out — the `except BaseException` path is indeed not the
real mechanism, and the implementation correctly does not rely on it); both `MCPManager` state and
`Harness.registry` are kept in sync; errors name the dead server; reconnect is bounded, backed off,
and re-populates tools from a fresh listing; and the full test suite (1319 tests, including two
real-subprocess kill/reconnect integration tests and two real remote-transport kill tests), mypy,
and ruff are all clean. The executor's STATE.md "premature bookkeeping" note flagged in this
verification's instructions was checked independently rather than trusted — the codebase evidence
supports the completion claim.

---

_Verified: 2026-09-24_
_Verifier: Claude (gsd-verifier)_
