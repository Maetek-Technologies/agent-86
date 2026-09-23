# Phase 10: MCP Conformance Audit - Research

**Researched:** 2026-09-22
**Domain:** MCP (Model Context Protocol) client conformance — spec surface enumeration, code audit,
ADR authorship. No implementation.
**Confidence:** HIGH (code claims — read with file:line citations and one test run for real) /
MEDIUM (spec-surface enumeration and corpus-server feature claims — WebSearch + official docs,
partially cross-verified) / LOW (GitHub hosted remote server internals, OAuth flow specifics — not
independently exercised, no live credentials in this environment)

## Summary

This phase produces documents, not code: a conformance matrix, a pinned five-server corpus record,
four ADRs, and one CI test. The research below front-loads the two things a document-only phase
still needs verified before planning — what the spec actually enumerates on the client side, and
what agent86's real MCP client code actually does — so the planner can write tasks that *fill in*
the matrix and ADRs rather than *discover* the facts they contain. Both were investigated directly
against the installed `mcp` SDK (2.0.0) and `src/agent86/tools/mcp_client.py` in this repository,
not from training-data memory of the MCP spec.

The single most consequential finding: **agent86's installed SDK speaks a materially different
protocol landscape than what "MCP spec" training data assumes.** The SDK ships two eras — a
handshake-based protocol family (`2024-11-05` through `2025-11-25`) and a new "modern" stateless
per-request envelope protocol (`2026-07-28`, the current spec revision as of this research). Because
`ClientSession(read, write)` calls `initialize()` with `protocol_version=LATEST_HANDSHAKE_VERSION`,
agent86 in practice negotiates **`2025-11-25`** — the last handshake-era revision — never
`2026-07-28`. That is a **research-verified fact, not a policy question**: enumerating the matrix
against `2026-07-28`'s wire format (`server/discover`, `_meta`-carried protocol version, no
`initialize` handshake) would describe a protocol agent86's client code cannot currently speak at
all, regardless of any feature-level ruling. This is now Open Question 1, deliberately not answered
here (a ruling, not a fact, belongs in the audit itself), but the matrix's row set and the
"implemented" ratings should be built and read with this split in mind.

Second: the two structural claims in the BACKLOG audit head start were checked against the real
code, not assumed. The `_serve`/`_server_tools` desync is **CONFIRMED** — with file:line evidence,
not just "leaves populated" language. And the "sampling/elicitation/roots are structurally absent"
claim is **confirmed but more precise than the backlog states**: the SDK's `ClientSession` doesn't
error or hang on these — it ships default callbacks that gracefully return
`ErrorData(code=INVALID_REQUEST, message="... not supported")`, and (more importantly) the client
never even *advertises* the capability during `initialize()`, because capability advertisement is
gated on whether a non-default callback was passed. agent86's current behavior is protocol-correct
"we don't do this," not a bug — which matters for how ADR MCP-08/MCP-09 should be framed (a ruling
on whether to build it, not a defect report on why it's missing).

Third: `server-everything`'s README and its `docs/features.md` **confirm with tool-name-level
evidence** that it drives sampling (`trigger-sampling-request`, `trigger-sampling-request-async`),
elicitation (`trigger-elicitation-request`, `trigger-url-elicitation`), and progress
(`trigger-long-running-operation`) — answering MCP-07, the audit's own first task, directly. This
research found the answer; the audit still needs to *run* the server against agent86 and record the
observed behavior as evidence, per the phase's audit-not-assume discipline.

Fourth: the stdio path for `live_mcp_server.py` **already exists and already passes** —
`test_per_server_start_lists_real_tools` in `tests/integration/test_mcp_client.py` drives the real
server over stdio via `MCPManager.start_server`, verified by running it in this session (1 test
passed in 1.38s, no network). MCP-06's new CI test is an *extension* of an already-working pattern
(add one tool that echoes `os.environ`, or read it via a resource), not new plumbing.

**Primary recommendation:** Structure the matrix's row set around the `2025-11-25` spec (what
agent86's SDK can actually negotiate today), but record `2026-07-28`'s existence and its effect
(roots deprecated, `Tool.execution` removed, wider JSON Schema on `output_schema`) as a stated
open question / forward-looking note rather than silently pinning to a superseded revision. Audit
every claim below marked HIGH against the real code before writing the matrix row; do not re-derive
what this research already verified with file:line citations.

## Project Constraints (from CLAUDE.md)

- **Lazy imports**: Textual, keyring, tomlkit must never be imported at module top-level; `run`
  (one-shot) and `--plain` must not pay their import cost. Not directly load-bearing for this
  phase (no code changes to those paths), but the one new test and any doc-generation tooling must
  not add an eager import to a cold-start-sensitive module.
- **Tool execution must never raise** — always return a structured `ToolResult` error. Directly
  relevant to MCP-06's new test: the tool added to `live_mcp_server.py` to echo the environment
  must follow the same discipline the rest of the MCP client code does (agent86's client side
  already wraps `call_tool` failures into soft `ToolResult` errors at
  `src/agent86/tools/mcp_client.py:62-69`).
- **API keys never stored in config** — only `api_key_env` names. Relevant to ADR MCP-08 (sampling
  as third-party spend against `limits.max_cost_usd`) and the OAuth/workstream-B corpus server
  (GitHub hosted remote): any credential handling the audit *describes* (it implements nothing)
  must respect this rule when the ADR sketches a future design.
- **`config.py` is read-only**; TOML write-back lives in `config_writer.py`. Not touched by this
  phase (no config schema changes), but any ADR that sketches a future `MCPServerConfig` field
  (e.g. MCP-11's per-server result cap, MCP-10's schema-deferral toggle) should describe it as a
  future `config.py` schema addition, `config_writer.py` write-back — never propose writing TOML
  from `config.py`.
- **`_no_home_writes` fixture** (`tests/conftest.py:12-14`) blocks flight-recorder writes into the
  real `~/.agent86` during tests. The new MCP-06 test lives in `tests/integration/`, alongside
  `test_mcp_live.py` and `test_mcp_client.py`, which don't go through `Harness` at all (they drive
  `MCPManager` directly) — so this fixture is very likely a non-issue, but confirm the new test
  doesn't construct a `Harness` before assuming so.
- **Windows console UTF-8 reconfigure** in `cli.py` — irrelevant to this phase's document/test
  output, noted only because CLAUDE.md flags it as a standing gotcha.
- **GSD workflow enforcement**: any file edits for this phase (the matrix, the ADRs, the §15
  updates, the one test) should happen inside `/gsd:execute-phase`, not as ad-hoc edits.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-02 | One matrix row per client-side spec capability, implemented/partial/absent | § Client-Side MCP Spec Surface (full capability enumeration, pinned to spec `2025-11-25` with `2026-07-28` noted) and § What agent86 Actually Implements Today (per-capability rating with file:line evidence) |
