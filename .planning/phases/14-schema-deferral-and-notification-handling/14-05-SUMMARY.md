---
phase: 14-schema-deferral-and-notification-handling
plan: 05
subsystem: testing
tags: [mcp, schema-deferral, list_changed, progress, logging, instructions, real-stdio, adr-0003]

# Dependency graph
requires:
  - phase: 14-schema-deferral-and-notification-handling
    provides: "plan 14-01's live_mcp_server.py AGENT86_LIVE_MCP_NOTIFY_TOOLS/AGENT86_LIVE_MCP_INSTRUCTIONS
      probes and 14-EVIDENCE.md's live-corpus instructions finding; plan 14-03's schema deferral
      (MCPTool stub/materialisation) and MCPManager.server_instructions()/prompt_catalog(); plan
      14-04's MCPManager._on_notification router (list_changed re-fetch, last_progress, logging)"
provides:
  - "tests/integration/test_mcp_client.py: 7 real-stdio tests proving SC1 (server instructions +
    schema deferral end to end over a real ReAct turn), SC2 (same-turn budget, folded into the
    schema-deferral test) and SC3 (list_changed/progress/logging routed through a real Harness +
    MCPManager, not fakes) — the same real-corpus proof pattern plans 12-06 and 13-05 used for
    their own phases"
