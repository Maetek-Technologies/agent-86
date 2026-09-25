---
phase: 14-schema-deferral-and-notification-handling
verified: 2026-09-25T00:00:00Z
status: passed
score: 7/7 must-haves verified
---

# Phase 14: Schema Deferral and Notification Handling Verification Report

**Phase Goal:** The system prompt's fixed overhead shrinks by deferring MCP tool schemas to
first use (never tool names), and a server-initiated notification — `list_changed`, progress, or
otherwise — reaches something other than a no-op.

**Verified:** 2026-09-25
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Compiled system prompt lists every mounted server's tool names (plus instructions) up front; only the full JSON Schema is withheld until first call (ADR 0003) | ✓ VERIFIED | `render_mcp_section` (`src/agent86/cognitive/prompt.py:62`), wired via `Harness._mcp_prompt_section`/`_system_content` (`src/agent86/orchestration/loop.py:442,468`); `MCPTool.spec()` returns stub `{"type":"object","properties":{}}` with `" [argument schema loads on first call]"` suffix until `run()` flips `_materialized` (`src/agent86/tools/mcp_client.py:118-227`) |
| 2 | `_context_budget` accounts for a materialising schema's cost inside the step that triggers it, not only on the next request's recomputation | ✓ VERIFIED | `MCPTool.run()` flips `self._materialized = True` synchronously before returning (line 223); `_context_budget` signature/call sites unchanged (grep confirms 2 call sites); `test_budget_shrinks_in_the_step_that_materialises` passes |
| 3 | `_on_message` routes `notifications/tools/list_changed` (and resources/prompts siblings) into a re-fetch instead of dropping it, reflecting a changed server without restart | ✓ VERIFIED | `_on_notification` → `_refetch_tools` (`mcp_client.py:920,970`); session-identity guard against death/stop race, per-server `asyncio.Lock`; identity-preserving diff by `_definition` equality; real-stdio proof in `test_real_stdio_list_changed_mounts_and_unmounts_through_the_harness` and human-approved TUI checkpoint |
| 4 | Instructions never override tool names — names always advertised even for deferred tools | ✓ VERIFIED | `_MCPCapabilityTool`/argument-less tools never deferred (`_materialized = not props`); stub schema still carries `self.name` |
| 5 | Progress/logging/resource-updated notifications reach something other than a no-op | ✓ VERIFIED | `_request_progress` progress_callback mints a token (line 154); `_on_progress` → `last_progress()` + throttled live note; `LoggingMessageNotification` → `logger.log` on `agent86.tools.mcp_client`; `ResourceUpdatedNotification` → live note naming URI + `read_resource` tool |
| 6 | `run --json` keys stay additive-only; no new core dependency; lazy imports preserved | ✓ VERIFIED | `pyproject.toml` untouched by any Phase 14 commit; `import mcp.types as mcp_types` is a local import inside `_on_notification` (line 929), not module-level; `test_scripting_contract.py` passes |
| 7 | Requirements MCP-20 and MCP-24 closed and documented | ✓ VERIFIED | `.planning/REQUIREMENTS.md` shows both as `[x]` with traceability rows mapping to Phase 14; matrix/ARCHITECTURE/CHANGELOG/README all updated consistently |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/agent86/cognitive/prompt.py::render_mcp_section` | Pure renderer, names + instructions, 2000-char cap | ✓ VERIFIED | Present, `MCP_INSTRUCTIONS_MAX_CHARS = 2000`, truncation marker present, `__all__` extended |
| `src/agent86/orchestration/loop.py::_mcp_prompt_section`/`_system_content` | Per-request recomputation, duck-typed on `prompt_catalog`, never raises | ✓ VERIFIED | `try/except Exception` degrades to `""` + `logger.debug`; `_context_budget` signature unchanged |
| `src/agent86/agents/subagent.py::_system` | Sub-agent uses `h._system_content(None)` | ✓ VERIFIED | `grep` confirms `self.h._system_content(None)` present, old `system_prompt.content` reference removed |
| `src/agent86/tools/mcp_client.py::MCPTool` deferral | Stub schema until first call, synchronous materialisation, required-arg precheck | ✓ VERIFIED | `_DEFERRED_NOTE`, `_deferred_schema`, `_missing_required`, `_materialized`, `_definition` all present and match plan spec exactly |
| `src/agent86/tools/mcp_client.py::MCPManager.prompt_catalog/server_instructions` | Instructions capture per connection, exposed sorted by server | ✓ VERIFIED | `self._instructions[name]` set beside `_sessions[name]`; popped in `finally` and `stop_server` (2 pop sites, matches spec) |
| `src/agent86/tools/mcp_client.py::_on_notification/_refetch_tools/_on_progress` | Notification router, identity-preserving re-fetch, race guard, progress/logging/resource-updated | ✓ VERIFIED | All present; session-identity guard (`if self._sessions.get(name) is not session: return`); `_refetch_locks` per-server `asyncio.Lock`; `CancelledNotification` correctly absent (SDK consumes it) |
| `tests/unit/test_mcp.py`, `test_mcp_schema_deferral.py`, `test_mcp_prompt_section.py` | Full unit coverage | ✓ VERIFIED | 172 tests pass across the three files (7.24s) |
| `tests/integration/live_mcp_server.py` opt-in probes | `grow_tools`/`shrink_tools`/`progress_steps`/`log_line`, `AGENT86_LIVE_MCP_INSTRUCTIONS` | ✓ VERIFIED | Present per 14-01-SUMMARY; real-stdio tests pass |
| `docs/mcp-conformance-matrix.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `README.md` | Re-ruled to match evidence, no over-claim | ✓ VERIFIED | All five rows re-ruled exactly per plan; no `CAP-SCHEMA-DEFERRAL` row; SC1 instructions claim matches `14-EVIDENCE.md` verbatim |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `Harness._system_content` | `render_mcp_section` | `self._mcp_prompt_section()` | ✓ WIRED | Confirmed at `loop.py:470` |
| `Harness._mcp_prompt_section` | `MCPManager.prompt_catalog` | `getattr(self.mcp, "prompt_catalog", None)` | ✓ WIRED | Confirmed at `loop.py:450` |
| `MCPTool.run` | `MCPTool.spec` | `self._materialized = True` before return | ✓ WIRED | Confirmed at `mcp_client.py:223` |
| `MCPManager._serve_once._on_message` | `MCPManager._on_notification` | `await self._on_notification(name, this_session[0], message)` | ✓ WIRED | Confirmed at `mcp_client.py:1155` |
| `MCPManager._refetch_tools` | `_emit_tools_changed` → `Harness._on_mcp_tools_changed` | `self._emit_tools_changed(name, removed, added)` | ✓ WIRED | Confirmed present; race-guarded by session-identity check before write |
| `MCPManager.call_tool` | SDK progress-token minting | `progress_callback=_request_progress` | ✓ WIRED | Confirmed at `mcp_client.py:1514` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unit + docs-consistency suite | `pytest tests/unit/test_mcp.py tests/unit/test_mcp_schema_deferral.py tests/unit/test_mcp_prompt_section.py tests/unit/test_docs_consistency.py -q` | 172 passed | ✓ PASS |
| Real-stdio integration suite | `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py tests/integration/test_scripting_contract.py -q` | 55 passed | ✓ PASS |
| Full suite (already run by orchestrator) | `pytest -q` | 1435 passed, 14 deselected | ✓ PASS |
| Lint/type-check (already run by orchestrator) | `ruff check .`; `mypy src/agent86` | clean | ✓ PASS |
| Human TUI checkpoint (14-06-03) | Manual: grow_tools/shrink_tools/dynamic_echo/progress in a live TUI session | Approved 2026-09-25 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| MCP-20 | 14-01, 14-02, 14-03, 14-05, 14-06 | Schema deferral to first use | ✓ SATISFIED | `MCPTool` deferral + `render_mcp_section`/`_mcp_prompt_section` wiring; real-stdio proof; matrix/ARCHITECTURE/CHANGELOG updated; `.planning/REQUIREMENTS.md` `[x]` |
| MCP-24 | 14-01, 14-04, 14-05, 14-06 | `list_changed` handling and other notification routing | ✓ SATISFIED | `_on_notification`/`_refetch_tools`/`_on_progress` + real-stdio proof + human TUI checkpoint; `.planning/REQUIREMENTS.md` `[x]` |

