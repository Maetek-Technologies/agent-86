---
phase: 11-resources-and-prompts-become-first-class
plan: 04
subsystem: docs
tags: [mcp, conformance-matrix, architecture-docs, changelog, phase-signoff]

# Dependency graph
requires:
  - phase: 11-resources-and-prompts-become-first-class
    provides: "plan 11-01's CI fixture/fake-session test machinery, plan 11-02's five capability-gated resource tools and MCPManager call sites, plan 11-03's three prompt/completion tools and call sites — all cited as corpus evidence by this plan's matrix rewrite"
provides:
  - "11-EVIDENCE.md — verbatim live transcripts against the pinned @2026.8.31 server-filesystem and server-everything packages, closing 11-RESEARCH.md Open Question 2"
  - "docs/mcp-conformance-matrix.md with CAP-RESOURCES/CAP-RESOURCE-TEMPLATES/CAP-PROMPTS/CAP-COMPLETION rated implemented and CAP-RESOURCE-SUBSCRIBE rated partial, all five ruled in"
  - "docs/ARCHITECTURE.md section 15 with the five matching non-goal rows removed and the departure recorded in its own block-quote; section 7 names the new per-server tool surface"
  - "README 'Connecting MCP servers' section documenting the eight capability-gated tools and the advertised-capability gate"
  - "CHANGELOG [Unreleased] Added entry for MCP-14/MCP-15"
  - "11-VALIDATION.md signed off: nyquist_compliant true, status complete, every per-task row filled with real pytest results"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live-evidence-before-doc-edit ordering: 11-EVIDENCE.md's transcripts were gathered and committed before docs/mcp-conformance-matrix.md was touched, so the matrix's corpus citations point at a file that already exists in git history"

key-files:
  created:
    - .planning/phases/11-resources-and-prompts-become-first-class/11-EVIDENCE.md
    - .planning/phases/11-resources-and-prompts-become-first-class/11-04-SUMMARY.md
  modified:
    - docs/mcp-conformance-matrix.md
    - docs/ARCHITECTURE.md
    - README.md
    - CHANGELOG.md
    - .planning/phases/11-resources-and-prompts-become-first-class/11-VALIDATION.md

key-decisions:
  - "SC1 recorded as 'not met', not 'blocked': the live server-filesystem@2026.8.31 run succeeded (npx.cmd connected on the first attempt, no retry needed) and returned a definitive, verified fact — this package's server_capabilities.resources is None, and both resources/list and resources/templates/list answer JSON-RPC -32601 Method not found. That is real, recorded live evidence, not an unavailable/blocked run, so the plan's 'do not fabricate a transcript, write blocked' fallback does not apply here; instead the honest verdict is recorded and the matrix's CAP-RESOURCES/CAP-RESOURCE-TEMPLATES corpus cells cite the CI fixture's real stdio round trip (plan 11-02) as their evidence, with this finding named explicitly in the reasoning."
  - "The roadmap's literal SC1 wording (a server-filesystem list_resources -> read_resource round trip) is answered honestly as not achievable against the currently published corpus member, rather than substituting a different server or reinterpreting the criterion — Phase 10's D-11 pin (@2026.8.31, re-verified) governs which package version is authoritative evidence, and that is the version tested."
  - "11-VALIDATION.md's 'Both manual live-evidence runs (SC1, SC2) recorded before the matrix is edited' sign-off box is ticked: both runs genuinely happened and were written into 11-EVIDENCE.md before docs/mcp-conformance-matrix.md's Task 2 edit, regardless of SC1's negative verdict — the box measures whether recording preceded editing, not whether every verdict came back positive."

requirements-completed: [MCP-14, MCP-15]

# Metrics
duration: ~45min
completed: 2026-09-24
---

# Phase 11 Plan 04: Phase Signoff — Live Evidence and Conformance Re-Ruling Summary

