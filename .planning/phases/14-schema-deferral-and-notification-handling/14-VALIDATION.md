---
phase: 14
slug: schema-deferral-and-notification-handling
status: complete
nyquist_compliant: true
wave_0_complete: true
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
| 14-01-01 | 01 | 1 | MCP-20 (SC1 instructions evidence), MCP-24 (SDK facts) | live evidence | `python -c` heading check on `14-EVIDENCE.md` (see 14-01 Task 1 verify) — `ok` | ✅ | ✅ green |
| 14-01-02 | 01 | 1 | MCP-24 (fixture probes) | integration | `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` — 36 passed | ✅ | ✅ green |
| 14-01-03 | 01 | 1 | MCP-20/MCP-24 (unit fake) | unit | `pytest tests/unit/test_mcp.py -q` — 135 passed | ✅ | ✅ green |
| 14-02-01 | 02 | 1 | MCP-20 (SC1 names + instructions renderer) | unit | `pytest tests/unit/test_mcp_prompt_section.py -q -k mcp_section` — 17 passed | ✅ | ✅ green |
| 14-02-02 | 02 | 1 | MCP-20 (SC1 per-request section, sub-agents) | unit | `pytest tests/unit/test_mcp_prompt_section.py tests/unit/test_loop.py -q` — 64 passed | ✅ | ✅ green |
| 14-03-01 | 03 | 2 | MCP-20 (deferral + Pitfall 1 provider shapes) | unit | `pytest tests/unit/test_mcp_schema_deferral.py -q -k "materializ or mcp_stub_schema"` — 11 passed, 2 deselected | ✅ | ✅ green |
| 14-03-02 | 03 | 2 | MCP-20 (SC2 same-turn budget, instructions capture) | unit | `pytest tests/unit/test_mcp_schema_deferral.py tests/unit/test_mcp.py -q -k "budget or instructions or prompt_catalog"` — 9 passed, 139 deselected | ✅ | ✅ green |
| 14-04-01 | 04 | 3 | MCP-24 (list_changed re-fetch, race guard) | unit | `pytest tests/unit/test_mcp.py -q -k list_changed` — 10 passed, 125 deselected | ✅ | ✅ green |
| 14-04-02 | 04 | 3 | MCP-24 (CAP-PROGRESS, logging, resource updates) | unit | `pytest tests/unit/test_mcp.py -q -k "progress_notification or logging_notification or resource_updated"` — 12 passed, 123 deselected | ✅ | ✅ green |
| 14-05-01 | 05 | 4 | MCP-24 (SC3 real stdio) | integration | `pytest tests/integration/test_mcp_client.py -q -k "list_changed or progress or logging"` — 4 passed, 28 deselected | ✅ | ✅ green |
| 14-05-02 | 05 | 4 | MCP-20 (SC1/SC2 real stdio) | integration | `pytest tests/integration/test_mcp_client.py -q -k "instructions or schema_deferral"` — 3 passed, 29 deselected | ✅ | ✅ green |
| 14-06-01 | 06 | 5 | docs consistency (no new ADR, no CAP-SCHEMA-DEFERRAL row) | unit | `pytest tests/unit/test_docs_consistency.py -q` — 7 passed | ✅ | ✅ green |
| 14-06-02 | 06 | 5 | phase gate + `run --json` additive-only | full | `pytest -q` — 1435 passed, 14 deselected; `mypy src/agent86` — no issues (94 files); `ruff check .` — all checks passed; `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py tests/integration/test_scripting_contract.py -q` — 55 passed | ✅ | ✅ green |
| 14-06-03 | 06 | 5 | MCP-24 (SC3 TUI) | manual checkpoint | human-verify (see Manual-Only Verifications) | n/a | ⬜ pending human checkpoint |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/unit/test_mcp.py` — `_DyingTransport.notify`/`notify_nowait`/`call_kwargs`/`list_delay`/`list_error` and `_Up.instructions` (14-01-03); materialisation-adjacent and notification tests land in 14-03/14-04
- [x] `tests/unit/test_mcp_schema_deferral.py` — new file: materialisation, per-provider stub-schema shapes (Pitfall 1 — no per-provider round-trip file existed; the adapters' static `_to_tools` converters are tested directly), same-turn budget (14-03)
- [x] `tests/unit/test_mcp_prompt_section.py` — new file: names + instructions section (14-02)
- [x] `tests/integration/live_mcp_server.py` — opt-in `AGENT86_LIVE_MCP_NOTIFY_TOOLS` (`grow_tools`/`shrink_tools` via `ctx.request_context.session.send_tool_list_changed()` — NOT `ctx.notify_tools_changed()`, which only reaches 2026-07-28 listen subscribers — plus `progress_steps`, `log_line`) and `AGENT86_LIVE_MCP_INSTRUCTIONS` (14-01-02)
- [x] `tests/integration/test_mcp_client.py` — real-stdio list_changed/progress/logging/instructions/deferral tests (14-05)

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `/config mcp` live mount reflects a server whose tool list changed mid-session | MCP-24 (SC3) | TUI observation against a live server | 14-06-03: run `agent86` with the CI fixture under `AGENT86_LIVE_MCP_NOTIFY_TOOLS=1`, have the model call `grow_tools`, confirm the `mcp:` note and that `/tools` (or `/config mcp`) lists `mcp__live__dynamic_echo` without restart |
| Whether any pinned corpus server sets `InitializeResult.instructions` | MCP-20 (SC1) | Live third-party servers (npx) | Done by 14-01-01 with a scratchpad raw-SDK script against `server-everything`, `server-filesystem`, `mcp-server-git` and the CI fixture; recorded in `14-EVIDENCE.md` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant` set to `true` in frontmatter

**Approval:** pending human checkpoint (14-06-03)
