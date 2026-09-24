---
phase: 11-resources-and-prompts-become-first-class
plan: 01
subsystem: testing
tags: [mcp, pytest, fixtures, resources, prompts, completions]

# Dependency graph
requires:
  - phase: 10-mcp-conformance-audit
    provides: "the pinned live_mcp_server.py stdio/HTTP/SSE fixture (add/shout/get_env tools) and the _install_fake_transport unit-test helper this plan extends"
provides:
  - "tests/integration/live_mcp_server.py serving three resources (text, binary, template), a two-argument review_code prompt, and a complete_argument completion handler alongside its three existing tools"
  - "tests/unit/test_mcp.py's _FakeCaps/_FakeResourcesCap/_FakePromptsCap/_FakeCompletionsCap duck-typed ServerCapabilities stand-ins, _fake_result(), and an _install_fake_transport extended with capabilities=/responses=/calls= keyword-only params"
  - "11-VALIDATION.md recording Wave 0 as closed"
affects: [11-02-resources-client-support, 11-03-prompts-and-completion-client-support, 11-04-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Duck-typed fake SDK result/capability stand-ins (_FakeCaps family, _fake_result) instead of importing mcp.types directly into unit-test fixtures, so unit tests stay independent of the mcp package's exact class shapes"
    - "Keyword-only, all-defaulted extension parameters on shared test helpers (_install_fake_transport) to guarantee existing call sites stay byte-unchanged"

key-files:
  created: []
  modified:
    - tests/integration/live_mcp_server.py
    - tests/unit/test_mcp.py
    - .planning/phases/11-resources-and-prompts-become-first-class/11-VALIDATION.md

key-decisions:
  - "resources.subscribe stays False on the live fixture (verified live, not just per planning notes) — subscribe/unsubscribe call sites are covered only through the new fake session, never the live transport"
  - "Documented rather than 'fixed': the plan's acceptance criterion expecting >=6 exact-pattern _install_fake_transport(monkeypatch, [ call sites was based on a miscount — the file has 4 total call sites (3 single-line + 1 multi-line), now 4 single-line-matching after this plan's one new test; no call site was reformatted or fabricated to hit the number"

requirements-completed: [MCP-14, MCP-15]

# Metrics
duration: ~15min
completed: 2026-09-24
---

# Phase 11 Plan 01: CI-Safe MCP Resources/Prompts/Completion Test Machinery Summary

**Live MCP fixture gains three resources + a completable prompt, and test_mcp.py gains a duck-typed `ServerCapabilities` fake session — the test infrastructure the rest of Phase 11 is written against.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-09-24T12:39:00Z (approx, first Read)
- **Completed:** 2026-09-24T12:55:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `tests/integration/live_mcp_server.py` now serves three resources (`res://agent86/greeting.txt` text, `res://agent86/blob.bin` binary, `res://agent86/echo/{word}` template), a two-argument `review_code` prompt, and a `complete_argument` completion handler offering `STYLE_COMPLETIONS` for the `style` argument — all reachable over the same CI-safe stdio/HTTP/SSE fixture used since Phase 10, no `npx` or network required.
- `tests/unit/test_mcp.py` gained `_FakeCaps`/`_FakeResourcesCap`/`_FakePromptsCap`/`_FakeCompletionsCap` (duck-typed `mcp.types.ServerCapabilities` stand-ins), `_fake_result()`, and an `_install_fake_transport` extended with keyword-only `capabilities=`/`responses=`/`calls=` params — a unit test can now declare `resources.subscribe = True`, which the live fixture provably cannot reach.
- `11-VALIDATION.md` records both named Wave 0 gaps as closed, naming the exact fixtures that closed them.

## Task Commits

Each task was committed atomically:

1. **Task 1: Give the live MCP fixture resources, a resource template, a prompt and a completion handler** - `8f0c5a1` (test)
2. **Task 2: A capability-aware fake session for unit tests, and a MISSING-marker test list** - `594f263` (test)
3. **Task 3: Mark Wave 0 complete in the phase validation contract** - `ecee6fc` (docs)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified
- `tests/integration/live_mcp_server.py` - Three resources, one prompt, one completion handler added; module docstring updated to name the new surface and the binary-resource rationale
- `tests/unit/test_mcp.py` - `_FakeCaps` family, `_fake_result`, extended `_install_fake_transport`, and one new regression test (`test_fake_transport_without_capabilities_mounts_only_remote_tools`)
- `.planning/phases/11-resources-and-prompts-become-first-class/11-VALIDATION.md` - `wave_0_complete: true`, both Wave 0 checkboxes ticked with landing notes, 11-01 T1/T2 verification-map rows set green

## Decisions Made
- **Observed capability dict** (run live against the exact fixture code, not just re-quoted from planning): `resources=ResourcesCapability(subscribe=False, list_changed=False)`, `prompts=PromptsCapability(list_changed=False)`, `completions=CompletionsCapability()`, `tools=ToolsCapability(list_changed=False)`. `subscribe` came back `False` as the plan predicted — nothing changed, so plan 11-02's subscribe-testing strategy (fake session only) stands unmodified.
- No architectural decisions required; this plan added zero production code by design (`git status --porcelain src/` empty throughout).

## Deviations from Plan

### Documented, Non-Blocking

**1. Plan's "at least 6" call-site acceptance criterion does not match the file's actual state**
- **Found during:** Task 2 verification
- **Issue:** The plan's `<read_first>`/acceptance-criteria text asserts "six existing `_install_fake_transport(monkeypatch, [...])` call sites" that must stay byte-unchanged, and an acceptance criterion expects `grep -c "_install_fake_transport(monkeypatch, \["` to return "at least 6". The actual file (both before and after this plan's edit) has 4 total call sites: 3 in the single-line form the grep pattern matches (lines 424, 432, 507) and 1 in a multi-line form (line 473) that the exact pattern does not match. This plan's new regression test adds a 4th single-line match, for a total of 4 — not 6.
- **Assessment:** This is a planning-time miscount, not a code defect. The substantive requirement the acceptance criterion exists to protect — "every pre-existing call site is byte-unchanged" — is fully met: all 4 existing call sites (`test_manager_passes_its_passthrough_to_the_transport`, `test_build_mcp_reads_env_passthrough_from_config`, `test_read_only_hint_makes_a_tool_non_side_effecting`, `test_close_allows_a_later_restart`) pass unmodified, and the new keyword-only parameters are all defaulted so no call site needed to change.
- **Fix:** None applied — no call site was reformatted or duplicated to inflate the count, since doing so would be cosmetic churn with no test-value. Documented here instead per the deviation rules' scope boundary (out-of-scope/non-blocking discrepancy, not a bug caused by this plan's own changes).
- **Files modified:** None beyond the plan's own edits.
- **Verification:** `grep -c "_install_fake_transport(monkeypatch, \[" tests/unit/test_mcp.py` returns 4 (not 6); `pytest tests/unit/test_mcp.py -q` — 38 passed, 0 failed.
- **Committed in:** `594f263` (part of Task 2 commit; no separate fix commit needed)

