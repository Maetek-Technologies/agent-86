---
phase: 15
slug: connect-to-github-s-hosted-server-and-implement-oauth-2-0-discovery-authorization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-09-25
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — no new config needed |
| **Quick run command** | `pytest tests/unit/test_mcp.py tests/unit/test_mcp_oauth.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~60 seconds (quick), several minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_mcp.py tests/unit/test_mcp_oauth.py -q`
- **After every plan wave:** Run `pytest tests/unit/ tests/integration/test_mcp_client.py tests/integration/test_mcp_oauth.py -q`
- **Before `/gsd:verify-work`:** Full suite must be green, and `15-EVIDENCE.md` records the live GitHub round trip
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled in by the planner/executor once plan task IDs exist. Requirement-level map (from 15-RESEARCH.md):

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| MCP-17 SC1 (offline) | Discovery (RFC 9728 → RFC 8414) + authorization-code + PKCE against a local mock AS/protected resource | integration | `pytest tests/integration/test_mcp_oauth.py -q` | ❌ W0 | ⬜ pending |
| MCP-17 SC3 | `oauth_client_secret_env` is a reference only; `_FORBIDDEN_LEAF_KEYS` rejects a literal secret | unit | `pytest tests/unit/test_config_writer.py -q` | ✅ extend | ⬜ pending |
| MCP-17 (DCR skip) | No `/register` request when `TokenStorage.get_client_info()` pre-seeds a client | unit | `pytest tests/unit/test_mcp_oauth.py -q` | ❌ W0 | ⬜ pending |
| MCP-17 (no token leak) | Access token never appears in a note, error, or flight-recorder event | unit | `pytest tests/unit/test_mcp_oauth.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/integration/test_mcp_oauth.py` — local mock AS + protected-resource fixture (uvicorn/starlette, following `live_mcp_server.py`'s pattern), offline and CI-safe
- [ ] `tests/unit/test_mcp_oauth.py` — TokenStorage, pre-seeded client info, `_streamable_http` `auth=` wiring, redirect/callback handlers with a faked browser and callback
- [ ] Human GitHub OAuth App registration (see 15-RESEARCH.md "Human setup") — precondition for the live evidence
- [ ] Framework install: none — pytest, pytest-asyncio, uvicorn, starlette already present

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real authorization-code round trip against `https://api.githubcopilot.com/mcp/` lists real tools | MCP-17 SC1/SC2 | Needs a human browser sign-in and a registered GitHub OAuth App; CI is network-free | Run the live script, sign in via browser, record discovery responses, tool count and names in `15-EVIDENCE.md` (token redacted) |
| No credential written to TOML during the live flow | MCP-17 SC3 | Confirms the real flow, not only the unit guard | After the live run, grep user/project config TOML for the token and client secret — expect no match |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
