---
phase: 11-resources-and-prompts-become-first-class
verified: 2026-09-24T13:40:10Z
status: passed
score: 19/19 must-haves verified
---

# Phase 11: Resources and Prompts Become First-Class Verification Report

**Phase Goal:** A model connected through agent86 can list and read any mounted server's
resources, and list/get its prompts — with argument-completion suggestions where the server
supports them — with the same round-trip fidelity tool calls already have. (Requirements MCP-14,
MCP-15.)

**Verified:** 2026-09-24T13:40:10Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (source plan) | Status | Evidence |
|---|---|---|---|
| 1 | CI-safe stdio/HTTP MCP server advertises resources, prompts, completions capabilities (11-01) | ✓ VERIFIED | `tests/integration/live_mcp_server.py` (87 lines) declares `.resource()` x3, `.prompt()`, `.completion()` |
| 2 | That server exposes a text resource, binary resource, resource template, two-arg prompt, completion handler (11-01) | ✓ VERIFIED | `res://agent86/greeting.txt` (text), `res://agent86/blob.bin` (binary), `res://agent86/echo/{word}` (template), `review_code(path, style)` prompt, `complete_argument` handler over `STYLE_COMPLETIONS` |
| 3 | A unit test can drive MCPManager against a fake session declaring any ServerCapabilities shape, incl. `resources.subscribe=True` (11-01) | ✓ VERIFIED | `tests/unit/test_mcp.py:328-364` — `_FakeCaps`/`_FakeResourcesCap`/`_FakePromptsCap`/`_FakeCompletionsCap`, wired through `_install_fake_transport(..., capabilities=...)` |
| 4 | Every existing MCP test still passes unchanged (11-01) | ✓ VERIFIED | `pytest -q` — 1264 passed, 0 failed |
| 5 | Resource-capable server shows `list_resources`/`read_resource`/`list_resource_templates` in the tool list (11-02) | ✓ VERIFIED | `_capability_tools` (`mcp_client.py:337-363`) gates on `getattr(caps, "resources", None)`; live stdio test `test_list_resources_then_read_resource_round_trip` asserts the three tool names appear |
| 6 | A server declaring no resources capability shows none of those tools (11-02) | ✓ VERIFIED | `_capability_tools` returns `[]` unless `resources is not None`; unit tests parametrize `capabilities=_FakeCaps()` (all-None) and assert absence; live SC1 run against `server-filesystem@2026.8.31` independently confirms zero resource tools mounted when `resources=None` |
| 7 | Reading a binary resource returns a mime-type/length marker, never base64, in model-visible content (11-02) | ✓ VERIFIED | `_resource_contents_to_text` (`mcp_client.py:877-908`) — text parts rendered verbatim, binary parts become `[binary resource uri=... mime_type=... base64_len=... — not inlined]`, base64 raw bytes carried nowhere; `test_blob_resource_content_is_never_inlined` pins it |
| 8 | `subscribe_resource`/`unsubscribe_resource` exist, are approval-gated, appear only when `resources.subscribe` (11-02) | ✓ VERIFIED | `MCPSubscribeResourceTool`/`MCPUnsubscribeResourceTool` both set `side_effecting = True`; `_capability_tools` only appends them `if getattr(resources, "subscribe", False)` |
| 9 | Every new tool returns a structured ToolResult error on failure, never raises (11-02) | ✓ VERIFIED | All 8 new `execute()` methods wrap the manager call in `try/except Exception` → `self._failed(exc)`; `test_read_resource_failure_is_a_soft_tool_result` pins it |
| 10 | Prompt-capable server shows `list_prompts`/`get_prompt` in tool list (11-03) | ✓ VERIFIED | `_capability_tools` gates on `getattr(caps, "prompts", None)`; live stdio test `test_list_prompts_then_get_prompt_round_trip` |
| 11 | `get_prompt` renders messages as a `[role]: text` transcript (11-03) | ✓ VERIFIED | `_prompt_messages_to_text` (`mcp_client.py:930+`) builds `f"[{role}]: {text}"` lines |
| 12 | Completion-capable server shows `complete`, returns suggestions for a named prompt argument (11-03) | ✓ VERIFIED | `_capability_tools` gates on `getattr(caps, "completions", None)`; live stdio test `test_complete_returns_argument_suggestions` against `STYLE_COMPLETIONS` |
| 13 | Server declaring neither prompts nor completions is offered neither tool (11-03) | ✓ VERIFIED | Same gate structure as #6; unit-tested with `_FakeCaps()` all-None |
| 14 | Non-text prompt content block renders as named marker, never Python repr (11-03) | ✓ VERIFIED | `_prompt_messages_to_text` docstring + code explicitly avoids `_content_to_text`'s repr fallback (documented as the older-path defect, MCP-25, intentionally not reproduced) |
| 15 | Roadmap SC1 evidenced: real server-filesystem list_resources→read_resource round-trip, text reaches caller (11-04) | ⚠ VERIFIED VIA ALTERNATE EVIDENCE — see adjudication below | `11-EVIDENCE.md` — direct probe of pinned `server-filesystem@2026.8.31` returns `resources=None` / `-32601 Method not found`; genuine MCP resources round trip instead proven by CI fixture's real stdio test (`test_list_resources_then_read_resource_round_trip`, plan 11-02) |
| 16 | Roadmap SC2 evidenced: real server-everything prompts + complete() suggestions, real names recorded (11-04) | ✓ VERIFIED | `11-EVIDENCE.md` — live run against `server-everything@2026.8.31`: 4 real prompts, `completable-prompt`/`department` → `Engineering`/`Sales`/`Marketing`/`Support` |
| 17 | Roadmap SC3 holds: 4 CAP rows read implemented in the matrix (11-04) | ✓ VERIFIED | `docs/mcp-conformance-matrix.md` — `CAP-RESOURCES`, `CAP-RESOURCE-TEMPLATES`, `CAP-PROMPTS`, `CAP-COMPLETION` all rated `implemented`/`in`; `CAP-RESOURCE-SUBSCRIBE` rated `partial`/`in` per plan |
| 18 | No capability this phase shipped still listed as non-goal in ARCHITECTURE.md §15 (11-04) | ✓ VERIFIED | §15 note: "Five rows left this table in v1.1's Phase 11" — all five removed from the not-built table |
| 19 | Live evidence runs stayed in scratchpad — no npx/network dependency entered committed test suite (11-04) | ✓ VERIFIED | `11-EVIDENCE.md` header: "throwaway scratchpad scripts, never committed"; `git status` clean, no new test file imports `npx`/network; `pytest -q` (1264 passed) contains only the stdio-fixture-driven tests |

