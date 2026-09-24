---
phase: 11-resources-and-prompts-become-first-class
plan: 03
subsystem: mcp
tags: [mcp, prompts, completion, tool-registry, pydantic, capability-gating]

# Dependency graph
requires:
  - phase: 11-resources-and-prompts-become-first-class
    provides: "plan 11-02's shared seam — _capability_tools(manager, server, caps), MCPManager._on_session, the _MCPCapabilityTool family, and the server_capabilities read in _serve — extended verbatim rather than re-created"
provides:
  - "MCPManager.list_prompts/get_prompt/complete — three real prompts/*/completion/* call sites sharing _on_session"
  - "Three capability-gated synthetic per-server tools (MCPListPromptsTool, MCPGetPromptTool, MCPCompleteTool) built on the existing _MCPCapabilityTool[TArgs] base"
  - "_capability_tools gained two independent branches: caps.prompts != None mounts list_prompts/get_prompt; caps.completions != None mounts complete (a server may declare either without the other)"
  - "_prompts_to_text / _prompt_messages_to_text / _completion_to_text renderers — a non-text prompt content block renders as a named marker (D-07), never a Python repr"
  - "complete()'s explicit ref_type: Literal['prompt','resource'] (D-08) — Pydantic validation refuses an invalid ref_type before any wire call"
affects: [11-04-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Same _MCPCapabilityTool[TArgs] wrapping strategy plan 11-02 established, extended to a third capability pair (prompts/completions) without touching the resources branch"
    - "Explicit discriminator field (ref_type: Literal[...]) instead of guessing a reference union from a bare string — a Pydantic validation failure names the fix rather than silently building the wrong SDK type"

key-files:
  created: []
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py
    - tests/integration/test_mcp_client.py

key-decisions:
  - "Tasks 1 and 2 landed as a single commit (4325a0a), same precedent as plan 11-02's Tasks 1+2: Task 1's Literal import is unused until Task 2's _CompleteArgs.ref_type consumes it, so a Task-1-only commit would fail ruff check (F401 unused import) even though the pre-existing test suite would still pass. Both tasks' edits were completed and the full verification trio (grep/python/mypy/ruff/pytest) run against the combined state before the first commit."
  - "PromptReference/ResourceTemplateReference each grep-count 2, not the plan's stated 1 — a planning-time miscount in the acceptance criteria (the plan's own literal action text puts each name in both the complete() docstring and the constructor call it documents). Not fixed; the substantive requirement (no top-level mcp import, ref_type explicitly selects the right SDK class) holds and is separately pinned by the wire-shape unit test."

requirements-completed: [MCP-15]

# Metrics
duration: ~20min
completed: 2026-09-24
---

# Phase 11 Plan 03: MCP Prompts and Completion Become First-Class Summary

**Capability-gated `mcp__{server}__{list_prompts,get_prompt,complete}` synthetic tools, an explicit `ref_type`-discriminated `complete()` call site, and a prompt-transcript renderer that never emits a Python repr for a non-text content block.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-09-24T13:10:00Z (approx, first Read)
- **Completed:** 2026-09-24T13:30:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `MCPManager` gained three real call sites (`list_prompts`, `get_prompt`, `complete`) sharing plan 11-02's `_on_session` marshaller — no new event-loop plumbing, same `run_coroutine_threadsafe(...).result(timeout=...)` shape every prior capability call site uses.
- Three new tool classes (`MCPListPromptsTool`, `MCPGetPromptTool`, `MCPCompleteTool`) share the existing `_MCPCapabilityTool[TArgs]` base from plan 11-02; all three keep `side_effecting = False` (D-06) — `list_prompts`/`get_prompt`/`complete` are pure reads and approval-gating them would be noise.
- `_capability_tools` gained two independent branches: a server declaring `prompts` mounts `list_prompts`+`get_prompt`; one declaring `completions` mounts `complete`; a server can declare either without the other (verified: `test_completions_capability_mounts_only_the_complete_tool` mounts exactly one tool with no `prompts` capability present).
- `complete()` takes an explicit `ref_type: Literal["prompt", "resource"]` (D-08) rather than guessing from a bare string — `MCPCompleteTool.run` with `ref_type="template"` is refused by Pydantic's "Invalid arguments" before the manager is ever reached (pinned by a unit test with a manager that raises `AssertionError` if called).
- `_prompt_messages_to_text` renders a non-text `PromptMessage` content block (image, audio, embedded resource) as `[role]: [non-text content block: TypeName — not inlined]` and records `{"index", "role", "type"}` per block under `metadata["non_text_blocks"]` — never `str(block)`, the Python repr `_content_to_text`'s pre-existing fallback still uses (untouched — that's MCP-25, workstream C). Pinned by a unit test asserting neither `object at 0x` nor `<` appears in the rendered text.
- Seven new tests: five unit (prompts-mounts, completions-mounts-only-complete, absent-mounts-neither, non-text-block-marker, complete-sends-a-real-PromptReference-over-the-wire) and two real-stdio integration tests (`list_prompts` → `get_prompt` against the live `review_code` fixture; `complete()` returning all three `STYLE_COMPLETIONS` unfiltered and exactly `["security-focused"]` prefix-filtered on `"s"`). `test_per_server_start_lists_real_tools`'s subset assertion widened to include the three new tool names.
- Full suite: **1264 passed** (up from the 1257 baseline after plan 11-02), 0 failed; `mypy src/agent86` and `ruff check .` both clean.

## Task Commits

Each task was committed atomically (Tasks 1 and 2 combined — see Deviations):

