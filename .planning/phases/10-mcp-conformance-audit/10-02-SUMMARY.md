---
phase: 10-mcp-conformance-audit
plan: 02
subsystem: docs
tags: [mcp, conformance-audit, model-context-protocol, adr-prep]

# Dependency graph
requires:
  - phase: 10-mcp-conformance-audit (plan 10-01)
    provides: SEC-04 end-to-end pin (`get_env` tool on `live_mcp_server.py`) used as corpus member 4
provides:
  - "docs/mcp-conformance-audit-2026-09.md — Scope and method, the five-server pinned corpus, the MCP-07 live-run evidence, and all nine BACKLOG head-start rows ruled against current code"
  - "First-party record of what agent86 actually received from a live server-everything run, not a citation of the server's README"
  - "The _serve/_server_tools zombie-tool desync ruled CONFIRMED with a dedicated explanation, no fix made"
affects: [10-03-adrs, 10-04-matrix, 10-05-workstream-breakdown]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Audit report as narrative half separate from the matrix (plan 10-04) and ADRs (plan 10-03)"]

key-files:
  created:
    - docs/mcp-conformance-audit-2026-09.md
  modified: []

key-decisions:
  - "All three corpus version pins (server-everything@2026.8.31, server-filesystem@2026.8.31, mcp-server-git==2026.8.18) matched 10-RESEARCH.md's MEDIUM-confidence figures exactly on re-verification today (npm view / pip index versions) — no drift to reconcile"
  - "npx.cmd was required (not bare npx) to spawn the live server from a Python subprocess in this Volta-managed Windows environment; worked on the first attempt, no retry needed"
  - "All nine BACKLOG head-start rows re-verified against current code (a30a2bb) and came back CONFIRMED — none CORRECTED; every cited line still resolves to the claim it supports"

requirements-completed: [MCP-05, MCP-07, MCP-12]

# Metrics
duration: 20min
completed: 2026-09-22
---

# Phase 10 Plan 02: MCP Conformance Audit — Corpus, Live Run, and Head-Start Rulings Summary

**Live-ran `server-everything@2026.8.31` against a scratch `MCPManager` (13 tools, 11/16 expected names present), pinned all five corpus servers by verified version/SHA/endpoint, and ruled all nine BACKLOG head-start defects CONFIRMED with re-checked file:line citations — including a dedicated explanation of the `_serve`/`_server_tools` zombie-tool desync.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-09-22
- **Tasks:** 2/2 completed
- **Files modified:** 1 (`docs/mcp-conformance-audit-2026-09.md`, created)

## Accomplishments

- Re-verified all four installable-corpus version pins live against their registries today
  (`npm view`, `python -m pip index versions`, `git rev-parse --short HEAD`) rather than trusting
  10-RESEARCH.md's MEDIUM-confidence figures — all matched exactly:
  `server-everything@2026.8.31`, `server-filesystem@2026.8.31`, `mcp-server-git==2026.8.18`,
  `live_mcp_server.py` at `a30a2bb`.
- Ran `@modelcontextprotocol/server-everything@2026.8.31` live via `npx.cmd -y ...` against a
  throwaway scratchpad script driving `agent86.tools.mcp_client.MCPManager.start_server`. agent86
  received **13 tools**. Of the 16 tool names this audit set out to check, 11 were present and 5
  were absent — every absent one was a sampling/elicitation/roots trigger
  (`trigger-sampling-request`, `trigger-sampling-request-async`, `trigger-elicitation-request`,
  `trigger-url-elicitation`, `get-roots-list`). Two tools appeared that were not on the 16-name
  list at all (`gzip-file-as-resource`, `simulate-research-query`) — evidence the package has
  evolved its demo tool set since 10-RESEARCH.md's docs-based read.
- Answered MCP-07 per capability, citing the exact mechanism: sampling and elicitation are not
  observable through agent86 today because the server never advertises those tools to a client
  that declares no matching `ClientCapabilities` (`mcp_client.py:219`, `session.py:591-608`);
  progress genuinely is driven by the server (`trigger-long-running-operation` was present and
  callable) but agent86 cannot see it because `_serve` installs no `message_handler`, so the SDK's
  default handler for `notifications/progress` is a true no-op (`session.py:212-213`).
- Pinned the fifth corpus member — GitHub's hosted remote MCP server — by endpoint
  (`https://api.githubcopilot.com/mcp/`) plus observation date `2026-09-22`, per D-02, with prose
  explaining why a version pin is impossible for a hosted product; no fixture file created for it.
