# Phase 12: Fix the zombie-tool desync and add reconnect - Research

**Researched:** 2026-09-24
**Domain:** `agent86.tools.mcp_client` — MCP client session lifecycle (Tier 4), `anyio`/`mcp` SDK 2.0.0 internals
**Confidence:** HIGH (grounded in the installed SDK's own source and a real, empirical kill-the-subprocess experiment against the pinned live fixture — not training-data recall)

No `CONTEXT.md` exists for this phase (`.planning/phases/12-fix-the-zombie-tool-desync-and-add-reconnect/` contains only `.gitkeep`), so there are no locked user decisions to reproduce verbatim. `.planning/config.json` has `workflow.nyquist_validation: true`, so a Validation Architecture section is included.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-26 | The session/registry desync on server death fixed | "The empirical correction" and "Architecture Patterns" below give the actual failure mode (verified by killing a real subprocess) and the `message_handler` hook needed to detect it at all — the roadmap's literal SC1 wording describes a code path that does not fire today. |
| MCP-23 | Reconnect after a dropped transport | "Architecture Patterns" gives the retry/backoff design (reusing `backoff_delay`'s math, not its cross-tier import) and the deliberate-stop-vs-drop distinction needed so `stop_server()`/`close()` are never treated as a failure worth retrying. |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tool execution must never raise** — `MCPTool.run`/`_MCPCapabilityTool` subclasses already wrap `self._manager.call_tool(...)` in `try/except Exception` and return a soft `ToolResult(ok=False, error=...)`. Any change to `call_tool`/`_on_session`'s error message must stay inside that contract; do not let a death-detection change raise past the tool boundary.
- **Lazy imports** — Textual/keyring/tomlkit rule doesn't apply here (`mcp` is already lazily imported per `_ensure_loop`/`_serve`); do not move any `mcp` import to module top-level.
- **`config.py` is read-only; `config_writer.py` owns TOML write-back** — if the plan adds any new `MCPServerConfig`/`MCPConfig` field (see Open Question 2 below on whether reconnect bounds belong in config), the field is defined in `config.py` but any UI/CLI write path must go through `config_writer.py`, never serialize TOML itself.
- **API keys never stored in config; only `api_key_env`/`${VAR}` references** — not directly touched by this phase, but `_resolve_server_secrets` runs once per `start_server`/reconnect attempt (see Pitfall 5) and must keep resolving fresh, never caching a resolved secret across a reconnect.
- **No new core dependency; `mcp` extra stays optional; cold-start unaffected; `run --json` keys additive-only** — restated from the roadmap's own Risk/constraint line; the fix must not add a dependency (retry/backoff math can be hand-derived or reused, see Don't Hand-Roll) and must not run any of this code before a session is running (server-death handling only fires post-connect).
- **GSD workflow enforcement** — implementation must happen via `/gsd:execute-phase`, not direct edits.

## Summary

The roadmap and the Phase 10 audit describe the zombie-tool defect as: a dying server's task exits through `except BaseException` after `ready` resolves, and the shared `finally` pops `self._sessions[name]` but not `self._server_tools[name]`. That description is **half right and half empirically wrong**, confirmed by actually killing the pinned `tests/integration/live_mcp_server.py` subprocess mid-session against the current code (script and full transcript below, "The empirical correction"). The `finally` block popping `self._sessions[name]` is real code (`mcp_client.py:501-502`), but it **never runs** on a real transport drop: the owning task hangs forever at `await close_event.wait()`, both `self._sessions[name]` and `self._server_tools[name]` stay populated indefinitely, and `call_tool()` does raise — but with `mcp.shared.exceptions.MCPError: Connection closed`, not the generic `RuntimeError("MCP session not available")` the roadmap's SC2 describes. The root cause: `ClientSession(read, write)` is built with no `message_handler`, and the SDK's default handler (`_default_message_handler`) is a true no-op for **both** server notifications and transport-level exceptions — `IncomingMessage: TypeAlias = types.ServerNotification | Exception`, and the installed SDK explicitly funnels stream failures into `message_handler`, not into a raise at the task's own cancel scope. Without a `message_handler` that reacts to the `Exception` branch, `_serve` has no way to ever learn the transport died, so neither the finally-block fix nor a retry loop can fire — this is the load-bearing finding for both MCP-26 and MCP-23, and it means the two requirements share one root fix, not two independent ones.

**Primary recommendation:** Pass a `message_handler` to `ClientSession(read, write, message_handler=...)` in `_serve` whose `Exception` branch resolves a "died" signal (e.g. a future/event raced against `close_event` via `asyncio.wait(..., return_when=FIRST_COMPLETED)`), leave its `ServerNotification` branch a no-op exactly as today (don't scope-creep into MCP-24/Phase 17's `list_changed` routing). On a died-signal, pop both `self._sessions[name]` and `self._server_tools[name]` together (satisfying the literal SC1 wording once the code path can actually reach it), then retry with a bounded attempt count and `agent86.cognitive.retry`-style exponential-backoff-with-jitter math (reuse the *formula*, not a cross-tier import — see Don't Hand-Roll) before giving up; on give-up, leave the manager in the same "server absent" state `stop_server()` already produces. Rewrite `call_tool`'s and `_on_session`'s generic `RuntimeError("MCP session not available")` to name the server explicitly and distinguish "never connected" from "disconnected, reconnecting" from "disconnected, gave up."

## The empirical correction

Reproduced against the real pinned fixture (`tests/integration/live_mcp_server.py`, git SHA `b64e79a`), stdio transport, `mcp==2.0.0`, `anyio==4.14.2`, Python 3.12.10, from a throwaway scratchpad script (never committed, mirroring Phase 10's D-03 evidence-gathering precedent):

1. `manager.start_server("alpha", cfg, timeout=30.0)` — 9 tools mounted, `sessions=['alpha']`, `server_tools=['alpha']`.
2. The `live_mcp_server.py` child process is killed via `Stop-Process -Force` (simulating a real crash, not a graceful `stop_server()`).
3. Observed for 20 seconds: `manager._tasks["alpha"].done()` stays **`False`** the entire time — the owning task never exits, never enters `except BaseException`, never reaches `finally`.
4. `self._sessions["alpha"]` and `self._server_tools["alpha"]` are **both still populated** at every sampled second — not just `_server_tools`.
5. `manager.call_tool("alpha", "add", {"a": 1, "b": 1})` **does** raise, but as `mcp.shared.exceptions.MCPError: Connection closed` — routed through `session.call_tool(...)` itself (the `server not in self._sessions` guard never fires, because the session dict entry is never removed), not the `RuntimeError` the roadmap's SC2 names.

**Why:** `mcp/client/session.py`'s `ClientSession.__init__` builds a `JSONRPCDispatcher(read_stream, write_stream, on_stream_exception=self._on_stream_exception)`. `_on_stream_exception` spawns `_deliver_stream_exception(exc)`, which calls `await self._message_handler(exc)` — **it does not cancel the task group or raise into the caller's scope.** `message_handler` defaults to `_default_message_handler(message: IncomingMessage) -> None: await anyio.lowlevel.checkpoint()`, a true no-op for both a `ServerNotification` and an `Exception` (`IncomingMessage: TypeAlias = types.ServerNotification | Exception`, `session.py:199,208-213`). agent86's `_serve` builds `ClientSession(read, write)` with every callback at default (`mcp_client.py:471`), so a transport-level fault is delivered to a handler that does nothing with it. `await close_event.wait()` (`mcp_client.py:497`) has no other reason to wake up, so it parks forever.

**What this changes for planning:** SC1's literal wording ("the finally block that already pops `self._sessions[name]`") describes code that is syntactically present but not reachable from the actual failure mode this phase exists to fix. A plan that only adds `self._server_tools.pop(name, None)` next to the existing `self._sessions.pop(name, None)` in the current `finally` (`mcp_client.py:501-502`) will pass a narrow unit test using a fake transport that raises synchronously (see Validation Architecture), but will **not** fix the real bug: a killed stdio subprocess, or a dropped SSE/HTTP connection, will still hang the task forever with no `message_handler`. The `message_handler` hookup is not optional scope for MCP-23 alone — it is the precondition for MCP-26's fix to ever run.

## Architecture Patterns

### Current shape (`src/agent86/tools/mcp_client.py`, as of `b64e79a`)

```
MCPManager
├── start_server()/_launch()        → creates the owning asyncio.Task via _serve()
├── _serve(name, cfg, ready, close_event)   ← the task every server owns for its whole life
│     async with AsyncExitStack() as stack:
│         streams = await stack.enter_async_context(_open_transport(...))
│         session = await stack.enter_async_context(ClientSession(read, write))  # <- no message_handler
│         await session.initialize(); listed = await session.list_tools()
│         self._sessions[name] = session          # line 493
│         self._server_tools[name] = tools         # line 494
│         if not ready.done(): ready.set_result(tools)
│         await close_event.wait()                 # line 497 — parks here for the server's life
│     except BaseException as exc:                 # line 498 — only reached pre-`ready` or on a
│         if not ready.done(): ready.set_exception(exc)   #  cooperative cancellation today
│     finally:
│         self._sessions.pop(name, None)            # line 502 — NOT self._server_tools
├── stop_server()   → close_event.set(); await task  — the ONLY path that pops _server_tools today (line 508)
├── call_tool()/_on_session()  → `if server not in self._sessions: raise RuntimeError("MCP session not available")`
└── tools_for()/tools()  → read self._server_tools
```

Both `MCPTool.run` (server-schema tools) and every Phase 11 `_MCPCapabilityTool` subclass (`list_resources`, `read_resource`, `list_prompts`, `get_prompt`, `complete`, `subscribe_resource`/`unsubscribe_resource`) route through `call_tool`/`_on_session`'s identical guard — fixing the error message in one place fixes it for all nine-per-server tools, confirming the roadmap's own note that Phase 11's capability tools "widen the desync."

### Recommended pattern: `message_handler`-driven death detection + bounded retry

Illustrative sketch (not literal final code — the planner should size this into tasks, and the exact control flow is an implementation decision, not a research one):

```python
# Source: derived from mcp/client/session.py's IncomingMessage = ServerNotification | Exception
# (installed SDK 2.0.0, .venv/Lib/site-packages/mcp/client/session.py:199-213)
async def _serve(self, name, cfg, ready, close_event) -> None:
    from contextlib import AsyncExitStack
    ClientSession = _get_client_session()
    attempt = 0
    while True:
        died: asyncio.Future = asyncio.get_running_loop().create_future()

        async def _on_message(message):
            if isinstance(message, Exception):
                if not died.done():
                    died.set_exception(message)
            else:
                await anyio.lowlevel.checkpoint()  # unchanged no-op; list_changed is Phase 17/MCP-24

        try:
            async with AsyncExitStack() as stack:
                streams = await stack.enter_async_context(_open_transport(cfg, self.env_passthrough))
                read, write = streams[0], streams[1]
                session = await stack.enter_async_context(
                    ClientSession(read, write, message_handler=_on_message)
                )
                await session.initialize()
                listed = await session.list_tools()
                tools = [...]  # unchanged
                tools.extend(_capability_tools(self, name, getattr(session, "server_capabilities", None)))
                self._sessions[name] = session
                self._server_tools[name] = tools
                if not ready.done():
                    ready.set_result(tools)
                    attempt = 0  # a successful (re)connect resets the retry budget
                else:
                    self._add_note(f"MCP server '{name}' reconnected after a dropped transport.")
                stop_task = asyncio.ensure_future(close_event.wait())
                try:
                    done, pending = await asyncio.wait(
                        {stop_task, died}, return_when=asyncio.FIRST_COMPLETED
                    )
                finally:
                    for p in pending:
                        p.cancel()
                if died in done:
                    died.result()  # re-raises the delivered Exception into the except below
                # else: close_event fired first -> deliberate stop_server()/close(), fall through
        except BaseException as exc:
            self._sessions.pop(name, None)
            self._server_tools.pop(name, None)  # SC1: popped alongside _sessions, every exit path
            if not ready.done():
                ready.set_exception(exc)
                return  # unchanged: connect-time failure still raises to start_server(), no retry
            if close_event.is_set():
                return  # a deliberate stop that raced the died-future; not a failure to retry
            attempt += 1
            if attempt > _MAX_RECONNECT_ATTEMPTS:
                self._add_note(
                    f"MCP server '{name}' disconnected and reconnect failed after "
                    f"{_MAX_RECONNECT_ATTEMPTS} attempts: {exc}"
                )
                return
            self._add_note(f"MCP server '{name}' disconnected ({exc}); reconnecting "
                            f"(attempt {attempt}/{_MAX_RECONNECT_ATTEMPTS})...")
            await asyncio.sleep(_reconnect_backoff(attempt))
            continue
        else:
            self._sessions.pop(name, None)
            self._server_tools.pop(name, None)
            return  # clean, deliberate shutdown (stop_server()/close())
```

Notes on this sketch, for the planner:
- `_reconnect_backoff` should be `min(base * 2**attempt, cap) / 2 + jitter` — the same shape as `agent86.cognitive.retry.backoff_delay`, but see Don't Hand-Roll below on **why to duplicate the formula rather than import it**.
- The `stop_task`/`died` race via `asyncio.wait(..., return_when=FIRST_COMPLETED)` is the mechanism that lets `_serve` distinguish "the user called `stop_server()`" (do not retry) from "the transport died" (retry) — both would otherwise look identical once `close_event.wait()` alone is the only signal. `close_event.is_set()` is checked again inside the `except` as a second guard for the race where `died` and `close_event` resolve in the same tick.
- `_resolve_server_secrets` is applied once in `start_server()` before `_launch()`, not inside `_serve`'s loop (`mcp_client.py:431`) — a reconnect attempt must re-resolve `${VAR}` secrets fresh (Pitfall 5), which likely means passing the already-resolved `cfg` into the loop is fine for stdio env/headers that don't rotate, but a token-based auth header that expired between connect and reconnect would need re-resolution. No corpus server in this phase's scope uses rotating credentials (that's workstream B), so re-using the resolved `cfg` across reconnect attempts is acceptable for this phase — flag as an explicit non-goal in the plan rather than leaving it implicit.

### Cross-cutting: `MCPManager` has no reference to `ToolRegistry`

`Harness.__init__` (`src/agent86/orchestration/loop.py:186-195`) builds `self.mcp = build_mcp(config)`, takes a **one-time snapshot** `mcp_tools = self.mcp.tools()`, and hands that snapshot to `default_registry(...)`, which copies each `Tool` object into `ToolRegistry._tools` (a private dict `tools/registry.py:43`). From that point on, `ToolRegistry` and `MCPManager._server_tools` are two **independent** stores — `ToolRegistry.specs()` (what the compiled system prompt and `_build_request` actually offer the model) never re-reads `MCPManager._server_tools`. The only code that keeps them in sync is the *explicit*, user-initiated `Harness.add_mcp_server`/`remove_mcp_server` (`loop.py:321-357`), which the TUI's `/config mcp` add/remove/disable flow calls directly — `remove_mcp_server` walks `self.mcp.tools_for(name)` and calls `self.registry.unregister(tool.name)` for each.

**This means popping `MCPManager._server_tools[name]` on death (SC1, as literally worded) stops `MCPManager.tools_for()`/`tools()` from listing the dead server's tools, but does NOT remove them from `self.registry` or the compiled system prompt** — nothing today calls `Harness.remove_mcp_server`-equivalent logic automatically on an unexpected server death. The model would still see the tool advertised (registry unchanged) and would still be able to call it; the improved error message (SC2) is what it would receive instead of a working result. This is consistent with the Goal's "not left callable-but-broken" in spirit (a *clear, actionable* error rather than a *generic* one) but not with "tools unregistered" read literally as "no longer offered to the model." See Open Question 1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff with jitter | A new formula from scratch | The *shape* of `agent86.cognitive.retry.backoff_delay(attempt)` (`min(_BASE_DELAY_S * 2**attempt, _MAX_DELAY_S) / 2 + jitter`) | Already reviewed, tested (`tests/unit/test_retry.py`), and battle-tested since v0.7 (REL-03) for the identical "transient failure, retry with backoff" shape. |
| Detecting "is the transport still alive" | Polling, heartbeats, manual `process.poll()` | `ClientSession`'s own `message_handler` hook (`IncomingMessage = ServerNotification \| Exception`) | The SDK already funnels every transport-level fault through this exact seam (`_on_stream_exception` → `_deliver_stream_exception` → `message_handler`); building a separate liveness check would duplicate what the SDK already detects and race with it. |
| ExceptionGroup unwrapping (if retry logic inspects exception *type*, e.g. to decide retryable-vs-not) | Manual `isinstance` checks assuming a bare exception | `except*` (Python 3.11+ native syntax; `requires-python = ">=3.11"`) or explicit `.exceptions` unwrapping | anyio task groups can deliver `BaseExceptionGroup` when more than one child task fails simultaneously; a bare `except SomeType` silently never matches a wrapped group. This phase's design mostly avoids the problem (the `died` future carries the exact `Exception` `message_handler` received, not a raw task-group failure), but any code that also inspects exceptions surfacing directly from `AsyncExitStack.__aexit__` (e.g. on `stop_server`'s own path) should account for this. |

**Key insight:** this phase's failure mode is not "we don't have retry infrastructure" (we do, in `cognitive/retry.py`) — it's "we don't have a way to *observe* the failure at all" (the SDK's default `message_handler` silently absorbs it). Don't reach for retry tooling before wiring the observation seam; a bounded loop around a signal that never fires is not a fix.

