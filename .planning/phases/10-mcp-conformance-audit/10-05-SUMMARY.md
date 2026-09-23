---
phase: 10-mcp-conformance-audit
plan: 05
subsystem: docs
tags: [mcp, conformance-audit, adr, phase-breakdown, pytest, docs-consistency]

# Dependency graph
requires:
  - phase: 10-mcp-conformance-audit (plans 10-01..10-04)
    provides: "the pinned corpus, the four ADR rulings, the 22-row conformance matrix, ARCHITECTURE.md sec 15, and the docs-consistency test scaffold (xfail-marked) these plans wrote"
provides:
  - "The audit report's final section: a machine-checkable Sizing line plus 7 proposed phases (A=2, B=2, C=3) covering deferred requirements MCP-14 through MCP-26, each in exactly one phase"
  - "The 2026-07-28 modern-protocol adoption question routed to a named candidate finding, as its own workstream candidate, not folded into A/B/C"
  - "tests/unit/test_docs_consistency.py running unmarked and green (7 passed, 0 xfail), proven to actually fail via a deliberate break-and-restore check"
  - "docs/BACKLOG.md sec 999.0's precondition ('phases 999.0b-d written only after the matrix is ruled on') now satisfied, closing Phase 10 / MCP-13"
affects: [phase-11-plus (workstreams A/B/C, once written via /gsd:add-phase)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sizing statements backed by counts across three independent metrics (matrix rows, head-start findings, deferred-requirement count) rather than a single number, with an explicit correction where metrics disagree"
    - "A phase-gate consistency test proven via deliberate break-and-restore, not just by passing once"

key-files:
  created:
    - .planning/phases/10-mcp-conformance-audit/deferred-items.md
    - .planning/phases/10-mcp-conformance-audit/10-05-SUMMARY.md
  modified:
    - docs/mcp-conformance-audit-2026-09.md
    - tests/unit/test_docs_consistency.py

key-decisions:
  - "Sizing counted three ways (matrix rows, head-start findings, deferred-requirement count); the standing 'C is larger than A, materially larger than B' hypothesis is confirmed on findings (C=6 vs A=2) and requirement count (C=7 vs A=3), but corrected on raw matrix-row count (A=9 vs C=7) — both reported rather than asserting the hypothesis unchecked"
  - "The 2026-07-28 modern-protocol question is not folded into workstream A, B or C — it is recorded as a new, currently-unlisted workstream candidate, since none of MCP-14..26 assumes a protocol upgrade"
  - "ruff format --check .'s 74-file failure is pre-existing drift (last-touched dates 2026-09-19/21, before Phase 10) unrelated to this plan's files; logged to deferred-items.md rather than mass-reformatted outside scope"

requirements-completed: [MCP-13, MCP-02, MCP-03, MCP-04]

# Metrics
duration: ~13min
completed: 2026-09-23
---

# Phase 10 Plan 05: Workstream A/B/C Phase Breakdown + Phase Gate Summary

**Recommended a 7-phase A/B/C breakdown (sizing: A=9 rows/2 findings, B=1 row/1 finding, C=7 rows/6 findings — correcting the row-count half of the standing hypothesis while confirming it on findings and requirement count) and turned the cross-document consistency test from an xfail scaffold into an unmarked, break-and-restore-proven phase gate.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-09-23T03:50Z (approx, from prior plan's STATE.md timestamp)
- **Completed:** 2026-09-23T04:02Z
- **Tasks:** 2/2 completed
- **Files modified:** 2 (plus 1 new deferred-items.md)

## Accomplishments

- Replaced the audit report's `_(filled by plan 10-05)_` placeholder with a machine-checkable
  `Sizing:` line and 7 fully-specified proposed phases (Phases 11-17), covering every deferred
  requirement MCP-14 through MCP-26 exactly once, with all eight required labels per phase.
- Computed sizing three independent ways from the matrix and the audit report's own head-start
  routing table, and reported all three rather than asserting the standing hypothesis unchecked —
  confirmed on two metrics, corrected on one.
- Routed the `2026-07-28` modern-protocol adoption question (Open Question 1 from 10-RESEARCH.md)
  into a named "candidate findings" subsection as its own workstream candidate, with all five
  required technical citations (`MODERN_PROTOCOL_VERSIONS`, `server/discover`, `SEP-2577`,
  `session.py:619`).
- Deleted the Wave 0 `pytestmark = pytest.mark.xfail(...)` scaffold from
  `tests/unit/test_docs_consistency.py`; all 7 tests pass unmarked.
- Proved the consistency gate can actually fail: flipped `CAP-TRANSPORTS`'s ruling from `in` to
  `out` in the matrix, confirmed the suite went red with the exact expected message
  ("out-ruled but absent from ARCHITECTURE.md section 15: ['CAP-TRANSPORTS']"), restored the file
  via a plain edit, confirmed green again, confirmed `git diff docs/mcp-conformance-matrix.md` was
  empty afterward.
- Ran the full phase gate: `pytest tests/unit/test_docs_consistency.py -q` (7 passed),
  `pytest tests/integration/test_mcp_client.py -q` (11 passed), `pytest -q` (1249 passed, 14
  deselected, 0 failed, 0 xfailed/xpassed — up from 1242 passed/7 xpassed before the marker was
  removed), `ruff check .` (clean), `mypy src/agent86` (clean, 93 files).
- Read through and confirmed all four cross-document reference groups resolve to real targets:
  matrix → audit report and all four ADRs; `ARCHITECTURE.md` §15 → matrix; ADRs 0001/0002 →
  audit report's MCP-07 section (ADRs 0003/0004 carry no such citation and needed none — not a
  broken path, just absent, and the instruction was to fix broken paths, not add new ones);
  audit report's workstream breakdown → matrix.

## Task Commits

Each task was committed atomically:

1. **Task 1: Recommend the workstream A/B/C phase breakdown (MCP-13)** - `88aafc5` (docs)
2. **Task 2: Un-xfail the consistency check and take the phase gate** - `20aa615` (test)

## Files Created/Modified

- `docs/mcp-conformance-audit-2026-09.md` - Added the `Sizing:` line, the derivation methodology
  paragraph, 7 `#### Proposed Phase` blocks (Phases 11-17), a `##### Deferred requirements not
  proposed` closing list (empty — all 13 placed), the `### Candidate findings outside the three
  workstreams` subsection (the 2026-07-28 question plus three no-ID matrix rows), and the closing
  `/gsd:add-phase` handoff.
- `tests/unit/test_docs_consistency.py` - Removed the Wave 0 `pytestmark` xfail block and the now-
  unused `import pytest`; the 7 tests it pins (matrix shape, corpus column, ruling+reasoning,
  §15 cross-reference, 4-ADR existence) now run and pass unmarked.
- `.planning/phases/10-mcp-conformance-audit/deferred-items.md` (new) - Logs the pre-existing
  74-file `ruff format --check .` drift found during the phase gate, out of this plan's scope.

## Decisions Made

- **Sizing metrics disagree on A vs C by row count; reported honestly rather than forcing
  confirmation.** By matrix-row count, workstream A (9 rows — resources, resource templates,
  resource subscribe, prompts, completion, sampling, elicitation, roots, tool annotations, each
  its own row) is larger than C (7 rows). By head-start findings (C=6 vs A=2) and deferred-
  requirement count (C=7 vs A=3), C is clearly larger. The Sizing line and its methodology
  paragraph state both, and conclude C is larger "on findings and deferred-requirement count and
  materially larger than B on every count," correcting the hypothesis "only on raw matrix-row
  count."
- **The 2026-07-28 protocol-modernization question gets its own workstream candidate slot,** not a
  forced fit into A, B or C — none of the 13 deferred requirements assumes a protocol upgrade, and
  folding it into an existing workstream would misrepresent its scope (it touches the handshake
  layer every capability sits on top of, not one capability).
- **CAP-RESOURCE-SUBSCRIBE is deliberately double-counted** (once in workstream A's row total, once
  in C's) because it genuinely needs both A's `subscribe_resource` call site and C's
  `message_handler` notification plumbing to fully close — recorded explicitly in the methodology
  paragraph rather than silently picking one workstream.
- **CAP-TRANSPORTS chosen for the break-and-restore check** because it's currently `in`-ruled and
  fully implemented — flipping it to `out` creates a genuinely new, currently-uncovered §15 gap
  (rather than duplicating an already-`out` row), making the test's failure meaningful.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking/out-of-scope] Logged, did not fix, 74-file `ruff format --check .` drift**
- **Found during:** Task 2, running the phase gate (`ruff format --check .`)
- **Issue:** `ruff format --check .` (ruff 0.15.21) reports 74 files under `tests/tui/` and
  `tests/unit/` "would be reformatted" — none touched by this plan or this phase.
  `tests/unit/test_docs_consistency.py` (this plan's only owned test file) is correctly formatted
  and not in the list.
- **Why not fixed:** Spot-checked two files' last-modified commits — `tests/tui/test_mcp_manager.py`
  (`10987d2`, 2026-09-21, Phase 8) and `tests/unit/test_config.py` (`0dedc8b`, 2026-09-19,
  Phase 7) — both predate Phase 10 entirely. A sample diff shows pure whitespace/line-wrap
  changes consistent with a ruff-version drift since those files were last formatted, not a defect
  this phase introduced. Per the scope boundary rule, 74 unrelated files across two test
  directories were not mass-reformatted here.
- **Action taken:** Logged to `.planning/phases/10-mcp-conformance-audit/deferred-items.md` with
  the evidence above and a recommendation that a future dedicated housekeeping pass reformat the
  tree in its own reviewable commit.
- **Files modified:** `.planning/phases/10-mcp-conformance-audit/deferred-items.md` (new file;
  no source or test file reformatted)
- **Committed in:** `20aa615` (part of Task 2's commit)

---

**Total deviations:** 1 logged-not-fixed (out-of-scope pre-existing formatting drift)
**Impact on plan:** No scope creep; `ruff check .` (lint) and `mypy src/agent86` both pass clean,
and this plan's own files are correctly formatted. The `ruff format --check .` failure is a
pre-existing, project-wide condition unrelated to Phase 10's file set — recorded for visibility,
not silently ignored and not out-of-scope-fixed.

## Issues Encountered

None beyond the logged deviation above.

## Deliberate Break-and-Restore Check (Task 2, required by plan)

1. **Break:** Edited `docs/mcp-conformance-matrix.md`'s `CAP-TRANSPORTS` row, flipping its
   `Ruling` cell from `in` to `out` (a capability not present in `ARCHITECTURE.md` §15, since it
   was never ruled out before).
2. **Confirm red:** `pytest tests/unit/test_docs_consistency.py -q` → `1 failed, 6 passed`, with
   `test_every_out_ruling_lands_in_architecture_section_15` failing on
   `AssertionError: out-ruled but absent from ARCHITECTURE.md section 15: ['CAP-TRANSPORTS']` —
   the exact message the acceptance criteria specify.
3. **Restore:** Edited the same line back (`out` → `in`), via a plain string edit, never
   `git checkout`.
4. **Confirm green:** `pytest tests/unit/test_docs_consistency.py -q` → `7 passed`.
5. **Confirm no residue:** `git diff docs/mcp-conformance-matrix.md` → empty output;
   `git status --porcelain docs/mcp-conformance-matrix.md` → empty.

Result: the gate is proven to actually fail when violated, not merely proven to pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Phase 10 (MCP Conformance Audit) is complete.** All 12 Phase-10 requirements (MCP-02 through
  MCP-13) are now satisfied; MCP-13 was the last, closed by this plan.
- **`docs/BACKLOG.md` § 999.0's precondition is satisfied:** "phases 999.0b-d are written only
  after the matrix is ruled on" — the matrix (`docs/mcp-conformance-matrix.md`) is ruled, and this
  plan's 7 proposed phases give `/gsd:add-phase` everything it needs (Goal, Depends on,
  Requirements, Success Criteria, Sizing signal, Risk/constraint) without further research.
- **Next command, once per proposed phase:** `/gsd:add-phase`, starting with whichever workstream
  the milestone owner prioritizes — Phase 15 (workstream C, the zombie-tool fix) has no
  dependencies and is a pure bugfix; Phase 11 (workstream A, resources/prompts) has no
  dependencies either; Phase 13 (workstream B, OAuth) is flagged as strains-constraints-hardest and
  should begin with an actual connection to GitHub's hosted server, which this audit did not make.
- **No blockers.** `git status --porcelain src/` is empty throughout; the harness itself is
  untouched by this audit-only phase.

---
*Phase: 10-mcp-conformance-audit*
*Completed: 2026-09-23*

## Self-Check: PASSED

- FOUND: `docs/mcp-conformance-audit-2026-09.md`
- FOUND: `tests/unit/test_docs_consistency.py`
- FOUND: `.planning/phases/10-mcp-conformance-audit/deferred-items.md`
- FOUND: `.planning/phases/10-mcp-conformance-audit/10-05-SUMMARY.md`
- FOUND commit: `88aafc5` (Task 1)
- FOUND commit: `20aa615` (Task 2)
