# Roadmap: agent86

## Milestones

- **v0.6 Interactive** — Phases 1-5 — shipped 2026-09-19
- **v0.7 Trustworthy Harness** — Phase 6 — shipped 2026-09-19
- **v0.8 Context & Cost** — Phase 7 — shipped 2026-09-19
- **v0.9 Coding-Agent UX** — Phase 8 — shipped 2026-09-21
- **v1.0 Release** — Phase 9 — shipped 2026-09-21, published to PyPI
- **v1.1 MCP Integration Depth** — Phases 10-12 — in progress (started 2026-09-22)

Full detail for v0.6-v1.0: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) ·
requirements: [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) ·
narrative: [MILESTONES.md](MILESTONES.md)

## Phases

<details>
<summary>v0.6 -> v1.0 (Phases 1-9) — SHIPPED 2026-09-21</summary>

| Phase | Milestone | Plans | Status | Completed |
|---|---|---|---|---|
| 1. TUI Skeleton + Live Status Line | v0.6 | 5/5 | Complete | 2026-07-20 |
| 2. Command Palette + Menus | v0.6 | 4/4 | Complete | 2026-07-20 |
| 3. Secrets + Model/Provider Config | v0.6 | 13/13 | Complete | 2026-08-06 |
| 4. MCP Config UI | v0.6 | 8/8 | Complete | 2026-08-06 |
| 5. Packaging & Hardening | v0.6 | direct | Complete | 2026-09-19 |
| 6. Trustworthy Harness | v0.7 | direct | Complete | 2026-09-19 |
| 7. Context & Cost | v0.8 | direct | Complete | 2026-09-19 |
| 8. Coding-Agent UX | v0.9 | direct | Complete | 2026-09-21 |
| 9. Release | v1.0 | direct | Complete | 2026-09-21 |

"direct" marks a phase executed as a coordinated subagent pass rather than as numbered
GSD plans; each still carries a `SUMMARY.md` in `phases/`.

</details>

### v1.1 MCP Integration Depth (In Progress)

**Milestone Goal:** Rule on the client half of the MCP spec — the conformance matrix, the pinned
server corpus, and the four contract-touching ADRs — so the implementation phases (workstreams A,
B, C) can be scoped from evidence rather than assumption, then build them. Phase 10 was
**deliberately the only phase at milestone start**: `docs/BACKLOG.md` § 999.0 rules that phases
999.0b–d "are written only after the matrix is ruled on." That matrix landed 2026-09-23, so the
implementation phases are now written from its recommended breakdown
([../docs/mcp-conformance-audit-2026-09.md](../docs/mcp-conformance-audit-2026-09.md)
§ "Recommended phase breakdown"), one at a time.

- [x] **Phase 10: MCP Conformance Audit** - Produce the client-side conformance matrix, pin the (completed 2026-09-23)
  five-server corpus (recording versions), and settle the four contract-touching ADRs; audit-only,
  no implementation
  — **5 plans**, 4 waves
- [x] **Phase 11: Resources and prompts become first-class** - Workstream A: `list_resources` /
 (completed 2026-09-24)
  `read_resource` / `list_prompts` / `get_prompt` / `complete` become real call sites, closing
  MCP-14 and MCP-15
  — **4 plans**, 4 waves
- [x] **Phase 12: Fix the zombie-tool desync and add reconnect** - Workstream C: a server that dies (completed 2026-09-24)
  mid-session has its tools unregistered, and a dropped transport reconnects with bounded backoff,
  closing MCP-26 and MCP-23

## Phase Details