### On reusing `cognitive/retry.py` directly (architectural layering)

`grep`-ing `src/agent86/tools/` for `from agent86.cognitive` returns **zero matches** — there is no existing precedent for Tier 4 (`tools/`) importing from Tier 3 (`cognitive/`). `docs/ARCHITECTURE.md`'s tier ordering (Gateway → Orchestration → Cognitive → Tools → Guardrails/Observability) implies dependencies flow downward (Orchestration depends on Cognitive, Cognitive depends on Tools); an import from `tools/mcp_client.py` to `cognitive/retry.py` would be the only backward (Tools → Cognitive) dependency in the codebase. `backoff_delay(attempt, *, jitter=...)` is a small, pure, dependency-free function (9 lines), so the lower-risk option is to **duplicate the formula locally** in `mcp_client.py` (or a small shared Tier-4/Tier-independent module) rather than import across tiers — flagged as Open Question 3 for the planner to rule on explicitly rather than silently importing across the boundary.

## Common Pitfalls

### Pitfall 1: Assuming the `finally` block already fires on death
**What goes wrong:** A fix that only adds `self._server_tools.pop(name, None)` next to the existing `self._sessions.pop(name, None)` in `_serve`'s current `finally` (`mcp_client.py:501-502`) looks correct by inspection and will pass a unit test built on the existing `_install_fake_transport` helper (whose `__aexit__` and `close_event.wait()` behave synchronously/cooperatively) — but does not fix a real dropped transport, because that `finally` is never reached without a `message_handler` hookup (see "The empirical correction").
**Why it happens:** Reading the code (as the Phase 10 audit did) suggests the `except BaseException`/`finally` path is the death path; only running it against a real killed process reveals it isn't reached.
**How to avoid:** Any Wave 0 test suite for this phase must include a real-process-kill integration test (see Validation Architecture), not only a fake-transport unit test.
**Warning signs:** A unit test passes with a fake transport that raises synchronously inside the `async with` body, but a manual repro (kill `live_mcp_server.py`'s PID) still hangs.

### Pitfall 2: Treating `stop_server()`/`close()` as a failure worth retrying
**What goes wrong:** If the retry loop only checks "did an exception surface," a deliberate `stop_server()` call (which sets `close_event` and awaits the task) could race with the `died` future's resolution and be misclassified as a drop, triggering an unwanted reconnect attempt on a server the user just explicitly disabled/removed.
**Why it happens:** `close_event.set()` and any late-arriving transport-level exception from the SDK's teardown (`stdio_client`'s own `shutdown()` closes streams, which can itself surface `anyio.ClosedResourceError`/`BrokenResourceError` noise) can land in the same tick.
**How to avoid:** Check `close_event.is_set()` before deciding to retry, and treat `stdio_client.py`'s own documented teardown noise (`ClosedResourceError` during its own `shutdown()`) as expected, not a signal.
**Warning signs:** `stop_server("alpha")`/`remove_mcp_server("alpha")` in a test or the TUI causes an unexpected "reconnecting..." note or a lingering task after `stop_server` returns.