affects: [14-06-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_harness_with(name, cfg, provider=None) builds a real Harness + MCPManager the way the TUI
      does it (ensure_mcp -> start_server -> add_mcp_server), so a real-stdio test drives the same
      registry/system-message path a live session uses, not a shortcut"
    - "A no-op-refetch repeat notification (calling grow_tools twice) produces no note and no
      registry churn by construction (14-04's identity-preserving diff), so its regression test
      polls for a steady state with a generous fixed window rather than a positive event signal"

key-files:
  modified:
    - tests/integration/test_mcp_client.py

key-decisions:
  - "Tasks 1 and 2 landed as a single commit rather than two: Task 1's new imports
    (ScriptedProvider, ApprovalMode, Completion, Usage) are unused until Task 2's schema-deferral
    test consumes them, which would fail ruff's F401 on a Task-1-only commit — the same category
    of split documented in this phase's own 14-01 and 14-04 SUMMARYs."
  - "The instructions/corpus claim is bounded exactly by 14-EVIDENCE.md's own Conclusion for SC1
    (quoted verbatim below), not restated or strengthened — this plan proves rendering against the
    CI fixture's synthetic instructions only; the live-corpus citation is server-everything, cited
    by 14-01/14-EVIDENCE.md, not re-verified here."

requirements-completed: [MCP-20, MCP-24]

# Metrics
duration: ~25min
completed: 2026-09-25
---

# Phase 14 Plan 05: Real-stdio proof of schema deferral and notification handling Summary

**Seven new real-stdio tests drive the actual `live_mcp_server.py` fixture through a real `MCPManager` and a real `Harness` (no fakes) — a mid-session `grow_tools`/`shrink_tools` mounts and unmounts a callable tool in `Harness.registry` and the system message with no restart, `progress_steps`/`log_line` surface in `MCPManager.last_progress` and the Python logger, and a real ReAct turn proves ADR 0003's stub-then-real schema and same-turn budget end to end.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-25T03:35:00Z (approx.)
- **Completed:** 2026-09-25T03:29:55-04:00 (commit `32eae0e`)
- **Tasks:** 2/2 completed
- **Files modified:** 1 (`tests/integration/test_mcp_client.py`)

## Accomplishments

- `test_real_stdio_list_changed_mounts_and_unmounts_through_the_harness`: over a real stdio
  session, `grow_tools` makes `mcp__alpha__dynamic_echo` appear in `harness.registry.names()` and
  `harness._system_content(None)` with no restart, callable end to end through
  `harness.registry.dispatch(...)`; a note in `manager.notes` names both the change and the tool;
  `shrink_tools` removes it from both places again; `mcp__alpha__add`'s object identity survives
  the whole round trip unchanged (Phase 12's identity-preservation guarantee, proven live).
- `test_real_stdio_list_changed_repeated_grow_is_stable`: a second `grow_tools` (a no-op re-list
  by 14-04's `(description, schema, read_only)` diff) produces exactly one
  `mcp__alpha__dynamic_echo` and no collision note.
- `test_real_stdio_progress_notifications_are_observed`: real `notifications/progress` from
  `progress_steps` land in `MCPManager.last_progress("alpha")` (`(3.0, 3.0, "step 3")`) and a live
  note (`"MCP server 'alpha': progress 3/3"`), never in the startup-rendered `manager.notes` list
  (`persistent=False`, 14-04).
- `test_real_stdio_logging_notification_reaches_the_logger`: real `notifications/message` from
  `log_line` reaches `agent86.tools.mcp_client`'s Python logger at `logging.WARNING`, message
  containing `"MCP server 'alpha'"` — captured via `caplog` with no custom handler needed (the
  MCP loop thread's log record reaches the root handler `caplog` installs).
- `test_real_stdio_instructions_and_names_reach_the_system_message` /
  `test_real_stdio_no_instructions_means_no_instructions_block`: a real
  `InitializeResult.instructions` string (set via `AGENT86_LIVE_MCP_INSTRUCTIONS`) reaches
  `Harness._system_content(None)` under the `"Instructions from MCP server 'alpha'"` header, and
  every registered tool name for that server appears in the same content; with no instructions
  set, that header is absent but the server's tool-name line (`"- alpha: "`) still renders.
- `test_real_stdio_schema_deferral_end_to_end`: a real `ScriptedProvider`-driven `run_turn` over a
  real stdio session proves ADR 0003 SC1/SC2 together — request 0's `mcp__alpha__shout` spec is
  the stub (`{"type": "object", "properties": {}}`, description ending
  `" [argument schema loads on first call]"`); request 1's spec (the very next request of the SAME
  turn) carries the real `text` property; request 0's system message names
  `"mcp__alpha__shout"`; the tool result (`"HI"`, from `shout("hi")`) reaches the transcript. Run
  with `guardrails.approval = ApprovalMode.AUTO` since `shout` is side-effecting and the test is
  non-interactive.
- Per the orchestrator's honesty ruling, the instructions test above proves rendering against the
  **CI fixture's** synthetic `instructions=`, not a live-corpus server. `14-EVIDENCE.md`'s own
  `## Conclusion for SC1`, quoted verbatim, is the only authority on what that is worth:

  > At least one pinned corpus server sets instructions: server-everything. Plan 14-05 proves
  > rendering against the CI fixture and 14-06 may cite server-everything as live-corpus demand.

  This SUMMARY does not claim more than that sentence states — the live-corpus citation
  (`server-everything@2026.8.31`) belongs to `14-01`/`14-EVIDENCE.md`, not to this plan's own test
  evidence.

## Task Commits

Both tasks landed in a single commit — see Deviations below for why:

1. **Task 1 (real-stdio list_changed/progress/logging) + Task 2 (real-stdio
   instructions/schema-deferral)** - `32eae0e` (test)

## Files Created/Modified

- `tests/integration/test_mcp_client.py` - `import logging`; new module-level imports
  (`agent86.orchestration.loop.Harness`, `agent86.types.{ApprovalMode, Completion, Usage}`,
  `tests.support.{ScriptedProvider, TextProvider}`); `_notify_cfg(instructions=None)` and
  `_harness_with(name, cfg, provider=None)` helpers; 7 new `test_real_stdio_*` tests covering
  list_changed (mount/unmount + repeated-grow stability), progress, logging, instructions
  (present/absent), and the schema-deferral same-turn-budget end-to-end proof

## Decisions Made

See `key-decisions` in the frontmatter: the single-commit landing (a lint-driven necessity, not a
scope change) and the deliberate bound on the instructions/corpus claim to `14-EVIDENCE.md`'s own
wording.

## Deviations from Plan

### Structural (documented, not a defect)

**1. Tasks 1 and 2 landed as one commit instead of two**
- **Found during:** preparing Task 1's commit in isolation
- **Issue:** Task 1's own action text imports `ScriptedProvider`, `ApprovalMode`, `Completion` and
  `Usage` are used only by Task 2's `test_real_stdio_schema_deferral_end_to_end` test. A
  Task-1-only commit containing those imports with nothing yet consuming them fails
  `ruff check`'s `F401` (unused import) rule, which this plan's own verification step requires to
  pass at every commit.
- **Resolution:** Landed both tasks' test additions in one commit, matching the identical,
  already-documented precedent in this phase's `14-01-SUMMARY.md` ("Context import...") and
  `14-04-SUMMARY.md`'s own Task-1/Task-2 forward-reference note. No production code involved; no
  test was weakened to work around this.
- **Committed in:** `32eae0e`

No code-behavior deviations: every test passed on the first written attempt with no production
bug uncovered (`git status --porcelain src/` empty throughout, confirmed after every command).

---

**Total deviations:** 1 (structural, commit-count only — not a Rule 1-4 category, no code fix
involved).
**Impact on plan:** None on scope or correctness; both tasks' full acceptance criteria are met by
the single commit's diff.

## Issues Encountered

None. The `mcp` extra, the live fixture, and all machinery from plans 14-01/14-03/14-04 were
available and worked as documented on the first attempt; no timing flake was observed across 3
consecutive runs of each new test group.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SC1 (server instructions + schema deferral), SC2 (same-turn budget) and SC3 (list_changed,
  progress, logging routed through the real harness) are now proven over a real stdio session, not
  only the fakes plans 14-03/14-04 used — closing this phase's own "real corpus, not just fakes"
  precedent from plans 12-06/13-05. `docs/mcp-conformance-matrix.md` / `ARCHITECTURE.md` §15 /
  `CHANGELOG.md` / `REQUIREMENTS.md` traceability updates remain for this phase's own signoff plan
  (14-06), matching every prior phase's sequencing (11-04, 12-07, 13-06).
- 14-06 may cite `14-EVIDENCE.md`'s `## Conclusion for SC1` verbatim (quoted above) as the
  live-corpus half of the instructions story; this plan supplies the CI-fixture-rendering half.
- Full suite green: `pytest -q` 1435 passed (up from 1428), 0 failed, 14 deselected;
  `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` 36 passed on
  3 consecutive runs; `ruff check .` and `mypy src/agent86` both clean; `git status --porcelain
  src/` empty throughout. No blockers for 14-06.

## Self-Check

- `tests/integration/test_mcp_client.py` — FOUND (modified)
- Commit `32eae0e` — FOUND (`git log --oneline --all | grep 32eae0e`)

## Self-Check: PASSED

---

*Phase: 14-schema-deferral-and-notification-handling*
*Completed: 2026-09-25*