#### Phase 10: MCP Conformance Audit
**Goal**: Rule on the client half of the MCP spec from evidence: a conformance matrix over every
client-side spec capability, a version-pinned server corpus to exercise it, and the ADRs for the
four decisions that would otherwise touch the prompt contract, the cost cap, and the security
model if implemented without a ruling. Produces documents plus one test — no implementation.
**Depends on**: Phase 9 (sequential; not a functional dependency — v1.0 shipped complete against
`docs/ARCHITECTURE.md`; the MCP client itself pre-dates this milestone)
**Requirements**: MCP-02, MCP-03, MCP-04, MCP-05, MCP-06, MCP-07, MCP-08, MCP-09, MCP-10, MCP-11,
MCP-12, MCP-13
**Success Criteria** (what must be TRUE):
  1. A reader can open the conformance matrix and find one row per client-side MCP spec
     capability, each carrying an implemented/partial/absent rating, whether a pinned corpus
     server exercises it, and an in/out ruling with written reasoning — with every "out" ruling
     also landing in `docs/ARCHITECTURE.md` §15 as a stated non-goal, not a silent gap.
  2. The audit report names all five corpus servers pinned by exact version
     (`server-everything`, `server-filesystem`, `mcp-server-git`, `live_mcp_server.py`, GitHub's
     hosted remote server) and states, with evidence, whether `server-everything` drives
     sampling, elicitation and progress.
  3. A CI test drives `tests/integration/live_mcp_server.py` to echo its own environment back to
     the client and fails if a stdio server ever receives the unscrubbed host environment —
     pinning SEC-04 end-to-end, locally and in CI, with no network dependency.
  4. Four ADR documents exist, one per contract-touching ruling — sampling as an inversion of
     control, elicitation as a Tier 1 surface, schema deferral's effect on the prompt contract,
     and where the result cap lives — each stating a ruling and its rationale rather than leaving
     the question open.
  5. The audit report confirms or corrects each of the nine head-start matrix rows against the
     current code (including the suspected `_serve`/`_server_tools` desync, ruled confirmed or
     refuted) and ends with a recommended phase breakdown for workstreams A, B and C that could be
     handed to `/gsd:add-phase` without further research.
**Plans**: 5 plans in 4 waves

Plans:
- [x] 10-01-PLAN.md — SEC-04 end-to-end stdio env-scrubbing test plus the Wave 0 cross-document
  consistency scaffold (wave 1)
- [x] 10-02-PLAN.md — pin the five-server corpus, run `server-everything` live for the MCP-07
  evidence, and rule the nine head-start rows (wave 1)
- [x] 10-03-PLAN.md — the four contract-touching ADRs: sampling, elicitation, schema deferral,
  result cap (wave 2)
- [x] 10-04-PLAN.md — the 22-row conformance matrix pinned to `2025-11-25`, and every "out" ruling
  landed in `docs/ARCHITECTURE.md` §15 (wave 3)
- [x] 10-05-PLAN.md — the workstream A/B/C phase breakdown, and the consistency check un-xfailed as
  the phase gate (wave 4)

#### Phase 11: Resources and prompts become first-class
**Workstream**: A
**Goal**: A model connected through agent86 can list and read any mounted server's resources, and
list/get its prompts — with argument-completion suggestions where the server supports them — with
the same round-trip fidelity tool calls already have.
**Depends on**: Phase 10 only
**Requirements**: MCP-14, MCP-15
**Matrix rows closed**: CAP-RESOURCES, CAP-RESOURCE-TEMPLATES, CAP-RESOURCE-SUBSCRIBE (the
`subscribe_resource` call site only — the update notification itself is closed by the proposed
schema-deferral/notification phase), CAP-PROMPTS, CAP-COMPLETION
**Success Criteria** (what must be TRUE):
  1. Connected to `@modelcontextprotocol/server-filesystem`, a model-issued tool call round-trips a
     real `list_resources` → `read_resource` pair and the file content reaches the model.
  2. Connected to `server-everything`, `list_prompts`/`get_prompt` return its 3 prompts, and
     `complete()` returns suggestions for the `completable` argument one of them exposes.
  3. A follow-up matrix re-audit moves `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`/`CAP-PROMPTS`/
     `CAP-COMPLETION` from `absent` to `implemented` in `docs/mcp-conformance-matrix.md`.
