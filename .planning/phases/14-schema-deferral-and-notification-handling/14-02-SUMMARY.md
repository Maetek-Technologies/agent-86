---
phase: 14-schema-deferral-and-notification-handling
plan: 02
subsystem: cognitive
tags: [mcp, prompt-compilation, adr-0003, sub-agents, context-budget]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    provides: ToolRegistry identity-checked register/unregister, MCPManager tool-list sync
provides:
  - "render_mcp_section(entries) -> str in cognitive/prompt.py — pure renderer for the
    per-request MCP names-plus-instructions system-message section (ADR 0003)"
  - "Harness._mcp_prompt_section() / Harness._system_content() append that section to every
    compiled request, duck-typed on self.mcp.prompt_catalog so it runs before plan 14-03 exists"
  - "SubAgent._system() reuses Harness._system_content(None) instead of the static
    system_prompt.content, so delegated tasks see the same MCP names"
affects: [14-03-mcp-tool-schema-deferral, 14-04, 14-05, 14-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Duck-typed manager contract (getattr(self.mcp, 'prompt_catalog', None)) lets a
      consumer plan (14-02) ship and merge before its producer plan (14-03) exists, with the
      pre-existing _FakeMCPManager test doubles (no prompt_catalog) continuing to work unchanged"
    - "Per-request recomputed prompt sections ride the same system_content plumbing
      _context_budget already reads fresh every request — no new hook added"

key-files:
  created:
    - tests/unit/test_mcp_prompt_section.py
  modified:
    - src/agent86/cognitive/prompt.py
    - src/agent86/orchestration/loop.py
    - src/agent86/agents/subagent.py

key-decisions:
  - "MCP names are never deferred, only schemas (ADR 0003) — render_mcp_section always lists
    every callable tool name per server regardless of schema-materialization state"
  - "Server instructions render capped at 2000 chars with a visible '…[truncated N chars of
    server instructions]' marker rather than being silently dropped or left uncapped"
  - "Identity check (registry.get(t.name) is t) ensures a name-collision loser or a
    since-unregistered tool is never advertised as callable"
  - "_mcp_prompt_section degrades to '' on any exception (logger.debug only) — a prompt
    section must never fail a request"

patterns-established:
  - "Pattern: mypy union-attr false positive when comparing an Any-typed loop variable
    directly against an Optional-returning call via `is` — mypy narrows the Any variable to
    the Optional type. Fix: split into `registered = get(...)`; `if registered is not None
    and registered is t`."

requirements-completed: [MCP-20]

# Metrics
duration: ~20min
completed: 2026-09-24
---

# Phase 14 Plan 02: MCP prompt section (names + server instructions) Summary

**Every request's compiled system message now lists every callable MCP tool's name per mounted server, plus that server's instructions (capped, labelled, untrusted), recomputed fresh on every request and shared verbatim by sub-agents — the ADR 0003 half of schema deferral that makes deferring schemas legal.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-09-24
- **Tasks:** 2/2
- **Files modified:** 3 (+1 test file created)

## Accomplishments
- `render_mcp_section` in `cognitive/prompt.py`: a pure, deterministic renderer that lists
  every server's callable tool names and (when present) its untrusted, bounded, labelled
  instructions block.
- `Harness._mcp_prompt_section()` / `Harness._system_content()`: the section is computed fresh
  on every request (identity-checked against the live registry) and folded into the same
  `system_content` string `_context_budget` already recomputes per request — no new budget hook.
- `SubAgent._system()` now reuses the parent's live compiled system content instead of the
  static startup-time `system_prompt.content`, so a delegated task sees the same MCP names its
  shared, deferred tool specs rely on.
- Duck-typed on `prompt_catalog` (`getattr(self.mcp, "prompt_catalog", None)`), so this plan
  runs and merges independently of plan 14-03 (which will add that method to `MCPManager`) and
  the pre-existing `_FakeMCPManager` test doubles in `test_loop.py` (no `prompt_catalog`)
  continue to exercise the "no section" path unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: render_mcp_section in cognitive/prompt.py** - `3db78af` (feat, TDD RED→GREEN)