| MCP-03 | Each row records whether a pinned corpus server exercises the capability | § The Corpus Servers (per-server feature list, with `server-everything`'s sampling/elicitation/progress claim independently verified) |
| MCP-04 | Each row carries an in/out ruling; every "out" lands in ARCHITECTURE.md §15 | § Where the Audit Report and Matrix Should Live (existing §15 table format and insertion pattern, ready to extend) |
| MCP-05 | Five-server corpus recorded by exact version | § The Corpus Servers (versions found for four of five; GitHub hosted server has no version to pin — see Open Question 2) |
| MCP-06 | `live_mcp_server.py` echoes its environment, pinning SEC-04 in CI, no network | § The SEC-04 Environment-Scrubbing Test (concrete extension of an already-passing stdio test, exact mechanism recommended) |
| MCP-07 | Does `server-everything` drive sampling/elicitation/progress — gates MCP-08/09 | § The Corpus Servers → `server-everything` (answered with tool-name evidence: yes, to all three) |
| MCP-08 | ADR: sampling as inversion of control, not a tool | § SDK Callback Reality (confirms current behavior is a protocol-correct declared "not supported," not a defect — reframes what the ADR is ruling on) |
| MCP-09 | ADR: elicitation as a Tier 1 surface | § SDK Callback Reality (same mechanism as MCP-08); § ADR Conventions (format recommendation) |
| MCP-10 | ADR: schema deferral's effect on the prompt contract | § Context Budget & Prompt Contract Interaction (cites the exact `context_budget` derivation and `allowed-tools` gate this ADR must reconcile with) |
| MCP-11 | ADR: where the result cap lives | § `_content_to_text` and the Missing Cap (exact function cited, `structured_content` also unread — relevant scope note for the ADR) |
| MCP-12 | Confirm/correct the nine head-start matrix rows against current code | § The Nine Head-Start Matrix Rows, Verified (each row re-verified against source in this research pass; the `_serve`/`_server_tools` desync is CONFIRMED with line numbers) |
| MCP-13 | Recommended phase breakdown for workstreams A/B/C | § Sizing Signal for Workstreams A/B/C (evidence-based volume signal per workstream, from the same code read) |

</phase_requirements>

## Client-Side MCP Spec Surface

**Spec revision pinned for this research:** `2025-11-25` (the last handshake-era revision, and the
one agent86's installed SDK actually negotiates — see § SDK Callback Reality). The current
published spec revision is **`2026-07-28`** (`modelcontextprotocol.io/specification/versioning`,
fetched 2026-09-22) — a structurally different, stateless per-request-envelope protocol that
replaces the `initialize` handshake with a `server/discover` RPC and moves the protocol version
into the `_meta` field. Confidence: HIGH (fetched live from the spec site and cross-checked against
the installed SDK's own version registry, which independently confirms the same revision list and
marks `2026-07-28` as the sole entry in `MODERN_PROTOCOL_VERSIONS`).

**Client-side capability surface** (source: `modelcontextprotocol.io/specification/2025-11-25/...`
pages by name, cross-checked against `mcp.client.session.ClientSession`'s actual method/parameter
list in the installed SDK — the SDK is the more reliable enumeration since it is code, not prose):

| Capability | Declared via | Client-initiated call | Server-initiated (client responds) |
|---|---|---|---|
| Tools — list | `tools` (implicit) | `list_tools()` (paginated: `PaginatedRequestParams`) | — |
| Tools — call | `tools` (implicit) | `call_tool()` | — |
| Tool annotations | (server metadata) | read from `Tool.annotations` (`title`, `read_only_hint`, `destructive_hint`, `idempotent_hint`, `open_world_hint`) | — |
| Structured/typed tool output | (server metadata) | `CallToolResult.structured_content` (validated against `Tool.output_schema`) | — |
| Resources — list/read | `resources` capability | `list_resources()`, `read_resource()` (paginated) | — |
| Resource templates | `resources` capability | discovered via `list_resource_templates` (part of `resources`) | — |
| Resource subscriptions | `resources.subscribe` | `subscribe_resource()` / `unsubscribe_resource()` | server sends `notifications/resources/updated` |
| Prompts — list/get | `prompts` capability | `list_prompts()`, `get_prompt()` (paginated) | — |
| Completion (argument autocomplete) | `completions` capability | `complete()` | — |
| Sampling | `sampling` capability, `ClientCapabilities.sampling` | — | server sends `sampling/createMessage`; client answers via `sampling_callback` |
| Elicitation | `elicitation` capability, `ClientCapabilities.elicitation` (form + URL modes in `2025-11-25`) | — | server sends `elicitation/*`; client answers via `elicitation_callback` |
| Roots | `roots` capability, `ClientCapabilities.roots` | client sends `notifications/roots/list_changed` when its roots change | server sends `roots/list`; client answers via `list_roots_callback` — **deprecated as of `2026-07-28`, SEP-2577, still fully supported in `2025-11-25`** |
| Logging | `logging` capability | `set_logging_level()` | server sends `notifications/message`; client routes via `logging_callback` |
| Progress notifications | (per-request, `_meta.progressToken`) | attach a progress token to any request | server sends `notifications/progress`; client routes via `message_handler` |
| Cancellation | (per-request) | send `notifications/cancelled` for an in-flight request | — |
| Pagination | (per-list-method) | `params.cursor` on list calls; server returns `nextCursor` | — |
| Ping | (base protocol) | `send_ping()` | — |
| `tools/list_changed` (and `resources/`, `prompts/` siblings) | `*.list_changed` capability flags | — | server sends `notifications/*/list_changed`; client routes via `message_handler` |
| `_meta` | (base protocol, every request/response/notification) | read/write on any typed params object | — |
| Transports | — | stdio (subprocess), Streamable HTTP, SSE (legacy, still supported `2025-11-25`) | — |
| OAuth 2.0 (remote servers) | (HTTP-transport-specific, RFC 8414/9728-based discovery) | authorization-code flow, dynamic client registration, token refresh | — |
| `server/discover` | `2026-07-28` only | replaces the `initialize` handshake in the modern protocol era | — |

Confidence: MEDIUM overall (enumeration cross-checked against two independent sources — spec pages
and SDK method signatures — but not exhaustively re-read against every spec page; the row set
above should be treated as a strong starting point for the matrix, not a substitute for the audit
task of walking each spec page once).

## What agent86 Actually Implements Today

All findings below are read directly from `src/agent86/tools/mcp_client.py` (463 lines) in this
repository, 2026-09-22. Confidence: HIGH — every claim has a file:line citation and, where noted, a
real test run backing it.

| Capability | Rating | Evidence |
|---|---|---|
| Tools — list | Implemented (no pagination) | `mcp_client.py:221` — `listed = await session.list_tools()`, no `params.cursor`, no loop over `nextCursor`. A server that paginates its tool list would silently return only page one. |
| Tools — call | Implemented | `mcp_client.py:286-295`, `call_tool()`, 120s hardcoded timeout |
| Tool annotations | Partial | Only `read_only_hint` is read (`_is_read_only`, `mcp_client.py:96-111`); `title`, `destructive_hint`, `idempotent_hint`, `open_world_hint` are never inspected |
| Structured/typed tool output | Absent | `_content_to_text` (`mcp_client.py:426-434`) iterates `result.content` and reads only `.text`; `CallToolResult.structured_content` (confirmed present on the installed SDK's `CallToolResult`, `mcp_types/_types.py:1474`) is never read |
| Non-text content blocks | Absent (falls through to `str()`) | `mcp_client.py:429-430` — `text = getattr(chunk, "text", None); parts.append(text if text is not None else str(chunk))`. An `ImageContent`/`AudioContent`/`EmbeddedResource` renders as its Python repr, not its actual payload |
| Result size cap | Absent | `_content_to_text` has no length limit anywhere; joins every part uncapped |
| Resources (list/read/subscribe) | Absent | `_serve` (`mcp_client.py:198-243`) calls only `session.initialize()` and `session.list_tools()` — no `list_resources`, `read_resource`, `subscribe_resource` call site anywhere in the file |
| Prompts (list/get) | Absent | Same — no `list_prompts`/`get_prompt` call site |
| Completion | Absent | No `complete()` call site |
| Sampling | Absent, and correctly *declared* absent | `ClientSession(read, write)` (`mcp_client.py:219`) passes no `sampling_callback`; the installed SDK's `_build_capabilities()` (`session.py:591-595`) sets `sampling=None` in `ClientCapabilities` whenever the callback is the SDK default — so agent86 doesn't just fail to answer sampling requests, it never advertises the capability, which is the protocol-correct way to say "not supported" |
| Elicitation | Absent, and correctly declared absent | Same mechanism, `session.py:596-600` |
| Roots | Absent, and correctly declared absent | Same mechanism, `session.py:601-608` |
| Logging | Absent (default no-op) | No `set_logging_level()` call; `logging_callback` unset → SDK default `_default_logging_callback` is a no-op (`session.py:245-248`) |
| Progress notifications | Absent | No progress token attached to any request; no `message_handler` passed, so even an unsolicited `notifications/progress` is dropped (see next row) |
| `tools/list_changed` / notifications generally | Absent — every notification dropped | No `message_handler` passed to `ClientSession(read, write)`; SDK default `_default_message_handler` is `await anyio.lowlevel.checkpoint()` — a true no-op (`session.py:212-213`) |
| Cancellation (client-initiated) | Absent | No `notifications/cancelled` send site |
| Pagination | Absent | See "Tools — list" row; same gap would apply to resources/prompts if those were implemented |
| Ping | Absent | No `send_ping()` call site |
| `_meta` | Not read or written by agent86's own code (SDK carries it internally for protocol negotiation) | No direct `_meta` access in `mcp_client.py` |
| Transports | Implemented: stdio, SSE, streamable HTTP | `_open_transport` (`mcp_client.py:395-423`) — all three, matching ARCHITECTURE.md §7's claim |
| OAuth 2.0 (remote servers) | Absent | Auth is `headers` + `${VAR}` only (`_resolve_server_secrets`, `mcp_client.py:336-358`); no discovery, no token storage, no refresh |
| Per-server configurable timeouts | Absent | `MCPConfig` (`src/agent86/config.py:293-294`) carries only `enabled: bool`; `start_server`'s `timeout: float = 30.0` (`mcp_client.py:166`) and `call_tool`'s hardcoded `timeout=120` (`mcp_client.py:295`) are both fixed in code, not config |
| Reconnect after dropped transport | Absent | `_serve` (`mcp_client.py:198-243`) parks on `await close_event.wait()`; there is no retry/reconnect path — a dropped transport ends the task and the `except BaseException` only fires before `ready` resolves, not after |
| Env scrubbing for stdio servers (SEC-04) | Implemented | `stdio_env()` (`mcp_client.py:376-392`) layers `cfg.env` over `SandboxPolicy.scrubbed_env()`; wired into `_open_transport`'s stdio branch (`mcp_client.py:406-416`). Asserted only by unit test today — not end-to-end over a real subprocess (this is exactly MCP-06's gap) |

### The `_serve`/`_server_tools` desync — CONFIRMED

Evidence, read directly from `mcp_client.py`:

- Line 234: `self._server_tools[name] = tools` — set once, on successful connect.
- Lines 241-242 (the `finally` block of `_serve`):
  ```python
  finally:
      self._sessions.pop(name, None)
  ```
  Only `self._sessions[name]` is popped. `self._server_tools[name]` is **never** touched here.
- `stop_server()` (lines 244-260) *does* pop `self._server_tools.pop(name, None)` (line 248) — but
  that is the user-initiated stop path, not the death path.
- `call_tool()` (lines 286-289):
  ```python
  def call_tool(self, server: str, tool: str, arguments: dict) -> str:
      if self._loop is None or server not in self._sessions:
          raise RuntimeError("MCP session not available")
  ```
  Indexes `self._sessions`, not `self._server_tools`.
- `tools_for()` / `tools()` (lines 262-266) read from `self._server_tools`.

**Confirmed defect, precisely scoped**: if a stdio server's task exits via the `except BaseException`
path *after* `ready` already resolved (i.e., the server died mid-session, not at connect time), its
tools remain visible via `tools_for()`/`tools()` (registry still lists them as callable) but every
call through them raises `RuntimeError("MCP session not available")` instead of the tool being
unregistered. This is a **zombie-tool** bug, not a crash — the model sees a tool it can no longer
successfully call, with a generic runtime error rather than "server X died." Ruling: **confirmed**,
matching the backlog's suspicion exactly. This phase does not fix it (MCP-12 explicitly: "confirmed
before any fix is proposed"); it becomes evidence for the workstream-C sizing in MCP-13 (tracked as
deferred requirement MCP-26).

### `_content_to_text` and the missing cap

```python
# src/agent86/tools/mcp_client.py:426-434
def _content_to_text(result: Any) -> str:
    parts: list[str] = []
    for chunk in getattr(result, "content", None) or []:
        text = getattr(chunk, "text", None)
        parts.append(text if text is not None else str(chunk))
    body = "\n".join(parts) if parts else "(no content)"
    if getattr(result, "isError", False):
        return f"ERROR: {body}"
    return body
```

No size limit anywhere in this function or its call site (`call_tool`, line 292-293). Compare to the
flight recorder's `max_field_chars` clip (referenced in ARCHITECTURE.md §9/§15 history, OBS-01) —
that cap exists on the *observability* side, not the *prompt* side. `structured_content` is never
read even though `CallToolResult` carries it (confirmed present, `mcp_types/_types.py:1243,1474`).
This is the exact gap MCP-11's ADR must rule on: where a prompt-side cap lives (a manager-level
constant? a per-server `MCPServerConfig` field, given `MCPConfig` currently carries only `enabled`?)
and whether `structured_content` should also be surfaced (currently silently dropped, not just
uncapped).

