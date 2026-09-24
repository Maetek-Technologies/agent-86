---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 02
subsystem: tools
tags: [threading, concurrency, mcp, registry, locking]

# Dependency graph
requires: []
provides:
  - "RLock-guarded ToolRegistry safe to mutate from the MCP background-loop thread while the harness thread reads specs()/names()/dispatches"
  - "ToolRegistry.unregister_tool(tool) — identity-checked removal so a dead MCP server's tool object can never delete a different owner that won a startup name collision"
  - "dispatch() never holds the registry lock during tool.run() — the lookup is guarded, execution is not"
affects: [12-04, 12-05, 12-06, 12-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "threading.RLock guarding a shared dict mutated from two threads (mirrors Harness._subagent_usage_lock precedent)"
    - "snapshot-under-lock, build-outside-lock (specs()) so a slow per-tool operation never holds the lock"
    - "identity check (`is`) rather than equality for removing an object from a dict keyed by name, so a name collision's losing tool can't be deleted by mistake"

key-files:
  created: []
  modified:
    - src/agent86/tools/registry.py
    - tests/unit/test_registry.py

key-decisions:
  - "RLock chosen over a plain Lock because dispatch's error path calls names() (which also locks) while resolving the 'unknown tool' message — same thread must be able to re-enter"
  - "Only the dict lookup in dispatch() is held under the lock; _skill_refusal and tool.run() execute outside it, since a tool run can take minutes and delegate re-enters the registry"
  - "specs() snapshots the tool list under the lock, then calls each tool's spec() outside it — spec() should be cheap but there's no reason to hold the lock while it runs"

patterns-established:
  - "Cross-thread mutation of a Tier 4 shared structure uses an RLock held only around the dict operation itself, never around a tool's execute()/run()"

requirements-completed: [MCP-26]

# Metrics
duration: 12min
completed: 2026-09-24
---

# Phase 12 Plan 02: RLock-Guarded ToolRegistry Summary

**`ToolRegistry` gained a `threading.RLock` around every dict access and an identity-checked `unregister_tool(tool)`, making it safe for `MCPManager`'s background event-loop thread to mutate the registry while the harness thread reads and dispatches — without ever holding the lock during a tool's actual execution.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-09-24T15:24:35Z (STATE.md session start)
- **Completed:** 2026-09-24T15:27:07Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `ToolRegistry._tools` (a plain dict) is now guarded by an `RLock` on every mutation and read path (`register`, `try_register`, `unregister`, `get`, `names`, `specs`, the lookup half of `dispatch`), closing the cross-thread hazard research Pitfall 4 named for plan 12-04's upcoming MCP death/reconnect wiring
- New `unregister_tool(tool)` removes a tool only if it is the exact object currently registered under its name — the precondition for a dying MCP server to clean up its own tools without accidentally deleting a different tool that won a startup name collision
- `dispatch()` releases the lock before calling `_skill_refusal`/`tool.run()`, proven by a test that spawns a second thread inside a tool's `execute()` and asserts a non-blocking `acquire()` on the registry's own lock succeeds

## Task Commits

Each task was committed atomically:

1. **Task 1: Tests for identity-checked removal and cross-thread safety** - `5332873` (test)
2. **Task 2: RLock-guard ToolRegistry and add unregister_tool** - `83a6e13` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `src/agent86/tools/registry.py` - `threading.RLock` added; `register`/`try_register`/`unregister`/`get`/`names`/`specs` wrapped; new `unregister_tool(tool)`; `dispatch()` locks only the lookup
- `tests/unit/test_registry.py` - five new tests: three identity-removal cases, one cross-thread mutate-while-read stress test, one lock-not-held-during-run proof (`_LockCheckTool` helper)

## Decisions Made
- RLock (not Lock): `dispatch`'s "unknown tool" error path calls `self.names()`, which also acquires the lock — needed re-entrancy from the same thread, matching the plan's stated rationale.
- `specs()` snapshots `list(self._tools.values())` under the lock, then calls `.spec()` per tool outside it, so a tool's `spec()` implementation is never run while blocking a concurrent mutator.
- Kept `unregister(name)` byte-behaviorally unchanged (still used by `Harness.remove_mcp_server`) — `unregister_tool` is additive, not a replacement.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The full acceptance-criteria command `pytest tests/unit/test_registry.py tests/unit/test_loop.py tests/unit/test_mcp.py -q` fails at collection with `ImportError: cannot import name 'MCPServerUnavailable' from 'agent86.tools.mcp_client'` — this is the concurrently-executing plan 12-01's in-progress work on `mcp_client.py`/`test_mcp.py` (files this plan does not own and was instructed to ignore per the parallel-execution contract). Verified instead with `pytest tests/unit/test_registry.py tests/unit/test_loop.py -q` (51 passed, 0 failed) and confirmed `test_mcp.py`'s failure is a collection-time `ImportError` unrelated to `registry.py`, not a regression this plan introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`ToolRegistry.unregister_tool` and the RLock are ready for plan 12-04 to wire MCP server death/reconnect detection into `Harness.registry` from `MCPManager`'s background thread, per the research's Open Question 1 recommendation. `unregister(name)` is untouched, so `Harness.add_mcp_server`/`remove_mcp_server` need no changes. No blockers.

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: src/agent86/tools/registry.py
- FOUND: tests/unit/test_registry.py
- FOUND: .planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-02-SUMMARY.md
- FOUND: 5332873 (test commit)
- FOUND: 83a6e13 (feat commit)
