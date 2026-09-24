---
phase: 12
slug: fix-the-zombie-tool-desync-and-add-reconnect
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-24
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/test_mcp.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10 seconds (quick), several minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_mcp.py -q`
- **After every plan wave:** Run `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` then `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green, plus the real kill-mid-session integration test passing
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-xx | TBD | TBD | MCP-26 (SC1) | unit | `pytest tests/unit/test_mcp.py -k death -x` | ❌ W0 | ⬜ pending |
| 12-xx | TBD | TBD | MCP-26 (SC1) | integration (real stdio kill) | `pytest tests/integration/test_mcp_client.py -k mid_session -x` | ❌ W0 | ⬜ pending |
| 12-xx | TBD | TBD | MCP-26 (SC2) | unit + integration | `pytest tests/unit/test_mcp.py -k named_server -x` | ❌ W0 | ⬜ pending |
| 12-xx | TBD | TBD | MCP-23 (SC3) | unit | `pytest tests/unit/test_mcp.py -k reconnect -x` | ❌ W0 | ⬜ pending |
| 12-xx | TBD | TBD | MCP-23 (SC3) | unit + integration | `pytest tests/unit/test_mcp.py -k reconnect_repopulates -x` | ❌ W0 | ⬜ pending |
| 12-xx | TBD | TBD | MCP-23 (no false retry on stop/close) | integration (existing) | `pytest tests/integration/test_mcp_client.py -k "teardown or partial_stop" -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs are filled in by the planner.*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_mcp.py` — fake-transport helper that can fire the injected `message_handler`'s `Exception` branch after `ready` resolves
- [ ] `tests/integration/test_mcp_client.py` — real-stdio test that kills `live_mcp_server.py` mid-session and asserts death detection / retry / named-server error
- [ ] SSE/HTTP kill-mid-session case in `tests/integration/test_mcp_live.py`, or an explicitly recorded accepted risk

*No framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-world server death in an interactive session | MCP-26, MCP-23 | End-to-end UX in TUI | Start `agent86` with a stdio MCP server, kill its process, confirm the tools disappear from the offered set / reconnect note appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
