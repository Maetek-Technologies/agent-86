# MCP Client Conformance Audit — September 2026

**Audited:** 2026-09-22 · **Protocol revision:** 2025-11-25 · **agent86:** v1.0.0 ·
**`mcp` SDK:** 2.0.0

## Scope and method

This report is audit-only. No source file changes here — `git status --porcelain src/ tests/` is
empty at every point in this document's history, including after the live run recorded below.
Its three deliverables:

1. **The conformance matrix** — every client-side spec capability rated implemented / partial /
   absent, and in / out with reasoning. It lives at `docs/mcp-conformance-matrix.md` (plan 10-04),
   not inline here.
2. **The four ADRs** — sampling as inversion of control, elicitation as a Tier 1 surface, schema
   deferral's effect on the prompt contract, and where the result cap lives. They live under
   `docs/adr/` (plan 10-03), not inline here.
3. **This report** — the narrative half: the pinned corpus (below), the MCP-07 live-run evidence,
   and the nine BACKLOG head-start rows each ruled against current code. The workstream breakdown
   (plan 10-05) closes it out.

**Spec revision pin (D-01).** This audit — and the matrix it feeds — is pinned to protocol
revision **`2025-11-25`**, not the currently-published `2026-07-28`. This is not a stylistic
choice: `ClientSession.initialize()` hardcodes `protocol_version=LATEST_HANDSHAKE_VERSION`
(`session.py:619`), and the installed SDK's own version registry resolves
`LATEST_HANDSHAKE_VERSION` to `2025-11-25` — the last revision of the handshake-based protocol
family. `2026-07-28` replaces the `initialize` handshake with a stateless `server/discover` RPC
and moves the protocol version into `_meta` — a wire format `mcp_client.py`'s `ClientSession(read,
write)` → `session.initialize()` call cannot speak today, regardless of any feature-level rating.
Rating the matrix against `2026-07-28` would therefore describe a protocol agent86's client code
cannot currently reach at all. `2026-07-28` is deliberately **not rated** in the matrix; adoption
of it is carried instead as a named candidate finding inside the MCP-13 workstream breakdown
(plan 10-05).

## The pinned corpus

| Server | Pin | Verified | Transport | What it exercises | Exercised in this audit? |
| --- | --- | --- | --- | --- | --- |
| `@modelcontextprotocol/server-everything` | `npx -y @modelcontextprotocol/server-everything@2026.8.31` | 2026-09-22, `npm view @modelcontextprotocol/server-everything version` | stdio | the conformance instrument (tools, resources, prompts, and the sampling/elicitation/progress triggers) | **yes** — see the MCP-07 section below |
| `@modelcontextprotocol/server-filesystem` | `npx -y @modelcontextprotocol/server-filesystem@2026.8.31 <allowed-dir>` | 2026-09-22, `npm view @modelcontextprotocol/server-filesystem version` | stdio | realistic file tools and the roots question | no — pinned for a workstream-A implementation pass; this report's only live run is `server-everything` (D-03) |
| `mcp-server-git` | `pip install mcp-server-git==2026.8.18` | 2026-09-22, `python -m pip index versions mcp-server-git` | stdio | realistic git tools, the bridge to `docs/BACKLOG.md` § 999.5 | no — pinned for a workstream-A implementation pass; not live-run in this audit |
| `tests/integration/live_mcp_server.py` | git SHA `a30a2bb` | 2026-09-22, `git rev-parse --short HEAD` | stdio | SEC-04 end-to-end — it gained a `get_env` tool in plan 10-01, so the scrubbed environment is asserted at the far end of a real subprocess, not just at the call site | yes, continuously — `tests/integration/test_mcp_client.py` drives it over stdio on every CI run; not separately re-run for this report |
| GitHub's hosted remote MCP server | `https://api.githubcopilot.com/mcp/` | 2026-09-22 (observation date, not a version) | streamable HTTP | OAuth 2.0 discovery, authorization and refresh — workstream B's target | **no** — no GitHub OAuth app or credentials exist in this environment |

`mcp-server-git`'s installable form is also commonly launched as `uvx mcp-server-git` (no separate
install step). `uv`/`uvx` is not installed on this machine, so the `pip install mcp-server-git==
2026.8.18` form above is the one actually verified and recorded here; a reader whose machine has
`uvx` can use that form interchangeably — the package and version are identical either way.

