# Requirements: agent86 — v1.1 MCP Integration Depth

**Defined:** 2026-09-22
**Core Value:** Rule on the client half of the MCP spec from evidence — a conformance matrix, a
pinned corpus and the contract-touching ADRs — so the implementation phases are scoped from what
real servers exercise rather than from what the spec permits.

**Scope origin:** `docs/BACKLOG.md` § 999.0, scoped 2026-09-22. The scope was **given, not
inferred** — the four rulings (which workstreams are in, that server mode is out, conformance as
the driver, demand as the ceiling) were answered by the requester. Do not widen it by inference:
the audit's job is to propose, not to assume.

## v1.1 Requirements

Phase 10 is **audit-only — no implementation.** Every requirement below is satisfied by a written
artifact plus, where stated, a test that pins it.

### Conformance matrix

- [x] **MCP-02**: A reader can see, for every client-side MCP spec capability, whether agent86
      implements it fully, partially, or not at all — one row per capability, so nothing is missed
      by accident
- [x] **MCP-03**: Each matrix row records whether a pinned corpus server exercises that
      capability, making the demand ceiling visible rather than asserted
- [x] **MCP-04**: Each matrix row carries an in/out ruling with written reasoning, and every
      "out" ruling lands in `docs/ARCHITECTURE.md` §15 as a conformance statement — a stated
      non-goal with its reasoning, never a silent gap

### Pinned corpus

- [x] **MCP-05**: The audit runs against a corpus of five servers recorded by version —
      `@modelcontextprotocol/server-everything`, `@modelcontextprotocol/server-filesystem`,
      `mcp-server-git`, `tests/integration/live_mcp_server.py`, and GitHub's hosted remote MCP
      server — so the same versions can be re-run later
- [x] **MCP-06**: `tests/integration/live_mcp_server.py` echoes its own environment, pinning
      SEC-04 (stdio servers get `SandboxPolicy.scrubbed_env()`, not the host environment)
      end-to-end in CI, locally and with no network
- [x] **MCP-07**: The audit determines whether `server-everything` drives sampling, elicitation
      and progress — the answer deciding whether those three are demand-triggered or stay written
      non-goals. This is the first audit task, because it gates MCP-08 and MCP-09

### Architecture decision records

- [x] **MCP-08**: An ADR rules on **sampling as an inversion of control, not a tool** —
      implementing it makes agent86 the model provider for a *server's* request: third-party spend
      inside our turn against `limits.max_cost_usd`, with the completion visible to the server. If
      it ships at all it is opt-in per server, with its own approval gate and egress pass
- [x] **MCP-09**: An ADR rules on **elicitation as a Tier 1 surface** — a server prompting our
      user through our gateway is a phishing vector. Who renders it, and what it may not ask for,
      precede any decision to support it
- [x] **MCP-10**: An ADR rules on **schema deferral changing the prompt contract** — names plus
      server instructions in the system prompt with full schema on first use means the prompt no
      longer lists every callable tool, which interacts with `allowed-tools` gating (the prompt
      currently names the boundary so a refusal does not cost a step) and with `context_budget`'s
      fixed-overhead computation
- [x] **MCP-11**: An ADR rules on **where the result cap lives** — `_content_to_text` joins every
      content part uncapped while the flight recorder clips at `max_field_chars`; the ADR decides
      the prompt-side cap's home and whether it is per-server

### Evidence and sizing

- [x] **MCP-12**: Each of the nine matrix rows already grounded by the BACKLOG audit head start is
      confirmed or corrected against the current code — including the suspected defect in
      `_serve`, whose `finally` pops `self._sessions[name]` but leaves `self._server_tools[name]`
      populated while `call_tool` indexes `self._sessions[server]`. Confirmed before any fix is
      proposed; this phase proposes, it does not fix
- [x] **MCP-13**: The audit outputs a recommended phase breakdown for workstreams A, B and C
      derived from the matrix, so phases 11+ can be written. Audit evidence already suggests
      **C is larger than A, and materially larger than B**

## Future Requirements (deferred)

The three workstreams are **in scope for the programme, not for this milestone.**
`docs/BACKLOG.md` § 999.0 rules that phases 999.0b–d "are written only after the matrix is ruled
on", so these are provisional: MCP-02…MCP-04 decide which survive, which become written non-goals,
and how they are grouped into phases 11+ via `/gsd:add-phase`.

### Workstream A — client depth (Tier 4, with Tier 3 fallout)

