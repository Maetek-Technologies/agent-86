---
phase: 11-resources-and-prompts-become-first-class
plan: 02
subsystem: mcp
tags: [mcp, resources, tool-registry, pydantic, capability-gating]

# Dependency graph
requires:
  - phase: 11-resources-and-prompts-become-first-class
    provides: "plan 11-01's live_mcp_server.py resources/prompt/completion fixture and test_mcp.py's _FakeCaps/_fake_result/_install_fake_transport(capabilities=/responses=/calls=) machinery"
provides:
  - "MCPManager.list_resources/list_resource_templates/read_resource/subscribe_resource (with subscribe=False for unsubscribe) — five real resources/* call sites sharing one _on_session marshaller"
  - "Five capability-gated synthetic per-server tools (MCPListResourcesTool, MCPReadResourceTool, MCPListResourceTemplatesTool, MCPSubscribeResourceTool, MCPUnsubscribeResourceTool) built on a shared _MCPCapabilityTool[TArgs] base"
  - "_capability_tools(manager, server, caps) gate wired into _serve, reading session.server_capabilities once and appending synthetic tools AFTER the server's own tools (D-04)"
  - "_resources_to_text / _resource_templates_to_text / _resource_contents_to_text renderers that never inline a binary resource's base64 (D-02)"
  - "The widened list[Tool] typing on MCPManager (_server_tools, start_server, _launch, tools_for, tools) — the shared seam plan 11-03 extends with prompts/completions branches"
