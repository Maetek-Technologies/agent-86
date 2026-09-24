---
phase: 12-fix-the-zombie-tool-desync-and-add-reconnect
plan: 01
subsystem: tools
tags: [mcp, asyncio, anyio, reliability, session-lifecycle]

# Dependency graph
requires:
  - phase: 11-resources-and-prompts-become-first-class
    provides: MCPManager, _MCPCapabilityTool base, capability-gated synthetic tools
provides:
  - "Mid-session server death is observable: a closed read stream ends the owning task and clears both `_sessions[name]` and `_server_tools[name]` in one `finally` block (SC1)"
  - "Every unavailable-session error names the server and its state (SC2) via `MCPManager._unavailable_error` / `MCPServerUnavailable`"
  - "`on_tools_changed` hook + `_server_state`/`_disconnect_cause`/`_reconnect_attempt` fields for plan 12-03 (reconnect) and 12-04 (registry sync)"
  - "`_MAX_RECONNECT_ATTEMPTS` constant and the exact `_unavailable_error` message strings plan 12-03 must reuse verbatim"
affects: [12-03-bounded-reconnect, 12-04-registry-sync]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_EOFWatchStream: wrap a transport read stream one layer above ClientSession so end-of-stream is observable transport-agnostically (stdio/SSE/HTTP all feed ClientSession a read stream)"
    - "_serve_once/_serve split: _serve_once is one connection attempt returning a _SessionEnd(cause, tools) NamedTuple; _serve is the task entry point that reacts to a non-None cause"
    - "asyncio.wait({stop_wait, died_wait}, return_when=FIRST_COMPLETED) races a deliberate close_event against the transport's own EOF signal, with close_event.is_set() re-checked to break same-tick races"

key-files:
  created: []
  modified:
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_mcp.py

key-decisions:
  - "The death signal is end-of-stream on the read stream (_EOFWatchStream), NOT message_handler's Exception branch — 12-RESEARCH.md's own planner correction, confirmed by reading the installed SDK (mcp/shared/jsonrpc_dispatcher.py, mcp/client/stdio.py): a real stdio kill makes stdout_reader exit `async with read_stream_writer:`, which closes the stream and ends the dispatcher's `async for item in self._read_stream` normally — no Exception item is ever delivered to message_handler."
  - "message_handler IS installed, but its Exception branch only records the latest transport error as cause TEXT for the disconnect note (a lone malformed line is not death); its notification branch stays a no-op (list_changed routing is MCP-24, untouched)."
  - "_is_connection_closed decides on the SDK's CONNECTION_CLOSED error CODE, never on MCPError's type alone — MCPError is also what a healthy server's ordinary JSON-RPC error raises (research Pitfall 3)."
  - "stop_server()/close() are distinguished from a drop by checking close_event.is_set() both right after the asyncio.wait race and again in the except block, so deliberate teardown never fires on_tools_changed or gets logged as 'disconnected'."

requirements-completed: [MCP-26]

# Metrics
duration: ~25min
completed: 2026-09-24
---

# Phase 12 Plan 01: Death detection + named unavailable-session errors Summary

**A killed stdio/SSE/HTTP server now stops parking its task forever — `_EOFWatchStream` observes end-of-stream above the transport, clears `_sessions`/`_server_tools` together, and every "no live session" error names the server and its state (SC1 + SC2, MCP-26).**

## Performance

- **Duration:** ~25 min (commits 15:28–15:30 UTC)
- **Tasks:** 3 (Task 1 tests + Task 2 detection landed as one commit, Task 3 named errors as a second)
- **Files modified:** 2 (`src/agent86/tools/mcp_client.py`, `tests/unit/test_mcp.py`)

## Accomplishments

