# Deferred items — Phase 10 (MCP Conformance Audit)

## `ruff format --check .` fails on 74 pre-existing files, unrelated to this phase

**Found during:** Plan 10-05, Task 2 (phase gate: `ruff check . && ruff format --check . && mypy
src/agent86`).

**What's wrong:** `ruff format --check .` (ruff 0.15.21) reports 74 files "would be reformatted"
— all under `tests/tui/` and `tests/unit/`. None of them are files this phase (or plan 10-05)
touched: `tests/unit/test_docs_consistency.py` (this plan's only owned test file) is correctly
formatted and not in the list. `ruff check .` (lint) exits 0 clean — this is a formatter-only
finding, not a lint violation.

**Why it's out of scope:** Every listed file was last modified well before Phase 10 started —
spot-checked two: `tests/tui/test_mcp_manager.py` last touched 2026-09-21 (`10987d2`, Phase 8),
`tests/unit/test_config.py` last touched 2026-09-19 (`0dedc8b`, Phase 7). A sample diff
(`ruff format --diff tests/unit/test_config.py`) shows pure whitespace/line-wrapping changes (a
one-line assertion the formatter now prefers to wrap across three lines, and similar), consistent
with a `ruff` version drift between when those files were last formatted and the `ruff 0.15.21`
installed in this environment today — not a defect this phase introduced. Per the scope boundary
rule ("only auto-fix issues directly caused by the current task's changes"), 74 unrelated files
across two test directories is not auto-fixed here.

**Recorded, not fixed.** A future task (or a dedicated `ruff format .` housekeeping pass) should
reformat the whole tree in one commit, separate from any feature work, so the diff is reviewable
on its own.
