# agent86 MCP Client Conformance Matrix

**Protocol revision: 2025-11-25** · **agent86 v1.0.0** · **`mcp` SDK 2.0.0** · **Audited 2026-09-22** · **Re-audited 2026-09-23 (Phase 11: resources, prompts, completion)**

## Why this revision

`ClientSession.initialize()` negotiates `protocol_version=LATEST_HANDSHAKE_VERSION`
(`session.py:619`), which the installed SDK's own version registry resolves to `2025-11-25` — the
last revision of the handshake-based protocol family. The current published revision,
`2026-07-28`, is a structurally different stateless per-request-envelope protocol (`server/discover`
instead of the `initialize` handshake, protocol version carried in `_meta`) that agent86's client
code cannot speak at all today. Rating capabilities against a wire format this client never sends
would describe a harness that does not exist. `2026-07-28` adoption is therefore **not rated here**;
it is carried as a candidate finding in `docs/mcp-conformance-audit-2026-09.md`'s workstream
breakdown.

## How to read this

Six columns, in this order: **ID** (the `CAP-*` identifier), **Capability** (the human name),
**Rating** (`implemented` / `partial` / `absent` — what agent86's client code actually does today,
with a file:line citation in the Reasoning cell), **Exercised by corpus** (which pinned corpus
server, if any, drives this capability, naming the server and, where relevant, the specific tool),
**Ruling** (`in` / `out` — whether the capability is a live goal or a deliberate non-goal), and
**Reasoning** (why the ruling was made).

The demand rule, stated verbatim from `docs/BACKLOG.md` § 999.0: **the spec is the measuring
stick, the corpus is the trigger** — a feature ships when a corpus server exercises it. Anything
the spec defines and no corpus server uses becomes a written non-goal in `docs/ARCHITECTURE.md`
§15, with its reasoning — a conformance statement, not a silent gap.

## The matrix

