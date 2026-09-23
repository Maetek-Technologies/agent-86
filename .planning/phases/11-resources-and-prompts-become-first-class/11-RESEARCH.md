# Phase 11: Resources and prompts become first-class - Research

**Researched:** 2026-09-23
**Domain:** MCP client depth — `mcp` Python SDK 2.0.0, `ClientSession` resource/prompt/completion
call sites, agent86's `tools/mcp_client.py`
**Confidence:** HIGH (SDK surface, existing client architecture) / MEDIUM (test-corpus reach for
live `server-filesystem`/`server-everything` evidence, content-mapping design choices)

## Summary

Everything this phase needs is additive to one file, `src/agent86/tools/mcp_client.py`, and one
new synthetic-tool class family alongside the existing `MCPTool`. The installed `mcp` SDK
(2.0.0, pinned `mcp>=1.0` in `pyproject.toml`) already implements every call site this phase
needs — `ClientSession.list_resources`, `read_resource`, `list_resource_templates`,
`subscribe_resource` (deprecated-but-functional for the `2025-11-25` protocol revision agent86
negotiates), `list_prompts`, `get_prompt`, and `complete` — at
`.venv/Lib/site-packages/mcp/client/session.py:852-1232`. None of them require a `ClientSession`
constructor change (unlike sampling/elicitation/roots, Phase 12's job): they are ordinary
request/response methods callable the moment `session.initialize()` returns, exactly like the
`list_tools()` call agent86 already makes at `mcp_client.py:221`.

The roadmap's own success criterion 1 — "a model-issued **tool call** round-trips a real
`list_resources` → `read_resource` pair" — settles the design question definitively: resources
and prompts surface to the model as ordinary `Tool` instances in the registry, mounted per
mounted server, gated on the server's own advertised `ServerCapabilities` (read once,
immediately after `session.initialize()`, from `session.server_capabilities`), following the
exact pattern `_is_read_only` already uses for `readOnlyHint`. This needs no Tier 1/gateway
surface, no `types.py` change, and no new core dependency — it is the same "wrap a remote
capability as a `Tool`" move the MCP client already makes for `list_tools`/`call_tool`.

The one real design decision this phase owns outright (not inherited from an ADR) is **how to
flatten non-`ToolResult`-shaped SDK types into `ToolResult.content: str`.** `ReadResourceResult`
carries `TextResourceContents | BlobResourceContents`; `GetPromptResult` carries a
`list[PromptMessage]` where each message's `content` is `TextContent | ImageContent |
AudioContent | ResourceLink | EmbeddedResource`. None of these are the `CallToolResult` shape
`_content_to_text` already handles, so this is new code, not a change to the ADR-0004-owned
`_content_to_text`/`max_result_chars` path (MCP-22, workstream C, explicitly out of this phase's
scope). Recommendation: never inline a base64 blob into `content` (wastes budget, unusable to the
model as text) — render text resources inline, render blobs as a `mime_type`/byte-length marker
in `content` with the raw blob carried in `ToolResult.metadata` (already `dict[str, Any]`,
already used this way for diffs), and for prompt messages render a `[role]: text` transcript,
applying the identical non-inlining treatment to any `EmbeddedResource`/`ImageContent`/
`AudioContent` block found inside a prompt message.

**Primary recommendation:** add up to seven new capability-gated, per-server synthetic tools
(`mcp__{server}__list_resources`, `read_resource`, `list_resource_templates`,
`subscribe_resource`, `list_prompts`, `get_prompt`, `complete`) to `mcp_client.py`, each a small
`Tool` subclass with its own `Args` model (unlike `MCPTool`, whose schema comes from the remote
server), registered into `_serve`'s tool list only when the server's `ServerCapabilities` says it
supports the underlying feature, calling through new `MCPManager` methods that mirror
`call_tool`'s `run_coroutine_threadsafe` pattern.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-14 | Resources become first-class — `list_resources` and `read_resource`, absent today | SDK methods confirmed at `session.py:852-930`; result types at `mcp_types/_types.py:849-938`; design: per-server synthetic tools gated on `ServerCapabilities.resources` |
| MCP-15 | Prompts become first-class — `list_prompts` and `get_prompt`, absent today | SDK methods confirmed at `session.py:1141-1232` (get_prompt, complete); result types at `mcp_types/_types.py:1103-1338, 1742-1817`; design: per-server synthetic tools gated on `ServerCapabilities.prompts`/`completions` |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `mcp` | 2.0.0 installed; `pyproject.toml` pins `mcp>=1.0` (line 43, `mcp` extra) | The MCP Python SDK — `ClientSession`, wire types (`mcp.types`, itself a mirror of the standalone `mcp_types` package) | Already the project's only MCP dependency; this phase adds zero new libraries — every method needed already ships in the installed version |

No new packages. `npm view @modelcontextprotocol/server-everything version` /
`server-filesystem version` were checked during Phase 10's audit (`docs/mcp-conformance-audit-
2026-09.md:39-40`) and pinned to `@2026.8.31` for both — re-verify at plan time if a live
evidence run is scheduled, since these are npm-hosted demo servers that move.

**Version verification (this research session, 2026-09-23):**
```
$ python -c "import importlib.metadata as m; print(m.version('mcp'))"
2.0.0
```
`pyproject.toml:43` — `mcp = ["mcp>=1.0"]`; `pyproject.toml:52,62` — dev/test extras also pin
`mcp>=1.0`. The floor (`>=1.0`) is looser than the installed version (2.0.0); this research is
grounded in the *installed* 2.0.0 source, since that is what CI and this environment actually
run. No evidence was found that anything this phase needs is version-gated above 1.0 — the
`ClientSession` methods below have no `@since`/version markers in the docstrings read.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mcp.server.mcpserver.MCPServer` | bundled with `mcp` 2.0.0 | The server API already used to build `tests/integration/live_mcp_server.py` | Extending that fixture with `.resource()`/`.prompt()`/`.completion()` decorators (all present — confirmed via `dir(MCPServer(...))`, see Environment Availability) is the no-network, no-npx way to test this phase's new call sites in CI |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Per-server synthetic `Tool` subclasses | A single generic `mcp_resource`/`mcp_prompt` meta-tool taking `server` as an argument | Rejected: breaks the existing per-server naming/approval/collision model (`mcp__{server}__{name}`, `ToolRegistry.collisions`), and the model would need to already know server names out-of-band; the existing `MCPTool` pattern (one instance per server per capability) is what `ARCHITECTURE.md` §7 documents as the contract |
| Inlining blob resource content as base64 text in `ToolResult.content` | Carrying it in `ToolResult.metadata` with a text marker in `content` | Rejected inlining: wastes context budget on data the model cannot use as text, and pre-empts MCP-22's future `max_result_chars` cap by front-loading exactly the kind of payload ADR 0004 was written to bound |
| Re-checking `server_capabilities` on every call | Reading it once at connect time (in `_serve`, alongside the existing `readOnlyHint` read) and freezing the tool list for the session's lifetime | Matches the existing architecture: `_server_tools[name]` is already set once per connect and only refreshed on reconnect/restart (a `list_changed`-driven refresh is explicitly MCP-24, workstream C, not this phase) |

