# Phase 14: Schema deferral and notification handling - Research

**Researched:** 2026-09-24
**Domain:** MCP client prompt-compilation strategy (schema deferral) + MCP notification routing
(`message_handler`) — `src/agent86/tools/mcp_client.py`, `src/agent86/orchestration/loop.py`,
`src/agent86/cognitive/prompt.py`
**Confidence:** HIGH (every claim below is grounded in a direct read of the installed `mcp` 2.0.0
SDK source and the current `src/agent86` code, not training-data recall — MCP SDKs move fast and
this project's own audit already found training-data assumptions stale twice)

## Summary

This phase closes two requirements — MCP-20 (schema deferral, ADR 0003) and MCP-24 (`list_changed`
handling) — and both turn out to be smaller, more localized changes than the roadmap text alone
suggests, because two structural facts already do most of the work:

1. **`ToolRegistry.specs()` and `Harness._context_budget` already recompute from scratch on every
   single request** (`tools/registry.py:110-113`, `orchestration/loop.py:485-490`). Deferring a
   tool's schema is therefore not a new caching/invalidation mechanism — it is a two-line change to
   what `MCPTool.spec()` returns before vs. after that tool's first successful call, on the exact
   same `MCPTool` instance the registry already holds. ADR 0003's "budget must be recomputed inside
   the step that triggers materialisation" requirement is satisfied for free, provided the
   materialisation flip happens synchronously inside `MCPTool.run()` (or `MCPManager.call_tool`),
   before that tool's `ToolResult` is returned — because the very next model call inside the same
   turn already reads `registry.specs()` fresh.
2. **The registry-sync plumbing `list_changed` needs already exists, built by Phase 12 for a
   different trigger (server death/reconnect).** `MCPManager.on_tools_changed` /
   `MCPManager._emit_tools_changed` / `Harness._on_mcp_tools_changed` / `Harness._wire_mcp`
   (`mcp_client.py:684-688,804-811`; `orchestration/loop.py:369-412`) already do exactly what SC3
   needs: diff an old/new tool list and sync `Harness.registry` from *any* thread, never raising.
   A `list_changed` handler only needs to (a) parse the notification, (b) re-run `list_tools()` +
   `_capability_tools()` for that one server, (c) diff against `self._server_tools[name]`, and
   (d) call the existing `_emit_tools_changed` — reusing, not rebuilding, the sync path.

Two findings complicate the naive reading of the roadmap text and need an explicit planning
decision (see Open Questions): first, **CAP-PROGRESS can be closed without wiring a per-call
`progress_callback`** — the installed SDK's dispatcher tees `notifications/progress` to
`message_handler` unconditionally, regardless of whether the client ever requested tracking
(`jsonrpc_dispatcher.py:629-647`), so observing progress is exactly the same shape of work as
observing `list_changed`. Second, **CAP-CANCELLATION almost certainly does *not* close
incidentally** — `notifications/cancelled` is applied by the dispatcher internally and explicitly
never reaches `message_handler` (`session.py:1435-1437`), so nothing this phase's `_on_message`
work can do would move that row; the roadmap's "may close incidentally" hope for that one row looks
unfounded and the matrix should say so rather than silently claim it.

**Primary recommendation:** Implement schema deferral as a per-`MCPTool` "materialized" boolean
flipped inside `run()`/`call_tool()` (no new fetch, no new transport call — the schema is already
known from the eager `list_tools()` at connect); implement `list_changed` handling as a new branch
inside `_serve_once`'s `_on_message` (`mcp_client.py:928-935`) that re-fetches and calls
`_emit_tools_changed`, reusing Phase 12's plumbing verbatim; treat server-instructions-in-the-prompt
as a small, separate, previously-unbuilt sub-feature (see Open Question 1) rather than assuming it
is covered by the existing `tools=` wire field.

## User Constraints

No `CONTEXT.md` exists for this phase — the user explicitly chose to continue without
`/gsd:discuss-phase`. There are no locked decisions, discretion areas, or deferred ideas to carry
forward from that source. ADR 0003 (`docs/adr/0003-mcp-schema-deferral-prompt-contract.md`) is
**Accepted** and is the locked design ruling for this phase; treat every sentence in its "Decision"
section as binding, not as a proposal to re-litigate.

**ADR 0003's ruling, restated as constraints the plan must satisfy:**
- Deferring MCP tool **schemas** is permitted; deferring tool **names** is not, ever.
- The system prompt (broadly: everything the model sees before it can act, not necessarily
  free-text) must always list every callable tool's name, plus its server's instructions where
  present, for every mounted server, regardless of whether that tool has ever been called.
- The budget must be recomputed around a materialising schema's cost inside the step that triggers
  it, not only on the next request's recomputation.
- A deferred schema's first fetch/materialisation is a synchronous cost inside the step that needs
  it — never modeled as free, never a background operation.
- `run --json` keys stay additive-only for any new key this phase adds.
- Schema deferral gets **no matrix row** — do not add `CAP-SCHEMA-DEFERRAL` to
  `docs/mcp-conformance-matrix.md`; ADR 0003 itself is the record of that decision.

## Project Constraints (from CLAUDE.md)

- **Lazy imports**: Textual, keyring, tomlkit must never be imported at module top level; this
  phase touches none of those, but any new import added to `mcp_client.py`/`loop.py` must stay
  inside the existing lazy-import discipline that file already follows (`mcp`, `anyio`, etc. are
  all imported inside functions).
- **Tool execution must never raise**: every new code path this phase adds (materialisation,
  `list_changed` re-fetch) must degrade to a note/log line, never an unhandled exception escaping
  into the MCP loop thread or the ReAct loop. `MCPManager._emit_tools_changed` and
  `Harness._on_mcp_tools_changed` already model the required shape (`try/except Exception`, log,
  continue) — new code should match it exactly, not invent a new failure contract.
- **`types.py` is the lingua franca**: if a new field is needed on `ToolSpec` (unlikely — see
  Architecture Patterns) it goes in `src/agent86/types.py`, provider-agnostic, never MCP-specific.
- **`config.py` is read-only**; any new `MCPServerConfig` field (none are obviously required by
  this phase, but see Open Question 2) must ship in `config.py` only as a Pydantic field/default —
  no TOML write-back logic there. `/config mcp` UI wiring, if any, lives in `config_writer.py`/TUI.
- **API keys never stored in config** — not implicated by this phase.
- **Windows console UTF-8** — not implicated.
- **`run --json` additive-only** — directly implicated (ADR 0003's own second-order requirement);
  see `tests/integration/test_scripting_contract.py:38-40`'s `REQUIRED_JSON_KEYS` frozenset, which
  documents "extra keys are allowed" as the enforced contract shape.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-20 | Schema deferral, as ruled by MCP-10 (ADR 0003) | Materialisation mechanism (Architecture Patterns §1), budget-recompute proof (Architecture Patterns §1 + `_context_budget` reading), server-instructions gap (Open Question 1) |
| MCP-24 | `list_changed` handling — no `message_handler` routes notifications anywhere; a server that changes its tool list mid-session is invisible until restart | `_on_message` extension point (Architecture Patterns §2), reuse of Phase 12's `on_tools_changed`/`_emit_tools_changed` plumbing, SDK notification type reference (Code Examples), CAP-PROGRESS/CAP-LOGGING/CAP-CANCELLATION scope corrections (Open Questions 3-4) |

## Standard Stack

No new dependency of any kind. Everything this phase needs already ships in the pinned `mcp==2.0.0`
SDK (installed at `.venv/Lib/site-packages/mcp`, confirmed via
`python -c "import importlib.metadata as m; print(m.version('mcp'))"` → `2.0.0`, matching
`docs/mcp-conformance-audit-2026-09.md`'s pin) and in `agent86`'s own existing `tools/mcp_client.py`
/ `orchestration/loop.py` / `tools/registry.py`.

### Core

| Component | Location | Purpose | Why standard |
|---|---|---|---|
| `mcp.types.ToolListChangedNotification` / `ResourceListChangedNotification` / `PromptListChangedNotification` | `mcp_types._v2025_11_25` (re-exported as `mcp.types.*`) | The three "sibling" notifications SC3 names | Already the SDK's canonical wire types for `2025-11-25`, the pinned revision (Phase 10, D-01) |
| `mcp.types.ProgressNotification` | same | Progress observation (CAP-PROGRESS) | Confirmed teed to `message_handler` unconditionally (see Code Examples) |
| `MCPManager.on_tools_changed` / `_emit_tools_changed` | `tools/mcp_client.py:684-688,804-811` | The exact sync mechanism SC3 needs | Built by Phase 12 for death/reconnect; this phase is its second caller, not a new mechanism |
| `Harness._wire_mcp` / `_on_mcp_tools_changed` | `orchestration/loop.py:369-412` | Cross-thread registry sync consumer | Same reasoning — reuse, don't rebuild |
| `ToolRegistry.specs()` | `tools/registry.py:110-113` | Reads `tool.spec()` fresh, every call, no caching | This is *why* materialisation needs no new hook |

### Supporting

| Component | Location | Purpose | When to use |
|---|---|---|---|
| `mcp.server.session.ServerSession.send_tool_list_changed()` (`mcp/server/session.py:461-463`) and `mcp.server.mcpserver.context.Context.notify_tools_changed()` (`mcp/server/mcpserver/context.py:129`) | server-side SDK | Making `tests/integration/live_mcp_server.py` emit a real `list_changed` notification for Wave 0 test infra | Needed to add an opt-in "dynamic tool" probe to the CI fixture, mirroring Phase 13's `AGENT86_LIVE_MCP_EXTRA_TOOLS` pattern |
| `InitializeResult.instructions: str | None` (`mcp_types/_v2025_11_25/__init__.py:2002-2007`) | SDK wire type | Server-provided prompt hint text — see Open Question 1 | Only if the plan implements the "plus server instructions" half of SC1 |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|---|---|---|
| Flipping a per-tool `materialized` flag on `MCPTool` | A separate "deferred schema registry" keyed by tool name, consulted by `_build_request` | More indirection for no benefit — `MCPTool` already IS the registered object `specs()` reads; a side table would need its own invalidation on tool add/remove/reconnect that the object's own field gets for free |
| Re-`list_tools()` on every `list_changed` notification | Trust the notification's payload (some SDKs/servers include the new list inline) | The SDK's `ToolListChangedNotification` carries no tool data — spec-correct clients must always follow up with a fresh `tools/list` call; there is no shortcut here |
| Wiring `progress_callback` per `call_tool`/`_on_session` invocation to observe progress | Observe `ProgressNotification` generically through the existing `_on_message` no-op branch | Confirmed (Code Examples) that the dispatcher tees progress unconditionally to `message_handler` even with no callback registered — per-call wiring is unnecessary extra surface for what CAP-PROGRESS actually requires (observability, not correlation to a specific call) |

**Installation:** none.

**Version verification:**
```
python -c "import importlib.metadata as m; print(m.version('mcp'))"   # 2.0.0 — unchanged since Phase 10's pin
```

## Architecture Patterns

### Recommended structural approach (not a directory-structure phase — everything lands in
existing files)

```
src/agent86/tools/mcp_client.py
├── MCPTool                     # gains a materialisation flag + a "stub schema" branch in spec()
├── _serve_once._on_message     # gains real notification-type branches (was Exception-only)
├── MCPManager._refetch_tools   # NEW: re-list_tools() + _capability_tools() for one server,
│                                 diff, call self._emit_tools_changed (reuses Phase 12 plumbing)
└── (existing) MCPManager.on_tools_changed / _emit_tools_changed / _add_note   # untouched, reused

src/agent86/orchestration/loop.py
└── (existing) Harness._wire_mcp / _on_mcp_tools_changed   # untouched, reused as-is

src/agent86/cognitive/prompt.py
└── build_system_prompt         # ONLY touched if the plan implements server-instructions text
                                   (Open Question 1) — currently has zero MCP awareness
```

### Pattern 1: Schema deferral via a per-tool materialisation flag, not a fetch

**What:** `MCPTool.__init__` already receives the tool's full `input_schema` eagerly, at connect
time, from the server's own `tools/list` response (`_tool_schema(t)`, called at
`mcp_client.py:969` inside `_serve_once`). There is no network-level "fetch schema later" to build
— the harness already has the schema in hand the whole time. "Deferred" is purely a
**prompt-compilation choice**: whether `MCPTool.spec()` reports that already-known schema to the
model this turn, or a minimal stub.

**When to use:** Every `MCPTool` (not the `_MCPCapabilityTool` synthetic tools, whose schemas are
agent86's own small, fixed Pydantic models — deferring those buys nothing and complicates the
"materialized" bookkeeping for no prompt-size win).

**Example (illustrative, not prescriptive of exact field names):**
```python
# src/agent86/tools/mcp_client.py — MCPTool, current shape (mcp_client.py:111-146)
class MCPTool(Tool[EmptyArgs]):
    def __init__(self, manager, server, tool_name, description, input_schema, read_only=False):
        ...
        self._schema = input_schema or {"type": "object", "properties": {}}
        # NEW: self._materialized = False  (flips True on first successful run())

    def spec(self) -> ToolSpec:
        # NEW: schema = self._schema if self._materialized else _DEFERRED_STUB_SCHEMA
        return ToolSpec(
            name=self.name, description=self.description,
            parameters=self._schema, side_effecting=self.side_effecting,
        )

    def run(self, call, ctx) -> ToolResult:
        try:
            text = self._manager.call_tool(self._server, self._tool, call.arguments)
        except Exception as exc:
            return ToolResult(call_id=call.id, name=self.name, ok=False,
                               error=f"MCP call failed: {exc}")
        # NEW: self._materialized = True  <- flips BEFORE returning, same step, per ADR 0003
        return ToolResult(call_id=call.id, name=self.name, content=text)
```
Because `ToolRegistry.specs()` calls `t.spec()` fresh on the *same* `MCPTool` instance every time
(`tools/registry.py:110-113`, confirmed: `register`/`try_register` store the exact object, never a
copy), flipping `self._materialized` inside `run()` is visible to the very next
`_build_request()`/`_context_budget()` call (`orchestration/loop.py:485-490`) with zero additional
plumbing. This is the load-bearing fact that makes MCP-20 small.

**Open sub-question the plan must resolve (not answered here):** what does the "deferred stub"
schema look like, concretely? It cannot be `{}` (some providers/validators reject a tool with no
`type`), and it must not silently let the model send arbitrary arguments that later fail Pydantic
validation in a confusing way. A minimal, permissive stub such as
`{"type": "object", "additionalProperties": True}` (accepts anything, describes nothing) is the
likely shape, but the plan should verify against each provider adapter (see Pitfall 1) that an
empty/wildcard schema round-trips through Anthropic's `tools[].input_schema`, OpenAI's
`tools[].function.parameters`, and Ollama's tool-calling format without a 4xx.

### Pattern 2: `list_changed` handling reuses Phase 12's tool-sync plumbing, triggered from `_on_message`

**What:** `_serve_once`'s `_on_message` (`mcp_client.py:928-935`) is already installed as
`ClientSession`'s `message_handler` (`mcp_client.py:959`) and already runs **on the MCP loop
thread, inside the same task that owns `session`**. Today it only records `Exception` items for
cause text; every `ServerNotification` (including all `list_changed` variants) falls through and is
silently dropped by the `if isinstance(message, Exception)` guard's implicit else-branch.

**When to use:** Add explicit `isinstance` branches for `ToolListChangedNotification`,
`ResourceListChangedNotification`, `PromptListChangedNotification` (SC3's "resources/prompts
siblings"), each triggering a re-fetch of that server's tool list.

**Example, following the codebase's exact idioms (never-raise, named-server notes):**
```python
# src/agent86/tools/mcp_client.py — inside _serve_once, after `session` exists
async def _on_message(message: Any) -> None:
    if isinstance(message, Exception):
        last_error[:] = [message]
        return
    if isinstance(message, (mcp_types.ToolListChangedNotification,
                             mcp_types.ResourceListChangedNotification,
                             mcp_types.PromptListChangedNotification)):
        await self._refetch_tools(name, session)          # NEW helper, see below
    elif isinstance(message, mcp_types.ProgressNotification):
        self._add_note(f"MCP server '{name}': progress — {message.params.message or ''}"
                        f" ({message.params.progress}/{message.params.total})")
    # LoggingMessageNotification / anything else: still a no-op for this phase's scope
```
`_refetch_tools` runs **on the same event loop** as `session` (no `run_coroutine_threadsafe`
marshalling needed — unlike `call_tool`/`_on_session`, which cross from the caller's thread; this
callback IS already on the loop thread), so it can `await session.list_tools()` directly, rebuild
the `MCPTool`/`_capability_tools()` list exactly as `_serve_once` does at connect
(`mcp_client.py:962-983`), diff against `self._server_tools.get(name, [])` by tool name, update
`self._server_tools[name]`, and call `self._emit_tools_changed(name, removed, added)` — the exact
function Phase 12 already wired to `Harness._on_mcp_tools_changed`
(`orchestration/loop.py:398-412`), which does the identity-checked `unregister_tool` /
`try_register` dance under `ToolRegistry`'s `RLock`. **No new registry-sync code is needed at all**
— only the notification-to-refetch glue inside `mcp_client.py`.

**A concurrency subtlety to design around (not yet proven safe, flagged for the plan's own
research/tests):** `_on_message` fires from the SDK's dispatcher while `_serve_once`'s own
`async with AsyncExitStack()` block is still executing (parked on the `asyncio.wait` at
`mcp_client.py:996-1002`). A `list_changed` notification racing a `stop_server()`/death/reconnect on
the *same* server needs the refetch to either (a) check `self._sessions.get(name) is session`
before mutating `_server_tools`, so a stale notification from a session that has already been torn
down cannot resurrect it, or (b) rely on the fact that `_on_message` is a closure over the specific
`session`/`name` of one `_serve_once` invocation and simply let a failed `list_tools()` call
(session already closing) raise, caught and logged the same way `_emit_tools_changed`'s own
listener-failure path already does. Either is workable; the plan must pick one and write a test for
the race (a `list_changed` notification delivered concurrently with `stop_server()`).

### Pattern 3: Server instructions are a genuinely new, small sub-feature (not covered by `tools=`)

**What:** `session.initialize()` returns an `InitializeResult` whose `.instructions: str | None`
field is, per the SDK's own docstring, meant to be "added to the system prompt"
(`mcp_types/_v2025_11_25/__init__.py:2002-2007`). Today, `_serve_once` calls
`await session.initialize()` and **discards the return value entirely**
(`mcp_client.py:961` — no variable assignment). Separately, `build_system_prompt`
(`cognitive/prompt.py:51-72`) has **zero awareness of MCP at all** — it composes identity,
environment, and skills only; MCP tool names reach the model exclusively through the native
`tools=` field of `CompletionRequest` (`orchestration/loop.py:492-499`), never through system-prompt
text.

**When to use:** Only if the plan interprets SC1's "(plus server instructions)" clause as a literal
new prompt-text requirement (see Open Question 1 for the alternative reading).

### Anti-Patterns to Avoid

- **Don't build a second "tool catalogue" cache anywhere.** `self._server_tools` (MCPManager) and
  `Harness.registry._tools` (ToolRegistry) are the only two stores of tool state and Phase 12
  already keeps them in sync via `on_tools_changed`. A third cache (e.g., "last known schema per
  tool name") would immediately desync on reconnect/list_changed.
- **Don't call `run_coroutine_threadsafe` from inside `_on_message`.** It already runs on the loop
  thread; wrapping the refetch in a threadsafe marshal would deadlock or double-schedule work that
  doesn't need it (`_on_session`/`call_tool` marshal because *they* are called from the harness's
  own thread — `_on_message` is not).
- **Don't materialise a tool's schema based on the model merely *naming* it in a failed/refused
  call.** Materialisation must be tied to a successful (or at least attempted-and-executed) call
  through `MCPTool.run()`/`MCPManager.call_tool`, not to the tool appearing in a `ToolCall` the
  registry never dispatched (e.g., an `allowed-tools` refusal) — ADR 0003's "first use" language
  means the harness actually ran the call.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Cross-thread tool-list sync into the registry | A new lock/queue/event mechanism for `list_changed` | `MCPManager.on_tools_changed` / `_emit_tools_changed` / `Harness._on_mcp_tools_changed` (already RLock-guarded, already never-raising, already tested) | Phase 12 built and tested this exact mechanism for a different trigger three phases ago; a second, parallel mechanism for the same job is pure duplication risk |
| Notification type dispatch | Hand-rolled `dict[str, ...]` method-name matching on raw JSON | `isinstance()` against `mcp.types.ToolListChangedNotification` etc. — the SDK already parses and discriminates these before `message_handler` ever sees them (`session.py:1402-1447`) | The SDK's `_on_notify` has already validated the notification against the negotiated protocol version and handed back a typed pydantic model; re-parsing raw params would throw away that validation |
| Progress observability | A new per-request progress-token bookkeeping table | The existing `_on_message` notification branch (Pattern 2) | Confirmed the dispatcher already tees every `notifications/progress` to `message_handler` unconditionally — building a `progress_callback`-per-call system is solving a problem CAP-PROGRESS doesn't actually have |

**Key insight:** almost everything this phase needs to reuse was built by Phase 12 for a narrower
purpose (server death/reconnect) and is more general than that purpose required. The main
implementation risk is *not* inventing new mechanism, but correctly wiring a second, independent
trigger (`list_changed`) into that existing mechanism without letting it race the first trigger
(death/reconnect) — see Pattern 2's concurrency subtlety and Pitfall 2 below.

## Common Pitfalls

### Pitfall 1: A "deferred" schema that breaks provider-side tool-call validation

**What goes wrong:** Some provider APIs (or their client SDKs) reject or warn on a tool schema
that is `{}`  or missing `"type": "object"` entirely. A poorly-chosen stub schema could make every
MCP tool call fail validation on the *first* call — exactly when materialisation is supposed to
happen — creating a chicken-and-egg failure where the tool can never be used at all.
**Why it happens:** Anthropic, OpenAI-compatible, and Ollama each validate/transform
`ToolSpec.parameters` slightly differently before sending it over the wire; agent86 has one
`ToolSpec.parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object",
"properties": {}})` (`types.py:117`) as its own "empty" default already, which is a strong signal
for what the deferred stub should reuse rather than invent.
**How to avoid:** Use `ToolSpec`'s own existing default-empty-schema shape
(`{"type": "object", "properties": {}}`) as the deferred stub rather than inventing a new shape, and
add one integration-level test per provider adapter (or at minimum the two adapters covering all
non-Anthropic providers: OpenAI-compatible and Ollama) proving a tool call against a stub-schema
tool round-trips.
**Warning signs:** A provider's `complete()`/`stream()` raising or returning an error response the
moment a deferred (never-yet-called) MCP tool is included in `tools=`.

### Pitfall 2: `list_changed` refetch racing Phase 12's death/reconnect state machine

**What goes wrong:** A `list_changed` notification could theoretically be delivered (or the refetch
still in flight) at the exact moment the server dies or a `stop_server()` call tears the session
down — `_refetch_tools` could then either raise into `_on_message` (already contained per
`session.py:1442-1447`'s outer try/except, so not fatal, but the note/log would be confusing) or,
worse, write a stale/partial tool list into `self._server_tools[name]` right before or after
`_serve_once`'s own `finally` pops it (`mcp_client.py:1025-1026`), producing exactly the kind of
zombie-registry-entry bug Phase 12 was built to fix, for a different code path.
**Why it happens:** `_on_message`, `_serve_once`'s main body, and `_serve`'s reconnect loop are
three independently-scheduled coroutines/tasks that all touch `self._server_tools[name]` and
`self._sessions[name]` without a shared lock (today's code relies on "only one owns a given name at
a time" by construction, not by explicit synchronization).
**How to avoid:** Guard the refetch's final write with a check that `self._sessions.get(name) is
session` (the exact session object this `_on_message` closure belongs to) immediately before
calling `_emit_tools_changed`, and write a test that fires a `list_changed` notification
concurrently with (or immediately before) a simulated drop, asserting the death path's cleanup wins
and no zombie entry survives.
**Warning signs:** A flaky test where a `list_changed`-triggered tool addition appears in
`self._server_tools` for a server whose `self._sessions` entry has already been popped.

### Pitfall 3: Assuming `CancelledNotification`/`CAP-CANCELLATION` "shares the same infrastructure"

**What goes wrong:** The roadmap text says CAP-LOGGING and CAP-CANCELLATION "share the same
notification routing and may close incidentally." Taking that at face value could lead to a plan
task that spends effort trying to observe `notifications/cancelled` through the new `_on_message`
branches, only to discover it never arrives there.
**Why it happens:** The SDK's own `_on_notify` explicitly special-cases `CancelledNotification`:
"Never surfaced (v1 parity): the dispatcher already applied it" (`session.py:1435-1437`), and the
dispatcher applies `notifications/cancelled` at `jsonrpc_dispatcher.py:623-628` by mutating
in-flight request state directly — it is consumed before `_on_notify`/`message_handler` is ever
called for that message.
**How to avoid:** Treat CAP-CANCELLATION as almost certainly staying `absent`/`out` after this
phase (client-initiated cancellation forwarding — sending `notifications/cancelled` when the user
hits Escape/Ctrl+C mid-tool-call — is a materially different, unbuilt feature: "agent86's own
turn-level cancel does not currently propagate," per the matrix's own CAP-CANCELLATION reasoning
cell). CAP-LOGGING (`LoggingMessageNotification`, method `notifications/message`) *does* fit the
same shape as `list_changed`/progress (teed to `message_handler` per `session.py:1439-1441`, which
also separately invokes `_logging_callback` first) and can close incidentally with near-zero extra
code — one more `isinstance` branch and a note.
**Warning signs:** A plan task or acceptance criterion that says "cancellation notifications are
observed" with no corresponding send-side (client → server) mechanism.

### Pitfall 4: Re-deriving the "recompute every request" argument instead of relying on it

**What goes wrong:** A plan could over-engineer SC2 by adding a bespoke "recompute the budget right
after a tool call" hook inside the OBSERVE phase of `run_turn`, duplicating logic
`_build_request`/`_context_budget` already performs on every subsequent model call.
**Why it happens:** ADR 0003's own Context section spends several paragraphs justifying that the
existing per-request recomputation "already structurally tolerates" a growing tool-schemas term —
this is presented as a *finding*, not a task, and it is easy to read the Decision section's
second-order requirements as demanding new machinery when they are actually describing a property
the code already has, contingent only on the materialisation flip being synchronous (Pattern 1).
**How to avoid:** Verify with a test that asserts NO new call to `_context_budget`/`context_window_for`
is needed beyond the existing per-request one — i.e., that flipping `_materialized` inside `run()`
is sufficient for the *next* `_build_request()` (same turn, next step) to already reflect the larger
schema, with no additional hook added to `_context_budget` itself.
**Warning signs:** A new parameter or hook added to `_context_budget`'s signature
(`orchestration/loop.py:458`) that duplicates what `registry.specs()` already provides fresh.

## Code Examples

### Confirmed: progress notifications reach `message_handler` unconditionally

```python
# .venv/Lib/site-packages/mcp/shared/jsonrpc_dispatcher.py:608-659 (excerpted)
def _dispatch_notification(self, msg, metadata, on_notify, sender_ctx):
    if msg.method == "notifications/cancelled":
        ...  # applied internally, consumed here — never teed onward
    elif msg.method == "notifications/progress":
        match msg.params:
            case {"progressToken": ..., "progress": ...} if (
                ... and (pending := self._pending.get(coerce_request_id(token))) is not None
                and pending.on_progress is not None
            ):
                self._spawn(_shielded_progress(pending.on_progress), ...)   # per-call callback
            case _:
                pass
    if run_notify_intercept(self._on_notify_intercept, msg.method, msg.params):
        return
    ...
    self._spawn(_contained_notify(on_notify), dctx, msg.method, msg.params, sender_ctx=sender_ctx)
    # ^ unconditional: progress is teed here regardless of whether a per-call on_progress matched
```
Source: installed `mcp==2.0.0` package, read directly (2026-09-24) — not training data.

### Confirmed: `notifications/cancelled` never reaches `message_handler`

```python
# .venv/Lib/site-packages/mcp/client/session.py:1435-1437
if isinstance(notification, types.CancelledNotification):
    # Never surfaced (v1 parity): the dispatcher already applied it;
    # listen cancels settled by the intercept.
    return
```

### Server-side: how the CI fixture could emit a real `list_changed` for Wave 0 tests

```python
# .venv/Lib/site-packages/mcp/server/mcpserver/context.py:129 (signature only)
async def notify_tools_changed(self) -> None: ...

# .venv/Lib/site-packages/mcp/server/session.py:461-463
async def send_tool_list_changed(self) -> None:
    await self.send_notification(types.ToolListChangedNotification())
```
A new opt-in tool in `tests/integration/live_mcp_server.py` (gated behind an env var, following
the exact `AGENT86_LIVE_MCP_EXTRA_TOOLS` precedent from plan 13-05) that registers one additional
tool at runtime and then calls `ctx.notify_tools_changed()` would let a real-stdio integration test
prove SC3 end-to-end, matching this project's own stated preference (per Phase 11-13's plans) for
live-fixture proof over mocked-only unit tests.

## State of the Art

| Old approach (agent86 before this phase) | New approach (this phase) | When changed | Impact |
|---|---|---|---|
| Every MCP tool's full JSON Schema is sent on every request, forever, once mounted | A tool's schema stays a small stub until its first successful call, then materializes for the rest of the session | This phase (MCP-20) | Shrinks the fixed per-request overhead for MCP-heavy sessions (many tools, few actually called) — directly reduces the `tool schemas` term in `_context_budget` |
| `message_handler` is installed but only records transport `Exception` cause text; every real `ServerNotification` is a no-op | `list_changed` (tools/resources/prompts), progress, and (incidentally) logging are observed and acted on | This phase (MCP-24) | `CAP-LIST-CHANGED`, `CAP-PROGRESS` move `absent`→`implemented`; `CAP-LOGGING` may follow |
| `session.initialize()`'s `InitializeResult` is discarded | (if Open Question 1 resolves toward building it) server `.instructions` captured and possibly surfaced | This phase, contingent | Closes a documented-but-unbuilt SDK-recommended feature |

**Deprecated/outdated:** nothing in this phase's scope deprecates prior agent86 behavior — MCP-20
and MCP-24 are pure additions to previously-absent capability, not replacements.

## Open Questions

1. **Does "(plus server instructions)" in SC1 require new system-prompt text, or is it satisfied
   by omission when no corpus server populates `InitializeResult.instructions`?**
   - What we know: the field exists in the SDK (`InitializeResult.instructions: str | None`) and is
     currently discarded (`mcp_client.py:961`); `build_system_prompt` has no MCP awareness at all
     today (`cognitive/prompt.py`); ADR 0003 states the requirement in passing, without treating it
     as a major new mechanism.
   - What's unclear: whether any pinned corpus server (`server-everything`, `server-filesystem`,
     `mcp-server-git`, the CI fixture) actually sets `instructions` on its `InitializeResult` — this
     audit did not check. If none do, building the plumbing is speculative work with no way to
     prove it against real evidence in this milestone's corpus.
   - Recommendation: the first plan/task should do a cheap live check (reuse the MCP-07-style
     scratchpad script against `server-everything`/`server-filesystem`, or just print
     `session.initialize()`'s result under the existing test fixtures) to see whether `instructions`
     is ever non-`None` in the corpus. If it's always `None`, implement the capture-and-store
     plumbing (cheap, ~10 lines) but treat "actually render it in the system prompt" as validated
     only by a synthetic test (the CI fixture can set `instructions=` on its own `MCPServer`
     construction) rather than a live-corpus success criterion — and say so explicitly in the plan
     rather than silently declaring SC1 met.

2. **Does `MCPServerConfig` need a new field to opt a server out of schema deferral?**
   - What we know: `MCPServerConfig` currently has no such field; deferral is not currently
     mentioned in `config.py` at all. Phase 13's `connect_timeout_s`/`call_timeout_s`/
     `max_result_chars` all shipped as new per-server fields with `config.py`-only ownership and no
     `/config mcp` form fields (hand-edited TOML), per 13-02's own scope ruling.
   - What's unclear: whether ADR 0003 intends deferral to be unconditional (every MCP tool, every
     server, always deferred until first use) or whether a server whose tools are cheap/few should
     be exempted. ADR 0003's Decision text reads as unconditional ("a future implementer can apply
     this without re-reading this document") with no per-server opt-out mentioned.
   - Recommendation: default to unconditional deferral for every `MCPTool` (not the small, fixed
     `_MCPCapabilityTool` synthetic tools), no new config field, unless the plan's own research step
     finds a corpus server where this materially breaks something (e.g., a provider that validates
     `tools=` shapes strictly at every turn, not just on first use).

3. **Is per-call `progress_callback` wiring in scope at all, given CAP-PROGRESS can close via
   generic `message_handler` observation alone?**
   - What we know: the dispatcher tees `notifications/progress` to `message_handler` unconditionally
     (Code Examples), so CAP-PROGRESS ("agent86 can trigger but not observe") can move to
     `implemented` purely by adding an `isinstance(message, ProgressNotification)` branch — no
     `call_tool`/`_on_session` signature change needed.
   - What's unclear: whether "observe" for the matrix's purposes requires the progress to be
     *attributable* to the specific in-flight tool call that caused it (which DOES need
     `progress_callback` wiring, since the generic `message_handler` path receives the notification
     with no correlation back to which `ToolCall`/step triggered it — only the server-assigned
     `progressToken`, which agent86 never sees since it never mints one).
   - Recommendation: the minimal-scope closure (generic observation via a note, no per-call
     correlation) is sufficient to justify moving the matrix row, and is far cheaper; the plan should
     explicitly scope CAP-PROGRESS to "observed generically, not attributed to a specific tool call"
     and record that scoping in the matrix's Reasoning cell, the same way Phase 13 recorded its own
     scope rulings (e.g., "MCP-21's scope is connect and call timeouts only").

4. **Does the `list_changed`-triggered refetch need to re-run `_capability_tools()` too, or only
   `list_tools()`?**
   - What we know: `_serve_once`'s connect-time tool-building does both — `session.list_tools()`
     for the server's own tools, then `_capability_tools(self, name, session.server_capabilities)`
     for the synthetic resources/prompts/completion tools (`mcp_client.py:962-983`). A
     `ToolListChangedNotification` only concerns `tools/list`; a server's *capabilities* (whether it
     supports `resources`/`prompts`/`completions` at all) do not change mid-session per the spec —
     only the *contents* of those lists change, signaled by their own sibling notifications.
   - What's unclear: whether re-running `_capability_tools()` on every refetch (cheap, idempotent —
     it just re-appends the same fixed synthetic tools if capabilities are unchanged) is simpler
     than trying to reuse the previously-built capability tools list, given the diff/re-registration
     step (`_emit_tools_changed`) needs stable object identity for tools that *didn't* change (so
     they aren't spuriously removed-then-re-added, which would needlessly perturb `ToolRegistry`).
   - Recommendation: on a `ToolListChangedNotification`, only rebuild the server's own `MCPTool`
     list from a fresh `list_tools()` call and re-append the **same, already-constructed**
     `_MCPCapabilityTool` instances (they don't need rebuilding since their identity/behavior never
     changes) — diff only the `MCPTool` portion. On a `ResourceListChangedNotification`/
     `PromptListChangedNotification`, no tool *identity* changes at all (the synthetic
     `list_resources`/`list_prompts` tools are the same objects regardless of what's inside those
     lists) — so those two notifications likely need **no registry mutation whatsoever**, only
     (optionally) a note, since the "list" itself is fetched live on each `list_resources`/
     `list_prompts` tool call anyway. This is a meaningful scope-reduction the plan should confirm
     and state explicitly, since SC3's literal wording ("routes ... into a re-fetch of that server's
     tool list") is written as if all three notifications trigger the same action, which on closer
     reading they should not.

## Environment Availability

No external service/tool dependency beyond what Phases 10-13 already require and have proven
available in this environment.

| Dependency | Required by | Available | Version | Fallback |
|---|---|---|---|---|
| `mcp` Python SDK | All of this phase | Yes | 2.0.0 (pinned, unchanged since Phase 10) | The `mcp` extra already degrades gracefully to zero MCP tools + a note when absent (`_ensure_loop`, `mcp_client.py:813-830`) — this phase adds no new degradation surface |
| `server-everything`/`server-filesystem` (npx) live corpus | Open Question 1's live-check recommendation only | Not verified in this research pass (no live run performed) | `@2026.8.31` per Phase 10/11 pins | If unavailable, the plan should fall back to the CI-safe fixture (`live_mcp_server.py`, no network/npx) for all new tests, exactly as Phase 12/13 already do for their real-stdio proofs |

**Missing dependencies with no fallback:** none.

**Missing dependencies with fallback:** the live npx corpus (only needed for one optional
live-evidence check, not for the phase's core implementation or its CI-safe test suite).

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest + pytest-asyncio (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing, unchanged) |
| Quick run command | `pytest tests/unit/test_mcp.py tests/unit/test_loop.py -q` |
| Full suite command | `pytest -q` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| MCP-20 | A never-called `MCPTool.spec()` returns a stub schema; the same tool's `spec()` returns the real schema after one successful `run()` | unit | `pytest tests/unit/test_mcp.py -k materializ -x` | ❌ Wave 0 — new tests in `tests/unit/test_mcp.py` |
| MCP-20 | `Harness._build_request`'s tool-schema token cost grows on the request immediately following a tool's first call, within the same turn | unit (loop) | `pytest tests/unit/test_loop.py -k defer -x` | ❌ Wave 0 — new tests in `tests/unit/test_loop.py` |
| MCP-20 | A deferred-schema tool still round-trips a real call through at least one non-Anthropic provider adapter shape (Pitfall 1) | unit | `pytest tests/unit/test_providers.py -k mcp_stub_schema -x` (exact file TBD — locate the existing per-provider tool-shape tests first) | ❌ Wave 0 — confirm target test file during planning |
| MCP-24 | A `ToolListChangedNotification` delivered to `_on_message` triggers a re-`list_tools()` and calls `_emit_tools_changed` with the correct added/removed diff | unit | `pytest tests/unit/test_mcp.py -k list_changed -x` | ❌ Wave 0 — extend `_install_fake_transport`'s fake session to accept an injectable notification, mirroring plan 12-01's `_DyingTransport.deliver()` helper (`tests/unit/test_mcp.py`) |
| MCP-24 | The same notification, delivered through a real stdio session against the CI-safe fixture, causes `Harness.registry.names()` to reflect the new tool set with no restart | integration | `pytest tests/integration/test_mcp_client.py -k list_changed -x` | ❌ Wave 0 — extend `tests/integration/live_mcp_server.py` with an opt-in dynamic-tool + `notify_tools_changed()` probe (Code Examples) |
| MCP-24 (CAP-PROGRESS, incidental) | A `ProgressNotification` delivered to `_on_message` produces an observable note (no per-call correlation required, per Open Question 3) | unit | `pytest tests/unit/test_mcp.py -k progress_notification -x` | ❌ Wave 0 |
| SC2 (budget) | Recomputing `_context_budget` after materialisation does not require a new hook — regression-proof by asserting no new call site was added | unit | `pytest tests/unit/test_loop.py -k context_budget -x` (extend existing budget tests rather than adding a new hook) | Partial — `tests/unit/test_loop.py` already has `_context_budget`-adjacent tests from Phase 7; extend, don't replace |
| Docs consistency (no new ADR, no new CAP row for deferral) | `test_docs_consistency.py`'s frozen `CAP-*` ID set and 4-ADR pin must stay green | unit | `pytest tests/unit/test_docs_consistency.py -q` | Yes — pre-existing, unmodified by this phase |
| Scripting contract (additive-only `run --json`) | No existing `REQUIRED_JSON_KEYS` entry removed or repurposed; any new key is additive | integration | `pytest tests/integration/test_scripting_contract.py -q` | Yes — pre-existing, `REQUIRED_JSON_KEYS` at `tests/integration/test_scripting_contract.py:40` |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_mcp.py tests/unit/test_loop.py -q`
- **Per wave merge:** `pytest tests/unit/ tests/integration/test_mcp_client.py tests/integration/test_scripting_contract.py -q`
- **Phase gate:** `pytest -q` full suite green, plus `mypy src/agent86` and `ruff check .` clean —
  matching every prior Phase 10-13 gate exactly.

### Wave 0 Gaps

- [ ] `tests/unit/test_mcp.py` — materialisation tests (spec() before/after first `run()`) and
  `list_changed`/`progress` notification-delivery tests; extend `_install_fake_transport`'s fake
  session with an injectable-notification helper (precedent: plan 12-01's `_DyingTransport.deliver()`)
- [ ] `tests/unit/test_loop.py` — budget-grows-after-materialisation regression test
- [ ] `tests/integration/live_mcp_server.py` — an opt-in (env-gated, matching
  `AGENT86_LIVE_MCP_EXTRA_TOOLS` precedent) dynamic-tool-plus-`notify_tools_changed()` probe for a
  real-stdio `list_changed` integration test
- [ ] `tests/integration/test_mcp_client.py` — the real-stdio `list_changed` round-trip test
  consuming the above fixture addition
- [ ] Locate (don't create blind) the existing per-provider tool-shape test file(s) —
  `tests/unit/test_providers.py` or similar — to add the deferred-stub-schema round-trip test
  (Pitfall 1); this research pass did not confirm the exact file name
- [ ] Framework install: none — pytest/pytest-asyncio already present

## Sources

### Primary (HIGH confidence — direct code read, this session, 2026-09-24)

- `src/agent86/tools/mcp_client.py` (full file, 1714 lines) — `MCPTool`, `_MCPCapabilityTool`,
  `_serve_once`/`_serve`, `_on_message`, `on_tools_changed`/`_emit_tools_changed`, `MCPManager`
- `src/agent86/orchestration/loop.py` (lines 160-600) — `_context_budget`, `_build_request`,
  `_wire_mcp`, `_on_mcp_tools_changed`, `build_system_prompt` call site
- `src/agent86/tools/registry.py` (full file) — `ToolRegistry.specs()`/`register()`/`try_register()`
- `src/agent86/cognitive/prompt.py` (full file) — `build_system_prompt`'s current (no-MCP) content
- `src/agent86/types.py` (lines 95-134) — `ToolSpec`
- `src/agent86/config.py` (lines 260-421) — `MCPConfig`, `MCPServerConfig`
- `.venv/Lib/site-packages/mcp/client/session.py` (lines 160-260, 355-420, 1380-1465) — SDK 2.0.0,
  `MessageHandlerFnT`, `IncomingMessage`, `_on_notify`, `CancelledNotification` non-surfacing
- `.venv/Lib/site-packages/mcp/shared/dispatcher.py` (lines 60-110) — `ProgressFnT`, `CallOptions`
- `.venv/Lib/site-packages/mcp/shared/jsonrpc_dispatcher.py` (lines 105-180, 340-370, 595-660) —
  progress-token correlation, unconditional notification tee
- `.venv/Lib/site-packages/mcp_types/_v2025_11_25/__init__.py` (notification classes,
  `InitializeResult`, `ServerNotification` union) — confirmed via `grep`, not training-data recall
- `.venv/Lib/site-packages/mcp/server/session.py` / `mcp/server/mcpserver/context.py` —
  server-side `send_tool_list_changed`/`notify_tools_changed`
- `docs/adr/0003-mcp-schema-deferral-prompt-contract.md` — the locked ruling
- `docs/mcp-conformance-matrix.md` — current CAP-PROGRESS/CAP-LIST-CHANGED/CAP-LOGGING/
  CAP-CANCELLATION rows and their reasoning cells
- `docs/mcp-conformance-audit-2026-09.md` — Proposed Phase 17 (renumbered 14), sizing rationale
- `.planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/12-01-SUMMARY.md`,
  `12-04-SUMMARY.md` — `on_tools_changed`/`_wire_mcp` build history and design rationale
- `.planning/phases/13-per-server-timeouts-the-result-cap-and-non-text-content/13-02-SUMMARY.md` —
  `MCPServerConfig` field precedent, config.py-read-only precedent
- `tests/integration/live_mcp_server.py` (full file) — CI fixture's current tool/resource/prompt
  surface and its opt-in-extra-tools precedent
- `tests/integration/test_scripting_contract.py` (lines 36-40) — `REQUIRED_JSON_KEYS` additive
  contract

### Secondary (MEDIUM confidence)

- None — every claim above was verified against either the installed SDK source or this
  repository's own code/docs during this research pass.

### Tertiary (LOW confidence, flagged for validation)

- Whether any pinned corpus server (`server-everything`, `server-filesystem`, `mcp-server-git`)
  populates `InitializeResult.instructions` — not checked live in this pass (Open Question 1).
- The exact test file housing per-provider tool-shape/round-trip tests for the Pitfall 1 stub-schema
  regression test — not located in this pass (Wave 0 Gaps).

## Metadata

**Confidence breakdown:**
- Standard stack (no new deps): HIGH — verified installed version directly
- Architecture (materialisation flag, `_on_message` reuse of Phase 12 plumbing): HIGH — read the
  exact call chain (`registry.specs()` → `_build_request` → `_context_budget`) and confirmed object
  identity is preserved through `try_register`/`register`
- Notification routing semantics (progress unconditional tee, cancelled never-surfaced): HIGH — read
  the installed SDK's dispatcher and session source directly, not recalled from training data
- Server-instructions gap (Open Question 1): MEDIUM — the code-gap claim is HIGH confidence; whether
  it matters in practice (any corpus server sets `instructions`) is unverified, hence flagged
- Pitfall 1 (provider schema validation strictness): MEDIUM — the concern is well-founded from
  `ToolSpec`'s own existing default-schema precedent, but no live per-provider test was run this pass

**Research date:** 2026-09-24
**Valid until:** ~30 days, or immediately upon any `mcp` SDK version bump (this research is tied to
exact line numbers in the installed 2.0.0 package) or any change to `mcp_client.py`'s `_serve_once`/
`_on_message` shape from a future plan