affects: [11-03-prompts-and-completion-client-support, 11-04-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_MCPCapabilityTool[TArgs] base class: a synthetic per-server tool with a fixed verb/local Args model, contrasted deliberately beside MCPTool (server-schema-driven) in the same file so the two wrapping strategies are readable side by side"
    - "_on_session(server, call, timeout) — one shared event-loop marshalling helper for every non-tools/* MCP capability call site, replacing what would otherwise be N copies of call_tool's run_coroutine_threadsafe(...).result(timeout=...) shape"
    - "Capability-gated tool registration (not capability-gated calls) — a server that never declared a capability never gets the tool offered, so it can never see a 'method not found' from a tool agent86 advertised"

key-files:
  created: []
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py
    - tests/integration/test_mcp_client.py
    - tests/integration/test_mcp_live.py

key-decisions:
  - "Tasks 1 and 2 landed as a single commit (a57e09f) rather than two: Task 1's _capability_tools function forward-references the five tool classes Task 2 defines. A Task-1-only commit would leave the file failing mypy (5 name-defined errors) and ruff (4 unused-import + 5 undefined-name errors) even though the pre-existing 38-test suite would still pass (no test yet exercised the capability-gated path). Splitting would have violated each task's own 'mypy exits 0' acceptance criterion, so both tasks' file edits were completed together before the first commit, matching the combined verification the plan's own acceptance criteria actually require."
  - "One line-wrap fix beyond the plan's literal action text: the read_resource _call body wrote _resource_contents_to_text(...) across three lines, which ruff format --check flagged. Collapsed to one line (a cosmetic, scope-limited fix on code this plan itself just wrote) rather than left unformatted; the two pre-existing MCPTool.__init__/spec() formatting gaps (present before this plan touched the file, part of the 74-file backlog plan 10-05 already logged in deferred-items.md) were left untouched, consistent with that precedent."

requirements-completed: [MCP-14]

# Metrics
duration: ~14min
completed: 2026-09-24
---

# Phase 11 Plan 02: MCP Resources Become First-Class Summary

**Capability-gated `mcp__{server}__{list_resources,read_resource,list_resource_templates,subscribe_resource,unsubscribe_resource}` synthetic tools, wired through a widened `MCPManager` that reads `server_capabilities` once and never inlines a binary resource's base64.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-09-24T12:56:00Z (approx, first Read)
- **Completed:** 2026-09-24T13:10:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `MCPManager` gained five `resources/*` call sites (`list_resources`, `list_resource_templates`, `read_resource`, `subscribe_resource` with a `subscribe=False` unsubscribe path) sharing one `_on_session` event-loop marshaller — the same `run_coroutine_threadsafe(...).result(timeout=...)` shape `call_tool` already used, not eight copies of it.
- `_serve` now reads `session.server_capabilities` once via `getattr(..., None)` (degrading to "no synthetic tools" for an SDK or fake without the property) and appends whatever `_capability_tools` returns AFTER the server's own tools (D-04), so a real tool named `read_resource` on a server keeps its name and the synthetic one is reported as a registry collision rather than shadowing it.
- Five new tool classes (`MCPListResourcesTool`, `MCPReadResourceTool`, `MCPListResourceTemplatesTool`, `MCPSubscribeResourceTool`, `MCPUnsubscribeResourceTool`) share a new `_MCPCapabilityTool[TArgs]` base — agent86's own fixed verb + local Pydantic `Args` model, contrasted deliberately beside `MCPTool` (server-schema-driven) in the same file. Only subscribe/unsubscribe are `side_effecting = True` (D-03); the three reads are not approval-gated.
- A binary resource's base64 never reaches the model: `_resource_contents_to_text` renders `[binary resource uri=... mime_type=... base64_len=N — not inlined]` and records only a `{uri, mime_type, base64_len}` descriptor under `ToolResult.metadata["binary"]` — the blob itself is carried nowhere (D-02).
- Six new unit tests pin capability gating (three-tools-mounted, none-mounted, subscribe-flag-gated), blob non-inlining, URI wire fidelity, and the never-raise contract. The two previously-exact tool-name-set assertions in the integration suite are now subset checks with negative assertions proving the subscribe gate holds, plus a new real-stdio `list_resources -> read_resource` round trip against the live fixture.
- Full suite: **1257 passed** (up from the 1250 baseline after plan 11-01), 0 failed; `mypy src/agent86` and `ruff check .` both clean.

## Task Commits

Each task was committed atomically (Tasks 1 and 2 combined — see Deviations):

1. **Tasks 1+2: shared seam (capability read, `_on_session`, resource renderers, `MCPManager` call sites) + the five resource tool classes** - `a57e09f` (feat)
2. **Task 3: capability-gating/blob-non-inlining unit tests, a real stdio round trip, and the two widened tool-set assertions** - `cc37312` (test)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified
- `src/agent86/tools/mcp_client.py` - `_capability_tools`, `_MCPCapabilityTool[TArgs]`, five resource tool classes, `MCPManager._on_session` + five resource call sites, three renderers (`_resources_to_text`/`_resource_templates_to_text`/`_resource_contents_to_text`), widened `list[Tool]` typing, `_serve`'s capability-gated tool append, `__all__` additions
- `tests/unit/test_mcp.py` - Six new tests: `test_resources_capability_mounts_the_three_read_tools`, `test_absent_resources_capability_mounts_no_synthetic_tools`, `test_resources_capability_subscribe_flag_gates_the_subscribe_tools`, `test_blob_resource_content_is_never_inlined`, `test_read_resource_sends_the_uri_over_the_wire`, `test_read_resource_failure_is_a_soft_tool_result`
- `tests/integration/test_mcp_client.py` - `test_per_server_start_lists_real_tools` widened to a remote-tools subset + resource-tools subset + subscribe-gate negative; new `test_list_resources_then_read_resource_round_trip` (real stdio)
- `tests/integration/test_mcp_live.py` - `test_live_transport_lists_and_calls_tools`'s exact-set assertion widened to a subset check plus `mcp__live__subscribe_resource` absence, so plan 11-03's prompt tools won't invalidate it a second time

## Decisions Made
- Tasks 1 and 2 landed as one commit rather than two (forward-reference coupling; see key-decisions above and Deviations).
- One line-wrap fix to stay `ruff format`-clean on new code, leaving the two pre-existing unformatted `MCPTool` spots untouched per the plan 10-05 precedent.
- No architectural decisions required beyond the plan's own D-01…D-05 rulings, all implemented as specified.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_on_session`'s `Awaitable[Any]` parameter type failed mypy against `asyncio.run_coroutine_threadsafe`**
- **Found during:** Task 1 verification (`mypy src/agent86`)
- **Issue:** The plan's literal action text types `_on_session`'s `call` parameter as `Callable[[Any], Awaitable[Any]]`. `asyncio.run_coroutine_threadsafe`'s typeshed signature expects a `Coroutine[Any, Any, T]`, not the broader `Awaitable[Any]`, so mypy reported `error: Argument 1 to "run_coroutine_threadsafe" has incompatible type "Awaitable[Any]"; expected "Coroutine[Any, Any, Never]"`.
- **Fix:** Imported `Coroutine` instead of `Awaitable` from `collections.abc` and typed the parameter as `Callable[[Any], Coroutine[Any, Any, Any]]`. No behavioral change — every call site already passes an `async def _call(...)` closure, which satisfies `Coroutine` too.
- **Files modified:** `src/agent86/tools/mcp_client.py`
- **Verification:** `mypy src/agent86` — Success, no issues found in 93 source files.
- **Committed in:** `a57e09f` (Task 1/2 commit)

**2. [Rule 1 - Bug/formatting] One new line exceeded the plan's own formatting acceptance criterion**
- **Found during:** Task 3 verification (`ruff format --check`)
- **Issue:** The `read_resource` call site's `_call` body wrote `_resource_contents_to_text(list(getattr(result, "contents", None) or []))` split across three lines (matching the plan's literal action text), which `ruff format --check` flagged as needing reformatting to fit on one line (99 chars, under the 100-char limit).
- **Fix:** Collapsed to one line.
- **Files modified:** `src/agent86/tools/mcp_client.py`
- **Verification:** `ruff format --check src/agent86/tools/mcp_client.py tests/unit/test_mcp.py tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py` — only the two pre-existing, out-of-scope `MCPTool.__init__`/`spec()` formatting gaps remain (confirmed present in the file at commit `7664fc3`, before this plan touched it — part of the 74-file backlog `deferred-items.md` already recorded by plan 10-05).
- **Committed in:** `cc37312` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking type-checker fix, 1 formatting fix on this plan's own new code)
**Impact on plan:** Neither changes behavior; both were required to meet the plan's own stated acceptance criteria (`mypy exits 0`, `ruff format --check` clean on this plan's files). No scope creep.

