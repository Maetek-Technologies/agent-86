---
phase: 10-mcp-conformance-audit
plan: 03
subsystem: docs
tags: [mcp, adr, architecture-decision-records, sampling, elicitation, context-budget, prompt-contract]

# Dependency graph
requires:
  - phase: 10-mcp-conformance-audit (plan 10-02)
    provides: "The live server-everything run and docs/mcp-conformance-audit-2026-09.md's MCP-07 evidence"
provides:
  - "docs/adr/ — the project's first ADR directory, with a lightweight-MADR convention (README.md)"
  - "ADR 0001 — sampling ruled opt-in-per-server, deferred until a realistic corpus server demands it"
  - "ADR 0002 — elicitation ruled opt-in-per-server with four non-negotiable preconditions (gateway-owned rendering, hard refusal list, headless behaviour, refusal-as-normal-answer)"
  - "ADR 0003 — schema deferral ruled permissible for schemas, not for tool names, reconciled with context_budget and allowed-tools"
  - "ADR 0004 — the MCP result cap ruled into a per-server MCPServerConfig.max_result_chars field (default 8,000 chars), truncate-with-marker, structured_content out of scope"
affects: [10-04-conformance-matrix, 10-05-workstream-breakdown]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Lightweight MADR ADRs (Context/Decision/Consequences, **Ruling:** line), docs/adr/NNNN-kebab-title.md"]

key-files:
  created:
    - docs/adr/README.md
    - docs/adr/0001-mcp-sampling-inversion-of-control.md
    - docs/adr/0002-mcp-elicitation-tier-1-surface.md
    - docs/adr/0003-mcp-schema-deferral-prompt-contract.md
    - docs/adr/0004-mcp-result-cap-location.md
  modified: []

key-decisions:
  - "CAP-SAMPLING ruled out: opt-in per server, deferred until a realistic corpus server (not the conformance instrument) demands it"
  - "CAP-ELICITATION ruled out: same opt-in-per-server deferral, plus four non-negotiable preconditions before it can ever ship"
  - "Schema deferral: deferring JSON Schema payloads is permissible; deferring tool names is not, to preserve the allowed-tools refusal-is-free boundary"
  - "MCP result cap: lives as MCPServerConfig.max_result_chars (default 8,000 chars), per-server, truncate-with-visible-marker, never drop, never raise; structured_content explicitly out of scope"
  - "CAP-STRUCTURED-OUTPUT and CAP-CONTENT-BLOCKS both ruled out per ADR 0004 — silently dropped / str(chunk) repr respectively, neither fixed by a byte cap"

patterns-established:
  - "ADR convention: docs/adr/NNNN-kebab-title.md, ## Status/## Context/## Decision/## Consequences, Decision opens with **Ruling:**, enforced by tests/unit/test_docs_consistency.py"

requirements-completed: [MCP-08, MCP-09, MCP-10, MCP-11]

# Metrics
duration: 20min
completed: 2026-09-22
---

# Phase 10 Plan 03: MCP Contract ADRs Summary

**Four ADRs rule sampling and elicitation opt-in-per-server (deferred, not built), schema deferral permissible only for schemas (never tool names), and the MCP result cap into a per-server `max_result_chars` field (default 8,000 chars) — no source file touched.**

## Performance

- **Duration:** ~20 min (from prior plan's commit to this plan's final commit)
- **Started:** 2026-09-22T23:35:59-04:00 (approx, prior commit boundary)
- **Completed:** 2026-09-22T23:41:51-04:00
- **Tasks:** 2/2
- **Files modified:** 5 created (docs/adr/README.md + 4 ADRs)

## Accomplishments
- Created `docs/adr/` — the project's first ADR directory — with a lightweight-MADR convention
  written down in `README.md` (path/naming, required headings, the `**Ruling:**` line, and the
  index table of all four ADRs).
- ADR 0001 rules sampling as an inversion-of-control build-or-don't decision: opt-in per server,
  deferred until a realistic corpus server demands it, citing the MCP-07 live-run evidence
  (`trigger-sampling-request`/`trigger-sampling-request-async` both absent because agent86 never
  advertises the capability) and the four cost/egress/approval/credential reasons it would be
  expensive if built.
- ADR 0002 rules elicitation the same way, framed as a Tier 1 (gateway) phishing-vector concern —
  who renders it, what it may never ask for (credentials, secrets, unvetted free text), what
  happens headless in `run --json`, and that a refusal must be a normal answer, not a retryable
  error.
