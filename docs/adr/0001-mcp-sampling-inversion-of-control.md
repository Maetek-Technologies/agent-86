# 0001. MCP sampling is an inversion of control, not a tool

## Status

Accepted — 2026-09-22

## Context

This is a build-or-don't decision, not a defect report. agent86 currently **declares** sampling
unsupported, correctly, at the protocol level — the question this ADR rules on is whether to
change that, not whether something is broken today.

**What sampling is, on the wire.** A server sends `sampling/createMessage`; the client answers
through a `sampling_callback`. Supporting it inverts who calls whom for that one exchange: agent86
stops being the thing that calls a model on the user's behalf and becomes, for the duration of
that request, the model provider for a *third party's* request — the connected MCP server's, not
the user's.

**Why agent86 does not do it today, and why that is correct.** `mcp_client.py:219` constructs
`ClientSession(read, write)` with no `sampling_callback` argument. The installed SDK's
`_build_capabilities()` (`session.py:591-595`) sets `sampling=None` in `ClientCapabilities`
whenever the callback installed is still the SDK's own default — which it is here, since none was
passed. So agent86 doesn't silently fail to answer a `sampling/createMessage` request; it never
advertises the capability in the first place, during `initialize()`. A spec-compliant server sees
`sampling=None` and will not even attempt the request. This is the protocol's own way of saying
"not supported," and agent86's current behaviour is a **declared** non-support, not a silent gap
or a latent defect.

**The demand signal.** `docs/mcp-conformance-audit-2026-09.md`'s MCP-07 section records what
actually happened when agent86 connected to a live `@modelcontextprotocol/server-everything`
instance: both `trigger-sampling-request` and `trigger-sampling-request-async` were **absent**
from the 13 tools agent86 received, out of the 16 the audit set out to check. The report's own
capability-gating explanation is exact: `server-everything` conditionally registers its
sampling-triggering tools based on the capabilities the connecting client declared at
`initialize()`, and because agent86 declares none, the server correctly withheld those two tools
from this client. That absence is the mechanism working as designed, not `server-everything`
failing to offer sampling — and it means the *only* corpus server that drives sampling at all is
the conformance instrument built to exercise the full spec, not a realistic workload server
(`server-filesystem`, `mcp-server-git`, GitHub's hosted server) that a real session would actually
mount.

**Why this is expensive rather than merely new, if it shipped.** Four things distinguish sampling
from an ordinary tool call:

1. **Third-party spend inside our turn.** A server's `sampling/createMessage` request, answered by
   calling a model on agent86's behalf, spends against `limits.max_cost_usd` for work the *user*
   never asked for directly — a server-initiated cost inside a user-initiated budget.
2. **The completion becomes visible to the server.** Whatever the model answers goes back over the
   wire to the requesting server. That is a new egress surface — the existing egress pass covers
   model output flowing *to the user*, not model output flowing *to a third-party server* — and it
   would need its own pass, not a reuse of the existing one.
3. **It needs its own approval gate.** The tool-call approval gate exists because the model
   *proposed* a step; sampling is the reverse — the server proposes a request the model never made,
   so the existing per-tool gate does not cover it.
4. **Whose model, at whose price, under which provider's key.** A sampling handler has to decide
   which model answers a server's request and which API key pays for it. CLAUDE.md's hard rule —
   API keys are never stored in config, only `api_key_env` is named — constrains any answer here:
   an opt-in sampling handler cannot invent a new credential-storage path to answer this question.

## Decision

**Ruling:** sampling stays **opt-in per server, deferred until a realistic corpus server demands
it** — not built today, not because agent86 is missing something, but because the only server that
exercises it is the conformance instrument itself, and the cost/egress/approval machinery a real
implementation needs does not yet exist and should not be built speculatively.

This reopens when a corpus server whose primary value depends on sampling is added to the pinned
corpus (i.e., a server the audit or a future workstream A pass judges worth mounting for its own
sake, not to exercise the spec). If it ships, the shape is:

- A per-server opt-in flag, described as a future field on `MCPServerConfig` in `config.py`'s
  schema (today `MCPConfig` carries only `enabled: bool`, `config.py:293-294`), written back
  through `config_writer.py` — never TOML written from `config.py` (CLAUDE.md's read-only rule).
- A dedicated approval gate distinct from the existing per-tool-call gate, since the server, not
  the model, originates the request.
- An egress pass over the completion before it leaves for the server, distinct from the pass that
  covers model output to the user.
- The sampled call's tokens folded into the same cost accounting sub-agent calls already use —
  counted against `limits.max_cost_usd`, never against a separate, invisible budget.

## Consequences

**What stays true if this ruling holds:** every connected server keeps receiving a correct "not
supported" signal at `initialize()`; no third-party spend path opens inside agent86's cost cap;
MCP-16 (workstream A's sampling/elicitation/roots line item) stays deferred exactly as scoped.

**What this ruling costs:** any MCP server whose main value proposition is driving sampling
through the connecting client is simply unusable with agent86 today, and stays that way until the
preconditions above are met.

**For the conformance matrix (plan 10-04):** `CAP-SAMPLING` is ruled **out** — absent today,
correctly declared absent, and deliberately not built pending the demand signal named above. This
sentence is the ruling plan 10-04 copies into the matrix row.
