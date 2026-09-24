# Phase 13 — Live evidence: pinned-corpus result sizes and non-text blocks

**Gathered:** 2026-09-24 · **Runner:** throwaway scratchpad scripts (never committed), raw `mcp`
SDK (`ClientSession` + `stdio_client`) — never `agent86.tools.mcp_client.MCPManager` — so
concurrent edits to `mcp_client.py` by plan 13-02 in the shared working tree do not affect this
measurement.
**Environment:** node v22.22.0, npx.cmd 10.9.4, `.venv` Python 3.12.10, `mcp` SDK 2.0.0
(`importlib.metadata.version("mcp")`). `npm view @modelcontextprotocol/server-everything version`
and `npm view @modelcontextprotocol/server-filesystem version` both re-resolved to `2026.8.31`
(re-run 2026-09-24, unchanged from Phase 10's D-11 pin and Phase 11's `11-EVIDENCE.md`
re-verification). `mcp-server-git==2026.8.18` installed into a throwaway scratchpad venv
(`uvx` not installed on this machine, per 13-RESEARCH.md and the audit's own note) via
`python -m venv <scratchpad>/gitvenv` +
`<scratchpad>/gitvenv/Scripts/python.exe -m pip install mcp-server-git==2026.8.18`, launched as
`command=<gitvenv python>`, `args=["-m", "mcp_server_git", "--repository", "C:/Projects/agent86CLI"]`.

**Parallel-execution note:** this repo's working tree is shared with two concurrent executors
(plans 13-02 and 13-03), both committing during this run. `mcp-server-git`'s results
(`git_status`/`git_log`/`git_show`/`git_diff`) therefore reflect whatever commit was `HEAD` at the
moment each call fired — re-running the same script minutes apart produced slightly different
`git_diff`/`git_show` character counts (observed range: `git_diff {target: HEAD~5}` 176,915 →
179,217 chars across three runs) because `HEAD` itself advanced between runs. This does not change
this evidence's conclusion — every recorded run stayed enormously over the 8,000-char cap — and the
table below records the final run's exact numbers as the reference figures.

## Corpus result sizes

| server | tool | arguments | blocks (types) | is_error | chars (today's join) | > 8,000? |
|---|---|---|---|---|---|---|
| server-filesystem@2026.8.31 | `read_text_file` | `{path: "C:/Projects/agent86CLI/src/agent86/tools/mcp_client.py"}` | TextContent | False | 71,167 | **yes** |
| server-filesystem@2026.8.31 | `read_text_file` | `{path: "C:/Projects/agent86CLI/README.md"}` | TextContent | False | 47,415 | **yes** |
| server-filesystem@2026.8.31 | `read_text_file` | `{path: "C:/Projects/agent86CLI/pyproject.toml"}` | TextContent | False | 5,369 | no |
| server-filesystem@2026.8.31 | `directory_tree` | `{path: "C:/Projects/agent86CLI/src/agent86"}` | TextContent | False | 20,149 | **yes** |
| server-filesystem@2026.8.31 | `list_directory` | `{path: "C:/Projects/agent86CLI"}` | TextContent | False | 348 | no |
| server-filesystem@2026.8.31 | `get_file_info` | `{path: "C:/Projects/agent86CLI/README.md"}` | TextContent | False | 263 | no |
| mcp-server-git==2026.8.18 | `git_status` | `{repo_path: "C:/Projects/agent86CLI"}` | TextContent | False | 439 | no |
| mcp-server-git==2026.8.18 | `git_log` | `{repo_path: ..., max_count: 10}` | TextContent | False | 4,507 | no |
| mcp-server-git==2026.8.18 | `git_log` | `{repo_path: ..., max_count: 50}` | TextContent | False | 32,286 | **yes** |
| mcp-server-git==2026.8.18 | `git_show` | `{repo_path: ..., revision: "HEAD"}` | TextContent | False | 9,094 | **yes** |
| mcp-server-git==2026.8.18 | `git_show` | `{repo_path: ..., revision: "HEAD~3"}` | TextContent | False | 4,802 | no |
| mcp-server-git==2026.8.18 | `git_diff` | `{repo_path: ..., target: "HEAD~5"}` | TextContent | False | 179,217 | **yes** |
| server-everything@2026.8.31 | `echo` | `{message: "hi"}` | TextContent | False | 8 | no |
| server-everything@2026.8.31 | `get-env` | `{}` | TextContent | False | 4,995 | no |
| server-everything@2026.8.31 | `get-resource-links` | `{}` | TextContent, ResourceLink×3 | False | 688 | no |
| server-everything@2026.8.31 | `get-resource-reference` | `{resourceId: 1, resourceType: "Text"}` | TextContent, EmbeddedResource, TextContent | False | 336 | no |
| server-everything@2026.8.31 | `get-structured-content` | `{location: "New York"}` | TextContent | False | 54 | no |
| server-everything@2026.8.31 | `get-sum` | `{a: 1, b: 2}` | TextContent | False | 24 | no |
| server-everything@2026.8.31 | `get-tiny-image` | `{}` | TextContent, ImageContent, TextContent | False | 5,514 | no |
| server-everything@2026.8.31 | `gzip-file-as-resource` | `{}` | ResourceLink | False | 188 | no |

**Tool-name/schema notes:** `server-filesystem`'s and `mcp-server-git`'s listed tool names matched
the plan's assumed names exactly (`read_text_file`, `directory_tree`, `list_directory`,
`get_file_info`; `git_status`, `git_log`, `git_show`, `git_diff` — `repo_path`/`target`/`revision`
argument names confirmed via live schema dump). `server-everything@2026.8.31` listed 13 tools
(matching Phase 10's `docs/mcp-conformance-audit-2026-09.md` MCP-07 run exactly); of these,
`trigger-long-running-operation` was excluded per the plan's `trigger-`/`long-running`/`toggle-`
filters, and `toggle-simulated-logging`/`toggle-subscriber-updates` were excluded as `toggle-`
tools; `simulate-research-query` and `get-annotated-message` both declare `required` input
properties and were not called (the plan's rule: "every listed tool whose input schema has no
`required` properties" plus the four explicitly named exceptions). `get-resource-reference`'s
schema takes `{resourceId, resourceType}` (`resourceType` enum-valued: `Text`/`Blob`); called with
`resourceType: "Text"` per the plan's example. `get-structured-content`'s schema requires
`location` (enum: `New York`/`Chicago`/`Los Angeles`, not a free string as a naive guess would
assume) — first attempt with a placeholder string was a soft `is_error: true` tool result (not a
crash), corrected to the enum's first value for the recorded row above.

## Results above 8,000 characters

| server | tool | arguments | chars | narrowing argument available? |
|---|---|---|---|---|
| server-filesystem@2026.8.31 | `read_text_file` | `{path: ".../mcp_client.py"}` | 71,167 | **yes** — `head`/`tail` (line-count limited read; schema confirmed: `head: "first N lines"`, `tail: "last N lines"`) |
| server-filesystem@2026.8.31 | `read_text_file` | `{path: ".../README.md"}` | 47,415 | **yes** — `head`/`tail` (same tool, same schema) |
| server-filesystem@2026.8.31 | `directory_tree` | `{path: ".../src/agent86"}` | 20,149 | **yes** — `excludePatterns` (array of glob patterns to prune the tree; no depth limit, but narrows the result) |
| mcp-server-git==2026.8.18 | `git_log` | `{max_count: 50}` | 32,286 | **yes** — `max_count` (the same call at `max_count: 10` measured 4,507 chars, under the cap — this tool is self-evidently narrowable) |
| mcp-server-git==2026.8.18 | `git_show` | `{revision: "HEAD"}` | 9,094 | **none** — schema is `{repo_path, revision}` only; no head/tail, no context-line limit, no path-scoping argument at all |
| mcp-server-git==2026.8.18 | `git_diff` | `{target: "HEAD~5"}` | 179,217 | **partial** — `context_lines` (default 3) narrows only the unchanged-line padding around each hunk, not the changed lines themselves, which dominate this diff's size; no path-scoping argument exists to restrict the diff to one file |

**No-narrowing note:** `mcp-server-git`'s `git_show` offers no narrowing argument of any kind
(`{repo_path, revision}` is its entire schema) — a large commit's `git_show HEAD` output has no way
to be shrunk except by raising `max_result_chars` for that server. This is the one over-cap tool in
this audit with zero mitigation short of the per-server override itself; it is listed under the
Ruling section's accepted-risk heading below.

## MCP-25 before-evidence: non-text blocks today

Today's `_content_to_text` (`mcp_client.py`, unmodified as of this run — pinned by 13-RESEARCH.md
at lines ~1438-1446) renders any content block with no non-`None` `.text` attribute as `str(chunk)`
— the Python `repr`-style `dataclass`/Pydantic string form, verbatim, joined into the model-facing
text with every other part. Verified against real `server-everything@2026.8.31` calls (not
fake-transport fixtures):

**`get-resource-links` (3× `ResourceLink` blocks):**
```
name='Blob Resource 1' title=None uri='demo://resource/dynamic/blob/1' description='Resource 1: plaintext resource' mime_type='text/plain' size=None icons=None annotations=None meta=None type='resource_link'
```
Base64 present: **no** (a `ResourceLink` carries only a URI pointer, no payload).

**`get-resource-reference` (1× `EmbeddedResource` block, `resource: TextResourceContents`):**
```
type='resource' resource=TextResourceContents(uri='demo://resource/dynamic/text/1', mime_type='text/plain', meta=None, text='Resource 1: This is a plaintext resource created at 2:15:28 PM') annotations=None meta=None
```
Base64 present: **no** (this call's resource type is `Text`, not `Blob`; the resource's own text
is inlined raw into the repr, not base64-encoded).

**`get-tiny-image` (1× `ImageContent` block):**
```
type='image' data='iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAKsGlDQ1BJQ0MgUHJvZmlsZQAASImVlwdUU+kSgOfe9JDQEiIgJfQmSCeAlBBaAAXpYCMkAUKJMRBU7MriClZURLCs6KqIgo0idizYFsWC3QVZBNR1sWDDlXeBQ9jdd9575805c+a7c+efmf+e/z9nLgCdKZDJMlF1gCxpjjwyyI8dn5DIJvUABRiY0kBdIMyWcSMiwgCTUft3+dgGyJC9YzuU69/f/1fREImzhQBIB
```
(300 of 5,449 total repr characters shown.) Base64 present: **yes** — the entire `data` field is a
base64-encoded PNG, inlined verbatim into the model-facing prompt text by today's `str(chunk)`
fallback. This is the literal defect MCP-25 exists to fix: a base64 image blob reaching the prompt.

**`gzip-file-as-resource` (1× `ResourceLink` block):**
```
name='README.md.gz' title=None uri='demo://resource/session/README.md.gz' description=None mime_type='application/gzip' size=None icons=None annotations=None meta=None type='resource_link'
```
Base64 present: **no** (a `ResourceLink` pointer again, no inlined payload).

## Ruling on the 8,000-character default

**6 of 20 recorded corpus calls (30%) exceeded 8,000 characters** with today's uncapped
`_content_to_text` join: two `server-filesystem` `read_text_file` calls, one `directory_tree`
call, and three `mcp-server-git` calls (`git_log` at `max_count: 50`, `git_show HEAD`, `git_diff
HEAD~5`). This is exactly the scenario 13-RESEARCH.md's Pitfall 3 anticipated and the roadmap's
own Risk/constraint text names by tool (`read_text_file` on a large file; `git_diff`/`git_show` on
a big commit) — both are confirmed here, not hypothetical.

Per this plan's pre-committed ruling (objective section, itself derived from ADR 0004): **the
default STILL ships at 8,000 characters.** ADR 0004 already rules that the cap is per-server
(`MCPServerConfig.max_result_chars`), truncates with a visible marker naming the field and the
server, never drops silently, and never raises. The numbers recorded above do not change that
ruling — they confirm the ADR's own stated tradeoff is real and observable: a legitimate corpus
tool (`read_text_file` on this repo's own largest source file, `git_diff` across five commits)
*does* exceed 8,000 characters in ordinary use, and the mitigation ADR 0004 already specifies
(a visible, per-server-overridable marker, not silence) is what makes shipping the small default
acceptable rather than a silent regression.

**Over-cap tools for plan 13-06's README worked example** (each of the six rows in "Results above
8,000 characters" above): `server-filesystem`'s `read_text_file` (narrow with `head`/`tail`) and
`directory_tree` (narrow with `excludePatterns`); `mcp-server-git`'s `git_log` (narrow with
`max_count`), `git_show` (**no narrowing argument** — see Accepted risk), and `git_diff` (narrow
partially with `context_lines`, though the changed-line content itself cannot be trimmed without a
path-scoping argument the tool does not offer). Plan 13-06 should use `mcp-server-git`'s `git_show`
as the worked example's "raise `max_result_chars` for this server" case, since it is the one tool
in this audit with genuinely no other way to fit under the default.

### Accepted risk

`mcp-server-git`'s `git_show {revision}` — schema is `{repo_path, revision}` only, no head/tail, no
context-line limit, no path-scoping argument. A large commit's `git_show HEAD` output (9,094 chars
in this run) has no way to be shrunk except by raising `max_result_chars` for that server. No other
over-cap tool in this audit lacks a narrowing argument entirely.

**Verdict:** complete