1. **Tasks 1+2: prompt/completion renderers, MCPManager call sites, the three tool classes, and the two new `_capability_tools` gates** - `4325a0a` (feat)
2. **Task 3: prompts/completions capability-gating unit tests, the non-text-block marker test, the wire-shape test, and a real stdio round trip** - `a248496` (test)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified
- `src/agent86/tools/mcp_client.py` - `_prompts_to_text`/`_prompt_messages_to_text`/`_completion_to_text` renderers; `MCPManager.list_prompts`/`get_prompt`/`complete`; `_GetPromptArgs`/`_CompleteArgs`; `MCPListPromptsTool`/`MCPGetPromptTool`/`MCPCompleteTool`; two new `_capability_tools` branches; `__all__` additions
- `tests/unit/test_mcp.py` - Five new tests: `test_prompts_capability_mounts_the_prompt_tools`, `test_completions_capability_mounts_only_the_complete_tool`, `test_absent_prompts_capability_mounts_no_prompt_tools`, `test_non_text_prompt_block_is_marked_not_repred`, `test_complete_sends_a_prompt_reference_over_the_wire`
- `tests/integration/test_mcp_client.py` - `test_per_server_start_lists_real_tools` widened to include the three new tool names; new `test_list_prompts_then_get_prompt_round_trip` and `test_complete_returns_argument_suggestions` (both real stdio, `from tests.integration.live_mcp_server import STYLE_COMPLETIONS` — a plain package import works because `tests/integration/__init__.py` already exists, so no `importlib.util.spec_from_file_location` indirection was needed)

## Decisions Made
- Tasks 1 and 2 landed as one commit rather than two (unused-`Literal`-import coupling; see key-decisions above and Deviations).
- No architectural decisions required beyond the plan's own D-06/D-07/D-08 rulings, all implemented as specified.

## Deviations from Plan

### Documented, Non-Blocking

**1. Plan's "grep -c PromptReference/ResourceTemplateReference returns 1" acceptance criterion does not match the file's actual state**
- **Found during:** Task 1 verification
- **Issue:** The plan's acceptance criteria state `grep -c "PromptReference"` and `grep -c "ResourceTemplateReference"` should each return 1. The plan's own literal action text for `complete()` places each name in both the method's docstring ("`PromptReference(name=ref)`, anything else a `ResourceTemplateReference(uri=ref)`") and the constructor call it documents — so the file, copied verbatim from the plan, has each name appearing twice, not once.
- **Assessment:** A planning-time miscount, not a code defect — the same class of issue plan 11-01 and 11-02 each documented once. The substantive requirements the criteria exist to protect (no top-level `mcp` import; `ref_type` explicitly selects `PromptReference` vs `ResourceTemplateReference`, never a guess) are met and separately pinned by `test_complete_sends_a_prompt_reference_over_the_wire`, which asserts `ref.type == "ref/prompt"` against the real SDK class.
- **Fix:** None applied — the docstring was not reworded to dodge the count, since doing so would be cosmetic churn against the plan's own specified text.
- **Files modified:** None beyond the plan's own edits.
- **Verification:** `grep -c "PromptReference" src/agent86/tools/mcp_client.py` returns 2 (docstring + constructor call); same for `ResourceTemplateReference`; `pytest tests/unit/test_mcp.py -q` — 49 passed, 0 failed.
- **Committed in:** `4325a0a` (part of Task 1/2 commit; no separate fix commit needed)

---

**Total deviations:** 1 documented, non-blocking (a plan-authoring miscount in an acceptance criterion; no code fix required) + 1 structural (Tasks 1+2 combined into one commit, matching plan 11-02's own precedent and explicitly allowed by this plan's execution notes)
**Impact on plan:** None on functionality or test coverage. Every acceptance criterion measuring actual load-bearing behavior (capability gating, wire shape, non-text-block marker, ref_type validation, full suite green) passes.

## Issues Encountered
None beyond the documented deviation above.

## User Setup Required
None - no external service configuration required.

## Observed evidence (for plan 11-04)

Recorded per this plan's `<output>` instruction, captured by connecting a fresh `MCPManager` to the real `live_mcp_server.py` fixture over stdio.

**Exact ordered tool-name list** a fresh stdio connection to the live fixture now produces — nine tools total, matching the plan's verification step 6 exactly:
```
mcp__alpha__add
mcp__alpha__shout
mcp__alpha__get_env
mcp__alpha__list_resources
mcp__alpha__read_resource
mcp__alpha__list_resource_templates
mcp__alpha__list_prompts
mcp__alpha__get_prompt
mcp__alpha__complete
```
`mcp__alpha__subscribe_resource`/`unsubscribe_resource` correctly absent (the fixture declares `resources.subscribe = False`).

**Exact rendered `get_prompt("review_code", {"path": "a.py", "style": "concise"})` output:**
```
Review a file in a given style.

[user]: Review the file at a.py in a concise style.
```
with `metadata == {"prompt": "review_code"}` (no `non_text_blocks` key — the fixture's prompt message is pure text).

## Next Phase Readiness
- Plan 11-04 (phase signoff) can cite the nine-tool ordered list and the exact `get_prompt` rendering above directly, as this plan's `<output>` instruction required, when it rewrites `docs/mcp-conformance-matrix.md`'s `CAP-PROMPTS` and `CAP-COMPLETION` rows from absent to implemented.
- `CAP-PROMPTS` and `CAP-COMPLETION` are now implemented, closing MCP-15.
- No blockers.

---
*Phase: 11-resources-and-prompts-become-first-class*
*Completed: 2026-09-24*

## Self-Check: PASSED

All claimed files found on disk (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`,
`tests/integration/test_mcp_client.py`); both task commit hashes (`4325a0a`, `a248496`) found in
git history.
