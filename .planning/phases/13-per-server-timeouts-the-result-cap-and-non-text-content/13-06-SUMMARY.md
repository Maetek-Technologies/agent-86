---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
plan: 06
subsystem: mcp
tags: [mcp, docs, phase-signoff, conformance-matrix, adr-0004, evidence]

# Dependency graph
requires:
  - phase: 13-01
    provides: "13-EVIDENCE.md's live pinned-corpus audit and the 8,000-char ruling, and MCP-25 before-evidence"
  - phase: 13-02
    provides: "MCPServerConfig.connect_timeout_s/call_timeout_s/max_result_chars"
  - phase: 13-03
    provides: "render_content_block/truncate_result pure helpers"
  - phase: 13-04
    provides: "_content_to_text wired to render + cap; the cap extended to read_resource/get_prompt"
  - phase: 13-05
    provides: "real-stdio proof of SC1/SC2/SC3 over a live subprocess"
provides:
  - "13-EVIDENCE.md 'After the fix' section: the same server-everything non-text-block calls and one server-filesystem over-cap call, re-run through the FIXED MCPManager, next to 13-01's before-evidence"
  - "CHANGELOG/README/ARCHITECTURE.md documentation of MCP-21/MCP-22/MCP-25"
  - "docs/mcp-conformance-matrix.md: CAP-CONTENT-BLOCKS re-ruled implemented/in, its §15 row removed"
  - "13-VALIDATION.md signed off against real pytest/mypy/ruff results"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "After-fix live evidence re-runs the exact before-evidence calls through the production MCPManager code path (not the raw SDK), so a reader can compare before/after for the same tool+arguments"

key-files:
  created: []
  modified:
    - .planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md
    - CHANGELOG.md
    - README.md
    - docs/ARCHITECTURE.md
    - docs/mcp-conformance-matrix.md
    - .planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-VALIDATION.md

key-decisions:
  - "The after-fix evidence run reused 13-01's exact tool+argument pairs (get-tiny-image, get-resource-links, get-resource-reference, gzip-file-as-resource) plus server-filesystem's largest over-cap row (read_text_file on README.md, 47,415 chars) at both the default 8,000-char cap and an explicit 200000 override — the override reproduced 13-01's uncapped number byte-for-byte (47,415), confirming the cap only cuts, never corrupts"
  - "No new architectural change and no ADR added or edited — docs/mcp-conformance-matrix.md and ARCHITECTURE.md §15 only re-rule what plans 13-02..13-05 already shipped; test_docs_consistency.py's four-ADR pin stays satisfied"

requirements-completed: [MCP-21, MCP-22, MCP-25]

# Metrics
duration: ~50min
completed: 2026-09-24
---

# Phase 13 Plan 06: Phase signoff — live after-evidence, docs, and validation sign-off Summary

**Re-ran 13-01's exact non-text-block and over-cap corpus calls through the FIXED `MCPManager`, confirmed every marker and the cap/override behave as documented, wrote CHANGELOG/README/ARCHITECTURE entries for MCP-21/22/25, re-ruled `CAP-CONTENT-BLOCKS` implemented/in and removed its `ARCHITECTURE.md` §15 row, and signed off `13-VALIDATION.md` against a green `pytest -q` (1367 passed), `mypy` and `ruff`.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3
- **Files modified:** 6 (1 evidence file, 4 doc files, 1 validation contract)

## Accomplishments
- Live after-fix evidence: the same `server-everything@2026.8.31` calls 13-01 recorded as raw
  `str(chunk)` reprs (including an inlined base64 PNG) now render as named markers with no base64
  and no repr, verified by string check (`"data=" not in out and "Content(" not in out`) as well
  as visual inspection.
- The same `server-filesystem@2026.8.31` `read_text_file(README.md)` call that measured 47,415
  chars uncapped in 13-01 now truncates to exactly 8,000 chars plus a 149-char marker naming the
  server (`files`), the field (`max_result_chars`) and the dropped count (39,415) at the default
  cap, and reproduces the identical 47,415-char uncapped number when `max_result_chars=200000` is
  configured for that server — proving the override raises the ceiling with no other change to
  the text.
- CHANGELOG `[Unreleased]` now has three new entries (per-server timeouts/MCP-21, the result
  cap/MCP-22 citing the live corpus audit's over-cap tool list, and the non-text-content-rendering
  fix/MCP-25 including the discovered `is_error`/`isError` defect) and the pre-existing MCP-23
  bullet's stale "per-server configurable retry/backoff is MCP-21" phrase corrected to state what
  MCP-21 actually scoped.
