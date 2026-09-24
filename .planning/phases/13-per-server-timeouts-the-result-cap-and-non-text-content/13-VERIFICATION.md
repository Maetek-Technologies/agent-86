---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
verified: 2026-09-24T00:00:00Z
status: passed
score: 3/3 must-haves verified
---

# Phase 13: Per-server timeouts, the result cap, and non-text content — Verification Report

**Phase Goal:** A slow-but-legitimate server and a hung one are distinguishable by config, an
oversized tool result truncates visibly instead of consuming the budget silently, and an
image/audio/resource content block renders as something other than a Python repr.

**Verified:** 2026-09-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `MCPServerConfig` has per-server `connect_timeout_s` (default 30.0), `call_timeout_s` (default 120.0), rejecting `<=0` | VERIFIED | `src/agent86/config.py:395-398` (`Field(default=DEFAULT_MCP_CONNECT_TIMEOUT_S, gt=0)`, same for call); `tests/unit/test_config.py:364-410` cover defaults, per-server override and rejection |
| 2 | No hardcoded 30/120 literal remains at `start_server`/`call_tool`/capability-call sites; each reads the per-server value | VERIFIED | `mcp_client.py:855` (`budget = timeout if timeout is not None else cfg.connect_timeout_s`), `:796-802` (`_call_timeout_for`/`_max_result_chars_for` read `_server_cfg`), used at `call_tool` (`:1235`), `_on_session`-based capability calls (`:1212`) |
| 3 | A call/connect that overruns its budget fails naming the server and the field, and the in-flight/orphaned attempt is cancelled | VERIFIED | `mcp_client.py:868-874` (connect: `_abort_launch` cancels the future+task, message names `connect_timeout_s`), `:1216-1225` (call: `fut.cancel()`, message names `call_timeout_s`) |
| 4 | A call during reconnect gets "is reconnecting", never a timeout | VERIFIED | `mcp_client.py:1218-1219` checks `_server_state != "connected"` before raising `MCPTimeout`, raises `_unavailable_error` instead; `tests/unit/test_mcp.py:1680` `test_timeout_during_reconnect_backoff_names_reconnecting`; real-stdio proof `tests/integration/test_mcp_client.py:501` |
| 5 | `_content_to_text` truncates a joined result at `MCPServerConfig.max_result_chars` (default 8,000) with a visible marker — never drops silently, never raises | VERIFIED | `mcp_content.py:80-94` `truncate_result` (clamps negative limit to 0, never raises, marker names dropped-count/server/field); wired at `mcp_client.py:1541`; `tests/unit/test_mcp_content.py:122-135` exact-cut assertions; `tests/unit/test_mcp.py:1704` `test_call_tool_result_truncates_at_max_result_chars` |
| 6 | `read_resource`/`get_prompt` text capped by the same per-server limit and marker | VERIFIED | `mcp_client.py:1296` and `:1351` both call `truncate_result(text, limit, server)` with `limit = self._max_result_chars_for(server)` |
| 7 | ImageContent/AudioContent/EmbeddedResource/ResourceLink render as named markers, never `str(chunk)`'s repr; no base64 reaches the prompt verbatim | VERIFIED | `mcp_content.py:33-77` `render_content_block` — isinstance dispatch per type, base64 length reported not payload, unknown/exception path returns `[non-text content block: <TypeName> — not inlined]`; `tests/unit/test_mcp_content.py:29-100` assert exact marker text and absence of raw base64/`repr()` substrings |

