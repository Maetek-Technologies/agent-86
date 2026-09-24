---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 06
subsystem: testing
tags: [mcp, stdio, sse, streamable-http, reconnect, death-detection, integration-test]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 03
    provides: "The bounded reconnect loop in _serve (_MAX_RECONNECT_ATTEMPTS, _reconnect_backoff, the 'reconnected; N tool(s) re-registered' note text)"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 05
    provides: "_pid_cfg/_read_pid/_kill/_wait_until helpers and the opt-in AGENT86_LIVE_MCP_PID_FILE hook in live_mcp_server.py"
provides:
  - "SC3 (MCP-23) proven end-to-end against a REAL re-spawned stdio process, not just a fake transport or the earlier no-retry (attempts=0) kill test: killing a live server mid-session under the shipped default reconnect budget brings it back as a new process with a fresh list_tools()-derived tool set that is immediately callable"
  - "Research Open Question 4 answered with evidence for both remote transports: a killed real SSE server is detected passively (end-of-stream on the read side, no further call needed); a killed real streamable-HTTP server is detected on the next call (the POST failing into _serve_once's outer except) — both close within the 12-01 _EOFWatchStream-based detection seam, no transport-specific special case needed"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_pid_changed(path, old) is a tolerant poll predicate (never raises on missing/empty/partial/non-numeric pid-file content) — needed because the reconnect test polls a file a brand-new child process is actively (re)writing, unlike plan 12-05's single-read _read_pid which only runs once against an already-stable file"
    - "_spawn_live_server mirrors the live_server fixture's launch/wait/log logic but yields (url, proc) instead of just url, so a kill-mid-session test can hold the process handle without touching the fixture every other live test depends on"

key-files:
  created: []
  modified:
    - tests/integration/test_mcp_client.py
    - tests/integration/test_mcp_live.py

key-decisions:
  - "No accepted-risk xfail was needed for either remote transport — both SSE and streamable HTTP proved detectable empirically on the first run, closing research Open Question 4 with evidence rather than reasoning alone. SSE: detected passively (`mgr.tools_for('live') == []` within the first 10s poll, no second call required). Streamable HTTP: detected on the next call (the passive 10s poll found nothing; a call_tool issued on a background thread failed and the subsequent poll found tools_for('live') empty)."
  - "The real-stdio reconnect test (Task 1) deliberately does NOT monkeypatch _MAX_RECONNECT_ATTEMPTS/_reconnect_backoff — it exercises the exact defaults (5 attempts, exponential backoff with jitter) a real deployment would use, distinguishing it from plan 12-05's sibling test which pins attempts=0 to stay a pure no-retry SC1 regression guard."
  - "The remote-transport kill test pins _MAX_RECONNECT_ATTEMPTS=0 (nothing is listening on the killed port to reconnect to) — it asserts pure death-detection (MCP-26), leaving MCP-23's retry loop to the already-passing real-stdio test."

requirements-completed: [MCP-23, MCP-26]

# Metrics
duration: ~25min
completed: 2026-09-24
---

# Phase 12 Plan 06: Real reconnect + remote-transport kill-detection evidence Summary

**A killed real stdio MCP server now proves the shipped reconnect loop end-to-end (new PID, fresh tool list, callable again) under production defaults, and both real SSE and streamable-HTTP servers proved their deaths are observably detected — SSE passively, HTTP on the next call — closing the phase's last open research question with evidence instead of reasoning.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 2 (`tests/integration/test_mcp_client.py`, `tests/integration/test_mcp_live.py`)

## Accomplishments

- **SC3 proven against a real re-spawned process (Task 1).** `test_mid_session_kill_reconnects_with_fresh_tools` starts a real `live_mcp_server.py` stdio subprocess with the pid-file hook from plan 12-05, hard-kills it, and — running under the shipped default `_MAX_RECONNECT_ATTEMPTS = 5` with no monkeypatched constants — asserts within a bounded 30s poll that: the pid file now holds a *different* pid (the SDK-spawned replacement process), `"alpha"` is back in `manager._sessions`, and `manager.tools_for("alpha")` is non-empty again. A subsequent `call_tool("alpha", "add", {...})` returns `"2"` against the new process, the fresh tool set matches exactly `{"add", "shout", "get_env"}` (proving a genuine new `list_tools()` call, not a stale cache), a `"MCP server 'alpha' reconnected"` note was recorded, and the *same* owning task (`manager._tasks["alpha"]`) is still not done — confirming `_serve`'s `while True` loop re-connected in place rather than `start_server` having been called again.
- **Research Open Question 4 closed with real evidence, no accepted risk needed (Task 2).** `test_live_transport_mid_session_kill_is_detected`, parametrized over both remote-transport cases, kills the real `live_mcp_server.py` subprocess serving SSE/streamable-HTTP mid-session (with `_MAX_RECONNECT_ATTEMPTS` pinned to 0 — nothing is listening on the killed port, so this test isolates death-detection from the retry loop) and observed:
  - **SSE: detected passively.** Within the first 10-second poll, `mgr.tools_for("live")` was already empty — the `sse_reader` task's read stream hit end-of-stream when the connection dropped, which `_EOFWatchStream` (plan 12-01) caught directly.
  - **streamable HTTP: detected on the next call.** The passive 10s poll found nothing (the transport's `post_writer` holds the read stream's writer open regardless of the dead peer); a `call_tool` issued on a background daemon thread then failed as the POST hit the dead server, crashing the transport's task group into `_serve_once`'s outer `except`, and the subsequent poll found `tools_for("live")` empty.
  - Both then correctly raised `RuntimeError` naming `'live'` on the next `call_tool` attempt. Printed evidence (`-s` run): `streamable-http: detected on next call`, `sse: detected passively`.