- README gained a "Timeouts and the result cap are per server" paragraph naming the three new
  `[mcp.servers.<name>]` keys, their defaults, the visible marker shape, and `mcp-server-git`'s
  `git_show` as the worked "no narrowing argument — raise `max_result_chars`" example from
  13-EVIDENCE.md's Accepted risk.
- `docs/ARCHITECTURE.md` §7 item 2 gained two sentences on the per-server timeouts and the cap's
  extension to `read_resource`/`get_prompt`; the config reference block gained the three new
  fields and a "Fields added in v1.1" line; §15 lost the `CAP-CONTENT-BLOCKS` row and gained a
  departure note pointing at `docs/mcp-conformance-matrix.md`.
- `docs/mcp-conformance-matrix.md` re-rules `CAP-CONTENT-BLOCKS` `implemented`/`in`, citing
  `13-EVIDENCE.md`'s before/after render and plan 13-05's real-stdio fixture tests as corpus
  evidence; `CAP-TOOLS-CALL`'s reasoning cell now names the real per-server timeout/cap mechanism
  instead of the stale "120s hardcoded timeout"; "Rows ruled out" drops the `CAP-CONTENT-BLOCKS`
  bullet; "Not rated here" marks both the per-server-timeouts and prompt-side-result-cap bullets
  closed by Phase 13.
- `13-VALIDATION.md` signed off: every `TBD` cell replaced with a real `13-0x-0y` task ID, plan
  and wave, and the real passing command output; all five Wave 0 and six Validation Sign-Off
  checkboxes ticked; frontmatter `status: complete`, `nyquist_compliant: true`,
  `wave_0_complete: true`, approved 2026-09-24.
- Phase gate green: `pytest -q` 1367 passed, 0 failed (unchanged from 13-05's count — this plan
  added no test); `mypy src/agent86` clean; `ruff check .` clean;
  `pytest tests/unit/test_docs_consistency.py -q` 7 passed;
  `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` 29 passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Live after-evidence for MCP-25 and the cap, appended to 13-EVIDENCE.md** - `6adcfa7` (docs)
2. **Task 2: Document the three changes and re-rule CAP-CONTENT-BLOCKS** - `c78f4e7` (docs)
3. **Task 3: Sign off 13-VALIDATION.md and run the phase gate** - `578d273` (docs)

## Files Created/Modified
- `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md` - "After the fix" section appended, next to 13-01's before-evidence
- `CHANGELOG.md` - three `[Unreleased]` entries (MCP-21/22/25) plus the corrected MCP-23 bullet
- `README.md` - "Timeouts and the result cap are per server" paragraph
- `docs/ARCHITECTURE.md` - §7 item 2 extended, config reference block gains three fields, §15 loses the `CAP-CONTENT-BLOCKS` row and gains a departure note
- `docs/mcp-conformance-matrix.md` - `CAP-CONTENT-BLOCKS` re-ruled, `CAP-TOOLS-CALL` reasoning updated, "Rows ruled out"/"Not rated here" both updated
- `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-VALIDATION.md` - signed off against real results

## Decisions Made
See `key-decisions` in frontmatter — the after-fix evidence's reuse of 13-01's exact calls, and
that no ADR was added or edited (the four-ADR pin in `test_docs_consistency.py` stays satisfied).

## Deviations from Plan

None - plan executed exactly as written. The after-fix evidence run's `get-tiny-image` marker
rendered its em-dash (`—`) correctly in the committed file; a `cat`-based terminal display of the
raw script output earlier in this plan's execution visually truncated after that character (a
Windows console/cp1252 rendering artifact), which was verified as a display-only issue — not a
data issue — by re-reading the same bytes with an explicit UTF-8 decode and `repr()` before
writing anything into `13-EVIDENCE.md`. No file content was affected; nothing to fix.

## Issues Encountered
None beyond the display-only artifact documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 13's three success criteria (per-server timeouts, the result cap, non-text content
rendering) are documented, test-backed (unit, integration and real-stdio), evidenced live
before and after the fix, and `CAP-CONTENT-BLOCKS` is closed in both the conformance matrix and
`ARCHITECTURE.md` §15. `CAP-STRUCTURED-OUTPUT` stays out (unchanged, still pending a future
ruling). No blockers for the orchestrator's phase-gate verification.

---
*Phase: 13-per-server-timeouts-the-result-cap-and-non-text-content*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md`
- FOUND: `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-VALIDATION.md`
- FOUND: `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-06-SUMMARY.md`
- FOUND: commit `6adcfa7` (Task 1)
- FOUND: commit `c78f4e7` (Task 2)
- FOUND: commit `578d273` (Task 3)