- ADR 0003 reconciles schema deferral with the real `context_budget` derivation
  (`ARCHITECTURE.md:615-619`, the `tool schemas` named subtracted term) and the real
  `allowed-tools` boundary (`ARCHITECTURE.md:543-544`): deferring schemas is fine because the
  budget is already recomputed before every request; deferring tool *names* is ruled out because
  it would make every out-of-bounds refusal cost a step instead of being free.
- ADR 0004 names the home for the uncapped `_content_to_text` join
  (`mcp_client.py:426-434`): a per-server `MCPServerConfig.max_result_chars` field, default 8,000
  characters, truncate-with-visible-marker (never drop, never raise per CLAUDE.md's tool-must-
  never-raise rule), and explicitly scopes `structured_content` (silently dropped today) out of
  this particular ruling.

## Task Commits

Each task was committed atomically:

1. **Task 1: ADR convention + ADR 0001 (sampling) and ADR 0002 (elicitation)** - `ff49af0` (docs)
2. **Task 2: ADR 0003 (schema deferral) and ADR 0004 (result cap)** - `8aa61b2` (docs)

_No TDD tasks in this plan — document-only, no code changes._

## Files Created/Modified
- `docs/adr/README.md` - ADR convention (lightweight MADR), naming rule, and the four-ADR index table
- `docs/adr/0001-mcp-sampling-inversion-of-control.md` - Ruling: sampling opt-in per server, deferred
- `docs/adr/0002-mcp-elicitation-tier-1-surface.md` - Ruling: elicitation opt-in per server, four preconditions
- `docs/adr/0003-mcp-schema-deferral-prompt-contract.md` - Ruling: defer schemas, never tool names
- `docs/adr/0004-mcp-result-cap-location.md` - Ruling: per-server `max_result_chars` (8,000 chars default), truncate-with-marker

## Decisions Made

For plan 10-04 (the conformance matrix), this plan's rulings translate directly into four matrix
rows:

- **`CAP-SAMPLING`** → **out** (ADR 0001: opt-in per server, deferred until demand)
- **`CAP-ELICITATION`** → **out** (ADR 0002: opt-in per server, deferred, with four preconditions)
- **`CAP-STRUCTURED-OUTPUT`** → **out** (ADR 0004: `structured_content` silently dropped, explicitly out of this ADR's scope)
- **`CAP-CONTENT-BLOCKS`** → **out** (ADR 0004: non-text blocks fall through to `str(chunk)`, a byte cap doesn't fix the representation problem)

Schema deferral (ADR 0003) is deliberately **not** a matrix row — it's an agent86-side prompt-
compilation strategy, not a spec-level client capability, and the ADR says so explicitly so plan
10-04 doesn't go looking for a `CAP-SCHEMA-DEFERRAL` row that shouldn't exist.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' acceptance criteria (required file:line
citations, required strings, `**Ruling:**` lines, `git status --porcelain src/ tests/` empty)
were verified directly before each commit.

## Issues Encountered

None. `pytest tests/unit/test_docs_consistency.py -q --runxfail -k adr` passed after Task 2
(`1 passed`), the module-scope `pytestmark = pytest.mark.xfail(...)` was left untouched (10-05
owns its removal), and the full suite ran green afterward: 1242 passed, 14 deselected, 6 xfailed,
1 xpassed (the now-genuinely-passing ADR test, xpassed rather than failed because the marker is
`strict=False`), 0 failed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 10-04 (the conformance matrix) can now read `CAP-SAMPLING`, `CAP-ELICITATION`,
`CAP-STRUCTURED-OUTPUT`, and `CAP-CONTENT-BLOCKS` rulings directly out of ADRs 0001/0002/0004 (all
four "out," with the reasoning captured in each ADR's `## Consequences` section) rather than
re-deriving them. Plan 10-05 (workstream breakdown) can cite ADR 0003's second-order requirements
(recompute the budget around materialising schemas, additive-only `run --json` keys) and ADR
0004's named field/default/behaviour when sizing MCP-20 and MCP-22. No blockers.

---
*Phase: 10-mcp-conformance-audit*
*Completed: 2026-09-22*

## Self-Check: PASSED

All 5 created docs files found on disk; both task commits (`ff49af0`, `8aa61b2`) found in git log.
