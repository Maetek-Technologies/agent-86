# Quick Task 261009-rh9: Discover OpenRouter model context window

**One-liner:** `context_window_for` now asks OpenRouter's `/models` for `context_length` (memo + 24h disk cache, 3s timeout, silent fallback) after `[model.context_window]` overrides and before provider rules and the name table.

## Commits
- 92ee395: feat - remote_windows.py, catalog fetcher, capabilities wiring, conftest fixture, tests
- 3845194: docs - ARCHITECTURE.md, README.md, CHANGELOG.md

## Files
- Created: `src/agent86/cognitive/remote_windows.py`, `tests/unit/test_remote_windows.py`
- Modified: `cognitive/catalog.py` (`fetch_openai_compatible_context_lengths`, `_get_json` timeout kwarg), `cognitive/capabilities.py`, `tests/conftest.py` (autouse offline fixture), `tests/unit/test_capabilities.py`, docs

## Verification
- Full pytest: 1231 passed, 16 skipped, 1 failed (`tests/tui/test_banner.py::test_compact_banner_is_the_identity_core_only`, pre-existing: fails identically on the commit before this task).
- ruff check: clean. mypy src/agent86: clean (94 files).
- `ruff format --check .`: 68 files would be reformatted, all pre-existing; files touched by this task were formatted.
- Importing `capabilities` pulls in no httpx/catalog/keyring.

## Deviations
- [Rule 3] A bulk `ruff format src` reformatted unrelated files; reverted them. Only my files were committed (formatting touched a few adjacent pre-existing lines in capabilities.py, catalog.py, test_capabilities.py).
- `ruff format --check .` was not clean before this task, so the plan's "passes" criterion could not be met repo-wide.

## Known Stubs
None.

## Self-Check: PASSED
