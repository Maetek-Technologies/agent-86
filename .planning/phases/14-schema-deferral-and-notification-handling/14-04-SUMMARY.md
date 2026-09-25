---
phase: 14-schema-deferral-and-notification-handling
plan: 04
subsystem: tools
tags: [mcp, notifications, list_changed, progress, logging, resource-updated, adr-0003]

# Dependency graph
requires:
  - phase: 14-schema-deferral-and-notification-handling
    provides: "plan 14-01's _DyingTransport.notify()/notify_nowait() (deliver a real mcp.types
      notification object to the installed message_handler without a live server) and
      list_delay/list_error on list_tools() for the race tests; plan 14-03's
      MCPTool._definition (description, schema, read_only) tuple this plan's diff compares
      against to decide whether an unchanged tool's object survives a re-list"
  - phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
    provides: "MCPManager.on_tools_changed/_emit_tools_changed -> Harness._on_mcp_tools_changed,
      the registry-sync plumbing this plan's second trigger (list_changed) reuses verbatim"
provides:
  - "MCPManager._on_notification: the message_handler router for every ServerNotification MCP-24
    scopes in (tools/resources/prompts list_changed, progress, logging, resource updates) and
    scopes out (cancelled, never delivered by the SDK)"
  - "MCPManager._refetch_tools: a guarded, identity-preserving re-list of one server's tools after
    a list_changed notification, serialized per-server and immune to a stop_server()/death race"
  - "MCPManager.last_progress(name) / _add_note(persistent=False): generic progress observation
    (CAP-PROGRESS) and the live-only note channel progress/resource-updates/resource-prompt-list-
    changed all share, distinct from the startup-rendered notes list"
affects: [14-05-server-instructions-in-the-prompt, 14-06-phase-signoff]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A list_changed re-fetch diffs by (description, schema, read_only) equality against the
      MCPTool._definition tuple 14-03 added, not by name alone — an unchanged tool keeps its
      object (and its ADR 0003 materialised flag) across a re-list; a redefined one is replaced"
    - "A per-server asyncio.Lock (created lazily on the loop thread) serializes back-to-back
      notifications for one server; a write only lands if self._sessions.get(name) is session,
      so a notification racing stop_server()/a transport death can never resurrect a torn-down
      server — the same 'write only while still the live session' discipline Phase 12 established
      for _serve_once's own teardown"
    - "_add_note(message, persistent=False) is the live-only note channel: event log + listener
      fan-out (notes_since/live surfaces), never the startup-rendered, deduped `notes` list —
      progress and resource/prompt list-changed notes use it so a long session's transcript isn't
      dominated by high-frequency, non-actionable events"
    - "A no-op progress_callback is passed to call_tool purely to make the SDK mint a progress
      token; observation happens generically in the same message_handler that already exists,
      not via per-call correlation — CAP-PROGRESS is scoped to 'observed, not attributed to a
      specific call', matching 14-RESEARCH.md's own scoping recommendation"

key-files:
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py

key-decisions:
  - "list_changed scope (orchestrator ruling 4): all three siblings (tools/resources/prompts)
    trigger the SAME re-fetch, which re-runs session.list_tools() ONLY — _capability_tools() is
    never re-run, since server capabilities are fixed for a session's lifetime. Resources/prompts
    siblings therefore mutate the registry only if the server's own tool list happens to have
    changed too; their visible effect is a live note, since the synthetic list_resources/
    list_prompts tools already fetch live on every call."
  - "Identity preservation: a re-listed tool whose (description, schema, read_only) equals the
    existing MCPTool._definition keeps the SAME object (never removed-then-re-added, never
    re-deferred); a tool with the same name but a changed definition is replaced."
  - "Race guard: the refetch awaits list_tools() and writes only if self._sessions.get(name) is
    session (the exact session the handler's _serve_once owns); otherwise it returns silently —
    the death/stop path already owns cleanup. Per-server asyncio.Lock serializes back-to-back
    refetches so they never interleave."
  - "Progress (orchestrator ruling 3, corrected by 14-EVIDENCE.md fact 3): a spec-compliant server
    sends NO progress unless the request carries a progress token, so call_tool passes a
    module-level no-op _request_progress purely so the SDK mints one. Observation is generic in
    _on_notification: latest (progress, total, message) per server kept for last_progress(name);
    a live-only note fires at most once per _PROGRESS_NOTE_INTERVAL_S = 2.0 per server, always on
    completion. Not attributed to a specific tool call. _on_session (resources/prompts/completion
    calls) does NOT request progress."
  - "Logging: LoggingMessageNotification -> logger.log(level, ...) on
    agent86.tools.mcp_client's logger, levels mapped from the eight RFC 5424 names; no note
    (transcript noise), no logging/setLevel request."
  - "Resource updates: ResourceUpdatedNotification -> live note naming the URI and the
    read_resource tool — the half of CAP-RESOURCE-SUBSCRIBE Phase 11 left to MCP-24."
  - "Cancellation: nothing. CancelledNotification never reaches message_handler (the SDK's own
    dispatcher consumes it first) — no branch was added for it, matching the plan's explicit
    ruling rather than the roadmap's unfounded 'may close incidentally' hope."

