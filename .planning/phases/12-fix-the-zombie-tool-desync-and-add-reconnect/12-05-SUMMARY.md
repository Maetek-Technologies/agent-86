---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 05
subsystem: testing
tags: [mcp, stdio, integration-test, death-detection, process-kill]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    provides: "plan 12-01's _EOFWatchStream death detection, _unavailable_error(server, cause), _MAX_RECONNECT_ATTEMPTS module constant"
provides:
  - "A committed CI test that kills a REAL live_mcp_server.py stdio subprocess mid-session and asserts the owning task exits, tools_for()/tools() empty, call_tool/MCPTool both raise naming the server, a sibling server keeps answering, and a disconnect note is recorded — MCP-26 SC1+SC2 proven against the research's own empirical repro, not only a fake transport"
  - "An opt-in AGENT86_LIVE_MCP_PID_FILE hook in the shared live fixture, letting any future lifecycle test (e.g. plan 12-06's reconnect-after-real-kill case) find and kill the fixture's own PID without changing its served tool/resource/prompt surface"
affects: [12-06-reconnect-after-real-kill]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Opt-in pid-file hook via cfg.env, not a new tool — keeps every exact-tool-name-set assertion in the fixture's other tests untouched"
    - "monkeypatch.setattr(mcp_client, \"_MAX_RECONNECT_ATTEMPTS\", 0) pins the pre-reconnect 'dead and gone' outcome so this test's assertions hold whether or not 12-03's reconnect loop has landed yet"

key-files:
  created: []
  modified:
    - tests/integration/live_mcp_server.py
    - tests/integration/test_mcp_client.py

key-decisions:
  - "Used signal.SIGTERM (mapped to TerminateProcess on Windows, a hard kill) rather than SIGKILL, since SIGKILL doesn't exist on Windows and the research's own probe used Stop-Process -Force, which SIGTERM-on-Windows is equivalent to."
  - "Bound the wait to _wait_until(predicate, 20.0) polling every 0.05s rather than a single sleep, matching the plan's bounded-wait requirement and avoiding a flaky fixed delay."

requirements-completed: [MCP-26]

# Metrics
duration: ~5min
completed: 2026-09-24
---

# Phase 12 Plan 05: Real-stdio kill-mid-session test Summary

**A killed `live_mcp_server.py` stdio subprocess now has a committed CI regression test proving MCP-26's death-detection fix against a real process kill, not only a fake transport — the exact scenario the phase's own research script found hanging before plan 12-01's fix.**

## Performance

- **Duration:** ~5 min (commits 11:33–11:35 local time)
- **Tasks:** 2
- **Files modified:** 2 (`tests/integration/live_mcp_server.py`, `tests/integration/test_mcp_client.py`)

## Accomplishments

- **Opt-in pid file, tool set unchanged (Task 1).** `live_mcp_server.py`'s `main()` now writes its own PID to `AGENT86_LIVE_MCP_PID_FILE` (when set) immediately before `mcp.run(...)`. No tool, resource, prompt, or completion handler was added — the fixture's `@mcp.tool()` count stayed at 3, so every existing exact-tool-name-set assertion in `test_mcp_client.py` and `test_mcp_live.py` still passes unmodified.
- **The research's real-kill repro is now a passing CI test (Task 2).** `test_mid_session_kill_unregisters_tools_and_names_server` starts two real stdio servers ("alpha" with the pid-file hook, "beta" plain), reads alpha's PID from the file, sends it a hard kill (`SIGTERM`/`SIGKILL` via `os.kill`), and within a 20s bounded wait asserts: `manager.tools_for("alpha") == []` and `manager._tasks["alpha"].done()`; `"alpha" not in manager._sessions`; no `mcp__alpha__*` tool remains in `manager.tools()`; `manager.call_tool("alpha", ...)` raises a `RuntimeError` naming `'alpha'`; a pre-kill `MCPTool.run()` for alpha returns `ok=False` with `'alpha'` in `.error`; `manager.call_tool("beta", "add", ...)` still answers `"2"`; and a note containing `"MCP server 'alpha' disconnected"` was recorded. `_MAX_RECONNECT_ATTEMPTS` is monkeypatched to `0` so the assertions hold regardless of whether plan 12-03's reconnect loop has landed in this shared tree yet (verified: it passed both before and after 12-03 committed its own changes to `mcp_client.py`/`tests/unit/test_mcp.py` during this plan's execution).
- **No architectural surprises.** The end-of-stream death signal from plan 12-01 (`_EOFWatchStream`) fired correctly on a real killed stdio process — no blocker, no weakened assertion, matching what the phase's own research already empirically verified in a throwaway scratchpad script. This plan turns that scratchpad probe into a permanent, committed regression test.

