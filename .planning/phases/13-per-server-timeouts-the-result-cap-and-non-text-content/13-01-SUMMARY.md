---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
plan: 01
subsystem: mcp
tags: [mcp, evidence, adr-0004, result-cap, non-text-content, corpus-audit]

# Dependency graph
requires:
  - phase: 10-mcp-conformance-audit
    provides: "ADR 0004 (result-cap ruling) and the pinned corpus table this plan re-verifies live"
  - phase: 11-resources-and-prompts-become-first-class
    provides: "11-EVIDENCE.md's live-evidence format precedent this plan mirrors"
provides:
  - "13-EVIDENCE.md: live pinned-corpus result-size audit (20 calls across 3 servers) closing the roadmap's stated MCP-22 precondition"
  - "Written ruling: the 8,000-char default in ADR 0004 ships as-is, despite 6/20 corpus calls exceeding it"
  - "Named list of every over-cap tool plus whether it offers a narrowing argument, for plan 13-06's README worked example"
  - "MCP-25 'before' evidence: verbatim str(chunk) reprs for real ResourceLink/EmbeddedResource/ImageContent blocks, including the base64 PNG that reaches the prompt today"
affects: [13-06-signoff, 13-02, 13-03]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Live corpus evidence via raw mcp SDK (ClientSession + stdio_client), never the project's own MCPManager, so a parallel-executing code change can't invalidate the measurement"]

key-files:
  created:
    - .planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md
  modified: []

key-decisions:
  - "The 8,000-char default ships as-is per ADR 0004, even though 6 of 20 corpus calls exceed it (30%) — the visible per-server-overridable marker is what makes the small default acceptable, not the absence of over-cap results"
  - "mcp-server-git's git_show is the one over-cap tool in the corpus with zero narrowing argument (schema is {repo_path, revision} only) — listed under Accepted risk, recommended as plan 13-06's worked 'raise max_result_chars' example"

patterns-established: []

requirements-completed: [MCP-22, MCP-25]

# Metrics
duration: ~25min
completed: 2026-09-24
---

# Phase 13 Plan 01: Live pinned-corpus result-size audit and 8,000-char ruling Summary

**Live-ran the pinned MCP corpus (server-filesystem, mcp-server-git, server-everything) through the raw SDK, found 6 of 20 real tool results exceed the ADR 0004 8,000-char default, and ruled in writing that the default ships anyway per the ADR's own visible-marker mitigation.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-09-24T18:17:00Z
- **Tasks:** 1
- **Files modified:** 1 created (`13-EVIDENCE.md`)

## Accomplishments
- Closed the roadmap's stated MCP-22 precondition ("the first plan audits the pinned corpus before
  shipping the default") with real character counts, not an inference from MCP-07's narrower
  sampling/elicitation run.
- Ran all three pinned corpus servers live: `server-filesystem@2026.8.31`,
  `mcp-server-git==2026.8.18` (installed into a throwaway scratchpad venv, `uvx` unavailable on
  this machine), `server-everything@2026.8.31` — 20 tool calls total, reproducing today's
  `_content_to_text` join rule exactly without importing `agent86.tools.mcp_client` (kept the
  measurement immune to plan 13-02's concurrent edits to that same file).
- Recorded a written ruling: the 8,000-char default ships unchanged, with the over-cap tool list
  and narrowing-argument answers plan 13-06 needs for its README worked example.
- Captured MCP-25 "before" evidence: real `str(chunk)` reprs for `ResourceLink`,
  `EmbeddedResource`, and `ImageContent` blocks from `server-everything`, including the literal
  base64 PNG payload (`get-tiny-image`) that reaches the model-facing prompt verbatim today.

## Task Commits

1. **Task 1: Run the pinned corpus live and write 13-EVIDENCE.md with the 8,000 ruling** -
   `514795d` (docs)

_No plan-metadata commit — this plan's execution context prohibits touching STATE.md/ROADMAP.md
(orchestrator updates those after the wave); this SUMMARY.md itself is the only remaining file to
land, in a follow-up commit._

## Files Created/Modified
- `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md` -
  Live corpus result-size table (20 rows), over-cap detail table (6 rows) with narrowing-argument
  answers, MCP-25 before-evidence (4 non-text-block calls, verbatim reprs), and the written 8,000
  ruling with an Accepted risk sub-section.

## Decisions Made
- **The 8,000-char default ships as-is.** 6/20 recorded calls (30%) exceeded it:
  `server-filesystem`'s `read_text_file` on `mcp_client.py` (71,167 chars) and `README.md`
  (47,415 chars), `directory_tree` on `src/agent86` (20,149 chars); `mcp-server-git`'s `git_log`
  at `max_count: 50` (32,286 chars), `git_show HEAD` (9,094 chars), and `git_diff HEAD~5`
  (179,217 chars). Per this plan's pre-committed ruling (derived from ADR 0004), the default still
  ships: the truncation is visible, per-server-overridable, and never silent — the numbers confirm
  ADR 0004's own stated tradeoff is real, not that the ruling was wrong.
- **`git_show` is the one true "accepted risk" tool.** Its schema (`{repo_path, revision}`) offers
  no head/tail, no context-line limit, and no path-scoping argument at all — every other over-cap
  tool (`read_text_file`: `head`/`tail`; `directory_tree`: `excludePatterns`; `git_log`:
  `max_count`; `git_diff`: `context_lines`, partial) has at least a partial narrowing knob.
  Recommended to plan 13-06 as the worked "raise `max_result_chars` for this server" example.

## Deviations from Plan

None — plan executed exactly as written. Two script-level bugs were found and fixed during
execution (both self-contained to the throwaway scratchpad script, never touching the repo):
`mcp.types.Tool` uses `input_schema`, not `inputSchema` (an initial naive guess based on the wire
JSON-RPC field name), and `server-everything`'s `get-structured-content` tool requires an
enum-valued `location` argument (`New York`/`Chicago`/`Los Angeles`), not a free string — both
corrected before the final recorded run, with the corrected run's numbers being the only ones
written into `13-EVIDENCE.md`.

## Issues Encountered
- **Live numbers drift between runs in this parallel wave.** Because this repo's working tree is
  shared with two concurrently-committing executors (plans 13-02, 13-03), `mcp-server-git`'s
  `git_show`/`git_diff` results reflect whatever commit was `HEAD` at call time — re-running the
  script minutes apart produced `git_diff {target: HEAD~5}` character counts ranging 176,915 to
  179,217 across three runs. This does not change the evidence's conclusion (every run stayed
  enormously over the cap); `13-EVIDENCE.md` records this explicitly in its own
  "Parallel-execution note" and uses the final run's numbers as the reference figures.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`13-EVIDENCE.md` is ready for plan 13-06 (phase signoff) to cite: it names every over-cap corpus
tool with its narrowing-argument answer for the README worked example, and the written ruling
closes the roadmap's stated MCP-22 precondition so 13-06 does not need to stop and ask the user
before its docs claim the 8,000 default was audited. No blockers for plans 13-02/13-03/13-04/13-05,
which implement the schema/timeout/truncation/content-block code this evidence justifies but do
not depend on this plan's artifact directly (this plan's only committed file,
`docs/adr/0004-mcp-result-cap-location.md`, was pre-existing and untouched).

---
*Phase: 13-per-server-timeouts-the-result-cap-and-non-text-content*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-EVIDENCE.md`
- FOUND: `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-01-SUMMARY.md`
- FOUND: commit `514795d` (`git log --oneline --all | grep 514795d`)