**Installation:** none — no new dependency.

## Architecture Patterns

### Recommended Project Structure

No new files. Everything lands in the existing single-file MCP client module:

```
src/agent86/tools/
└── mcp_client.py   # MCPTool (unchanged) + new MCPResourceTool/MCPPromptTool family,
                     # new MCPManager methods, capability-gated registration in _serve
```

### Pattern 1: Capability-gated synthetic tool registration (extends `_is_read_only`'s pattern)

**What:** Read `session.server_capabilities` once, right after `await session.initialize()`
(`mcp_client.py:220`), and conditionally build extra `Tool` instances alongside the existing
per-remote-tool `MCPTool` list — never unconditionally, since a server that doesn't declare
`resources`/`prompts`/`completions` will answer those methods with a JSON-RPC "method not found"
error (an `MCPError`, `mcp/shared/exceptions.py:19-53`), and advertising a tool the server can't
serve trains the model to expect failures.

**When to use:** Every server connect, inside `_serve`, immediately after `session.initialize()`
and before/alongside the existing `session.list_tools()` call.

**Example (grounded in real SDK types this session verified):**
```python
# Source: .venv/Lib/site-packages/mcp/client/session.py:791-798 (server_capabilities property)
#         .venv/Lib/site-packages/mcp_types/_types.py:485-505 (ServerCapabilities fields)
caps = session.server_capabilities  # populated by initialize()'s adopt() call, before this line
extra_tools: list[Tool] = []
if caps and caps.resources is not None:
    extra_tools.append(MCPListResourcesTool(self, name))
    extra_tools.append(MCPReadResourceTool(self, name))
    extra_tools.append(MCPListResourceTemplatesTool(self, name))
    if caps.resources.subscribe:
        extra_tools.append(MCPSubscribeResourceTool(self, name))
if caps and caps.prompts is not None:
    extra_tools.append(MCPListPromptsTool(self, name))
    extra_tools.append(MCPGetPromptTool(self, name))
if caps and caps.completions is not None:
    extra_tools.append(MCPCompleteTool(self, name))
```
This mirrors `_is_read_only`'s existing philosophy exactly: a server-declared signal can only
ever change what agent86 *offers*, never grant something the user didn't already choose to mount.

### Pattern 2: New `MCPManager` call methods (parallel to `call_tool`)

**What:** Each new synthetic tool needs a synchronous entry point on `MCPManager`, following
`call_tool`'s existing `run_coroutine_threadsafe` + `.result(timeout=...)` shape
(`mcp_client.py:286-295`) rather than inventing a new dispatch mechanism.

