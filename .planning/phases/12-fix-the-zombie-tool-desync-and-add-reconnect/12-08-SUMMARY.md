---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 08
subsystem: tools
tags: [mcp, tui, observability, reconnect, threading, textual]

# Dependency graph
requires:
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 01
    provides: "_server_state/_disconnect_cause/_reconnect_attempt fields, _MAX_RECONNECT_ATTEMPTS, on_tools_changed hook"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 03
    provides: "the bounded reconnect loop in _serve and its exact note text"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    plan: 06
    provides: "real-stdio reconnect + remote-transport kill-detection evidence the manual re-check in this plan's <verification> depends on"
provides:
  - "MCPManager push-hook note API: add_note_listener/remove_note_listener, notes_since(seq) (a bounded, non-deduped sequenced log), server_status()/server_statuses() as the public non-connected-state accessor"
  - "describe_start_failure() — ExceptionGroup unwrapping to every distinct leaf, plus the stdio child's captured stderr tail with a named fix, instead of the SDK's bare 'unhandled errors in a TaskGroup'"
  - "Harness.on_mcp_note seam + Harness._wire_mcp forwarding every MCPManager note to it, on whichever thread produced it"
  - "TUI: a disconnect/reconnect/gave-up note reaches the transcript live (post_message, not call_from_thread) even while idle"
  - "/tools names every non-connected MCP server with its state; --plain drains new notes before each prompt via _Repl.pending_mcp_notes()"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Push hook over drain-per-turn: MCPManager._add_note fires registered listeners on every call (never deduped), so a disconnect is visible on the TUI transcript while the app is otherwise idle — a per-turn drain could not do that."
    - "App.post_message (not App.call_from_thread) to marshal a cross-thread event onto the Textual UI thread — post_message is thread-safe and non-blocking; call_from_thread blocks the caller and would deadlock against stop_server() (UI thread blocking on the MCP loop) if the loop thread emitted a note during that stop."
    - "A ContextVar (_STDIO_ERRLOG), not a new _open_transport parameter, to hand a per-attempt stderr-capture file handle across an async boundary without changing a call signature that ~7 existing test fakes replace verbatim."
    - "State transitions that a cross-thread poller can observe (_server_state) are set atomically with the dict pops that signal 'session gone' (_sessions/_server_tools), in the same finally block — not left to a later, separate function call on the same thread, however 'synchronous' that call looks on paper."

key-files:
  created:
    - tests/tui/test_mcp_notes.py
    - tests/integration/test_mcp_note_surfaces.py
  modified:
    - src/agent86/tools/mcp_client.py
    - src/agent86/tui/screens/mcp_test.py
    - src/agent86/orchestration/loop.py
    - src/agent86/tui/messages.py
    - src/agent86/tui/app.py
    - src/agent86/tui/commands.py
    - src/agent86/ui/repl.py
    - tests/unit/test_mcp.py
    - tests/integration/test_mcp_client.py

key-decisions:
  - "stdio child stderr now goes to a per-connection temp file (tempfile.NamedTemporaryFile), never the terminal — Windows' create_windows_process hands errlog straight to anyio.open_process(stderr=...), which needs a real fileno(), so a pipe or StringIO does not work. The file is deleted (best-effort; a leftover file on Windows is acceptable, a raise is not) in _serve_once's finally on every exit, stdio or not."
  - "Found and fixed a genuine (narrow) production race this plan's own stderr-capture I/O exposed: _serve_once now sets _server_state/_disconnect_cause synchronously, atomically with popping _sessions/_server_tools, in its own finally block — not left to _serve's later _on_drop call. The capture's real (GIL-releasing) file I/O was otherwise enough for another thread polling _sessions to observe 'session gone' next to a still-unset _server_state (reproduced as a ~15-20% flake in tests/unit/test_mcp.py::test_named_server_error_after_death before the fix; 20/20 clean afterward)."

requirements-completed: [MCP-26, MCP-23]

# Metrics
duration: ~75min
completed: 2026-09-24
---

# Phase 12 Plan 08: Gap closure — live MCP notes and readable start failures Summary

**A mid-session MCP disconnect/reconnect now reaches the TUI transcript, `/tools`, and the plain loop on its own — even while idle — via a push-hook note API (`MCPManager.add_note_listener`), and a stdio start failure names the real leaf cause plus the child's own stderr tail instead of the SDK's bare `unhandled errors in a TaskGroup`.**

## Performance

- **Duration:** ~75 min
- **Tasks:** 3 (Tasks 1+2 landed in one commit; Task 3 in a second)
- **Files modified:** 9 (2 new test files)

## Accomplishments