| ID | Capability | Rating | Exercised by corpus | Ruling | Reasoning |
|---|---|---|---|---|---|
| CAP-TOOLS-LIST | Tools — list | implemented | all five corpus servers list tools on connect; server-everything's 13-tool list is the live-run evidence (MCP-07) | in | Already implemented and load-bearing for every mounted server, `mcp_client.py:221` (`session.list_tools()`, no pagination — see CAP-PAGINATION for that gap separately) |
| CAP-TOOLS-CALL | Tools — call | implemented | all five corpus servers; server-everything's `echo`/`get-sum`/etc. called live in MCP-07 | in | Already implemented, `mcp_client.py:286-295`, per-server `call_timeout_s` (default 120 s, MCP-21) and a per-server `max_result_chars` cap (MCP-22); the core mechanism every mounted tool depends on |
| CAP-TOOL-ANNOTATIONS | Tool annotations | partial | server-everything's `get-annotated-message` exercises `title`/hints beyond `read_only_hint`, per its own name | in | Only `read_only_hint` is read today (`_is_read_only`, `mcp_client.py:96-111`); `title`, `destructive_hint`, `idempotent_hint`, `open_world_hint` are never inspected. Ruled in because the approval gate already depends on the one hint that is read, and a realistic server (server-filesystem) ships destructive-hint-worthy tools (delete/write) this gate should eventually see — deferred to workstream A rather than a silent gap |
| CAP-STRUCTURED-OUTPUT | Structured / typed tool output | absent | server-everything's `get-structured-content` returns typed output agent86 never reads | out | `_content_to_text` (`mcp_client.py:426-434`) never reads `CallToolResult.structured_content` (present on the SDK, `mcp_types/_types.py:1474`); ADR 0004 rules this explicitly out of its own scope pending a future ADR — see `docs/adr/0004-mcp-result-cap-location.md`, whose Consequences state `CAP-STRUCTURED-OUTPUT` is ruled out: silently dropped today, left unaddressed pending its own future ruling |
| CAP-CONTENT-BLOCKS | Content block types — text, image, audio, embedded resource | implemented | server-everything@2026.8.31's `get-tiny-image`/`get-resource-links`/`get-resource-reference`, rendered live before and after the fix in `13-EVIDENCE.md`; the CI fixture's `tiny_image`/`tiny_audio`/`mixed_blocks` tools over real stdio (plan 13-05) | in | Shipped in Phase 13 (MCP-25): `_content_to_text` renders every block through `render_content_block` (`tools/mcp_content.py`) — image/audio as a mime-type + base64-length marker, an embedded text resource inlined under its URI, an embedded blob as a marker, a resource link as its URI/name/type/size, anything else as a named marker; never `str(chunk)`, never base64. The joined text is then capped at the server's `max_result_chars` (MCP-22, ADR 0004) |
| CAP-RESOURCES | Resources — list and read | implemented | `tests/integration/live_mcp_server.py`'s three resources, exercised over real stdio in plan 11-02's `test_list_resources_then_read_resource_round_trip`; the live `server-filesystem@2026.8.31` run recorded in `11-EVIDENCE.md` found it declares no `resources` capability at all (`resources=None`, both `resources/list` and `resources/templates/list` answer `Method not found`), so it does not itself exercise this row | in | Shipped in Phase 11 (MCP-14) — `_serve` reads `session.server_capabilities` once after `initialize()` and mounts `mcp__{server}__list_resources` and `read_resource` for any server declaring the `resources` capability, via `_capability_tools` in `mcp_client.py`; binary content is never inlined as base64, a mime-type and length marker goes to the model and a descriptor to `ToolResult.metadata` |
| CAP-RESOURCE-TEMPLATES | Resource templates | implemented | the CI fixture's `res://agent86/echo/{word}` template (plan 11-02); `server-filesystem@2026.8.31`'s live run (`11-EVIDENCE.md`) returned the same `Method not found` for `resources/templates/list`, since it declares no `resources` capability | in | `mcp__{server}__list_resource_templates` ships behind the same `resources` gate; single-page like `list_tools`, since CAP-PAGINATION stays workstream C |
| CAP-RESOURCE-SUBSCRIBE | Resource subscriptions | partial | `server-everything@2026.8.31`'s live `server_capabilities.resources.subscribe` is `True` (`11-EVIDENCE.md`), matching its `toggle-subscriber-updates` tool; `MCPServer`-hosted fixtures declare `subscribe` `False`, so the gate itself is unit-tested rather than live-exercised | in | Both call sites ship as approval-gated tools behind the `resources.subscribe` sub-capability, but a `notifications/resources/updated` is still dropped for lack of a `message_handler` — the remaining half is MCP-24, workstream C. Both SDK methods are marked deprecated relative to protocol revision `2026-07-28` and remain correct for the `2025-11-25` revision agent86 negotiates (Phase 10, D-01) |
| CAP-PROMPTS | Prompts — list and get | implemented | `server-everything@2026.8.31`'s four live prompts observed in `11-EVIDENCE.md` (`simple-prompt`, `args-prompt`, `completable-prompt`, `resource-prompt`), plus the CI fixture's `review_code` prompt (plan 11-03) | in | `mcp__{server}__list_prompts` and `get_prompt` ship behind the `prompts` capability gate; messages render as a role-prefixed transcript and a non-text block becomes a named marker rather than the Python repr `_content_to_text` still falls back to (that older path stays MCP-25) |
| CAP-COMPLETION | Completion — argument autocomplete | implemented | `completable-prompt`'s `department` argument, observed live in `11-EVIDENCE.md` returning `Engineering`/`Sales`/`Marketing`/`Support`, plus the CI fixture's `complete_argument` handler (plan 11-03) | in | `mcp__{server}__complete` ships behind the `completions` capability gate, taking an explicit `ref_type` so a prompt reference and a resource-template reference are never guessed apart; `context_arguments` is deliberately not exposed yet |
| CAP-SAMPLING | Sampling | absent | none reachable through agent86 — `trigger-sampling-request`/`trigger-sampling-request-async` were absent from the 13 tools agent86 received in the MCP-07 live run, because agent86 declares no sampling capability (`docs/mcp-conformance-audit-2026-09.md`, MCP-07 section); server-everything is the only server in the corpus that would exercise it at all | out | Absent, and *correctly declared* absent — `mcp_client.py:219` passes no `sampling_callback`, so `session.py:591-595` sets `sampling=None`, a declared "not supported" at `initialize()`, not a silent gap. Ruled verbatim from `docs/adr/0001-mcp-sampling-inversion-of-control.md`: opt-in per server, deferred until a realistic corpus server demands it — not built today, not because agent86 is missing something, but because the only server that exercises it is the conformance instrument itself and the cost/egress/approval machinery a real implementation needs does not yet exist |
| CAP-ELICITATION | Elicitation — form and URL modes | absent | none reachable through agent86 — `trigger-elicitation-request`/`trigger-url-elicitation` were absent from the MCP-07 live-run tool list for the identical capability-gating reason as sampling | out | Absent, and *correctly declared* absent — same mechanism, `session.py:596-600`. Ruled verbatim from `docs/adr/0002-mcp-elicitation-tier-1-surface.md`: opt-in per server, deferred until a realistic corpus server demands it, with four non-negotiable preconditions (gateway-owned rendering, a hard refusal list, defined headless behaviour, refusal-as-a-normal-answer) before it ever ships |
| CAP-ROOTS | Roots | absent | server-everything's `get-roots-list` would exercise it; server-filesystem's roots-protocol interaction with CLI-provided allowed directories is documented upstream (GitHub issue #3602) but not exercised by agent86 today | out | Absent, and *correctly declared* absent — `mcp_client.py:219` passes no `list_roots_callback`; SDK's `_build_capabilities()` (`session.py:601-608`) sets `roots=None` — declared, not silent, absence, same mechanism as sampling/elicitation. No corpus server's primary value depends on agent86 offering roots; note the spec deprecates roots in `2026-07-28` (SEP-2577) while `2025-11-25` still fully supports it, which further weakens the case for building it now. Deferred to workstream A (MCP-16, alongside sampling/elicitation) |
| CAP-LOGGING | Logging | absent | server-everything's `toggle-simulated-logging` exercises this in principle | out | No `set_logging_level()` call; SDK default `_default_logging_callback` is a no-op (`session.py:245-248`). Only the conformance instrument exercises it; no realistic corpus server needs agent86 to consume its log stream. Deferred to workstream C |
| CAP-PROGRESS | Progress notifications | absent | server-everything's `trigger-long-running-operation` — present and callable in agent86's tool list per the MCP-07 live run, but its progress notifications are dropped on arrival | out | No progress token attached to any request, and no `message_handler` to receive `notifications/progress` — SDK default is `await anyio.lowlevel.checkpoint()` (`session.py:212-213`), a true no-op. `docs/mcp-conformance-audit-2026-09.md`'s MCP-07 section records this precisely: agent86 can *trigger* the long-running operation but cannot *observe* its progress. Deferred to workstream C (MCP-24) |
| CAP-CANCELLATION | Cancellation | absent | none | out | No `notifications/cancelled` send site. No corpus server's primary workflow depends on client-initiated cancellation being wired through to the server; agent86's own turn-level cancel (Escape/Ctrl+C) does not currently propagate. Deferred to workstream C |
| CAP-PAGINATION | Pagination | absent | none of the five corpus servers' tool/resource/prompt lists are large enough to paginate in this audit's observation | out | `mcp_client.py:221` — no `params.cursor`, no `nextCursor` loop; a server that paginates its tool list would silently return page one only. No corpus server has demonstrated this gap in practice, but it is a real latent risk as server tool counts grow. Deferred to workstream C (MCP-21-adjacent) |
| CAP-PING | Ping | absent | none | out | No `send_ping()` call site. No corpus server needs a liveness probe; the transports already fail loudly on disconnect (surfaced as a session error, not silently). Deferred to workstream C |
| CAP-LIST-CHANGED | list_changed notifications — tools, resources, prompts | absent | server-everything's `toggle-subscriber-updates` exercises the mechanism this depends on | out | `mcp_client.py:219` passes no `message_handler`; SDK default is `await anyio.lowlevel.checkpoint()` (`session.py:212-213`), so every server notification is dropped, list_changed included. Only the conformance instrument exercises it. Deferred to workstream C (MCP-24) |
| CAP-META | `_meta` on requests, responses and notifications | absent | none — the SDK carries `_meta` internally for protocol negotiation only; no corpus server's tool behaviour depends on agent86 reading or writing it | out | No direct `_meta` access in `mcp_client.py`. No corpus server demands agent86-side `_meta` handling beyond what the SDK already does internally. Not routed to any workstream — this is SDK-internal plumbing, not a client-code gap |
| CAP-TRANSPORTS | Transports — stdio, Streamable HTTP, SSE | implemented | server-everything, server-filesystem, mcp-server-git and `live_mcp_server.py` all connect over stdio; GitHub's hosted server is the streamable-HTTP corpus member (workstream B target, not yet connected) | in | Already implemented, `_open_transport` (`mcp_client.py:395-423`) — all three transports. Load-bearing for every corpus server this audit names |
| CAP-OAUTH | OAuth 2.0 for remote servers | absent | GitHub's hosted remote MCP server (`https://api.githubcopilot.com/mcp/`) is the corpus member this would unlock; not connected to in this audit (no live credentials available, per `docs/mcp-conformance-audit-2026-09.md`'s corpus table) | out | `_resolve_server_secrets` (`mcp_client.py:336-358`) supports only `headers` plus `${VAR}` — no discovery, no token storage, no refresh. GitHub's hosted server is a named, realistic demand signal (not merely the conformance instrument), so this is deferred to workstream B rather than ruled a permanent non-goal — workstream B (deferred requirements MCP-17, MCP-18) exists specifically to close this gap once phased |

