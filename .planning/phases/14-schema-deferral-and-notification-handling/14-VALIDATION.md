---
phase: 14
slug: schema-deferral-and-notification-handling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-24
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (existing) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing, unchanged) |
| **Quick run command** | `pytest tests/unit/test_mcp.py tests/unit/test_loop.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_mcp.py tests/unit/test_loop.py -q`
- **After every plan wave:** Run `pytest tests/unit/ tests/integration/test_mcp_client.py tests/integration/test_scripting_contract.py -q`
- **Before `/gsd:verify-work`:** `pytest -q` full suite green, plus `mypy src/agent86` and `ruff check .` clean
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

Filled in by the planner/executor against the task IDs in the PLAN.md files. Requirement → test map from research:

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MCP-20 | unit | `pytest tests/unit/test_mcp.py -k materializ -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-20 (SC2) | unit | `pytest tests/unit/test_loop.py -k defer -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-20 (Pitfall 1) | unit | per-provider stub-schema round trip (file located during planning) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-24 | unit | `pytest tests/unit/test_mcp.py -k list_changed -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-24 | integration | `pytest tests/integration/test_mcp_client.py -k list_changed -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-24 (CAP-PROGRESS) | unit | `pytest tests/unit/test_mcp.py -k progress_notification -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | docs consistency | unit | `pytest tests/unit/test_docs_consistency.py -q` | ✅ | ⬜ pending |
| TBD | TBD | TBD | `run --json` additive-only | integration | `pytest tests/integration/test_scripting_contract.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_mcp.py` — materialisation tests (`spec()` before/after first `run()`) and `list_changed`/`progress` notification-delivery tests; extend `_install_fake_transport`'s fake session with an injectable-notification helper (precedent: plan 12-01's `_DyingTransport.deliver()`)
- [ ] `tests/unit/test_loop.py` — budget-grows-after-materialisation regression test
- [ ] `tests/integration/live_mcp_server.py` — opt-in (env-gated, per the `AGENT86_LIVE_MCP_EXTRA_TOOLS` precedent) dynamic-tool + `notify_tools_changed()` probe
- [ ] `tests/integration/test_mcp_client.py` — real-stdio `list_changed` round-trip test
- [ ] Locate the existing per-provider tool-shape test file(s) and add the deferred-stub-schema round-trip test there

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `/config mcp` live mount reflects a server whose tool list changed mid-session | MCP-24 (SC3) | TUI observation against a live server | Run `agent86` with the CI fixture in dynamic-tools mode, trigger the change, open `/config mcp` and confirm the new tool is listed without restart |
| Whether any pinned corpus server sets `InitializeResult.instructions` | MCP-20 (SC1) | Live third-party servers | Print `session.initialize()` result against `server-everything`/`server-filesystem`; record in `14-EVIDENCE.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