## SDK Callback Reality (load-bearing for ADR MCP-08 and MCP-09)

The installed `mcp` SDK (2.0.0) is more permissive than "no callback = crash." Read directly from
`mcp/client/session.py`:

```python
# .venv/Lib/site-packages/mcp/client/session.py:216-248
async def _default_sampling_callback(context, params) -> types.ErrorData:
    return types.ErrorData(code=types.INVALID_REQUEST, message="Sampling not supported")

async def _default_elicitation_callback(context, params) -> types.ErrorData:
    return types.ErrorData(code=types.INVALID_REQUEST, message="Elicitation not supported")

async def _default_list_roots_callback(context) -> types.ErrorData:
    return types.ErrorData(code=types.INVALID_REQUEST, message="List roots not supported")

async def _default_logging_callback(params) -> None:
    pass

async def _default_message_handler(message) -> None:
    await anyio.lowlevel.checkpoint()
```

And capability advertisement is conditioned on whether the *default* is still installed:

```python
# session.py:591-608 (ClientSession._build_capabilities)
sampling = (self._sampling_capabilities or types.SamplingCapability()) \
    if self._sampling_callback is not _default_sampling_callback else None
elicitation = (...) if self._elicitation_callback is not _default_elicitation_callback else None
roots = (types.RootsCapability(list_changed=True)) \
    if self._list_roots_callback is not _default_list_roots_callback else None
```

