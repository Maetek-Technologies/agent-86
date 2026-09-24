---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 07
subsystem: tools
tags: [mcp, docs, tui, reconnect, validation, changelog]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 04
    provides: "harness registry sync (mcp_tools_changed) the docs describe"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 06
    provides: "real-stdio reconnect + remote-transport kill-detection evidence this plan's human checkpoint verifies"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 08
    provides: "live MCP notes (push-hook listener), /tools per-server state, and readable start failures — the gap closure this plan's own Task 3 checkpoint required before it could be honestly approved"
provides:
  - "CHANGELOG/README/ARCHITECTURE/mcp-conformance-matrix entries stating what Phase 12 shipped (end-of-stream death detection, named-server errors, bounded reconnect, live MCP notes, readable start failures)"
  - "12-VALIDATION.md signed off with every row mapped to a real task ID and a real passing command, including plan 12-08's five gap-closure rows"
  - "Human confirmation, in the real TUI, of a real MCP server dying and reconnecting — including the disconnect/reconnecting/reconnected notes appearing live"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-07-SUMMARY.md
  modified:
    - CHANGELOG.md
    - README.md
    - docs/ARCHITECTURE.md
    - docs/mcp-conformance-matrix.md
    - .planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-VALIDATION.md

key-decisions:
  - "Task 3's human verification surfaced a real planning gap (the TUI could only render MCP notes at mount, not live) rather than a code bug in the reconnect machinery itself — closed by a new plan (12-08), not an inline fix inside this checkpoint, because it touched five files well outside 12-07's own files_modified list."
  - "12-08's shipped behaviour (live notes, per-server /tools state, readable start failures, stdio stderr moved to a per-connection temp file) is folded into this plan's own docs (CHANGELOG, README, ARCHITECTURE §7) rather than left for a later plan, since 12-07 is the phase's docs owner and the phase gate should describe the phase as it actually behaves today."

requirements-completed: [MCP-26, MCP-23]

# Metrics
duration: ~35min active (Tasks 1-2: ~5min; Task 3 resume + gap-closure docs fold-in: ~30min); elapsed wall-clock from first commit to phase close ~5h39m, including a ~75min gap-closure plan (12-08) and three rounds of human verification in between
completed: 2026-09-24
---

# Phase 12 Plan 07: Phase signoff — docs, validation sign-off, and human-verified reconnect Summary

**Phase 12 (zombie-tool desync + bounded reconnect) is documented, validated, and human-confirmed live in the TUI — after a real gap-closure detour (plan 12-08) that made the reconnect's own notes visible outside a fresh mount.**

## Performance

- **Duration:** ~35 min active work by this plan across two sessions (see metrics above for the full elapsed timeline, which includes plan 12-08's own ~75 min gap-closure execution and the user's three manual verification passes)
- **Tasks:** 3 (Task 1 and Task 2 auto; Task 3 a blocking human-verify checkpoint)
- **Files modified:** 5 (CHANGELOG.md, README.md, docs/ARCHITECTURE.md, docs/mcp-conformance-matrix.md, 12-VALIDATION.md)

## Accomplishments