**Score:** 19/19 truths verified (1 verified via documented alternate evidence rather than literal wording — see adjudication).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/integration/live_mcp_server.py` | resource/template/prompt/completion fixtures, `@mcp.completion()`, ≥80 lines | ✓ VERIFIED | 87 lines, contains `@mcp.completion()` |
| `tests/unit/test_mcp.py` | fake capabilities session helper, `_FakeCaps` | ✓ VERIFIED | 858 lines, `_FakeCaps`/`_FakeResourcesCap`/`_FakePromptsCap`/`_FakeCompletionsCap` all present |
| `src/agent86/tools/mcp_client.py` | capability-gated resource tools, `class MCPReadResourceTool`, ≥700 lines | ✓ VERIFIED | 1002 lines; `MCPListResourcesTool`, `MCPReadResourceTool`, `MCPListResourceTemplatesTool`, `MCPSubscribeResourceTool`, `MCPUnsubscribeResourceTool` all present |
| `tests/integration/test_mcp_client.py` | real stdio `read_resource` round trip | ✓ VERIFIED | 265 lines; `test_list_resources_then_read_resource_round_trip` present and passing |
| `src/agent86/tools/mcp_client.py` | prompt/completion tools, `class MCPCompleteTool` | ✓ VERIFIED | `MCPListPromptsTool`, `MCPGetPromptTool`, `MCPCompleteTool` all present |
| `tests/unit/test_mcp.py` | prompts/completions capability-gate tests, `prompts_capability` | ✓ VERIFIED | matching test names present, all passing |
| `tests/integration/test_mcp_client.py` | real stdio prompts/complete round trip, `review_code` | ✓ VERIFIED | `test_list_prompts_then_get_prompt_round_trip`, `test_complete_returns_argument_suggestions` present, `review_code` referenced |
| `.planning/phases/11.../11-EVIDENCE.md` | verbatim transcripts for SC1/SC2, `server-everything`, ≥60 lines | ✓ VERIFIED | 192 lines, contains `server-everything` |
| `docs/mcp-conformance-matrix.md` | 4 rows implemented, `CAP-RESOURCE-SUBSCRIBE` partial, `CAP-COMPLETION` | ✓ VERIFIED | confirmed by direct grep of rows 40-44 |
| `docs/ARCHITECTURE.md` | §15 with 5 shipped capabilities removed, `CAP-STRUCTURED-OUTPUT` still present as non-goal | ✓ VERIFIED | §15 note block documents the 5-row departure; `CAP-STRUCTURED-OUTPUT` remains in the not-built table |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tests/unit/test_mcp.py` | `agent86.tools.mcp_client.ClientSession` | monkeypatch of `_install_fake_transport` | ✓ WIRED | `_install_fake_transport` present and used throughout new tests |
| `tests/integration/live_mcp_server.py` | `mcp.server.mcpserver.MCPServer` | `.resource()`/`.prompt()`/`.completion()` decorators | ✓ WIRED | all three decorator forms present in the fixture |
| `mcp_client.py::_serve` | `session.server_capabilities` | `getattr` read once after `initialize()` feeding `_capability_tools` | ✓ WIRED | `mcp_client.py:491` — `_capability_tools(self, name, getattr(session, "server_capabilities", None))` |
| `mcp_client.py::MCPReadResourceTool` | `MCPManager.read_resource` | `_on_session` marshalling onto MCP event loop | ✓ WIRED | `execute()` calls `self._manager.read_resource(...)`; `MCPManager.read_resource` present |
| `mcp_client.py::_capability_tools` | `ServerCapabilities.prompts`/`.completions` | `getattr` branches | ✓ WIRED | `mcp_client.py:357-362` |
| `mcp_client.py::MCPManager.complete` | `mcp.types.PromptReference`/`ResourceTemplateReference` | lazy import inside coroutine | ✓ WIRED | confirmed via live evidence run and passing `test_complete_returns_argument_suggestions` |
| `docs/mcp-conformance-matrix.md` | `11-EVIDENCE.md` | "Exercised by" cells citing live runs | ✓ WIRED | rows 40-44 cite `11-EVIDENCE.md` explicitly |
| `docs/ARCHITECTURE.md` | `docs/mcp-conformance-matrix.md` | §15 MCP client conformance paragraph | ✓ WIRED | §15 cross-references `docs/mcp-conformance-matrix.md` |