- Re-verified all nine BACKLOG § 999.0a head-start claims directly against
  `src/agent86/tools/mcp_client.py` at the current commit — every cited line (`mcp_client.py:219`,
  `:220-221`, `:166`, `:295`, `config.py:293-294`, `:426-434`, `:429-430`, `:234`, `:241-242`,
  `:244-260`, `:262-266`, `:286-289`, `:237`, `:336-358`, `session.py:212-213`, `:591-608`,
  `mcp_types/_types.py:1474`) still resolved to the claim it was cited for. All nine came back
  **CONFIRMED**, none **CORRECTED**.
- Wrote a dedicated "Row 7 in detail" subsection on the `_serve`/`_server_tools` desync: the
  zombie-tool defect fires only when a server's task dies *after* `ready` already resolved (not at
  connect time), leaving `self._server_tools` populated (registry still lists the tools as
  callable) while `self._sessions` is already emptied by the `finally` block, so every call
  through one of those tools raises `RuntimeError("MCP session not available")` instead of the
  tool disappearing. Ruled CONFIRMED, no fix made (MCP-12), routed to deferred requirement MCP-26.
- Closed with a workstream-routing count over the nine rows (A: 2, B: 1, C: 6), independent
  evidence supporting the prior observation that workstream C is the largest of the three.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin the five-server corpus and record the server-everything live run (MCP-05,
   MCP-07)** — `3668c44` (docs)
2. **Task 2: Rule each of the nine head-start rows against current code (MCP-12)** — `185e3e6`
   (docs)

_No separate plan-metadata commit — this SUMMARY.md and STATE.md/ROADMAP.md updates land in the
final commit per the parallel-execution constraint (own paths only)._

## Files Created/Modified

- `docs/mcp-conformance-audit-2026-09.md` — the audit's narrative report: Scope and method (D-01
  protocol-revision pin), the pinned five-server corpus table, the MCP-07 live-run evidence
  section, and the nine head-start rows ruled with a dedicated zombie-tool explanation. Ends with
  two placeholders (`_(filled by plan 10-05)_` for the workstream breakdown — the matrix at
  `docs/mcp-conformance-matrix.md` and the four ADRs under `docs/adr/` are separate files owned by
  plans 10-04 and 10-03 respectively, not sections of this report).

## Decisions Made

- Used `npx.cmd` directly for the live run (not bare `npx`) since this environment's Volta-managed
  `npx` is a shim a Python subprocess cannot spawn without a shell — worked first try, so the
  plan's documented `npx`/`npx.cmd` fallback path was exercised only in its successful branch.
- Recorded the two tool names present in the live run but absent from the original 16-name list
  (`gzip-file-as-resource`, `simulate-research-query`) as evidence of upstream package drift since
  10-RESEARCH.md was written, rather than treating them as an error in the audit's method.
- Kept the workstream-distribution closing line to a count only ("C: 6 of 9"), explicitly declining
  to state a final sizing conclusion, per the plan's own instruction that synthesis belongs to
  plan 10-05.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria were verified by the
exact automated checks the plan specified (grep counts, the `awk`-scoped row count, the git-status
emptiness checks) before each commit.

## Issues Encountered

The pinned-corpus table's separator row (`|---|---|...|`) initially didn't start with `| ` and so
was undercounted by the plan's own `awk`+`grep -c "^| "` acceptance check (6 instead of the
required 7). Fixed by writing the separator as `| --- | --- | ... |` instead — a formatting-only
correction, made before the Task 1 commit, not a deviation from the plan's content requirements.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The audit report now has three of its five sections real (Scope and method, The pinned corpus,
  MCP-07, and The nine head-start rows); two placeholders remain for plan 10-05's workstream
  breakdown.
- Plan 10-03 (the four ADRs) can cite this report's MCP-07 answer directly — ADRs MCP-08 and
  MCP-09 were explicitly gated on that answer per the plan's locked decisions.
- Plan 10-04 (the conformance matrix) can reuse this report's corpus table and the nine confirmed
  rulings as source evidence without re-deriving them.
- No blockers. `src/` and `tests/` are untouched by this plan (`git diff --stat src/` empty,
  `src/agent86/tools/mcp_client.py` byte-identical to HEAD at both task commits).

---
*Phase: 10-mcp-conformance-audit*
*Completed: 2026-09-22*

## Self-Check: PASSED

- FOUND: `docs/mcp-conformance-audit-2026-09.md`
- FOUND: `.planning/phases/10-mcp-conformance-audit/10-02-SUMMARY.md`
- FOUND: `3668c44` (Task 1 commit)
- FOUND: `185e3e6` (Task 2 commit)