GitHub's hosted server has no installable artifact to pin a version against — it's a live product
endpoint GitHub controls unilaterally and updates on its own cadence, with no version tag a client
can request. Per **D-02**, the closest analogue to a version pin for a hosted product is the
endpoint URL plus the date its capability surface was observed, recorded above as
`https://api.githubcopilot.com/mcp/` observed `2026-09-22`. A future re-audit of this server must
re-observe its current behavior rather than re-install a pinned artifact. This audit documented it
from GitHub's own public setup documentation and did **not** connect to it — no fixture file was
captured or committed for it, per D-02's explicit instruction.

## MCP-07 — does `server-everything` drive sampling, elicitation and progress?

**Command run**, from a throwaway script in the scratchpad (never inside the repo tree), against
the project's own `.venv` Python:

```
command="npx.cmd", args=["-y", "@modelcontextprotocol/server-everything@2026.8.31"]
```

driven through `agent86.tools.mcp_client.MCPManager.start_server("everything", cfg,
timeout=180.0)`. This environment's `npx` is a Volta shim that a Python subprocess cannot spawn
directly without a shell; `npx.cmd` was used from the first attempt and succeeded without a retry
— no fallback to bare `npx` was needed. `manager.close()` ran in a `finally` block so the
background event-loop thread was torn down cleanly.

**Tool list agent86 actually received** (`TOOL COUNT: 13`), alphabetically:

`echo`, `get-annotated-message`, `get-env`, `get-resource-links`, `get-resource-reference`,
`get-structured-content`, `get-sum`, `get-tiny-image`, `gzip-file-as-resource`,
`simulate-research-query`, `toggle-simulated-logging`, `toggle-subscriber-updates`,
`trigger-long-running-operation`.

**Present/absent breakdown of the sixteen tool names this audit set out to check** (from
`docs/BACKLOG.md` § 999.0a's audit head start and 10-RESEARCH.md's `server-everything` feature
read):

| Tool name | Present in agent86's list? |
|---|---|
| `echo` | present |
| `get-sum` | present |
| `get-annotated-message` | present |
| `get-resource-links` | present |
| `get-resource-reference` | present |
| `get-env` | present |
| `get-structured-content` | present |
| `get-tiny-image` | present |
| `trigger-long-running-operation` | present |
| `toggle-simulated-logging` | present |
| `toggle-subscriber-updates` | present |
| `trigger-elicitation-request` | **absent** |
| `trigger-url-elicitation` | **absent** |
| `trigger-sampling-request` | **absent** |
| `trigger-sampling-request-async` | **absent** |
| `get-roots-list` | **absent** |

