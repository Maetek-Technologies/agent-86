---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
plan: 05
subsystem: testing
tags: [mcp, timeouts, result-cap, content-blocks, integration-tests, mcp-21, mcp-22, mcp-25]

# Dependency graph
requires:
  - phase: 13-02
    provides: "MCPTimeout, MCPServerUnavailable, MCPServerConfig.connect_timeout_s/call_timeout_s/max_result_chars"
  - phase: 13-03
    provides: "render_content_block, truncate_result (mcp_content.py)"
  - phase: 13-04
    provides: "_content_to_text wired to render_content_block + truncate_result; the cap extended to read_resource/get_prompt"
provides:
  - "tests/integration/live_mcp_server.py opt-in AGENT86_LIVE_MCP_EXTRA_TOOLS=1 tools: sleep_for, big_text, tiny_image, tiny_audio, mixed_blocks"
  - "Eight real-stdio integration tests proving SC1 (per-server call timeout), SC2 (the result cap, configured and default), SC3 (real ImageContent/AudioContent/EmbeddedResource/ResourceLink render as markers) end to end"
affects: ["13-06 (docs signoff can now cite real-stdio evidence for MCP-21/22/25, not only fake-transport unit tests)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Extra fixture tools gated behind an env var (AGENT86_LIVE_MCP_EXTRA_TOOLS=1), mirroring the existing AGENT86_LIVE_MCP_PID_FILE opt-in hook, so the fixture's default tool set stays exactly {add, shout, get_env} for every pre-existing exact-set assertion"
    - "_extra_cfg(**limits) helper builds an MCPServerConfig with the extra-tools env flag plus any per-server limit override (call_timeout_s/max_result_chars), and pops a pid_file kwarg into AGENT86_LIVE_MCP_PID_FILE so it composes with the existing kill/reconnect helpers (_read_pid/_kill/_wait_until)"

key-files:
  created: []
  modified:
    - tests/integration/live_mcp_server.py
    - tests/integration/test_mcp_client.py

key-decisions:
  - "IMAGE_BYTES/AUDIO_BYTES imported via `from tests.integration.live_mcp_server import IMAGE_BYTES` / `AUDIO_BYTES`, following the file's own existing precedent (`test_complete_returns_argument_suggestions` already imports STYLE_COMPLETIONS the same way) rather than the plan's importlib.util.spec_from_file_location alternative — simpler, and tests/integration is already importable as a package in this suite."
  - "The oversized-cap test's literal plan text (`out.count(\"x\") == 100`) does not hold: the truncation marker's own wording (\"max_result_chars\" appears twice) contributes extra 'x' characters to the full string. Replaced with asserting the pre-marker line (`out.split(\"\\n\", 1)[0]`) is exactly 100 x's — the assertion the test actually means to make, still pinning the exact cut point."
  - "mixed_blocks' EmbeddedResource/ResourceLink constructor calls pass mime_type= (snake_case); the installed mcp 2.0 BlobResourceContents/ResourceLink models use populate_by_name=True with a to_camel alias generator, so both mime_type and mimeType work — verified by hand round trip before writing the tests."

requirements-completed: [MCP-21, MCP-22, MCP-25]

# Metrics
duration: ~35min
completed: 2026-09-24
---

# Phase 13 Plan 05: Real-stdio proof of per-server timeouts, the result cap and non-text content Summary

**Eight new integration tests drive `live_mcp_server.py` over a real stdio subprocess (no network) through five opt-in fixture tools gated behind `AGENT86_LIVE_MCP_EXTRA_TOOLS=1`, proving that a per-server `call_timeout_s` fails naming the server without killing the session, a call during reconnect backoff gets "is reconnecting" rather than a timeout, an oversized result truncates visibly at both a configured and the default 8,000-char `max_result_chars`, and real SDK `ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink` blocks render as named markers with no inlined base64 and no Python repr — closing out MCP-21/22/25 with live evidence on top of plans 13-02/13-03/13-04's fake-transport unit tests.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 (fixture extra tools, then real-stdio tests)
- **Files modified:** 2 (`tests/integration/live_mcp_server.py`, `tests/integration/test_mcp_client.py`)

## Accomplishments
- `live_mcp_server.py` gained five opt-in tools behind `AGENT86_LIVE_MCP_EXTRA_TOOLS=1`: `sleep_for` (an `anyio.sleep`-based call-timeout probe), `big_text` (an n-character result-cap probe), `tiny_image`/`tiny_audio` (real `mcp.server.mcpserver.Image`/`Audio` returns), and `mixed_blocks` (text plus a real binary `EmbeddedResource` plus a `ResourceLink` in one result) — verified by hand round trip via a scratchpad `MCPManager.start_server` + `call_tool` script before any test was written. The fixture's default tool set (`add`, `shout`, `get_env`) is unchanged, confirmed by every pre-existing exact-set assertion still passing.
- `test_mcp_client.py` gained a `_extra_cfg(**limits)` helper and eight `test_real_stdio_*` tests:
  - `test_real_stdio_call_timeout_is_per_server` — a 1s `call_timeout_s` against a 10s sleep raises `MCPTimeout` in under 6s naming `'slow'` and `call_timeout_s`, and the same server answers `add` right after (the cancelled call didn't take the session down).
  - `test_real_stdio_call_under_budget_succeeds` — a call that finishes inside budget is unaffected.
  - `test_real_stdio_call_during_reconnect_backoff_names_reconnecting` — with `_reconnect_backoff` monkeypatched to a long window, a call issued while `_server_state` reads `"reconnecting"` raises `MCPServerUnavailable` (not `MCPTimeout`) naming "is reconnecting" in under 1s, and the server is callable again once it reconnects.
  - `test_real_stdio_oversized_result_truncates_at_max_result_chars` / `test_real_stdio_default_cap_is_8000` — both a configured 100-char cap and the unconfigured 8,000-char default truncate visibly with the exact dropped-count marker.
  - `test_real_stdio_image_content_block_renders_marker` / `test_real_stdio_audio_content_block_renders_marker` / `test_real_stdio_embedded_and_link_blocks_render_markers` — real `ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink` blocks from the wire render as named markers; none of their base64 payloads or Python reprs (`ImageContent(`, `AudioContent(`, `EmbeddedResource(`, `data=`) appear in the output.

## Task Commits

Each task was committed atomically:

1. **Task 1: Opt-in extra tools on the live fixture server** - `b955221` (feat)
2. **Task 2: Real-stdio tests for timeouts, reconnect precedence, the cap and content blocks** - `8ef10dd` (test)

## Files Created/Modified
- `tests/integration/live_mcp_server.py` - five opt-in Phase 13 probe tools behind `AGENT86_LIVE_MCP_EXTRA_TOOLS=1`, plus `IMAGE_BYTES`/`AUDIO_BYTES` module constants
- `tests/integration/test_mcp_client.py` - `_extra_cfg` helper and eight `test_real_stdio_*` integration tests

## Decisions Made
See `key-decisions` in frontmatter: the import-path choice for `IMAGE_BYTES`/`AUDIO_BYTES`, the corrected oversized-cap assertion, and the confirmed `mime_type=` snake_case compatibility with the installed mcp 2.0 SDK's alias generator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's own oversized-cap acceptance text (`out.count("x") == 100`) does not hold against the real marker text**
- **Found during:** Task 2, first `pytest -k real_stdio` run
- **Issue:** `truncate_result`'s marker wording contains "max_result_chars" (twice), each contributing an 'x' from "max" — so the full output's total 'x' count is 103, not 100, even though the visible truncation point is correct.
- **Fix:** Replaced the assertion with `out.split("\n", 1)[0] == "x" * 100`, which pins the actual thing the test means to prove (the pre-marker line is exactly the 100-char cut) without being thrown off by unrelated 'x' characters in the marker's own prose.
- **Files modified:** `tests/integration/test_mcp_client.py`
- **Verification:** `pytest tests/integration/test_mcp_client.py -q -k real_stdio` — 8 passed, re-run 3x with no flakes.
- **Committed in:** `8ef10dd` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — a planning-time miscount in the test's own literal assertion text, test-only, no production code affected)
**Impact on plan:** No scope creep. The fix makes the test assert what it was always meant to prove.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
SC1 (per-server call timeouts), SC2 (the result cap) and SC3 (non-text content block rendering) are now each proven over a real stdio session with the real SDK's content-block types, not only against the fake transport plans 13-02/13-04 used. Plan 13-06 (phase signoff/docs) can cite this evidence directly. No production code (`src/agent86/`) was touched by this plan — `git status --porcelain src/` empty throughout. Full suite green: `pytest -q` 1367 passed (up from 1319), 0 failed; `ruff check .` and `mypy src/agent86` both clean.

---
*Phase: 13-per-server-timeouts-the-result-cap-and-non-text-content*
*Completed: 2026-09-24*

## Self-Check: PASSED

- FOUND: tests/integration/live_mcp_server.py (AGENT86_LIVE_MCP_EXTRA_TOOLS, sleep_for/big_text/tiny_image/tiny_audio/mixed_blocks, IMAGE_BYTES/AUDIO_BYTES)
- FOUND: tests/integration/test_mcp_client.py (_extra_cfg, eight test_real_stdio_* tests)
- FOUND commit b955221 (Task 1)
- FOUND commit 8ef10dd (Task 2)
