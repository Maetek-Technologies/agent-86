---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 04
subsystem: orchestration
tags: [mcp, threading, tool-registry, reconnect]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    provides: "12-01's MCPManager.on_tools_changed hook (fired never-raising from the MCP loop thread on a drop or reconnect) and 12-02's RLock-guarded ToolRegistry.unregister_tool/try_register"
provides:
  - "Harness._on_mcp_tools_changed(server, removed, added) — the listener that mutates self.registry from the MCP loop thread, closing research Open Question 1 (in scope)"
  - "Harness._wire_mcp(manager) — wired both at construction (when self.mcp already exists) and inside ensure_mcp (when a manager is created lazily mid-session)"
  - "A dead MCP server's tools now disappear from Harness.registry.specs() (what the model is actually offered), not only from MCPManager.tools()"
  - "A reconnected server's fresh tools are re-added into Harness.registry"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-thread mutation of ToolRegistry (MCP loop thread -> self.registry) routed only through 12-02's lock-guarded unregister_tool/try_register, never a bare dict operation"
    - "Listener never raises: caught and logged via logger.exception, matching MCPManager's own on_tools_changed never-raise contract"

key-files:
  created: []
  modified:
    - src/agent86/orchestration/loop.py
    - tests/unit/test_loop.py

key-decisions:
  - "unregister_tool (identity-checked) is used for removals, not unregister(name) — so a tool that won a startup name collision can never be deleted by a different, same-named object reported dead by a different server path"
  - "try_register (lenient) is used for additions, not register (raises on clash) — a collision on reconnect is recorded by the registry, not raised into the MCP loop thread"
  - "_wire_mcp is a separate method (not inlined) so both call sites (__init__ and ensure_mcp) stay one line and can never drift out of sync"

requirements-completed: [MCP-26, MCP-23]

# Metrics
duration: ~12min
completed: 2026-09-24
---

# Phase 12 Plan 04: MCPManager <-> Harness.registry desync fix Summary

**`Harness._on_mcp_tools_changed` wires `MCPManager.on_tools_changed` into the RLock-guarded `ToolRegistry` so a dead MCP server's tools disappear from the model's offered tool list — not just from `MCPManager.tools()` — and a reconnect re-adds them, from the MCP loop thread, without ever raising into it.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-09-24T15:34:54Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- **The registry gap research Open Question 1 flagged is closed.** Before this plan, `MCPManager._server_tools` (popped on death by plan 12-01) and `Harness.registry` (what `_build_request` actually reads via `specs()`) were two independent stores kept in sync only by the user-initiated `add_mcp_server`/`remove_mcp_server` path — an unexpected server death left its tools still advertised to the model and still callable, only returning a better-worded error (SC2) instead of disappearing. `Harness._on_mcp_tools_changed(server, removed, added)` now runs as `MCPManager.on_tools_changed`'s listener on the MCP background loop thread: it calls `self.registry.unregister_tool(tool)` for each removed tool (identity-checked — a tool that won a startup name collision is never taken out by a different, same-named dead object) and `self.registry.try_register(tool)` for each added tool (lenient — a clash on reconnect is recorded, not raised). The whole body is wrapped in `try/except Exception: logger.exception(...)`, so a registry failure never surfaces inside the MCP manager's own event loop.
- **Wired at both places a live `MCPManager` can come from.** `Harness._wire_mcp(manager)` sets `manager.on_tools_changed = self._on_mcp_tools_changed` and is called once in `__init__` (right after `self.registry` is built, only when `self.mcp is not None`) and once inside `ensure_mcp()` (inside the `if self.mcp is None:` branch, right after the lazy `MCPManager({})` is created) — so a session that starts with MCP servers configured and a session that mounts its first server mid-session both end up wired the same way.
- **No prompt/turn plumbing needed.** `_build_request` already reads `self.registry.specs()` fresh on every request (Phase 4 D-15), so the moment the listener mutates the registry, the very next model call sees the change — nothing else in `run_turn` was touched.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests for harness registry sync** - `5d4d258` (test)
2. **Task 2: Wire MCPManager.on_tools_changed into Harness.registry** - `0f366e2` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `src/agent86/orchestration/loop.py` — `import logging` + module `logger`; `Tool` added to the `agent86.tools.base` import; `Harness.__init__` calls `self._wire_mcp(self.mcp)` right after `self.registry` is built (guarded by `if self.mcp is not None`); `ensure_mcp()` calls `self._wire_mcp(self.mcp)` inside its `if self.mcp is None:` branch; new `Harness._wire_mcp(manager)` and `Harness._on_mcp_tools_changed(server, removed, added)` methods placed right after `remove_mcp_server`.
- `tests/unit/test_loop.py` — `import threading`; six new tests under a new `# ---- MCPManager.on_tools_changed <-> Harness.registry wiring (plan 12-04) ----` section: bound-method-equality wiring checks at `ensure_mcp()` and at construction (via a monkeypatched `build_mcp`), cross-thread identity-checked removal (run from a separate `threading.Thread`, joined), re-add on reconnect, collision-winner safety, and never-raise on a `try_register` failure.

## Decisions Made

- Removals go through `unregister_tool` (identity check), additions through `try_register` (lenient) — matching plan 12-02's own stated precondition for exactly this cross-thread MCP death/reconnect wiring.
- The listener is wrapped in one `try/except Exception` around both loops (not one per tool) — a failure on the first tool doesn't leave a partial mutation silently un-logged; the whole call is logged once and the manager's own state is untouched either way.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1 and 2 landed as two separate commits (RED then GREEN), matching the plan's own TDD task structure.

## Issues Encountered

None. `ruff format --check` flags pre-existing unformatted regions in both `src/agent86/orchestration/loop.py` (long-line collapsed dict literals from before this phase, part of plan 10-05's already-logged 74-file `deferred-items.md` backlog) and `tests/unit/test_loop.py`; confirmed via `ruff format --diff` that none of the flagged hunks touch any line this plan added or modified — all this plan's new code (`_wire_mcp`, `_on_mcp_tools_changed`, the `logger` line, the six new tests) is absent from the diff. `ruff check .` (whole repo) separately flags one pre-existing `E501` in `tests/integration/test_mcp_client.py`, a file owned by the concurrently-executing plan 12-05, not this plan's scope — `ruff check` scoped to this plan's own two files passes clean.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- MCP-26 (session/registry desync fixed) and MCP-23 (reconnect) are both closed from the registry side: a server death now removes its tools from what the model is actually offered, and a reconnect re-adds them, satisfying the phase goal's "tools unregistered" read literally, not just at the `MCPManager` layer.
- Cross-thread mutation goes only through plan 12-02's locked `ToolRegistry` methods — no bare dict access was added.
- No blockers for 12-03 (bounded reconnect) or 12-05 (integration coverage), both parallel plans touching disjoint files.
- Full verification for this plan's scope: `pytest tests/unit/test_loop.py -q` (47 passed), `pytest tests/unit/test_loop.py tests/unit/test_registry.py tests/unit/test_mcp.py -q` (116 passed), `pytest tests/integration/test_scripting_contract.py -q` (19 passed, cold-start/scripting contract unchanged), `mypy src/agent86` clean, `ruff check` clean on this plan's own files.

## Self-Check: PASSED

- FOUND: `src/agent86/orchestration/loop.py`
- FOUND: `tests/unit/test_loop.py`
- FOUND commit `5d4d258` (test(12-04): RED tests for harness registry sync)
- FOUND commit `0f366e2` (feat(12-04): wire MCPManager.on_tools_changed into Harness.registry)

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