- **SC1 — death is observable and both dicts clear together.** `MCPManager._serve` is split into `_serve_once` (one connection attempt) and `_serve` (the task entry point). The transport's read stream is wrapped in a new `_EOFWatchStream`, whose `on_eof` fires only on real end-of-stream / `anyio.ClosedResourceError` / `anyio.BrokenResourceError` conditions — never on its own `aclose()`/`__aexit__` (a deliberate teardown cancels the dispatcher rather than draining it to EOF). That `died` event is raced against the existing `close_event` via `asyncio.wait({stop_wait, died_wait}, return_when=FIRST_COMPLETED)`; `close_event.is_set()` is checked both immediately after the race and again inside the `except` block, so a `stop_server()`/`close()` that lands in the same tick as a drop is never misreported. `self._sessions.pop(name, None)` and `self._server_tools.pop(name, None)` now happen together in the single `finally` of `_serve_once`, on every exit path — the owning task's asyncio `Task` object reaches `.done()` instead of parking on `close_event.wait()` forever.
- **SC2 — every unavailable-session error names the server.** `MCPManager._unavailable_error(server, cause=None)` is the one place these messages are built, branching on `self._server_state.get(server)`: never-connected/stopped → `"MCP server '{server}' is not connected."`; disconnected → names the recorded cause and points at `/config mcp`; reconnecting (plan 12-03's state) → names the attempt count against `_MAX_RECONNECT_ATTEMPTS`; connected but the call itself just failed → `"...closed the connection during the call (...)."`. `call_tool` and `_on_session` both use `.get()` instead of `in` + index (the loop thread can pop `_sessions[name]` between the two reads) and reclassify a failed `result()` as `MCPServerUnavailable` only when the server state isn't `"connected"` **or** `_is_connection_closed(exc)` is true — decided on the SDK's `CONNECTION_CLOSED` error *code*, never on `MCPError`'s type alone, so a healthy server's ordinary JSON-RPC error (`bad params`, `tool not found`) still propagates completely unchanged to the model.
- **A closed server's tools no longer look callable-but-broken with a generic error.** `MCPTool.run`/`_MCPCapabilityTool` were unchanged (they already wrap any exception as a soft `ToolResult(ok=False, error=...)`) but now surface the named `MCPServerUnavailable` message through that same path.
- **`on_tools_changed` hook + reconnect scaffolding for the rest of the phase.** `MCPManager.on_tools_changed: Callable[[str, list[Tool], list[Tool]], None] | None` is called (never raising — failures are logged as a note) via `_emit_tools_changed` from the new `_on_drop`, which records `"MCP server '{name}' disconnected ({cause}); its {n} tool(s) were unregistered."` and sets `_server_state`/`_disconnect_cause`. `_MAX_RECONNECT_ATTEMPTS = 5` and `_reconnect_attempt` exist but are inert in this plan — `_serve` still ends the task on a drop rather than looping; wiring the retry loop is plan 12-03.
- **`tools()` now snapshots.** `list(self._server_tools.values())` guards against "dictionary changed size during iteration" now that the loop thread can mutate `_server_tools` asynchronously from the main thread's read.

## Task Commits

1. **Task 1 + Task 2: Wave 0 death/named_server tests + `_EOFWatchStream`/`_serve_once` split** — `3236266` (test) — landed together because Task 1's new imports (`MCPServerUnavailable`, `MCPListResourcesTool`) break collection of the whole test file until Task 2's `MCPServerUnavailable` class exists, matching the documented 11-02/11-03 precedent.
2. **Task 3: Name the server in every unavailable-session error (SC2)** — `7763494` (feat)

**Plan metadata:** (this commit) `docs(12-01): complete death detection, registry sync, bounded reconnect plan`

## Files Created/Modified

- `src/agent86/tools/mcp_client.py` — `MCPServerUnavailable`, `_EOFWatchStream`, `_describe`, `_SessionEnd`, `_is_connection_closed`, `_serve_once`/`_serve` split, `_on_drop`, `_emit_tools_changed`, `_unavailable_error`, `on_tools_changed`/`_server_state`/`_disconnect_cause`/`_reconnect_attempt` fields, `_MAX_RECONNECT_ATTEMPTS`; `call_tool`/`_on_session`/`stop_server`/`close`/`tools()` updated to match.
- `tests/unit/test_mcp.py` — `_wait_until`, `_Up`, `_DyingTransport` (a fake transport built on a real `anyio.create_memory_object_stream` whose send side can really be closed mid-session, plus a `deliver()` helper that drives the injected `message_handler` directly), and ten new tests: six `test_death_*` and four `test_named_server_*`.

## Decisions Made

- **The death signal is end-of-stream, not `message_handler`'s `Exception` branch.** This is 12-RESEARCH.md's own planner correction (see the plan's `<objective>`), reconfirmed against the installed SDK while implementing: `mcp/shared/jsonrpc_dispatcher.py`'s read loop (`async for item in self._read_stream:`) ends *normally* on a killed stdio subprocess — `stdout_reader` in `mcp/client/stdio.py` exits `async with read_stream_writer:` on subprocess EOF, which closes the stream, and the dispatcher calls `_fan_out_closed()` and returns. No `Exception` item is ever delivered to `message_handler` in that path. `_EOFWatchStream` therefore sits one layer above `ClientSession`, wrapping the transport's own read stream — the one place end-of-stream is visible regardless of transport (stdio/SSE/streamable-HTTP all hand `ClientSession` a read stream). `message_handler` **is** installed (`_on_message`) and its `Exception` branch records the latest transport error as *cause text* for the disconnect note only; a single malformed line alone does not mark the server dead (pinned by `test_death_transport_exception_item_alone_is_not_death`). This design is what plans 12-03 through 12-07 and the verifier must build on — future work should not attempt to detect death via `message_handler`'s `Exception` branch alone, it will not fire on a real subprocess kill.
- **`_is_connection_closed` checks the error CODE, not the exception type.** `mcp.shared.exceptions.MCPError` is the SDK's general JSON-RPC-error exception, raised both for "the connection is gone" (code `CONNECTION_CLOSED = -32000`) and for an ordinary protocol error from a healthy server (e.g. `-32602 bad params`). Rewriting every `MCPError` to say "disconnected" would misreport a live server's real error — pinned by `test_named_server_healthy_error_is_not_rewritten`, which asserts the *same exception type* propagates with `"bad params"` intact and `"disconnected"` absent.
- **A deliberate stop is distinguished from a drop by checking `close_event.is_set()` twice** — once right after the `asyncio.wait` race (normal case) and again inside the `except` block (the race where teardown noise from `stdio_client`'s own `shutdown()` — e.g. `ClosedResourceError` — could otherwise be misread as a drop). Neither `on_tools_changed` nor a "disconnected" note fires for `stop_server()`/`close()` (`test_death_not_reported_for_stop_server`).

## Deviations from Plan

None — plan executed exactly as written. Tasks 1 and 2 landed as a single commit rather than two, but this was explicitly anticipated and pre-authorized by the plan's own Task 1 action text: "Import `MCPServerUnavailable`, `MCPTool`, `MCPListResourcesTool`... These imports make the file fail at collection until Task 2/3 land — that is the intended RED state; commit the tests together with Task 2 if a RED-only commit would break collection of the rest of the file (document that in the SUMMARY, matching the 11-02/11-03 precedent)." Not counted as a deviation since the plan itself specifies this outcome.

## Issues Encountered

None. Two `ruff format`-flagged long lines (`_EOFWatchStream.__init__`'s tuple and `_is_connection_closed`'s `getattr` chain) were wrapped across multiple lines during implementation before the first commit — routine formatting, not a deviation.

## Known Stubs

None. This plan's scope (SC1 + SC2) is fully wired end to end — no placeholder data paths were introduced. The reconnect loop itself (`_MAX_RECONNECT_ATTEMPTS`, `_reconnect_attempt`, the `"reconnecting"` state branch in `_unavailable_error`) is intentionally inert scaffolding for plan 12-03, not a stub masking missing functionality within this plan's own success criteria — `_server_state` never transitions to `"reconnecting"` anywhere in this plan's code, so that branch is unreachable until 12-03 adds the retry loop that sets it.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 12-03 (bounded reconnect, MCP-23) can now build its retry loop directly on `_serve_once`'s `_SessionEnd(cause, tools)` return value and the `_server_state`/`_disconnect_cause`/`_reconnect_attempt` fields this plan added — the exact `_unavailable_error` "reconnecting" message string is already written and unit-testable once 12-03 starts setting that state.
- Plan 12-04 (registry sync) can wire `MCPManager.on_tools_changed` directly to `ToolRegistry` — the hook already fires `(server, removed_tools, added_tools)` on the MCP loop thread with the never-raise backstop (`_emit_tools_changed`) in place; 12-04 only needs to supply a thread-safe callback (per 12-RESEARCH.md Pitfall 4).
- Full verification suite green: `pytest tests/unit/test_mcp.py -q` (59 passed), `pytest tests/integration/test_mcp_client.py -q` (14 passed, file unmodified), `pytest tests/integration/test_scripting_contract.py -q` (19 passed), `mypy src/agent86` clean, `ruff check .` clean.
- No blockers for 12-02 (parallel plan, ToolRegistry) or 12-03/12-04 (both depend on this plan's `on_tools_changed`/`_server_state` seam, both closed).

## Self-Check: PASSED

- FOUND: `src/agent86/tools/mcp_client.py`
- FOUND: `tests/unit/test_mcp.py`
- FOUND commit `3236266` (test(12-01): death detection tests + _EOFWatchStream/_serve_once split)
- FOUND commit `7763494` (feat(12-01): name the server in every unavailable-session error (SC2))

---
*Phase: 12-fix-the-zombie-tool-desync-and-add-reconnect*
*Completed: 2026-09-24*
