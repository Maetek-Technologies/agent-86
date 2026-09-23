---
phase: 10
slug: mcp-conformance-audit
status: draft
nyquist_compliant: false
wave_0_complete: false
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

Task IDs are assigned by the planner; rows are keyed on requirement until then.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MCP-02 | doc check | `pytest tests/unit/test_docs_consistency.py -q` (row set matches research capability enumeration) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-03 | doc check | same test — asserts every matrix row has a non-empty corpus-exercised column | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-04 | grep assertion | same test — every "out"-ruled capability name appears in `docs/ARCHITECTURE.md` §15 | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-05 | doc check | manual review — five servers named with exact versions | N/A | ⬜ pending |
| TBD | TBD | TBD | MCP-06 | **integration test** | `pytest tests/integration/test_mcp_client.py -q -k scrubbed_env` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-07 | doc check + live run | manual review of audit evidence; optional `npx -y @modelcontextprotocol/server-everything@2026.8.31` run (not committed) | N/A | ⬜ pending |
| TBD | TBD | TBD | MCP-08 | doc check | same test — ADR file exists with a Decision heading (sampling as inversion of control) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-09 | doc check | same test — ADR exists (elicitation as a Tier 1 surface) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-10 | doc check | same test — ADR exists (schema deferral vs. the prompt contract) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-11 | doc check | same test — ADR exists (where the result cap lives) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-12 | doc check | manual review — nine head-start rows each ruled confirmed/corrected with file:line evidence | N/A | ⬜ pending |
| TBD | TBD | TBD | MCP-13 | doc check | manual review — workstream A/B/C phase breakdown present and `/gsd:add-phase`-ready | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `docs/mcp-conformance-matrix.md` — does not exist; create from the Client-Side MCP Spec
      Surface table in `10-RESEARCH.md` as the row skeleton
- [ ] `docs/adr/` — does not exist; create, with the four ADR files (MCP-08..MCP-11)
- [ ] `tests/unit/test_docs_consistency.py` — does not exist; the cross-document check backing
      MCP-02, MCP-03, MCP-04 and MCP-08..MCP-11 (reads both docs, asserts cross-references resolve)
- [ ] New SEC-04 end-to-end test in `tests/integration/test_mcp_client.py` — reuse the existing
      `_stdio_cfg`, `MCPManager` and `_HAS_MCP_SERVER` scaffolding in that file; do not duplicate it
- [ ] An environment-echoing tool added to `tests/integration/live_mcp_server.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Five corpus servers named with exact versions | MCP-05 | Versions are static facts in prose, not runtime-checkable; GitHub's hosted server has no installable version | Read the audit report's corpus table; confirm five rows, each with a version or an endpoint + observation date |
| `server-everything` drives sampling, elicitation, progress | MCP-07 | Evidence-gathering, not a CI-pinned assertion; a committed test would add a network/npx dependency | Read the audit report's evidence section; confirm it cites `server-everything`'s tool names (`trigger-sampling-request`, `trigger-elicitation-request`, `trigger-long-running-operation`) |
| Nine head-start rows confirmed or corrected | MCP-12 | Judgement over evidence, not a mechanical check | Read the audit report's table; each of the nine rows carries a confirmed/corrected ruling with a file:line citation |
| Workstream A/B/C phase breakdown | MCP-13 | Quality of a recommendation is not machine-checkable | Confirm each proposed phase has a goal, requirements and success criteria sufficient for `/gsd:add-phase` without further research |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
