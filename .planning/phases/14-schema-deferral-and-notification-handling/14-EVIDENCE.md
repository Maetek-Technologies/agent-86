# Phase 14 — Live evidence: server instructions and notification delivery

**Gathered:** 2026-09-25 · **Runner:** throwaway scratchpad scripts, raw `mcp` SDK
(`ClientSession` + `stdio_client`, `MCPServer`), never `agent86.tools.mcp_client.MCPManager` — so
the result does not depend on code plans 14-02..14-04 change and is unaffected by any concurrent
edit to `mcp_client.py`/`loop.py`/`prompt.py` in the shared working tree (this plan touches no
production code).

**Environment:** node v22.22.0, npx.cmd 10.9.4, `.venv` Python 3.12.10, `mcp` SDK 2.0.0
(`importlib.metadata.version("mcp")`). `npm view @modelcontextprotocol/server-everything version`
and `npm view @modelcontextprotocol/server-filesystem version` both resolved to `2026.8.31`
(re-run 2026-09-25, unchanged from Phase 10's D-11 pin and Phase 13's `13-EVIDENCE.md`
re-verification). `mcp-server-git==2026.8.18` installed into a throwaway scratchpad venv via
`python -m venv <scratchpad>/gitvenv` +
`<scratchpad>/gitvenv/Scripts/python.exe -m pip install mcp-server-git==2026.8.18`, launched as
`command=<gitvenv python>`, `args=["-m", "mcp_server_git", "--repository", "C:/Projects/agent86CLI"]`.

## InitializeResult.instructions across the corpus

| server | version | instructions | declares tools.list_changed |
|---|---|---|---|
| server-everything | 2026.8.31 (server_info reports `2.0.0`) | `'# Everything Server – Server Instructions\n\nAudience: These instructions are written for an LLM or autonomous agent integrating with the Everything MCP Server.\nFollow them to use, extend, and troubleshoot the server safely and effectively.\n\n## Cross-Feature Relationships\n\n- Use `get-roots-list` to see client wor…'` (1,607 chars total, quoted to 300 here; full text captured verbatim in the scratchpad run and not committed) | `True` |
| server-filesystem | 2026.8.31 (server_info reports `0.2.0`) | `None` | `True` |
| mcp-server-git | 2026.8.18 (server_info reports `1.30.0`) | `None` | `False` |
| live_mcp_server | (this repo's CI fixture, no env flags; server_info reports empty version string) | `None` | `False` |

All four servers were reachable; none needed the "not reachable" fallback.

## Conclusion for SC1

At least one pinned corpus server sets instructions: server-everything. Plan 14-05 proves
rendering against the CI fixture and 14-06 may cite server-everything as live-corpus demand.

(Full detail: `server-everything@2026.8.31`'s instructions are substantial — audience framing,
cross-feature relationships between its own tools, constraints/limits per tool, operational
patterns, and even an easter egg instructing the model to acknowledge the instructions were
received. This is a real, LLM-facing "how to use this server's tools" document, not an incidental
field. `server-filesystem@2026.8.31` and `mcp-server-git==2026.8.18` both leave it unset (`None`).)

## SDK notification facts (mcp 2.0.0)

Scratch `MCPServer("probe", instructions="Use probe tools carefully.")` over stdio with `grow`
(`mcp.add_tool` + `await ctx.request_context.session.send_tool_list_changed()`), `grow_via_bus`
(`mcp.add_tool` + `await ctx.notify_tools_changed()`), and `slow` (three
`ctx.report_progress(...)` then `ctx.log("info", "hello log")`). Client recorded
`type(message).__name__` for every `message_handler` call, per the sequence in the plan
(`grow` → sleep 0.5s → record; `grow_via_bus` → sleep 0.5s → record; `slow` with no
`progress_callback` → sleep 0.3s → record; `slow` with a no-op async `progress_callback` → sleep
0.3s → record). `init.instructions` printed as `'Use probe tools carefully.'`, confirming
`MCPServer(name, instructions="...")` → `InitializeResult.instructions == "..."` on the client.

All four findings matched this plan's stated expectations exactly — no deviation section is
needed.

1. **`send_tool_list_changed` → `ToolListChangedNotification` reached `message_handler`.**
   Observed: `['ToolListChangedNotification']` after calling `grow`.
2. **`notify_tools_changed` (the `Context` bus method) → nothing arrived.** Observed: `[]` after
   calling `grow_via_bus` — confirms it publishes only to the `subscriptions/listen` bus
   (SEP-2575), which a `2025-11-25` handshake client never opens, and does NOT reach `message_handler`.
3. **Progress without `progress_callback` → no `ProgressNotification`; with it → N
   `ProgressNotification`s teed to `message_handler`.** Observed: calling `slow` with no
   `progress_callback` produced `['LoggingMessageNotification']` (zero `ProgressNotification`s —
   `report_progress` is confirmed a no-op when the caller never requested progress); calling
   `slow` again with a no-op async `progress_callback` produced
   `['ProgressNotification', 'ProgressNotification', 'ProgressNotification', 'LoggingMessageNotification']`
   — exactly 3 progress notifications (one per `ctx.report_progress` call) teed to
   `message_handler` even though nothing in the client code correlates them to the call beyond
   the fact they arrived while it was in flight.
4. **`LoggingMessageNotification` arrived with no `logging/setLevel` request ever sent.** Observed
   in both slow-tool runs above — the client never called `session.set_logging_level` (or
   equivalent) at any point, yet the server's `ctx.log("info", "hello log")` still produced a
   `LoggingMessageNotification` delivered to `message_handler`. (The server side additionally
   emitted an `MCPDeprecationWarning` — "The logging capability is deprecated as of 2026-07-28
   (SEP-2577)" — a note for any future logging-capability plan, not something this phase's scope
   changes.)

## Metadata

**Corpus availability:** all four servers (server-everything, server-filesystem, mcp-server-git,
live_mcp_server) were reachable in this environment; none needed the "not reachable" fallback path.

**Re-verification of plan-time corrections:** the four plan-time corrections to 14-RESEARCH.md
listed in `14-01-PLAN.md`'s objective (progress not sent unconditionally;
`notify_tools_changed()` does not reach agent86; logging arrives with no `setLevel`; `instructions`
round-trips) are all re-confirmed live above, with no deviation.