Since `mcp_client.py:219` constructs `ClientSession(read, write)` with **no** `sampling_callback`,
`elicitation_callback`, `list_roots_callback`, `logging_callback`, or `message_handler` arguments,
every one of these stays at its SDK default. The practical consequence: **agent86 already tells a
server, during `initialize()`, that it does not support sampling, elicitation, or roots** — a
spec-compliant server should not even attempt those requests against agent86. The backlog's
"structurally absent... any one of them is a constructor change" is correct about the *cost to add*
(true — it is a constructor change, since the callbacks are `ClientSession.__init__` parameters,
`session.py:371-380`), but understates that what exists today is *already the intended non-goal
behavior*, not a gap silently waiting to misbehave. Both ADRs (MCP-08, MCP-09) should be framed as
"should we build this opt-in surface" rather than "we have a latent defect here."

Also confirmed: `initialize()` negotiates `protocol_version=LATEST_HANDSHAKE_VERSION`
(`session.py:619`), which the SDK's own registry (`mcp_types/version.py`) defines as `"2025-11-25"`
— the newest *handshake-era* revision, one behind the current published `2026-07-28`. See Open
Question 1.

## The Nine Head-Start Matrix Rows, Verified

Verbatim from `docs/BACKLOG.md` § 999.0 "Audit head start," each followed by this research's
verification:

1. *"`ClientSession(read, write)` is built with no callbacks — sampling, elicitation and roots are
   structurally absent, not merely uncalled. Any one of them is a constructor change."*
   **CONFIRMED**, with the refinement above (§ SDK Callback Reality) — absence is declared, not
   silent.
2. *"`initialize()` → `list_tools()` and nothing else: no `list_resources`, `read_resource`,
   `list_prompts`, `get_prompt`."* **CONFIRMED** — `_serve`, `mcp_client.py:220-221`.
3. *"No `message_handler`, so every server notification is dropped."* **CONFIRMED** —
   `mcp_client.py:219` passes none; SDK default is a true no-op (`session.py:212-213`).
4. *"Timeouts are hardcoded and asymmetric: 30 s connect (`start_server`), 120 s per tool call
   (`call_tool`). `MCPConfig` carries only `enabled`."* **CONFIRMED** — `mcp_client.py:166,295`;
   `config.py:293-294`.
5. *"`_content_to_text` applies no size cap."* **CONFIRMED** — `mcp_client.py:426-434`.
6. *"Only `.text` content is read. Image, audio and embedded-resource blocks fall through to
   `str(chunk)`."* **CONFIRMED** — same function.
7. *"Likely defect, confirm before fixing: `_serve`'s `finally` pops `self._sessions[name]` but
   leaves `self._server_tools[name]` populated, while `call_tool` indexes
   `self._sessions[server]`."* **CONFIRMED**, see dedicated section above for line-level detail.
8. *"No reconnect path at all — `_serve` awaits `close_event`; a dropped transport ends the task."*
   **CONFIRMED** — `mcp_client.py:237` (`await close_event.wait()`), no retry loop anywhere.
9. *"Auth is `headers` + `${VAR}` only: no discovery, no refresh, no token storage."* **CONFIRMED**
   — `_resolve_server_secrets`, `mcp_client.py:336-358`; no OAuth-related import or call anywhere in
   the file.

All nine confirmed, none refuted. This research found no additional errors in the head-start list.

## The Corpus Servers

