# Phase 13: Per-server timeouts, the result cap, and non-text content - Research

**Researched:** 2026-09-24
**Domain:** MCP client hardening (agent86's `tools/mcp_client.py`) — config schema growth, a
prompt-side truncation cap, and non-text `ContentBlock` rendering
**Confidence:** HIGH

## Summary

Phase 13 applies three already-ruled decisions rather than deriving new ones: ADR 0004 names the
result-cap field, default, and behaviour; the audit's head-start rows 4/5/6 confirm the three
defects against the current code with exact file:line citations; and Phase 12 just finished
repairing the `_serve` lifecycle these timeouts must compose with. All the client-side plumbing
needed already has a working precedent in the same file (`MCPManager.servers: dict[str,
MCPServerConfig]` is available at every call site keyed by server name) and in `config.py`
(`ProviderConfig.connect_timeout_s`/`read_timeout_s` is the exact naming and default-constant
pattern to copy for `MCPServerConfig`). The three success criteria are independent and can be
built as three separate, narrow changes to the same file plus a schema addition — no new
dependency, no architecture question left open.

The one substantive risk the roadmap already flags — the 8,000-char default silently truncating a
legitimate large result from a pinned corpus tool (`server-filesystem`'s `read_text_file`,
`mcp-server-git`'s `log`/`diff`) — needs a live-run audit before the default ships, exactly as
Phase 11's `11-EVIDENCE.md` did for prompts/resources. This is a "first plan" concern, not a
research gap: the mechanism is proven (run the pinned corpus live, record output lengths).

**Primary recommendation:** Build the three items as three separable slices — (1) schema +
timeout wiring, (2) a shared truncation helper called from `_content_to_text` only (ADR 0004
scopes `structured_content` out), and (3) a shared non-repr rendering helper for
`ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink` reused by both `_content_to_text`
and (optionally, for consistency) `_prompt_messages_to_text`, which already has the correct
never-repr pattern to copy.

## User Constraints

No `CONTEXT.md` exists yet for Phase 13 (`.planning/phases/13-.../` contains only `.gitkeep`) —
`/gsd:discuss-phase` has not been run for this phase. There are no locked decisions, discretion
notes, or deferred ideas to copy verbatim. The planner should treat ROADMAP.md's Success Criteria
and ADR 0004 as the binding constraints instead (see Phase Requirements below), and everything
this document calls "recommended" is Claude's own research-driven judgment, not a user ruling.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-21 | Per-server configurable timeouts (today hardcoded: 30s connect, 120s call; `MCPConfig` carries only `enabled`) | Exact hardcode sites confirmed at current line numbers (§ Code Sites below); `ProviderConfig` already has the identical `connect_timeout_s`/`read_timeout_s` pattern to copy field-naming and default-constant style from |
| MCP-22 | A prompt-side result cap, as ruled by ADR 0004 | ADR 0004 fully read: field name, default, home (`MCPServerConfig.max_result_chars`), truncate-never-drop-never-raise behaviour, `structured_content` explicitly out of scope |
| MCP-25 | Non-text content blocks handled (image/audio/embedded-resource render as something other than `str(chunk)`) | SDK's real field shapes confirmed via `mcp` 2.0.0 installed package (`ImageContent.data`/`mime_type`, `AudioContent.data`/`mime_type`, `EmbeddedResource.resource` → `TextResourceContents`/`BlobResourceContents`, `ResourceLink.uri`/`name`/`mime_type`/`size`); `_prompt_messages_to_text`'s existing never-repr marker pattern (Phase 11) is the model to reuse |

## Project Constraints (from CLAUDE.md)

- **`config.py` stays read-only.** The new `MCPServerConfig` fields (`connect_timeout_s`,
  `call_timeout_s`, `max_result_chars`) are schema additions to `config.py`'s Pydantic model
  (reading config is fine there), but any `/config mcp` UI write-back of these fields MUST go
  through `config_writer.py`'s `plan_edit`/`apply_edit`, never write TOML from `config.py`
  directly. `config_writer.py` is already generic (dotted key-path diffs) — no MCP-specific
  change is needed there for plain scalar fields.
- **Tool execution must never raise.** `_content_to_text` and the new content-block renderer must
  return a string in every case; ADR 0004 states this explicitly ("it never raises — a tool must
  never raise into the loop"). This applies equally to the non-text rendering helper (MCP-25):
  an unrecognized/future content-block type must fall back to a safe named marker, not raise or
  repr.
- **Lazy imports.** Nothing about this phase needs a new top-level import; `mcp.types` classes
  are already referenced lazily inside functions (`complete()` imports `from mcp import types as
  mcp_types` inside its `_call` closure) — follow that same pattern for any new `isinstance`
  checks against `ImageContent`/`AudioContent`/`EmbeddedResource`/`ResourceLink`.
- **`run --json` keys additive-only.** A truncation marker or a content-block marker appearing in
  `ToolResult.content` is a string-content change, not a new/removed key — compatible. If a new
  `metadata` key is added (e.g. `metadata["truncated"]` or `metadata["non_text_blocks"]`, mirroring
  the existing `metadata["binary"]`/`metadata["non_text_blocks"]` precedent in
  `_resource_contents_to_text`/`_prompt_messages_to_text`), that is additive too.
- **No new core dependency.** Everything needed (the `mcp.types` content classes) is already
  imported by the `mcp` extra; no new package.
- **Testing conventions.** New tests belong in `tests/unit/test_mcp.py` (fake-transport unit
  tests, following `_install_fake_transport`/`_FakeCaps`/`_fake_result` helpers) and
  `tests/unit/test_config.py` (new `MCPServerConfig` field defaults/overrides, following
  `test_provider_config_default_timeouts`'s exact pattern). Live evidence, if the corpus audit
  needs it, belongs in a new `phases/13-.../13-EVIDENCE.md`, mirroring Phase 11's precedent.

## Standard Stack

No new libraries. This phase works entirely within the already-installed `mcp` SDK and the
project's own Pydantic config models.

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (Python SDK) | 2.0.0 (installed, confirmed via `importlib.metadata.version("mcp")`) | Provides `mcp.types.{TextContent,ImageContent,AudioContent,EmbeddedResource,ResourceLink,TextResourceContents,BlobResourceContents}` | Already the project's only MCP dependency; `CallToolResult.content: list[TextContent \| ImageContent \| AudioContent \| ResourceLink \| EmbeddedResource]` (confirmed via `CallToolResult.model_fields["content"].annotation`) |
| `pydantic` v2 | already a core dep | `MCPServerConfig` field additions | Existing model; no version change needed |

### Alternatives Considered

None — this phase is schema growth plus rendering logic on top of an existing, complete client.
No external alternative applies.

**Version verification:** `pip show mcp` / `python -c "import importlib.metadata as m;
print(m.version('mcp'))"` → confirmed `2.0.0` installed in `.venv`, matching the conformance
matrix's pinned `mcp SDK 2.0.0` header. No action needed.

## Architecture Patterns

### Recommended Project Structure

No new files. All three success criteria land in the two existing files:

```
src/agent86/
├── config.py            # MCPServerConfig gains connect_timeout_s, call_timeout_s, max_result_chars
└── tools/
    └── mcp_client.py     # start_server/_serve_once use cfg.connect_timeout_s;
                           # call_tool/_on_session use cfg.call_timeout_s;
                           # _content_to_text truncates at cfg.max_result_chars and renders
                           # non-text blocks via a shared helper
```

### Pattern 1: Per-server timeout fields, `ProviderConfig`'s exact precedent

**What:** `ProviderConfig` (`config.py:134-158`) already has this exact shape:

```python
# Source: src/agent86/config.py:144-145 (existing code, read verbatim)
connect_timeout_s: float = _DEFAULT_CONNECT_TIMEOUT_S
read_timeout_s: float = _DEFAULT_READ_TIMEOUT_S
```

**When to use:** Add the analogous pair to `MCPServerConfig` (`config.py:358-399`), using module
constants for the current hardcoded values so `start_server`'s default parameter and `call_tool`'s
hardcoded `120` both point at the same named constant the field defaults to — never two different
magic numbers for "the same 120":

```python
# Recommended shape — not yet in the code
class MCPServerConfig(BaseModel):
    ...
    connect_timeout_s: float = 30.0   # was: start_server's `timeout: float = 30.0` param default
    call_timeout_s: float = 120.0     # was: call_tool's hardcoded `timeout=120`, and
                                       # _on_session's `timeout: float = 120` default
    max_result_chars: int = 8_000     # ADR 0004's ruled default
```

**Where the value is read at call time — confirmed available:** `MCPManager.__init__` takes
`servers: dict[str, MCPServerConfig]` and stores it as `self.servers` (`mcp_client.py:642-648`),
and it is never discarded — `start()`, `server_statuses()`, and every capability call site's
governing server name can look up `self.servers[name]` for its configured timeouts. `call_tool`
and `_on_session` currently take only a bare `server: str`; the plan should have them resolve
`cfg = self.servers.get(server)` (falling back to the constant default if the server was removed
mid-flight, which `close()`/`stop_server()` can otherwise race) rather than threading `cfg` through
every call signature.

**Confirmed exact current hardcode sites (re-verified 2026-09-24, current `mcp_client.py`, not
copied from the roadmap's possibly-stale line numbers):**

| Site | Current | Line (confirmed) |
|------|---------|-------------------|
| `MCPManager.start_server` | `timeout: float = 30.0` parameter default | `mcp_client.py:808` |
| `MCPManager.call_tool` | `.result(timeout=120)` hardcoded | `mcp_client.py:1147` |
| `MCPManager._on_session` | `timeout: float = 120` parameter default | `mcp_client.py:1157` |

(The roadmap's own text cites `mcp_client.py:804,1136,1157` / `mcp-conformance-audit-2026-09.md`
cites `:166,295` — both predate Phase 12's edits to this file; the table above is the ground truth
as of the commit this research was performed against. **Re-confirm line numbers again at plan
time** — Phase 12 touched this file eight times since the audit was written.)

**MCPTestModal's own `TIMEOUT_S = 30.0`** (`tui/screens/mcp_test.py:42`) is a *UI* hard-cap
independent of `cfg.connect_timeout_s` — it wraps `start_server(..., timeout=self.TIMEOUT_S,
...)` and is deliberately generous for a first-run `npx` download. **Recommendation: leave this
one alone.** It answers a different question ("how long will the *test modal* wait before giving
up and showing a UI timeout message") than `connect_timeout_s` ("what does `start_server` itself
pass through to the coroutine's `.result(timeout=...)`"). If a plan wires
`MCPTestModal.TIMEOUT_S` to the configured `connect_timeout_s` instead, it should raise it to
`max(self.TIMEOUT_S, cfg.connect_timeout_s)` so a deliberately slow server's own configured budget
isn't silently overridden downward by the UI's fixed 30s — but this is a UI nicety, not required
by any of the three success criteria, and is **not itself part of MCP-21's stated scope**
(the roadmap's SC1 names only `start_server`/`call_tool`/the capability-tool call path).

### Pattern 2: The truncation cap — home, behaviour, and where NOT to apply it

**What ADR 0004 rules, verbatim (already binding, not to be re-derived):**
- Field: `MCPServerConfig.max_result_chars: int`, default **8,000**.
- Behaviour: truncate the joined body at the cap, append a **visible** marker — never drop
  silently, never raise.
- Scope: **only** `_content_to_text`'s existing text-join path (`CallToolResult.content` →
  `MCPTool.run`'s `call_tool()` return). `structured_content` is explicitly out of scope for this
  ADR (still silently dropped, pending a future ADR — do not fix it in this phase).

**Where it does NOT apply — confirmed by reading every call site producing model-facing text:**

| Call site | Function | In ADR 0004's scope? |
|-----------|----------|----------------------|
| `MCPTool.run` → `call_tool()` | `_content_to_text` | **Yes** — this is the function ADR 0004 names |
| `MCPReadResourceTool` → `read_resource()` | `_resource_contents_to_text` | **Not named by ADR 0004.** Open question below — recommend applying the same cap here for consistency (a large text resource is exactly as capable of blowing the budget as a large tool result), but this is a plan-time extension of the ruling, not the ruling itself |
| `MCPGetPromptTool` → `get_prompt()` | `_prompt_messages_to_text` | **Not named by ADR 0004.** Same open question — a prompt template's rendered text could also be large, though every corpus prompt observed so far is short |
| `MCPListResourcesTool`/`MCPListPromptsTool`/etc. | `_resources_to_text`/`_prompts_to_text`/etc. | Table listings, not raw content — bounded by list length already, lower risk |

**Recommendation:** implement the cap as a small, reusable helper —
`_truncate(text: str, limit: int) -> str` — called from `_content_to_text` (mandatory, ADR 0004)
and, at the planner's discretion, from `_resource_contents_to_text`/`_prompt_messages_to_text` too
(same `cfg.max_result_chars`, same visible-marker shape) so a large resource read or prompt render
gets the identical protection a tool call gets. This is the single largest scope judgment call
this research surfaces — flagged as an Open Question below rather than assumed.

**Visible marker shape — no existing precedent to copy verbatim (new territory).** The flight
recorder's `max_field_chars` clip (`observability/redact.py`, per ADR 0004's own comparison) is
the closest existing analogue but is trace-side, not prompt-side, and its exact marker text was
not inspected in this pass (not in `<files_to_read>`; recommend the plan author open
`observability/redact.py` briefly before choosing wording, so both truncation markers in the
codebase read consistently). A reasonable shape, consistent with this file's existing marker
style (`[binary resource uri=... — not inlined]`, `[non-text content block: TypeName — not
inlined]`):

```python
f"{text[:limit]}\n[... truncated at {limit} characters ({len(text) - limit} more) — " \
f"raise MCPServerConfig.max_result_chars for '{server}' to see more]"
```

Naming the server and the config field the model (or the user reading a transcript) would need to
change is more actionable than a bare "[truncated]".

**Truncate where in the pipeline?** `_content_to_text` is a bare function, not a method — it has
no `self` and thus no access to `self.servers[name].max_result_chars` today. It must gain a
`limit: int` parameter (or become a method / take `cfg`), threaded from `call_tool`'s existing
`server` lookup. Confirm no other caller of `_content_to_text` exists (grep before changing its
signature) — **confirmed: exactly one call site**, inside `call_tool`'s `_call()` closure
(`mcp_client.py:1142-1144`).

**Order relative to other truncation/redaction in the pipeline (answering the research
question directly):** `ToolResult.content` (the capped string) is what `call_tool()` returns; it
flows into `MCPTool.run`'s `ToolResult(content=text)`, then into the loop's message history and
from there into (a) the flight recorder — which applies its own, *separate*,
`max_field_chars`-based clip on top, at the trace boundary, unrelated to this cap — and (b) the
egress guardrail scan (`stage="egress_tool_args"`/similar), which operates on the *already
MCP-capped* text. **No double-truncation risk was found**: the flight recorder's clip and this
cap are independent, sequential, and each named for a different budget (trace file size vs.
prompt/context budget), exactly as ADR 0004's Context section states. No other global
truncation of tool output exists in `orchestration/` or `tools/base.py` that this research found —
confirm with a repo-wide grep for `max_field_chars`/`truncat` at plan time to be certain no
third truncator exists that would compound.

### Pattern 3: Non-text content — the exact SDK field shapes (verified against installed 2.0.0)

**What agent86 currently does wrong** (`mcp_client.py:1438-1446`, confirmed at these exact
lines):

```python
# Source: src/agent86/tools/mcp_client.py:1438-1446 (current code, the defect)
def _content_to_text(result: Any) -> str:
    parts: list[str] = []
    for chunk in getattr(result, "content", None) or []:
        text = getattr(chunk, "text", None)
        parts.append(text if text is not None else str(chunk))   # <-- the defect: Python repr
    ...
```

**What the SDK's `ContentBlock` union actually contains** (verified live against the installed
`mcp` 2.0.0 package, not assumed from training data):

```python
# CallToolResult.content: list[TextContent | ImageContent | AudioContent | ResourceLink |
#                                EmbeddedResource]   -- confirmed via
# CallToolResult.model_fields["content"].annotation

TextContent:       type, text, annotations, meta
ImageContent:      type, data, mime_type, annotations, meta        # data = base64 str
AudioContent:      type, data, mime_type, annotations, meta        # data = base64 str
EmbeddedResource:  type, resource, annotations, meta                # resource: Text|BlobResourceContents
ResourceLink:      name, title, uri, description, mime_type, size, icons, annotations, meta, type
TextResourceContents: uri, mime_type, meta, text
BlobResourceContents: uri, mime_type, meta, blob                    # blob = base64 str
```

**The existing correct pattern to copy** — `_prompt_messages_to_text`
(`mcp_client.py:1541-1565`), which Phase 11 (D-07) already wrote correctly for `PromptMessage`
content and explicitly notes it does NOT share code with `_content_to_text`'s still-buggy
fallback:

```python
# Source: src/agent86/tools/mcp_client.py:1553-1563 (existing correct pattern, Phase 11)
kind = type(content).__name__
non_text.append({"index": index, "role": role, "type": kind})
lines.append(f"[{role}]: [non-text content block: {kind} — not inlined]")
```

**Recommended rendering per block type (extending, not just generalizing, that pattern — MCP-25's
"real representation" bar is higher than a bare type-name marker, per the roadmap's own wording
and the risk section's example marker text):**

| Type | Field(s) to surface | Recommended marker (never the base64 payload) |
|------|----------------------|--------------------------------------------------|
| `ImageContent` | `mime_type`, `len(data)` | `[image: image/png, base64_len=16820 — not inlined]` |
| `AudioContent` | `mime_type`, `len(data)` | `[audio: audio/wav, base64_len=48000 — not inlined]` |
| `EmbeddedResource` with `resource: TextResourceContents` | `resource.uri`, `resource.mime_type`, `resource.text` | Inline the text (it's already textual and bounded by the same cap) — same treatment `_resource_contents_to_text` already gives a direct text resource read |
| `EmbeddedResource` with `resource: BlobResourceContents` | `resource.uri`, `resource.mime_type`, `len(resource.blob)` | `[embedded resource uri=... mime_type=... base64_len=... — not inlined]` — literally the same shape `_resource_contents_to_text` (`mcp_client.py:1488-1519`) already uses for a binary resource read; **reuse that function or its marker format rather than inventing a third one** |
| `ResourceLink` | `uri`, `name`, `mime_type`, `size` | `[resource link: uri=... name=... mime_type=... size=...]` — this one carries no payload at all (it's a pointer), so there is nothing to avoid inlining; just render its fields |
| Unknown/future type | `type(chunk).__name__` | Fall back to `_prompt_messages_to_text`'s existing `[non-text content block: {kind} — not inlined]` — never `str(chunk)` |

**Key architectural decision for the plan: one shared helper, not two parallel implementations.**
`_resource_contents_to_text` (binary-resource marker), `_prompt_messages_to_text` (generic
non-text marker) and the new `_content_to_text` fix all need overlapping logic (mime-type +
length descriptors for binary payloads; the never-repr fallback for anything else). Introducing a
single `_render_content_block(chunk) -> str` (or similar) that all three call is lower-risk than
three independently-drifting marker formats — flagged as a recommended refactor, not a
requirement, since `_prompt_messages_to_text`'s current behavior is already spec-compliant
("no repr") even though its marker is less informative than the table above. Do not break any of
the three's existing passing tests when unifying.

### Anti-Patterns to Avoid

- **Do not touch `structured_content`.** ADR 0004 is explicit that this is future scope; adding
  it now would be solving a problem this phase was not asked to solve and would blur MCP-22's
  boundary.
- **Do not silently drop truncated content or non-text blocks.** Both ADR 0004 (for the cap) and
  the CLAUDE.md "tool must never raise" rule (for both) require a visible, never-raising fallback.
- **Do not inline base64 anywhere**, even under the higher size cap this phase adds — that's the
  literal defect the roadmap goal describes ("no base64 blob reaches the prompt verbatim") and
  the cap is a size protection, not a permission to inline once "small enough".
- **Do not change `_MAX_RECONNECT_ATTEMPTS`/`_RECONNECT_BASE_DELAY_S`/`_RECONNECT_MAX_DELAY_S`.**
  These are explicitly commented as out of MCP-21's scope: "Hardcoded on purpose: per-server
  timeout/retry config is MCP-21's ruling, not this phase's" (`mcp_client.py:42-46`) — read
  literally, MCP-21 governs *connect*/*call* timeouts, not the reconnect *retry count/backoff*
  window. Confirm this reading with the user/planner if ambiguous, but the comment is unambiguous
  as written.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting which `ContentBlock` subtype a chunk is | A custom duck-typing chain (`hasattr(chunk, "data")` etc.) | `isinstance(chunk, mcp_types.ImageContent)` etc., imported lazily inside the function (matching `complete()`'s existing `from mcp import types as mcp_types` pattern) | The SDK's types are real Pydantic models with stable field names (verified above); `isinstance` is both clearer and immune to duck-typing collisions between `ImageContent`/`AudioContent` (both have `data`+`mime_type`) |
| String truncation with byte-safety for multi-byte chars | A custom slice-and-hope | Python's `str` slicing (`text[:limit]`) — already character-count based, matching ADR 0004's "8,000 characters" wording exactly (not bytes) | The ADR explicitly says characters, and Python str indexing is by code point, which matches |

**Key insight:** every piece of machinery this phase needs — capability-gated call sites,
config-driven per-server fields, never-raise marker rendering — already has a working precedent
in this exact file from Phases 11 and 12. The main risk is scope creep (touching
`structured_content`, or over-broadly capping every capability-tool output without flagging it as
a discretionary extension) rather than any missing tool or pattern.

## Runtime State Inventory

Not applicable — this is additive schema growth and rendering-logic fixes, not a rename, refactor,
or migration. No stored data, live service config, OS-registered state, secrets, or build
artifacts carry the old behavior in a way that needs migrating: existing `MCPServerConfig` TOML
entries have no `connect_timeout_s`/`call_timeout_s`/`max_result_chars` keys today, and Pydantic's
default values mean an absent key resolves to the old hardcoded numbers — "no existing config
changes behavior" (SC1) is satisfied by the default alone, no migration script needed.

## Common Pitfalls

### Pitfall 1: Stale line-number citations
**What goes wrong:** The roadmap (`mcp_client.py:808,1147,1157`) and the audit
(`mcp_client.py:166,295`) already disagree with each other and with this research's own
re-verification, because Phase 12 (8 plans, 4 waves) touched this file repeatedly after the audit
was written.
**Why it happens:** Line numbers drift with every commit; citations in planning docs are
snapshots, not live pointers.
**How to avoid:** Grep for the actual hardcoded values (`timeout: float = 30.0`,
`timeout=120`, `timeout: float = 120`) at plan/implementation time rather than trusting any
document's line numbers, including this one.
**Warning signs:** A grep that doesn't find the expected literal at the cited line.

### Pitfall 2: Threading `cfg`/`max_result_chars` through the wrong layer
**What goes wrong:** `_content_to_text` is a bare module function with no access to `self`. A
naive fix might pass the whole `MCPManager` or `MCPServerConfig` object into it, over-widening its
signature and coupling a small pure-text-rendering helper to the manager's internals.
**Why it happens:** The natural first instinct is "just pass what you need."
**How to avoid:** Pass only the two scalars the function needs (`limit: int` and, if the marker
should name the server, `server: str`) — keep `_content_to_text` a small pure function taking
primitives, matching the existing style of `_resources_to_text(resources: list[Any]) -> str`
and friends, which take exactly what they render, nothing more.
**Warning signs:** A test needing to construct a fake `MCPManager` just to unit-test
`_content_to_text`.

### Pitfall 3: The 8,000-char default silently breaking a legitimate corpus tool
**What goes wrong:** A pinned corpus tool (`server-filesystem`'s `read_text_file` on a large
file, `mcp-server-git`'s `log`/`diff` on a long history) legitimately returns >8,000 characters
today; shipping the default without checking would silently degrade behavior the roadmap
explicitly says must not happen.
**Why it happens:** ADR 0004's default was chosen from "no observed corpus-server tool result in
this audit's MCP-07 run came close to it" — but MCP-07's run exercised `server-everything`
specifically for the sampling/elicitation/progress question, not necessarily every tool on every
corpus server at realistic payload sizes (e.g., a large real git repo's `git log`).
**How to avoid:** The phase's first plan must run the pinned corpus live (same pattern as
`11-EVIDENCE.md`: `server-filesystem@2026.8.31` against a real large file, `mcp-server-git`
against a real repo with meaningful history, `server-everything`'s own large-payload tools like
`simulate-research-query` or `get-tiny-image`) and record actual character counts before the
8,000 default ships, OR document explicitly why the roadmap's already-stated audit precondition is
satisfied by MCP-07's existing evidence alone (a judgment call for the plan, not this research, to
make — flagged as **HIGH-priority Open Question** below).
**Warning signs:** A live corpus tool call returning a truncated result with no way to prove that
was expected.

### Pitfall 4: A call timeout firing mid-reconnect-backoff window
**What goes wrong:** `_serve`'s reconnect loop (Phase 12) has its own bounded backoff
(`_reconnect_backoff`, up to `_RECONNECT_MAX_DELAY_S = 30.0`s per attempt, up to
`_MAX_RECONNECT_ATTEMPTS = 5` attempts, ~31s total per outage per the module docstring). A model
call issued *during* that window hits `self._sessions.get(server)` returning `None` (the session
was popped by `_on_drop`/`_serve_once`'s `finally` before reconnect begins) — `call_tool` and
`_on_session` both already raise `self._unavailable_error(server)` in this state, which correctly
special-cases `state == "reconnecting"` to name the attempt count
(`mcp_client.py:1113-1120`). **This is already handled correctly and is orthogonal to
`call_timeout_s`** — a call during reconnect never reaches the `asyncio.run_coroutine_threadsafe(
...).result(timeout=cfg.call_timeout_s)` line at all, because `session is None` is checked first.
**How to avoid:** No code change needed for this interaction — confirm with a test that a call
issued while `_server_state[name] == "reconnecting"` gets the reconnecting-specific message, not a
timeout, and that this remains true once `call_timeout_s` is configurable (it should, since the
`session is None` guard runs before any timeout is applied).
**Warning signs:** A new test asserting `TimeoutError` where the existing `MCPServerUnavailable`
with the "reconnecting" message should fire instead.

### Pitfall 5: Unifying content-block rendering breaks a passing test
**What goes wrong:** `_resource_contents_to_text` and `_prompt_messages_to_text` already have
passing tests pinning their exact current marker text (e.g.
`test_blob_resource_content_is_never_inlined`, `test_non_text_prompt_block_is_marked_not_repred`
in `tests/unit/test_mcp.py`). If Pattern 3's shared-helper refactor changes their marker wording
to match the new richer format, those tests break.
**Why it happens:** Consolidating three near-duplicate marker formats into one is attractive but
touches code with existing test coverage pinning the old wording.
**How to avoid:** Either (a) keep `_resource_contents_to_text`'s and `_prompt_messages_to_text`'s
existing marker text byte-for-byte and only add the *new* `_content_to_text` fix using a
compatible-but-separate helper, or (b) update the existing tests deliberately and document the
marker-text change as an intentional, in-scope consistency improvement. Plan should pick one
explicitly rather than discovering the test breakage mid-implementation.
**Warning signs:** `pytest tests/unit/test_mcp.py -k "resource or prompt"` regressing after the
`_content_to_text` fix lands.

## Code Examples

### The existing never-repr pattern to copy (Phase 11, already correct)

```python
# Source: src/agent86/tools/mcp_client.py:1553-1563
kind = type(content).__name__
non_text.append({"index": index, "role": role, "type": kind})
lines.append(f"[{role}]: [non-text content block: {kind} — not inlined]")
```

### The existing binary-marker pattern to copy (Phase 11, D-02)

```python
# Source: src/agent86/tools/mcp_client.py:1507-1517
descriptor: dict[str, Any] = {
    "uri": str(getattr(item, "uri", "") or ""),
    "mime_type": str(getattr(item, "mime_type", None) or "unknown"),
    "base64_len": len(getattr(item, "blob", None) or ""),
}
binary.append(descriptor)
parts.append(
    f"[binary resource uri={descriptor['uri']} "
    f"mime_type={descriptor['mime_type']} "
    f"base64_len={descriptor['base64_len']} — not inlined]"
)
```

### The existing config-field pattern to copy (pre-existing, `ProviderConfig`)

```python
# Source: src/agent86/config.py:144-145
connect_timeout_s: float = _DEFAULT_CONNECT_TIMEOUT_S
read_timeout_s: float = _DEFAULT_READ_TIMEOUT_S
```

### The exact SDK content-block field shapes (verified live, mcp 2.0.0 installed)

```python
# Verified via: python -c "import mcp.types as t; print(t.ImageContent.model_fields.keys())"
# ImageContent:      type, data, mime_type, annotations, meta
# AudioContent:      type, data, mime_type, annotations, meta
# EmbeddedResource:  type, resource, annotations, meta
# ResourceLink:      name, title, uri, description, mime_type, size, icons, annotations, meta, type
# TextResourceContents: uri, mime_type, meta, text
# BlobResourceContents: uri, mime_type, meta, blob
```

### `MCPServer`'s own `Image`/`Audio` helpers, for extending the live test fixture

```python
# Confirmed present in the installed SDK:
# python -c "import mcp.server.mcpserver as m; print([n for n in dir(m) if n in ('Image','Audio')])"
# -> ['Audio', 'Image']
# A live_mcp_server.py tool can return mcp.server.mcpserver.Image(...)/Audio(...) to legitimately
# exercise a real ImageContent/AudioContent round trip end to end, the same way server-everything's
# get-tiny-image already does — useful if the plan wants live (not just fake-transport) evidence
# for MCP-25, mirroring Phase 11's live-evidence pattern.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Hardcoded 30s connect / 120s call timeout, `MCPConfig{enabled}` only | Per-server `MCPServerConfig.connect_timeout_s`/`call_timeout_s`, defaulting to the old values | This phase (MCP-21) | A slow-but-legitimate server can be configured with a longer budget without a code change; a hung server still fails, just per-server-tunable |
| `_content_to_text` uncapped | Capped at `MCPServerConfig.max_result_chars` (default 8,000) with a visible marker | This phase (MCP-22, ADR 0004) | Bounds one tool call's contribution to the conversation budget, making ADR 0003's budget recomputation more predictable (ADR 0004's own stated consequence) |
| Non-text `ContentBlock` → `str(chunk)` Python repr | Named, informative marker per block type, base64 never inlined | This phase (MCP-25) | `CAP-CONTENT-BLOCKS` moves from `partial`/`absent` to `implemented` in the conformance matrix |

**Deprecated/outdated:** Nothing in this phase's scope deprecates prior code; `_prompt_messages_to_text`
and `_resource_contents_to_text` (Phase 11) remain the model to extend, not replace.

## Open Questions

1. **Does the result cap apply to `read_resource`/`get_prompt`, or only `call_tool`?**
   - What we know: ADR 0004 names only `_content_to_text` (the `call_tool` path) in its Decision
     and Consequences sections. `read_resource`/`get_prompt` render through separate functions
     (`_resource_contents_to_text`, `_prompt_messages_to_text`) that ADR 0004 does not mention.
   - What's unclear: Whether MCP-22's implementation should extend the ADR's ruling to these two
     sibling functions for consistency (a large resource or prompt render is exactly as capable
     of consuming the budget as a large tool result), or whether that's out of this phase's
     literal scope and should wait for a future ruling, matching how ADR 0004 explicitly deferred
     `structured_content`.
   - Recommendation: Apply the same `max_result_chars` cap to all three for consistency (they all
     ultimately feed the same context budget, and ADR 0004's own rationale — "large enough that no
     observed result came close, small enough that one unbounded result cannot silently consume a
     meaningful fraction of the budget" — applies identically to a resource or prompt render). If
     the planner disagrees, document the narrower reading explicitly as a deliberate scope
     decision rather than an oversight, since the roadmap's SC2 text ("`_content_to_text`
     truncates...") is literally narrow but the roadmap's Goal text ("an oversized tool result
     truncates visibly") is capability-framed, not function-framed.

2. **Does the 8,000-char default need corpus-audit evidence before it ships, or does MCP-07's
   existing run already satisfy the roadmap's stated precondition?**
   - What we know: The roadmap's own Risk/constraint text says "the first plan audits the pinned
     corpus for that before shipping the default" — this reads as a requirement on the *plan*,
     not merely a suggestion. ADR 0004's default rationale cites "no observed corpus-server tool
     result in this audit's MCP-07 run came close to it" as its justification, but MCP-07's run
     was scoped to answering the sampling/elicitation/progress question (per MCP-07's own
     definition in REQUIREMENTS.md), not to exhaustively sizing every tool's typical output.
   - What's unclear: Whether MCP-07's existing evidence (in
     `docs/mcp-conformance-audit-2026-09.md`) already covers enough tool calls to satisfy this, or
     whether a fresh live run against `server-filesystem`'s `read_text_file` on a realistically
     large file and `mcp-server-git`'s `log`/`diff` on a real repo is needed.
   - Recommendation: Treat this as a required Wave-0-style task in the plan — a short live-corpus
     script (following `11-EVIDENCE.md`'s pattern) that calls each corpus server's largest-output
     tool and records the character count, landing in a new `13-EVIDENCE.md`. This closes the
     roadmap's own stated precondition with real evidence rather than an assumption.

3. **Should `MCPServerFormModal`/`/config mcp` gain UI fields for the three new config values in
   this phase, or is that out of scope?**
   - What we know: None of the three roadmap Success Criteria mention the TUI form; they are
     phrased entirely in terms of `MCPServerConfig` schema and `mcp_client.py` behavior.
     `config_writer.py` needs no change (it already writes arbitrary dotted key paths generically).
   - What's unclear: Whether a user is expected to be able to set
     `connect_timeout_s`/`call_timeout_s`/`max_result_chars` only by hand-editing TOML after this
     phase, or whether `/config mcp`'s add/edit form (`MCPServerFormModal`,
     `src/agent86/tui/screens/mcp_manager.py`) should gain matching fields.
   - Recommendation: Treat as out of scope for this phase unless the planner or a
     `/gsd:discuss-phase` pass rules otherwise — the roadmap's Risk/constraint section only
     requires that *if* a write-back happens it goes through `config_writer.py`, which is already
     true structurally; it does not require a new UI surface to exist. Hand-editing TOML for three
     rarely-changed numeric fields is a reasonable v1 for this phase, with a TUI form as a
     natural follow-up.

4. **Should `_MAX_RECONNECT_ATTEMPTS`/backoff constants also move to per-server config in this
   phase?**
   - What we know: The code comment at `mcp_client.py:42-43` explicitly scopes them out
     ("Hardcoded on purpose: per-server timeout/retry config is MCP-21's ruling, not this
     phase's" — written during Phase 12, referring forward to this phase).
   - What's unclear: Whether "per-server timeout/retry config is MCP-21's ruling" means the
     *retry count and backoff window* were always intended to become configurable too, or whether
     that comment only anticipated `connect_timeout_s`/`call_timeout_s`.
   - Recommendation: Read literally — MCP-21's roadmap text says only "connect/call timeouts", not
     reconnect attempts/backoff. Leave `_MAX_RECONNECT_ATTEMPTS`/`_RECONNECT_BASE_DELAY_S`/
     `_RECONNECT_MAX_DELAY_S` as module constants, unchanged. If the planner wants to widen scope,
     flag it as a deliberate, documented decision, not an assumption from this research.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` Python SDK | All three success criteria (content-block types, `CallToolResult` shape) | ✓ | 2.0.0 (installed in `.venv`) | — |
| `mcp.server.mcpserver.MCPServer`, `Image`/`Audio` helpers | Optional: extending `live_mcp_server.py` with a real image/audio tool for live MCP-25 evidence | ✓ | Same package | If unavailable in CI, fake-transport unit tests (`_install_fake_transport` + hand-built `ImageContent`/`AudioContent` instances) fully cover MCP-25 without a live server |
| `@modelcontextprotocol/server-filesystem`, `mcp-server-git`, `@modelcontextprotocol/server-everything` (pinned corpus, npm/pip) | Open Question 2's corpus-size audit | Not probed in this research pass (no live network calls performed) | Pinned versions recorded in `docs/mcp-conformance-audit-2026-09.md`'s corpus table | If a pinned corpus server is unavailable at plan/implementation time, fall back to the CI-safe `tests/integration/live_mcp_server.py` fixture (always available, no network) for the *mechanism* proof, and document the corpus-size question as an accepted risk requiring later verification, matching Phase 11's precedent for `server-filesystem`'s missing `resources` capability |

**Missing dependencies with no fallback:** None identified — the phase's mechanism is fully
buildable and testable against the always-available fixture server plus fake-transport unit
tests.

**Missing dependencies with fallback:** The live pinned-corpus servers (not verified reachable in
this research pass) have a documented fallback (fixture server + fake transports) if unavailable
at implementation time.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = "auto"`, `pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (implicit; `[tool.pytest]`/`testpaths` set there) |
| Quick run command | `pytest tests/unit/test_mcp.py tests/unit/test_config.py -q` |
| Full suite command | `pytest -q` (1319 passed as of Phase 12's close, per STATE.md) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-21 | `MCPServerConfig` gains `connect_timeout_s`/`call_timeout_s` with old values as defaults | unit | `pytest tests/unit/test_config.py -k "mcp_server" -x` | ❌ Wave 0 — no existing `MCPServerConfig` timeout test; follow `test_provider_config_default_timeouts`'s exact pattern |
| MCP-21 | `start_server`/`call_tool`/`_on_session` read the per-server configured timeout instead of the hardcoded constant | unit | `pytest tests/unit/test_mcp.py -k "timeout" -x` | ❌ Wave 0 — new test needed against `_install_fake_transport` with a monkeypatched slow response |
| MCP-21 | A call during a reconnect backoff window still gets the "reconnecting" message, not a raw timeout, once `call_timeout_s` is configurable | integration | `pytest tests/integration/test_mcp_client.py -k reconnect -x` | ✅ Extend existing reconnect test coverage from Phase 12 (`test_mid_session_kill_reconnects_with_fresh_tools` et al.) |
| MCP-22 | `_content_to_text` truncates at `max_result_chars` with a visible marker, never raises | unit | `pytest tests/unit/test_mcp.py -k "truncat or result_cap or max_result_chars" -x` | ❌ Wave 0 — new test |
| MCP-22 | Corpus tools' legitimate output sizes recorded before the 8,000 default ships | integration/manual | live corpus script → `phases/13-.../13-EVIDENCE.md` (not a pytest-automatable acceptance test; an evidence-gathering task) | ❌ Wave 0 — new evidence file, following `11-EVIDENCE.md`'s pattern |
| MCP-25 | `ImageContent`/`AudioContent`/`EmbeddedResource` render as a named, informative marker, never `str(chunk)`/base64 | unit | `pytest tests/unit/test_mcp.py -k "content_block or image or audio or embedded" -x` | ❌ Wave 0 — new tests; follow `test_non_text_prompt_block_is_marked_not_repred`'s exact fake-object pattern, extended to real `mcp.types.ImageContent(...)` instances (constructible directly, no live server needed) |
| MCP-25 | `docs/mcp-conformance-matrix.md`'s `CAP-CONTENT-BLOCKS` row moves `partial`/`out` → `implemented`/`in`; `docs/ARCHITECTURE.md` §15 loses its matching row | doc-consistency | `pytest tests/unit/test_docs_consistency.py -q` | ✅ Existing test (Phase 10) enforces the matrix/§15 cross-reference structurally; the row-content update itself is a docs task for the phase-signoff plan |

### Sampling Rate

- **Per task commit:** `pytest tests/unit/test_mcp.py tests/unit/test_config.py -q`
- **Per wave merge:** `pytest tests/unit/ tests/integration/test_mcp_client.py -q`, plus
  `mypy src/agent86` and `ruff check .` (both clean as of Phase 12's close, per STATE.md)
- **Phase gate:** Full suite green (`pytest -q`) before `/gsd:verify-work`, plus
  `pytest tests/unit/test_docs_consistency.py -q` for the matrix/§15 cross-reference, matching
  every prior phase's own gate.

### Wave 0 Gaps

- [ ] `tests/unit/test_config.py` — new tests for `MCPServerConfig.connect_timeout_s`/
      `call_timeout_s`/`max_result_chars` defaults and overrides (covers MCP-21, MCP-22 schema)
- [ ] `tests/unit/test_mcp.py` — new tests for timeout wiring at `start_server`/`call_tool`/
      `_on_session` reading `cfg.connect_timeout_s`/`cfg.call_timeout_s` (covers MCP-21 behavior)
- [ ] `tests/unit/test_mcp.py` — new tests for `_content_to_text` truncation at
      `max_result_chars` with a visible marker (covers MCP-22)
- [ ] `tests/unit/test_mcp.py` — new tests for `ImageContent`/`AudioContent`/`EmbeddedResource`
      rendering as named markers, never `str(chunk)` (covers MCP-25) — real `mcp.types.*`
      instances can be constructed directly in the test (confirmed constructible via the field
      lists in § Code Examples above), no fake-object duck-typing needed
- [ ] `phases/13-.../13-EVIDENCE.md` — live pinned-corpus run recording actual result sizes for
      `server-filesystem`, `mcp-server-git`, `server-everything`'s largest-output tools, closing
      Open Question 2 and the roadmap's stated "audit the pinned corpus" precondition
- [ ] Optional: extend `tests/integration/live_mcp_server.py` with a tool returning
      `mcp.server.mcpserver.Image(...)`/`Audio(...)` for live (not just fake-transport) MCP-25
      evidence over real stdio, mirroring Phase 11's `res://agent86/blob.bin` binary-resource
      precedent — not required (fake-transport unit tests fully cover the rendering logic) but
      would strengthen the phase-signoff evidence the same way `11-EVIDENCE.md` did

## Sources

### Primary (HIGH confidence)

- `docs/adr/0004-mcp-result-cap-location.md` — full text read; the binding ruling for MCP-22
- `docs/mcp-conformance-matrix.md` — full text read; `CAP-CONTENT-BLOCKS` row and "Not rated here"
  section (timeouts/reconnect/desync routing)
- `docs/mcp-conformance-audit-2026-09.md` §§ "The nine head-start rows, ruled" (rows 4/5/6) and
  "Proposed Phase 16" — full text read
- `src/agent86/tools/mcp_client.py` — read in full at the cited line ranges: module header,
  `MCPManager.__init__`/`self.servers`, `start_server`, `_serve`/`_serve_once` (reconnect
  interaction), `stop_server`, `call_tool`, `_on_session`, `list_resources`/`read_resource`/
  `list_prompts`/`get_prompt`/`complete`, `_content_to_text`, `_resource_contents_to_text`,
  `_prompt_messages_to_text`, `_completion_to_text`, `build_mcp`
- `src/agent86/config.py` — `MCPServerConfig` (lines 358-399), `MCPConfig` (lines 293-294),
  `ProviderConfig`'s timeout-field precedent (lines 134-158)
- `src/agent86/config_writer.py` — module docstring and `_FORBIDDEN_LEAF_KEYS`/`DELETE`/
  `ConfigEdit` read; confirmed generic dotted-key-path write mechanism needs no MCP-specific change
- `src/agent86/tui/screens/mcp_test.py` — full file read; `MCPTestModal.TIMEOUT_S` UI-timeout
  boundary distinguished from `connect_timeout_s`
- `tests/integration/live_mcp_server.py` — full file read; the CI-safe fixture's current tool/
  resource/prompt surface
- `tests/unit/test_mcp.py` — relevant test names and one full test body
  (`test_non_text_prompt_block_is_marked_not_repred`) read; confirms the fake-transport pattern
- `tests/unit/test_config.py` — `test_provider_config_default_timeouts`/
  `test_provider_timeout_override_is_per_provider` read; the naming/testing precedent to copy
- `tests/integration/test_mcp_live.py` — header read; confirms live-test skip/gating mechanism
- Live SDK introspection (this session, 2026-09-24): `importlib.metadata.version("mcp")` → `2.0.0`;
  `mcp.types.{TextContent,ImageContent,AudioContent,EmbeddedResource,ResourceLink,
  TextResourceContents,BlobResourceContents}.model_fields`; `CallToolResult.model_fields["content"]
  .annotation`; `mcp.server.mcpserver.{Image,Audio}` presence — all HIGH confidence, direct
  inspection of the exact installed package, not training-data recollection
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` § Phase 13, `.planning/STATE.md` (Recent
  Activity, Phase 12 close) — full text read for phase scope and precondition context
- `docs/ARCHITECTURE.md` §7 (MCP client behavior paragraph) and §15 (non-goals table,
  `CAP-CONTENT-BLOCKS` row) — read to confirm exactly one §15 row needs removal on this phase's
  close, matching Phase 11's precedent for multi-row §15 updates

### Secondary (MEDIUM confidence)

- None — all findings in this document were verified directly against the installed package or
  the project's own files; no unverified WebSearch claims were needed for this phase's scope.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new library; exact installed version and field shapes confirmed live
- Architecture: HIGH — every pattern recommended has a working precedent already in this exact
  file (Phases 11/12), read directly rather than inferred
- Pitfalls: HIGH — five pitfalls, each grounded in a specific confirmed code fact (line numbers,
  existing test names, the `_serve` reconnect interaction read in full)
- Open questions: honestly flagged as MEDIUM — these are scope judgment calls the roadmap's own
  text leaves room for, not gaps in investigation; each carries a recommendation and its rationale

**Research date:** 2026-09-24
**Valid until:** ~2026-10-24 (30 days) for the architecture/pattern guidance — stable, since it
describes an already-complete client being incrementally extended. Re-verify SDK field shapes and
exact hardcoded line numbers at plan/implementation time regardless of this window, since this
file has changed in every recent phase.