11 of the 16 were present; 5 were absent, and every absent one is exactly the sampling,
elicitation, and roots surface. Two additional tools appeared that were not on the sixteen-name
list at all — `gzip-file-as-resource` and `simulate-research-query` — evidence that
`@modelcontextprotocol/server-everything@2026.8.31` has evolved its demo tool set since
10-RESEARCH.md's docs-based feature read; `simulate-research-query`'s own description ("If
'ambiguous' is true and client supports elicitation, sends an elicitation request for
clarification") shows the elicitation demo was folded into this newer tool rather than removed —
consistent with, not contradicting, the absence ruling below.

**The capability-gating mechanism.** `server-everything` conditionally registers its
sampling/elicitation/roots tools based on the capabilities the connecting client declared during
`initialize()` (10-RESEARCH.md, secondary source: `modelcontextprotocol/servers` issue #4792).
agent86's `_serve` constructs `ClientSession(read, write)` with no `sampling_callback`,
`elicitation_callback`, or `list_roots_callback` argument (`mcp_client.py:219`). The installed
SDK's `_build_capabilities()` (`session.py:591-608`) therefore sets `sampling`, `elicitation`, and
`roots` all to `None` in the `ClientCapabilities` object sent at `initialize()` — agent86 is not
silently failing to ask for these; it is actively telling the server "not supported" at the
protocol level. A spec-compliant server that gates tool registration on that signal, as
`server-everything` does, will correctly withhold those tools from exactly this client. The five
absent tool names above are that mechanism working as designed, not a gap in what
`server-everything` offers.

**Answering MCP-07, one sentence per capability:**

- **Sampling**: `server-everything` cannot be observed driving sampling through agent86 today —
  both `trigger-sampling-request` and `trigger-sampling-request-async` were absent from the tool
  list agent86 received, because agent86 declares no sampling capability at `initialize()`
  (`mcp_client.py:219`, `session.py:591-608`), so the server never advertised those tools to this
  client in the first place.
- **Elicitation**: the same is true of elicitation — `trigger-elicitation-request` and
  `trigger-url-elicitation` were both absent for the identical capability-gating reason, and while
  `simulate-research-query` (present) documents elicitation-conditional behavior in its own
  description, it is gated on the same declared-capability signal agent86 does not raise, so its
  elicitation branch is not reachable through agent86 either.
- **Progress**: `server-everything` genuinely drives progress and agent86 can trigger it —
  `trigger-long-running-operation` is present and callable in agent86's tool list — but agent86
  *as currently built* cannot observe it happening: `_serve`'s `ClientSession(read, write)` passes
  no `message_handler` (`mcp_client.py:219`), so the SDK's default handler for any
  `notifications/progress` message is `await anyio.lowlevel.checkpoint()` — a true no-op
  (`session.py:212-213`). The server would send the notifications; agent86 drops every one on
  arrival.

This run was evidence-gathering performed once during this plan's execution, from a script outside
the repository tree. It is deliberately **not** committed as a test — CI must stay network-free and
`npx`-free (D-03), and `git status --porcelain src/ tests/` was confirmed empty immediately after
this run completed.

## The nine head-start rows, ruled

The nine rows below come verbatim from `docs/BACKLOG.md` § 999.0a's "Audit head start", found by
reading `tools/mcp_client.py` on 2026-09-22. Each is ruled **CONFIRMED** or **CORRECTED** here
against the code as of `a30a2bb` — every cited line was re-opened and re-read during this task,
not copied from 10-RESEARCH.md's earlier pass, and every citation below still resolves to the
claim it supports. Per **MCP-12**, this phase proposes, it does not fix: every confirmed defect is
routed into the workstream breakdown (plan 10-05) rather than patched here, and
`src/agent86/tools/mcp_client.py` is untouched by this plan.

| # | Head-start claim | Ruling | Evidence (file:line) | Routed to |
| --- | --- | --- | --- | --- |
| 1 | `ClientSession(read, write)` is built with no callbacks — sampling, elicitation and roots are structurally absent, not merely uncalled. Any one of them is a constructor change. **Refinement confirmed against code:** the absence is *declared*, not silent — `_build_capabilities()` sets `sampling`/`elicitation`/`roots` to `None` whenever the SDK's default callback is still installed, so agent86 already tells servers "not supported" at `initialize()` time. That is protocol-correct behaviour, not a latent defect. | CONFIRMED | `mcp_client.py:219`, `session.py:371-380`, `session.py:591-608` | MCP-16 (workstream A), ADRs 0001/0002 |
| 2 | `initialize()` → `list_tools()` and nothing else — no `list_resources`, `read_resource`, `list_prompts`, `get_prompt`. | CONFIRMED | `mcp_client.py:220-221` | MCP-14, MCP-15 (workstream A) |
| 3 | No `message_handler`, so every server notification is dropped. | CONFIRMED | `mcp_client.py:219`, SDK default `_default_message_handler` is `await anyio.lowlevel.checkpoint()` at `session.py:212-213` | MCP-24 (workstream C) |
| 4 | Timeouts hardcoded and asymmetric — 30 s connect, 120 s per tool call; `MCPConfig` carries only `enabled`. | CONFIRMED | `mcp_client.py:166`, `mcp_client.py:295`, `config.py:293-294` | MCP-21 (workstream C) |
| 5 | `_content_to_text` applies no size cap. **Scope note confirmed against code:** `CallToolResult.structured_content` is never read either (`mcp_types/_types.py:1474`), so the gap is not only "uncapped" but also "silently dropped". | CONFIRMED | `mcp_client.py:426-434` | MCP-22 (workstream C), ADR 0004 |
| 6 | Only `.text` content is read; image, audio and embedded-resource blocks fall through to `str(chunk)`. | CONFIRMED | `mcp_client.py:429-430` | MCP-25 (workstream C) |
| 7 | **The `_serve`/`_server_tools` desync.** `mcp_client.py:234` sets `self._server_tools[name] = tools`; the `finally` at `mcp_client.py:241-242` pops only `self._sessions[name]`; `stop_server()` at `mcp_client.py:244-260` *does* pop `self._server_tools` (line 248) but that is the user-initiated path, not the death path; `call_tool()` at `mcp_client.py:286-289` indexes `self._sessions`; `tools_for()`/`tools()` at `mcp_client.py:262-266` read `self._server_tools`. | CONFIRMED | `mcp_client.py:234`, `mcp_client.py:241-242`, `mcp_client.py:244-260`, `mcp_client.py:286-289`, `mcp_client.py:262-266` | MCP-26 (workstream C) |
| 8 | No reconnect path — `_serve` awaits `close_event`; a dropped transport ends the task. | CONFIRMED | `mcp_client.py:237`, and the absence of any retry loop anywhere in `_serve` | MCP-23 (workstream C) |
| 9 | Auth is `headers` plus `${VAR}` only — no discovery, no refresh, no token storage. | CONFIRMED | `_resolve_server_secrets`, `mcp_client.py:336-358` | MCP-17, MCP-18 (workstream B) |

### Row 7 in detail — the zombie-tool defect

This is the one row the requirement singles out by name ("including the suspected defect in
`_serve`"), so it gets a dedicated explanation rather than a single table cell. The defect fires
only under one precise condition: a server's owning task exits through the `except BaseException`
path at `mcp_client.py:238-240` *after* `ready` has already resolved — that is, the server died
mid-session, having already connected and listed its tools successfully, not at connect time.
Before `ready` resolves, a failure there sets `ready`'s exception and `start_server` raises to the
caller, so no zombie state is possible on the connect path; the defect is specific to a live
server dying later. When that happens, the `finally` block at `mcp_client.py:241-242` pops the
dead session out of `self._sessions`, but `self._server_tools[name]` — set once, at
`mcp_client.py:234`, on successful connect — is never touched by that `finally`. `stop_server()`
does clean up `self._server_tools` (`mcp_client.py:248`), but that is the *user-initiated* removal
path; a server that dies on its own never goes through `stop_server()`.

The practical consequence: `tools_for()`/`tools()` (`mcp_client.py:262-266`) keep reading from
`self._server_tools`, so the dead server's tools remain listed as callable in the registry — the
model still sees them, and the compiled system prompt still advertises them, exactly as if the
server were healthy. But `call_tool()` (`mcp_client.py:286-289`) checks membership in
`self._sessions`, which the `finally` block already emptied for that server, so every call through
one of those tools raises `RuntimeError("MCP session not available")` instead of the tool simply
disappearing. The model is left calling a tool it can no longer successfully use, receiving a
generic runtime error rather than an actionable "server X died, its tools are gone" signal it
could reason about or route around. This is precisely a **zombie-tool** bug — the registry entry
outlives the connection it depends on — not a crash: the harness itself keeps running, the turn
keeps going, and only the specific tool calls into the dead server fail, repeatedly, with no
self-correcting information. Per MCP-12, **no fix is made in this phase** — it is routed to
deferred requirement MCP-26 and sized in the workstream breakdown (plan 10-05).

**Distribution across workstreams.** Of the nine rows, counting each once by its primary routing
column above: **2 route to workstream A** (rows 1 and 2), **1 routes to workstream B** (row 9),
and **6 route to workstream C** (rows 3, 4, 5, 6, 7, 8). That lopsided 6-of-9 weight toward
workstream C is additional, independent evidence — on top of BACKLOG's own prior observation —
that **C is the largest of the three workstreams**; this section does not state a final sizing
conclusion, that synthesis is plan 10-05's job.

## Recommended phase breakdown — workstreams A, B and C

Sizing: A = 9 matrix rows / 2 findings, B = 1 matrix row / 1 finding, C = 7 matrix rows / 6 findings — C is larger than A on findings and deferred-requirement count and materially larger than B on every count, correcting the standing hypothesis only on raw matrix-row count, where A (9) is larger than C (7).

**How the matrix-row counts were derived.** A matrix row is counted against a workstream when
`docs/mcp-conformance-matrix.md`'s own Reasoning cell (or, for `CAP-SAMPLING`/`CAP-ELICITATION`,
the ADR it cites verbatim) names that workstream or the deferred requirement ID assigned to it.
Workstream **A**: `CAP-TOOL-ANNOTATIONS`, `CAP-RESOURCES`, `CAP-RESOURCE-TEMPLATES`,
`CAP-RESOURCE-SUBSCRIBE`, `CAP-PROMPTS`, `CAP-COMPLETION`, `CAP-SAMPLING`, `CAP-ELICITATION`,
`CAP-ROOTS` — 9 rows. Workstream **B**: `CAP-OAUTH` alone — 1 row. Workstream **C**:
`CAP-CONTENT-BLOCKS`, `CAP-RESOURCE-SUBSCRIBE` (shared with A — it needs A's `list_resources`/
`subscribe_resource` call sites *and* C's notification plumbing to fully close), `CAP-LOGGING`,
`CAP-PROGRESS`, `CAP-CANCELLATION`, `CAP-PAGINATION`, `CAP-LIST-CHANGED` — 7 rows (the shared row
counted once here and once in A, so the two workstream totals sum to 16 against 15 distinct rows).
The remaining 6 of the matrix's 22 rows are not counted against any workstream: `CAP-TOOLS-LIST`,
`CAP-TOOLS-CALL`, `CAP-TRANSPORTS` are already implemented (nothing to propose), `CAP-STRUCTURED-
OUTPUT` is left pending its own future ADR, and `CAP-PING`/`CAP-META` are ruled out with no
workstream named at all. **Findings counts** repeat this report's own "Distribution across
workstreams" paragraph above (2 to A, 1 to B, 6 to C of the nine head-start rows). A third,
un-tabulated metric agrees with findings rather than rows: of the 13 deferred requirements
MCP-14 through MCP-26, workstream C carries 7 (MCP-20–26) against A's 3 (MCP-14–16) and B's 3
(MCP-17–19) — so on two of the three metrics this audit can count, the milestone's "C is larger
than A, and materially larger than B" hypothesis holds; the correction is that A's *matrix-row*
count is inflated relative to C's by how many small, individually-absent capabilities (resources,
resource templates, prompts, completion, sampling, elicitation, roots) collapse into A's 3
requirement IDs, while C's rows are fewer but each is backed by a confirmed, currently-exercised
code defect (a head-start finding), not merely untouched spec surface. B is smallest on every
metric without exception.

Each proposed phase below is sized against these same three metrics, and the coverage rule holds:
every deferred requirement MCP-14 through MCP-26 appears in exactly one phase.

#### Proposed Phase 11: Resources and prompts become first-class
**Workstream**: A
**Goal**: A model connected through agent86 can list and read any mounted server's resources, and
list/get its prompts — with argument-completion suggestions where the server supports them — with
the same round-trip fidelity tool calls already have.
**Depends on**: Phase 10 only
**Requirements**: MCP-14, MCP-15
**Matrix rows closed**: CAP-RESOURCES, CAP-RESOURCE-TEMPLATES, CAP-RESOURCE-SUBSCRIBE (the
`subscribe_resource` call site only — the update notification itself is closed by Proposed Phase
17's `message_handler` work), CAP-PROMPTS, CAP-COMPLETION
**Success Criteria** (what must be TRUE):
  1. Connected to `@modelcontextprotocol/server-filesystem`, a model-issued tool call round-trips a
     real `list_resources` → `read_resource` pair and the file content reaches the model.
  2. Connected to `server-everything`, `list_prompts`/`get_prompt` return its 3 prompts, and
     `complete()` returns suggestions for the `completable` argument one of them exposes.
  3. A follow-up matrix re-audit moves `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`/`CAP-PROMPTS`/
     `CAP-COMPLETION` from `absent` to `implemented`.
**Sizing signal**: zero call sites for `list_resources`/`read_resource`/`list_prompts`/`get_prompt`/
`complete` exist today (`_serve`, `mcp_client.py:220-221`); `server-everything` alone exercises 4
resource URI schemes and 3 prompts, and `server-filesystem`'s entire value proposition is file
resources.
**Risk / constraint**: none of the four standing constraints are strained directly — this is
additive client surface, no new core dependency, and any new tool-result content flowing through
`run --json` is additive-only; the `mcp` extra stays optional throughout.

#### Proposed Phase 12: Sampling, elicitation and roots as an opt-in per-server surface
**Workstream**: A
**Goal**: A server operator can opt a specific mounted server into sampling/elicitation/roots,
governed exactly by ADR 0001/0002's rulings, without changing default behavior for any server that
stays opted out.
**Depends on**: Phase 10 only
**Requirements**: MCP-16
**Matrix rows closed**: CAP-SAMPLING, CAP-ELICITATION, CAP-ROOTS
**Success Criteria** (what must be TRUE):
  1. A new per-server config flag exists on `MCPServerConfig` (default off) that, when set, passes
     real `sampling_callback`/`elicitation_callback`/`list_roots_callback` arguments into
     `ClientSession`.
  2. An opted-in server's `sampling/createMessage` request is answered through a dedicated approval
     gate distinct from the tool-call gate, spends against `limits.max_cost_usd`, and the completion
     crossing back to the server passes its own egress check.
  3. Elicitation is rendered by the gateway tier only, refuses the concrete list (credentials, API
     keys, secret-shaped strings, any unvetted free-text answer), and a non-interactive `run --json`
     turn declines automatically with a recorded reason rather than blocking on stdin.
**Sizing signal**: `ClientSession(read, write)` (`mcp_client.py:219`) passes none of the three
callbacks today — a constructor change, not an extension; the only corpus server observed
exercising any of the three is `server-everything` itself (MCP-07's live run), so this phase's
first plan should re-confirm a realistic demand signal exists before building further.
**Risk / constraint**: strains the approval/egress model hardest of any workstream-A item — a new
approval gate and a new egress pass are new mechanisms, not reuse; must not weaken the existing
`allowed-tools` gate or open a credential-storage path CLAUDE.md's `api_key_env` rule forbids.

#### Proposed Phase 13: Connect to GitHub's hosted server and implement OAuth 2.0 discovery/authorization
**Workstream**: B
**Goal**: agent86 can discover and complete an OAuth 2.0 authorization-code flow against a real
remote MCP server over streamable HTTP, proven against GitHub's hosted server rather than a mock.
**Depends on**: Phase 10 only
**Requirements**: MCP-17
**Matrix rows closed**: CAP-OAUTH (moves `absent` → `partial`: discovery and first-time
authorization; refresh is Proposed Phase 14)
**Success Criteria** (what must be TRUE):
  1. agent86 completes RFC 8414/9728-based discovery against `https://api.githubcopilot.com/mcp/`
     and obtains a token via an interactive authorization-code flow.
  2. The obtained token lists tools from GitHub's hosted server over streamable HTTP — the first
     live connection this audit did not make.
  3. No credential is written to `config.py`-managed TOML at any point in the flow — only a
     reference, per CLAUDE.md's `api_key_env` rule.
**Sizing signal**: `_resolve_server_secrets` (`mcp_client.py:336-358`) supports only `headers` +
`${VAR}` today — no discovery, no authorization flow, no token storage anywhere in the file;
GitHub's hosted server is a named, realistic demand signal, not the conformance instrument.
**Risk / constraint**: this is the workstream that strains the standing constraints hardest — an
OAuth flow that must work both interactively and headless in CI is a design decision, not a
library choice — and this audit did **not** connect to GitHub's hosted server, so this phase's
first plan must begin by doing so before any implementation is written.

#### Proposed Phase 14: Token refresh and keyring storage, interactive and headless
**Workstream**: B
**Goal**: A token obtained by Proposed Phase 13 survives expiry without a re-prompt, stored in the
same keyring `/config model` already uses, and the whole flow has a defined, tested headless-CI
path.
**Depends on**: Proposed Phase 13
**Requirements**: MCP-18, MCP-19
**Matrix rows closed**: CAP-OAUTH (moves `partial` → `implemented`)
**Success Criteria** (what must be TRUE):
  1. An expired access token is refreshed automatically on the next call, with no user-visible
     interruption, using the existing keyring plumbing `/config model` already exercises.
  2. A CI run with no interactive terminal and no cached token fails with a named, actionable error
     rather than hanging on a browser redirect it can never complete.
  3. The same code path serves both the interactive TUI/plain-loop flow and the headless CI flow —
     one implementation, not a fork.
**Sizing signal**: zero token-refresh or token-storage code exists anywhere in `mcp_client.py`
today; the keyring plumbing this phase reuses is proven at `/config model`'s `store_api_key`/
`resolve_api_key` call sites (Phase 3).
**Risk / constraint**: strains the same OAuth/headless-CI constraint as Proposed Phase 13; the
`mcp` extra must stay optional even when this phase's new keyring-backed token path is exercised,
and no new core dependency may be added to satisfy the discovery/refresh RFCs.

#### Proposed Phase 15: Fix the zombie-tool desync and add reconnect
**Workstream**: C
**Goal**: A server that dies mid-session has its tools unregistered rather than left
callable-but-broken, and a dropped transport reconnects instead of ending the task permanently.
**Depends on**: Phase 10 only
**Requirements**: MCP-26, MCP-23
**Matrix rows closed**: none directly — both are agent86-side lifecycle strategies, not spec
capabilities (see "Not rated here" in `docs/mcp-conformance-matrix.md`)
**Success Criteria** (what must be TRUE):
  1. When a stdio server's task exits through the `except BaseException` path after `ready` has
     resolved, `self._server_tools[name]` is popped in the same `finally` block that already pops
     `self._sessions[name]`, so `tools_for()`/`tools()` (`mcp_client.py:262-266`) stop listing that
     server's tools instead of leaving them callable-but-broken.
  2. A model that calls a tool belonging to a server that has died receives a message naming the
     dead server, not a generic `RuntimeError("MCP session not available")`.
  3. `_serve` retries a dropped transport a bounded number of times with backoff before giving up,
     and a successful reconnect re-populates `self._server_tools` from a fresh `list_tools()` call.
**Sizing signal**: the defect is a confirmed, precisely-scoped bug — see "Row 7 in detail" above —
this phase should lead with it because it is the one item in this whole breakdown that is a fix
rather than new surface; `mcp_client.py:234`, `mcp_client.py:241-242` and `mcp_client.py:286-289`
are the three call sites the fix touches.
**Risk / constraint**: touches the one piece of `mcp_client.py` every other workstream-C phase
also depends on (`_serve`'s task lifecycle) — must land first among the workstream-C phases so
later phases aren't built against the buggy version; no new core dependency, cold-start unaffected
(server-death handling only fires once a session is already running).

#### Proposed Phase 16: Per-server timeouts, the result cap, and non-text content
**Workstream**: C
**Goal**: A slow-but-legitimate server and a hung one are distinguishable by config, an oversized
tool result truncates visibly instead of consuming the budget silently, and an image/audio/resource
content block renders as something other than a Python repr.
**Depends on**: Proposed Phase 15
**Requirements**: MCP-21, MCP-22, MCP-25
**Matrix rows closed**: CAP-CONTENT-BLOCKS (`absent`/`partial` → `implemented`)
**Success Criteria** (what must be TRUE):
  1. `MCPServerConfig` gains per-server `connect_timeout_s`/`call_timeout_s` fields, replacing the
     hardcoded 30s/120s in `start_server`/`call_tool` (`mcp_client.py:166,295`), with the old values
     as defaults so no existing config changes behavior.
  2. `_content_to_text` truncates a joined result at `MCPServerConfig.max_result_chars` (default
     8,000, per ADR 0004) with a visible truncation marker, never drops silently, never raises.
  3. An `ImageContent`/`AudioContent`/`EmbeddedResource` block renders as a real representation
     rather than `str(chunk)`'s Python repr.
**Sizing signal**: three independently-confirmed head-start rows land here — row 4 (timeouts,
`mcp_client.py:166,295`), row 5 (result cap, `mcp_client.py:426-434`), row 6 (content blocks,
`mcp_client.py:429-430`) — the ADR 0004 ruling this phase implements is already written, so this
phase applies a decision rather than re-deriving one.
**Risk / constraint**: `MCPConfig` schema growth (`config.py:293-294`) must go through
`config_writer.py`'s write-back path, never `config.py` itself (CLAUDE.md's read-only rule); the
default 8,000-char cap must not silently break an existing server whose legitimate results already
exceed it — this phase's first plan should audit the pinned corpus for that before shipping the
default.

#### Proposed Phase 17: Schema deferral and notification handling
**Workstream**: C
**Goal**: The system prompt's fixed overhead shrinks by deferring MCP tool schemas to first use
(never tool names), and a server-initiated notification — `list_changed`, progress, or otherwise —
reaches something other than a no-op.
**Depends on**: Proposed Phase 15
**Requirements**: MCP-20, MCP-24
**Matrix rows closed**: CAP-PROGRESS, CAP-LIST-CHANGED (both `absent` → `implemented`;
CAP-LOGGING and CAP-CANCELLATION share the same `message_handler` infrastructure this phase adds
and may close incidentally, though neither carries its own deferred requirement ID)
**Success Criteria** (what must be TRUE):
  1. The compiled system prompt still lists every mounted server's tool names (plus server
     instructions) up front; only the full JSON Schema payload is withheld until a tool's first
     call, per ADR 0003.
  2. `Harness._context_budget` accounts for a materialising schema's cost inside the step that
     triggers it, not only on the next request's recomputation.
  3. A `message_handler` passed to `ClientSession` routes `notifications/tools/list_changed` (and
     the `resources`/`prompts` siblings) into a re-fetch of that server's tool list, so
     `/config mcp`'s live mount reflects a server that changed its tools mid-session without a
     restart.
**Sizing signal**: `Harness._context_budget`'s per-request recomputation
(`docs/ARCHITECTURE.md:286-290`) already structurally tolerates a growing `tool schemas` term, per
ADR 0003's Context section — this phase applies that finding rather than re-deriving it; no
`message_handler` is passed anywhere today (`mcp_client.py:219`), so every notification, not only
`list_changed`, is currently a true no-op (`session.py:212-213`).
**Risk / constraint**: `run --json`'s keys stay additive-only for any new key signaling a
materialised schema or a live tool-list change, per ADR 0003's second-order requirement; this is
the most structurally invasive workstream-C phase (`_context_budget` and the compiled-prompt path
are both touched), so it should land last among the workstream-C phases.

##### Deferred requirements not proposed

None — every deferred requirement MCP-14 through MCP-26 above is placed in exactly one proposed
phase.

### Candidate findings outside the three workstreams

1. **Adopting the `2026-07-28` modern protocol.** The installed SDK supports it in principle —
   it appears in the SDK's own `MODERN_PROTOCOL_VERSIONS` registry — but agent86's client code
   cannot reach it today: `ClientSession.initialize()` hardcodes
   `protocol_version=LATEST_HANDSHAKE_VERSION`, which the SDK's version registry resolves to
   `2025-11-25` (`session.py:619`), the last handshake-era revision. `2026-07-28` replaces the
   `initialize` handshake with a stateless `server/discover` RPC and moves the protocol version
   into `_meta`. It also deprecates roots (SEP-2577, while `2025-11-25` still fully supports them),
   removes the `Tool.execution` field entirely, and widens `Tool.output_schema` from a
   `type: object`-rooted schema to any JSON Schema 2020-12 root. Recommendation: this is not a line
   item inside workstream A, B or C as scoped — none of MCP-14 through MCP-26 assumes a protocol
   upgrade — it is a **new, currently-unlisted workstream candidate** ("protocol modernization"),
   gated on the `mcp` SDK actually shipping a client-side `server/discover` path a future audit can
   verify, not merely declare present in the registry. `docs/mcp-conformance-matrix.md` deliberately
   does not rate `2026-07-28` against any `CAP-*` row, per the spec-revision pin (D-01) — this
   candidate finding is where that question is recorded instead of being silently dropped.
2. **Other findings with no requirement ID.** Three matrix rows carry no deferred requirement
   number at all, because no corpus server's demand justified minting one: `CAP-STRUCTURED-OUTPUT`
   (`structured_content` silently dropped — ADR 0004 leaves it explicitly unaddressed pending its
   own future ADR, not assigned to any workstream), `CAP-PING` (no corpus server needs a liveness
   probe — the transports already fail loudly on disconnect), and `CAP-META` (SDK-internal
   plumbing, not a client-code gap). Two further workstream-C rows are named in the matrix
   ("Deferred to workstream C") without an MCP-XX number of their own — `CAP-LOGGING` and
   `CAP-CANCELLATION` — because, like `CAP-PAGINATION` ("MCP-21-adjacent" but not actually MCP-21),
   no corpus server has yet demonstrated the gap in practice; they are latent risks, not proposed
   phases, and a future audit revisiting the corpus is the right place to decide whether they
   graduate to a numbered requirement.

Next: run `/gsd:add-phase` once per proposed phase above. `docs/BACKLOG.md` § 999.0's
precondition — "phases 999.0b–d are written only after the matrix is ruled on" — is now satisfied;
the ruling is `docs/mcp-conformance-matrix.md`.