No orphaned requirements: `.planning/REQUIREMENTS.md`'s Phase 14 mapping lists exactly MCP-20 and MCP-24, matching every plan's frontmatter `requirements:` field.

### Anti-Patterns Found

None. Grep for `TODO|FIXME|XXX|HACK|placeholder|not implemented` across `mcp_client.py`, `prompt.py`, `subagent.py` returned no matches (the one `MCPDeprecationWarning`/`deprecated` hit is an intentional citation of upstream SDK deprecation, not a stub marker). No hardcoded empty stub schemas outside the documented ADR 0003 deferral mechanism (which is the feature, not a defect — it is a *fresh* dict per call, verified by `test_materializ_stub_is_a_fresh_dict`).

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense (no dashboard/component); the equivalent trace here is
schema-materialisation-into-budget, which is explicitly proven by
`test_budget_shrinks_in_the_step_that_materialises` (unit) and
`test_real_stdio_schema_deferral_end_to_end` (real stdio + real `ReAct` turn) — both pass.

### Human Verification Required

None outstanding. The one item that needed a human (14-06-03: a mid-session tool-list change
appears in the TUI without restart) was already run and approved by the user on 2026-09-25, per
`14-VALIDATION.md` (`**Approval:** approved 2026-09-25`) and `14-06-SUMMARY.md` (user replied
verbatim "approved").

### Gaps Summary

No gaps found. Every must-have across all six plans (14-01 through 14-06) is present in the
codebase, wired, tested at unit and real-stdio integration level, and matches the documentation
exactly (matrix ratings, ARCHITECTURE §7/§15, CHANGELOG, README, REQUIREMENTS.md). The SC1
"server instructions" claim is honestly bounded to `14-EVIDENCE.md`'s finding (server-everything
sets instructions live; no over-claim). CAP-CANCELLATION correctly stays absent/out with the
SDK-dispatcher-consumes-it finding recorded, and CAP-LOGGING correctly stays partial/out
(`logging/setLevel` never sent, no transcript surfacing). No `CAP-SCHEMA-DEFERRAL` row was
improperly added. Constraints (additive-only `run --json`, no race with Phase 12's
unregistration, no new core dependency, lazy imports) all hold under direct code inspection and
passing race-guard tests.

---

*Verified: 2026-09-25*
*Verifier: Claude (gsd-verifier)*