- **Gap 1 closed — notes are pushed live, not just rendered once at mount.** `MCPManager` gained a lock-guarded, never-raising push-hook API: `add_note_listener`/`remove_note_listener`, a bounded (500-event) sequenced log behind `notes_since(seq)` that is deliberately **not** deduped (a repeat "reconnecting (attempt 1 of 5)" is real news, not noise — `notes`/`note` keep their existing dedup unchanged), and `server_status()`/`server_statuses()` as the one public accessor for "reconnecting (attempt N of M): cause" / "disconnected: cause" / "not connected", so no caller needs the private `_server_state`/`_disconnect_cause`/`_reconnect_attempt` dicts. `Harness.on_mcp_note` is the seam an interactive surface sets; `Harness._wire_mcp` (already called at construction and inside `ensure_mcp()`) additionally does `manager.add_note_listener(self._forward_mcp_note)`, which relays to `on_mcp_note` on whichever thread produced the note, never raising. `run`/`run --json` never set `on_mcp_note`, so their output carries no new keys.
- **The TUI renders it live.** `Agent86App._post_mcp_note` marshals with `self.post_message(McpNote(text))` — deliberately **not** `call_from_thread`, whose blocking-until-the-UI-runs-it contract would deadlock against `stop_server()` (called on the UI thread, itself blocking on `.result()` for the MCP loop) if the loop thread emitted a note during that stop. `on_mcp_note` mirrors `on_turn_notice`: finishes any reply in progress, writes `[yellow]mcp: {escaped text}[/yellow]`, scrolls to end. Wired before the `startup_notes` loop in `on_mount` (a note racing mount can duplicate, never vanish) and detached in `on_unmount` by bound-method equality.
- **`/tools` and `--plain` get the same information.** `_tools_render` appends one `mcp {name}: {status}` line per non-connected server from `server_statuses()`, through the public accessor only — `grep` confirms zero references to the private state dicts outside `mcp_client.py` itself. `_Repl.pending_mcp_notes()` is the plain loop's equivalent of the push hook (there is no event loop to push into): it polls `notes_since()` from a stored `(id(mcp), seq)` cursor, marked *before* `startup_notes` runs so a note racing startup can duplicate but never disappear, and resets automatically when `harness.mcp` is swapped for a new manager. `plain_loop()` drains it before every `agent86> ` prompt.
- **Gap 2 closed — a stdio start failure names the real cause.** `describe_start_failure()` unwraps a (possibly nested) `BaseExceptionGroup` to every distinct leaf (order-preserving, duplicates collapsed, joined by `"; "`) instead of the SDK's bare `unhandled errors in a TaskGroup (1 sub-exception)`; a plain exception keeps `start()`'s pre-existing `str(exc)` format. A new `_StderrCapture` writes a stdio child's stderr to a per-connection temp file — Windows' `create_windows_process` hands the SDK's `errlog` straight to `anyio.open_process(stderr=...)`, which needs a real `fileno()`, so neither a pipe nor a `StringIO` works — threaded through a module-level `contextvars.ContextVar` (`_STDIO_ERRLOG`) rather than a new `_open_transport` parameter, because roughly seven existing test fakes across three files replace `_open_transport` with a bare `(cfg, env_passthrough=None)` signature that the real call site must keep matching byte-for-byte. A connect-time failure's note gets the full 20-line tail (redacted for secrets/PII via `guardrails.scanners.redact`) plus, when the SDK's own `CONNECTION_CLOSED` fired, a named hint ("Check this server's command/args..."); a mid-session drop's note gets a short 3-line tail appended to the *note* text only — never to `_disconnect_cause`, which stays the short, stable, model-facing string. `MCPTestModal` (the `/config mcp` pre-save connection test) reuses `describe_start_failure` for identical text in both places a start failure is shown.
- **A found-and-fixed production race, not just a gap closure.** While stabilizing the new stderr-capture I/O, `tests/unit/test_mcp.py::test_named_server_error_after_death` (a pre-existing, unmodified test) started failing intermittently (~15-20% of runs) with `"MCP server 'srv' is not connected."` instead of the expected "disconnected" text. Root cause: `_serve_once`'s `finally` block already popped `_sessions`/`_server_tools` (the signal a cross-thread poller uses to know a session is gone) *before* `_serve`'s later, separate `_on_drop()` call set `_server_state`/`_disconnect_cause` — a narrow but real window that existed since plan 12-01/12-03. This plan's own `capture.tail()`/`capture.close()` calls in that same `finally` block are real (GIL-releasing) file syscalls, which was enough to let the test's polling thread reliably land inside that window. Fixed at the root: `_server_state[name]`/`_disconnect_cause[name]` are now set **synchronously, atomically with the two pops**, in `_serve_once`'s own `finally`, before any stderr-capture I/O runs — `_on_drop` (called later, back in `_serve`) still owns the note text and `on_tools_changed` emission, and its re-set of the same two fields is harmless. Verified: 20/20 clean runs of the previously-flaky test after the fix, plus 3 consecutive full-suite runs (`pytest -q`) all green.