**Two real MCP client-server round trips (server-filesystem, server-everything@2026.8.31) recorded verbatim, then four conformance-matrix rows moved from `absent`/`out` to `implemented`/`in` and one to `partial`/`in`, closing Phase 11.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-09-24 (approx, first Read)
- **Completed:** 2026-09-24
- **Tasks:** 3
- **Files modified:** 6 (1 created: `11-EVIDENCE.md`; 5 modified: matrix, `ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, `11-VALIDATION.md`)

## Accomplishments

- **SC1 (server-filesystem) — run to completion, verdict "not met" with a real finding.** A
  scratchpad script drove `agent86.tools.mcp_client.MCPManager` against the pinned
  `@modelcontextprotocol/server-filesystem@2026.8.31` (re-verified via `npm view` immediately
  before the run — unchanged from Phase 10's D-11 pin). The package connected cleanly, mounted 14
  `tools/*` tools, and declared `server_capabilities.resources = None` — no `resources` capability
  at all. Both `resources/list` and `resources/templates/list` answered JSON-RPC `-32601 Method
  not found`. A fallback probe through the server's actual surface (`read_text_file`) confirmed the
  test file's exact text (`phase-11 resource evidence`) does reach the caller — just not via
  `resources/read`, because this server has no `resources/read` at all. This is a genuine,
  reproducible fact about the currently published third-party package, not an agent86 defect.
- **SC2 (server-everything) — run to completion, verdict "met".** The same pattern against the
  pinned `@modelcontextprotocol/server-everything@2026.8.31` succeeded in full: `list_prompts`
  returned 4 prompts (the roadmap's own text anticipated 3 — recorded as observed, not "corrected"
  to match), `get_prompt` rendered three of the four with supplied arguments (the fourth,
  `resource-prompt`, correctly failed the server's own enum validation on a placeholder value —
  exercising the soft-`ToolResult`-error contract, not an agent86 bug), and `complete()` returned
  real, non-empty suggestions for `completable-prompt`'s `department` argument
  (`Engineering`/`Sales`/`Marketing`/`Support`), closing 11-RESEARCH.md Open Question 2 with the
  real prompt and argument names.
- **`docs/mcp-conformance-matrix.md` re-ruled.** `CAP-RESOURCES`, `CAP-RESOURCE-TEMPLATES`,
  `CAP-PROMPTS` and `CAP-COMPLETION` moved `absent`→`implemented`; `CAP-RESOURCE-SUBSCRIBE` moved
  `absent`→`partial` (D-10: both call sites ship, but the update notification is still dropped —
  MCP-24). All five moved `out`→`in`. Every reasoning cell cites concrete file:line/plan evidence,
  and `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES` explicitly name the `11-EVIDENCE.md` finding that
  `server-filesystem` itself doesn't exercise them — their corpus evidence is the CI fixture's real
  stdio round trip (plan 11-02) instead. The five matching "Rows ruled out" bullets were deleted;
  the header line gained a "Re-audited 2026-09-23" mark; `docs/mcp-conformance-audit-2026-09.md`
  was left untouched (D-09).
- **`docs/ARCHITECTURE.md` section 15 closed out.** The five matching `Not built` rows were
  deleted, the departure recorded in the section's own block-quote (naming the real call sites that
  shipped and the one thing that didn't — the resource-update notification, MCP-24), and one new
  sentence added after the conformance paragraph. Section 7's "MCP client" bullet now names the new
  per-server tool surface (`list_resources`, `read_resource`, `list_resource_templates`,
  `subscribe_resource`, `unsubscribe_resource`, `list_prompts`, `get_prompt`, `complete`) and the
  capability gate that governs it.
- **README and CHANGELOG updated; `11-VALIDATION.md` signed off.** README's "Connecting MCP
  servers" section gained a paragraph naming the eight tools and the "only if advertised" gate.
  CHANGELOG's `[Unreleased]` gained an `### Added` entry citing MCP-14/MCP-15. `11-VALIDATION.md`'s
  per-task verification map was filled in with real `pytest` results (all green), both manual rows
  record their actual verdicts, every sign-off box is ticked, and the frontmatter moved to
  `nyquist_compliant: true` / `status: complete` / `evidence: 11-EVIDENCE.md`.
- Full suite green: **1264 passed**, 14 deselected, 0 failed; `ruff check .` and
  `mypy src/agent86` both clean. `git status --porcelain src/ tests/` empty throughout — this plan
  touched no production code and no test, exactly as scoped.

## Task Commits

Each task was committed atomically:

1. **Task 1: Gather the two live-evidence runs and write 11-EVIDENCE.md** - `a4089db` (docs)
2. **Task 2: Re-rule the five matrix rows and strip them from ARCHITECTURE.md section 15** - `f77c688` (docs)
3. **Task 3: User-facing docs, CHANGELOG, and the phase validation sign-off** - `391cefc` (docs)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified

- `.planning/phases/11-resources-and-prompts-become-first-class/11-EVIDENCE.md` - New: verbatim SC1/SC2 transcripts, capability declarations table, deviations/findings
- `docs/mcp-conformance-matrix.md` - Five rows re-rated (four `implemented`, one `partial`), all ruled `in`; matching "Rows ruled out" bullets deleted; header re-audited mark added
- `docs/ARCHITECTURE.md` - Section 15's five matching `Not built` rows deleted, departure recorded in the block-quote and the conformance paragraph; section 7 names the new tool surface
- `README.md` - "Connecting MCP servers" gains a paragraph on the resource/prompt/completion tools and their capability gate
- `CHANGELOG.md` - `[Unreleased]` gains an `### Added` entry for MCP-14/MCP-15
- `.planning/phases/11-resources-and-prompts-become-first-class/11-VALIDATION.md` - Per-task map filled with real results, manual rows recorded, sign-off ticked, frontmatter moved to complete

## Decisions Made

See `key-decisions` in the frontmatter above: SC1 is recorded as a genuine "not met" verdict backed
by real evidence rather than treated as a "blocked" run (the plan's fallback for an unavailable
`npx`/download); the roadmap's literal wording is answered honestly against the pinned corpus
member rather than reinterpreted or substituted; and the "both runs recorded before the matrix is
edited" sign-off box is ticked because both runs did happen and were written down first, independent
of SC1's negative outcome.

## Deviations from Plan

### Documented, Non-Blocking

**1. SC1 could not be satisfied as literally worded, for a reason the plan did not anticipate**
- **Found during:** Task 1
- **Issue:** The plan's contingency text anticipated one specific shape of "SC1 still passes despite
  a surprise": "If `server-filesystem` exposes its files only as resource *templates* rather than
  concrete resources ... that still satisfies SC1." The actual, verified behavior of the pinned
  `@2026.8.31` release is stronger than that: it declares no `resources` capability at all
  (`server_capabilities.resources = None`), and both `resources/list` and
  `resources/templates/list` return JSON-RPC `-32601 Method not found`. This is not a templates-vs-
  concrete-resources shape difference; it is the complete absence of the capability in the current
  package.
- **Assessment:** This is a real, externally-verified fact about a third-party package agent86 does
  not control (re-confirmed via `npm view` immediately before the run, same version as Phase 10's
  D-11 pin), not a defect in agent86's own code — `_capability_tools`'s gate behaved exactly as
  designed by mounting zero resource tools for a server that never declared the capability.
- **Fix:** None applied to code (none is warranted — `_capability_tools`'s gate is correct
  behavior). `11-EVIDENCE.md` records the finding in full, including a fallback probe proving the
  file's exact text does reach the caller through the server's actual `tools/read_text_file`
  surface. `docs/mcp-conformance-matrix.md`'s `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES` reasoning
  cells cite the CI fixture's real stdio round trip (plan 11-02) as their corpus evidence instead of
  this server, and name the finding explicitly rather than silently substituting evidence.
- **Files modified:** None beyond the plan's own scoped edits (`11-EVIDENCE.md`,
  `docs/mcp-conformance-matrix.md`).
- **Verification:** `grep -c "resources=None" .planning/phases/11-resources-and-prompts-become-first-class/11-EVIDENCE.md` finds the raw `server_capabilities` line; `pytest tests/unit/test_docs_consistency.py -q` — 7 passed.
- **Committed in:** `a4089db` (Task 1), `f77c688` (Task 2 reasoning cells)

**2. server-everything returned 4 prompts, not the roadmap's anticipated 3**
- **Found during:** Task 1
- **Issue:** The roadmap's own text for SC2 says "the roadmap expects 3." The pinned
  `@2026.8.31` package returns `simple-prompt`, `args-prompt`, `completable-prompt` and
  `resource-prompt` — four, not three.
- **Assessment:** The demo package evolved since the roadmap text was written (consistent with
  Phase 10's MCP-07 finding that this same package's tool set had also grown two tools beyond what
  10-RESEARCH.md's docs-based read expected). Not a defect; recorded as observed.
- **Fix:** None — `11-EVIDENCE.md` records the actual count and names; no roadmap or planning
  document was edited to retroactively match the anticipated number.
- **Files modified:** None beyond `11-EVIDENCE.md`.
- **Verification:** `grep -c "Prompt count:" .planning/phases/11-resources-and-prompts-become-first-class/11-EVIDENCE.md` returns 1, showing "4 (the roadmap expects 3 ...)".
- **Committed in:** `a4089db` (Task 1)

---

**Total deviations:** 2 documented, non-blocking (both are real findings about third-party MCP
server behavior recorded honestly, not agent86 defects requiring a fix)
**Impact on plan:** None on functionality or test coverage — every acceptance criterion measuring
actual load-bearing behavior (matrix shape, docs-consistency test, full suite, ruff, mypy, no
src/tests changes) passes. The only effect is that `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`'s
"Exercised by corpus" cells cite the CI fixture rather than a live `server-filesystem` run, stated
explicitly rather than glossed over.

## Issues Encountered

None beyond the two documented findings above. Both `npx.cmd` runs connected and completed in a
single attempt each — no retry or fallback to bare `npx` was needed, matching Phase 10's MCP-07
precedent.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 11 is complete: `11-VALIDATION.md` is signed off (`nyquist_compliant: true`,
  `status: complete`), `MCP-14` and `MCP-15` are both closed, and
  `docs/mcp-conformance-matrix.md`/`docs/ARCHITECTURE.md` no longer describe resources, resource
  templates, prompts or completion as non-goals.
- `CAP-RESOURCE-SUBSCRIBE` remains `partial` — its remaining half (the
  `notifications/resources/updated` delivery) is explicitly routed to MCP-24, workstream C, not
  silently dropped.
- No blockers for whichever workstream-A/B/C phase is written next via `/gsd:add-phase`; this
  plan's own scope boundary (`git status --porcelain src/ tests/` empty throughout) held for the
  entire plan.

---
*Phase: 11-resources-and-prompts-become-first-class*
*Completed: 2026-09-24*

## Self-Check: PASSED

All claimed files found on disk (`11-EVIDENCE.md`, `docs/mcp-conformance-matrix.md`,
`docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md`, `11-VALIDATION.md`, this summary); all three
task commit hashes (`a4089db`, `f77c688`, `391cefc`) found in git history.