### Pitfall 3: `MCPError` is not exclusively a "connection closed" signal
**What goes wrong:** `mcp.shared.exceptions.MCPError` (`.venv/Lib/site-packages/mcp/shared/exceptions.py`) is the SDK's general "the peer answered with a JSON-RPC error" exception — a live, healthy server returning "tool not found" or a validation error also raises `MCPError`. `call_tool()` cannot assume "any `MCPError` means the server died."
**Why it happens:** The empirical repro's `MCPError: Connection closed` message text is specific to this scenario, but the exception *type* is shared with ordinary protocol errors.
**How to avoid:** Base the "server X is dead" message on manager-level state (a flag set by the `message_handler`'s `died` signal, or the post-fix absence from `self._sessions`/`self._server_tools`), not on sniffing the exception's type or message text in `call_tool`.
**Warning signs:** A legitimate "tool not found" error from a healthy server gets rewritten to say "server X has disconnected."

### Pitfall 4: Cross-thread mutation of `ToolRegistry` (if the plan wires death detection into `Harness.registry`)
**What goes wrong:** `_serve` runs on `MCPManager`'s own background event-loop thread (`_run_loop`, `mcp_client.py:541-544`), a **different thread** than the one driving `run_turn`/`_build_request`, which reads `self.registry.specs()`/`self.registry._tools`. If Open Question 1 is resolved by having death-detection call `self.registry.unregister(name)` directly from the MCP loop thread, that is a concurrent mutation of a plain `dict` (`ToolRegistry._tools`) with no lock — `Harness` already uses `threading.Lock` for cross-thread accumulation elsewhere (`self._subagent_usage_lock`, `loop.py:229`), establishing the project's own precedent for this exact class of hazard.
**Why it happens:** `MCPManager` and `Harness`/`ToolRegistry` were designed as separately-owned components wired together only at explicit call sites (`add_mcp_server`/`remove_mcp_server`), not via a live callback — an automatic-unregister-on-death feature is new coupling this phase would introduce.
**How to avoid:** If the plan chooses to close the registry gap (see Open Question 1), route the unregister through a thread-safe mechanism (a lock, or deferring the mutation to the main thread at the next safe point — e.g. checked at the top of `run_turn`), not a bare cross-thread `dict.pop`.
**Warning signs:** An intermittent `RuntimeError: dictionary changed size during iteration` from `ToolRegistry.specs()`/`names()`, or a flaky test only failing under load/timing pressure.

### Pitfall 5: Secrets are resolved once, at `start_server()`, not inside the reconnect loop
**What goes wrong:** `_resolve_server_secrets(cfg, overrides)` runs in `start_server()` before `_launch()` (`mcp_client.py:431`), producing the `cfg` object `_serve` is called with. If reconnect re-enters the connect logic *inside* `_serve` (as the sketch above does, re-using the same already-resolved `cfg` across attempts), a `${VAR}` that legitimately changes value between the original connect and a later reconnect (e.g. a rotated header) would not be picked up.
**Why it happens:** The resolve-once-then-pass-down shape predates this phase and was correct for the non-reconnecting design.
**How to avoid:** Explicitly scope this out (no corpus server in Phase 12's scope has rotating credentials — that's workstream B/OAuth) rather than silently re-resolving or silently not re-resolving; state the decision in the plan.
**Warning signs:** None expected to surface in this phase's own tests; flagged for the plan to rule on rather than discover mid-implementation.

## Code Examples

### The SDK's own detection seam (verified against the installed package, HIGH confidence)

```python
# Source: .venv/Lib/site-packages/mcp/client/session.py:199,208-213 (mcp==2.0.0, installed)
IncomingMessage: TypeAlias = types.ServerNotification | Exception

class MessageHandlerFnT(Protocol):
    async def __call__(self, message: IncomingMessage) -> None: ...

async def _default_message_handler(message: IncomingMessage) -> None:
    await anyio.lowlevel.checkpoint()  # true no-op for BOTH notifications and transport exceptions
```

```python
# Source: .venv/Lib/site-packages/mcp/client/session.py:1449-1462
async def _on_stream_exception(self, exc: Exception) -> None:
    """Deliver a transport-level fault to message_handler via a spawned task.

    Running the handler inline would park the dispatcher's read loop and
    deadlock handlers that await session I/O.
    """
    assert self._task_group is not None
    self._task_group.start_soon(self._deliver_stream_exception, exc)

async def _deliver_stream_exception(self, exc: Exception) -> None:
    try:
        await self._message_handler(exc)
    except Exception:
        logger.exception("message_handler raised on transport exception")
```

This confirms `message_handler` is the SDK's sanctioned integration point for exactly this problem — it is not an internal/undocumented detail; `ClientSession.__init__` accepts `message_handler: MessageHandlerFnT | None = None` as a public constructor parameter (`session.py:380`).

### Existing retry/backoff shape to mirror (not import — see Don't Hand-Roll)

```python
# Source: src/agent86/cognitive/retry.py:116-124 (v0.7, REL-03)
def backoff_delay(attempt: int, *, jitter: Callable[[float, float], float] | None = None) -> float:
    """Exponential backoff with equal jitter: half the window fixed, half random."""
    window = min(_BASE_DELAY_S * (2**attempt), _MAX_DELAY_S)
    rand = jitter or random.uniform
    return window / 2 + rand(0.0, window / 2)
```

Note `RetryPolicy._wait` uses the blocking `time.sleep` (via the `sleep()` indirection) — that is correct for `cognitive/retry.py`'s synchronous provider-call context but **must not** be reused as-is inside `_serve`, which runs on `MCPManager`'s dedicated asyncio event loop; the equivalent must be `await asyncio.sleep(delay)`.

## Open Questions

1. **Does closing the `MCPManager` ↔ `ToolRegistry` gap belong in this phase, or is the improved error message (SC2) sufficient for now?**
   - What we know: `Harness.add_mcp_server`/`remove_mcp_server` already show the pattern (`manager.tools_for(name)` → `self.registry.unregister(tool.name)`), so the code shape to copy exists. `MCPManager` has no reference to `ToolRegistry` today, and wiring one in crosses a thread boundary (Pitfall 4) that needs a lock or a deferred-to-main-thread mechanism.
   - What's unclear: whether the roadmap's Goal text ("has its tools unregistered") requires the tool to disappear from the model's advertised tool list (registry-level), or whether a `MCPManager`-only fix plus a clearly-named error (SC2, satisfiable without touching `ToolRegistry`) is what the phase's Success Criteria, read literally (they only name `MCPManager`/`tools_for()`/`tools()`), actually require.
   - Recommendation: size this as an explicit decision point in the plan's first task, not an assumption. The literal Success Criteria as roadmapped are satisfiable at the `MCPManager` layer alone; closing the `ToolRegistry` gap is a larger, thread-safety-sensitive change that could be its own follow-on if the planner judges it out of this phase's bounded scope (the roadmap's Risk/constraint line only mentions `_serve`'s task lifecycle, not `ToolRegistry`).

2. **Do the retry bound and backoff parameters belong in `MCPServerConfig`, or are they hardcoded constants for this phase?**
   - What we know: `_on_session`'s own comment explicitly defers per-server timeout configuration to MCP-21 ("a second timeout knob here would pre-empt that ruling"), and Proposed Phase 16 (not 12) is where `MCPServerConfig` gains `connect_timeout_s`/`call_timeout_s`. The roadmap's Proposed Phase 15 (renumbered 12) text says only "a bounded number of times with backoff," naming no config surface.
   - What's unclear: whether "bounded" should be a fixed constant (matching the existing hardcoded 30s/120s precedent this phase inherits) or a new config field, which would need to go through `config_writer.py` for any UI write path.
   - Recommendation: hardcode a small constant (e.g. 3-5 attempts, capped backoff matching `cognitive/retry.py`'s `_MAX_DELAY_S = 30.0` shape) for this phase, consistent with the "no scope creep into MCP-21" precedent already set in this file. Revisit if Phase 16 wants a unified per-server timeout/retry config block.

3. **Duplicate `backoff_delay`'s formula locally, or accept a Tools→Cognitive import as this phase's one exception?**
   - What we know: no existing precedent for `tools/` importing `cognitive/`; the function is small and pure.
   - What's unclear: whether the project considers this tier boundary a hard rule or a soft convention (ARCHITECTURE.md's tier list is stated as a data-flow shape, not an explicit "must never import upward" rule — I could not find an explicit statement of that rule in the files read for this research).
   - Recommendation: duplicate the ~9-line formula locally in `mcp_client.py` with a comment crediting `cognitive/retry.py` as the pattern source. Lowest-risk, avoids introducing the only backward-tier import in the codebase.

4. **Does the fix need to be verified against a non-stdio transport (SSE/streamable HTTP), given the phase description's explicit call-out?**
   - What we know: `message_handler`/`IncomingMessage` detection happens at the `ClientSession`/dispatcher layer, above the transport (`_open_transport` only selects which stream pair `ClientSession` is built on) — the fix should be transport-agnostic in principle. `tests/integration/test_mcp_live.py` already has a pattern for driving a real SSE/HTTP `live_mcp_server.py` subprocess.
   - What's unclear: whether killing an HTTP/SSE-serving subprocess produces the same `Exception`-to-`message_handler` delivery (httpx-level errors may surface differently than the stdio pipe-close case verified above) — not empirically tested in this research pass, only reasoned about.
   - Recommendation: the plan's Wave 0 evidence-gathering (mirroring this research's own probe) should include at least one non-stdio kill-and-observe pass before the fix is considered SSE/HTTP-verified, not just stdio-verified.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` (the `agent86[mcp]` extra) | All of this phase's code paths | ✓ | 2.0.0 (installed in `.venv`) | Already optional/graceful-degrade per existing `_ensure_loop` design; unaffected by this phase |
| `anyio` | Transport/task-group internals `_serve` depends on | ✓ | 4.14.2 | — (transitive dep of `mcp`) |
| Python | `except*`/native `ExceptionGroup` (if needed, see Don't Hand-Roll) | ✓ | 3.12.10 (project requires `>=3.11`) | — |
| `live_mcp_server.py`'s `mcp.server.mcpserver` | Real-stdio integration tests (existing `_HAS_MCP_SERVER` skipif gate) | ✓ | bundled with `mcp==2.0.0` | Tests already skip cleanly when absent |

No missing dependencies; nothing blocks this phase from proceeding.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`, `pyproject.toml:118-119`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (no separate `pytest.ini`) |
| Quick run command | `pytest tests/unit/test_mcp.py -q` (unit-level, fake transport, no subprocess) |
| Full suite command | `pytest -q` (default excludes `-m packaging`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-26 (SC1) | `_server_tools`/`_sessions` both cleared once a server's task actually detects death | unit (fake `message_handler`-driven exception) | `pytest tests/unit/test_mcp.py -k death -x` | ❌ Wave 0 — extend `_install_fake_transport`/add a fake that delivers an `Exception` via the injected `message_handler` |
| MCP-26 (SC1) | A **real** killed subprocess reproduces the same outcome (not just a synchronous fake) | integration, real stdio | `pytest tests/integration/test_mcp_client.py -k mid_session -x` | ❌ Wave 0 — new test killing `live_mcp_server.py`'s PID after `ready` resolves, mirroring this research's probe script |
| MCP-26 (SC2) | `call_tool`/`_on_session` name the dead server, not a generic message | unit + integration | `pytest tests/unit/test_mcp.py -k named_server -x` and the same real-kill integration test asserting the server name appears in the raised/returned error | ❌ Wave 0 |
| MCP-23 (SC3) | Bounded retries with backoff attempted before giving up; `_add_note` records attempts | unit (fake transport failing N times then succeeding) | `pytest tests/unit/test_mcp.py -k reconnect -x` | ❌ Wave 0 |
| MCP-23 (SC3) | A successful reconnect re-populates `_server_tools` from a fresh `list_tools()`/`server_capabilities` read | unit + integration (real subprocess restarted, or fake transport returning a new tool set on the second attempt) | `pytest tests/unit/test_mcp.py -k reconnect_repopulates -x` | ❌ Wave 0 |
| MCP-23 | `stop_server()`/`close()` are never mistaken for a drop worth retrying (Pitfall 2) | unit + existing integration (`test_independent_teardown_leaves_other_server_intact`, `test_close_after_partial_stop_is_clean` must keep passing unmodified) | `pytest tests/integration/test_mcp_client.py -k "teardown or partial_stop" -x` | ✅ existing, must stay green |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/test_mcp.py -q` (fast, no subprocess spawn)
- **Per wave merge:** `pytest tests/integration/test_mcp_client.py tests/integration/test_mcp_live.py -q` (real stdio + real SSE/HTTP subprocess round trips) plus `pytest -q` for the full suite
- **Phase gate:** Full suite green (`pytest -q`), plus a manual or scripted repro of the empirical probe in this research (kill the fixture mid-session, confirm the task now actually exits/retries instead of hanging) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_mcp.py` — extend `_install_fake_transport` (or add a sibling helper) so a test can trigger the injected `message_handler`'s `Exception` branch *after* `ready` has resolved, to unit-test the death-detection + retry loop without a real subprocess (mirrors the fake-session pattern already at `tests/unit/test_mcp.py:373-456`).
- [ ] `tests/integration/test_mcp_client.py` — a new real-stdio test that starts `live_mcp_server.py`, waits for `ready`, kills the child process (Windows: match this research's `Stop-Process`/PowerShell approach or a cross-platform `process.kill()` if the manager is changed to expose the underlying process handle; POSIX: `os.kill(pid, signal.SIGKILL)`), and asserts (a) the task eventually reaches a terminal/retrying state within a bounded wait, (b) `tools_for()`/`tools()` empty out or repopulate correctly, (c) `call_tool` during the gap names the server.
- [ ] Consider whether `tests/integration/test_mcp_live.py`'s SSE/HTTP fixture needs an equivalent kill-mid-session case (Open Question 4) — at minimum, note it as accepted risk if descoped.
- [ ] No new framework install needed — pytest/pytest-asyncio already cover this; `_HAS_MCP_SERVER` skipif gate already handles environments without the `mcp` extra.

## Sources

### Primary (HIGH confidence)
- `src/agent86/tools/mcp_client.py` (read in full, git SHA `b64e79a`) — the file this phase modifies.
- `src/agent86/orchestration/loop.py:160-357` — `Harness.__init__`, `ensure_mcp`, `add_mcp_server`, `remove_mcp_server` (the `ToolRegistry` coupling finding).
- `src/agent86/tools/registry.py` (read in full) — `ToolRegistry` is an independent, flat dict, confirming the registry-desync gap.
- `src/agent86/cognitive/retry.py` (read in full) — the existing backoff/retry pattern.
- `.venv/Lib/site-packages/mcp/client/session.py` (installed `mcp==2.0.0`, read directly, lines 199-486, 1420-1462) — `IncomingMessage`, `MessageHandlerFnT`, `_default_message_handler`, `_on_stream_exception`, `_deliver_stream_exception`. This is the actual installed SDK, not training-data recall of a possibly different version.
- `.venv/Lib/site-packages/mcp/client/stdio.py` (`stdio_client`, read via `inspect.getsource`) — confirms `stdout_reader`/`stdin_writer` do not raise on subprocess EOF, consistent with the empirical hang.
- `.venv/Lib/site-packages/mcp/shared/exceptions.py` (`MCPError`, read via `inspect.getsource`) — confirms it is a general protocol-error type, not connection-specific (Pitfall 3).
- **Empirical experiment** (this research pass): a throwaway scratchpad script started a real `manager.start_server("alpha", ...)` against the pinned `tests/integration/live_mcp_server.py`, killed the child process via PowerShell `Stop-Process -Force`, and observed the task hang (`done()==False` for 20s), `_sessions`/`_server_tools` both still populated, and `call_tool` raising `MCPError: Connection closed`. Never committed to the repo (matches Phase 10's D-03 precedent for evidence-gathering scripts).
- `tests/unit/test_mcp.py`, `tests/integration/test_mcp_client.py`, `tests/integration/test_mcp_live.py`, `tests/integration/live_mcp_server.py` (all read) — existing test patterns to extend for Wave 0.
- `docs/mcp-conformance-audit-2026-09.md`, `docs/BACKLOG.md` §999.0, `docs/mcp-conformance-matrix.md` "Not rated here", `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` (all read) — phase scope, success criteria, and the "Row 7 in detail"/"Row 8" claims this research corrects.
- `CLAUDE.md` (project root) — project constraints extracted above.

### Secondary / Tertiary
None — no WebSearch/Context7/WebFetch was needed or used; every claim above is grounded in the actually-installed source (this environment's exact `mcp==2.0.0`) or agent86's own code and history, which outranks any external documentation for a pinned-version question like this one.

## Metadata

**Confidence breakdown:**
- Root cause / failure mode (message_handler swallowing transport faults): HIGH — verified by reading the installed SDK's source AND reproducing it against a real killed subprocess, not inferred from either alone.
- Fix design (message_handler + bounded retry + backoff): HIGH on the mechanism (the SDK's own public constructor parameter), MEDIUM on the exact control-flow shape (the sketch is illustrative; race conditions around `close_event`/`died` need the planner's own task-level scrutiny and test coverage, not just this research's sketch).
- `ToolRegistry` desync gap (Open Question 1): HIGH confidence the gap exists (read both files in full); MEDIUM on whether it's in-scope for this phase (a scoping judgment call, not a fact).
- Non-stdio (SSE/HTTP) transport behavior (Open Question 4): LOW — reasoned from architecture (`message_handler` sits above the transport layer) but not empirically verified the way stdio was.

**Research date:** 2026-09-24
**Valid until:** Pinned to `mcp==2.0.0`/`anyio==4.14.2`/git SHA `b64e79a` — revalidate the empirical finding if either dependency is upgraded before this phase is implemented (30 days if unchanged, immediately if `mcp` or `anyio` bump in `pyproject.toml`/lockfile).
