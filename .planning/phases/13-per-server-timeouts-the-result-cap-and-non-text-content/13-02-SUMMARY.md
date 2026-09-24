---
phase: 13-per-server-timeouts-the-result-cap-and-non-text-content
plan: 02
subsystem: tools
tags: [mcp, timeouts, config-schema, mcp-21, mcp-22]

# Dependency graph
requires: []
provides:
  - "MCPServerConfig.connect_timeout_s (default 30.0) / call_timeout_s (default 120.0) /
    max_result_chars (default 8000) — each gt=0 validated"
  - "MCPManager.MCPTimeout(TimeoutError) — connect/call overrun, names the server and the
    config field to raise"
  - "MCPManager._call_timeout_for(server) / _max_result_chars_for(server) — the per-server
    lookup order (active launched cfg > configured servers > module default) plan 13-04
    consumes for the result cap"
affects: ["13-04 (consumes _max_result_chars_for for the cap's behaviour)", "13-05", "13-06"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-server budget resolved through MCPManager._server_cfg: the cfg actually passed to
      start_server (self._active_cfg[name]) wins over self.servers.get(name), because the TUI's
      connection-test modal launches an edited cfg before Harness.add_mcp_server stores it"
    - "A single _await_result(server, fut, what) helper shared by call_tool and _on_session so
      the timeout-vs-unavailable precedence (reconnecting always wins, checked before any
      timeout) lives in exactly one place"
    - "A first-connect timeout cancels its own orphaned attempt on the loop thread
      (_abort_launch: cancel the launch future, then cancel the owning _serve task) so a slow
      response arriving after the caller gave up can never mount tools later"

key-files:
  created: []
  modified:
    - src/agent86/config.py
    - src/agent86/tools/mcp_client.py
    - tests/unit/test_config.py
    - tests/unit/test_mcp.py

key-decisions:
  - "Scope of MCP-21 = connect and call timeouts only. _MAX_RECONNECT_ATTEMPTS /
    _RECONNECT_BASE_DELAY_S / _RECONNECT_MAX_DELAY_S stay hardcoded module constants (research
    Open Question 4, read literally: the roadmap says 'connect/call timeouts'); the comment
    above _MAX_RECONNECT_ATTEMPTS was rewritten so it no longer promises MCP-21 will make them
    configurable."
  - "Reconnect attempts inside _serve get no new connect deadline in this phase: SC1 names only
    start_server, call_tool and the capability-tool call path (_on_session). Recorded as a known
    limit for 13-06's docs, not fixed here."
  - "/config mcp gains NO form fields for the three new values (research Open Question 3): they
    are hand-edited TOML for now; config_writer.py needed no change (its dotted-key write path
    is already generic). MCPTestModal.TIMEOUT_S (the TUI connection test's own 30s UI cap) was
    left alone — a different question, pinned by its own tests."
  - "config.py stays read-only: only the three Pydantic fields and their three DEFAULT_MCP_*
    constants were added there; no TOML writing anywhere in this plan."
  - "Per-server lookup order at call time: MCPManager._active_cfg[name] (the cfg actually passed
    to start_server) first, then self.servers.get(name), then the module defaults — because the
    TUI's test modal can launch an edited cfg before Harness.add_mcp_server stores it in
    self.servers, so self.servers alone can be stale."

requirements-completed: [MCP-21]

# Metrics
duration: ~25min
completed: 2026-09-24
---

# Phase 13 Plan 02: Per-server connect/call timeouts + max_result_chars schema Summary

**`MCPServerConfig` gains `connect_timeout_s` (30s default), `call_timeout_s` (120s default) and
`max_result_chars` (8000 default, ADR 0004's schema half); `MCPManager.start_server`, `call_tool`
and every capability-tool call now read the per-server value through a new `MCPTimeout`
exception and a shared `_await_result` helper, replacing the module's last hardcoded 30/120
literals, with the "server is reconnecting" precedence and an orphaned-connect cancel both
proven by test.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 (TDD: config schema RED->GREEN, then wiring-test RED, then wiring GREEN)
- **Files touched:** 4 (`src/agent86/config.py`, `src/agent86/tools/mcp_client.py`,
  `tests/unit/test_config.py`, `tests/unit/test_mcp.py`)

## Scope rulings applied (from the plan's objective — recorded here for the verifier)

1. **MCP-21's scope is connect and call timeouts only.** `_MAX_RECONNECT_ATTEMPTS`,
   `_RECONNECT_BASE_DELAY_S` and `_RECONNECT_MAX_DELAY_S` stay hardcoded module constants in
   `mcp_client.py` — the comment above `_MAX_RECONNECT_ATTEMPTS` was rewritten to say the
   connect/call timeouts (not the reconnect budget) are MCP-21's ruling, and no longer promises
   the reconnect constants will become configurable.
2. **Reconnect attempts inside `_serve` get no new connect deadline this phase.** SC1 names only
   `start_server`, `call_tool` and the capability-tool call path (`_on_session`); a reconnect
   attempt after a mid-session drop is not bounded by `connect_timeout_s`. Recorded as a known
   limit for plan 13-06's docs, not fixed here.
3. **`/config mcp` gains no new form fields.** `connect_timeout_s`, `call_timeout_s` and
   `max_result_chars` are hand-edited TOML for now — `config_writer.py`'s dotted-key write path
   is already generic and needed no change. `tui/screens/mcp_test.py`'s `MCPTestModal.TIMEOUT_S`
   (the connection-test's own 30s UI cap) answers a different question and was left untouched;
   its own tests still pin it, and `start_server`'s explicit `timeout=` keyword (which
   `MCPTestModal` still passes) continues to override the per-server config as before.
4. **Per-server lookup order at call time.** `MCPManager._server_cfg(server)` returns
   `self._active_cfg.get(server) or self.servers.get(server)` — the cfg actually launched wins
   over the configured one, because the TUI's connection-test modal launches an edited cfg
   *before* `Harness.add_mcp_server` stores it in `self.servers`, so `self.servers` alone can be
   stale at that moment. Verified by `test_call_timeout_default_is_120_when_server_unconfigured`.

## Task 1 — `MCPServerConfig` schema (`src/agent86/config.py`, `tests/unit/test_config.py`)

Three new `DEFAULT_MCP_CONNECT_TIMEOUT_S = 30.0` / `DEFAULT_MCP_CALL_TIMEOUT_S = 120.0` /
`DEFAULT_MCP_MAX_RESULT_CHARS = 8_000` module constants above `MCPServerConfig`, and three new
`gt=0`-validated fields (`connect_timeout_s`, `call_timeout_s`, `max_result_chars`) on the model
itself — the pre-MCP-21 hardcoded values become the defaults, and `max_result_chars` lands ADR
0004's ruling (its *behaviour* is plan 13-04's job, not this one's). Four new tests:
`test_mcp_server_config_default_timeouts`, `test_mcp_server_config_max_result_chars_defaults_to_8000`,
`test_mcp_server_config_override_is_per_server` (a `[mcp.servers.slow]`/`[mcp.servers.fast]` TOML
fixture proving the override is per-server, not global) and
`test_mcp_server_config_rejects_non_positive_limits`. `config.py` stayed read-only throughout —
no TOML-writing code was touched.

## Task 2 — RED timeout-wiring tests (`tests/unit/test_mcp.py`)

`_install_fake_transport`'s `_FakeSession` gained `call_tool()` (delegating to the existing
`_answer` dispatcher) and `inspect.isawaitable(value)` handling in `_answer` so a response value
can itself be an `asyncio.sleep(...)` coroutine; `_install_fake_transport` gained an `init_delay`
keyword that makes `initialize()` sleep before returning. Both changes are additive — all 81
pre-existing `test_mcp.py` tests kept passing unmodified. Nine new tests were appended pinning:
a slow `call_tool` timing out into `MCPTimeout` within budget; the timeout message naming the
server, the configured seconds and `call_timeout_s`, and the same wording surfacing through
`MCPTool.run`'s `ToolResult.error`; a slow capability call (`list_prompts`) timing out
identically; the `_call_timeout_for`/`_max_result_chars_for` lookup order (unconfigured ->
default, configured -> its value, launched-but-not-in-`servers` -> the launched cfg's value,
stopped -> back to default); a slow `initialize()` timing out `start_server` into `MCPTimeout`
naming `connect_timeout_s`; an explicit `timeout=` kwarg overriding the configured
`connect_timeout_s`; a timed-out connect leaving no orphaned session/task/tools behind after the
background attempt finally finishes; and a call during the reconnect backoff window still
raising `MCPServerUnavailable` naming "is reconnecting" rather than `MCPTimeout`, even with a
very short `call_timeout_s`. All nine failed RED (`AttributeError: ... has no attribute
'MCPTimeout'`) except the reconnecting-precedence test, which already passed against the
pre-existing "session is None" guard — a valid regression pin, not a false RED.

## Task 3 — Wiring (`src/agent86/tools/mcp_client.py`)

- `MCPTimeout(TimeoutError)` next to `MCPServerUnavailable`, carrying `.server`.
- `MCPManager` gained `self._active_cfg: dict[str, MCPServerConfig]` (set in `start_server`
  right before launching, popped in the failure path and in `stop_server`) plus
  `_server_cfg`/`_call_timeout_for`/`_max_result_chars_for`.
- `start_server(timeout: float | None = None, ...)`: the budget is `timeout if timeout is not
  None else cfg.connect_timeout_s`. On a real timeout (not the transport's own failure) it calls
  the new `_abort_launch(name, fut)` — cancels the `run_coroutine_threadsafe` future and, on the
  loop thread, pops and cancels the owning `_serve` task — before raising `MCPTimeout` naming the
  server, the elapsed budget and `connect_timeout_s`. `_serve`'s `except BaseException` gained a
  guard: if `ready` isn't done and the exception is `asyncio.CancelledError` (the orphaned
  attempt being cancelled, whose `ready` future may already be cancelled via the task's own
  `_fut_waiter` chain), it returns without touching `ready` rather than risking
  `InvalidStateError` from `set_exception` on an already-done future.
- New `_await_result(self, server, fut, what)` is the one place that turns a
  `concurrent.futures.TimeoutError` into `MCPTimeout` (naming `call_timeout_s`) or, if the
  session already looks unavailable, `MCPServerUnavailable` instead — cancelling `fut` either
  way so the request doesn't keep running on the loop. `call_tool` and `_on_session` were
  rewritten to both call it, sharing one precedence rule instead of two independent
  `result(timeout=120)` sites; `_on_session` dropped its now-meaningless `timeout` parameter
  (no caller passed one — verified by grep across `src/` and `tests/`).
- `stop_server` also pops `_active_cfg`.

## Verification

```
pytest tests/unit/test_mcp.py tests/unit/test_config.py -q          # 118 passed
pytest tests/integration/test_mcp_client.py -q                       # 17 passed
pytest tests/tui/test_mcp_test_modal.py -q                           # 8 passed
pytest tests/integration/test_scripting_contract.py -q               # 19 passed
mypy src/agent86                                                     # Success: no issues found in 94 source files
ruff check .                                                         # All checks passed!
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Two RED-phase test lines exceeded the 100-char ruff limit**
- **Found during:** Task 2, pre-Task-3 `ruff check .` pass
- **Issue:** `test_call_timeout_uses_per_server_config` and
  `test_call_timeout_error_names_server_and_field`'s `_install_fake_transport(...)` calls were
  written on one line each, both over 100 characters (E501).
- **Fix:** Reformatted both calls onto multiple lines (no behaviour change).
- **Files modified:** `tests/unit/test_mcp.py`
- **Commit:** Folded into `daeba97` (Task 3's commit; the tests were still RED-authored in Task
  2's commit `9a4e42b` and only reformatted once Task 3's `ruff check .` ran).

### Parallel-execution note (not a deviation in this plan's own files)

This plan ran concurrently with 13-01 (evidence-only) and 13-03 (new files
`src/agent86/tools/mcp_content.py` / `tests/unit/test_mcp_content.py`) in a shared working tree,
per the orchestrator's file-ownership split. Task 1's commit (`a624a0e`) was made without an
explicit pathspec and swept up 13-03's already-staged-but-not-yet-committed
`src/agent86/tools/mcp_content.py` into this plan's commit, because `git commit` with no pathspec
commits the whole index, not just the files this plan added. The orchestrator confirmed the fix
is to leave that commit as-is (no amend/reset, per the no-history-rewrite rule) and to scope every
subsequent commit to an explicit pathspec — Task 2 and Task 3's commits (`9a4e42b`, `daeba97`)
both did so (`git commit ... -- <this-plan's-files-only>`), and no further sweep occurred. No
production code from 13-03 was altered by this plan; only its git-history attribution is
affected.

## Self-Check: PASSED

- FOUND: src/agent86/config.py (DEFAULT_MCP_CONNECT_TIMEOUT_S / DEFAULT_MCP_CALL_TIMEOUT_S /
  DEFAULT_MCP_MAX_RESULT_CHARS + the three MCPServerConfig fields)
- FOUND: src/agent86/tools/mcp_client.py (MCPTimeout, _active_cfg, _server_cfg,
  _call_timeout_for, _max_result_chars_for, _abort_launch, _await_result)
- FOUND: tests/unit/test_config.py (four `test_mcp_server_config_*` tests)
- FOUND: tests/unit/test_mcp.py (nine timeout-wiring tests + the additive helper change)
- FOUND commit a624a0e (Task 1)
- FOUND commit 9a4e42b (Task 2)
- FOUND commit daeba97 (Task 3)
