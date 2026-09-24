---
phase: 13
slug: per-server-timeouts-the-result-cap-and-non-text-content
status: complete
nyquist_compliant: true
wave_0_complete: true
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

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-02-01 | 13-02 | 1 | MCP-21 | unit | `pytest tests/unit/test_config.py -k "mcp_server" -x` (defaults 30/120, per-server override) — 7 passed | ✅ | ✅ green |
| 13-02-03 | 13-02 | 1 | MCP-21 | unit | `pytest tests/unit/test_mcp.py -k "timeout" -x` (`start_server`/`call_tool`/`_on_session` read per-server config) — 8 passed | ✅ | ✅ green |
| 13-05-02 | 13-05 | 3 | MCP-21 | integration | `pytest tests/integration/test_mcp_client.py -k reconnect -x` (call during backoff still gets the "reconnecting" message) — 2 passed | ✅ | ✅ green |
| 13-02-01 | 13-02 | 1 | MCP-22 | unit | `pytest tests/unit/test_config.py -k "max_result_chars" -x` (default 8000) — 1 passed | ✅ | ✅ green |
| 13-04-02 | 13-04 | 2 | MCP-22 | unit | `pytest tests/unit/test_mcp.py -k "truncat or result_cap or max_result_chars" -x` (visible marker, never raises) — 6 passed | ✅ | ✅ green |
| 13-01-01 | 13-01 | 1 | MCP-22 | evidence | live pinned-corpus run → `13-EVIDENCE.md` (largest legitimate result sizes vs 8,000; 6 of 20 calls over cap) — plus `13-06-01` after-evidence re-running the same corpus over the fixed client | ✅ | ✅ green |
| 13-04-02 | 13-04 | 2 | MCP-25 | unit | `pytest tests/unit/test_mcp.py -k "content_block or image or audio or embedded" -x` (named marker, never `str(chunk)`, no base64) — 7 passed | ✅ | ✅ green |
| 13-06-02 | 13-06 | 4 | MCP-25 | doc-consistency | `pytest tests/unit/test_docs_consistency.py -q` (`CAP-CONTENT-BLOCKS` → implemented; §15 row removed) — 7 passed | ✅ | ✅ green |
| 13-03-02 | 13-03 | 1 | MCP-22, MCP-25 | unit | `pytest tests/unit/test_mcp_content.py -q` (pure `render_content_block`/`truncate_result` helpers) — 13 passed | ✅ | ✅ green |
| 13-05-02 | 13-05 | 3 | MCP-21, MCP-22, MCP-25 | integration | `pytest tests/integration/test_mcp_client.py -q -k "timeout or truncat or max_result_chars or image or audio or embedded"` (real stdio, real SDK content-block types) — 5 passed | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/unit/test_config.py` — `MCPServerConfig.connect_timeout_s`/`call_timeout_s`/`max_result_chars` defaults and overrides (MCP-21, MCP-22) — `13-02-01`
- [x] `tests/unit/test_mcp.py` — timeout wiring at `start_server`/`call_tool`/`_on_session` (MCP-21) — `13-02-02`
- [x] `tests/unit/test_mcp.py` — `_content_to_text` truncation at `max_result_chars` with a visible marker (MCP-22) — `13-03-01`/`13-04-01`
- [x] `tests/unit/test_mcp.py` — `ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink` rendering from real `mcp.types.*` instances (MCP-25) — `13-03-01`/`13-04-01`
- [x] `13-EVIDENCE.md` — live pinned-corpus result-size audit before the 8,000 default ships (MCP-22 precondition) — `13-01-01`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pinned-corpus result sizes vs the 8,000-char default | MCP-22 | Needs live `npx`/`uvx` servers and network; deselected in CI like `test_mcp_live` | Run the corpus audit script against `server-filesystem`, `mcp-server-git`, `server-everything`; record largest outputs verbatim in `13-EVIDENCE.md` |

The corpus audit was run live by plan 13-01 (`13-EVIDENCE.md`'s "Verdict: complete" — 20 real
calls across the three pinned servers, 6 of 20 over the 8,000-char default) and re-checked after
the fix landed by plan 13-06's Task 1 (`13-EVIDENCE.md`'s "After-fix verdict: complete" — the same
`server-everything` non-text-block calls and one `server-filesystem` over-cap call, re-run through
the FIXED `MCPManager`, confirming markers render and the cap/override both behave as documented).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant` set to `true` in frontmatter

**Approval:** approved 2026-09-24