**Risk / constraint**: none of the four standing constraints are strained directly — this is
additive client surface, no new core dependency, and any new tool-result content flowing through
`run --json` is additive-only; the `mcp` extra stays optional throughout.
**Source**: [../docs/mcp-conformance-audit-2026-09.md](../docs/mcp-conformance-audit-2026-09.md)
§ "Recommended phase breakdown" → Proposed Phase 11
**Plans**: 4 plans in 4 waves

Plans:
- [x] 11-01-PLAN.md — the Wave 0 fixtures: resources/prompt/completion on the CI-safe live MCP
  server, and a capability-aware fake session for unit tests (wave 1)
- [x] 11-02-PLAN.md — resources become first-class (MCP-14): the capability-gated seam,
  list/read/templates plus subscribe/unsubscribe, and the never-inlined blob (wave 2)
- [x] 11-03-PLAN.md — prompts and argument completion become first-class (MCP-15): list/get
  prompts and `complete`, on the same seam (wave 3)
- [x] 11-04-PLAN.md — the two live-evidence runs, and the conformance matrix / ARCHITECTURE §15 /
  README / CHANGELOG re-ruling (wave 4)

#### Phase 12: Fix the zombie-tool desync and add reconnect
**Workstream**: C
**Goal**: A server that dies mid-session has its tools unregistered rather than left
callable-but-broken, and a dropped transport reconnects instead of ending the task permanently.
**Depends on**: Phase 10 only (sequenced after Phase 11, whose capability-gated tools now also
live in `_server_tools` and so widen the desync)
**Requirements**: MCP-26, MCP-23
**Matrix rows closed**: none directly — both are agent86-side lifecycle strategies, not spec
capabilities (see "Not rated here" in `docs/mcp-conformance-matrix.md`)
**Success Criteria** (what must be TRUE):
  1. When a stdio server's task exits through the `except BaseException` path after `ready` has
     resolved, `self._server_tools[name]` is popped in the same `finally` block that already pops
     `self._sessions[name]`, so `tools_for()`/`tools()` stop listing that server's tools —
     including the Phase 11 resource/prompt/completion tools — instead of leaving them
     callable-but-broken.
  2. A model that calls a tool belonging to a server that has died receives a message naming the
     dead server, not a generic `RuntimeError("MCP session not available")`.
  3. `_serve` retries a dropped transport a bounded number of times with backoff before giving up,
     and a successful reconnect re-populates `self._server_tools` from a fresh `list_tools()` call
     and a fresh `server_capabilities` read.
**Risk / constraint**: touches `_serve`'s task lifecycle, which every later workstream-C phase
(timeouts/result cap/content, schema deferral/notifications) depends on — so it lands first among
them. No new core dependency; cold-start unaffected (server-death handling only fires once a
session is running); `run --json` keys additive-only.
**Source**: [../docs/mcp-conformance-audit-2026-09.md](../docs/mcp-conformance-audit-2026-09.md)
§ "Recommended phase breakdown" → Proposed Phase 15 (renumbered 12 on promotion); defect first
flagged in [../docs/BACKLOG.md](../docs/BACKLOG.md) § 999.0 audit head start, confirmed by Phase 10
**Plans**: 8 plans in 4 waves

Plans:
- [x] 12-01-PLAN.md — end-of-stream death detection, both dicts popped, named-server errors,
  `on_tools_changed` hook (wave 1, MCP-26)
- [x] 12-02-PLAN.md — RLock-guarded ToolRegistry + identity-checked `unregister_tool` (wave 1)
- [x] 12-03-PLAN.md — bounded reconnect with local jittered backoff; stop/close never retried
  (wave 2, MCP-23)
- [x] 12-04-PLAN.md — Harness wires `on_tools_changed` into its registry so dead tools leave the
  model's tool list (wave 2)
- [x] 12-05-PLAN.md — real-stdio kill-mid-session integration test via a fixture pid file (wave 2)
- [x] 12-06-PLAN.md — real-stdio reconnect test + SSE/streamable-HTTP kill tests or recorded
  accepted risk (wave 3)
