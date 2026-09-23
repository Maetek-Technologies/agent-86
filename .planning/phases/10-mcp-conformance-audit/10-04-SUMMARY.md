---
phase: 10-mcp-conformance-audit
plan: 04
subsystem: docs
tags: [mcp, conformance, audit, architecture]
dependency_graph:
  requires:
    - docs/adr/0001-mcp-sampling-inversion-of-control.md
    - docs/adr/0002-mcp-elicitation-tier-1-surface.md
    - docs/adr/0003-mcp-schema-deferral-prompt-contract.md
    - docs/adr/0004-mcp-result-cap-location.md
    - docs/mcp-conformance-audit-2026-09.md
    - tests/unit/test_docs_consistency.py
  provides:
    - docs/mcp-conformance-matrix.md
  affects:
    - docs/ARCHITECTURE.md (§15)
tech_stack:
  added: []
  patterns:
    - "22-row client-side MCP capability matrix pinned to a single protocol revision"
    - "in/out ruling per capability, backed by a file:line citation and a corpus-exercise record"
key_files:
  created:
    - docs/mcp-conformance-matrix.md
  modified:
    - docs/ARCHITECTURE.md
decisions:
  - "CAP-SAMPLING / CAP-ELICITATION rulings copied verbatim from ADRs 0001/0002, not re-derived"
  - "CAP-DISCOVER deliberately has no row; 2026-07-28 stays unrated per D-01"
  - "No capability was ruled a permanent non-goal bullet — every out-ruling is deferred to a workstream or 'matrix' only, so §15(c)'s non-goals-bullet step was not exercised"
metrics:
  duration_minutes: 45
  completed: 2026-09-22
---

# Phase 10 Plan 04: MCP Conformance Matrix + ARCHITECTURE.md §15 Summary

22-row client-side MCP conformance matrix pinned to protocol revision `2025-11-25`, with every
"out" ruling landed in `docs/ARCHITECTURE.md` §15 as a stated non-goal.

## What Was Built

**`docs/mcp-conformance-matrix.md`** (Task 1) — one row per client-side MCP spec capability from
`tests/unit/test_docs_consistency.py`'s `_EXPECTED_IDS`, each carrying:
- An `implemented` / `partial` / `absent` rating with a file:line citation into
  `src/agent86/tools/mcp_client.py` or the installed `mcp` SDK's `session.py`, every citation
  spot-checked against the real file before being written (none needed correction — see below).
- An `Exercised by corpus` cell naming the pinned server(s), drawn from
  `docs/mcp-conformance-audit-2026-09.md`'s corpus table and its MCP-07 live-run section — never
  from memory.
- An `in`/`out` ruling with reasoning; `CAP-SAMPLING` and `CAP-ELICITATION` copied verbatim from
  ADRs 0001/0002, `CAP-STRUCTURED-OUTPUT`/`CAP-CONTENT-BLOCKS` from ADR 0004's Consequences.