---

**Total deviations:** 1 documented, non-blocking (a plan-authoring miscount in an acceptance criterion; no code fix required)
**Impact on plan:** None on functionality or test coverage. All acceptance criteria that measure the actual load-bearing behavior (fake session works, existing calls unchanged, full suite green) pass.

## Issues Encountered
None beyond the documented deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 11-02 (resources client support) can now drive `_install_fake_transport(..., capabilities=_FakeCaps(resources=_FakeResourcesCap(subscribe=True)), responses={...}, calls=[...])` against a fake session for `list_resources`/`list_resource_templates`/`read_resource`/`subscribe_resource`/`unsubscribe_resource`, and against the live fixture's three resources for real-transport coverage.
- Plan 11-03 (prompts/completion client support) can drive `list_prompts`/`get_prompt`/`complete` the same way, plus the live `review_code` prompt and `complete_argument` handler over stdio/HTTP/SSE.
- No blockers. `git status --porcelain src/` was empty throughout this plan, and remains so — no production code changed, matching the plan's explicit scope boundary.

---
*Phase: 11-resources-and-prompts-become-first-class*
*Completed: 2026-09-24*

## Self-Check: PASSED

All claimed files found on disk; all three task commit hashes (`8f0c5a1`, `594f263`, `ecee6fc`) found in git history.