| Server | Source | Version-pin mechanism | Version found (2026-09-22) | Capabilities exercised |
|---|---|---|---|---|
| `@modelcontextprotocol/server-everything` | npm | `npx -y @modelcontextprotocol/server-everything@X.Y.Z` (or pin in an `[mcp.servers.*]` `args` entry) | **2026.8.31** (npm registry, published ~9 days before this research date) | Tools (16, incl. `echo`, `get-sum`, `get-annotated-message` [tool annotations], `get-resource-links`/`get-resource-reference` [resources], `get-env`, `get-structured-content` [structured/typed output], `get-tiny-image` [non-text content], `trigger-long-running-operation` [**progress**], `toggle-simulated-logging` [logging], `toggle-subscriber-updates` [resource subscriptions], `trigger-elicitation-request`/`trigger-url-elicitation` [**elicitation**, form + URL modes], `trigger-sampling-request`/`trigger-sampling-request-async` [**sampling**], `get-roots-list` [**roots**]); Prompts (3, incl. argument autocompletion via `completable` [**completion**]); Resources (4 URI schemes); MCP Tasks (async request lifecycle, cancellation). **MCP-07 answer: YES — confirmed by tool name, not inferred** — `server-everything` drives sampling, elicitation, and progress |
| `@modelcontextprotocol/server-filesystem` | npm | `npx -y @modelcontextprotocol/server-filesystem@X.Y.Z <allowed-dir>` | **2026.8.31** (npm registry) | Realistic stdio file tools (read/write/list/search); the **roots** question specifically — GitHub issue #3602 on this repo documents the server's roots-protocol interaction with CLI-provided allowed directories, worth reading directly during the audit task, not just citing here |
| `mcp-server-git` | PyPI | `pip install mcp-server-git==X.Y.Z` or `uvx mcp-server-git` (this machine has no `uv`/`uvx` installed — `pip install` is the available path here) | **2026.8.18** (PyPI) | Git read/search/manipulate tools over stdio; second realistic stdio server, natural bridge to backlog 999.5 (git awareness) |
| `tests/integration/live_mcp_server.py` | in-repo | git commit SHA (it's source, not a package) | current repo HEAD | Two trivial tools (`add`, `shout`) today. **Already supports stdio** — `tests/integration/test_mcp_client.py`'s `_stdio_cfg()` (line 82) already invokes it as `[sys.executable, str(_SERVER), "stdio", "0"]`, and `MCPServer.run(transport="stdio", **kwargs)` accepts the unused `host`/`port` kwargs without error (verified: `test_per_server_start_lists_real_tools` passed for real in this research session, 1.38s, subprocess-pipe-only, no network). Needs one new tool (or resource) added to echo `os.environ` for MCP-06 |
| GitHub's hosted remote MCP server | Hosted product, `github/github-mcp-server` | No installable version to pin — it's a live hosted endpoint (`https://api.githubcopilot.com/mcp/`); "pinning" here means recording the endpoint URL and the API surface/date observed, not a package version | N/A — hosted, not versioned in the way the other four are | Workstream B's target (OAuth 2.0, discovery, refresh) exercised against a real product rather than the archived `modelcontextprotocol/servers` reference implementation, per the explicit out-of-scope ruling in REQUIREMENTS.md. **Not independently exercised in this research** — no live GitHub OAuth app/credentials available in this environment. See Open Question 2 |

Confidence: HIGH for the four installable servers (versions read directly from npm/PyPI registry
pages, fetched 2026-09-22; `server-everything`'s feature claims cross-verified against both a
GitHub issue thread and the server's own `docs/features.md`, fetched live). MEDIUM-LOW for the
GitHub hosted server (WebSearch-sourced URL and auth-model description, not independently connected
to).

## Where the Audit Report and Matrix Should Live

`docs/ARCHITECTURE.md` §15 already has the exact table format this phase's "out" rulings must land
in — read directly, lines 1157-1167:

```markdown
| Not built | Area | Tracked |
|---|---|---|
| Prompt-level tool-emulation shim for models without native tool calling | §6 cognitive | — (swap the model) |
...
```

And a **non-goals bullet list** immediately above it (lines 1130-1139) already carries the MCP
server-mode non-goal:

```markdown
- An MCP **server** mode. agent86 mounts other servers' tools over all three transports; it
  is not itself mountable by another harness. Ruled out when §999.0 was scoped (2026-09-22):
  the client half is the whole of it. See `docs/BACKLOG.md` § 999.0.
```

Recommendation for the audit's own output:
- **The conformance matrix** — a new file, `docs/mcp-conformance-matrix.md` (or under a new
  `docs/mcp/` directory if the ADRs go there too — see below). Not inline in `ARCHITECTURE.md`,
  which stays the "what's built" contract, not the audit trail.
- **Every "out" ruling** — a new row in the existing §15 table (bullet-list style if it's closer to
  a non-goal, table-row style if it's "not built yet"), each with a one-line reason and a pointer to
  the matrix for full reasoning — following the exact pattern already used for the MCP server-mode
  non-goal above.
- **The audit report itself** (the narrative: corpus versions, MCP-07's answer, the nine
  confirmed/corrected rows, the workstream sizing) — a new file, e.g.
  `docs/mcp-conformance-audit-2026-09.md`, dated because (per this document's own experience) MCP
  spec revisions move fast enough that a future re-audit is plausible and the old one should stay
  legible as a snapshot rather than be overwritten.

## ADR Conventions

**No `docs/adr/` directory exists in this repo** (confirmed: no file matching `*adr*`/`ADR*` under
`docs/`). This phase is the first ADR-writing work in the project. Recommendation, since there is no
existing convention to match:

- **Format: lightweight MADR-style** (Markdown Architecture Decision Records) — Context / Decision
  / Consequences, not the more elaborate MADR template with alternatives-considered tables. This
  project's own doc style (ARCHITECTURE.md, BACKLOG.md) is prose-heavy with tables used sparingly
  and precisely — a lightweight MADR keeps consistency with that voice.
- **Path: `docs/adr/NNNN-title.md`**, numbered sequentially starting at `0001`, matching the
  most common convention (Nygard's original, and MADR's default) so tooling (if ever added) can
  glob-sort by number. Four ADRs for this phase: something like `0001-mcp-sampling-inversion-of-
  control.md`, `0002-mcp-elicitation-tier1-surface.md`, `0003-mcp-schema-deferral-prompt-contract.md`,
  `0004-mcp-result-cap-location.md`.
- **Each ADR states a ruling and rationale**, per the phase's success criteria — not "we might do
  X or Y," an actual decision, even if the decision is "opt-in, deferred until a corpus server
  demands it."

Confidence: MEDIUM — this is a recommendation (no existing convention to defer to), not a verified
fact; flagging it explicitly so the planner/user can override the format choice if they have a
preference not visible in the repo.

## Context Budget & Prompt Contract Interaction (for ADR MCP-10)

Read directly from `docs/ARCHITECTURE.md`:

```
# ARCHITECTURE.md:615-619 (§8 derivation)
window            = context_window_for(model_ref, config)
conversation      = window − (system prompt + tool schemas)
                           − limits.context_reserve_tokens
                           − max_output_tokens_for(model_ref, config)
```

```
# ARCHITECTURE.md:286-290 (§5 narrative)
The context budget is recomputed before every request... `Harness._context_budget` asks
`capabilities.context_window_for` for the model's real window and subtracts the compiled system
prompt, the tool schemas, `limits.context_reserve_tokens`, and the output cap the call will ask
for... Skills, MCP servers and the episodic recall note all change the overhead mid-session, so a
figure computed at startup [would be stale].
```

And the `allowed-tools` boundary (§7, ARCHITECTURE.md:543-544):

> The compiled system prompt lists each skill's `allowed-tools`, so the boundary is known before a
> refusal costs a step.

MCP-10's ADR must reconcile schema deferral (names + server instructions up front, full JSON Schema
only on first tool use) against two things this research confirms are real, present mechanisms, not
hypothetical ones: (1) `tool schemas` is a named, subtracted term in the fixed-overhead computation
— deferring schemas changes what that term *means* mid-session (today it's computed once per
request from the full compiled set; a deferred-schema world has the term grow after a tool's first
use, which the "recomputed before every request" design already tolerates structurally, but the ADR
should say so explicitly rather than leave it implied); and (2) the system prompt is where the
model currently learns the full boundary of what it may call, which is exactly what `allowed-tools`
gating depends on to make a refusal "free" (caught before a step, not after). Deferred schemas that
still list every tool's *name* preserve that boundary; deferred schemas that also defer *which
tools exist* would not.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `node`/`npm`/`npx` | Running `server-everything`, `server-filesystem` for the audit | ✓ | node v22.22.0, npm 10.9.4, npx 10.9.4 | — |
| `git` | `mcp-server-git`'s underlying operations; general | ✓ | 2.52.0 | — |
| `python`/`pip` (in `.venv`) | `mcp-server-git` install, running `live_mcp_server.py` | ✓ | pip 26.1.2, mcp SDK 2.0.0 already installed | — |
| `uv`/`uvx` | The MCP ecosystem's common launcher for Python-packaged servers (incl. `mcp-server-git`) | ✗ | — | `pip install mcp-server-git` works as a direct substitute; document both invocation forms in the audit, since a reader's machine may have `uvx` and not want a separate pip install |
| `docker` | Not required by this phase (audit-only); available for a future implementation phase's sandboxed server runs | ✓ | 29.6.1 | — |
| Live network / GitHub OAuth credentials | Exercising GitHub's hosted remote MCP server directly | ✗ (not configured in this environment) | — | Document the server's endpoint, auth model, and capability surface from its public documentation (already done above); flag in the audit report that live verification against it was not performed in this research pass — see Open Question 2 |

**Missing dependencies with no fallback:** None block the phase — this phase does not implement
against the GitHub hosted server, it only records its existence and pinning mechanism (an endpoint
URL, not a version) per MCP-05's explicit scope.

**Missing dependencies with fallback:** `uv`/`uvx` absent, `pip install` fallback works.

## Common Pitfalls

### Pitfall 1: Treating "structurally absent" as "buggy"
**What goes wrong:** Writing the ADRs (MCP-08/MCP-09) as if agent86 has a latent defect around
sampling/elicitation/roots.
**Why it happens:** The backlog's own head-start language ("structurally absent") reads like a gap
report.
**How to avoid:** This research confirms the SDK's capability-advertisement gating means agent86
already tells servers "not supported" correctly at the protocol level. The ADR is a build-or-don't
decision, not a defect writeup.
**Warning signs:** An ADR that opens with "agent86 fails to implement..." instead of "agent86
currently declares X unsupported; should it be supported, and under what constraints?"

### Pitfall 2: Pinning the matrix to `2026-07-28` because it's "the current spec"
**What goes wrong:** Enumerating rows against a protocol era (`server/discover`, `_meta`-based
version negotiation) that agent86's client code — via the installed SDK's `initialize()` call —
cannot currently reach at all, producing a matrix that rates capabilities against a wire format
never actually spoken.
**Why it happens:** "Always use the current spec revision" is the obvious default instinct, and
training data on MCP predates this SDK-era split entirely.
**How to avoid:** Pin to `2025-11-25` (verified as what `LATEST_HANDSHAKE_VERSION` resolves to,
`session.py:619`) for the matrix's baseline, and record `2026-07-28`'s existence/implications as an
explicit note or Open Question — this is exactly what this research document does, and the audit
should inherit that structure rather than re-litigate it.
**Warning signs:** Matrix rows referencing `server/discover` or `_meta`-based protocol negotiation
as if agent86 could exercise them today.

### Pitfall 3: Re-deriving what this research already confirmed with line numbers
**What goes wrong:** The audit re-reads `mcp_client.py` from scratch and produces looser claims
("looks like it might drop notifications") instead of citing exact evidence.
**Why it happens:** Audit work and research work can duplicate effort when not coordinated.
**How to avoid:** The matrix's "implemented/partial/absent" column and the `_serve`/`_server_tools`
desync ruling can cite this RESEARCH.md's file:line evidence directly; the audit's incremental
value is corpus-server-driven *behavioral* confirmation (actually running `server-everything`
against agent86 and observing what happens), not re-reading source that's already been read.
**Warning signs:** Matrix cells with vaguer claims than this research document already supports.

### Pitfall 4: Treating the live-server extension as new infrastructure
**What goes wrong:** Planning MCP-06 as if a stdio test harness needs to be built from scratch.
**Why it happens:** The phase description says "extend `live_mcp_server.py`," which could read as
greenfield work.
**How to avoid:** The stdio path is proven working today — `_stdio_cfg()` in
`test_mcp_client.py:81-82` and `test_per_server_start_lists_real_tools` (verified passing, 1.38s, no
network, in this research session). MCP-06 is: add one tool/resource to `live_mcp_server.py` that
returns `dict(os.environ)`, write one new test alongside the existing stdio tests in
`test_mcp_client.py` (or `test_mcp_live.py`) that sets a fake host-only env var
(e.g. `AGENT86_TEST_HOST_SECRET`), starts the server via `MCPManager.start_server` with a stdio
config, calls the echo tool, and asserts the fake var is **absent** from the echoed dict while the
allowlisted vars (`PATH`, etc., per `SandboxPolicy.env_allowlist()`,
`src/agent86/tools/sandbox/policy.py:70-73`) **are** present.
**Warning signs:** A plan that budgets significant effort for "build a stdio test harness."

## Code Examples

### The exact mechanism MCP-06's test should extend

```python
# tests/integration/test_mcp_client.py:81-82 (existing, already proven)
def _stdio_cfg() -> MCPServerConfig:
    return MCPServerConfig(command=sys.executable, args=[str(_SERVER), "stdio", "0"])

# tests/integration/test_mcp_client.py:85-93 (existing, already proven — model for MCP-06)
@pytest.mark.skipif(not _HAS_MCP_SERVER, reason="requires the 'mcp' extra")
def test_per_server_start_lists_real_tools():
    manager = MCPManager({})
    try:
        tools = manager.start_server("alpha", _stdio_cfg(), timeout=30.0)
        assert {t._tool for t in tools} == {"add", "shout"}
        assert all(t.name.startswith("mcp__alpha__") for t in tools)
    finally:
        manager.close()
```

A new tool on `live_mcp_server.py` (sketch, not a load-bearing exact-string requirement — the
planner's task should write this for real against the live SDK):

```python
# tests/integration/live_mcp_server.py — addition sketch
import os

@mcp.tool()
def get_env() -> dict[str, str]:
    """Echo this server's own process environment, for SEC-04 verification."""
    return dict(os.environ)
```

And the scrubbing mechanism the test must assert against
(`src/agent86/tools/sandbox/policy.py:123-133`):

```python
def scrubbed_env(self) -> dict[str, str]:
    """The environment a tool subprocess gets: allowlist + opt-in passthrough, no secrets."""
    allowed = env_allowlist()
    env = {k: v for k, v in os.environ.items() if k in allowed}
    env.update({
        k: v for k, v in os.environ.items()
        if k.startswith(_ENV_ALLOWLIST_PREFIXES) and not is_secret_name(k)
    })
    ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| MCP `initialize` handshake as the only negotiation path | A parallel "modern," stateless per-request-envelope protocol (`server/discover`, `_meta`-carried version) | `2026-07-28` spec revision | agent86's SDK (2.0.0) supports both eras in principle, but agent86's own client code (`ClientSession.initialize()`) only reaches the handshake era — see Open Question 1 |
| `roots/list` as a standard, non-deprecated capability | Deprecated (still fully supported) as of `2026-07-28`, SEP-2577 | `2026-07-28` | Any ADR/implementation work on roots (deferred requirement MCP-16) inherits a capability on its way out; worth noting even though agent86 doesn't implement it yet |
| `Tool.execution` field (`2025-11-25` only) | Removed in `2026-07-28` | `2026-07-28` | Not currently read by agent86 either way; a non-issue today, but a reason not to design a future feature around it |
| `Tool.output_schema` restricted to `type: object` at root | Any valid JSON Schema 2020-12 keyword permitted at root | `2026-07-28` | Relevant only if/when MCP-11's structured-output support is eventually built |

**Deprecated/outdated:** Nothing agent86 currently relies on is itself deprecated by the spec —
agent86's gap is *absence*, not *staleness*, for every row above except the protocol-era split
itself.

## Open Questions

1. **Which spec revision should the matrix's row set and ratings be pinned against —
   `2025-11-25` (what agent86's client code can actually negotiate today) or `2026-07-28` (the
   current published revision)?**
   - What we know: agent86's SDK-mediated `initialize()` call is hardcoded to
     `LATEST_HANDSHAKE_VERSION`, which resolves to `2025-11-25` (`session.py:619`,
     `mcp_types/version.py`). The SDK itself supports `2026-07-28` in principle
     (`MODERN_PROTOCOL_VERSIONS`), but nothing in `mcp_client.py` invokes that path.
   - What's unclear: whether upgrading to the `2026-07-28` "modern" protocol is itself a
     deferred-requirement-worthy piece of work (it isn't named anywhere in REQUIREMENTS.md's
     workstreams A/B/C), or whether it should be added as a new deferred item this audit surfaces.
   - Recommendation: pin the matrix to `2025-11-25` as agent86's practical ceiling, and add "adopt
     the `2026-07-28` modern protocol" as a candidate row/finding in the audit report itself — this
     is exactly the kind of finding MCP-13's phase-breakdown recommendation should route into
     workstream C (context & lifecycle) or flag as a new, currently-unlisted workstream candidate.

2. **How should the GitHub hosted remote MCP server be "pinned by version" per MCP-05, given it has
   no installable version?**
   - What we know: it's a hosted endpoint (`https://api.githubcopilot.com/mcp/`), not a package;
     GitHub controls its release cadence unilaterally.
   - What's unclear: whether "pinned by version" for this one corpus member should mean recording
     the endpoint URL plus an observed capability snapshot with today's date (the closest analog to
     a version pin for a hosted product), or whether the audit should treat this server as
     out-of-reach for actual exercising in this pass (no live OAuth credentials were available in
     this research environment) and document it from public sources only.
   - Recommendation: record the endpoint URL + observation date as the "version," and be explicit
     in the audit report about whether the audit task actually connected to it (this research did
     not) versus documented it from GitHub's own docs.

3. **Does the audit need to independently install and run `server-everything`, or is the
   README/`features.md` evidence (already tool-name-level specific) sufficient to answer MCP-07
   without a live run?**
   - What we know: the feature list is specific enough to name exact tool names
     (`trigger-sampling-request`, `trigger-elicitation-request`, `trigger-long-running-operation`)
     that map 1:1 onto sampling/elicitation/progress.
   - What's unclear: whether the phase's "audit sweeps... with evidence" framing (REQUIREMENTS.md,
     MCP-03) requires a live run's transcript as the evidence, or whether documented tool names from
     the server's own maintained docs satisfy "with evidence."
   - Recommendation: run it live if `npx` access and time allow (confirmed available in this
     environment, § Environment Availability) — it upgrades MEDIUM confidence to HIGH and produces
     the kind of first-party evidence this phase's success criteria emphasize ("states, with
     evidence, whether `server-everything` drives sampling, elicitation and progress").

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included.

This phase's output is almost entirely documents; validation here means **checking documents make
verifiable claims that actually hold**, not testing application behavior. One real pytest test
(MCP-06) is the exception.

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest + pytest-asyncio (already the project standard) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| Quick run command | `pytest tests/integration/test_mcp_client.py -q` |
| Full suite command | `pytest -q` (currently ~1100 tests, per `.planning/STATE.md`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| MCP-02 | Matrix has one row per client-side spec capability | doc check (row-count grep/script) | `grep -c '^\| ' docs/mcp-conformance-matrix.md` against a known capability count, or a small Python script asserting every capability name from this research's enumeration table appears as a row | ❌ Wave 0 — matrix file doesn't exist yet |
| MCP-03 | Each row records corpus-exercised status | doc check | manual review + the same row-count script extended to check a second column is non-empty | ❌ Wave 0 |
| MCP-04 | Every "out" ruling lands in ARCHITECTURE.md §15 | grep assertion | a script/test that extracts every "out"-ruled capability name from the matrix and asserts it (or a paraphrase) appears in `ARCHITECTURE.md`'s §15 block | ❌ Wave 0 — write this as the one non-MCP-06 automated check, since it is cheap and directly enforces MCP-04's cross-document consistency requirement |
| MCP-05 | Five servers named with exact versions | doc check | manual review (versions are static facts, not runtime-checkable) | N/A — no test, human-verifiable table |
| MCP-06 | `live_mcp_server.py` echoes environment; stdio servers never get unscrubbed host env | **real pytest integration test** | `pytest tests/integration/test_mcp_client.py::test_stdio_server_gets_scrubbed_env -x` (name illustrative — planner assigns final name) | ❌ Wave 0 — the one test this phase must write |
| MCP-07 | Determination of sampling/elicitation/progress in `server-everything` | doc check + optional live run | manual review of audit report's evidence section; optionally `npx -y @modelcontextprotocol/server-everything@2026.8.31` run against a scratch `MCPManager` during the audit task (not a committed test) | N/A — evidence-gathering, not a CI-pinned assertion |
| MCP-08–MCP-11 | Four ADRs exist with rulings | doc check | a script asserting exactly 4 files under `docs/adr/` matching this phase's naming, each containing a "## Decision" (or MADR-equivalent) heading | ❌ Wave 0 |
| MCP-12 | Nine head-start rows confirmed/corrected | doc check (this research already did the confirmation pass) | manual review — the audit report's own table, citing this RESEARCH.md's evidence directly | N/A |
| MCP-13 | Phase breakdown recommendation exists | doc check | manual review — a structured list/table in the audit report naming candidate phases for workstreams A/B/C | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/integration/test_mcp_client.py -q` (fast, no network,
  proven ~1.4s for the existing stdio tests)
- **Per wave merge:** `pytest -q` (full suite, since this phase also touches
  `docs/ARCHITECTURE.md`, which other tests may assert content against — check for existing
  `ARCHITECTURE.md`-content tests before assuming none exist)
- **Phase gate:** full suite green, plus a manual pass confirming every matrix row/ADR/§15 update
  cross-reference actually resolves (the grep-assertion script above should be run as part of this
  gate, not just written and forgotten)

### Wave 0 Gaps
- [ ] `docs/mcp-conformance-matrix.md` — doesn't exist; create with the row set from this
  research's Client-Side MCP Spec Surface table as a starting skeleton
- [ ] `docs/adr/` directory — doesn't exist; create with the four ADR files
- [ ] A cross-document consistency script/test (§15 ↔ matrix "out" rulings) — doesn't exist;
  smallest version is a plain Python script run manually or wired as a cheap pytest test under
  `tests/unit/` (e.g. `test_docs_consistency.py`) reading both files and asserting the cross-
  reference
- [ ] `tests/integration/test_mcp_client.py`'s new SEC-04 end-to-end test — doesn't exist; the
  stdio scaffolding it needs (`_stdio_cfg`, `MCPManager`, `_HAS_MCP_SERVER` skip guard) already
  exists in the same file and should be reused, not duplicated

## Sources

### Primary (HIGH confidence)
- `src/agent86/tools/mcp_client.py` (this repo, read in full, 2026-09-22) — every client-code claim
- `.venv/Lib/site-packages/mcp/client/session.py` (installed SDK, `mcp==2.0.0`) — `ClientSession`
  constructor, default callbacks, capability-advertisement gating, `initialize()` protocol version
- `.venv/Lib/site-packages/mcp_types/version.py` (installed SDK) — protocol version registry
- `.venv/Lib/site-packages/mcp_types/_types.py` — `CallToolResult.structured_content`,
  `ToolAnnotations`, `Tool.output_schema`/`execution` field notes
- `tests/integration/test_mcp_client.py`, `tests/integration/live_mcp_server.py`,
  `tests/integration/test_mcp_live.py` (this repo) — existing test conventions, stdio scaffolding
- `src/agent86/tools/sandbox/policy.py` — `scrubbed_env()`, `env_allowlist()`, `is_secret_name()`
- `src/agent86/config.py` — `MCPConfig`, `MCPServerConfig`
- `docs/ARCHITECTURE.md` (this repo) — §7 tools, §8 memory/context budget, §15 non-goals table
  format
- `docs/BACKLOG.md` (this repo) — § 999.0 scope, the nine-row audit head start (verbatim source for
  the confirmation pass)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md` (this repo) — phase
  scope, requirement text
- Live test run: `pytest tests/integration/test_mcp_client.py -k per_server_start_lists_real_tools -q`
  → 1 passed, 1.38s (this research session, 2026-09-22)
- `modelcontextprotocol.io/specification/versioning` (fetched live, 2026-09-22) — current spec
  revision `2026-07-28`, revision history

### Secondary (MEDIUM confidence)
- `github.com/modelcontextprotocol/servers/blob/main/src/everything/docs/features.md` (fetched via
  WebFetch, 2026-09-22) — `server-everything`'s tool-by-tool feature list (sampling/elicitation/
  progress tool names)
- `github.com/modelcontextprotocol/servers/issues/4792` (surfaced via WebSearch) — corroborates
  `server-everything` conditionally registers sampling/elicitation tools based on declared client
  capabilities
- npmjs.com package pages for `@modelcontextprotocol/server-everything` and
  `@modelcontextprotocol/server-filesystem` (via WebSearch, versions 2026.8.31 both) — not directly
  fetched with WebFetch, so treated as MEDIUM rather than HIGH; **the planner/auditor should
  re-verify with `npm view <pkg> version` before the matrix is finalized**, per this document's own
  stated verification protocol
- pypi.org project page for `mcp-server-git` (fetched via WebFetch, version 2026.8.18) — HIGH for
  the version number specifically (directly fetched), MEDIUM for feature claims (not independently
  run)
- `github.com/github/github-mcp-server`, `docs.github.com` GitHub MCP setup pages, `mcpservers.org`
  (via WebSearch) — endpoint URL and OAuth model description; not independently connected to
- `modelcontextprotocol.io/specification/2025-06-18/client/roots` and related WebSearch results —
  roots deprecation in `2026-07-28` (SEP-2577)

### Tertiary (LOW confidence)
- General WebSearch summaries of "MCP spec 2025 revisions" (elicitation, sampling-with-tools
  SEP-1577 mentions) — used only for orientation, not cited as fact anywhere above without a
  primary/secondary source backing the specific claim

## Metadata

**Confidence breakdown:**
- Client-side spec surface enumeration: MEDIUM — cross-checked SDK method signatures against spec
  pages, but not every spec page was individually re-read; treat as a strong starting matrix
  skeleton, not a substitute for the audit's own page-by-page pass
- What agent86 implements: HIGH — every claim has a file:line citation against code read in this
  session, several load-bearing claims (stdio test, capability-advertisement gating) additionally
  verified by reading the installed SDK's own source or running a real test
- Corpus server pinning: HIGH for versions of the four installable servers (fetched from
  registries), MEDIUM for `server-everything`'s deep feature claims (docs-based, not independently
  run — see Open Question 3), LOW-MEDIUM for the GitHub hosted server (WebSearch only, not
  connected to)
- ADR conventions: MEDIUM — this is a recommendation in the absence of any existing project
  convention, not a verified fact
- Pitfalls: HIGH — each is grounded in a specific, cited piece of evidence from this research pass

**Research date:** 2026-09-22
**Valid until:** ~14 days for the corpus-server version pins (npm/PyPI packages here update on the
order of weeks; re-verify with `npm view`/`pip index versions` immediately before the matrix is
finalized, not from this document alone) — the code-audit findings (agent86's own `mcp_client.py`
behavior) are stable until that file changes, which only happens inside this milestone's own later
phases.
