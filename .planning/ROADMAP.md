# Roadmap: agent86

## Milestones

- **v0.6 Interactive** — Phases 1-5 — shipped 2026-09-19
- **v0.7 Trustworthy Harness** — Phase 6 — shipped 2026-09-19
- **v0.8 Context & Cost** — Phase 7 — shipped 2026-09-19
- **v0.9 Coding-Agent UX** — Phase 8 — shipped 2026-09-21
- **v1.0 Release** — Phase 9 — shipped 2026-09-21, published to PyPI
- **v1.1 MCP Integration Depth** — Phase 10 — in progress (started 2026-09-22)

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
B, C) can be scoped from evidence rather than assumption. **Deliberately one phase**: `docs/BACKLOG.md`
§ 999.0 rules that phases 999.0b–d "are written only after the matrix is ruled on."

- [ ] **Phase 10: MCP Conformance Audit** - Produce the client-side conformance matrix, pin the
  five-server corpus (recording versions), and settle the four contract-touching ADRs; audit-only,
  no implementation
  — **5 plans**, 4 waves

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
- [ ] 10-03-PLAN.md — the four contract-touching ADRs: sampling, elicitation, schema deferral,
  result cap (wave 2)
- [ ] 10-04-PLAN.md — the 22-row conformance matrix pinned to `2025-11-25`, and every "out" ruling
  landed in `docs/ARCHITECTURE.md` §15 (wave 3)
- [ ] 10-05-PLAN.md — the workstream A/B/C phase breakdown, and the consistency check un-xfailed as
  the phase gate (wave 4)

## Next

**v1.1 is planned.** Phase 10 — MCP Conformance Audit — is planned (5 plans, 4 waves) and
ready to run: `/gsd:execute-phase 10`. It is
audit-only (no implementation) and produces the conformance matrix, the pinned corpus, and the
four ADRs described above.

Phases 11+ are **deliberately unwritten**: `docs/BACKLOG.md` § 999.0 rules that phases 999.0b–d
(workstream A client depth, B remote auth, C context & lifecycle) are written only after Phase
10's matrix is ruled on, via `/gsd:add-phase`. Audit evidence already suggests **C is larger than
A, and materially larger than B**.

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
999.0b–d remain here, blocked on Phase 10's matrix. They are ordered *among themselves*; MCP sits
above the whole block.

Prioritised order — 999.1 → 999.2 → 999.3 → 999.4, then the rest unordered.
999.0b–d are blocked on Phase 10's matrix and are not sequenced yet.

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
**Plans:** 2/5 plans executed

### Phases 999.0b–d: MCP client depth / remote auth / context & lifecycle (BACKLOG — blocked)

**Goal:** The three workstreams themselves. Deliberately unwritten: sizing and sequencing come
from Phase 10's matrix (formerly 999.0a, promoted to v1.1), and the head start suggests C > A > B
by volume.
**Requirements:** Blocked on Phase 10. Do not promote before the matrix is ruled on.
**Plans:** 0 plans

Plans:
- [ ] TBD (write after Phase 10 lands)

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
