---
phase: 12
slug: fix-the-zombie-tool-desync-and-add-reconnect
status: complete
nyquist_compliant: true
wave_0_complete: true
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
| 12-01-02 | 12-01 | 1 | MCP-26 (SC1) | unit | `pytest tests/unit/test_mcp.py -k death -x` | ✅ | ✅ (7 passed) |
| 12-05-02 (+12-06-01) | 12-05 | 2 | MCP-26 (SC1) | integration (real stdio kill) | `pytest tests/integration/test_mcp_client.py -k mid_session -x` | ✅ | ✅ (2 passed — 12-05's no-retry kill test and 12-06's reconnect-after-kill test both match `-k mid_session`) |
| 12-01-03 | 12-01 | 1 | MCP-26 (SC2) | unit + integration | `pytest tests/unit/test_mcp.py -k named_server -x` | ✅ | ✅ (4 passed) |
| 12-03-02 | 12-03 | 2 | MCP-23 (SC3) | unit | `pytest tests/unit/test_mcp.py -k reconnect -x` | ✅ | ✅ (11 passed) |
| 12-03-02 | 12-03 | 2 | MCP-23 (SC3) | unit + integration | `pytest tests/unit/test_mcp.py -k reconnect_repopulates -x` | ✅ | ✅ (1 passed) |
| 12-03-02 | 12-03 | 2 | MCP-23 (no false retry on stop/close) | integration (existing) | `pytest tests/integration/test_mcp_client.py -k "teardown or partial_stop" -x` | ✅ | ✅ (2 passed) |
| 12-02-02 | 12-02 | 1 | registry thread-safety (identity-checked removal, cross-thread mutation) | unit | `pytest tests/unit/test_registry.py -q -k "unregister_tool or concurrent"` | ✅ | ✅ (4 passed) |
| 12-04-02 | 12-04 | 2 | harness registry sync (MCP-26 unregister / MCP-23 re-add on reconnect) | unit | `pytest tests/unit/test_loop.py -q -k mcp_tools_changed` | ✅ | ✅ (6 passed) |
| 12-06-02 | 12-06 | 3 | MCP-26 (SC1) HTTP/SSE death detection, research OQ4 | integration (real SSE/streamable-HTTP kill) | `pytest tests/integration/test_mcp_live.py -q -k mid_session` | ✅ | ✅ (2 passed — no accepted risk needed; SSE detected passively, HTTP detected on next call) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Full suite `pytest -q`: 1300 passed, 14 deselected, 0 failed. `mypy src/agent86`: clean. `ruff check .`: clean. `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q`: 20 passed.

---

## Wave 0 Requirements

- [x] `tests/unit/test_mcp.py` — fake-transport helper that can fire the injected `message_handler`'s `Exception` branch after `ready` resolves (12-01-01)
- [x] `tests/integration/test_mcp_client.py` — real-stdio test that kills `live_mcp_server.py` mid-session and asserts death detection / retry / named-server error (12-05-02)
- [x] SSE/HTTP kill-mid-session case in `tests/integration/test_mcp_live.py` (12-06-02) — no accepted risk was needed; both transports proved detectable on the first run against the installed `mcp==2.0.0` SDK

*No framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-world server death in an interactive session | MCP-26, MCP-23 | End-to-end UX in TUI | Start `agent86` with a stdio MCP server, kill its process, confirm the tools disappear from the offered set / reconnect note appears |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant` set to `true` in frontmatter

**Approval:** approved 2026-09-24
