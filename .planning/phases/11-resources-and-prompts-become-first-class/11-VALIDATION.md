---
phase: 11
slug: resources-and-prompts-become-first-class
status: planned
nyquist_compliant: false
wave_0_complete: true
created: 2026-09-23
planned: 2026-09-23
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `11-RESEARCH.md` § "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2+ / pytest-asyncio 0.23+ (`pyproject.toml:59`), `asyncio_mode = "auto"` (`pyproject.toml:119`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (no separate `pytest.ini`) |
| **Quick run command** | `pytest tests/unit/test_mcp.py tests/integration/test_mcp_client.py -q` |
| **Full suite command** | `pytest -q` (default `addopts = "-m 'not packaging'"` excludes the slow packaging suite) |
| **Estimated runtime** | ~20 seconds quick / ~120 seconds full |

**Skip pattern (MANDATORY for new live-stdio tests):** module-level
`try: import mcp.server.mcpserver; _HAS_MCP_SERVER = True; except ImportError: _HAS_MCP_SERVER = False`,
then `@pytest.mark.skipif(not _HAS_MCP_SERVER, ...)` per real-transport test. Never a bare
module-scope `pytest.importorskip` — that would also skip the mock-only tests in the same file.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_mcp.py tests/integration/test_mcp_client.py -q`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green, plus both manual live-evidence runs
  (SC1 against `server-filesystem`, SC2 against `server-everything`) recorded below
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

Wave numbers below are the *validation* waves the research named (0 = fixtures). The frontmatter
`wave:` on each PLAN is offset by one, matching Phase 10's precedent — plan 11-01 carries the
Wave 0 work at `wave: 1`.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01 T1 | 11-01 | 0 | MCP-14/15 | fixture | `pytest tests/integration/test_mcp_client.py -q` | ✅ landed — `live_mcp_server.py` extended with `.resource()` / `.prompt()` / `.completion()` | ✅ green |
| 11-01 T2 | 11-01 | 0 | MCP-14 | fixture | `pytest tests/unit/test_mcp.py -q` | ✅ landed — fake `ServerCapabilities` session fixture extending `_install_fake_transport` (`tests/unit/test_mcp.py:328-364`) | ✅ green |
| 11-02 T3 | 11-02 | 1 | MCP-14 | integration | `pytest tests/integration/test_mcp_client.py -k resource -q` | ❌ W0 dep (11-01 T1) | ⬜ pending |
| 11-02 T3 | 11-02 | 1 | MCP-14 | unit | `pytest tests/unit/test_mcp.py -k resources_capability -q` | ❌ W0 dep (11-01 T2) | ⬜ pending |
| 11-02 T3 | 11-02 | 1 | MCP-14 | unit | `pytest tests/unit/test_mcp.py -k blob_resource -q` | ❌ W0 dep (11-01 T2) | ⬜ pending |
| 11-03 T3 | 11-03 | 1 | MCP-15 | integration | `pytest tests/integration/test_mcp_client.py -k prompt -q` | ❌ W0 dep (11-01 T1) | ⬜ pending |
| 11-03 T3 | 11-03 | 1 | MCP-15 | integration | `pytest tests/integration/test_mcp_client.py -k complete -q` | ❌ W0 dep (11-01 T1) | ⬜ pending |
| 11-03 T3 | 11-03 | 1 | MCP-15 | unit | `pytest tests/unit/test_mcp.py -k prompts_capability -q` | ❌ W0 dep (11-01 T2) | ⬜ pending |
| 11-04 T2 | 11-04 | 2 | SC3 (docs) | docs | `pytest tests/unit/test_docs_consistency.py -q` | ✅ exists (enforces matrix *shape*, not rating) | ⬜ pending |

*Task IDs filled by the planner 2026-09-23; the rows above are the required verification surface.*
*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Implementation tasks with no row of their own (11-02 T1/T2, 11-03 T1/T2) each carry
`<automated>pytest tests/unit/test_mcp.py -q</automated>` in their own plan, so sampling
continuity holds: no three consecutive tasks run without an automated verify.

---

## Wave 0 Requirements

- [x] `tests/integration/live_mcp_server.py` — add a `.resource()`-decorated resource, a
      `.prompt()`-decorated prompt (with at least one completable-style argument), and a
      `.completion()` handler, so CI exercises resources/prompts/completion without network or
      `npx` (mirrors the `add`/`shout`/`get_env` tools added for SEC-04 in plan 10-01)
      Landed by plan 11-01 Task 1: three resources (`res://agent86/greeting.txt` text,
      `res://agent86/blob.bin` binary, `res://agent86/echo/{word}` template), the `review_code`
      prompt with `path`/`style` arguments, and a `complete_argument` handler offering
      `STYLE_COMPLETIONS` for `style`. `resources.subscribe` is `False` and cannot be raised
      through `MCPServer` — the subscribe/unsubscribe call sites are covered by the fake session
      instead.
- [x] `tests/unit/test_mcp.py` — a fake `ServerCapabilities`-bearing session fixture (extending
      `_install_fake_transport`) so capability-gated registration is unit-testable without a real
      server
      Landed by plan 11-01 Task 2: `_FakeCaps` / `_FakeResourcesCap` / `_FakePromptsCap` /
      `_FakeCompletionsCap`, `_fake_result`, and `_install_fake_transport(..., capabilities=,
      responses=, calls=)`.
- [ ] Framework install: **none** — the `mcp` extra is already a dev/test dependency
      (`pyproject.toml:59,62`)

**Planner note (2026-09-23):** an `MCPServer`-hosted fixture declares `resources.subscribe = False`
and cannot be made to declare it `True` — the high-level server never registers a
`resources/subscribe` handler. The `subscribe_resource` / `unsubscribe_resource` call sites are
therefore covered by the fake session, not the live fixture. Verified by running the proposed
fixture code during planning: `resources={'subscribe': False, 'list_changed': False}`,
`prompts={'list_changed': False}`, `completions={}`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real `list_resources` → `read_resource` round-trip against `@modelcontextprotocol/server-filesystem`, file content reaching the model | Roadmap SC1 | Phase 10 ruling D-03: CI must stay network-free and `npx`-free | Scratchpad script, same pattern as the MCP-07 run in `docs/mcp-conformance-audit-2026-09.md`; transcript recorded in `11-EVIDENCE.md` by plan 11-04 Task 1 |
| `list_prompts`/`get_prompt` return `server-everything`'s 3 prompts; `complete()` returns suggestions for its `completable` argument | Roadmap SC2 | Same as SC1 | Scratchpad script against pinned `server-everything@2026.8.31` (re-verified 2026-09-23 via `npm view`); record real prompt name + argument name in `11-EVIDENCE.md` |
| Four matrix rows ruled `absent` → `implemented` | Roadmap SC3 | The *rating* is a human/plan judgement; only the matrix shape is machine-checked | Plan 11-04 Task 2 edits `docs/mcp-conformance-matrix.md` only after the full suite is green and both evidence runs above are recorded |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`live_mcp_server.py` fixtures, fake capabilities session)
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] Both manual live-evidence runs (SC1, SC2) recorded before the matrix is edited
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