## Rows ruled out

- **CAP-STRUCTURED-OUTPUT** — Structured / typed tool output: `structured_content` is silently
  dropped today; ADR 0004 rules it explicitly out of its own scope, pending a future ADR.
- **CAP-SAMPLING** — Sampling: opt-in per server, deferred until a realistic corpus server demands
  it — see `docs/adr/0001-mcp-sampling-inversion-of-control.md`.
- **CAP-ELICITATION** — Elicitation: opt-in per server, deferred pending four preconditions — see
  `docs/adr/0002-mcp-elicitation-tier-1-surface.md`.
- **CAP-ROOTS** — Roots: correctly declared absent, no live demand, and the spec itself deprecates
  the capability in `2026-07-28`; deferred to workstream A (MCP-16).
- **CAP-LOGGING** — Logging: only the conformance instrument exercises it; deferred to workstream C.
- **CAP-PROGRESS** — Progress notifications: agent86 can trigger but not observe them; deferred to
  workstream C (MCP-24).
- **CAP-CANCELLATION** — Cancellation: no corpus server demand; deferred to workstream C.
- **CAP-PAGINATION** — Pagination: a latent risk, not yet demonstrated by any corpus server;
  deferred to workstream C.
- **CAP-PING** — Ping: no corpus server needs a liveness probe; the transports already fail loudly.
- **CAP-LIST-CHANGED** — list_changed notifications: only the conformance instrument exercises it;
  deferred to workstream C (MCP-24).
