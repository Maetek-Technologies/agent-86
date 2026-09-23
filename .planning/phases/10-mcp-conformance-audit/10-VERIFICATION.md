---
phase: 10-mcp-conformance-audit
verified: 2026-09-23T00:00:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 10: MCP Conformance Audit Verification Report

**Phase Goal:** Rule on the client half of the MCP spec from evidence: a conformance matrix over
every client-side spec capability, a version-pinned server corpus to exercise it, and the ADRs for
the four decisions that would otherwise touch the prompt contract, the cost cap, and the security
model if implemented without a ruling. Produces documents plus one test — no implementation.

**Verified:** 2026-09-23
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Conformance matrix: one row per client-side capability, rated, corpus-checked, ruled in/out with reasoning; every "out" lands in ARCHITECTURE.md §15 | ✓ VERIFIED | `docs/mcp-conformance-matrix.md` has exactly 22 `CAP-*` rows (independently counted), 4 `in` / 18 `out`. Independently re-parsed both files: all 18 out-ruled IDs appear verbatim in `docs/ARCHITECTURE.md` §15's "Not built" table, one row each, no batching. `tests/unit/test_docs_consistency.py` (7 tests, unmarked) passes for real. |
| 2 | Audit report names all 5 corpus servers with exact version pins, and states with evidence whether `server-everything` drives sampling/elicitation/progress | ✓ VERIFIED | `docs/mcp-conformance-audit-2026-09.md` "The pinned corpus" table names `server-everything@2026.8.31`, `server-filesystem@2026.8.31`, `mcp-server-git==2026.8.18`, `live_mcp_server.py@a30a2bb`, and GitHub's hosted server by endpoint+date (D-02, no version possible, with prose justification). "MCP-07" section gives the real command run, the 13-tool live-run result, a present/absent table for all 16 target tool names, the `session.py:591-608` capability-gating citation, and one sentence each for sampling (not observable — declared absent), elicitation (same), and progress (server drives it, agent86 can trigger but not observe — no `message_handler`). |
| 3 | CI test drives `live_mcp_server.py` to echo its own environment and fails if a stdio server ever receives the unscrubbed host environment; no network dependency | ✓ VERIFIED | `tests/integration/live_mcp_server.py` has a real `get_env` tool (`return dict(os.environ)`) that runs *inside the subprocess*. `test_stdio_server_gets_scrubbed_env` calls it through a real stdio `MCPManager` session and asserts on `raw` (the tool's return value echoed back through the protocol) — a genuine end-to-end assertion on what the subprocess received, not on what the client sent. Ran independently: `pytest tests/integration/test_mcp_client.py -q -k scrubbed_env` → `1 passed`, not skipped (the `mcp` extra is installed). No `requests`/`httpx`/`npx` string in the test file; no network calls. |
| 4 | Four ADR documents exist, each stating a ruling and rationale, not an open question | ✓ VERIFIED | `docs/adr/0001..0004-*.md` all exist with `## Status`/`## Context`/`## Decision`/`## Consequences` and a `**Ruling:**` line each (grep-confirmed, one per file). 0001: sampling opt-in-per-server, deferred. 0002: elicitation opt-in-per-server, deferred, 4 preconditions. 0003: schemas deferrable, tool names not. 0004: per-server `MCPServerConfig.max_result_chars` (8,000 default), truncate-with-marker. `docs/adr/README.md` documents the convention and indexes all four. |
| 5 | Audit report confirms/corrects the nine head-start rows (incl. the `_serve`/`_server_tools` desync) and ends with a workstream A/B/C phase breakdown handoff-ready for `/gsd:add-phase` | ✓ VERIFIED | Nine-row table in `docs/mcp-conformance-audit-2026-09.md`, all ruled `CONFIRMED` (none `CORRECTED`), each with resolving file:line citations spot-checked against `src/agent86/tools/mcp_client.py` directly. Row 7 has a dedicated 2-paragraph "in detail" subsection on the zombie-tool defect, explicitly stating no fix was made. Independently confirmed `mcp_client.py:241-242`'s `finally` block still pops only `self._sessions[name]`, not `self._server_tools` — the desync is recorded, not fixed. 7 proposed phases (11–17) cover all 13 deferred requirements MCP-14..MCP-26 exactly once (`grep` confirms each appears; "Deferred requirements not proposed" section explicitly states "None"). The `2026-07-28` modern-protocol question is named as its own candidate finding, not dropped. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docs/mcp-conformance-matrix.md` | 22-row matrix pinned to 2025-11-25 | ✓ VERIFIED | 112 lines, `Protocol revision: 2025-11-25` present, 22 `CAP-` rows confirmed by independent parse |
| `docs/mcp-conformance-audit-2026-09.md` | Corpus, live run, 9 rulings, workstream breakdown | ✓ VERIFIED | 455 lines, all 5 required `##` sections present, 7 proposed-phase blocks |
| `docs/adr/README.md` + 0001–0004 | ADR convention + 4 rulings | ✓ VERIFIED | All 5 files exist, correct headings, `**Ruling:**` present in each ADR |
| `docs/ARCHITECTURE.md` §15 | 18 new "Not built" rows | ✓ VERIFIED | Exactly 18 new rows, one per out-ruled `CAP-*`, sections 1–14 byte-identical to pre-phase HEAD, insertions only (0 deletions in diff) |
| `tests/integration/live_mcp_server.py` | new `get_env` tool | ✓ VERIFIED | `def get_env` present, echoes `dict(os.environ)` from inside the subprocess |
| `tests/integration/test_mcp_client.py` | `test_stdio_server_gets_scrubbed_env` | ✓ VERIFIED | Present, passes for real (`1 passed`), genuinely end-to-end |
| `tests/unit/test_docs_consistency.py` | 7 tests, xfail marker removed | ✓ VERIFIED | `grep -c xfail` returns 0; `pytest -q` on this file → `7 passed` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `test_mcp_client.py` | `MCPManager.start_server` | `_stdio_cfg()` reused | WIRED | New test reuses existing factory, no duplicate `MCPServerConfig(command=sys.executable` literal |
| `test_docs_consistency.py` | `docs/mcp-conformance-matrix.md` | Path read + table parse | WIRED | `_matrix_rows()` reads and parses the real file; independently re-implemented the same parse and got matching results |
| `mcp-conformance-matrix.md` | `docs/ARCHITECTURE.md` §15 | out-ruled `CAP-` ids | WIRED | All 18 confirmed present via independent script, not just via the test |
| `mcp-conformance-matrix.md` | `docs/adr/0001…` | `CAP-SAMPLING`/`CAP-ELICITATION` ruling copied from ADR | WIRED | Matrix rows cite the ADR filenames directly and the rulings match |
| Audit report workstream breakdown | `mcp-conformance-matrix.md` | derived sizing | WIRED | Sizing line and per-phase "Matrix rows closed" reference real `CAP-*` ids |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| MCP-02 | 10-04, 10-05 | ✓ SATISFIED | Matrix has 1 row/capability |
| MCP-03 | 10-04 | ✓ SATISFIED | Corpus-exercise column present per row |
| MCP-04 | 10-04, 10-05 | ✓ SATISFIED | Every out-ruling lands in §15, test-proven |
| MCP-05 | 10-02 | ✓ SATISFIED | 5-server corpus pinned with versions/SHA/endpoint |
| MCP-06 | 10-01 | ✓ SATISFIED | SEC-04 end-to-end stdio test, passes for real |
| MCP-07 | 10-02 | ✓ SATISFIED | Live run recorded, sampling/elicitation/progress answered |
| MCP-08 | 10-03 | ✓ SATISFIED | ADR 0001 rules sampling |
| MCP-09 | 10-03 | ✓ SATISFIED | ADR 0002 rules elicitation |
| MCP-10 | 10-03 | ✓ SATISFIED | ADR 0003 rules schema deferral |
| MCP-11 | 10-03 | ✓ SATISFIED | ADR 0004 rules result cap location |
| MCP-12 | 10-02 | ✓ SATISFIED | 9 head-start rows ruled, all CONFIRMED, desync recorded not fixed |
| MCP-13 | 10-05 | ✓ SATISFIED | 7-phase workstream breakdown, 13/13 deferred requirements placed |

All 12 requirement IDs (MCP-02 through MCP-13) declared in ROADMAP.md and .planning/REQUIREMENTS.md
are accounted for in plan frontmatter across the 5 plans. No orphaned requirements found —
REQUIREMENTS.md's Phase-10 mapping table lists exactly MCP-02..MCP-13, all "Complete", matching the
plans' declared coverage. (Note: the GSD init tool's phase-detail summary undercounts to
MCP-02..MCP-11; ROADMAP.md and REQUIREMENTS.md — both authoritative — list and cover all twelve.)