## Task Commits

1. **Tasks 1+2: MCPManager note listeners/sequenced log/server-status accessors + describe_start_failure/stderr capture** — `a2ad249` (feat) — landed together; both touch the same handful of functions in `mcp_client.py` and a clean post-hoc split would have been artificial (matching plan 12-01's own precedent for combining tasks when splitting isn't practical).
2. **Task 3: Harness forwarder, TUI push via post_message, /tools state, plain-loop drain** — `e1d90bc` (feat)

**Plan metadata:** (this commit) `docs(12-08): complete gap closure plan`

## Files Created/Modified

- `src/agent86/tools/mcp_client.py` — `add_note_listener`/`remove_note_listener`/`note_seq`/`notes_since`/`server_status`/`server_statuses` on `MCPManager`; `describe_start_failure`/`_leaf_exceptions`/`_StderrCapture`/`_STDERR_NOTE_PREFIX`/`_STDIO_ERRLOG`; `_serve_once`/`_on_drop`/`_SessionEnd` carry `stderr_tail`; `_open_transport`'s stdio branch reads the ContextVar; `start()` uses `describe_start_failure`; the `_server_state` race fix in `_serve_once`'s `finally`.
- `src/agent86/tui/screens/mcp_test.py` — `MCPTestModal._run_test._call` uses `describe_start_failure(exc)` instead of `str(exc) or exc.__class__.__name__`.
- `src/agent86/orchestration/loop.py` — `Harness.on_mcp_note`, `Harness._forward_mcp_note`, `_wire_mcp` additionally calls `manager.add_note_listener(...)`.
- `src/agent86/tui/messages.py` — new `McpNote(Message)`.
- `src/agent86/tui/app.py` — `_post_mcp_note`, `on_mcp_note`, wiring in `on_mount`/detach in `on_unmount`.
- `src/agent86/tui/commands.py` — `_tools_render` appends `mcp {name}: {status}` lines from `server_statuses()`.
- `src/agent86/ui/repl.py` — `_mcp_note_mark`, `pending_mcp_notes`, cursor init before `startup_notes`, drained at the top of `plain_loop`'s `while True:`.
- `tests/unit/test_mcp.py` — 11 new tests (5 note-listener/status, 6 describe_start_failure/_StderrCapture), append-only (`git diff` confirmed no existing line changed).
- `tests/integration/test_mcp_client.py` — `test_stdio_start_failure_note_carries_child_stderr` (real subprocess, real stderr), append-only.
- `tests/tui/test_mcp_notes.py` (new) — cross-thread note reaches the transcript twice for a repeated note; listener detached on unmount.
- `tests/integration/test_mcp_note_surfaces.py` (new) — `/tools` non-connected state, `/tools` unchanged without MCP, `pending_mcp_notes` skip-startup/repeat/reset-on-swap, plain-loop pre-prompt drain.

## Decisions Made

- Push hook (`add_note_listener`, fired unconditionally on every `_add_note`) over a per-turn drain — a per-turn drain cannot show a disconnect while the app is idle between turns, which is exactly what this gap closure requires.
- `App.post_message`, not `App.call_from_thread` — see the objective's own reasoning, reconfirmed in code: `call_from_thread` blocks and would deadlock against `stop_server()`.
- `_STDIO_ERRLOG` as a `ContextVar`, not a new `_open_transport` parameter — preserves every existing test fake's `(cfg, env_passthrough=None)` signature unchanged.
- The stderr capture file is deleted on every disconnect (best-effort on Windows — a leftover temp file is acceptable, a raise is not) rather than kept around; nothing currently reads it after `_serve_once` returns except the two `tail()` calls already inside that function.
- `_disconnect_cause` (the model-facing string via `_unavailable_error`) never carries the stderr tail — only the human-facing *note* text does, keeping the model's error message short and stable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a genuine cross-thread state-visibility race exposed by this plan's own stderr-capture I/O**
- **Found during:** Task 2, stabilizing the new tests (`tests/unit/test_mcp.py::test_named_server_error_after_death`, a pre-existing, unmodified test, failed intermittently — ~15-20% of runs).
- **Issue:** `_serve_once`'s `finally` block popped `_sessions`/`_server_tools` before `_serve`'s later, separate `_on_drop()` call set `_server_state`/`_disconnect_cause`. This narrow window existed since plan 12-01/12-03, but this plan's own `capture.tail()`/`capture.close()` calls in the same `finally` block perform real (GIL-releasing) file syscalls, which reliably widened it enough for a cross-thread poller to observe "session gone, but not yet marked why."
- **Fix:** `_server_state[name]`/`_disconnect_cause[name]` are now set synchronously, atomically with the `_sessions`/`_server_tools` pops, inside `_serve_once`'s own `finally`, before any capture I/O runs. `_on_drop`'s later re-set of the same fields is now redundant but harmless.
- **Files modified:** `src/agent86/tools/mcp_client.py`
- **Verification:** 20/20 consecutive clean runs of the previously-flaky test; 3 consecutive full-suite (`pytest -q`, 1319 passed) runs all green.
- **Commit:** `a2ad249`