- [x] 12-07-PLAN.md — docs, VALIDATION sign-off, phase gate, TUI human-verify (wave 4)
- [x] 12-08-PLAN.md — gap closure: MCP drop/reconnect notes pushed live to the TUI, `/tools`
  server state, plain-loop drain; start-failure note unwraps ExceptionGroups and quotes the stdio
  child's stderr tail (wave 4, MCP-26, MCP-23)

## Next

**Phase 10 — MCP Conformance Audit — is complete** (5/5 plans, 2026-09-23). The conformance
matrix, the pinned five-server corpus, and the four contract-touching ADRs are landed, and the
audit ends with a ruled phase breakdown for workstreams A, B and C.

**Phase 11 — Resources and prompts become first-class — is complete** (4/4 plans, 2026-09-24).
Workstream A's first phase (requirements MCP-14 and MCP-15) shipped a capability-gated
`mcp__{server}__{list_resources,read_resource,list_resource_templates,subscribe_resource,
unsubscribe_resource,list_prompts,get_prompt,complete}` surface, and `docs/mcp-conformance-matrix.md`
now rates `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`/`CAP-PROMPTS`/`CAP-COMPLETION` `implemented` and
`CAP-RESOURCE-SUBSCRIBE` `partial` (the update notification itself stays MCP-24), all five moved
`out` → `in`. Success criterion 3 is met in full. Success criteria 1 and 2 were tested live against
the pinned `@2026.8.31` demo servers, recorded verbatim in
`phases/11-resources-and-prompts-become-first-class/11-EVIDENCE.md`: **SC2 met** —
`server-everything` returned 4 real prompts (not the 3 this roadmap text originally expected) and
`complete()` returned real suggestions for `completable-prompt`'s `department` argument
(`Engineering`/`Sales`/`Marketing`/`Support`). **SC1 not met as literally worded** — the pinned
`server-filesystem@2026.8.31` declares no `resources` capability at all (`Method not found` on
`resources/list`), so file content reaches the model only through its `tools/read_text_file`
surface, never `resources/read`; `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES` are evidenced instead by
the CI fixture's own real stdio round trip (plan 11-02), which does exercise a genuine MCP
`resources` capability end to end. This is a fact about the current third-party package, not an
agent86 defect, and is not this milestone's to fix.

**Phase 12 — Fix the zombie-tool desync and add reconnect — is next** (added 2026-09-24, not yet
planned): workstream C's lead phase, MCP-26 and MCP-23. Chosen ahead of the rest because it is the
only item in the breakdown that fixes a confirmed defect rather than adding surface, and the later
workstream-C phases build on the `_serve` lifecycle it repairs.

Phases 13+ remain **unwritten by design** and are promoted one at a time from the audit's
recommended breakdown via `/gsd:add-phase`: timeouts/result cap/non-text content and schema
deferral/notification handling (C), and OAuth discovery/authorization and token refresh against
GitHub's hosted server (B). Sampling/elicitation/roots (A, MCP-16) stays behind them: the matrix
rules all three `out` under the BACKLOG's "the ceiling is demand" rule until a realistic corpus
server needs them (ADRs 0001/0002). Sizing, corrected by the audit: **C is larger than A on
findings and deferred requirements, and materially larger than B on every metric**; A leads only
on raw matrix-row count (9 vs 7).

Behind all of it, and outranked by MCP integration work per the standing constraint below: the
seven **competitive gaps** in § Backlog below (phases 999.1–999.7) — `grep`/`glob` built-ins, tool
hooks, declarative sub-agents, a plan-mode gate, git awareness, shell network control, and an
injection classifier. Analysis for each: [../docs/BACKLOG.md](../docs/BACKLOG.md) §
"Competitive gaps 2026-09-22".

Start the milestone after v1.1 with `/gsd:new-milestone`, which gathers fresh requirements — this
milestone's `REQUIREMENTS.md` is archived and removed, by design.

## Backlog

Unsequenced parking lot (999.x). Added 2026-09-22 from a competitive read of Claude Code and
Antigravity. Full analysis for every item: [../docs/BACKLOG.md](../docs/BACKLOG.md) §
"Competitive gaps 2026-09-22".

