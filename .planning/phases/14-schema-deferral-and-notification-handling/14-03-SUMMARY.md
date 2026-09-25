---
phase: 14-schema-deferral-and-notification-handling
plan: 03
subsystem: tools
tags: [mcp, schema-deferral, adr-0003, context-budget, prompt-compilation]

# Dependency graph
requires:
  - phase: 14-schema-deferral-and-notification-handling
    provides: "plan 14-01's _DyingTransport.notify()/_Up.instructions/call_kwargs test machinery
      and plan 14-02's Harness._mcp_prompt_section() duck-typed on
      getattr(self.mcp, 'prompt_catalog', None)"
provides:
  - "MCPTool schema deferral: a never-called tool advertises its name with ToolSpec's own
    default-empty stub schema and a ' [argument schema loads on first call]' description
    suffix; the real server schema materialises synchronously inside run() on first
    execution, success or failure"
  - "MCPManager.server_instructions(name) / prompt_catalog() -> list[tuple[str, list[Tool],
    str | None]] — InitializeResult.instructions captured per server, feeding plan 14-02's
    Harness system-message section with no change to loop.py"
  - "A same-turn budget regression test proving ADR 0003 SC2: a materialising schema's cost is
    already reflected in the very next request of the same turn, with no new
    _context_budget hook"
affects: [14-04-route-list-changed-and-progress, 14-05, 14-06-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Materialisation flag flips synchronously at the top of MCPTool.run(), before any return —
      the same object ToolRegistry.specs() already re-reads fresh every request, so no new
      budget hook is needed for a schema that grows mid-turn"
    - "The deferred stub is ToolSpec's own default-empty shape ({'type': 'object',
      'properties': {}}), never a bespoke schema, so no provider adapter (Anthropic,
      OpenAI-compatible, Ollama) meets a new wire shape on a never-called tool"
    - "InitializeResult.instructions is set atomically beside _sessions[name]/_server_tools[name]
      (never before 'connected' is true) and popped beside them in every _serve_once exit path
      and in stop_server — same SC1 'cleared in the same place' discipline Phase 12 established"

key-files:
  created:
    - tests/unit/test_mcp_schema_deferral.py
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/integration/test_mcp_client.py
    - tests/unit/test_mcp.py

key-decisions:
  - "Unconditional deferral, no config field (per the plan's own ruling, orchestrator
    ruling 2 / research Open Question 2): every MCPTool whose server schema has at least one
    property is deferred; _MCPCapabilityTool synthetic tools and argument-less tools never
    are. config.py is untouched (git diff --stat confirms empty)."
  - "Materialise on first execution, success or failure — not 'first successful call' — so a
    tool whose first call legitimately fails does not permanently withhold its schema from the
    model. The flip happens synchronously at the top of run(), before any return, so the very
    next request of the same turn already carries the real schema and its real budget cost."
  - "A first call missing the real schema's required arguments short-circuits with a named
    error and never reaches the server (a side-effecting server must not receive a guessed
    call); the precheck fires only on the first use — a second omission reaches the server,
    per ADR 0003's reconnect-preserves-identity ruling."
  - "Every first-use ToolResult carries metadata={'schema_materialized': True} — tool-result
    metadata, not a run --json key, so the scripting contract's additive-only rule is
    untouched."