2. **Task 2: Wire the section into Harness._system_content and sub-agents** - `30bf887` (feat, TDD RED→GREEN)

_Both tasks' RED phase was verified by running the new tests before implementation and
confirming the expected import/assertion failures; no separate `test:` commit was made per
task since the plan's TDD instruction was RED-then-GREEN within one task, not a full
red/green/refactor three-commit cycle — matching how this project's other `tdd="true"` tasks
in this milestone have landed (see e.g. plan 11-02/11-03 precedent of single-commit
RED+GREEN when the two are inseparable without breaking `ruff`/`mypy` mid-task)._

## Files Created/Modified
- `src/agent86/cognitive/prompt.py` - `render_mcp_section`, `MCP_INSTRUCTIONS_MAX_CHARS`
- `src/agent86/orchestration/loop.py` - `Harness._mcp_prompt_section`, `_system_content` now
  appends it
- `src/agent86/agents/subagent.py` - `SubAgent._system()` calls `self.h._system_content(None)`
- `tests/unit/test_mcp_prompt_section.py` - 17 tests (7 renderer, 10 Harness/sub-agent wiring)

## Decisions Made
- Kept `render_mcp_section` pure (no MCP import, never raises on well-typed input) per the
  plan's design ruling, so it's trivially unit-testable and reusable.
- Used the identity-check pattern (`registered is not None and registered is t`) rather than
  the plan's literal one-line comprehension (`registry.get(t.name) is t`) after discovering
  a genuine mypy false positive with the one-liner — documented below as a Rule 1 auto-fix.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mypy union-attr false positive on the tool-identity filter**
- **Found during:** Task 2, running `mypy src/agent86` per the task's own acceptance criteria
- **Issue:** The plan's literal action text specified
  `names = [t.name for t in tools if self.registry.get(t.name) is t]`. mypy narrows the
  Any-typed comprehension variable `t` to `Tool | None` because it appears in an `is`
  comparison against `ToolRegistry.get()`'s `Tool | None` return, then flags `t.name` as
  "Item None of Tool | None has no attribute name" — reproduced in isolation with a minimal
  mypy repro before touching production code, confirming it is a real mypy narrowing quirk,
  not a runtime bug.
- **Fix:** Rewrote the filter as an explicit loop: `registered = self.registry.get(t.name)`;
  `if registered is not None and registered is t: names.append(t.name)`. Runtime behavior is
  identical; mypy's narrowing no longer touches `t`.
- **Files modified:** `src/agent86/orchestration/loop.py`
- **Verification:** `mypy src/agent86` — 0 errors (94 files); all 17 new tests plus the full
  `tests/unit/` suite (827 passed) still green.
- **Committed in:** `30bf887` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/type-check fix)
**Impact on plan:** No behavior change — purely a type-checker-satisfying rewrite of the same
identity check the plan specified. No scope creep.

## Issues Encountered
- `ruff check .` (run once at the end, across the whole repo per the plan's own verification
  step) reports one pre-existing `F401` unused-import finding in
  `tests/integration/live_mcp_server.py` — a file explicitly owned by the concurrent 14-01
  executor per this plan's parallel-execution boundary, not touched by this plan. `ruff check`
  scoped to this plan's own four files (`src/agent86/cognitive/prompt.py`,
  `src/agent86/orchestration/loop.py`, `src/agent86/agents/subagent.py`,
  `tests/unit/test_mcp_prompt_section.py`) passes with zero findings. Left for 14-01/its own
  plan to resolve, not fixed here (out-of-scope per the shared-tree file-ownership boundary).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 14-03 can now add `MCPManager.prompt_catalog() -> list[tuple[str, list[Tool], str |
None]]` and the section will populate automatically — no further changes needed in
`loop.py`/`prompt.py`/`subagent.py`. `Harness._mcp_prompt_section()`'s duck-typed
`getattr(self.mcp, "prompt_catalog", None)` is the exact seam 14-03's research/plan already
names as the contract. No blockers.

---
*Phase: 14-schema-deferral-and-notification-handling*
*Completed: 2026-09-24*

## Self-Check: PASSED

All created/modified files confirmed present; both task commits (`3db78af`, `30bf887`)
confirmed present in `git log --oneline --all`.