## Task Commits

1. **Task 1: Opt-in pid file in the live fixture (no tool-set change)** - `eb52c4b` (feat)
2. **Task 2: Real-stdio kill-mid-session test (SC1 + SC2 against the real failure mode)** - `ba00ebe` (test)

**Plan metadata:** (this commit) `docs(12-05): complete real-stdio kill-mid-session plan`

## Files Created/Modified

- `tests/integration/live_mcp_server.py` — `main()` now writes its PID to `AGENT86_LIVE_MCP_PID_FILE` (if set) right before serving; one docstring sentence documents the hook. `from pathlib import Path` added.
- `tests/integration/test_mcp_client.py` — new helpers `_pid_cfg`, `_read_pid`, `_kill`, `_wait_until`, and `test_mid_session_kill_unregisters_tools_and_names_server`; `contextlib`, `os`, `signal`, `time` imports added.

## Decisions Made

- `SIGTERM` (not `SIGKILL`) is the kill signal — Windows has no `SIGKILL`, and `signal.SIGTERM` on Windows maps to `TerminateProcess`, the same hard-kill semantics the research's `Stop-Process -Force` used. `getattr(signal, "SIGKILL", signal.SIGTERM)` picks real `SIGKILL` on POSIX.
- A 20-second bounded poll (`_wait_until`, 0.05s interval) rather than a fixed sleep, so the test is neither flaky under load nor slower than necessary once the condition is met.

## Deviations from Plan

None — plan executed exactly as written. Two ruff-flagged formatting issues (one `E501` line-too-long, one `ruff format` line-wrap) were fixed before the Task 2 commit — routine formatting, not a deviation.

## Issues Encountered

None. The parallel-tree note in the plan (wait for 12-03's `mcp_client.py` commit if a failure traces into a mid-edit) never triggered — this plan's test passed on first run and was re-verified passing again after 12-03 landed its own commit to `mcp_client.py`/`tests/unit/test_mcp.py` during this plan's execution window, confirming no cross-plan interference.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 12-06 (reconnect-after-real-kill) can reuse `_pid_cfg`/`_read_pid`/`_kill`/`_wait_until` directly and simply remove the `_MAX_RECONNECT_ATTEMPTS = 0` monkeypatch to observe a real reconnect instead of a permanent drop.
- Verified green: `pytest tests/integration/test_mcp_client.py -q -k mid_session -x` (1 passed), `pytest tests/integration/test_mcp_client.py -q -k "teardown or partial_stop"` (2 passed, `git diff` confirms those two functions are additions-only/untouched), `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` (17 passed), `ruff check`/`ruff format --check` clean on both owned files.
- No blockers for 12-03 (bounded reconnect) or 12-04 (registry sync), both of which were editing `src/agent86/tools/mcp_client.py`/`src/agent86/orchestration/loop.py` concurrently in this shared tree — neither file was touched by this plan.

## Self-Check: PASSED

- FOUND: `tests/integration/live_mcp_server.py`
- FOUND: `tests/integration/test_mcp_client.py`
- FOUND commit `eb52c4b` (feat(12-05): opt-in pid file in live_mcp_server.py fixture)
- FOUND commit `ba00ebe` (test(12-05): real-stdio kill-mid-session test proves MCP-26 SC1+SC2)

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