### Anti-Patterns Found

None (blocker or warning level) in any phase-produced document. No `TODO`/`FIXME`/`PLACEHOLDER`/
`TBD`/"not yet implemented" strings found in `docs/mcp-conformance-matrix.md`,
`docs/mcp-conformance-audit-2026-09.md`, or any of the four ADRs.

**ℹ️ Info:** `.planning/phases/10-mcp-conformance-audit/deferred-items.md` (the phase's own logged
deviation) states the pre-existing `ruff format --check .` 74-file failure is "all under
`tests/tui/` and `tests/unit/`". Independently re-verified this is inaccurate — 32 of the 74 files
are under `src/agent86/` (e.g. `mcp_client.py`, `cli.py`, `loop.py`). However, independently
diffing `ruff format --check .` against commit `3384e6a` (immediately pre-Phase-10) confirms all of
`src/`'s flagged files, including `mcp_client.py`, were *already* failing the format check before
Phase 10 started (71 files pre-phase vs. 74 post-phase; the 3 new failures are all test files, none
under `src/`). This confirms the deviation's substantive claim — the drift predates Phase 10 and is
not caused by it — while its "all under tests/" categorization is simply wrong. Per this task's
explicit instruction, this is not reported as a phase gap; noted here only because the note's
wording should be corrected in a future housekeeping pass.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SEC-04 end-to-end test passes for real (not skipped) | `pytest tests/integration/test_mcp_client.py -q -k scrubbed_env` | `1 passed` | ✓ PASS |
| Docs-consistency gate passes unmarked | `pytest tests/unit/test_docs_consistency.py -q` | `7 passed` | ✓ PASS |
| Full suite green | `pytest -q` | `1249 passed, 14 deselected` | ✓ PASS |
| Lint clean | `ruff check .` | `All checks passed!` | ✓ PASS |
| Type-check clean | `mypy src/agent86` | `Success: no issues found in 93 source files` | ✓ PASS |
| `src/` untouched across the whole phase | `git diff --stat 3384e6a..HEAD -- src/` | empty | ✓ PASS |
| Desync recorded, not fixed | `sed -n '241,242p' src/agent86/tools/mcp_client.py` | `finally: self._sessions.pop(name, None)` (only) | ✓ PASS |
| Every out-ruled `CAP-*` independently found in §15 | custom Python re-parse of both documents | 18/18 present | ✓ PASS |
| ARCHITECTURE.md §§1-14 unchanged | `cmp` of first 1120 lines, pre- vs. post-phase | identical | ✓ PASS |

### Human Verification Required

None. All five ROADMAP success criteria and all specific scrutiny items (a–e) named in the task
were independently verifiable by direct file inspection, re-parsing, and running the real test
suite — no visual, real-time, or subjective judgment call remains open.

### Gaps Summary

No gaps found. All five ROADMAP success criteria verified against the actual codebase (not
SUMMARY claims), all 12 requirement IDs satisfied, the one behavioral claim in the phase
(SEC-04 end-to-end) genuinely tests subprocess-received environment rather than call-site
assertions, the consistency gate is proven to fail when violated (documented break-and-restore
in 10-05-SUMMARY.md, and independently re-confirmed the test's assertions are real, not vacuous),
scope discipline held (`src/` byte-identical across the whole phase), and the `_serve`/
`_server_tools` desync was recorded with correct line citations and left unfixed as required.
The one known, accepted deviation (`ruff format --check .` pre-existing drift) is carried debt,
not a phase gap, per the task's explicit instruction — though its logged description undersells
which directories it touches.

---

*Verified: 2026-09-23*
*Verifier: Claude (gsd-verifier)*
