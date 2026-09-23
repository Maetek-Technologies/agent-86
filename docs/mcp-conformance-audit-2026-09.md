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

_(filled by task 2 of this plan)_

## Recommended phase breakdown — workstreams A, B and C

_(filled by plan 10-05)_
