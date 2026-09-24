---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 03
subsystem: tools
tags: [mcp, asyncio, reconnect, backoff, reliability]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 01
    provides: "_serve_once/_serve split, _SessionEnd, _on_drop, _server_state/_disconnect_cause/_reconnect_attempt fields, _MAX_RECONNECT_ATTEMPTS constant, the exact 'reconnecting' _unavailable_error message"
provides:
  - "A dropped transport is retried up to _MAX_RECONNECT_ATTEMPTS times with exponential backoff and equal jitter before the manager gives up (SC3, MCP-23)"
  - "A successful reconnect re-populates _server_tools from a fresh list_tools() and server_capabilities read, and resets the retry budget for the next outage"
  - "stop_server()/close() — including one issued mid-backoff-sleep — are never retried and return promptly (Pitfall 2 closed)"
affects: [12-04-registry-sync, 12-05-live-kill-integration-test, 12-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_reconnect_backoff duplicates cognitive/retry.py's backoff_delay formula locally rather than importing across the Tools -> Cognitive tier boundary (research Open Question 3, ruled: duplicate)"
    - "The backoff sleep is asyncio.wait_for(close_event.wait(), timeout=delay), never time.sleep or asyncio.sleep — a stop_server()/close() issued mid-backoff wakes the task immediately via close_event and ends it without retrying"
    - "_serve references _MAX_RECONNECT_ATTEMPTS and _reconnect_backoff as bare module globals (not self.-qualified) so tests can monkeypatch mcp_client._MAX_RECONNECT_ATTEMPTS / mcp_client._reconnect_backoff and have the running loop pick up the patched value on its next read"

key-files:
  created: []
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py

key-decisions:
  - "Secrets are NOT re-resolved per reconnect attempt (non-goal, stated in the _serve docstring) — cfg was resolved once by start_server()'s _resolve_server_secrets; rotating credentials are workstream B's (OAuth) concern, not this phase's."
  - "Reconnect bounds (_MAX_RECONNECT_ATTEMPTS, _RECONNECT_BASE_DELAY_S=0.5, _RECONNECT_MAX_DELAY_S=30.0) are hardcoded module constants, not a new MCPServerConfig field — per-server timeout/retry config is MCP-21's ruling, consistent with the existing hardcoded 30s/120s precedent in this file."
  - "The backoff formula is duplicated locally rather than imported from agent86.cognitive.retry.backoff_delay — there is no existing tools/ -> cognitive/ import anywhere in the codebase, and this phase does not introduce the first one. The ~9-line pure function is cheap to duplicate; a comment in _reconnect_backoff's docstring credits the source."
  - "A pre-existing plan-12-01 unit test (test_death_eof_clears_sessions_and_tools) needed a one-line fix: its fake transport's single _Up attempt is reused on every retry per _DyingTransport's own 'the last element repeats' contract, so under the new default _MAX_RECONNECT_ATTEMPTS=5 the server now reconnects successfully instead of the task ever reaching .done(). Pinned _MAX_RECONNECT_ATTEMPTS=0 in that one test via monkeypatch so it stays a pure SC1 (death observed, both dicts cleared, task ends) regression guard, unaffected by reconnect."

requirements-completed: [MCP-23]

# Metrics
duration: ~20min
completed: 2026-09-24
---

# Phase 12 Plan 03: Bounded reconnect after a dropped transport Summary

**A server killed mid-session no longer stays dead for the rest of the process — `_serve` now retries the connection up to `_MAX_RECONNECT_ATTEMPTS` (default 5) times with exponential backoff and equal jitter, re-mounting a fresh tool set on success and giving up cleanly (same "disconnected" state 12-01 already produces) if every attempt fails, while a deliberate `stop_server()`/`close()` — even one issued mid-backoff-sleep — is never mistaken for a drop worth retrying.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 (RED reconnect tests, then the bounded retry loop implementation)
- **Files modified:** 2 (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`)

## Accomplishments

- **SC3 — bounded retries with backoff, fresh repopulation on success.** `_serve` (previously a single-shot connect-then-park-then-end task, per plan 12-01) is now a `while True` loop around `_serve_once`: a post-connect drop resets the attempt counter to a fresh budget (`attempt = 0`) before incrementing, retries `_MAX_RECONNECT_ATTEMPTS` times with `_reconnect_backoff(attempt)` seconds of jittered exponential backoff between attempts (same equal-jitter shape as `agent86.cognitive.retry.backoff_delay`, duplicated locally per the plan's Open Question 3 ruling — no Tools→Cognitive import exists anywhere in the codebase and this phase doesn't introduce the first one), and gives up with a named note (`"...did not reconnect after N attempts: <cause>"`) if every attempt fails. `_serve_once` gained a `reconnecting: bool = False` keyword: on a successful reconnect it clears `_reconnect_attempt`/`_disconnect_cause`, records `"MCP server '{name}' reconnected; {n} tool(s) re-registered."`, and calls `_emit_tools_changed(name, [], tools)` — the fresh `list_tools()` and `server_capabilities` read happen for free because every attempt (first connect or reconnect) runs the exact same connect body.
- **Pitfall 2 closed — a deliberate stop is never retried, including mid-backoff.** The backoff sleep is `asyncio.wait_for(close_event.wait(), timeout=_reconnect_backoff(attempt))`, never `time.sleep`/bare `asyncio.sleep` — a `stop_server()`/`close()` issued while a server is backing off sets `close_event`, which wakes the `wait_for` immediately (no `TimeoutError`), and `_serve` returns without another connect attempt. `stop_server` needed no code change: it already sets `close_event` synchronously and pops `_server_state`/`_disconnect_cause`/`_reconnect_attempt` before awaiting the task, so a stop issued mid-backoff both returns promptly (verified `<2s` against a 5s-patched backoff) and leaves no reconnecting state behind.
- **A connect-time failure on a genuine reconnect attempt is distinguished from a post-connect drop.** `_serve_once` only raises (rather than returning a `_SessionEnd`) when `connected` was never set `True` for that attempt — so a reconnect attempt that fails to even open the transport propagates as a `BaseException` into `_serve`'s outer `try`, which (since `ready` is already resolved from the original first connect) treats it as another failed attempt against the same budget rather than calling `_on_drop` a second time.
- **Non-goal stated explicitly, per the plan.** `_serve`'s docstring states secrets are NOT re-resolved per reconnect attempt — `cfg` was resolved once by `start_server()`'s `_resolve_server_secrets`; rotating credentials are workstream B's (OAuth) concern, out of this phase's scope.
- **Eleven new unit tests** (`test_reconnect_*`) pin: tools restored after a drop, fresh `list_tools()`/capabilities repopulation, bounded give-up with the exact attempt-count note text, a per-attempt "reconnecting (attempt N of M)" note trail, the `MCPServerUnavailable` message naming the server and saying "is reconnecting" while a retry is pending, a mid-backoff `stop_server()` returning promptly with no further connect, `stop_server()` with no prior drop never triggering "reconnecting", an unchanged first-connect-failure-raises-no-retry contract, `on_tools_changed` firing `(removed=[old], added=[])` then `(removed=[], added=[new])` in that order, a fresh budget after a first successful reconnect (proven by a *second* outage also succeeding under a 1-attempt budget), and the pure `_reconnect_backoff` formula's bounds/jitter arithmetic.

## Task Commits

1. **Task 1: RED reconnect tests** — `3052c8a` (test) — eleven `test_reconnect_*` tests added; all fail (or fail collection-safely at the monkeypatch call, since `_reconnect_backoff` did not exist yet) ahead of Task 2.
2. **Task 2: Bounded reconnect loop in `_serve`, with local backoff and reconnect emission** — `4ce7157` (feat) — `_reconnect_backoff`, the rewritten `_serve`, the `_serve_once(reconnecting=...)` mount-time emission, and one necessary fix to a plan-12-01 test whose assumptions the new retry loop correctly invalidates (see Deviations).

**Plan metadata:** (this commit) `docs(12-03): complete bounded reconnect plan`

## Files Created/Modified

- `src/agent86/tools/mcp_client.py` — `import random`; `_RECONNECT_BASE_DELAY_S`/`_RECONNECT_MAX_DELAY_S` constants beside `_MAX_RECONNECT_ATTEMPTS`; new `_reconnect_backoff(attempt, *, jitter=None)`; `_serve_once` gained `reconnecting: bool = False` and the post-mount reconnect-emission block; `_serve` replaced with the bounded retry loop described above.
- `tests/unit/test_mcp.py` — eleven `test_reconnect_*` tests plus a `_patch_reconnect(monkeypatch, *, max_attempts=3, backoff=...)` helper; one existing plan-12-01 test (`test_death_eof_clears_sessions_and_tools`) pinned to `_MAX_RECONNECT_ATTEMPTS=0` to stay a pure no-retry SC1 regression guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/regression] Fixed a plan-12-01 test invalidated by the new reconnect behavior**
- **Found during:** Task 2, running the full `tests/unit/test_mcp.py` suite after implementing the retry loop.
- **Issue:** `test_death_eof_clears_sessions_and_tools` asserted `manager._tasks["srv"].done()` immediately after a death — true under plan 12-01 (no retry, the task always ends on a drop), but no longer true under plan 12-03's default `_MAX_RECONNECT_ATTEMPTS = 5`: the test's `_DyingTransport` was constructed with a single `_Up(...)` entry, and per `_DyingTransport`'s own documented contract ("an Exception element in `attempts` makes that connect raise; the last element repeats"), every reconnect attempt reuses that same successful attempt — so the server now reconnects successfully instead of the task ever finishing, and the assertion failed (`assert False`).
- **Fix:** Pinned `monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", 0)` at the top of that one test, restoring the "give up immediately, no retry" behavior the test was actually exercising (SC1: death is observed, both `_sessions`/`_server_tools` clear in the same `finally`, and the task ends) — matching the plan's own stated pattern for tests that want 12-01-equivalent behavior ("With `_MAX_RECONNECT_ATTEMPTS = 0` ... the loop gives up at once and behaviour equals plan 12-01's").
- **Files modified:** `tests/unit/test_mcp.py`
- **Commit:** `4ce7157`

**2. [Rule 1 - Lint] Two `ruff format` line-length fixes in newly added code**
- **Found during:** Task 2, pre-commit `ruff format --check`.
- **Issue:** `_reconnect_backoff`'s signature line and one new test's lambda exceeded 100 columns.
- **Fix:** Wrapped the signature across three lines; wrapped the lambda's comparison in parentheses across two lines. Both are new code from this plan — the pre-existing, already-logged `deferred-items.md` format debt (two spots in `MCPTool.__init__`/`spec()`, one in `_unavailable_error`'s "connected" message, one in a plan-12-01 test) was left untouched, per the project's established precedent of not mass-reformatting out-of-scope files.
- **Files modified:** `src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`
- **Commit:** `4ce7157`

**3. [Test-only, not a deviation rule] One `_wait_until` predicate race in a test I wrote**
- **Found during:** Task 2, verifying the new tests were stable across repeated runs.
- **Issue:** `test_reconnect_after_drop_restores_tools` originally waited only on `"srv" in manager._sessions`, which could be trivially true immediately after `kill()` (the stale pre-kill session entry hadn't been popped yet) — a false-positive race, not a production defect.
- **Fix:** Combined the predicate with `transport.connects == 2` so the wait genuinely settles on the post-reconnect state. Verified stable across 5 consecutive runs before and after.
- **Files modified:** `tests/unit/test_mcp.py`

## Issues Encountered

None beyond the two documented above.

## Known Stubs

None. This plan's scope (SC3, MCP-23) is fully wired end to end — the retry loop, backoff, repopulation, and give-up paths are all live code exercised by the eleven new tests plus the pre-existing integration suite; no placeholder data paths were introduced.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 12-06 (or whichever plan closes out phase 12) can rely on `_MAX_RECONNECT_ATTEMPTS = 0` as the documented pattern for any test/integration fixture that wants plan-12-01-equivalent (no-retry) behavior — already used by both this plan's own `test_reconnect_gives_up_after_bounded_attempts`-style tests (via the `_patch_reconnect` helper's `max_attempts` override) and by 12-05's real-stdio integration test per the plan's own note.
- Verification green: `pytest tests/unit/test_mcp.py -q` (70 passed, up from 59 in 12-01), `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` (17 passed, unmodified files), `pytest tests/integration/test_scripting_contract.py -q` (19 passed), `mypy src/agent86` clean, `ruff check .` clean. `ruff format --check` reports only pre-existing, previously-logged debt untouched by this plan.
- No blockers for parallel plans 12-04 (registry sync) or 12-05 (live-kill integration fixture) — this plan touched only `src/agent86/tools/mcp_client.py` and `tests/unit/test_mcp.py`, per the parallel-execution file-ownership split; `git status --porcelain` outside those two files stayed empty throughout.

## Self-Check: PASSED

- FOUND: `src/agent86/tools/mcp_client.py`
- FOUND: `tests/unit/test_mcp.py`
- FOUND commit `3052c8a` (test(12-03): add failing reconnect tests for bounded retry (MCP-23))
- FOUND commit `4ce7157` (feat(12-03): bounded reconnect loop in _serve with local backoff (MCP-23))

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