- [x] **MCP-14**: Resources become first-class — `list_resources` and `read_resource`, absent today — Phase 11
- [x] **MCP-15**: Prompts become first-class — `list_prompts` and `get_prompt`, absent today — Phase 11
- **MCP-16**: Sampling, elicitation and roots are supported *only* as MCP-07 through MCP-09 rule
  them in. They are structurally absent today: `ClientSession(read, write)` is built with no
  callbacks, so any one of them is a constructor change

### Workstream B — remote auth (Tier 4 + secrets)

- **MCP-17**: OAuth 2.0 discovery and authorization for hosted servers. Auth today is `headers`
  plus `${VAR}` only
- **MCP-18**: Token refresh, with tokens stored in the existing keyring — the plumbing from
  `/config model` is reusable as-is
- **MCP-19**: An auth flow that works both interactively and headless in CI. This is a design
  decision, not a library choice, and it strains the standing constraints hardest

### Workstream C — context and lifecycle (Tier 3/4)

- [x] **MCP-20**: Schema deferral, as ruled by MCP-10 — Phase 14
- **MCP-21**: Per-server configurable timeouts. Today they are hardcoded and asymmetric — 30 s
  connect, 120 s per tool call — and `MCPConfig` carries only `enabled`, so a slow legitimate
  server and a hung one are indistinguishable
- **MCP-22**: A prompt-side result cap, as ruled by MCP-11
- **MCP-23**: Reconnect after a dropped transport. There is no reconnect path at all today:
  `_serve` awaits `close_event`, and a dropped transport ends the task
- [x] **MCP-24**: `list_changed` handling. No `message_handler` is installed, so every server
  notification is dropped and a server that changes its tool list mid-session is invisible until
  restart — and `list_changed` is the mechanism `/config mcp`'s live mount already wants — Phase 14
- **MCP-25**: Non-text content blocks handled. Only `.text` is read today; image, audio and
  embedded-resource blocks fall through to `str(chunk)`, so a base64 blob lands in the prompt
  verbatim
- **MCP-26**: The session/registry desync on server death fixed, if MCP-12 confirms it

## Out of Scope

| Feature | Reason |
|---------|--------|
| **MCP server mode** | agent86 stays a client and does not become mountable by other harnesses. Recorded in `docs/ARCHITECTURE.md` §15 so the slot is not reopened by inference |
| Any MCP implementation in Phase 10 | Audit-only by design. The matrix must rule before code is written, or the rulings are post-hoc |
| DocIngest as a corpus server | Explicitly excluded — the corpus is common examples only, so the audit's conclusions generalise |
| The archived `modelcontextprotocol/servers` reference server for workstream B | Use GitHub's externally maintained hosted product instead, so OAuth, streamable HTTP and refresh are exercised against something real |
| New core dependencies | The `mcp` extra stays optional with graceful degradation; the cold-start budget holds |
| Breaking `run --json` keys | The scripting contract is additive-only |
| Rebuilding the MCP client | It is built and complete against `docs/ARCHITECTURE.md` as a *tool* client over all three transports. This milestone is about depth, auth and lifecycle |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MCP-02 | Phase 10 | Complete |
| MCP-03 | Phase 10 | Complete |
| MCP-04 | Phase 10 | Complete |
| MCP-05 | Phase 10 | Complete |
| MCP-06 | Phase 10 | Complete |
| MCP-07 | Phase 10 | Complete |
| MCP-08 | Phase 10 | Complete |
| MCP-09 | Phase 10 | Complete |
| MCP-10 | Phase 10 | Complete |
| MCP-11 | Phase 10 | Complete |
| MCP-12 | Phase 10 | Complete |
| MCP-13 | Phase 10 | Complete |
| MCP-14 | Phase 11 | Complete |
| MCP-15 | Phase 11 | Complete |
| MCP-23 | Phase 12 | Complete |
| MCP-26 | Phase 12 | Complete |
| MCP-21 | Phase 13 | Complete |
| MCP-22 | Phase 13 | Complete |
| MCP-25 | Phase 13 | Complete |
| MCP-20 | Phase 14 | Complete |
| MCP-24 | Phase 14 | Complete |

**Coverage:**
- v1.1 requirements: 21 total (12 Phase 10 + 2 Phase 11 + 2 Phase 12 + 3 Phase 13 + 2 Phase 14 to date)
- Mapped to phases: 21
- Unmapped: 0 ✓ (the remaining deferred IDs — MCP-16…MCP-19 — stay
  intentionally unmapped until written into a future phase)

Deferred requirements are intentionally unmapped — they are written into phases only after
scoped via `/gsd:add-phase`.

---
*Requirements defined: 2026-09-22*
*Last updated: 2026-09-25 after Phase 14 added (MCP-20, MCP-24)*