### Structural deviation (documented, not a "fix")

**Tasks 1 and 2 committed together, not as two separate commits.**
- **Reason:** Task 1's action text adds `_capability_tools`, which references `MCPListResourcesTool`, `MCPReadResourceTool`, `MCPListResourceTemplatesTool`, `MCPSubscribeResourceTool`, `MCPUnsubscribeResourceTool` — classes Task 2's action text defines. A commit containing only Task 1's edits would fail `mypy` (5 `name-defined` errors) and `ruff check` (4 unused-import + 5 `F821` undefined-name errors), even though `pytest tests/unit/test_mcp.py` would still pass 38/38 at that point (no test before Task 3 exercises the capability-gated path with `resources` non-`None`). Verified by actually staging the two halves separately via `git add -p`, stashing the remainder, and running the full verification trio against the Task-1-only tree before deciding to combine.
- **Resolution:** Completed both tasks' file edits, then ran each task's full acceptance-criteria grep/python/mypy/ruff/pytest list (all passed against the combined state — see verification transcript above), then committed once as `a57e09f`.
- **Impact:** None on functionality, test coverage, or the plan's own acceptance criteria — every grep/python/mypy/ruff/pytest check the plan lists for both Task 1 and Task 2 passed against the final state. The only change is commit granularity (one commit covering two tightly-coupled tasks in the same file instead of two, one of which would not itself have been independently green).

## Issues Encountered
None beyond the two documented auto-fixes above.

## User Setup Required
None - no external service configuration required.

## Observed evidence (for plan 11-03/11-04)

Recorded per this plan's `<output>` instruction, captured by connecting a fresh `MCPManager` to the real `live_mcp_server.py` fixture over stdio:

**`ReadResourceResult.contents` shape for `res://agent86/blob.bin`:** the installed `mcp` SDK returns it as a `BlobResourceContents` (i.e. `blob`, not `text`) — `_resource_contents_to_text` accordingly renders:
```
[binary resource uri=res://agent86/blob.bin mime_type=application/octet-stream base64_len=32 — not inlined]
```
with `metadata == {"uri": "res://agent86/blob.bin", "binary": [{"uri": "res://agent86/blob.bin", "mime_type": "application/octet-stream", "base64_len": 32}]}`. No fallback-to-text branch was exercised on this platform; the `not inlined` assertion in `test_list_resources_then_read_resource_round_trip` is exercising the real blob path, not a tautology.

**Exact ordered tool-name list** a fresh stdio connection to the live fixture now produces (`resources.subscribe = False` on this fixture, so no subscribe/unsubscribe tools — plan 11-03 appends prompts/completions tools after these):
```
mcp__alpha__add
mcp__alpha__shout
mcp__alpha__get_env
mcp__alpha__list_resources
mcp__alpha__read_resource
mcp__alpha__list_resource_templates
```

## Next Phase Readiness
- Plan 11-03 (prompts and completion client support) can add `prompts`/`completions` branches to the now-shared `_capability_tools` function and `_on_session` marshaller without re-deriving either — both are explicitly named in this plan's objective as the seam 11-03 extends, not reinvents.
- Plan 11-04 (phase signoff) can cite the ordered tool-name list and the observed `BlobResourceContents` shape above directly, as this plan's `<output>` instruction required.
- `CAP-RESOURCES` and `CAP-RESOURCE-TEMPLATES` are now implemented; `CAP-RESOURCE-SUBSCRIBE` moves to `partial` per D-01 (both call sites exist; the update notification itself is still dropped, tracked as MCP-24) — matching the plan's success criteria exactly.
- No blockers.

---
*Phase: 11-resources-and-prompts-become-first-class*
*Completed: 2026-09-24*

## Self-Check: PASSED

All claimed files found on disk (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`,
`tests/integration/test_mcp_client.py`, `tests/integration/test_mcp_live.py`); both task commit
hashes (`a57e09f`, `cc37312`) found in git history.
