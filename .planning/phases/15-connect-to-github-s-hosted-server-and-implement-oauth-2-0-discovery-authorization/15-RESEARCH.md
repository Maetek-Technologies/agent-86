# Phase 15: Connect to GitHub's hosted server and implement OAuth 2.0 discovery/authorization - Research

**Researched:** 2026-09-25
**Domain:** OAuth 2.0 (RFC 8414/9728/7591 discovery + authorization-code + PKCE) over MCP streamable HTTP, against a real third-party remote MCP server (GitHub's hosted `api.githubcopilot.com/mcp/`)
**Confidence:** HIGH (SDK capability and GitHub's live endpoint behavior are both directly verified — the SDK by reading the installed source, GitHub by live unauthenticated `curl` against the real production endpoint on 2026-09-25 and cross-checked against two independent GitHub-authored sources)

## Summary

The installed `mcp` SDK (2.0.0, confirmed via `pip show mcp`) already ships a **complete**
`OAuthClientProvider(httpx2.Auth)` at `mcp/client/auth/oauth2.py` that implements RFC 9728
protected-resource discovery, RFC 8414 authorization-server metadata discovery (with OIDC and
legacy fallbacks), RFC 7591 dynamic client registration, PKCE (S256), state/CSRF validation, RFC
9207 issuer validation, and automatic refresh — all triggered transparently the first time the
underlying `httpx2.AsyncClient` gets a 401. This is dramatically more than the audit's
`_resolve_server_secrets` gap description implied it would need to build: **this phase is
integration and a redirect/callback UI, not a hand-rolled OAuth implementation.** The hook point
is exactly where the audit's sizing note said it would be: `_streamable_http`
(`mcp_client.py:1694`) builds `create_mcp_http_client(headers=...)` with no `auth=` argument —
adding one turns on the whole flow.

Live probing of `https://api.githubcopilot.com/mcp/` (2026-09-25, unauthenticated `curl`, safe and
read-only) confirms the wire-level shape the SDK expects: a `WWW-Authenticate: Bearer` header
naming a `resource_metadata` URL, real RFC 9728 protected-resource metadata naming
`https://github.com/login/oauth` as the sole authorization server, and real RFC 8414
authorization-server metadata at the exact path-aware well-known URL the SDK's own discovery
builder constructs (`https://github.com/.well-known/oauth-authorization-server/login/oauth`). The
one decisive finding that reshapes the plan: **GitHub's AS metadata carries no
`registration_endpoint`, and a probe POST to the SDK's registration fallback path
(`https://github.com/login/oauth/register`) returns HTML 422, not a JSON client record** — GitHub
does not support RFC 7591 dynamic client registration. This is independently confirmed by GitHub's
own setup docs ("GitHub doesn't support dynamic client registration (DCR) for this server... a
one-time setup step in GitHub first: register a GitHub OAuth App"). The SDK has a clean built-in
escape hatch for this: if `TokenStorage.get_client_info()` returns a pre-built
`OAuthClientInformationFull` (constructed from config, not discovered), the SDK's own auth-flow
code skips its Step-4 registration call entirely and proceeds straight to the authorization
redirect. That is the mechanism this phase should use — no code path needs to attempt
registration against GitHub at all.

GitHub's token endpoint also requires `client_secret` at exchange time even when PKCE parameters
are sent (confirmed against GitHub's own OAuth Apps documentation) — so the pre-built client
record must carry a real secret, which per CLAUDE.md's `api_key_env` rule must be a config
*reference* (an env-var/keyring name), never a literal in TOML.

**Primary recommendation:** Add an `auth = "oauth"` mode to `MCPServerConfig` carrying
`oauth_client_id` (a plain string, not a secret), `oauth_client_secret_env` (a secret reference
resolved exactly like `api_key_env`), `oauth_scopes`, and `oauth_redirect_port`; implement a
minimal in-memory `TokenStorage` whose `get_client_info()` returns that pre-built client record
(skipping DCR) and whose `get_tokens`/`set_tokens` hold the token only in the `MCPManager`
instance's own memory for this phase (MCP-18 swaps in keyring persistence later, same Protocol, no
interface change); implement a `redirect_handler` that opens the system browser
(`webbrowser.open`, lazily imported) and a `callback_handler` that runs a short-lived loopback
HTTP listener on the configured fixed port (GitHub requires an exact registered-URI match, not a
port wildcard); wire `auth=OAuthClientProvider(...)` into `_streamable_http`'s
`create_mcp_http_client` call only when `cfg.auth == "oauth"`. The first plan must be a live spike:
register a real GitHub OAuth App (human action, detailed below) and complete one real
authorization-code round trip against `https://api.githubcopilot.com/mcp/`, listing its tools,
before any of the above is written as production code — exactly as the roadmap's phase entry
requires.

## Project Constraints (from CLAUDE.md)

These apply to every task this phase produces, with the same authority as a locked decision:

- **Lazy imports mandatory.** `webbrowser`, `httpx2`'s OAuth pieces (already lazily reached through
  `mcp.client.auth`), and any new stdlib HTTP-listener code must be imported inside function
  bodies, never at module top level — `run` (one-shot) and `--plain` must not pay for them, and
  they already don't touch `mcp_client.py`'s existing lazy-import boundary (everything MCP-related
  is already behind `from mcp import ...` inside function bodies).
- **API keys/secrets never in config.py-managed TOML.** Only a reference (`api_key_env`-style) may
  be written. `oauth_client_id` is not a secret (GitHub OAuth App client IDs are not
  security-sensitive server-side, matching GitHub's own public documentation of them being visible
  in URLs) and may be a plain config value; `oauth_client_secret_env` must hold a variable *name*,
  resolved via the existing `agent86.secrets.resolve_api_key`/`expand_var_refs` env-then-keyring
  chain — never a literal secret.
- **Tool execution must never raise.** Any OAuth failure (missing app registration, denied
  authorization, expired code, network failure during discovery) must surface as a named,
  actionable error through the existing note/error plumbing (`MCPManager`'s note listeners,
  `describe_start_failure`-style unwrapping), never an unhandled exception reaching the ReAct loop.
- **`config.py` is read-only; write-back goes through `config_writer.py`.** Any new
  `MCPServerConfig` fields this phase adds must be addressable through the existing generic
  leaf-key write path; `oauth_client_secret` as a literal leaf name would already be blocked by
  `_FORBIDDEN_LEAF_KEYS` (`{"api_key","apikey","key","token","secret","password","authorization"}`)
  — naming the field `oauth_client_secret_env` (an `_env`-suffixed reference field, exactly like
  `api_key_env`) avoids that trap by construction rather than needing an exception carved into the
  guard.
- **Windows console / cold start.** No new core dependency; the `mcp` extra stays optional with
  graceful degradation (already the case — everything OAuth-related lives inside `mcp.client.auth`,
  reached only when the `mcp` extra is installed and a server sets `auth = "oauth"`).
- **`run --json` keys stay additive-only.** Any new key surfacing OAuth state (e.g. "awaiting
  authorization") must be additive.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-17 | OAuth 2.0 discovery and authorization for hosted servers. Auth today is `headers` plus `${VAR}` only | The installed `mcp` SDK's `OAuthClientProvider` (verified source read) already implements RFC 8414/9728 discovery and PKCE end to end; live `curl` evidence against `https://api.githubcopilot.com/mcp/` confirms the exact wire shape (WWW-Authenticate → PRM → AS metadata) the SDK's discovery code expects, with real response bodies recorded below for the plan's Wave 0 fixture/mock design. The one gap requiring agent86-side work beyond wiring is DCR's absence on GitHub — solved via a pre-seeded `TokenStorage.get_client_info()` returning a config-built client record, confirmed to skip the SDK's registration call by reading its own source (`oauth2.py:699`: `if not self.context.client_info:`). |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` (already a project extra) | 2.0.0 installed (extra pins `mcp>=1.0`) | `mcp.client.auth.oauth2.OAuthClientProvider`, `mcp.shared.auth.*` models, `mcp.client.streamable_http.create_mcp_http_client` | This *is* the project's existing MCP transport dependency — no new package. The OAuth machinery ships inside it already; nothing to add to `pyproject.toml`. |

**Version verification:** `pip show mcp` in the project venv reports `Version: 2.0.0`,
`Location: C:\Projects\agent86CLI\.venv\Lib\site-packages`, confirming the exact installed build
this research read from. The `mcp` extra in `pyproject.toml` (`mcp = ["mcp>=1.0"]`, line 43) is
unchanged by this phase — 2.0.0 already satisfies it and already carries the OAuth code.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx2` (transitive, via `mcp`) | pinned by `mcp`'s own dependency set | `OAuthClientProvider` subclasses `httpx2.Auth`; `create_mcp_http_client(auth=...)` wires it into the transport's client | Already a transitive dependency of the installed `mcp` package (`pip show mcp` lists it under `Requires`) — nothing new to install. |
| `webbrowser` (stdlib) | n/a | Opens the system default browser for the authorization redirect, interactive TUI/`--plain` paths only | Lazy-imported inside the `redirect_handler` function body, per CLAUDE.md's lazy-import rule; no third-party browser-launch package needed. |
| `http.server` / `asyncio.start_server` (stdlib) | n/a | Loopback callback listener on `127.0.0.1:<fixed port>` to receive the authorization code | Either works; `asyncio`-native is a better fit since the OAuth flow already runs on `MCPManager`'s dedicated background event loop thread (the same thread `_serve`/`_serve_once` already run on) — no new thread needed, matching the existing architecture rather than adding a second concurrency model. |
| `uvicorn` + `starlette` (already transitive via `mcp`, and already used by `tests/integration/live_mcp_server.py`/`test_mcp_live.py`) | already installed (`pip show mcp` lists both under `Requires`) | Building a local mock authorization-server + protected-resource fixture for Wave-0 no-network tests, mirroring the existing `live_server` fixture pattern in `test_mcp_live.py` | Already proven in this codebase for exactly this kind of "spin up a real local ASGI server and drive a real client at it" test — no new dependency, no new pattern to invent. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| The SDK's built-in `OAuthClientProvider` | Hand-rolled discovery/PKCE/token-exchange code | Rejected outright — the SDK's implementation is complete, already imported transitively, and re-implementing RFC 8414/9728/PKCE by hand would violate "no new core dependency... don't hand-roll" in spirit even though it's not a *dependency* question; it is unnecessary and error-prone duplication of code already in the venv. |
| A fixed loopback port from config | A dynamically chosen free port per session | Rejected for the GitHub case specifically: GitHub's OAuth App redirect-URI matching is documented as an **exact match** unless wildcard matching is separately enabled on the app (not confirmed available for OAuth Apps, only referenced generically). A random port would require re-registering the OAuth App's callback URL every run. A fixed, configurable port (`oauth_redirect_port`, sensible default e.g. `8765`) registered once in the GitHub OAuth App matches GitHub's actual constraint. |
| Dynamic client registration | Pre-seeded static client record via `TokenStorage.get_client_info()` | Not a real choice for GitHub — DCR is confirmed unsupported (no `registration_endpoint`, `/register` returns HTML 422). The pre-seeded-storage approach is the SDK-sanctioned way to skip Step 4 without SDK modification, confirmed by reading `oauth2.py`'s own conditional. |

**Installation:** None required — `mcp>=1.0` (already an optional extra) is sufficient; 2.0.0 is
already installed in the project venv and already carries every module this phase needs.

## Architecture Patterns

### Recommended Project Structure

No new top-level module is required. Extend the existing seam:

```
src/agent86/
├── config.py                 # MCPServerConfig gains: auth, oauth_client_id,
│                              #   oauth_client_secret_env, oauth_scopes, oauth_redirect_port
├── secrets.py                 # reused as-is: expand_var_refs/resolve_api_key for
│                              #   oauth_client_secret_env — no new secret-resolution code
└── tools/
    └── mcp_client.py           # _streamable_http gains an optional auth= wiring;
                                 #   new small helper(s) for TokenStorage + redirect/callback
                                 #   handlers, private to this module like _resolve_server_secrets
```

A dedicated `oauth.py` submodule under `tools/` is reasonable if the handler code grows past a
page, but nothing here demands a new package — the existing single-file `mcp_client.py`
convention (1990 lines, already the home for `_resolve_server_secrets`, `_streamable_http`,
`_open_transport`) is where every other transport/secrets concern already lives.

### Pattern 1: OAuth as an opt-in per-server `auth` mode, not a new transport

**What:** `MCPServerConfig` gains `auth: Literal["headers", "oauth"] | None = None` (default
`None`/`"headers"` preserves today's behavior byte-for-byte — no existing config changes
behavior). When `auth == "oauth"` and `transport == "http"` (streamable HTTP; GitHub's only
supported transport per its own capability surface), `_streamable_http` constructs an
`OAuthClientProvider` and passes it as `create_mcp_http_client(headers=..., auth=provider)`.
**When to use:** Any remote server (`sse`/`http` transport) that 401s without a bearer token and
advertises RFC 9728 metadata. Headers-based auth (today's only mode) stays available and unchanged
for servers using a static PAT/API key — GitHub's own docs confirm a PAT-as-bearer-header path
already works today with zero code change (`headers.Authorization = "Bearer ${GITHUB_PAT}"`), so
this phase does not have to force every user through interactive OAuth.
**Example (SDK's own integration point, source-verified):**
```python
# Source: C:\Projects\agent86CLI\.venv\Lib\site-packages\mcp\client\streamable_http.py:640
# and mcp\shared\_httpx_utils.py:23 (installed mcp==2.0.0)
async def _streamable_http(url: str, headers: dict[str, str], auth: "httpx2.Auth | None" = None) -> Any:
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    async with create_mcp_http_client(headers=headers or None, auth=auth) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            yield streams
```

### Pattern 2: Skip dynamic client registration via a pre-seeded `TokenStorage`

**What:** Implement `TokenStorage` (a `Protocol`, not an ABC — no subclassing required) with
`get_client_info()` returning a static `OAuthClientInformationFull` built from
`cfg.oauth_client_id`/the resolved `oauth_client_secret_env` value/`cfg.oauth_scopes`/a
`redirect_uris=[AnyUrl(f"http://127.0.0.1:{cfg.oauth_redirect_port}/callback")]`, with
`token_endpoint_auth_method="client_secret_post"` (GitHub's token endpoint requires the secret in
the POST body or Basic header; `client_secret_post` is the simpler of the two supported methods
and matches what the SDK's `prepare_token_auth` already implements for both).
**When to use:** Any authorization server without a `registration_endpoint` in its RFC 8414
metadata and requiring a pre-registered app — this is GitHub's exact situation and is a common
pattern among vendor-hosted OAuth (GitHub, GitLab, many first-party APIs never adopted RFC 7591).
**Why this works (source-verified control flow):**
```python
# Source: C:\Projects\agent86CLI\.venv\Lib\site-packages\mcp\client\auth\oauth2.py:550-554,
# and :699-743 (installed mcp==2.0.0)
async def _initialize(self) -> None:
    """Load stored tokens and client info."""
    self.context.current_tokens = await self.context.storage.get_tokens()
    self.context.client_info = await self.context.storage.get_client_info()  # <- our pre-seed
    self._initialized = True

# later, inside the 401 handler:
if not self.context.client_info:            # False when storage pre-seeded it — DCR skipped
    ...  # registration_request / handle_registration_response never runs
```

### Pattern 3: Loopback redirect + callback on the MCP manager's own event loop

**What:** `redirect_handler(url: str) -> None` opens the browser (`webbrowser.open(url)`, lazily
imported) or, for a headless/no-display environment, prints the URL for the user to open manually
(this phase does not need to solve headless *authorization completion* — that is MCP-19's job —
but the redirect handler should degrade gracefully to "print the URL" rather than crash when
`webbrowser.open` fails, e.g. no `DISPLAY` on Linux CI). `callback_handler() -> AuthorizationCodeResult`
awaits a one-shot request on a small `asyncio`-native loopback listener bound to
`127.0.0.1:cfg.oauth_redirect_port`, started *before* `redirect_handler` fires so no race exists
between "browser opens" and "listener is ready."
**When to use:** The interactive TUI and `--plain` paths both funnel through the same
`MCPManager` background event loop (Phase 12's existing architecture: one dedicated thread running
its own loop, called into via `run_coroutine_threadsafe`), so this handler pair is written once
and works identically for both surfaces — no TUI-specific vs. plain-specific branching needed at
the OAuth layer itself. Only the *notification* of "authorization needed, check your browser" vs.
"open this URL: ..." needs a surface-specific rendering, and that can reuse the existing
`MCPManager` note-listener push mechanism Phase 12-08 already built (`add_note_listener`,
`server_status()`), so an OAuth-pending state is just another status string, not a new plumbing
layer.
**Constraint:** GitHub's OAuth App redirect URI must be registered as an **exact match**
(confirmed: "Without wildcard matching enabled, the redirect URL must exactly match the callback
URL", GitHub's own authorizing-oauth-apps documentation). `oauth_redirect_port` must therefore be a
fixed, configured value (a sensible default, e.g. `8765`), not chosen freshly per run from an
ephemeral free port — the opposite of the pattern used elsewhere in this codebase for test-only
servers (`_free_port()` in `test_mcp_live.py`), which is a deliberate, documented departure driven
by GitHub's own external constraint, not an oversight.

### Anti-Patterns to Avoid

- **Re-implementing PKCE/discovery by hand:** the SDK already has it; duplicating it risks a subtly
  wrong RFC 8707 `resource` parameter, RFC 9207 `iss` validation, or PKCE verifier — all of which
  the SDK's `OAuthClientProvider` already gets right and this phase gets to inherit for free by
  wiring `auth=`.
- **Writing the access/refresh token to `config.py`-managed TOML or logging it:** the in-memory
  `TokenStorage.set_tokens` must not touch `config_writer.py` at all this phase (MCP-18 adds
  persistence); tokens must never appear in a note, a flight-recorder field, or an exception
  message — the existing `agent86.secrets.redact()` helper (key-shaped-token regex plus explicit
  secret list) is the right place to redact an access token if it ever needs to appear in an error
  string, mirroring how the codebase already treats provider API keys.
- **Assuming a random/ephemeral loopback port works:** GitHub's exact-match redirect-URI rule
  makes this a real footgun, not a style preference — confirmed above.
- **Attempting dynamic client registration against GitHub:** confirmed to fail (HTML 422, not a
  JSON client record) — build the pre-seeded `TokenStorage.get_client_info()` path from the start
  rather than discovering the failure via CI/live-run trial and error.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RFC 8414/9728 metadata discovery, well-known URL fallback chains, OIDC discovery fallback | Custom discovery-URL builder + JSON parsing | `mcp.client.auth.utils.build_protected_resource_metadata_discovery_urls` / `build_oauth_authorization_server_metadata_discovery_urls` (used internally by `OAuthClientProvider`) | Already implements the exact fallback priority (WWW-Authenticate hint → path-based well-known → root well-known) that this research's live GitHub probe exercised and confirmed matches GitHub's real responses. |
| PKCE code_verifier/code_challenge generation | Custom `secrets`/`hashlib` S256 implementation | `mcp.client.auth.oauth2.PKCEParameters.generate()` | Already correct (128-char verifier, SHA-256 + base64url challenge, matches GitHub's "only S256 is accepted" requirement). |
| Token refresh scheduling | Custom expiry-tracking + refresh-before-call logic | `OAuthContext.is_token_valid()` / `can_refresh_token()` + `OAuthClientProvider.async_auth_flow`'s automatic refresh-on-401-then-retry | Refresh is MCP-18's *storage* concern (keyring persistence across restarts), but the *mechanism* (detect expiry, refresh, retry the request) is already built into the SDK's `httpx2.Auth` integration and fires automatically within a single process's lifetime even before MCP-18 lands. |
| CSRF `state` validation, RFC 9207 `iss` validation | Custom redirect-response validation | `OAuthClientProvider._perform_authorization_code_grant`'s built-in `secrets.compare_digest` state check and `validate_authorization_response_iss` | Security-sensitive comparison logic already correct (constant-time compare) — reimplementing invites a timing side-channel or a missed check. |

**Key insight:** This phase's "don't hand-roll" list is unusually short on *new* things to avoid
building, because the SDK already built the hard part. The actual engineering risk in this phase is
**wiring and config-surface design** (where does the client_id/secret/redirect-port config live,
how does a pre-seeded client record skip DCR cleanly, how does the loopback listener share the
MCP manager's existing event loop) — not OAuth protocol correctness, which the SDK already owns.

## Runtime State Inventory

Not applicable — this phase adds new capability (OAuth config fields, an in-memory token store); it
does not rename, refactor, or migrate any existing runtime state. (This section is included per the
research template's trigger rule but the trigger condition — rename/refactor/migration — does not
apply to Phase 15.)

## Common Pitfalls

### Pitfall 1: Assuming DCR will "just work" against GitHub
**What goes wrong:** Wiring `auth=OAuthClientProvider(...)` with no pre-seeded `client_info` and
no `client_metadata_url` (CIMD) will trigger the SDK's Step-4 registration attempt, which POSTs to
`https://github.com/login/oauth/register` and gets back an HTML 422 error page, which
`handle_registration_response` turns into `OAuthRegistrationError` (`status_code not in (200,
201)` branch, `oauth2.py`'s `create_oauth_metadata_request`/registration handler).
**Why it happens:** Most MCP OAuth documentation and examples (including the SDK's own docstrings)
describe DCR as the default happy path, because many demo/spec-reference authorization servers do
support it. GitHub, a real production identity provider that pre-dates MCP by over a decade,
deliberately does not.
**How to avoid:** Pre-seed `TokenStorage.get_client_info()` with a config-built
`OAuthClientInformationFull` from the start (Pattern 2 above); confirm no registration request is
sent as an explicit acceptance criterion (e.g., no request to `*/register` observed in a live or
mocked run).
**Warning signs:** An `OAuthRegistrationError` naming a non-JSON or HTML-shaped response body; a
`422` status code from a registration attempt.

### Pitfall 2: Ephemeral/random loopback ports break GitHub's redirect-URI match
**What goes wrong:** Using `_free_port()`-style ephemeral port selection (the existing pattern in
`tests/integration/test_mcp_live.py`) for the OAuth callback listener means the actual redirect
URI sent in the authorization request never matches what's registered on the GitHub OAuth App,
producing a `redirect_uri_mismatch`-shaped error from GitHub at the authorize step.
**Why it happens:** Ephemeral ports are the idiomatic pattern *elsewhere* in this codebase for
test servers with no external registration constraint; OAuth callback listeners look superficially
similar but have an external, one-time-registered constraint that test servers don't.
**How to avoid:** `oauth_redirect_port` is a fixed config field with a sensible, documented
default; the human setup step registers the GitHub OAuth App's callback URL using that same fixed
port.
**Warning signs:** GitHub's authorize page or callback redirect shows a
"redirect_uri is not associated with this application" error.

### Pitfall 3: Treating the client secret like `headers`' existing `${VAR}` values
**What goes wrong:** Storing the GitHub OAuth App's client secret as a literal string in
`MCPServerConfig.headers` or a new plain string field would put a real credential in
`config.py`-managed TOML, violating CLAUDE.md's hard security rule and this phase's own SC3.
**Why it happens:** `headers` already resolves `${VAR}` references via `_resolve_server_secrets`, so
it's tempting to route the OAuth secret through the same mechanism informally (e.g., a
`headers = {"__oauth_secret__": "${GITHUB_OAUTH_CLIENT_SECRET}"}` hack) rather than a first-class
field.
**How to avoid:** Add a real `oauth_client_secret_env: str | None` field (an *_env-suffixed name*,
exactly mirroring `ProviderConfig.api_key_env`'s existing pattern), resolved via the existing
`agent86.secrets.resolve_api_key(name, name)` at connect time — same precedence, same code path,
no new secret-resolution logic, and no risk of the literal ever reaching TOML because the field
itself never accepts anything but an env-var *name*.
**Warning signs:** A code review or `config_writer.py`'s `_FORBIDDEN_LEAF_KEYS` guard rejecting a
write attempt (a signal the design put a secret-shaped value in the wrong place).

### Pitfall 4: `_streamable_http`'s current signature has no `auth` parameter, and `_open_transport` calls it positionally
**What goes wrong:** A change to `_streamable_http`'s signature without checking every call site
(and the tests that fake it) can silently break other transports or existing tests that construct
fake transports with the current two-argument shape (`(cfg, env_passthrough=None)` is the pattern
already called out in the file's own comments for `_open_transport`, and a parallel concern likely
applies to any test that patches `_streamable_http` directly).
**Why it happens:** The codebase has an established pattern (documented in-line at
`mcp_client.py:1790-1794`) of tests replacing transport-construction functions with bare fakes that
must keep matching signatures exactly.
**How to avoid:** Add `auth` as a keyword-only parameter with a `None` default so every existing
call site and fake stays valid unchanged; grep for `_streamable_http(` call/patch sites before
editing.
**Warning signs:** `mypy`/test failures in files that patch `_streamable_http` for non-OAuth
transport tests.

### Pitfall 5: Assuming SSE transport needs the same OAuth wiring
**What goes wrong:** Spending phase budget generalizing OAuth to the `sse` transport when GitHub
(the only workstream-B corpus target) is streamable-HTTP only, and the conformance matrix already
rates `CAP-TRANSPORTS` (all three transports) as implemented/in with SSE noted as deprecated
relative to the newer protocol revision.
**Why it happens:** Symmetry instinct — "if HTTP gets `auth=`, SSE should too."
**How to avoid:** Scope this phase's `auth=` wiring to `_streamable_http` only, per the phase's own
named target (`https://api.githubcopilot.com/mcp/` is streamable HTTP); note SSE OAuth as an
explicit non-goal for this phase's own scope statement if the plan wants to record it, rather than
silently expanding scope.
**Warning signs:** Plan tasks touching `sse_client(...)` call sites with no corpus server or
requirement driving it.

## Code Examples

### GitHub's real 401 response (live-verified 2026-09-25, unauthenticated POST)
```
$ curl -s -i -X POST https://api.githubcopilot.com/mcp/ -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer error="invalid_request", error_description="No access token was provided in this request", resource_metadata="https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp/"
...
bad request: missing required Authorization header
```

### GitHub's real RFC 9728 protected-resource metadata (live-verified 2026-09-25)
```
$ curl -s https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp/
{"resource":"https://api.githubcopilot.com/mcp/","authorization_servers":["https://github.com/login/oauth"],"scopes_supported":["repo","read:org","read:user","user:email","read:packages","write:packages","read:project","project","gist","notifications"],"bearer_methods_supported":["header"],"resource_name":"GitHub MCP Server"}
```

### GitHub's real RFC 8414 authorization-server metadata (live-verified 2026-09-25)
```
$ curl -s https://github.com/.well-known/oauth-authorization-server/login/oauth
{"issuer":"https://github.com/login/oauth","authorization_endpoint":"https://github.com/login/oauth/authorize","token_endpoint":"https://github.com/login/oauth/access_token","response_types_supported":["code"],"grant_types_supported":["authorization_code","refresh_token","urn:ietf:params:oauth:grant-type:device_code"],"service_documentation":"https://docs.github.com/apps/creating-github-apps/registering-a-github-app/registering-a-github-app","code_challenge_methods_supported":["S256"],"device_authorization_endpoint":"https://github.com/login/device/code","authorization_response_iss_parameter_supported":true,"scopes_supported":["offline_access"]}
```
Note: **no `registration_endpoint` key** — this is the direct evidence backing Pitfall 1 and
Pattern 2 above.

### GitHub's `/register` probe (live-verified 2026-09-25 — confirms DCR is unsupported)
```
$ curl -s -i -X POST https://github.com/login/oauth/register
HTTP/1.1 422 Unprocessable Entity
Content-Type: text/html; charset=utf-8
...
```
An HTML error page, not a JSON client-information response — `handle_registration_response` in the
installed SDK (`mcp/client/auth/utils.py`) would raise `OAuthRegistrationError` on this response
(status not in `{200, 201}`).

### The TokenStorage Protocol this phase must implement (source, installed mcp==2.0.0)
```python
# Source: C:\Projects\agent86CLI\.venv\Lib\site-packages\mcp\client\auth\oauth2.py:127-144
class TokenStorage(Protocol):
    """Protocol for token storage implementations."""

    async def get_tokens(self) -> OAuthToken | None: ...
    async def set_tokens(self, tokens: OAuthToken) -> None: ...
    async def get_client_info(self) -> OAuthClientInformationFull | None: ...
    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None: ...
```
No built-in in-memory implementation ships with the SDK — agent86 must write one (small: four
async methods over a couple of instance attributes). This phase's implementation holds state only
for the `MCPManager` instance's lifetime; MCP-18 replaces the body with keyring-backed persistence
without changing the Protocol or any caller.

### Existing hook point that needs one new keyword argument (current code, unmodified)
```python
# Source: C:\Projects\agent86CLI\src\agent86\tools\mcp_client.py:1693-1707 (as of Phase 14)
@asynccontextmanager
async def _streamable_http(url: str, headers: dict[str, str]) -> Any:
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    async with create_mcp_http_client(headers=headers or None) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            yield streams
```
`create_mcp_http_client` already accepts `auth: httpx2.Auth | None = None`
(`mcp/shared/_httpx_utils.py:23-27`) — the only change needed here is threading an optional `auth`
parameter through and constructing an `OAuthClientProvider` when `cfg.auth == "oauth"`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| MCP auth as ad hoc bearer headers only (`_resolve_server_secrets`'s `headers` + `${VAR}`) | MCP spec's own OAuth 2.1-aligned authorization flow (RFC 8414/9728/7591 discovery, PKCE mandatory) built into the SDK's transport layer | The MCP authorization spec matured well before this SDK's 2.x line; agent86 simply hadn't wired it in yet (confirmed absent by the Phase 10 audit: `_resolve_server_secrets` at the time supported only `headers`+`${VAR}`) | This phase closes that gap by wiring existing SDK capability rather than building new protocol logic — the "state of the art" shift already happened in the dependency; agent86's own catch-up is the whole of this phase's engineering work. |
| Assuming every OAuth-capable MCP server supports Dynamic Client Registration | Real-world hosted servers (GitHub confirmed here; likely others) require a pre-registered app because DCR wasn't part of their pre-existing identity infrastructure | Observed directly against GitHub's production endpoint, 2026-09-25 | The plan must design for the pre-seeded-`client_info` path from the start, not as a later fallback. |

**Deprecated/outdated:** None specific to this phase's dependencies — `mcp==2.0.0` is current per
`pip show mcp` and the project's own conformance-matrix protocol-revision pin (`2025-11-25`,
`docs/mcp-conformance-matrix.md`), unrelated to this phase's OAuth scope.

## Open Questions

1. **Does GitHub's OAuth App/GitHub App distinction matter for this phase?**
   - What we know: GitHub offers two registrable application types — "OAuth Apps" (classic,
     simpler, org-wide) and "GitHub Apps" (installable, fine-grained permissions). The AS metadata
     and token/authorize endpoints observed above (`github.com/login/oauth/...`) are the classic
     OAuth App / user-to-server flow; GitHub's docs reference "GitHub App" registration too in the
     device-flow context but the flow this phase targets (browser authorization-code + PKCE) is the
     OAuth App path per the documentation fetched.
   - What's unclear: Whether GitHub's hosted MCP server's scope list (`repo`, `read:org`, etc. —
     classic OAuth scopes, not GitHub App permissions) *requires* an OAuth App specifically, or
     whether a GitHub App configured for user-to-server "Device and OAuth" auth would also work
     with the same endpoints. The scopes returned by the live PRM probe are classic OAuth scope
     names, which points toward an OAuth App being the correct registration type.
   - Recommendation: The plan's Wave 0 human-setup spike should register a classic **GitHub OAuth
     App** (Settings → Developer settings → OAuth Apps → New OAuth App) as the primary path, since
     the scope names returned by the live probe match that registration type; confirm this works
     end-to-end before considering a GitHub App as an alternative.

2. **Exact redirect-URI wildcard behavior for OAuth Apps.**
   - What we know: GitHub's docs state redirect URI matching is exact "without wildcard matching
     enabled" and that wildcard matching is "optional" and "allows subdomains/subdirectories" —
     phrased in terms of hostname/path wildcards, not port wildcards, and the fetched summary
     doesn't confirm whether OAuth Apps (vs. GitHub Apps) even expose a wildcard-matching toggle in
     their settings UI.
   - What's unclear: Whether a single registered `http://127.0.0.1:8765/callback` needs to be exact
     down to the port, or whether GitHub loosens loopback matching in the RFC 8252 sense (any port
     on 127.0.0.1). Not confirmed either way by anything fetched.
   - Recommendation: Treat the port as exact-match (the conservative assumption) — fix
     `oauth_redirect_port` in config and register that literal callback URL. If the Wave 0 human
     spike finds GitHub actually tolerates a floating port, that's a welcome, documented relaxation
     discovered during the spike, not something to assume going in.

3. **Should `oauth_scopes` default to anything, or must the user always specify them?**
   - What we know: The live PRM probe lists GitHub's full supported scope set (`repo`, `read:org`,
     `read:user`, `user:email`, `read:packages`, `write:packages`, `read:project`, `project`,
     `gist`, `notifications`); requesting none/empty would presumably grant whatever GitHub treats
     as a scope-less default (typically minimal/public-only access for classic OAuth Apps).
   - What's unclear: Whether GitHub's *MCP server specifically* requires a minimum scope set to
     answer `tools/list` usefully (e.g., without `repo` many GitHub MCP tools would 403 on real
     calls, even though `initialize`/`tools/list` itself might succeed).
   - Recommendation: The Wave 0 spike should record which scopes were actually granted/needed to
     list and successfully call at least one real tool, and that finding should set the config
     field's documented default (not necessarily "all of them" — least-privilege is the safer
     default per the project's general security posture, but the exact minimal set needs the live
     spike's evidence, not a guess).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `mcp` extra (SDK) | `OAuthClientProvider`, `create_mcp_http_client`, streamable-HTTP transport | ✓ | 2.0.0 (`.venv/Lib/site-packages`) | none needed — already installed in this project's venv |
| `httpx2` | `OAuthClientProvider(httpx2.Auth)` base class | ✓ (transitive via `mcp`) | pinned by `mcp`'s own requirements | none needed |
| `uvicorn` + `starlette` | Wave-0 local mock AS/PRM fixture, mirroring `test_mcp_live.py`'s existing `live_server` pattern | ✓ (transitive via `mcp`) | already used by `tests/integration/test_mcp_live.py` | none needed |
| Network access to `api.githubcopilot.com` / `github.com` | The live-evidence spike (roadmap's own requirement: "first plan must make the live GitHub connection the audit never made") | ✓ (confirmed by this research's own live `curl` probes, 2026-09-25) | n/a (live product endpoint, no version) | If network access is unavailable in the actual execution environment, the spike cannot substitute a mock for GitHub itself — the roadmap explicitly requires the *real* connection; a mock only covers the Wave-0 no-network CI test layer, not SC1/SC2 |
| A registered GitHub OAuth App with a real `client_id`/`client_secret` | The entire authorization-code flow, including the Wave-0 human spike | ✗ (confirmed absent — Phase 10's audit explicitly recorded "no GitHub OAuth app or credentials exist in this environment", and nothing in this research changes that) | n/a | **No fallback** — this is the named human action the phase's first plan must perform before any implementation is written (see "Human setup" below) |
| A registered GitHub OAuth App with a real `client_id`/`client_secret` | GitHub App-only "PAT-as-bearer" already works today | n/a | n/a | ✓ **Fallback available today, code-unchanged**: `headers = {"Authorization": "Bearer ${GITHUB_PAT}"}` against `https://api.githubcopilot.com/mcp/` already works via the existing `_resolve_server_secrets` `${VAR}` mechanism — confirmed by GitHub's own VS Code setup docs ("Add a new header... `Bearer YOUR_GITHUB_PAT`"). This is a legitimate stopgap if the OAuth App registration step is delayed, but does not satisfy SC1 (RFC 8414/9728 discovery + authorization-code flow) — it only satisfies SC2 in isolation. |

**Missing dependencies with no fallback:**
- A registered GitHub OAuth App (`client_id` + `client_secret`) — must be created by a human before
  this phase's first plan can produce live evidence. See "Human setup" below for the exact steps.

**Missing dependencies with fallback:**
- None beyond the OAuth App itself — every library dependency this phase needs is already
  installed in the project's venv today.

### Human setup: what a person must do before this phase's first plan can run live

1. Sign in to GitHub, go to **Settings → Developer settings → OAuth Apps → New OAuth App**
   (classic OAuth App, not a GitHub App — see Open Question 1 for why).
2. **Application name:** anything identifying, e.g. `agent86 (local dev)`.
3. **Homepage URL:** any valid URL (e.g. `https://github.com/<user>/agent86CLI`) — GitHub requires
   one but it is not used by the flow.
4. **Authorization callback URL:** `http://127.0.0.1:8765/callback` (or whatever fixed
   `oauth_redirect_port` the plan settles on) — must be entered **exactly**, matching what agent86
   will send as `redirect_uri`.
5. Register the app; GitHub issues a **Client ID** immediately (visible on the app's settings page)
   and lets the user **Generate a new client secret** (shown once — must be captured immediately).
6. Store the client secret somewhere `agent86.secrets.resolve_api_key` can find it — an environment
   variable (e.g. `GITHUB_OAUTH_CLIENT_SECRET`) for the simplest Wave-0 spike, or the OS keyring
   under service `"agent86"` / account `GITHUB_OAUTH_CLIENT_SECRET` (mirroring the existing
   `resolve_api_key`/keyring account-naming convention) for a more production-like setup.
7. Configure an MCP server entry in agent86 pointing `url = "https://api.githubcopilot.com/mcp/"`,
   `transport = "http"`, `auth = "oauth"`, `oauth_client_id = "<the Client ID from step 5>"`,
   `oauth_client_secret_env = "GITHUB_OAUTH_CLIENT_SECRET"`, `oauth_redirect_port = 8765` (once
   those fields exist — this step happens after the config-surface task, not before).
8. Run the connection: agent86 opens the browser to `github.com/login/oauth/authorize`, the human
   signs in/approves, GitHub redirects to the loopback listener, agent86 exchanges the code for a
   token, and `tools/list` should return GitHub's real MCP tool set.

This sequence is exactly the "first plan must begin by [connecting to GitHub's hosted server]
before any implementation is written" constraint the roadmap names — steps 1-6 are pure human
action with no agent86 code required; step 7-8 need at minimum the config fields and the
`_streamable_http`/`TokenStorage` wiring described above, which is why the roadmap frames this as
"first plan," not "task zero of a later plan."

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (existing project standard) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) — no new config needed |
| Quick run command | `pytest tests/unit/test_mcp.py -q` (existing unit suite for `mcp_client.py`) plus a new `tests/unit/test_mcp_oauth.py` this phase adds |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-17 (SC1: RFC 8414/9728 discovery + interactive authorization-code flow) | `_streamable_http`/`OAuthClientProvider` wiring completes discovery and authorization against a **local mock** AS + protected resource (no network, CI-safe) | integration | `pytest tests/integration/test_mcp_oauth.py -q` | ❌ Wave 0 — new fixture (mock PRM/AS/token endpoints via `uvicorn`/`starlette`, mirroring `live_mcp_server.py`'s existing pattern) and new test file |
| MCP-17 (SC1/SC2, live) | A real authorization-code round trip against `https://api.githubcopilot.com/mcp/` lists real tools | manual-only (human browser interaction; not CI-automatable per this project's own network-free CI constraint, D-03-equivalent) | scratchpad script, recorded in `15-EVIDENCE.md`, per this phase's precedent (`11-EVIDENCE.md`, `13-EVIDENCE.md`) | n/a — evidence document, not a pytest file |
| MCP-17 (SC3: no credential in TOML) | `oauth_client_secret_env` round-trips as a reference only; `config_writer.py`'s `_FORBIDDEN_LEAF_KEYS` still rejects a literal secret under any OAuth-related leaf key | unit | `pytest tests/unit/test_config_writer.py -q` (extend existing file) | ✅ file exists — extend with OAuth-field cases |
| DCR-skip behavior (Pitfall 1) | No request to `*/register` is ever sent against a server whose `TokenStorage.get_client_info()` pre-seeds a client record | unit | `pytest tests/unit/test_mcp_oauth.py -q` (new) | ❌ Wave 0 |
| Token never logged/noted in plaintext | An access token never appears in a `MCPManager` note, error message, or (if reachable) the flight recorder | unit | `pytest tests/unit/test_mcp_oauth.py -q` (new) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/test_mcp.py tests/unit/test_mcp_oauth.py -q`
- **Per wave merge:** `pytest tests/unit/ tests/integration/test_mcp_client.py tests/integration/test_mcp_oauth.py -q`
- **Phase gate:** Full suite green (`pytest -q`) before `/gsd:verify-work`, plus the live-evidence
  document (`15-EVIDENCE.md`) recording the real GitHub round trip per this phase's own SC1/SC2,
  matching the precedent set by `11-EVIDENCE.md`/`13-EVIDENCE.md`/`14-EVIDENCE.md`.

### Wave 0 Gaps
- [ ] `tests/integration/test_mcp_oauth.py` — a local mock authorization-server + protected-resource
  fixture (uvicorn/starlette, following `live_mcp_server.py`'s existing pattern) driving
  `MCPManager`'s new OAuth wiring end-to-end with no network — covers discovery, the DCR-skip path,
  PKCE round trip, and token storage, entirely offline and CI-safe.
- [ ] `tests/unit/test_mcp_oauth.py` — unit-level coverage of the new `TokenStorage` implementation,
  the pre-seeded `get_client_info()` behavior, the `_streamable_http` `auth=` wiring, and the
  redirect/callback handler pair (with a fake/short-circuited browser open and a fake callback
  delivery, not a real loopback listener, for speed).
- [ ] The human GitHub OAuth App registration (see "Human setup" above) — not a test file, but a
  hard precondition for the phase's own live-evidence requirement; must happen before or during
  this phase's first plan, exactly as the roadmap's "first plan must begin by doing so" instructs.
- [ ] Framework install: none — `pytest`, `pytest-asyncio`, `uvicorn`, `starlette` are all already
  present in the dev/`mcp`-extra environment.

## Sources

### Primary (HIGH confidence)
- Installed `mcp` SDK source, read directly: `mcp/client/auth/oauth2.py`, `mcp/client/auth/utils.py`,
  `mcp/shared/auth.py`, `mcp/shared/auth_utils.py`, `mcp/client/streamable_http.py`,
  `mcp/shared/_httpx_utils.py` (all at `C:\Projects\agent86CLI\.venv\Lib\site-packages\mcp\`,
  version 2.0.0 per `pip show mcp`) — read 2026-09-25.
- Live unauthenticated `curl` probes against `https://api.githubcopilot.com/mcp/`,
  `https://api.githubcopilot.com/.well-known/oauth-protected-resource/mcp/`,
  `https://github.com/.well-known/oauth-authorization-server/login/oauth`,
  `https://github.com/login/oauth/.well-known/openid-configuration`, and
  `https://github.com/login/oauth/register` — run 2026-09-25, real production responses recorded
  verbatim above.
- Project source: `src/agent86/tools/mcp_client.py`, `src/agent86/config.py`,
  `src/agent86/secrets.py`, `src/agent86/config_writer.py`,
  `tests/integration/test_mcp_live.py`, `src/agent86/tui/screens/mcp_test.py` — read 2026-09-25.
- `docs/mcp-conformance-audit-2026-09.md`, `docs/mcp-conformance-matrix.md`, `.planning/ROADMAP.md`,
  `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — this project's own prior audit/planning
  artifacts, read 2026-09-25.

### Secondary (MEDIUM confidence)
- GitHub Docs, "Setting up the GitHub MCP server"
  (docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/set-up-the-github-mcp-server)
  — confirms DCR unsupported, PAT-as-bearer fallback, VS Code's built-in OAuth app; fetched via
  WebFetch 2026-09-25.
- GitHub Docs, "Authorizing OAuth Apps"
  (docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps) — confirms
  `client_secret` required at token exchange even with PKCE, loopback redirect URIs allowed,
  exact-match redirect-URI rule; fetched via WebFetch 2026-09-25.
- GitHub Changelog, "PKCE support for OAuth and GitHub App authentication" (2025-07-14)
  (github.blog/changelog/2025-07-14-pkce-support-for-oauth-and-github-app-authentication/) —
  confirms PKCE (S256 only) added, not yet mandatory; fetched via WebFetch 2026-09-25.

### Tertiary (LOW confidence)
- None — every substantive claim above is backed by either the installed SDK's own source, a live
  probe of the real GitHub production endpoint, or an official GitHub documentation page fetched
  directly.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — the exact installed SDK version was read directly; no version ambiguity.
- Architecture: HIGH — every integration point (`_streamable_http`, `TokenStorage` Protocol,
  `create_mcp_http_client`'s `auth=` parameter) is quoted from the installed source, not inferred
  from documentation.
- Pitfalls: HIGH for GitHub-specific findings (DCR absence, client-secret requirement, exact
  redirect-URI matching) — all independently confirmed by both a live probe and official GitHub
  documentation. MEDIUM for the redirect-URI port-wildcard question (Open Question 2) — genuinely
  unconfirmed either way.

**Research date:** 2026-09-25
**Valid until:** 30 days for the SDK-source findings (stable once a specific installed version is
pinned); GitHub's own endpoint behavior should be considered valid until re-verified at
implementation time, since it is a live product GitHub can change unilaterally (the audit's own D-02
already makes this point about GitHub's hosted server generally) — if this phase's execution is
delayed by more than a few weeks, re-run the `curl` probes above before trusting the recorded
response bodies verbatim.