- **Task 1 — documented what Phase 12 shipped.** CHANGELOG.md gained a `Fixed` bullet (MCP-26: end-of-stream death detection via `_EOFWatchStream`, tools unregistered from both `MCPManager` and `Harness.registry`, named-server errors) and an `Added` bullet (MCP-23: bounded reconnect, up to 5 attempts with exponential backoff and jitter, fresh tool re-listing, `/tools` MCP notes). README's `## Resilience` section gained a "MCP servers recover too" paragraph; `docs/ARCHITECTURE.md` §7 item 2 gained two sentences on death detection and bounded reconnect (sections 1-6/8-15 untouched); `docs/mcp-conformance-matrix.md`'s two "Not rated here" bullets (reconnect, zombie-tool desync) were marked closed by Phase 12.
- **Task 2 — 12-VALIDATION.md signed off against real results.** Every `12-xx`/`TBD` placeholder in the Per-Task Verification Map was replaced with a real task ID and a real passing `pytest` command/count; all three Wave 0 checkboxes and all six Validation Sign-Off checkboxes ticked; frontmatter set to `status: complete`, `nyquist_compliant: true`, `wave_0_complete: true`, `Approval: approved 2026-09-24`. Phase gate at that point: `pytest -q` 1300 passed, `mypy`/`ruff` clean.
- **Task 3 — the human checkpoint, closed after a real gap-closure detour.** See "Task 3 verification history" below for the full, verbatim account the user asked to have recorded.
- **This session — folded plan 12-08's shipped behaviour into the phase's docs.** CHANGELOG.md gained a new `Added` bullet (live MCP notes in the TUI transcript and `--plain`, per-server `/tools` state, readable start failures naming the real cause plus the child's own stderr, and the stdio-stderr-now-goes-to-a-temp-file behaviour change called out explicitly); README's Resilience paragraph was extended with the same three behaviours; `docs/ARCHITECTURE.md` §7 item 2 gained two more sentences (push-hook note listener; readable start-failure text) — still only §7 touched. `12-VALIDATION.md` gained five new Per-Task Verification Map rows for plan 12-08 (task IDs `12-08-01+02`, `12-08-03`) with real `pytest -k` commands re-run and counted in this session, plus a note recording 12-08's own full-suite result (1319 passed). `pytest tests/unit/test_docs_consistency.py -q` — 7 passed — confirms the matrix/ARCHITECTURE shape these edits must keep satisfying is unbroken.
- **Phase gate re-run clean after the docs fold-in.** `pytest -q` (isolated `HOME`/`USERPROFILE`) — 1319 passed, 0 failed; `mypy src/agent86` — clean (93 source files); `ruff check .` — clean.

## Task 3 verification history (recorded verbatim per user instruction)

1. **First attempt.** The user's config used `command = "python"`, which outside the project's venv resolves to a system Python 3.12 with no `mcp` package installed — the server died on import, and agent86 showed an opaque `failed to start: unhandled errors in a TaskGroup (1 sub-exception)`. Fixed by pointing `command` at the venv interpreter (a user config fix, not an agent86 code change).
2. **Second attempt.** Reconnect actually worked — the orchestrator confirmed it live: killed PID 39700, a new PID 28380 was spawned by the agent86 process within 1.75s — but the user saw no disconnect/reconnect message, because the TUI only rendered MCP notes once, at mount. The original Task 3 `<how-to-verify>` steps promised notes the TUI could not, at the time, actually show — a genuine planning gap in this plan's own checkpoint, not a bug in the reconnect logic itself.
3. **Gap closure.** Plan 12-08 (`394c99b`, `80020eb`, `a2ad249`, `e1d90bc`, `7e3ec01`) added live MCP notes to the TUI transcript and `--plain` (a push-hook `add_note_listener` API on `MCPManager`, marshaled via `App.post_message` — not `call_from_thread`, to avoid deadlocking against `stop_server()`), per-server state in `/tools` (`server_status()`/`server_statuses()`), and readable start failures (`describe_start_failure()` unwrapping `BaseExceptionGroup`s to their real leaf causes, plus the stdio child's own captured stderr tail). It also fixed a genuine pre-existing race in `_serve_once` where `_server_state`/`_disconnect_cause` were set after (not atomically with) the `_sessions`/`_server_tools` pops a cross-thread poller relies on — reproduced as a ~15-20% flake in `test_named_server_error_after_death`, fixed at the root, 20/20 clean reruns afterward. See `12-08-SUMMARY.md` for the full breakdown.
4. **Third attempt, after restarting agent86.** **Approved.** The user watched a live disconnect → reconnecting → reconnected sequence of notes appear in the TUI transcript without typing anything, and confirmed a tool call works again after reconnect.

## Task Commits

1. **Task 1: Document the fix and the reconnect** — `0248ee2` (docs)
2. **Task 2: Sign off 12-VALIDATION.md and run the phase gate** — `29efe4b` (docs)
3. **Task 3: Watch a real MCP server die and come back in the TUI** — no file changes of its own (manual verification only); the gap it surfaced was closed by a separate plan, 12-08 (`394c99b`, `80020eb`, `a2ad249`, `e1d90bc`, `7e3ec01`); this session's fold-in of 12-08's shipped behaviour into CHANGELOG/README/ARCHITECTURE/12-VALIDATION.md — `0df3d05` (docs)

**Plan metadata:** (this commit) `docs(12-07): complete phase signoff for the zombie-tool desync and reconnect plan`

## Files Created/Modified

- `CHANGELOG.md` — Fixed/Added entries for MCP-26/MCP-23 (Task 1); a further Added bullet folding in plan 12-08's live-notes/`/tools`-state/readable-start-failure/stderr-temp-file behaviour (this session)
- `README.md` — "MCP servers recover too" Resilience paragraph (Task 1), extended with 12-08's behaviour (this session)
- `docs/ARCHITECTURE.md` — §7 item 2, two sentences on death detection/reconnect (Task 1), two more on live notes/readable start failures (this session); no other section touched either time
- `docs/mcp-conformance-matrix.md` — two "Not rated here" bullets marked closed by Phase 12 (Task 1)
- `.planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-VALIDATION.md` — Per-Task Verification Map filled from real results and signed off (Task 2); five new rows for plan 12-08's gap closure, with commands re-run and counted in this session

## Decisions Made

- The Task 3 gap (notes not visible live) was routed to a new plan (12-08) rather than fixed inline inside this checkpoint — it touched `mcp_client.py`, `loop.py`, `tui/app.py`, `tui/commands.py`, `tui/messages.py` and `ui/repl.py`, none of which are in this plan's `files_modified`, and the fix was substantial enough (a new push-hook API, a new cross-thread marshaling seam, a new stderr-capture mechanism) to warrant its own plan, task list, and test suite rather than an ad hoc checkpoint fix.
- 12-08's shipped behaviour is folded into this plan's own docs (rather than deferred to a later phase) because 12-07 is the phase's docs owner and CHANGELOG/README/ARCHITECTURE should describe the phase as it actually behaves at phase close, not as it behaved before the gap closure.

## Deviations from Plan

### Auto-fixed Issues

None — no code was changed by this plan; all production-code fixes (the note-listener API, `describe_start_failure`, the `_serve_once` race fix) belong to plan 12-08 and are documented in `12-08-SUMMARY.md`.

### Documented, not auto-fixed

**1. [Gap surfaced by human verification, closed via a new plan] Task 3's original `<how-to-verify>` steps assumed the TUI could show MCP notes live; it could not.**
- **Found during:** Task 3, first checkpoint pass.
- **Issue:** `MCPManager` already recorded disconnect/reconnect notes, but the TUI rendered `manager.notes` only once, at mount — a note that arrived after mount (exactly the scenario Task 3 asks the user to watch for) was invisible until the next restart.
- **Fix:** Plan 12-08 added a push-hook listener API (`add_note_listener`/`notes_since`), a `Harness.on_mcp_note` forwarding seam, and TUI/`/tools`/`--plain` consumers of it.
- **Files modified:** `src/agent86/tools/mcp_client.py`, `src/agent86/orchestration/loop.py`, `src/agent86/tui/messages.py`, `src/agent86/tui/app.py`, `src/agent86/tui/commands.py`, `src/agent86/ui/repl.py` (all in plan 12-08, not this plan).
- **Verification:** Third human-verification pass (this plan's own Task 3) — approved.
- **Commits:** `394c99b`, `80020eb`, `a2ad249`, `e1d90bc`, `7e3ec01` (plan 12-08).

**2. [User environment issue, not a code defect] `command = "python"` in the user's MCP server config resolved to a system interpreter without `mcp` installed.**
- **Found during:** Task 3, first checkpoint pass.
- **Issue:** Outside the project's venv, `python` on PATH was a system Python 3.12 lacking the `mcp` package; the stdio server died on import.
- **Fix:** The user pointed `command` at the venv interpreter. No agent86 code change — this is what plan 12-08's `describe_start_failure()` now makes legible instead of a bare TaskGroup wrapper.

---

**Total deviations:** 2 documented (1 gap closed via a new plan, 1 user config issue) — no code auto-fixed inside this plan.
**Impact on plan:** Both are now resolved: the gap closure shipped and was itself human-verified; the config issue was a one-time local fix with no lasting effect on agent86's code or docs beyond making the failure mode readable (plan 12-08).

## Issues Encountered

None beyond the Task 3 gap documented above, which is why Task 3 took three verification passes instead of one.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required. (The user's own local MCP server config needed a `command` path fix during verification, documented above; this is user-side config, not an agent86 setup step.)

## Next Phase Readiness

- Phase 12 success criteria 1-3 are documented, test-backed, and human-confirmed live in the TUI.
- `pytest -q` (isolated HOME/USERPROFILE): 1319 passed, 0 failed. `mypy src/agent86`: clean. `ruff check .`: clean.
- `12-VALIDATION.md`: `status: complete`, `nyquist_compliant: true`, every row (including plan 12-08's five gap-closure rows) mapped to a real task ID and a real passing command.
- No blockers for closing out Phase 12.

## Self-Check: PASSED

- FOUND: `CHANGELOG.md`
- FOUND: `README.md`
- FOUND: `docs/ARCHITECTURE.md`
- FOUND: `docs/mcp-conformance-matrix.md`
- FOUND: `.planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-VALIDATION.md`
- FOUND commit `0248ee2` (docs(12-07): document zombie-tool fix and bounded reconnect)
- FOUND commit `29efe4b` (docs(12-07): sign off 12-VALIDATION.md against real phase-gate results)
- FOUND commit `0df3d05` (docs(12-07): fold 12-08 gap closure into CHANGELOG, README, ARCHITECTURE, and 12-VALIDATION.md)

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