**Example (real SDK signatures this session read from `session.py`):**
```python
# Source: .venv/Lib/site-packages/mcp/client/session.py:852-871, 895-930
async def list_resources(self, *, params: types.PaginatedRequestParams | None = None
                          ) -> types.ListResourcesResult: ...
async def list_resource_templates(self, *, params: types.PaginatedRequestParams | None = None
                                   ) -> types.ListResourceTemplatesResult: ...
async def read_resource(self, uri: str, *, ...) -> types.ReadResourceResult: ...

# Source: .venv/Lib/site-packages/mcp/client/session.py:1141-1210
async def list_prompts(self, *, params=None) -> types.ListPromptsResult: ...
async def get_prompt(self, name: str, arguments: dict[str, str] | None = None, *, ...
                      ) -> types.GetPromptResult: ...

# Source: .venv/Lib/site-packages/mcp/client/session.py:1212-1232
async def complete(
    self,
    ref: types.ResourceTemplateReference | types.PromptReference,
    argument: dict[str, str],          # {"name": ..., "value": ...} -> CompletionArgument(**argument)
    context_arguments: dict[str, str] | None = None,
) -> types.CompleteResult: ...
```
`MCPManager.call_tool`'s 120-second hardcoded timeout (`mcp_client.py:295`) is a reasonable
default to reuse for these new calls too — per-server configurable timeouts are MCP-21
(workstream C), out of this phase's scope; don't invent a second timeout knob here.

### Pattern 3: Non-`_content_to_text`-shaped result flattening

**What:** `_content_to_text` (`mcp_client.py:426-434`) only handles `CallToolResult`'s
`content: list[ContentBlock]` where every block might have `.text`. Resources and prompts need
their own renderers because their shapes are different:

```python
# ReadResourceResult.contents: list[TextResourceContents | BlobResourceContents]
# Source: mcp_types/_types.py:900-938
def _resource_contents_to_text(contents: list) -> str:
    parts = []
    for c in contents:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
        else:
            blob = getattr(c, "blob", None)  # base64 str, BlobResourceContents
            size = len(blob) if blob else 0
            parts.append(f"[binary resource uri={c.uri} mime_type={c.mime_type} "
                          f"base64_len={size} — not inlined, see metadata]")
    return "\n".join(parts) if parts else "(no content)"

# GetPromptResult.messages: list[PromptMessage(role, content: ContentBlock)]
# Source: mcp_types/_types.py:1323-1338
def _prompt_messages_to_text(messages: list) -> str:
    lines = []
    for m in messages:
        text = getattr(m.content, "text", None)  # TextContent
        if text is not None:
            lines.append(f"[{m.role}]: {text}")
        else:
            lines.append(f"[{m.role}]: [non-text content block: {type(m.content).__name__}]")
    return "\n".join(lines)
```
**Why not reuse `_content_to_text` verbatim:** its `str(chunk)` fallback for non-text blocks is
the exact behaviour ADR 0004 and `CAP-CONTENT-BLOCKS` call out as a bug (a Python repr landing in
the prompt). This phase's new renderers are new code with no legacy behaviour to preserve —
recommend they never repr-fallback, even though fixing the *existing* `_content_to_text` path is
explicitly MCP-25's job (workstream C), not this phase's.

### Anti-Patterns to Avoid

- **Calling `list_resources`/`list_prompts`/`complete` on every mounted server unconditionally.**
  A server with no `resources`/`prompts`/`completions` capability answers with a JSON-RPC error
  (`MCPError`), and advertising tools that always fail trains the model to distrust the tool list.
  Gate on `server_capabilities`, read once at connect.
- **Inlining a `BlobResourceContents.blob` (base64) directly into `ToolResult.content`.** It is
  unusable to the model as text, and can be arbitrarily large — the opposite of what ADR 0004's
  forthcoming `max_result_chars` (MCP-22) is trying to protect against. Keep it out of `content`,
  put the marker there and the raw blob in `metadata` if it must be carried at all.
  `Message`/`types.py` (`agent86.types`) stays provider-agnostic either way, since the flattening
  happens entirely inside `mcp_client.py` before the result becomes an ordinary `ToolResult`.
- **Re-inventing pagination.** All four new list results (`ListResourcesResult`,
  `ListResourceTemplatesResult`, `ListPromptsResult`) inherit `PaginatedResult.next_cursor`
  (`mcp_types/_types.py:190-195`), matching `list_tools()`'s existing un-paginated single-page
  call (`mcp_client.py:221`). No corpus server has demonstrated pagination need
  (`docs/mcp-conformance-matrix.md` CAP-PAGINATION row: "absent... deferred to workstream C").
  Calling once with `params=None` and ignoring `next_cursor` is consistent with existing
  behaviour, not a new gap this phase introduces.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Resources/prompts/completion wire calls | A custom JSON-RPC client for `resources/list`, `resources/read`, `prompts/list`, `prompts/get`, `completion/complete` | `ClientSession.list_resources` / `read_resource` / `list_resource_templates` / `list_prompts` / `get_prompt` / `complete` (all present, `session.py:852-1232`) | The SDK already implements request construction, response typing (Pydantic models), and error mapping (`MCPError`) for all six methods — there is nothing left to hand-roll |
| Capability negotiation | Manually parsing `InitializeResult` | `session.server_capabilities` property (`session.py:791-798`), populated automatically by `initialize()`'s `adopt()` call | Already computed and cached by the SDK; re-deriving it risks drifting from what the SDK actually negotiated |
| Result pagination bookkeeping | A cursor-tracking loop | Deliberately **not** built this phase — single-page calls, matching `list_tools()`'s existing behaviour (see Anti-Patterns) | No corpus server needs it yet (matrix CAP-PAGINATION); building it now is scope creep into workstream C |