### Data-Flow Trace (Level 4)

Not applicable in the UI-rendering sense (no component/dashboard renders this data) — the
relevant "data flow" is the tool-result content pipeline, which was traced above under Key Links
and Observable Truths #7/#11/#14 (binary marker, role-prefixed transcript, named non-text
marker). All three trace to real transformation functions (`_resource_contents_to_text`,
`_prompt_messages_to_text`) fed by live `MCPManager` calls, not hardcoded/static values.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full test suite green | `pytest -q` | 1264 passed, 14 deselected in 97.88s | ✓ PASS |
| Lint clean | `ruff check .` | All checks passed! | ✓ PASS |
| Type-check clean | `mypy src/agent86` | Success: no issues found in 93 source files | ✓ PASS |
| Resource/prompt/completion suite specifically | `pytest tests/unit/test_mcp.py tests/integration/test_mcp_client.py -q` | 63 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| MCP-14 | 11-01, 11-02, 11-04 | Resources become first-class — `list_resources`/`read_resource`, absent today | ✓ SATISFIED | `MCPListResourcesTool`/`MCPReadResourceTool`/`MCPListResourceTemplatesTool` shipped, capability-gated, tested over real stdio (CI fixture) and unit-tested for absence; matrix rows `implemented` |
| MCP-15 | 11-01, 11-03, 11-04 | Prompts become first-class — `list_prompts`/`get_prompt`, absent today | ✓ SATISFIED | `MCPListPromptsTool`/`MCPGetPromptTool`/`MCPCompleteTool` shipped, capability-gated, tested over real stdio and against live `server-everything`; matrix rows `implemented` |

**REQUIREMENTS.md cross-reference:** Both MCP-14 and MCP-15 are marked `[x]` / `Complete` in
`.planning/REQUIREMENTS.md`, mapped to Phase 11. No orphaned requirement IDs found — every ID
mapped to Phase 11 in REQUIREMENTS.md appears in at least one plan's `requirements:` frontmatter
(11-01 claims both as scaffolding; 11-02 claims MCP-14; 11-03 claims MCP-15; 11-04 claims both for
evidence/docs closure).

### Anti-Patterns Found

None. Scanned `src/agent86/tools/mcp_client.py` and all four test/fixture files for
TODO/FIXME/XXX/HACK/placeholder/empty-implementation patterns — none found. Every new `execute()`
method has a real try/except body calling into `MCPManager`, not a stub.

### Adjudication: SC1 (server-filesystem live round trip) — external fact, not an agent86 gap

