# 0003. Schema deferral changes the prompt contract

## Status

Accepted — 2026-09-22

## Context

Schema deferral means putting tool *names* plus server instructions into the system prompt and
fetching the full JSON Schema for a tool only on its first use, rather than compiling every MCP
tool's full schema into the prompt up front. It is attractive because MCP tool schemas are the
largest uncontrolled term in the fixed prompt overhead — a server can register dozens of tools,
each with an arbitrarily large schema, and none of that is bounded by agent86 today. But deferral
collides with two mechanisms that are real and present in the code, not hypothetical, and this ADR
has to reconcile with both.

**1. The budget term.** The conversation budget is derived as:

```
window            = context_window_for(model_ref, config)
conversation      = window - (system prompt + tool schemas)
                           - limits.context_reserve_tokens
                           - max_output_tokens_for(model_ref, config)
```

(`docs/ARCHITECTURE.md:615-619`). `tool schemas` is a **named, subtracted term** in that
derivation — not folded anonymously into "system prompt." Deferring schemas changes what that term
*means* mid-session: today it is computed once per request from the full compiled tool set: every
schema, every time. In a deferred world, the term starts small (names only) and grows after each
tool's first use, as that tool's full schema materialises into the prompt. That is a real shift in
what "the fixed overhead" means, and it has to be said explicitly rather than left implied.

It is not, however, a shift the design is unprepared for. `Harness._context_budget` already
recomputes the budget **before every request** (`docs/ARCHITECTURE.md:286-290`), precisely because
skills, MCP servers and the episodic recall note already change the overhead mid-session — a
figure computed once at startup would already be wrong by the second step, deferred schemas or
not. So the "recomputed before every request" design structurally tolerates a growing `tool
schemas` term today; deferral would exploit a property the budget computation already has, not
require a new one.

**2. The `allowed-tools` gate.** "The compiled system prompt lists each skill's `allowed-tools`,
so the boundary is known before a refusal costs a step" (`docs/ARCHITECTURE.md:543-544`). This is
the distinction the ruling below turns on. If the system prompt keeps listing every tool's *name*
— even when its schema is deferred — the model still learns the full boundary of what it may call
up front: an out-of-allowlist call is still refused before a step is spent, exactly as today.
If schema deferral is taken one step further to defer *which tools exist at all* — not just their
schemas — that boundary disappears: the model can no longer tell, from the prompt alone, whether a
tool is out of bounds or simply not yet materialised, and every such refusal now costs a step
instead of being free.

## Decision

**Ruling:** deferral of **schemas** is permissible; deferral of tool **names** is not. A future
implementer can apply this without re-reading this document: the system prompt must always list
every callable tool's name (plus its server's instructions, where present), for every mounted
server, regardless of whether that tool has ever been called. Only the full JSON Schema payload
for a tool's arguments may be withheld until the tool's first use.

Second-order requirements that follow from this ruling:

- **The budget must be recomputed after a schema materialises, not only at turn start.** A
  deferred schema's first fetch happens mid-turn, inside the step that calls the tool for the
  first time — `Harness._context_budget`'s existing per-request recomputation already covers the
  *next* request, but the step that triggers materialisation must account for the schema's cost
  before deciding whether the resulting request still fits, not discover the overrun after the
  fact.
- **A deferred schema's first fetch is a synchronous cost inside the step that needs it** — it is
  not a background operation and must not be modelled as free; the step that first calls a
  previously name-only tool pays the schema-materialisation cost as part of that step, visibly.
- **`run --json` keys stay additive-only.** Any key schema deferral would add to the scripting
  contract's output (e.g. to signal a tool's schema was materialised mid-turn) is additive, never a
  replacement for or removal of an existing key — the same rule the rest of the harness's
  `run --json` surface already follows.

## Consequences

**What MCP-20 (workstream C) inherits as a specification, not an open question:** schema deferral,
if built, must preserve the full tool-name listing in the system prompt; must recompute the budget
around a materialising schema's cost rather than after the fact; and must not touch `run --json`'s
existing keys.

**What breaks if a future implementer defers names as well:** the `allowed-tools` boundary
(`ARCHITECTURE.md:543-544`) stops being knowable from the prompt alone, and every refusal of a
not-yet-materialised tool costs a step instead of being free — exactly the cost `allowed-tools`
gating exists to avoid. This ADR rules that trade-off out; a future implementer proposing it would
need a new ADR, not an extension of this one.

**For the conformance matrix:** schema deferral is an agent86-side prompt-compilation strategy, not
a spec-level client capability — the MCP spec does not define "deferred schema" as a capability a
client implements or doesn't. It therefore gets **no matrix row**; nobody should go looking for a
`CAP-SCHEMA-DEFERRAL` row in `docs/mcp-conformance-matrix.md`, because this ruling is the record of
that decision, not the matrix.