---

**Total deviations:** 1 auto-fixed (1 bug, Rule 1)
**Impact on plan:** The fix is a correctness improvement squarely inside this plan's own file (`mcp_client.py`) and its own feature area (the `_server_state` surface Task 1 just made public via `server_status`/`server_statuses`) — no scope creep, no architectural change.

## Issues Encountered

- The unit-test suite's `test_build_mcp_none_without_servers` (and by extension the whole `pytest tests/unit/test_mcp.py` run) reads the machine's real `~/.agent86/config.toml` via `load_config()` with no test isolation — on this machine that file has a real, `enabled` MCP server (`live`, from the user's separately-running TUI session per this plan's execution rules), which made that one pre-existing test fail when run against the real `HOME`/`USERPROFILE`. Not a code defect and out of this plan's scope to fix (no `conftest.py`/config-isolation file is in this plan's `files_modified` list); every test run in this plan's own verification was instead made against an isolated `USERPROFILE`/`HOME` pointed at an empty temp directory, which is also how CI runs (a fresh runner has no `~/.agent86`).

## Known Stubs

None. Every surface this plan touches (TUI transcript, `/tools`, `--plain`) is wired to live data (`MCPManager`'s real state), not a placeholder.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Gaps 1 and 2 from 12-07 Task 3's human verification are both closed. **12-07 should now resume its own Task 3 manual re-check** (kill the `live` stdio server's PID and watch the disconnect/reconnect notes appear live in the TUI without typing anything; check `/tools` while it is down; break a server's `command` and confirm the start-failure note quotes the child's stderr) — this plan's own automated verification (`tests/integration/test_mcp_client.py::test_stdio_start_failure_note_carries_child_stderr`, real subprocess, real captured stderr) already proves the mechanism end to end, but the interactive TUI walkthrough is 12-07's to close out.
- **Suggested CHANGELOG line for 12-07 to fold in** (CHANGELOG.md is 12-07's file — not edited here):
  > MCP disconnect/reconnect notes now appear live in the TUI transcript and `--plain` (not only at
  > startup), `/tools` lists every non-connected MCP server with its state, and a stdio server's
  > start failure now names the real cause plus its own stderr instead of a bare "unhandled errors
  > in a TaskGroup".
- Full suite green: `pytest -q` — 1319 passed (up from 1300), 0 failed, across 2 consecutive full runs; `mypy src/agent86` clean (93 source files); `ruff check .` clean; `ruff format --check` on this plan's own new/changed lines clean (pre-existing repo-wide debt, logged in `deferred-items.md` by plan 10-05, untouched).
- No blockers. `git status --porcelain` outside this plan's declared `files_modified` (plus the two new test files) stayed empty throughout.

## Self-Check: PASSED

- FOUND: `src/agent86/tools/mcp_client.py`
- FOUND: `src/agent86/tui/screens/mcp_test.py`
- FOUND: `src/agent86/orchestration/loop.py`
- FOUND: `src/agent86/tui/messages.py`
- FOUND: `src/agent86/tui/app.py`
- FOUND: `src/agent86/tui/commands.py`
- FOUND: `src/agent86/ui/repl.py`
- FOUND: `tests/unit/test_mcp.py`
- FOUND: `tests/integration/test_mcp_client.py`
- FOUND: `tests/tui/test_mcp_notes.py`
- FOUND: `tests/integration/test_mcp_note_surfaces.py`
- FOUND commit `a2ad249` (feat(12-08): note listeners, sequenced note log, server-status accessors, and readable start failures (Tasks 1+2))
- FOUND commit `e1d90bc` (feat(12-08): surface MCP notes live - Harness forwarder, TUI push, /tools state, plain-loop drain (Task 3))

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