**Standing constraint:** none of these outranks MCP integration work. 999.0a is **promoted to
Phase 10** in the active milestone (v1.1, above) and no longer lives in this unsequenced block;
999.0b–d are unblocked (Phase 10's matrix is ruled) and are being promoted into v1.1 one phase at
a time. The 999.1–999.7 items are ordered *among themselves*; MCP sits above the whole block.

Prioritised order — 999.1 → 999.2 → 999.3 → 999.4, then the rest unordered.

### Phase 999.0a: MCP conformance audit + ADRs — PROMOTED to Phase 10 (v1.1)

**Status:** Promoted 2026-09-22. This entry's scope now lives in the active roadmap as **Phase
10: MCP Conformance Audit** (see `## Phase Details` above) — kept here, unedited in substance, as
the backlog record of where it came from.
**Goal:** Turn "spec conformance" into a ruled list. Produce the client-side conformance matrix
(every spec capability × implemented/partial/absent × exercised-by-corpus × in/out with
reasoning), pin the server corpus, and write the ADRs for the four contract-touching rulings.
No implementation in this phase.
**Requirements:** See [../docs/BACKLOG.md](../docs/BACKLOG.md) § 999.0 — scope set 2026-09-22.
Three workstreams in (A client depth, B remote auth, C context & lifecycle); **MCP server mode is
a non-goal** (`docs/ARCHITECTURE.md` §15). Corpus: `server-everything`, `server-filesystem`,
`mcp-server-git`, the local `live_mcp_server.py` extended to echo its environment, and GitHub's
hosted remote server for B. Nine matrix rows are already grounded in the BACKLOG entry's audit
head start — start there, not from the spec.
**Plans:** 8/8 plans complete

### Phases 999.0b–d: MCP client depth / remote auth / context & lifecycle (BEING PROMOTED)

**Status:** Unblocked 2026-09-23 when Phase 10's matrix was ruled; sized and sequenced in
`docs/mcp-conformance-audit-2026-09.md` § "Recommended phase breakdown". Promoted so far:
**Phase 11** (999.0b, workstream A — MCP-14/MCP-15, complete 2026-09-24) and **Phase 12**
(999.0d, workstream C — MCP-26/MCP-23, added 2026-09-24). The rest are promoted one at a time.
**Goal:** The three workstreams themselves.
**Requirements:** MCP-16…MCP-26, per the audit's breakdown.
**Plans:** 0 plans

Plans:
- [x] TBD (write after Phase 10 lands) (completed 2026-09-23)

### Phase 999.1: Codebase intelligence — `grep` / `glob` built-in tools (BACKLOG)

**Goal:** Give the agent first-class search so "where is this defined?" stops routing through
approval-gated, platform-variable `run_command`.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.2: PreToolUse / PostToolUse hook events (BACKLOG)

**Goal:** An extension point between the loop and the outside world — and the deterministic
policy gate Tier 5 wants, instead of regex scanners carrying the whole story.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.3: Declarative sub-agents — `.agent86/agents/*.md` (BACKLOG)

**Goal:** Check-in-able agent definitions (Markdown + YAML front matter: model, tool allowlist,
permission mode, isolation) so `delegate` stops being dynamic-only and unreproducible.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.4: Plan-mode gate — approve one plan, not forty diffs (BACKLOG)

**Goal:** A read-only planning phase whose output is reviewed and approved once, before any
file changes — a strategic gate above the existing per-call tactical one.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.5: Git awareness — checkpoint/rewind, worktree isolation, diff surface (BACKLOG)

**Goal:** Treat the worktree as the unit of agent isolation: checkpoints, rewind, per-sub-agent
worktrees, and a diff/stage/commit surface.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.6: Network control around `run_command` (BACKLOG)

**Goal:** Close the gap where the SSRF guard protects `web_fetch` only and the shell has
unrestricted network. OS-native primitives; gVisor/WASM stay non-goals.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.7: Model-based prompt-injection classifier (BACKLOG)

**Goal:** A second model over proposed actions in auto mode, above the regex ingress/egress
scanners — with the ceiling stated honestly.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