- **CAP-META** — `_meta`: SDK-internal plumbing, not a client-code gap; not routed to any workstream.
- **CAP-OAUTH** — OAuth 2.0: GitHub's hosted server is a named, realistic demand signal; deferred
  to workstream B (MCP-17, MCP-18).

Each of these is recorded in `docs/ARCHITECTURE.md` §15 as a stated non-goal, not a silent gap.

## Not rated here

- **The `2026-07-28` "modern" stateless protocol (D-01).** Its RPC-based discovery mechanism,
  `_meta`-carried protocol version, and any feature gated on that wire format are deliberately
  excluded from this matrix's row set — agent86's client code cannot negotiate that revision today
  (see "Why this revision" above). Adoption of it is carried as a named candidate finding inside
  the MCP-13 workstream breakdown, written by plan 10-05, in
  `docs/mcp-conformance-audit-2026-09.md`.
- **agent86-side strategies that are not spec capabilities.** These get no row because the MCP
  spec does not define them as something a client implements or doesn't — each is recorded where
  it *is* decided:
  - Schema deferral — `docs/adr/0003-mcp-schema-deferral-prompt-contract.md` (deferring schemas is
    permissible, deferring tool names is not).
  - The prompt-side result cap — `docs/adr/0004-mcp-result-cap-location.md`
    (`MCPServerConfig.max_result_chars`, default 8,000 characters) — implemented by Phase 13, and
    extended to resource reads and prompt renders.
  - Per-server timeouts — `docs/mcp-conformance-audit-2026-09.md`'s nine head-start rows, row 4
    (routed to MCP-21, workstream C) — closed by Phase 13
    (`MCPServerConfig.connect_timeout_s`/`call_timeout_s`).
  - Reconnect after a dropped transport — same report, row 8 (routed to MCP-23, workstream C) —
    closed by Phase 12 (reconnect with bounded backoff).
  - The `_serve`/`_server_tools` desync (the zombie-tool defect) — same report, row 7 and its
    dedicated "Row 7 in detail" section (routed to MCP-26, workstream C) — closed by Phase 12
    (end-of-stream death detection; tools unregistered from both the manager and the harness
    registry).
