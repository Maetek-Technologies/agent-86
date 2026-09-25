---
phase: 14-schema-deferral-and-notification-handling
plan: 06
subsystem: mcp
tags: [mcp, docs, phase-signoff, conformance-matrix, adr-0003, human-verify, notifications]

# Dependency graph
requires:
  - phase: 14-01
    provides: "14-EVIDENCE.md's live-corpus instructions finding and the CI fixture's notification/instructions probes"
  - phase: 14-02
    provides: "the names + instructions section wired into the system message"
  - phase: 14-03
    provides: "MCPTool schema deferral (ADR 0003), server_instructions()/prompt_catalog()"
  - phase: 14-04
    provides: "MCPManager._on_notification routing (list_changed re-fetch, progress, logging, resource updates)"
  - phase: 14-05
    provides: "real-stdio proof of SC1/SC2/SC3 over a live subprocess and Harness"
provides:
  - "docs/mcp-conformance-matrix.md and docs/ARCHITECTURE.md §7/§15 re-ruled to describe exactly
    what Phase 14 closed (CAP-LIST-CHANGED, CAP-PROGRESS, CAP-RESOURCE-SUBSCRIBE implemented/in;
    CAP-LOGGING partial/out; CAP-CANCELLATION stays absent/out with the SDK-dispatcher finding)"
  - "CHANGELOG/README document schema deferral (MCP-20) and notification handling (MCP-24) as
    user-facing behavior"
  - "14-VALIDATION.md signed off with every TBD replaced by a real task ID/command/count,
    nyquist_compliant: true, and the 14-06-03 human checkpoint approved 2026-09-25"
  - "A human confirmed live in the TUI: a mid-session tools/list_changed mounts a new tool
    (mcp__live__dynamic_echo), the deferred schema materialises and becomes callable, and
    progress notes appear — all with no restart"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase signoff sequencing (docs -> validation sign-off -> human checkpoint) matches every
      prior phase in this milestone (11-04, 12-07, 13-06)"

key-files:
  created:
    - .planning/phases/14-schema-deferral-and-notification-handling/14-06-SUMMARY.md
  modified:
    - docs/mcp-conformance-matrix.md
    - docs/ARCHITECTURE.md
    - CHANGELOG.md
    - README.md
    - .planning/phases/14-schema-deferral-and-notification-handling/14-VALIDATION.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "No ADR added or edited for this plan — ADR 0003 (schema deferral) is an accepted record from
    Phase 10; test_docs_consistency.py's four-ADR pin stays satisfied (ls docs/adr/*.md == 4,
    git diff --stat docs/adr/ empty)"
  - "The SC1 'server instructions' claim in every doc is bounded exactly to 14-EVIDENCE.md's own
    Conclusion for SC1 (server-everything sets instructions live; the CI fixture proves rendering)
    — not restated or strengthened in CHANGELOG/README/ARCHITECTURE.md"
  - "REQUIREMENTS.md traceability rows for MCP-20/MCP-24 were added by hand (Phase 11/13 precedent)
    because gsd-tools requirements mark-complete only toggles existing '- [ ] **ID**' checkboxes,
    and MCP-20/MCP-24 were still plain '- **ID**:' bullets under 'Future Requirements (deferred)'
    with no checkbox to toggle"

requirements-completed: [MCP-20, MCP-24]

# Metrics
duration: ~15min (Task 3 checkpoint + wrap-up only; Tasks 1-2 completed in a prior session, see
  their own commits)
completed: 2026-09-25
---

# Phase 14 Plan 06: Phase signoff — matrix/ARCHITECTURE re-ruling, CHANGELOG/README, and human-verified live notifications Summary

**Re-ruled the MCP conformance matrix and ARCHITECTURE.md §7/§15 to describe exactly what Phase 14 closed (list_changed, progress, resource-subscribe notifications, and ADR 0003 schema deferral), documented it in CHANGELOG/README, signed off 14-VALIDATION.md against real command output, and got a human-confirmed live TUI verification that a mid-session `tools/list_changed` mounts a new tool with no restart.**

