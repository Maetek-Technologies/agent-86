---
phase: 13
slug: per-server-timeouts-the-result-cap-and-non-text-content
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-24
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/unit/test_mcp.py tests/unit/test_config.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10 seconds (quick), several minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_mcp.py tests/unit/test_config.py -q`
- **After every plan wave:** Run `pytest tests/unit/ tests/integration/test_mcp_client.py -q`, then `mypy src/agent86` and `ruff check .`
- **Before `/gsd:verify-work`:** Full suite must be green (`pytest -q`), plus `pytest tests/unit/test_docs_consistency.py -q` for the matrix/§15 cross-reference
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

Task IDs are filled in once plans exist; rows below are the requirement-level contract from
`13-RESEARCH.md` § Validation Architecture.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MCP-21 | unit | `pytest tests/unit/test_config.py -k "mcp_server" -x` (defaults 30/120, per-server override) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-21 | unit | `pytest tests/unit/test_mcp.py -k "timeout" -x` (`start_server`/`call_tool`/`_on_session` read per-server config) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-21 | integration | `pytest tests/integration/test_mcp_client.py -k reconnect -x` (call during backoff still gets the "reconnecting" message) | ✅ extend | ⬜ pending |
| TBD | TBD | TBD | MCP-22 | unit | `pytest tests/unit/test_config.py -k "max_result_chars" -x` (default 8000) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-22 | unit | `pytest tests/unit/test_mcp.py -k "truncat or result_cap or max_result_chars" -x` (visible marker, never raises) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-22 | evidence | live pinned-corpus run → `13-EVIDENCE.md` (largest legitimate result sizes vs 8,000) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-25 | unit | `pytest tests/unit/test_mcp.py -k "content_block or image or audio or embedded" -x` (named marker, never `str(chunk)`, no base64) | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MCP-25 | doc-consistency | `pytest tests/unit/test_docs_consistency.py -q` (`CAP-CONTENT-BLOCKS` → implemented; §15 row removed) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/unit/test_config.py` — `MCPServerConfig.connect_timeout_s`/`call_timeout_s`/`max_result_chars` defaults and overrides (MCP-21, MCP-22)
- [ ] `tests/unit/test_mcp.py` — timeout wiring at `start_server`/`call_tool`/`_on_session` (MCP-21)
- [ ] `tests/unit/test_mcp.py` — `_content_to_text` truncation at `max_result_chars` with a visible marker (MCP-22)
- [ ] `tests/unit/test_mcp.py` — `ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink` rendering from real `mcp.types.*` instances (MCP-25)
- [ ] `13-EVIDENCE.md` — live pinned-corpus result-size audit before the 8,000 default ships (MCP-22 precondition)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pinned-corpus result sizes vs the 8,000-char default | MCP-22 | Needs live `npx`/`uvx` servers and network; deselected in CI like `test_mcp_live` | Run the corpus audit script against `server-filesystem`, `mcp-server-git`, `server-everything`; record largest outputs verbatim in `13-EVIDENCE.md` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