**Key insight:** every wire-level piece this phase needs is already implemented in the installed
SDK. The entire phase is client-side plumbing — wrapping already-correct SDK calls as `Tool`
instances and flattening their results into `ToolResult.content: str` — not new protocol code.

## Common Pitfalls

### Pitfall 1: Calling a capability the server never declared

**What goes wrong:** `session.list_resources()` (or `list_prompts`/`complete`) against a server
that didn't advertise the matching `ServerCapabilities` field raises `MCPError` (a JSON-RPC error
response, typically "Method not found").
**Why it happens:** Nothing in the SDK stops you from calling it — the gating is advisory, spec-
level, not enforced client-side (confirmed: `session.py` has no `check_capability`-style guard
before these methods send their request).
**How to avoid:** Gate tool *registration* on `session.server_capabilities` at connect time (see
Pattern 1), so the tool simply never appears in a server's tool list rather than appearing and
always failing.
**Warning signs:** A model repeatedly retrying a `list_resources`/`list_prompts` call that always
returns a soft `ToolResult(ok=False, error=...)` — `MCPTool.run`'s existing `except Exception`
wrap (mirror this for the new tools) will catch `MCPError` fine, but a tool that can never
succeed is still a UX defect, not just a caught exception.

### Pitfall 2: `subscribe_resource`/`unsubscribe_resource` are `@deprecated` on the installed SDK

**What goes wrong:** Both methods carry a `@deprecated(..., category=MCPDeprecationWarning)`
decorator (`session.py:932-952`) — `"resources/subscribe is removed as of 2026-07-28; use
Client.listen() instead."` — so every call emits a `MCPDeprecationWarning` (a `UserWarning`
subclass, shown by default, not silenced like the stdlib `DeprecationWarning`).
**Why it happens:** The SDK's `subscribe_resource` is the `2025-11-25`-era call; the *newer*
`2026-07-28` protocol replaces it with `Client.listen()`. Per Phase 10's D-01 ruling
(`docs/mcp-conformance-audit-2026-09.md:22-33`), agent86 negotiates `2025-11-25`
(`LATEST_HANDSHAKE_VERSION`), so this is still the **correct, spec-compliant call for the
protocol version agent86 actually speaks** — the deprecation is a forward notice about a protocol
revision agent86's client cannot reach yet, not a bug in using it now.
**How to avoid:** Either accept the warning (it will not fail tests — `pyproject.toml`'s
`[tool.pytest.ini_options]` has no `filterwarnings`, confirmed by grep) or wrap the call site in
`warnings.catch_warnings()` with a comment explaining why the deprecated call is still correct.
Document the choice; don't silently suppress without a comment, since a future reader will
otherwise "fix" it by removing the call entirely.
**Warning signs:** Noisy `MCPDeprecationWarning` lines in test output or `--plain` stderr if left
unhandled.

### Pitfall 3: Flattening a `BlobResourceContents` straight into the model's context