patterns-established:
  - "Pattern: when a notification handler must never raise into the SDK's dispatcher, wrap the
    router call itself in a try/except at the _on_message level (a second backstop) even though
    every branch inside the router is already individually careful — belt and suspenders for a
    callback the SDK will not tolerate an exception from."

requirements-completed: [MCP-24]

# Metrics
duration: ~25min
completed: 2026-09-25
---

# Phase 14 Plan 04: Route list_changed, progress, logging, and resource updates Summary

**MCPManager._on_notification routes every in-scope server notification (tools/resources/prompts list_changed into a guarded, identity-preserving re-fetch reusing Phase 12's tool-sync plumbing; progress into a throttled live note plus `last_progress()`; logging into the Python logger; resource updates into a live note) while a session-identity guard and a per-server lock keep a list_changed re-fetch from ever racing stop_server()/a transport death.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-25T03:05:00Z (approx.)
- **Completed:** 2026-09-25T03:30:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 2 (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`)

## Accomplishments

- `_serve_once`'s `_on_message` no longer silently drops every `ServerNotification`: it now
  routes anything that isn't a transport `Exception` item into a new `_on_notification(name,
  session, message)`, guarded by `if not this_session: return` (a notification delivered before
  the session is marked live is ignored — the connect path lists tools right after) and a
  `try/except` backstop so a routing bug can never escape into the SDK's dispatcher.
- `ToolListChangedNotification` triggers `_refetch_tools`, which re-runs `session.list_tools()`
  only (capabilities never change mid-session per spec, so the existing synthetic capability
  tools are reused as-is), diffs the fresh list against the current `MCPTool` set by
  `(description, schema, read_only)` equality (14-03's `_definition` tuple), and calls Phase 12's
  existing `_emit_tools_changed(name, removed, added)` with the real diff — an unchanged tool
  keeps its object and its ADR 0003 `materialized` flag; a redefined tool is replaced; a no-op
  re-list produces zero events and zero registry churn.
- The refetch is race-proof by construction: it writes `self._server_tools[name]` only while
  `self._sessions.get(name) is session` (the exact session this notification's `_serve_once` task
  owns), so a `list_changed` notification racing `stop_server()` or a transport death can never
  resurrect a torn-down server; a per-server `asyncio.Lock` (created lazily on the loop thread)
  serializes back-to-back notifications so they never interleave. A `list_tools()` failure during
  the refetch degrades to a note naming the reason, never a raise.
- `ResourceListChangedNotification`/`PromptListChangedNotification` fire a live-only note (`"its
  resource/prompt list changed."`) and run the same tools re-fetch, per the plan's scope ruling
  that only `tools/list` needs re-running — the synthetic `list_resources`/`list_prompts` tools
  already fetch live on every call, so these two notifications typically produce no registry
  mutation at all.
- `_add_note` gained `persistent: bool = True`; `persistent=False` still reaches every listener
  and `notes_since`, but never the startup-rendered, deduped `notes` list — used for progress,
  resource updates, and the resource/prompt list-changed notes, none of which should accumulate
  forever in a long-running session's rendered note history.
- `call_tool` now passes a module-level no-op `_request_progress` as `progress_callback` purely
  so the SDK mints a progress token (a spec-compliant server sends none otherwise, per
  14-EVIDENCE.md fact 3); `_on_session` (resources/prompts/completion calls) is unchanged.
  `_on_notification`'s new `ProgressNotification` branch observes generically via `_on_progress`:
  the latest `(progress, total, message)` per server is kept for `MCPManager.last_progress(name)`,
  and a live-only note fires at most once per `_PROGRESS_NOTE_INTERVAL_S = 2.0` per server, always
  on completion (`progress >= total`) regardless of the throttle window.
- `LoggingMessageNotification` reaches `agent86.tools.mcp_client`'s Python logger at the mapped
  RFC 5424 level (`logger.log(level, "MCP server %r [%s]: %s", ...)`), no note, no
  `logging/setLevel` ever sent. `ResourceUpdatedNotification` becomes a live note naming the URI
  and the `read_resource` tool. `CancelledNotification` gets no branch at all, matching the
  plan's explicit ruling (the SDK's dispatcher consumes it before `message_handler` ever runs).
- Twenty-one new unit tests in `tests/unit/test_mcp.py` (10 for `list_changed`, 11 for
  progress/logging/resource-updated/unrouted/never-raises) drive every branch through
  `_DyingTransport.notify()`/`notify_nowait()` — including both list-changed-vs-death and
  list-changed-vs-stop race tests, back-to-back serialization, throttling with always-on
  completion, message clipping, and the handler surviving a monkeypatched branch that raises.

## Task Commits

Each task was committed atomically:

1. **Task 1: Route list_changed into a guarded, identity-preserving tools re-fetch** - `d66b1d9`
   (feat, TDD)
2. **Task 2: Request and observe progress; route logging and resource-updated** - `4c56bbd`
   (feat, TDD)

## Files Created/Modified

- `src/agent86/tools/mcp_client.py` - `_NOTIFICATION_TEXT_MAX`/`_clip`; `_add_note(...,
  persistent=True)`; `MCPManager._refetch_locks`/`_last_progress`/`_progress_note_at`;
  `_serve_once`'s `this_session` list and rewritten `_on_message`; new
  `MCPManager._on_notification`/`_refetch_tools`/`_on_progress`/`last_progress`;
  `_PROGRESS_NOTE_INTERVAL_S`/`_MCP_LOG_LEVELS`/`_request_progress`; `call_tool`'s `_call` now
  passes `progress_callback=_request_progress`; module docstring gained one sentence naming
  `_on_notification` as MCP-24's router
- `tests/unit/test_mcp.py` - `import logging`; 21 new tests (10 `list_changed`, 11
  progress/logging/resource-updated/unrouted/never-raises)

## Decisions Made

See `key-decisions` in the frontmatter — every ruling (list_changed scope, identity preservation,
the race guard, progress's "observed generically, not attributed" scoping, logging with no
`setLevel`, resource updates as a live note, cancellation getting no branch) is the plan's own,
carried forward verbatim from its objective's "Rulings" section; no new decision was required
during execution.

## Deviations from Plan

None — plan executed exactly as written. Progress/logging/resource-updated branches were
implemented in the same `_on_notification` method Task 1 introduced (as the plan's own Task 2
action text specifies: "before the debug fallback, add..."), landed across the two commits in
the order the plan's own task boundaries describe: Task 1's commit contains only the
`list_changed`-routing branches plus the `else` fallback comment noting "Task 2 (14-04) adds
progress/logging/resource-updated branches here" (later replaced by the real branches in Task
2's commit) — verified by inspecting `d66b1d9` and `4c56bbd`'s diffs independently.

## Issues Encountered

None. `test_death_eof_clears_sessions_and_tools` (the known pre-existing Phase 12 flake documented
in 13-04's and 14-03's own SUMMARYs) did not flake in any of the full-suite runs performed for
this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MCP-24 is closed: a server that changes its tool list mid-session is reflected in the manager
  and (through Phase 12's listener) the harness registry, without racing death/stop; progress,
  logging and resource updates all reach something other than a no-op. `docs/mcp-conformance-
  matrix.md`/`ARCHITECTURE.md` §15/CHANGELOG/REQUIREMENTS.md traceability updates are left to
  this phase's own signoff plan (14-06), matching this milestone's established per-phase docs
  sequencing (Phases 11-13's own final plans and 14-03's own note to the same effect).
- `MCPManager.last_progress(name)`/`_add_note(persistent=False)` are live and available for
  14-06's matrix re-ruling of CAP-PROGRESS (implemented, scoped to "observed generically") and
  CAP-LOGGING (partial, receive-side routed only) and CAP-CANCELLATION (staying `absent`/`out`,
  explicitly not claimed by this plan).
- Full suite green: `pytest -q` 1428 passed (up from 1404), 0 failed, 14 deselected; `pytest
  tests/unit/ -q` 871 passed; `pytest tests/integration/test_mcp_client.py
  tests/integration/test_mcp_live.py tests/integration/test_scripting_contract.py -q` 48 passed;
  `mypy src/agent86` and `ruff check .` both clean. No blockers for 14-05/14-06.

## Self-Check

- `src/agent86/tools/mcp_client.py` — FOUND (modified)
- `tests/unit/test_mcp.py` — FOUND (modified)
- Commit `d66b1d9` — FOUND (`git log --oneline --all | grep d66b1d9`)
- Commit `4c56bbd` — FOUND (`git log --oneline --all | grep 4c56bbd`)

## Self-Check: PASSED

---

*Phase: 14-schema-deferral-and-notification-handling*
*Completed: 2026-09-25*
