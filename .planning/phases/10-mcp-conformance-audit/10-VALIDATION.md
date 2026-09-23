---
phase: 10
slug: mcp-conformance-audit
status: ready
nyquist_compliant: true
wave_0_complete: false  # 10-01 is the Wave-0-equivalent plan (wave 1)
created: 2026-09-22
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Phase shape:** this phase produces documents plus ONE real test. Validation here means
> *checking documents make verifiable claims that actually hold*, not testing application
> behaviour. Derived from `10-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (existing project standard) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `pytest tests/integration/test_mcp_client.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~2 seconds quick / full suite ~1100 tests |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/integration/test_mcp_client.py -q`
- **After every plan wave:** Run `pytest -q` (this phase edits `docs/ARCHITECTURE.md`; check for
  existing tests asserting its content before assuming none exist)
- **Before `/gsd:verify-work`:** Full suite must be green, AND the docs-consistency check must
  pass (matrix "out" rulings ↔ `ARCHITECTURE.md` §15)
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

Plans exist; rows below carry their real plan and wave assignments.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 10-01 | 1 | MCP-06 | **integration test** | `pytest tests/integration/test_mcp_client.py -q -k scrubbed_env` | ❌ W0 | ⬜ pending |
| 10-01-02 | 10-01 | 1 | MCP-02, MCP-03, MCP-04, MCP-08…11 | doc check (xfail scaffold) | `pytest tests/unit/test_docs_consistency.py -q` → 7 xfailed | ❌ W0 | ⬜ pending |
| 10-02-01 | 10-02 | 1 | MCP-05, MCP-07 | doc check + live run | `grep -c "api.githubcopilot.com/mcp/" docs/mcp-conformance-audit-2026-09.md` | ❌ W0 | ⬜ pending |
| 10-02-02 | 10-02 | 1 | MCP-12 | doc check | nine head-start rows ruled, each with a file:line citation | ❌ W0 | ⬜ pending |
| 10-03-01 | 10-03 | 2 | MCP-08, MCP-09 | doc check | `pytest tests/unit/test_docs_consistency.py --runxfail -q -k adr` | ❌ W0 | ⬜ pending |
| 10-03-02 | 10-03 | 2 | MCP-10, MCP-11 | doc check | `pytest tests/unit/test_docs_consistency.py --runxfail -q -k adr` | ❌ W0 | ⬜ pending |
| 10-04-01 | 10-04 | 3 | MCP-02, MCP-03 | doc check | `pytest tests/unit/test_docs_consistency.py --runxfail -q` (22 rows, 6 columns, `2025-11-25` pin) | ❌ W0 | ⬜ pending |
| 10-04-02 | 10-04 | 3 | MCP-04 | grep assertion | `pytest tests/unit/test_docs_consistency.py --runxfail -q` (every `out` ruling present in ARCHITECTURE.md §15) | ❌ W0 | ⬜ pending |
| 10-05-01 | 10-05 | 4 | MCP-13 | doc check | `grep -c "#### Proposed Phase" docs/mcp-conformance-audit-2026-09.md` | ❌ W0 | ⬜ pending |
| 10-05-02 | 10-05 | 4 | MCP-02, MCP-03, MCP-04 | **gate** | `pytest tests/unit/test_docs_consistency.py -q` → 7 passed, 0 xfail markers remain | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All five are owned by planned tasks; `10-01` (wave 1) is the Wave-0-equivalent plan.

- [ ] `docs/mcp-conformance-matrix.md` — owned by `10-04`; — does not exist; create from the Client-Side MCP Spec
      Surface table in `10-RESEARCH.md` as the row skeleton
- [ ] `docs/adr/` — owned by `10-03`; does not exist; create, with the four ADR files (MCP-08..MCP-11)
- [ ] `tests/unit/test_docs_consistency.py` — owned by `10-01` Task 2 (xfail scaffold) and un-xfailed by `10-05` Task 2; does not exist; the cross-document check backing
      MCP-02, MCP-03, MCP-04 and MCP-08..MCP-11 (reads both docs, asserts cross-references resolve)
- [ ] New SEC-04 end-to-end test in `tests/integration/test_mcp_client.py` — owned by `10-01` Task 1; reuse the existing
      `_stdio_cfg`, `MCPManager` and `_HAS_MCP_SERVER` scaffolding in that file; do not duplicate it
- [ ] An environment-echoing tool (`get_env`) added to `tests/integration/live_mcp_server.py` — owned by `10-01` Task 1

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Five corpus servers named with exact versions | MCP-05 | Versions are static facts in prose, not runtime-checkable; GitHub's hosted server has no installable version and is pinned by endpoint + observation date (locked decision D-02) | Read the audit report's corpus table; confirm five rows, each with a version or an endpoint + observation date |
| `server-everything` drives sampling, elicitation, progress | MCP-07 | Evidence-gathering, not a CI-pinned assertion; a committed test would add a network/npx dependency (locked decision D-03) | Read the audit report's MCP-07 section; confirm it records the exact `npx -y @modelcontextprotocol/server-everything@<version>` command that was run live, the tool list agent86 actually received with its count, and the present/absent breakdown of all sixteen tool names |
| Nine head-start rows confirmed or corrected | MCP-12 | Judgement over evidence, not a mechanical check | Read the audit report's table; each of the nine rows carries a confirmed/corrected ruling with a file:line citation |
| Workstream A/B/C phase breakdown | MCP-13 | Quality of a recommendation is not machine-checkable | Confirm each proposed phase has a goal, requirements and success criteria sufficient for `/gsd:add-phase` without further research |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 10 tasks carry one
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — no task uses the `MISSING` sentinel
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-09-22 (plans verified by gsd-plan-checker: 0 blockers)