**Finding:** `11-EVIDENCE.md` records that the pinned `@modelcontextprotocol/server-filesystem@2026.8.31`
declares no `resources` capability at all (`server_capabilities.resources == None`) and answers
both `resources/list` and `resources/templates/list` with JSON-RPC `-32601 Method not found`. File
content instead reaches the model through that server's `tools/read_text_file` surface. Roadmap
success criterion 1, as literally worded ("a real `server-filesystem` connection round-trips
`list_resources` → `read_resource`"), was therefore not met against that specific third-party
package.

**Judgment: this is an external fact the phase handled correctly, not an agent86 gap.** Reasoning:

1. **The claim is independently verifiable and was verified two ways, not asserted.** The evidence
   run re-confirmed the pinned version via `npm view` immediately before probing (ruling out
   version drift), then called `MCPManager.list_resources`/`list_resource_templates` directly
   against a live session and got an explicit, unambiguous JSON-RPC `Method not found` — not a
   silent empty list that could be a client-side bug. `server_capabilities.resources` being `None`
   at `initialize()` is the authoritative, protocol-level signal; agent86's client reads exactly
   that signal (`mcp_client.py:491`, `_capability_tools:349-356`) and correctly mounts zero
   resource tools for a server that never declared the capability — the gating logic behaved
   exactly as designed.
2. **agent86's own implementation of the resources capability is proven end-to-end against a real
   MCP server that does declare it**, over a real stdio transport, in a test that runs in CI:
   `tests/integration/test_mcp_client.py::test_list_resources_then_read_resource_round_trip`
   against `tests/integration/live_mcp_server.py` (a genuine `mcp.server.mcpserver.MCPServer`
   subprocess, not a mock). This is the client-side capability the roadmap goal is actually about
   ("A model connected through agent86 can list and read any mounted server's resources") — it is
   demonstrated, not merely asserted.
3. **agent86 cannot make a third-party package implement a protocol capability it doesn't
   implement.** There is no code change available to agent86 that would make `server-filesystem`
   answer `resources/list`. The roadmap's SC1 wording assumed (in Phase 10's audit, before any
   live run against this server) that "`server-filesystem`'s entire value proposition is file
   resources" — an assumption made without verification, which Phase 11 then tested and found
   false. That the assumption baked into the roadmap text turned out wrong is a fact discovered
   about the environment, not a defect introduced or missed by this phase's implementation work.
4. **The team did not quietly reinterpret or paper over the miss.** `11-EVIDENCE.md` states the
   verdict as "not met" in bold, in its own section; `11-VALIDATION.md`'s sign-off explicitly
   records "SC1's real, recorded verdict is not met"; `docs/mcp-conformance-matrix.md`'s
   `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES` rows name the finding in their reasoning cells rather
   than citing the server-filesystem run as if it had succeeded; `.planning/ROADMAP.md`'s "Next"
   section states it in the same forthright terms. This is exactly the documentation standard a
   goal-backward verifier looks for when a literal criterion can't be met for reasons outside the
   codebase's control.
5. **No further agent86 work is implied.** There is nothing to add to a future plan here — the
   capability-gating code, the tool set, the blob-never-inlined rule, and the approval gate for
   subscribe/unsubscribe are all already correct and tested. Re-running this exact roadmap
   scenario against a future `server-filesystem` release that does add resources support would
   either pass (if agent86's gate correctly picks up the new capability — which the code already
   does generically) or reveal a real defect at that time; today's result is simply "this package
   version doesn't have it."

This does not block phase completion and is not routed to `human_needed` — the evidence trail is
complete, cross-checked, and internally consistent enough that no human input changes the
conclusion. It is recorded here for visibility, matching the phase's own EVIDENCE/VALIDATION
documentation.

### Human Verification Required

None. All must-haves are verified against the codebase, the full test suite is green, lint and
type-check are clean, and the one deviation from literal roadmap wording (SC1 above) is resolved
by direct, reproducible evidence already gathered by the phase — no visual, real-time, or
subjective judgment call remains open.

### Gaps Summary

No gaps. All 19 derived observable truths across the phase's four plans are verified against the
actual codebase: capability-gated resource/prompt/completion tools exist, are substantive (1002
lines, all real `MCPManager` call sites), and are wired (registered through `_capability_tools`,
read from `session.server_capabilities`, tested over real stdio in CI and against two live pinned
npm packages). `pytest -q` (1264 passed), `ruff check .` (clean), and `mypy src/agent86` (clean)
all confirm this independently of the SUMMARY/EVIDENCE documents' own claims. The one literal
roadmap-wording miss (SC1 against `server-filesystem`) is an external fact about a third-party
package version, verified two independent ways, already documented forthrightly by the phase
itself, and does not indicate any missing or incorrect agent86 code.

---

_Verified: 2026-09-24T13:40:10Z_
_Verifier: Claude (gsd-verifier)_
