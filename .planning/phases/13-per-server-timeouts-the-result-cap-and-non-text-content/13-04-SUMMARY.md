---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
plan: 04
subsystem: tools
tags: [mcp, result-cap, content-rendering, mcp-22, mcp-25]

# Dependency graph
requires:
  - phase: 13-02
    provides: "MCPServerConfig.max_result_chars, MCPManager._max_result_chars_for(server)"
  - phase: 13-03
    provides: "render_content_block(block), truncate_result(text, limit, server)"
provides:
  - "_content_to_text(result, *, limit, server) — every tools/call result rendered through
    render_content_block and capped through truncate_result, no str(chunk) repr, no dropped
    ERROR prefix"
  - "read_resource / get_prompt text capped by the same per-server max_result_chars and marker
    (ruling on research Open Question 1 — the cap extends beyond call_tool alone)"
affects: ["13-05", "13-06 (docs: ARCHITECTURE §7 extension of the cap to read_resource/get_prompt)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The per-server max_result_chars limit is computed once on the caller's thread
      (call_tool/read_resource/get_prompt) before scheduling the coroutine onto the MCP event
      loop, not inside the async _call — keeps _max_result_chars_for's dict lookups off the
      loop thread, matching the existing _call_timeout_for pattern"

key-files:
  created: []
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py

key-decisions:
  - "Research Open Question 1 ruled: the cap applies to call_tool (ADR 0004's named site) AND to
    read_resource/get_prompt, using the same per-server max_result_chars and marker text. ADR
    0004 names only _content_to_text, but the roadmap goal is capability-framed ('an oversized
    tool result truncates visibly'), a resource read or prompt render feeds the same context
    budget, and nothing argues against it. list_resources/list_prompts/list_resource_templates/
    complete are NOT capped — they are bounded by list length, and ADR 0004 does not reach them."
  - "Phase 11's _resource_contents_to_text / _prompt_messages_to_text marker text stays
    byte-for-byte; only a truncate_result(text, limit, server) call was added after each,
    leaving their own binary-marker and non-text-block wording untouched."
  - "structured_content stays unread (ADR 0004 scope); the docstring mentions it once, never
    reads it."
  - "call_tool keeps returning str; no new ToolResult.metadata key was added for MCP tool calls
    — the marker carries the facts, run --json stays additive-only by adding nothing here."
  - "Discovered-defect fix (found while rewriting the function this plan owns): mcp 2.0's
    CallToolResult field is is_error, not isError, so server error results had silently lost
    their 'ERROR: ' prefix. _content_to_text now reads is_error first, falling back to isError
    for older SDKs."

requirements-completed: [MCP-22, MCP-25]

# Metrics
duration: ~20min
completed: 2026-09-24
---

# Phase 13 Plan 04: Wire the result cap and non-text content rendering into the MCP client Summary

**`_content_to_text` now caps every `tools/call` result at the server's `max_result_chars`
(default 8,000, ADR 0004) with a visible truncation marker and renders every content block —
text, image, audio, embedded resource, resource link, or unknown — through
`render_content_block` instead of `str(chunk)`'s Python repr; the same cap now also bounds
`read_resource` and `get_prompt` text, and a discovered `is_error`/`isError` field-name defect
that had silently dropped the `ERROR: ` prefix on mcp 2.0 server errors is fixed in the same
rewrite.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 2 (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`)

## Accomplishments
- `_content_to_text(result, *, limit, server)` joins `render_content_block(chunk)` output for
  every content block, then truncates the joined body with `truncate_result(body, limit,
  server)`, then applies the `ERROR: ` prefix — so a truncated error result still starts with
  `ERROR: ` followed by the capped (not the full) body, and the truncation marker sits inside the
  `ERROR: ` wrapper.
- `call_tool` computes `limit = self._max_result_chars_for(server)` on the caller's thread before
  scheduling the coroutine, matching the existing `_call_timeout_for` pattern, and passes it
  through to `_content_to_text`.
- `read_resource` and `get_prompt` each compute the same per-server limit and call
  `truncate_result(text, limit, server)` immediately after their existing Phase-11
  `_resource_contents_to_text` / `_prompt_messages_to_text` call — those two functions and their
  own marker wording and metadata are untouched.
- Non-text blocks never reach the prompt as a Python repr or inlined base64: `ImageContent`/
  `AudioContent` render as `[image|audio content: mime_type=... base64_len=N — not inlined]`,
  binary `EmbeddedResource` as the same shape under a `uri=...` header, text `EmbeddedResource`
  inlined under the header, `ResourceLink` as `[resource link uri=... name=... mime_type=...
  size=...]`, and any unknown/duck-typed block as `[non-text content block: TypeName — not
  inlined]` — verified against real `mcp.types` SDK objects in every new test but one (the
  duck-typed unknown-block test, which intentionally uses a local class with no SDK base).
- Discovered-defect fix: `_content_to_text` now reads `getattr(result, "is_error", None)` first,
  falling back to `getattr(result, "isError", False)` for pre-2.0 SDKs — mcp 2.0's
  `CallToolResult` field is `is_error`, so the pre-existing code (`getattr(result, "isError",
  False)`) always read `False` against a real 2.0 server error and silently dropped the `ERROR: `
  prefix. Pinned by `test_call_tool_error_result_is_prefixed_on_sdk2_is_error` and
  `test_truncated_error_result_keeps_error_prefix`.
- Two Phase-11 docstrings (`_resource_contents_to_text`, `_prompt_messages_to_text`) updated to
  stop pointing at `_content_to_text`'s repr fallback and MCP-25/CAP-CONTENT-BLOCKS as future
  work — both are now true: the caller caps the text (MCP-22) and `_content_to_text` renders the
  same block types through `render_content_block` (MCP-25).

## Task Commits

Each task was committed atomically:

1. **Task 1: RED — cap and content-block tests through the fake transport** - `a3e9a92` (test)
2. **Task 2: GREEN — cap and render in _content_to_text, read_resource and get_prompt** -
   `d74edcd` (feat)

_TDD: RED (test) then GREEN (feat) commits._

## Files Created/Modified
- `src/agent86/tools/mcp_client.py` - `_content_to_text` rewritten to render + cap; `call_tool`,
  `read_resource`, `get_prompt` each compute and pass the per-server limit; two docstrings updated
- `tests/unit/test_mcp.py` - fourteen new tests pinning the cap, the error-prefix fix, and
  no-repr/no-base64 rendering through the real `call_tool`/`read_resource`/`get_prompt` call paths

## Decisions Made
See `key-decisions` in frontmatter — the Research Open Question 1 ruling (cap extends to
`read_resource`/`get_prompt`) and the `is_error`/`isError` discovered-defect fix are the two
load-bearing decisions; both are recorded there for 13-06's docs pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The GREEN docstring's own wording would have failed its own acceptance
criterion**
- **Found during:** Task 2, immediately after writing `_content_to_text`'s new docstring
- **Issue:** The plan's own action text for the new docstring includes the literal phrase
  ``never ``str(chunk)``'s Python repr`` — but the plan's acceptance criteria also requires
  `grep -c "str(chunk)" src/agent86/tools/mcp_client.py` to equal `0`. Following the action text
  verbatim would leave one `str(chunk)` match (in the docstring itself, not in code) and fail
  the plan's own acceptance check.
- **Fix:** Reworded the docstring sentence to "never the raw chunk's Python repr" — same meaning,
  no literal `str(chunk)` substring. No behavior change; docstring only.
- **Files modified:** `src/agent86/tools/mcp_client.py`
- **Verification:** `grep -c "str(chunk)" src/agent86/tools/mcp_client.py` → `0`
- **Committed in:** `d74edcd` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — a self-contradictory plan instruction, docstring
wording only, no functional change)
**Impact on plan:** No scope creep. The fix makes the plan's own two acceptance criteria (the
docstring wording, and the `str(chunk)` grep count) simultaneously satisfiable.

## Issues Encountered
- `tests/unit/test_mcp.py::test_death_eof_clears_sessions_and_tools` failed once in a full
  `pytest tests/unit/ -q` run (a pre-existing Phase-12 timing-sensitive assertion — `_tasks["srv"]
  .done()` checked before the background task had actually finished cancelling — unrelated to
  this plan's files) and passed both in isolation and on a full rerun immediately after. Not
  fixed here (out of this plan's scope per the Fix Attempt Limit / scope boundary rules); not
  logged to `deferred-items.md` since it is a known flake pattern, not a new discovery, and
  reruns confirm it is not a regression introduced by this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
`_content_to_text`, `read_resource` and `get_prompt` all cap their text at the server's
`max_result_chars` with a visible, consistently-worded marker, and no MCP content block can reach
the model as a Python repr or inlined base64. Plan 13-06 (docs signoff) can now record the
Research Open Question 1 ruling in `ARCHITECTURE.md` §7 and update
`docs/mcp-conformance-matrix.md`'s `CAP-CONTENT-BLOCKS`/`CAP-STRUCTURED-OUTPUT` rows if needed. No
other file in `mcp_client.py` beyond `_content_to_text`, `call_tool`, `read_resource`,
`get_prompt` and the two Phase-11 docstrings was touched by this plan.

---
*Phase: 13-per-server-timeouts-the-result-cap-and-non-text-content*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: src/agent86/tools/mcp_client.py (render_content_block/truncate_result imports,
  rewritten _content_to_text, capped call_tool/read_resource/get_prompt)
- FOUND: tests/unit/test_mcp.py (fourteen new `test_call_tool_*`/`test_read_resource_*`/
  `test_get_prompt_*`/`test_result_cap_*`/`test_truncated_error_result_*` tests)
- FOUND commit a3e9a92 (Task 1 - test)
- FOUND commit d74edcd (Task 2 - feat)