**Score:** 7/7 derived truths verified (mapping onto the 3 ROADMAP success criteria / 3 requirement IDs)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/agent86/config.py` | `MCPServerConfig.connect_timeout_s`/`call_timeout_s`/`max_result_chars` + public defaults | VERIFIED | Lines 358-402; `DEFAULT_MCP_CONNECT_TIMEOUT_S=30.0`, `DEFAULT_MCP_CALL_TIMEOUT_S=120.0`, `DEFAULT_MCP_MAX_RESULT_CHARS=8_000`, each field `gt=0` |
| `src/agent86/tools/mcp_client.py` | `MCPTimeout`, `_server_cfg`/`_call_timeout_for`/`_max_result_chars_for`, per-server timeouts wired at all named sites | VERIFIED | `class MCPTimeout(TimeoutError)` at line 99; helper methods at 792-802; wired at `start_server` (836-876), `_await_result`/`call_tool` (1210-1243), `_on_session` capability path (1245-1263), `read_resource`/`get_prompt` (1289-1357) |
| `src/agent86/tools/mcp_content.py` | `render_content_block`, `truncate_result` | VERIFIED | New module, 94 lines, both functions exported, no top-level `mcp` import (lazy inside `render_content_block`, line 47) |
| `tests/unit/test_mcp.py` | timeout wiring + cap tests | VERIFIED | `test_call_timeout_uses_per_server_config` (1534), `test_timeout_during_reconnect_backoff_names_reconnecting` (1680), `test_call_tool_result_truncates_at_max_result_chars` (1704) |
| `tests/unit/test_mcp_content.py` | pure-function tests against real `mcp.types` | VERIFIED | `test_render_content_block_image` and 12 siblings present |
| `tests/integration/test_mcp_client.py` | real-stdio Phase 13 tests | VERIFIED | `test_real_stdio_call_timeout_is_per_server` (470), `test_real_stdio_call_during_reconnect_backoff_names_reconnecting` (501) |
| `tests/integration/live_mcp_server.py` | opt-in extra tools behind `AGENT86_LIVE_MCP_EXTRA_TOOLS` | VERIFIED | grep confirms env-gated extra tools; default tool set unchanged per fixture docstring |
| `.planning/.../13-EVIDENCE.md` | live pinned-corpus audit, 8,000 ruling, MCP-25 before/after evidence | VERIFIED | `## Ruling on the 8,000-character default` (line 119), `**Verdict:** complete` (154), `## After the fix (plans 13-02..13-05)` (156) with per-tool before/after pairs |
| `CHANGELOG.md` | Unreleased entries closing MCP-21/22/25 | VERIFIED | "Closes MCP-21." (18), "Closes MCP-22." (29), "Closes MCP-25." (81); reconnect-attempt/backoff no longer promised configurable (line 46 notes it stays fixed) |
| `docs/mcp-conformance-matrix.md` | `CAP-CONTENT-BLOCKS` re-ruled `implemented`/`in` | VERIFIED | Row at line 39 rates `implemented`/`in`, cites `13-EVIDENCE.md` |
| `docs/ARCHITECTURE.md` | §15 no longer lists `CAP-CONTENT-BLOCKS` under "Not built" | VERIFIED | Narrative note at line ~1191 documents the row leaving the table; grep of the "Not built" table shows no `CAP-CONTENT-BLOCKS` row remaining |
| `README.md` | documents the three keys, defaults, over-cap behavior, override example | VERIFIED | Lines 357-366: worked `[mcp.servers.NAME]` example with all three keys and their defaults |
| `13-VALIDATION.md` | signed off | VERIFIED | `status: complete`, `nyquist_compliant: true`, checklist item `[x]` at line 87 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `mcp_client.py::call_tool` | `MCPServerConfig.call_timeout_s` | `self._call_timeout_for(server)` | WIRED | `_await_result` reads `self._call_timeout_for(server)` (line 1212), called from `call_tool` |
| `mcp_client.py::start_server` | `MCPServerConfig.connect_timeout_s` | `timeout if timeout is not None else cfg.connect_timeout_s` | WIRED | Line 855, exact pattern present |
| `mcp_client.py::call_tool` | `_content_to_text` | `limit=self._max_result_chars_for(server)` | WIRED | Line 1235-1239 |
| `mcp_client.py::_content_to_text` | `mcp_content.py` | `render_content_block` per chunk, `truncate_result` on joined body | WIRED | Line 1539 (`render_content_block(chunk)`), 1541 (`truncate_result(body, limit, server)`) |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense (no React/Vue components) — this phase's "rendering" is
the text handed back through `call_tool`/`read_resource`/`get_prompt` to the ReAct loop. The trace
was instead performed end-to-end via the integration tests, which exercise real stdio + a real
`mcp` SDK session and assert the actual truncation marker and content-block marker text arrive at
the caller (`tests/integration/test_mcp_client.py`), and via `13-EVIDENCE.md`'s live after-fix
run against `server-everything`, confirming non-mocked data flows through the full stack.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| MCP-21 | 13-02, 13-05, 13-06 | Per-server configurable connect/call timeouts | SATISFIED | `config.py` fields, `mcp_client.py` wiring, unit + real-stdio tests, CHANGELOG "Closes MCP-21" |
| MCP-22 | 13-01, 13-02, 13-03, 13-04, 13-05, 13-06 | Prompt-side result cap | SATISFIED | `max_result_chars` field, `truncate_result`, wired at `call_tool`/`read_resource`/`get_prompt`, corpus audit + ruling in `13-EVIDENCE.md`, CHANGELOG "Closes MCP-22" |
| MCP-25 | 13-01, 13-03, 13-04, 13-05, 13-06 | Non-text content blocks handled | SATISFIED | `render_content_block`, before/after live evidence, conformance matrix re-ruling, CHANGELOG "Closes MCP-25" |