- **No production code touched.** Per this plan's ownership boundary, only `tests/integration/test_mcp_client.py` and `tests/integration/test_mcp_live.py` were modified — the 12-01 `_EOFWatchStream` detection seam and 12-03 reconnect loop needed no changes to pass either new test.

## Task Commits

1. **Task 1: Real-stdio reconnect after a kill (SC3 end-to-end)** — `62e31a1` (test)
2. **Task 2: SSE and streamable-HTTP kill-mid-session (research Open Question 4)** — `24f5ffe` (test)

**Plan metadata:** (this commit) `docs(12-06): complete real reconnect + remote-transport kill-detection plan`

## Files Created/Modified

- `tests/integration/test_mcp_client.py` — new `_pid_changed(path, old)` tolerant helper and `test_mid_session_kill_reconnects_with_fresh_tools`, appended after plan 12-05's sibling test; reuses `_pid_cfg`/`_read_pid`/`_kill`/`_wait_until` unchanged.
- `tests/integration/test_mcp_live.py` — `contextlib`/`threading` imports; new `_spawn_live_server` context manager (mirrors the `live_server` fixture, yields `(url, proc)`), a local `_wait_until` poll helper, and `test_live_transport_mid_session_kill_is_detected` parametrized over `_CASES`; the existing `live_server` fixture and `test_live_transport_lists_and_calls_tools` are byte-unchanged (confirmed via `git diff`, additions-only).

## Decisions Made

- Neither transport needed the plan's accepted-risk xfail escape hatch — both proved detectable on the first run against the real `mcp==2.0.0` SDK installed in this environment, closing 12-RESEARCH.md's Open Question 4 (previously rated LOW confidence, reasoned-not-verified) with HIGH-confidence empirical evidence.
- The stdio reconnect test's fresh-tool-set assertion (`{"add", "shout", "get_env"}`) doubles as proof the reconnect actually re-ran `list_tools()` against the new process rather than replaying a cached list.

## Deviations from Plan

None — plan executed exactly as written. Both tasks passed on first implementation; no auto-fixes, no accepted-risk path, no production code changes.

## Issues Encountered

None.

## Known Stubs

None — both new tests exercise real subprocesses over real transports with no mocked data paths.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 12's two requirements (MCP-23, MCP-26) are now both closed with evidence spanning all three transports agent86 supports (stdio, SSE, streamable HTTP) — stdio proven for both death-detection (plan 12-05) and reconnect (this plan); SSE and HTTP proven for death-detection (this plan; their reconnect path shares the same `_serve` loop already proven on stdio).
- Verified green: `pytest tests/integration/test_mcp_client.py -q -k mid_session -x` (2 passed), `pytest tests/integration/test_mcp_client.py -q -k "teardown or partial_stop"` (2 passed, unchanged per `git diff`), `pytest tests/integration/test_mcp_live.py -q -k mid_session -s` (2 passed, evidence printed), `pytest tests/integration/test_mcp_live.py -q` (4 passed, existing test unmodified), `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` (20 passed), full suite `pytest -q` (1300 passed, up from 1264, 0 failed), `mypy src/agent86` clean, `ruff check .` clean, `ruff format --diff` clean on both owned files.
- No blockers. This is the last plan in phase 12's wave 3 (`depends_on: ["12-03", "12-05"]`, no `affects` — nothing downstream depends on it).

## Self-Check: PASSED

- FOUND: `tests/integration/test_mcp_client.py`
- FOUND: `tests/integration/test_mcp_live.py`
- FOUND commit `62e31a1` (test(12-06): real-stdio reconnect after a kill proves SC3 end-to-end (MCP-23))
- FOUND commit `24f5ffe` (test(12-06): SSE and streamable-HTTP kill-mid-session detection (MCP-26, research OQ4))

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