## Performance

- **Duration:** ~15 min for this session (Task 3 checkpoint resolution + STATE/ROADMAP/REQUIREMENTS
  wrap-up); Tasks 1-2 (docs re-ruling, CHANGELOG/README/validation sign-off) were completed in a
  prior session — see their own commits below
- **Tasks:** 3/3 completed
- **Files modified:** 8 across the full plan (5 in Tasks 1-2, 3 more in this session's wrap-up:
  14-VALIDATION.md's approval line, REQUIREMENTS.md, STATE.md/ROADMAP.md)

## Accomplishments

- `docs/mcp-conformance-matrix.md` re-rules `CAP-LIST-CHANGED`, `CAP-PROGRESS`, and
  `CAP-RESOURCE-SUBSCRIBE` `implemented`/`in`; `CAP-LOGGING` `partial`/`out`; `CAP-CANCELLATION`
  stays `absent`/`out` with the SDK-dispatcher-consumes-it finding recorded
  (`mcp/client/session.py:1435-1437`). No `CAP-SCHEMA-DEFERRAL` row was added — schema deferral is
  recorded under "Not rated here" per ADR 0003, per the plan's own ruling.
- `docs/ARCHITECTURE.md` §7 item 2 gained sentences on schema deferral (ADR 0003) and live
  notification routing; §15 dropped the `CAP-PROGRESS`/`CAP-LIST-CHANGED` rows and gained a
  departure block-quote; `CAP-LOGGING`'s row text was updated; `CAP-CANCELLATION`'s row stayed.
  `pytest tests/unit/test_docs_consistency.py -q` — 7 passed; `ls docs/adr/*.md` — 4 files,
  `git diff --stat docs/adr/` empty (no ADR touched).
- `CHANGELOG.md` gained two `[Unreleased]` bullets — schema deferral (ADR 0003, closes MCP-20) and
  MCP server notification handling (closes MCP-24) — and corrected the Phase 11 bullet's stale
  "resource update notifications are still dropped" sentence to point at the new MCP-24 entry.
  `README.md` gained a "MCP tool lists stay live" paragraph describing deferred schemas and live
  `list_changed`/progress/resource-update behavior as `mcp:` notes.
- `14-VALIDATION.md` was signed off against real results: every `TBD` replaced with a real task
  ID/plan/wave and real passing command output (`pytest -q` 1435 passed; `mypy src/agent86` clean;
  `ruff check .` clean; `pytest tests/unit/test_docs_consistency.py -q` 7 passed;
  `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py
  tests/integration/test_scripting_contract.py -q` 55 passed); frontmatter
  `status: complete`, `nyquist_compliant: true`, `wave_0_complete: true`.
- **Task 3 (the human checkpoint) approved.** The user ran the six how-to-verify steps in the TUI
  against a scratch `.agent86/config.toml` pointing at `tests/integration/live_mcp_server.py` with
  `AGENT86_LIVE_MCP_NOTIFY_TOOLS=1` and `AGENT86_LIVE_MCP_INSTRUCTIONS="Prefer shout for
  emphasis."` on 2026-09-25, and replied verbatim: **"approved"**. Row 14-06-03's Status was set to
  green and `14-VALIDATION.md`'s `**Approval:**` line set to `approved 2026-09-25`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Re-rule the matrix and update ARCHITECTURE §7/§15** - `bb261ef` (docs)
2. **Task 2: CHANGELOG, README, and 14-VALIDATION.md sign-off against real results** - `1369399` (docs)
3. **Task 3: Human verification — a mid-session tool-list change appears in the TUI** - `a3ed48e` (docs)

**Plan metadata:** this commit (docs: complete plan) — see final commit below.

## Files Created/Modified

- `docs/mcp-conformance-matrix.md` - five rows re-ruled (CAP-LIST-CHANGED, CAP-PROGRESS,
  CAP-RESOURCE-SUBSCRIBE, CAP-LOGGING, CAP-CANCELLATION); "Rows ruled out" and "Not rated here"
  updated; header re-audit date appended
- `docs/ARCHITECTURE.md` - §7 item 2 gained schema-deferral and notification-routing sentences;
  §15 dropped two Not-built rows and gained a departure block-quote
- `CHANGELOG.md` - two new `[Unreleased]` entries (MCP-20, MCP-24); Phase 11 bullet corrected
- `README.md` - new "MCP tool lists stay live" paragraph
- `.planning/phases/14-schema-deferral-and-notification-handling/14-VALIDATION.md` - fully signed
  off; row 14-06-03 set to green; Approval set to `approved 2026-09-25`
- `.planning/REQUIREMENTS.md` - MCP-20/MCP-24 converted to `[x]` checked, traceability rows added,
  coverage counts updated (21 mapped, 4 remaining deferred: MCP-16..19)
- `.planning/STATE.md` / `.planning/ROADMAP.md` - progress and session state updated via gsd-tools

## Decisions Made

See `key-decisions` in frontmatter: no ADR touched (schema deferral is ADR 0003, already accepted
from Phase 10); the SC1 instructions claim bounded exactly to `14-EVIDENCE.md`'s own Conclusion;
REQUIREMENTS.md traceability rows added by hand because `requirements mark-complete` only toggles
existing checkboxes and MCP-20/MCP-24 had none yet (matching Phase 11/13 precedent, where the
signoff plan itself converts the bullet to `- [x]` and adds the traceability row).

## Deviations from Plan

None - plan executed exactly as written. Tasks 1 and 2 were completed and committed in a prior
session; this session resumed at the Task 3 human-verify checkpoint exactly as specified in the
`<resume>` block, and completed the plan's remaining wrap-up steps (REQUIREMENTS.md traceability,
STATE.md/ROADMAP.md updates, final commit) per the resume instructions.

