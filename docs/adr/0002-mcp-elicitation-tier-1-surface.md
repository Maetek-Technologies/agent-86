# 0002. MCP elicitation is a Tier 1 surface, and a phishing vector

## Status

Accepted — 2026-09-22

## Context

Like sampling, this is a build-or-don't decision, not a defect report: agent86 currently
**declares** elicitation unsupported, correctly, at the protocol level, on the same SDK mechanism
as ADR 0001. `mcp_client.py:219` passes no `elicitation_callback` to `ClientSession(read, write)`,
so the SDK's default stays installed — `_default_elicitation_callback` returns
`ErrorData(code=INVALID_REQUEST, message="Elicitation not supported")` when called, but more to
the point, `_build_capabilities()` (`session.py:596-600`) never advertises `elicitation` as a
capability in the first place, because the callback in use is still the default. A spec-compliant
server sees no elicitation capability at `initialize()` and will not attempt the request.

**Two modes, one sharper than the other.** The `2025-11-25` revision carries two elicitation
modes: form elicitation (a structured prompt for data) and URL elicitation (a link the server
hands the user to open). `server-everything` exercises both — `trigger-elicitation-request` for
the form mode, `trigger-url-elicitation` for the URL mode. URL mode is the sharper edge of the
two: a connected server handing our user a link to open, through our own interface, is
indistinguishable in presentation from agent86 itself vouching for that link.

**Why this is a Tier 1 (gateway) concern, not a Tier 4 (tools) concern.** A tool call is something
the model proposes and the harness executes or refuses — the trust boundary is between the model
and the harness. Elicitation inverts that: a *server* is asking to prompt our *user*, through our
gateway, and whatever agent86 renders inherits agent86's own trust with that user. The user has no
way to tell an elicitation prompt apart from agent86's own prompt — there is no visual or textual
signal today that would let them, and inventing one is squarely a gateway-tier design problem, not
a tool-tier one.

**Who would render it.** agent86 has two interactive surfaces — the Textual TUI and the plain loop
— and one non-interactive one, `run` / `run --json`, the scripting/CI contract. Any elicitation
design has to answer what happens in the non-interactive case explicitly, not by omission: a
non-interactive turn cannot pop a modal or block on stdin, and `run --json`'s output keys are
additive-only, so any elicitation-related key added to that contract must be additive too, never a
replacement for an existing key.

**What a server must never be allowed to ask for.** Rather than a general principle, the list is
concrete: credentials, API keys, anything matching the guardrail tier's own secret-shaped patterns
(`guardrails/scanners.py`, `secrets.py`), and any free-text field whose answer would be forwarded
back to the server verbatim without first passing through an egress pass. An elicitation design
that lets a server ask for any of these, even once, defeats the entire point of ruling on this
before building it.

**The demand signal.** As recorded in `docs/mcp-conformance-audit-2026-09.md`'s MCP-07 section,
both `trigger-elicitation-request` and `trigger-url-elicitation` were **absent** from the 13 tools
agent86 received from the live `server-everything` run, for the identical capability-gating reason
as sampling — agent86 declares no elicitation capability, so the server correctly withheld both
tools. The report also notes that a newer tool, `simulate-research-query` (present in the tool
list agent86 *did* receive), documents elicitation-conditional behaviour in its own description
("if 'ambiguous' is true and client supports elicitation, sends an elicitation request for
clarification") — but that branch is gated on the same declared-capability signal agent86 does not
raise, so it is not reachable through agent86 either. As with sampling, the only corpus server
observed driving elicitation is the conformance instrument itself.

## Decision

**Ruling:** elicitation stays **opt-in per server, deferred until a realistic corpus server
demands it** — the same two-option space as ADR 0001, resolved the same way, for the same reason:
the only server observed exercising it is the audit's own instrument, and the preconditions below
do not yet exist.

Non-negotiable preconditions any future implementation must satisfy before elicitation ships at
all:

- **Who renders it:** the gateway tier, never the tool tier — elicitation UI is visually and
  structurally distinct from agent86's own prompts, so a user can always tell which is asking.
- **What it may never ask for:** the concrete refusal list above (credentials, API keys,
  secret-shaped strings, any answer forwarded without an egress pass) is enforced in code, not
  left as a documented expectation a server can ignore.
- **What happens headless:** a non-interactive turn (`run`, `run --json`) either declines
  elicitation automatically with a recorded reason, or surfaces it through an additive-only
  `run --json` key — it must never block waiting on input that can't arrive.
- **A refusal is a normal answer, not an error the model retries around.** The model must see a
  declined elicitation as a legitimate outcome of that step, the same way a declined tool approval
  is, not as a failure worth immediately retrying.

## Consequences

**What stays true if this ruling holds:** no server can prompt our user through our own interface
today; the phishing-vector risk this ADR names stays closed rather than open-and-unaddressed; MCP-16
stays deferred exactly as scoped, alongside sampling and roots.

**What this ruling costs:** any MCP server whose interaction model depends on asking the user
follow-up questions — the demo pattern `simulate-research-query` documents — cannot use that
pattern through agent86 until the preconditions above are met.

**For the conformance matrix (plan 10-04):** `CAP-ELICITATION` is ruled **out** — absent today,
correctly declared absent, deliberately not built pending the demand signal and the four
preconditions named above. This is the sentence plan 10-04 copies into the matrix row.