The header pins `Protocol revision: 2025-11-25` with a "Why this revision" paragraph (D-01) and a
"How to read this" paragraph stating the BACKLOG § 999.0 demand rule verbatim. Below the table,
`## Rows ruled out` lists all 18 out-ruled IDs, and `## Not rated here` names the `2026-07-28`
protocol (routed to plan 10-05's workstream breakdown) and the four agent86-side strategies that
get no row (schema deferral, the result cap, per-server timeouts/reconnect, the
`_serve`/`_server_tools` desync), each pointed at where it *is* recorded.

**`docs/ARCHITECTURE.md` §15** (Task 2) — a new paragraph after the non-goals bullet list pointing
at the matrix and the audit report, plus 18 new rows appended to the existing
`| Not built | Area | Tracked |` table, one per out-ruled `CAP-*` id, each naming its area (`§7
tools` for 17 of the 18, `§9 observability` for `CAP-LOGGING`) and a tracking pointer (`matrix` or
`matrix; MCP-1x/2x` where a deferred requirement already exists). Sections 1-14 are byte-identical
to HEAD's first 1120 lines (verified by `cmp`, not by eye); the diff is 25 insertions, 0 deletions.

## Rating Distribution (22 rows)

| Rating | Count | IDs |
|---|---|---|
| implemented | 3 | CAP-TOOLS-LIST, CAP-TOOLS-CALL, CAP-TRANSPORTS |
| partial | 2 | CAP-TOOL-ANNOTATIONS, CAP-CONTENT-BLOCKS |
| absent | 17 | CAP-STRUCTURED-OUTPUT, CAP-RESOURCES, CAP-RESOURCE-TEMPLATES, CAP-RESOURCE-SUBSCRIBE, CAP-PROMPTS, CAP-COMPLETION, CAP-SAMPLING, CAP-ELICITATION, CAP-ROOTS, CAP-LOGGING, CAP-PROGRESS, CAP-CANCELLATION, CAP-PAGINATION, CAP-PING, CAP-LIST-CHANGED, CAP-META, CAP-OAUTH |

## Ruling Distribution

- **in (4):** CAP-TOOLS-LIST, CAP-TOOLS-CALL, CAP-TOOL-ANNOTATIONS, CAP-TRANSPORTS
- **out (18):** CAP-STRUCTURED-OUTPUT, CAP-CONTENT-BLOCKS, CAP-RESOURCES, CAP-RESOURCE-TEMPLATES,
  CAP-RESOURCE-SUBSCRIBE, CAP-PROMPTS, CAP-COMPLETION, CAP-SAMPLING, CAP-ELICITATION, CAP-ROOTS,
  CAP-LOGGING, CAP-PROGRESS, CAP-CANCELLATION, CAP-PAGINATION, CAP-PING, CAP-LIST-CHANGED,
  CAP-META, CAP-OAUTH — all 18 confirmed present, one per table row, in `docs/ARCHITECTURE.md` §15.

## Corpus Exercise Notes

- **Exercised only by `server-everything`** (the conformance instrument, a weaker demand signal
  than a realistic workload server) — 12 rows: CAP-TOOL-ANNOTATIONS, CAP-STRUCTURED-OUTPUT,
  CAP-CONTENT-BLOCKS, CAP-RESOURCE-SUBSCRIBE, CAP-PROMPTS, CAP-COMPLETION, CAP-SAMPLING (not
  reachable through agent86 even so — MCP-07), CAP-ELICITATION (same), CAP-ROOTS, CAP-LOGGING,
  CAP-PROGRESS, CAP-LIST-CHANGED.
- **Exercised by no corpus server** (`none`) — 5 rows: CAP-RESOURCE-TEMPLATES, CAP-CANCELLATION,
  CAP-PAGINATION, CAP-PING, CAP-META.
- **Exercised by a realistic server or a named non-instrument corpus member** — 5 rows:
  CAP-TOOLS-LIST, CAP-TOOLS-CALL, CAP-TRANSPORTS (all five corpus servers), CAP-RESOURCES
  (`server-everything` *and* `server-filesystem`, whose whole value proposition is file
  resources), CAP-OAUTH (GitHub's hosted remote server).

## Citation Corrections

None. Every file:line citation carried over from `10-RESEARCH.md` and
`docs/mcp-conformance-audit-2026-09.md` was independently re-opened and spot-checked against
`src/agent86/tools/mcp_client.py` and the installed SDK's `.venv/Lib/site-packages/mcp/client/
session.py` before being written into the matrix (`list_tools` at `mcp_client.py:221`,
`call_tool`/timeout at `286-295`, `_is_read_only` at `96-111`, the `_serve`/`_server_tools` desync
lines at `234`/`241-242`/`244-260`/`262-266`/`286-289`, `_content_to_text` at `426-434`,
`_open_transport` at `395-423`, `_resolve_server_secrets` at `336-358`, `structured_content` at
`mcp_types/_types.py:1474`, and the SDK's capability-gating block at `session.py:591-608`/`619`/
`212-213`/`245-248`). Every citation resolved to the exact claim it was cited for; none needed
correction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_RATINGS` enum violation on the sampling/elicitation/roots rows**
- **Found during:** Task 1 verification (`pytest tests/unit/test_docs_consistency.py --runxfail`)
- **Issue:** The plan's own action text describes these three ratings as
  `"absent, and correctly declared absent"`, which is exactly what I first wrote into the `Rating`
  column — but the plan's acceptance criteria (and the test's `_RATINGS = {"implemented",
  "partial", "absent"}`) require the cell to be exactly one of the three enum values, with the
  nuance moved to `Reasoning`. First run failed `test_every_row_rates_implementation` on
  `CAP-SAMPLING`.
- **Fix:** Changed the `Rating` cell to plain `absent` for `CAP-SAMPLING`, `CAP-ELICITATION`, and
  `CAP-ROOTS`; moved the "and correctly declared absent" language, with its file:line evidence,
  into the `Reasoning` cell.
- **Files modified:** `docs/mcp-conformance-matrix.md`
- **Commit:** `f91234a`

**2. [Rule 1 - Bug] Duplicate `server/discover` mention exceeded the acceptance-criteria grep bound**
- **Found during:** Task 1 acceptance-criteria pass (`grep -c "server/discover"` returned 2, criterion requires at most 1)
- **Issue:** "Why this revision" and "Not rated here" both named the literal string
  `server/discover`, tripping the count.
- **Fix:** Reworded the "Not rated here" bullet to say "its RPC-based discovery mechanism" instead
  of repeating the literal string, keeping the one occurrence in "Why this revision".
- **Files modified:** `docs/mcp-conformance-matrix.md`
- **Commit:** `f91234a` (caught and fixed before the first commit of Task 1 — no separate commit
  needed; no `--amend` was used at any point)

No architectural deviations. `src/` was never touched (`git status --porcelain src/` empty
throughout both tasks).

## Verification

- `pytest tests/unit/test_docs_consistency.py -q --runxfail -k "not architecture"` — 6 passed (Task 1)
- `pytest tests/unit/test_docs_consistency.py -q --runxfail` — 7 passed (Task 2, full file)
- `pytest -q` (full suite) — 1242 passed, 14 deselected, 7 xpassed, 0 failed
- `grep -c "^| CAP-" docs/mcp-conformance-matrix.md` — 22
- `grep -c "server/discover" docs/mcp-conformance-matrix.md` — 1 (in "Why this revision" prose only)
- `grep -c "TBD" docs/mcp-conformance-matrix.md` — 0
- `git diff -U0 docs/ARCHITECTURE.md | grep -c "^-[^-]"` — 0 (insertions only)
- `cmp` of `sed -n '1,1120p'` on HEAD vs. working tree for `docs/ARCHITECTURE.md` — identical
- `git status --porcelain src/` — empty
- The module-scope `pytestmark = pytest.mark.xfail(...)` in `tests/unit/test_docs_consistency.py`
  was left in place, untouched — confirmed by `grep -n "pytestmark"` still resolving to line 15

## Self-Check

- `docs/mcp-conformance-matrix.md` — FOUND
- `docs/ARCHITECTURE.md` — FOUND, modified
- Commit `f91234a` — FOUND (`docs(10-04): write the 22-row MCP client conformance matrix`)
- Commit `3709fa5` — FOUND (`docs(10-04): land every out-ruled MCP capability in ARCHITECTURE.md sec 15`)

## Self-Check: PASSED