## Issues Encountered

None. `gsd-tools requirements mark-complete MCP-20 MCP-24` returned `not_found` for both IDs
because they were plain `- **ID**:` bullets with no checkbox (not yet mapped to a phase) — resolved
by hand-editing `.planning/REQUIREMENTS.md` per the Phase 11/13 precedent, converting each bullet
to `- [x] **ID**: ... — Phase 14`, adding two traceability table rows, and updating the coverage
counts and the "remaining deferred IDs" list (now MCP-16…MCP-19 only).

## User Setup Required

None - no external service configuration required. The scratch `.agent86/config.toml` used for
Task 3's human verification lived in the session scratchpad, never the repo
(`git status --porcelain` showed no scratch config).

## Next Phase Readiness

Phase 14 is now complete: 6/6 plans, MCP-20 and MCP-24 both closed and documented, with
CAP-PROGRESS's generic-not-attributed scope and CAP-CANCELLATION's non-closure written down in
both the matrix and `ARCHITECTURE.md` §15, the SC1 instructions claim bounded by real evidence, and
a human-confirmed live tool-list change in the TUI (approved 2026-09-25). This closes out the v1.1
"MCP Integration Depth" milestone's fourth and final written phase at 28/29 total plans complete
(97%) — the orchestrator's own `phase complete`/milestone-close verification is the only remaining
step, deliberately left to the orchestrator per this plan's own instruction not to run it here.

## Self-Check

- `docs/mcp-conformance-matrix.md` — FOUND (modified)
- `docs/ARCHITECTURE.md` — FOUND (modified)
- `CHANGELOG.md` — FOUND (modified)
- `README.md` — FOUND (modified)
- `.planning/phases/14-schema-deferral-and-notification-handling/14-VALIDATION.md` — FOUND (modified)
- `.planning/REQUIREMENTS.md` — FOUND (modified)
- Commit `bb261ef` — FOUND
- Commit `1369399` — FOUND
- Commit `a3ed48e` — FOUND

## Self-Check: PASSED

---
*Phase: 14-schema-deferral-and-notification-handling*
*Completed: 2026-09-25*