No orphaned requirements: REQUIREMENTS.md lines 144-146 map exactly MCP-21/22/25 to Phase 13, all
three appear in plan frontmatter `requirements:` fields (13-01 through 13-06).

### Anti-Patterns Found

None. Scanned `src/agent86/config.py`, `src/agent86/tools/mcp_client.py`,
`src/agent86/tools/mcp_content.py` for TODO/FIXME/placeholder/empty-return patterns — no matches
outside an intentional forward-reference to tracked issue MCP-24 (unrelated, pre-existing
`subscribe_resource` docstring). `render_content_block`/`truncate_result` both wrap their logic in
try/except per CLAUDE.md's "tool execution must never raise" rule, confirmed by
`test_render_content_block_never_raises` and `test_truncate_result_never_raises_on_bad_limit`.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit + content-block + config test suite | `pytest -q tests/unit/test_mcp.py tests/unit/test_mcp_content.py tests/unit/test_config.py` | 145 passed | PASS |
| No top-level `mcp` import added (lazy-import constraint) | `grep -n "^from mcp\|^import mcp" mcp_content.py config.py` | no matches (import is inside the function body at line 47) | PASS |
| CLAUDE.md constraint: `config.py` stays read-only | inspected `config.py` for TOML write calls | none found — config.py only defines/loads, `config_writer.py` untouched by this phase | PASS |
| `run --json` additive-only | inspected `call_tool` return type | still returns `str`; no new `ToolResult.metadata` key added (explicit ruling in 13-04-PLAN.md, confirmed in code) | PASS |

Orchestrator-reported full-suite results (not re-run in full here to avoid duplicate cost):
`pytest -q` → 1367 passed, 14 deselected; `ruff check .` clean; `mypy src/agent86` clean (94
files). Spot-check above re-confirms the Phase-13-relevant subset independently.

### Human Verification Required

None. All success criteria are backend/library behavior fully exercised by unit tests (fake
transport) and integration tests (real stdio, real `mcp` SDK types), with live evidence against a
real third-party server (`server-everything`) recorded in `13-EVIDENCE.md`. No UI, visual, or
subjective-quality surface is in scope for this phase.

### Gaps Summary

None. All three ROADMAP success criteria are implemented, tested at both the fake-transport and
real-stdio levels, and documented (README, CHANGELOG, ARCHITECTURE §15, conformance matrix). The
one documented process note — commit `a624a0e` (labelled 13-02) also containing 13-03's
`mcp_content.py` due to a shared-index race — does not affect content correctness; both files'
content matches their respective plans' must-haves exactly.

---

*Verified: 2026-09-24*
*Verifier: Claude (gsd-verifier)*
