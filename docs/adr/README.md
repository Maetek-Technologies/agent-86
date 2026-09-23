# Architecture Decision Records

This directory holds agent86's ADRs — the first ADR work in the project, started in Phase 10 (the
MCP conformance audit) to rule on four decisions that touch the prompt contract, the cost cap and
the security model. Format: **lightweight MADR** (Context / Decision / Consequences), not the
fuller MADR template with alternatives-considered tables — this project's own doc voice
(`docs/ARCHITECTURE.md`, `docs/BACKLOG.md`) is prose-heavy with tables used sparingly and
precisely, and a lightweight ADR keeps that voice.

## Convention

- **Path and naming:** `docs/adr/NNNN-kebab-title.md`, numbered sequentially starting at `0001`,
  zero-padded to four digits so a plain glob (`[0-9][0-9][0-9][0-9]-*.md`) sorts and enumerates
  correctly.
- **Required headings, in this order:** `## Status`, `## Context`, `## Decision`,
  `## Consequences`.
- **`## Decision` must open with a line beginning `**Ruling:**`**, stating the decision in one
  sentence. An ADR that leaves the question open is not an ADR — ruling now, even "opt-in,
  deferred until demand," is the whole point of writing one.
- **`## Status`** carries one of `Accepted`, `Superseded by NNNN`, or `Deprecated`, plus the date
  the status was set (e.g. `Accepted — 2026-09-22`).
- **The convention is executable, not aspirational** — `tests/unit/test_docs_consistency.py`
  enforces the numbered-file glob and the four required headings (and the `**Ruling:**` line) as a
  real pytest check, not a documentation-only promise.

## Index

| ADR | Ruling |
|---|---|
| [0001 — MCP sampling is an inversion of control, not a tool](0001-mcp-sampling-inversion-of-control.md) | Sampling stays opt-in per server, deferred until a realistic corpus server demands it — not built today, and not a defect that it isn't |
| [0002 — MCP elicitation is a Tier 1 surface, and a phishing vector](0002-mcp-elicitation-tier-1-surface.md) | Elicitation stays opt-in per server, deferred until a realistic corpus server demands it, and only ever behind gateway-owned rendering with a hard-refusal list |
| [0003 — Schema deferral changes the prompt contract](0003-mcp-schema-deferral-prompt-contract.md) | Deferring tool *schemas* to first use is permissible; deferring tool *names* is not — the system prompt must keep listing every callable tool so `allowed-tools` refusals stay free |
| [0004 — Where the MCP result cap lives](0004-mcp-result-cap-location.md) | A per-server `MCPServerConfig.max_result_chars` field (default 8,000 chars), truncating with a visible marker, never dropping and never raising; `structured_content` is out of scope for this ADR |