patterns-established:
  - "Pattern: when a plan's own action text specifies the exact insertion point for a stateful
    side effect relative to an existing synchronization boundary (here: 'directly before
    self._sessions[name] = session'), place it there literally rather than at the first
    plausible spot (right after the awaited call) — the ordering is load-bearing for SC1's
    'never set before connected is true' invariant."

requirements-completed: [MCP-20]

# Metrics
duration: ~17min
completed: 2026-09-25
---

# Phase 14 Plan 03: MCP schema deferral, server instructions, and the same-turn budget proof Summary

**MCPTool schemas are deferred until first execution (ADR 0003) — a never-called tool advertises its name with ToolSpec's own empty-stub schema, materialising its real schema synchronously inside `run()` — plus `InitializeResult.instructions` capture and `MCPManager.prompt_catalog()` feeding plan 14-02's system-message section, and a regression test proving the budget accounts for a materialising schema in the very next request of the same turn with no new hook.**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-09-25T02:41:00Z (approx.)
- **Completed:** 2026-09-25T02:58:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 3 (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`,
  `tests/integration/test_mcp_client.py`); 1 created (`tests/unit/test_mcp_schema_deferral.py`)

## Accomplishments

- `MCPTool` gained `_DEFERRED_NOTE`, `_deferred_schema()`, `_missing_required()`, a
  `materialized` property, and a materialisation flag flipped synchronously at the top of
  `run()`, before any return. `spec()` reports the stub (`{"type": "object", "properties":
  {}}` plus a `" [argument schema loads on first call]"` description suffix) until the first
  execution, then the real server schema for the rest of the session.
- A first call missing the real schema's `required` keys is answered with a named error
  listing them and never reaches the server; the precheck only fires on first use. Every
  first-use `ToolResult` carries `metadata={"schema_materialized": True}`.
- `_MCPCapabilityTool` synthetic tools and any tool whose server schema has no properties are
  never deferred — nothing to save.
- Thirteen new unit tests (`tests/unit/test_mcp_schema_deferral.py`) pin materialisation
  behaviour and prove the stub round-trips unchanged through all three provider wire shapes
  (Anthropic `input_schema`, OpenAI-compatible/Ollama `function.parameters`) both before and
  after materialisation — the Pitfall 1 check the plan named as the one thing that could
  overturn the "unconditional, no config field" ruling. It did not: no adapter meets a new
  shape.
- `MCPManager.__init__` gained `self._instructions: dict[str, str | None]`; `_serve_once` now
  keeps `session.initialize()`'s result and, directly before `self._sessions[name] = session`
  (never before "connected" is true), stores the stripped-empty-to-`None` instructions text —
  popped beside `_sessions`/`_server_tools` in every `_serve_once` exit path and in
  `stop_server`. New public `server_instructions(name)` and `prompt_catalog() -> list[tuple[
  str, list[Tool], str | None]]` (sorted by server name) feed plan 14-02's
  `Harness._mcp_prompt_section()` with zero change to `loop.py` — confirmed by `git diff
  --stat src/agent86/orchestration/loop.py` being empty.
- A new `test_budget_shrinks_in_the_step_that_materialises` proves ADR 0003 SC2 end-to-end: a
  local Anthropic-shaped provider runs a turn where step 1 calls a read-only MCP tool with a
  2,000-char-schema and step 2 answers with text; the tool's spec in request 0 is the stub, in
  request 1 is the full schema, and `budget0 - budget1` equals exactly
  `count_spec_tokens(req1.tools) - count_spec_tokens(req0.tools)` (and is `> 0`) — with no new
  `_context_budget` hook (`test_budget_hook_unchanged` pins the method's signature and its
  exactly-2 call sites via `inspect`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Defer MCPTool schemas until first execution** - `d75fa1c` (feat, TDD)
2. **Task 2: Capture server instructions, expose prompt_catalog, prove the same-turn budget** -
   `c3af602` (feat, TDD)

## Files Created/Modified

- `src/agent86/tools/mcp_client.py` - `_DEFERRED_NOTE`, `_deferred_schema()`,
  `_missing_required()`; `MCPTool._definition`/`_materialized`/`materialized` property;
  `MCPTool.spec()`/`run()` deferral logic; `MCPManager._instructions`,
  `server_instructions()`, `prompt_catalog()`; `_serve_once`'s `initialize()` result capture
  and cleanup in its `finally` and in `stop_server`
- `tests/unit/test_mcp_schema_deferral.py` (new) - 13 tests: materialisation (7), provider
  wire-shape round trips (4), same-turn budget proof (2)
- `tests/unit/test_mcp.py` - 6 new tests: `test_instructions_captured_per_server`,
  `test_instructions_blank_is_none`, `test_instructions_absent_when_initialize_returns_none`,
  `test_instructions_cleared_on_stop_and_death`, `test_prompt_catalog_sorted_by_server`,
  `test_prompt_catalog_feeds_the_system_message`
- `tests/integration/test_mcp_client.py` - `test_mcp_tool_spec_uses_server_schema` rewritten to
  assert the pre-call stub, then the real schema after one `run()`

## Decisions Made

See `key-decisions` in the frontmatter — all four rulings were fixed by the plan itself
(unconditional deferral with no config field, materialise on first execution regardless of
outcome, a visible synchronous first-use cost with a named precheck error, additive-only
`metadata` rather than a `run --json` key) and were followed exactly as written; no new
decision was required during execution.

## Deviations from Plan

None — plan executed exactly as written. The one placement detail worth calling out explicitly
(not a deviation, since the plan's own action text specified it): `self._instructions[name] =
...` is set directly before `self._sessions[name] = session` (after the tool list and
capability tools are built), not immediately after `await session.initialize()` — matching the
plan's "never before connected is true" invariant and Phase 12's "both dicts cleared in the
same place" discipline.

## Issues Encountered

- Two lint-only findings surfaced on the full-repo `ruff check .` after Task 2 (a line over 100
  chars in the new instructions-assignment expression, and an unsorted local-import block in a
  new test): both fixed immediately (reformatted the expression across three lines;
  `ruff check --fix` on the import block) and re-verified with a clean `ruff check .` before
  committing. Neither changed behaviour.
- `tests/unit/test_mcp.py::test_death_eof_clears_sessions_and_tools` (a pre-existing Phase 12
  test, untouched by this plan) failed once in a full-suite run
  (`manager._tasks["srv"].done()` was `False` under load) and passed 3/3 in isolation and on a
  full-suite re-run (895 passed, 0 failed) — a known, documented timing-sensitive flake (see
  e.g. plan 13-04's SUMMARY for the same category of pre-existing flake), not a regression
  introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MCP-20 is closed: schema deferral, the server-instructions capture, and the same-turn budget
  proof are all in place with unit coverage. `docs/mcp-conformance-matrix.md`/`ARCHITECTURE.md`
  §15/CHANGELOG updates are left to this phase's own signoff plan (14-06), matching how prior
  phases in this milestone sequenced docs.
- `MCPTool._definition` (raw description, schema, read_only) is in place specifically for plan
  14-04's `list_changed` re-fetch to compare against and decide whether an unchanged tool's
  object (and its `materialized` flag) should be preserved across a re-list — ready to consume,
  untouched by anything else in this plan.
- `MCPManager.prompt_catalog()`/`server_instructions()` are live and already feeding plan
  14-02's `Harness._mcp_prompt_section()` end-to-end (`test_prompt_catalog_feeds_the_system_
  message` proves it against a full `Harness` + fake transport). No further wiring needed in
  `loop.py`/`prompt.py`.
- Full suite green: `pytest -q` 1404 passed (up from 1367), 0 failed, 14 deselected;
  `pytest tests/unit/ tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py
  tests/integration/test_scripting_contract.py -q` 895 passed on the clean re-run; `mypy
  src/agent86` and `ruff check .` both clean; `git diff --stat src/agent86/config.py` and
  `src/agent86/orchestration/loop.py` both empty, confirming the plan's "no config field, no
  loop.py change" rulings held. No blockers for 14-04/14-05/14-06.

## Self-Check

- `src/agent86/tools/mcp_client.py` — FOUND (modified)
- `tests/unit/test_mcp_schema_deferral.py` — FOUND (created)
- `tests/unit/test_mcp.py` — FOUND (modified)
- `tests/integration/test_mcp_client.py` — FOUND (modified)
- Commit `d75fa1c` — FOUND (`git log --oneline --all | grep d75fa1c`)
- Commit `c3af602` — FOUND (`git log --oneline --all | grep c3af602`)

## Self-Check: PASSED

---

*Phase: 14-schema-deferral-and-notification-handling*
*Completed: 2026-09-25*
