# 0004. Where the MCP result cap lives

## Status

Accepted — 2026-09-22

## Context

`_content_to_text` (`src/agent86/tools/mcp_client.py:426-434`) joins every content part of a tool
result with no size limit anywhere in the function, and `call_tool` (`mcp_client.py:292-293`)
applies none at its call site either — a server that returns a large resource dump sends the whole
thing straight into the model's context budget, uncapped, on every call. The contrast that gives
this ADR its shape: a cap of this kind **does already exist**, just on the wrong side of the
boundary — the flight recorder clips big free-text fields at `[observability] max_field_chars`
before they reach the trace file. That cap protects the *trace*; nothing protects the *prompt*,
and those are different budgets with different consequences for going over.

Two further facts widen the scope of what "uncapped" means here, and both must be dealt with by
this ADR rather than conflated into one fix:

- **`CallToolResult.structured_content` is never read** (`mcp_types/_types.py:1474` on the
  installed SDK) — so when a tool returns typed, structured output alongside its text content,
  that structured output is not merely uncapped, it is **silently dropped**. A cap on text content
  does nothing for this; it is a separate gap.
- **Non-text content blocks fall through to `str(chunk)`** (`mcp_client.py:429-430`) — an
  `ImageContent`, `AudioContent`, or `EmbeddedResource` block is not skipped or summarised, it is
  rendered as its Python object repr and joined into the prompt text as-is. Capping the *number of
  bytes* of that repr does not fix the underlying problem that it is the wrong representation in
  the first place; these are two different gaps that happen to share one function.

**Candidate homes for a prompt-side cap**, weighed:

1. **A module-level constant in `mcp_client.py`.** Simplest to implement, uniform across every
   server, but gives an operator no way to raise the cap for one server they trust more (e.g. a
   local filesystem server) or lower it for one they trust less, without a code change.
2. **A `[limits]` config key applying to every MCP server uniformly.** One config knob, consistent
   with how `limits.max_cost_usd` and `limits.context_reserve_tokens` already work, but still
   uniform across servers with very different result shapes (a `get-tiny-image` tool and a
   `simulate-research-query` tool have nothing in common in expected result size).
3. **A per-server `MCPServerConfig` field.** `MCPConfig` today carries only `enabled: bool`
   (`src/agent86/config.py:293-294`), so this is a schema addition — a new field on
   `MCPServerConfig`, written back through `config_writer.py` (never TOML written from
   `config.py`, per CLAUDE.md's read-only rule for that module). This lets a chatty or
   large-payload server be capped tighter than a terse one, at the cost of one more field to
   document.
4. **The tool layer generally, capping every tool's result, not only MCP's.** Broader in principle
   — a non-MCP tool with an unbounded result has the identical problem — but out of scope for an
   MCP-only audit phase, and would need its own evidence of which built-in tools actually return
   unbounded results before it could be ruled on responsibly.

## Decision

**Ruling:** the cap lives as a **per-server `MCPServerConfig` field**
(`MCPServerConfig.max_result_chars: int`, default **8,000 characters**), option 3 above. It is
per-server, not global, because MCP servers vary enormously in expected result size and a uniform
cap would either be too tight for a legitimate bulk-data server or too loose to protect the budget
against a chatty one; the per-server field lets each mounted server carry the number that fits its
actual payloads, with the module-level default applying to any server that doesn't set one
explicitly. 8,000 characters is chosen as the default because it is roughly 2,000 tokens at the
project's already-used ~4 chars/token estimate (`docs/ARCHITECTURE.md`'s cache-eligibility
estimate) — large enough that no observed corpus-server tool result in this audit's MCP-07 run
came close to it, small enough that one unbounded result cannot silently consume a meaningful
fraction of a typical conversation budget on its own.

**Behaviour when the cap is exceeded:** `_content_to_text` truncates the joined body at the cap and
appends a visible, explicit truncation marker the model can see and act on — the same pattern the
flight recorder's `max_field_chars` clip already uses for the trace side, applied here to the
prompt side. It never silently drops content past the cap (a model reasoning over a silently
shortened result would draw wrong conclusions without knowing why), and it never raises — a tool
must never raise into the loop (CLAUDE.md's hard rule) — an oversized result is a truncation, not a
failure.

**Scope:** `structured_content` is **explicitly out of scope for this ADR**. Whether and how to
surface `CallToolResult.structured_content` — today silently dropped entirely, not merely uncapped
— is a separate question from capping the size of the text content this ADR rules on; a future ADR
or the MCP-22 implementation may take it up, but this ruling only governs `_content_to_text`'s
existing text-join path.

## Consequences

**What MCP-22 (workstream C) inherits:** a named field (`MCPServerConfig.max_result_chars`), a
named default (8,000 characters), and a named behaviour (truncate with a visible marker, never
drop, never raise) — MCP-22's implementation applies this ruling rather than re-deriving it.

**Interaction with ADR 0003's budget term:** a capped MCP result bounds how much a single tool call
can grow the `tool schemas`-adjacent conversation content in one step, which makes the budget
recomputation ADR 0003 requires more predictable — a materialising schema plus an uncapped result
in the same step would have been a much harder number to bound in advance; a capped result removes
one of the two unknowns.

**For the conformance matrix:** `CAP-STRUCTURED-OUTPUT` is ruled **out** — `structured_content` is
never read, is silently dropped today, and this ADR leaves that gap explicitly unaddressed pending
its own future ruling. `CAP-CONTENT-BLOCKS` is ruled **out** — non-text content blocks fall through
to `str(chunk)`, a Python repr in the prompt, and capping bytes (this ADR's ruling) does not fix
that representation problem; it is a distinct, still-open gap. Plan 10-04 reads both rulings
directly from this paragraph.