**What goes wrong:** A resource read that returns binary content (`BlobResourceContents.blob`, a
base64 string) can be large and is not human/model-readable text; joining it verbatim into
`ToolResult.content` the way `_content_to_text` joins `.text` wastes the conversation budget on
unusable data.
**Why it happens:** The naive symmetric move — "treat `.blob` like `.text`" — is the obvious
first draft, and there is no compiler-enforced signal stopping it (both are plain `str` fields on
sibling Pydantic models).
**How to avoid:** Branch on which field is present (`TextResourceContents.text` vs
`BlobResourceContents.blob`) and never inline the blob; see Pattern 3's `_resource_contents_to_text`.
**Warning signs:** A `read_resource` call against an image/binary resource (`server-everything`'s
`get-tiny-image`-adjacent resource URIs, or any file server's images) produces a multi-KB base64
string in the transcript.

### Pitfall 4: Assuming `server-everything`'s tool/resource/prompt surface hasn't moved

**What goes wrong:** Phase 10's live MCP-07 run already found two tools
(`gzip-file-as-resource`, `simulate-research-query`) present on
`@modelcontextprotocol/server-everything@2026.8.31` that weren't in the original 16-tool
head-start list — the demo package's surface **changed between the head-start read and the
audit's live run**, in the same milestone (`docs/mcp-conformance-audit-2026-09.md:104-111`).
**Why it happens:** `server-everything` is a demo/conformance-instrument package actively
maintained upstream; its exact resource URIs, prompt names, and `completable` argument name are
not contractually stable.
**How to avoid:** This phase's success criterion 2 ("`list_prompts`/`get_prompt` return its 3
prompts, and `complete()` returns suggestions for the `completable` argument one of them
exposes") should be verified against a **live run at plan/execution time**, not assumed from this
research document or from Phase 10's audit text. Re-pin the version
(`npm view @modelcontextprotocol/server-everything version`) and re-observe before writing an
integration test that hardcodes prompt names or argument names.
**Warning signs:** A test hardcoding a specific prompt name or resource URI from this research
document without re-verifying it against the currently-pinned package version.

## Code Examples

### `MCPTool.run`'s existing error-wrapping contract (the pattern every new tool must follow)

```python
# Source: src/agent86/tools/mcp_client.py:62-69 (existing, unmodified)
def run(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
    try:
        text = self._manager.call_tool(self._server, self._tool, call.arguments)
    except Exception as exc:
        return ToolResult(
            call_id=call.id, name=self.name, ok=False, error=f"MCP call failed: {exc}"
        )
    return ToolResult(call_id=call.id, name=self.name, content=text)
```
Every new synthetic tool (`MCPListResourcesTool`, `MCPReadResourceTool`, etc.) must follow this
exact shape — `except Exception`, never let an `MCPError` or transport failure escape `run()` —
per CLAUDE.md's hard rule ("Tool execution must never raise... always return a structured
`ToolResult` error").

### `ServerCapabilities` — the exact fields this phase gates on

```python
# Source: .venv/Lib/site-packages/mcp_types/_types.py:485-505
class ServerCapabilities(MCPModel):
    experimental: dict[str, dict[str, Any]] | None = None
    logging: LoggingCapability | None = None
    prompts: PromptsCapability | None = None       # PromptsCapability.list_changed: bool | None
    resources: ResourcesCapability | None = None    # .subscribe: bool | None, .list_changed: bool | None
    tools: ToolsCapability | None = None
    completions: CompletionsCapability | None = None  # empty marker class, presence is the signal
```

### `CompleteRequest`'s `ref` union — resource-template vs prompt completion

```python
# Source: .venv/Lib/site-packages/mcp_types/_types.py:1742-1782
class ResourceTemplateReference(MCPModel):
    type: Literal["ref/resource"] = "ref/resource"
    uri: str

class PromptReference(MCPModel):
    type: Literal["ref/prompt"] = "ref/prompt"
    name: str
    title: str | None = None

class CompletionArgument(MCPModel):
    name: str
    value: str
```
A `complete()` call therefore needs the caller (the model, via the new `MCPCompleteTool`'s Args)
to supply: which kind of ref (`"resource"` or `"prompt"`), the ref's `uri` or `name`, and the
argument `name`/`value` being completed. `context_arguments` (previously-resolved template
variables) is optional and can be omitted for this phase's minimal implementation.

## Runtime State Inventory

Not applicable — this is a greenfield additive-tool phase, not a rename/refactor/migration.
Confirmed: no stored data, live service config, OS-registered state, secret/env-var names, or
build artifacts reference "resources"/"prompts" as identifiers that would need migrating; this
phase only adds new call sites and new tool names (`mcp__{server}__list_resources` etc.), which
are newly minted, not renamed from anything.

## Common Pitfalls
(see above — merged into one section per this document's structure)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `ClientSession(read, write)` → `initialize()` → `list_tools()` only (`mcp_client.py:219-221`) | Same connect sequence, plus capability-gated `list_resources`/`read_resource`/`list_resource_templates`/`subscribe_resource`/`list_prompts`/`get_prompt`/`complete` tools registered from `session.server_capabilities` | This phase | Closes `CAP-RESOURCES`, `CAP-RESOURCE-TEMPLATES`, `CAP-RESOURCE-SUBSCRIBE` (call-site only), `CAP-PROMPTS`, `CAP-COMPLETION` from `absent` to `implemented` in `docs/mcp-conformance-matrix.md` |
| `resources/subscribe` as the standing subscription mechanism | Deprecated in the `2026-07-28` protocol revision in favor of `Client.listen()` | SDK marks it `@deprecated` now; the protocol revision itself is `2026-07-28`, not yet adopted by agent86 (D-01) | Still the correct call for the `2025-11-25` revision agent86 negotiates; a future protocol-revision-adoption phase (the standing "`2026-07-28` adoption" open question, `docs/mcp-conformance-audit-2026-09.md`) would need to migrate this call site |

**Deprecated/outdated:** `ClientSession.subscribe_resource`/`unsubscribe_resource` are marked
deprecated on the *installed* SDK relative to the *newer* protocol revision, but are not
deprecated relative to the protocol revision agent86 actually speaks. Do not "fix" this by
removing the calls — that would silently drop `CAP-RESOURCE-SUBSCRIBE`'s call site.

## Open Questions

1. **Should `subscribe_resource`/`unsubscribe_resource` both ship this phase, or `subscribe_resource` alone?**
   - What we know: the roadmap's Matrix rows list names only `subscribe_resource` ("the
     `subscribe_resource` call site only"); the update notification (what actually happens after
     a subscription fires) is explicitly deferred to the later `message_handler`/notification
     phase (MCP-24, referenced as "Proposed Phase 17" in the audit doc).
   - What's unclear: whether shipping `subscribe_resource` without a paired
     `unsubscribe_resource` leaves a resource-leak-shaped gap (a subscription with no way to
     cancel it) that a reviewer would flag.
   - Recommendation: ship both — `unsubscribe_resource` is the same SDK shape
     (`session.py:947-952`), same capability gate, and near-zero marginal cost; the roadmap's
     wording most likely means "the notification handling is out of scope," not "unsubscribe is
     out of scope." Confirm with the plan author before treating this as settled.

2. **What is the exact prompt name and `completable` argument name on the currently-pinned
   `server-everything@2026.8.31`?**
   - What we know: Phase 10's audit confirms 3 prompts exist and one exposes a `completable`
     argument (`docs/mcp-conformance-audit-2026-09.md`, corpus table), but did not name them —
     MCP-07's live run enumerated *tools*, not prompts, since prompts were unreachable through
     agent86 before this phase existed.
   - What's unclear: the literal prompt/argument names to hardcode into an integration test or
     manual-verification script.
   - Recommendation: a throwaway scratchpad script (same pattern as MCP-07's evidence-gathering
     run, `docs/mcp-conformance-audit-2026-09.md:59-72` — never committed to the repo tree) should
     connect, call `list_prompts()`, and record the real names before writing the success-
     criterion-2 verification, exactly as Phase 10 did for the tool list. `npx`/`node` are
     confirmed available in this environment (see Environment Availability).

3. **Does `side_effecting=True` or `False` best fit `subscribe_resource`?**
   - What we know: `MCPTool`'s existing default is `side_effecting = not read_only` — a genuine
     external effect gets approval-gated; a `readOnlyHint`-annotated tool doesn't. Subscribing
     creates server-side subscription state (not destructive, not data-mutating, but not a pure
     read either).
   - What's unclear: there is no server-declared `readOnlyHint` equivalent for a *synthetic*
     tool this phase invents (it isn't a remote tool the server annotated) — this phase must pick
     a default itself.
   - Recommendation: default `side_effecting=False` for `list_resources`/`read_resource`/
     `list_resource_templates`/`list_prompts`/`get_prompt`/`complete` (pure reads, no state
     change), and `side_effecting=True` for `subscribe_resource`/`unsubscribe_resource` (creates/
     removes server-side state, and — until MCP-24 lands — the resulting notification is silently
     dropped, so an unapproved background subscription would be invisible to the user). Flagged
     as this phase's own discretionary call, not derived from an existing pattern.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ / pytest-asyncio 0.23+ (`pyproject.toml:59`); `asyncio_mode = "auto"` (`pyproject.toml:119`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (no separate `pytest.ini`) |
| Quick run command | `pytest tests/unit/test_mcp.py tests/integration/test_mcp_client.py -q` |
| Full suite command | `pytest -q` (default `addopts = "-m 'not packaging'"` already excludes the slow packaging suite) |

No `mcp`-extra-specific pytest marker exists; the established pattern (both
`tests/unit/test_mcp.py` and `tests/integration/test_mcp_client.py`) is a module-level
`try: import mcp.server.mcpserver; _HAS_MCP_SERVER = True; except ImportError: False`, then
`@pytest.mark.skipif(not _HAS_MCP_SERVER, ...)` per real-transport test — never a bare
`pytest.importorskip` at module scope, which would also skip the mock-only tests in the same
file. Follow this exact pattern for any new live-stdio test.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| MCP-14 | `list_resources`/`read_resource` round-trip against a real (non-mocked) stdio server | integration | `pytest tests/integration/test_mcp_client.py -k resource -q` | ❌ Wave 0 — extend `live_mcp_server.py` with `.resource()`-decorated resources, mirroring the existing `add`/`shout`/`get_env` tool pattern |
| MCP-14 | Capability-gated registration — a server with no `resources` capability gets no resource tools | unit | `pytest tests/unit/test_mcp.py -k resources_capability -q` | ❌ Wave 0 — needs a fake `ClientSession`/`ServerCapabilities` fixture, following `_install_fake_transport`'s existing pattern (`tests/unit/test_mcp.py:328-364`) |
| MCP-14 | Blob resource content never inlines into `ToolResult.content` | unit | `pytest tests/unit/test_mcp.py -k blob_resource -q` | ❌ Wave 0 |
| MCP-15 | `list_prompts`/`get_prompt` round-trip against a real stdio server | integration | `pytest tests/integration/test_mcp_client.py -k prompt -q` | ❌ Wave 0 — extend `live_mcp_server.py` with a `.prompt()`-decorated prompt |
| MCP-15 | `complete()` returns suggestions for a `completable` prompt argument | integration | `pytest tests/integration/test_mcp_client.py -k complete -q` | ❌ Wave 0 — `MCPServer.completion()` decorator confirmed present (see Environment Availability); needs a `.completion()`-decorated handler on `live_mcp_server.py` |
| Roadmap SC1 | Real `list_resources → read_resource` against `@modelcontextprotocol/server-filesystem` | manual / evidence-gathering (not committed to CI, per Phase 10's D-03: "CI must stay network-free and `npx`-free") | scratchpad script, same pattern as `docs/mcp-conformance-audit-2026-09.md`'s MCP-07 run | N/A — evidence recorded in the plan/VALIDATION doc, not a pytest file |
| Roadmap SC2 | `list_prompts`/`get_prompt` return `server-everything`'s 3 prompts; `complete()` suggests for its `completable` argument | manual / evidence-gathering, same reasoning as SC1 | scratchpad script | N/A |
| Roadmap SC3 | Matrix re-audit moves the 4 rows `absent` → `implemented` | docs | `pytest tests/unit/test_docs_consistency.py -q` (structural checks only — does not itself validate the *rating*, a human/plan edit updates `docs/mcp-conformance-matrix.md`) | ✅ exists (`tests/unit/test_docs_consistency.py`), enforces matrix *shape*, not content |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_mcp.py tests/integration/test_mcp_client.py -q`
- **Per wave merge:** `pytest -q` (full suite, packaging excluded by default)
- **Phase gate:** full suite green, plus the two manual live-evidence runs (SC1 against
  `server-filesystem`, SC2 against `server-everything`) recorded in the phase's VALIDATION
  artifact before `docs/mcp-conformance-matrix.md` is edited to rule the four rows `implemented`.

### Wave 0 Gaps

- [ ] `tests/integration/live_mcp_server.py` — add a `.resource()`-decorated resource, a
      `.prompt()`-decorated prompt (with at least one `completable`-style argument if
      `MCPServer.completion()` supports declaring one — verify at plan time), and a
      `.completion()` handler, so CI can exercise resources/prompts/completion without network or
      `npx` (mirrors the existing `add`/`shout`/`get_env` tools added for SEC-04 in plan 10-01)
- [ ] `tests/unit/test_mcp.py` — a fake `ServerCapabilities`-bearing session fixture (extending
      `_install_fake_transport`) so capability-gated registration can be unit-tested without a
      real server
- [ ] Framework install: none — `mcp` extra is already a dev/test dependency
      (`pyproject.toml:59,62`)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| `mcp` Python SDK | Every call site this phase adds | ✓ | 2.0.0 (installed; `pyproject.toml` floor `>=1.0`) | — |
| `mcp.server.mcpserver.MCPServer` (`.resource()`/`.prompt()`/`.completion()` decorators) | Extending `live_mcp_server.py` for CI-safe integration tests | ✓ | confirmed via `dir(MCPServer("x"))` in this session: `resource`, `prompt`, `completion`, `add_resource`, `add_prompt`, `list_resources`, `read_resource`, `list_prompts`, `get_prompt`, `list_resource_templates` all present | — |
| Node.js / `npx` (for a live `server-everything`/`server-filesystem` evidence run) | Roadmap success criteria 1 and 2 (manual evidence, not committed CI) | ✓ | node v22.22.0; `npx.cmd` (Volta shim) 10.9.4 — same combination Phase 10's MCP-07 run used | If unavailable at execution time: the plan should still ship the capability-gated tools and CI-safe `live_mcp_server.py` tests; success criteria 1/2 would need to be verified by whoever has `npx` access, flagged as an outstanding manual step (same posture Phase 3 took for its Windows Terminal manual verification) |
| `@modelcontextprotocol/server-filesystem` | Roadmap SC1 | not installed; installable via `npx -y @modelcontextprotocol/server-filesystem@<pinned>` | pinned `@2026.8.31` as of Phase 10's audit (2026-09-22) — **re-verify via `npm view @modelcontextprotocol/server-filesystem version` before relying on this pin**, since a day has passed | Same manual-fallback note as above |
| `@modelcontextprotocol/server-everything` | Roadmap SC2 | not installed; installable via `npx -y @modelcontextprotocol/server-everything@<pinned>` | pinned `@2026.8.31` as of Phase 10's audit — **re-verify** | Same manual-fallback note as above |

**Missing dependencies with no fallback:** none — every dependency this phase's *implementation*
needs (the `mcp` SDK, `MCPServer`'s server-side decorators for CI tests) is already installed and
verified.

**Missing dependencies with fallback:** the two npm-hosted demo servers (`server-filesystem`,
`server-everything`) are not installed but are `npx`-fetchable on demand, exactly as Phase 10's
MCP-07 evidence run did it — not a blocker, just a manual/one-time step outside the committed test
suite (per D-03, they must never become a CI dependency).

## Sources

### Primary (HIGH confidence)

- `.venv/Lib/site-packages/mcp/client/session.py:852-1232` — every `ClientSession` method this
  phase needs (`list_resources`, `list_resource_templates`, `read_resource`,
  `subscribe_resource`/`unsubscribe_resource`, `list_prompts`, `get_prompt`, `complete`), read in
  full this session, including their `@deprecated` markers and docstrings
- `.venv/Lib/site-packages/mcp/client/session.py:576-798` — `_build_capabilities`,
  `server_capabilities` property, and `initialize()`/`adopt()` confirming when
  `server_capabilities` becomes available
- `.venv/Lib/site-packages/mcp_types/_types.py:107-198, 430-505, 793-938, 1103-1338, 1742-1817` —
  every wire type this phase touches: `PaginatedRequestParams`/`PaginatedResult` (cursor
  fields), `ServerCapabilities`/`PromptsCapability`/`ResourcesCapability`/`CompletionsCapability`,
  `Resource`/`ResourceTemplate`/`ResourceContents`/`TextResourceContents`/
  `BlobResourceContents`/`ReadResourceResult`, `Prompt`/`PromptArgument`/`ListPromptsResult`/
  `GetPromptRequestParams`/`PromptMessage`/`GetPromptResult`, `ResourceTemplateReference`/
  `PromptReference`/`CompletionArgument`/`Completion`/`CompleteResult`
- `.venv/Lib/site-packages/mcp/shared/exceptions.py` — `MCPError` (raised for JSON-RPC error
  responses, e.g. an uncapable server), `MCPDeprecationWarning`
- `src/agent86/tools/mcp_client.py` (full file, 464 lines) — the existing client this phase
  extends: `MCPTool`, `MCPManager`, `_serve`, `call_tool`, `_content_to_text`, `_is_read_only`,
  `_tool_schema`
- `src/agent86/tools/base.py` — `Tool` ABC, `ToolContext`, `EmptyArgs`, `Tool.run`'s
  never-raise contract
- `src/agent86/types.py:108-190` — `ToolSpec`, `ToolCall`, `ToolResult` (confirms `content: str`,
  `metadata: dict[str, Any]`), `Message`
- `src/agent86/config.py:293-294, 358-398` — `MCPConfig`, `MCPServerConfig` (confirms no
  `max_result_chars` field yet — that's MCP-22/ADR 0004, not this phase)
- `docs/ARCHITECTURE.md:474-586` (§7 Tool & Execution Tier), `:1121-1204` (§15, current "not
  built" table rows for the five `CAP-*` ids this phase closes)
- `docs/mcp-conformance-matrix.md:35-54` — rows `CAP-TOOLS-LIST` through `CAP-ROOTS`, especially
  `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`/`CAP-RESOURCE-SUBSCRIBE`/`CAP-PROMPTS`/
  `CAP-COMPLETION` (lines 40-44) and `CAP-CONTENT-BLOCKS`/`CAP-PAGINATION`
  (lines 39, 51) for the boundary between this phase and MCP-22/MCP-25
- `docs/mcp-conformance-audit-2026-09.md` (full read: scope/method, pinned corpus, MCP-07 live
  run, the nine head-start rows, Proposed Phase 11 section) — the phase's own source document
- `docs/adr/0004-mcp-result-cap-location.md` — confirms `max_result_chars`/`structured_content`
  are explicitly MCP-22's scope, not this phase's
- `docs/adr/README.md` — ADR convention (not directly load-bearing for this phase; no new ADR is
  required, since the design question is settled by the roadmap's own success-criterion wording)
- `tests/integration/test_mcp_client.py`, `tests/unit/test_mcp.py`,
  `tests/integration/live_mcp_server.py` (all read in full) — existing test patterns
  (`_install_fake_transport`, `skipif(not _HAS_MCP_SERVER)`, real-SDK-object regression tests)
  this phase's new tests should follow
- `pyproject.toml:39-62, 117-126` — `mcp` extra definition, dev/test extras, pytest config (no
  `filterwarnings`, confirmed by direct grep)
- `tests/integration/test_scripting_contract.py:150-172` — `REQUIRED_JSON_KEYS <= set(payload)`
  confirms the `run --json` contract is structurally subset-checked, so new additive keys (if any
  surface through it) cannot break the existing contract test
- Direct commands run this session: `python -c "import importlib.metadata as m;
  print(m.version('mcp'))"` → `2.0.0`; `python -c "from mcp.server.mcpserver import MCPServer;
  ..."` → confirmed `.resource`/`.prompt`/`.completion` methods present; `command -v npx.cmd`,
  `node --version` → v22.22.0, `npx.cmd --version` → 10.9.4

### Secondary (MEDIUM confidence)

- `docs/mcp-conformance-audit-2026-09.md:39-40` — the `server-filesystem`/`server-everything`
  npm version pins (`@2026.8.31`), dated 2026-09-22 (yesterday relative to this research); treated
  as MEDIUM because npm-hosted demo packages can move and the pin should be re-verified at plan
  time (flagged explicitly in Open Questions and Environment Availability)

### Tertiary (LOW confidence)

None — every claim in this document is grounded in a file path/line number this session directly
read, or a command this session directly ran. No WebSearch was used (Context7/WebFetch were not
needed either — the installed SDK source itself is the primary source, and it was fully
available on disk).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency; every SDK method verified against the actually-
  installed `mcp` 2.0.0 source, not documentation or training-data recall
- Architecture: HIGH — the per-server synthetic-tool pattern is a direct, minimal extension of
  the existing `MCPTool`/`_serve`/`MCPManager` architecture, every piece of which was read in full
- Pitfalls: HIGH for the SDK-level pitfalls (deprecation warning, capability gating — both
  directly observed in source); MEDIUM for the exact prompt/argument names on
  `server-everything`'s current release (Open Question 2) and for whether `unsubscribe_resource`
  is in-scope by the roadmap's literal wording (Open Question 1)

**Research date:** 2026-09-23
**Valid until:** 2026-10-07 (14 days) — shorter than the default 30-day stability window because
this phase's live-evidence success criteria depend on two independently-versioned npm demo
packages (`server-filesystem`, `server-everything`) that have already been observed to change
their tool/resource/prompt surface between two points in the same milestone
(`docs/mcp-conformance-audit-2026-09.md:104-111`); re-verify their pinned versions at plan time
regardless of this date.
