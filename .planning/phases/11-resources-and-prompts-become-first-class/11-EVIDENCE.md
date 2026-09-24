# Phase 11 — Live evidence for roadmap success criteria 1 and 2

**Gathered:** 2026-09-24 · **Runner:** throwaway scratchpad scripts, never committed (Phase 10, D-03)
**Environment:** node v22.22.0, npx.cmd 10.9.4, .venv Python 3.12.10, mcp 2.0.0

## SC1 — server-filesystem: list_resources then read_resource

**Package version resolved:** @modelcontextprotocol/server-filesystem@2026.8.31 (`npm view
@modelcontextprotocol/server-filesystem version` re-run 2026-09-24, confirms the D-11 pin
unchanged)

**Command:** `npx.cmd -y @modelcontextprotocol/server-filesystem@2026.8.31 <scratchpad sc1 dir>`,
driven through `agent86.tools.mcp_client.MCPManager.start_server("files", cfg, timeout=180.0)`
against a scratchpad directory `sc1` containing one file, `hello.txt`, with content
`phase-11 resource evidence`.

**Tool names agent86 mounted:**
```
mcp__files__create_directory
mcp__files__directory_tree
mcp__files__edit_file
mcp__files__get_file_info
mcp__files__list_allowed_directories
mcp__files__list_directory
mcp__files__list_directory_with_sizes
mcp__files__move_file
mcp__files__read_file
mcp__files__read_media_file
mcp__files__read_multiple_files
mcp__files__read_text_file
mcp__files__search_files
mcp__files__write_file
```
Fourteen `tools/*` tools only. **No `mcp__files__list_resources` / `read_resource` /
`list_resource_templates` tools were mounted at all** — see "Capability declarations observed"
below for why: this server never declares the `resources` capability, so `_capability_tools`
correctly offers none of the five resource tools for it.

**`server_capabilities` observed** (the exact object `_capability_tools` gates on):
```
experimental=None logging=None prompts=None resources=None tools=ToolsCapability(list_changed=True) completions=None extensions=None tasks=None
```
`resources=None` — this server does not implement the MCP resources capability in the currently
published `@2026.8.31` release.

**list_resources output:** not applicable via the synthetic tool (never mounted, per the capability
gate above). Called directly through `MCPManager.list_resources("files")` for evidence purposes,
bypassing the tool-mounting gate to test the raw session:
```
LIST_RESOURCES ERROR: MCPError(-32601, 'Method not found', None)
```

**list_resource_templates output:** same direct-session probe:
```
TEMPLATES ERROR: MCPError(-32601, 'Method not found', None)
```

**read_resource(\<uri\>) output:** not reachable — `list_resources` never returned a URI to read,
because the server has no `resources/list` handler (JSON-RPC method not found, not an empty list).
As a fallback probe (not the roadmap's literal `resources/read` mechanism, but answering the
underlying question "does the file's text reach the caller through agent86 at all"), the file was
read through the server's actual surface, `read_text_file`, called via
`MCPManager.call_tool("files", "read_text_file", {"path": "<sc1 dir>\\hello.txt"})`:
```
READ_TEXT_FILE fallback: 'phase-11 resource evidence'
```
The file's exact text reaches the caller — through `tools/read_text_file`, not through
`resources/read`, because this server exposes no `resources/read` at all.

**Verdict:** SC1 **not met** as literally worded (a `list_resources` → `read_resource` round trip
against the live, pinned `server-filesystem@2026.8.31`) — this package declares no `resources`
capability at `initialize()` and answers both `resources/list` and `resources/templates/list` with
JSON-RPC `-32601 Method not found`; file content is exposed exclusively through its `tools/*`
surface (`read_text_file`, `read_file`, `read_multiple_files`), and the file's exact text
(`phase-11 resource evidence`) does reach the caller through that surface. `CAP-RESOURCES` and
`CAP-RESOURCE-TEMPLATES` are therefore evidenced by the CI fixture's real stdio round trip alone
(plan 11-02's `test_list_resources_then_read_resource_round_trip`, against
`tests/integration/live_mcp_server.py`) for this pinned corpus, not by a live `server-filesystem`
run — see "Deviations and findings" below.

## SC2 — server-everything: list_prompts, get_prompt, complete

**Package version resolved:** @modelcontextprotocol/server-everything@2026.8.31 (`npm view
@modelcontextprotocol/server-everything version` re-run 2026-09-24, confirms the D-11 pin
unchanged)

**Prompt count:** 4 (the roadmap expects 3 — the currently published package returns one more than
the roadmap's own text anticipated; recorded as observed, not corrected to match the roadmap)

**Prompt names:**
```
simple-prompt        (none)
args-prompt           city*, state
completable-prompt    department*, name*
resource-prompt       resourceType*, resourceId*
```
(`*` = required argument, as rendered by `_prompts_to_text`)

**Prompt with a completable argument:** `completable-prompt`, argument `department`
<- this answers 11-RESEARCH.md Open Question 2

`resource-prompt`'s `resourceType` argument is also completable (values `Text`/`Blob`, see below),
but `completable-prompt`/`department` was the first one found while iterating prompts in the order
`list_prompts` returned them, matching the plan's instruction to iterate "until one returns a
non-empty suggestion list".

**get_prompt output, one call per observed prompt name and argument set:**
```
get_prompt("simple-prompt", {}):
[user]: This is a simple prompt without arguments.
metadata == {"prompt": "simple-prompt"}

get_prompt("args-prompt", {"city": "example", "state": "example"}):
[user]: What's weather in example, example?
metadata == {"prompt": "args-prompt"}

get_prompt("completable-prompt", {"department": "example", "name": "example"}):
[user]: Please promote example to the head of the example team.
metadata == {"prompt": "completable-prompt"}

get_prompt("resource-prompt", {"resourceType": "example", "resourceId": "example"}):
MCPError(-32603, "Invalid resourceType: example. Must be Text or Blob.", None)
```
The fourth call's failure is the server validating its own enum-like argument (`resourceType` must
be `Text` or `Blob`) against the placeholder value `"example"` this script supplied — not a defect
in agent86's `get_prompt` call site. `MCPGetPromptTool.execute`'s try/except converts this into a
soft `ToolResult` error rather than raising into the loop (same pattern
`test_read_resource_failure_is_a_soft_tool_result` pins for resources).

**complete suggestions for that argument:**
```
complete(server="everything", ref_type="prompt", ref="completable-prompt", argument_name="department", argument_value=""):
Engineering
Sales
Marketing
Support
metadata == {"ref_type": "prompt", "ref": "completable-prompt", "argument": "department", "count": 4, "total": 4, "has_more": False}
```
For completeness, every other prompt argument was also probed: `args-prompt`'s `city`/`state` and
`completable-prompt`'s `name` returned no suggestions (`count: 0`); `resource-prompt`'s
`resourceType` also returned a real completion list (`Text`, `Blob`, `count: 2`) but was reached
second, after `completable-prompt`/`department` already satisfied "the first non-empty list".

**Verdict:** SC2 **met** — a real `server-everything@2026.8.31` connection returned its prompts (4,
not the roadmap's anticipated 3), `get_prompt` rendered three of the four prompts' argument-filled
text, and `complete()` returned real, non-empty suggestions for `completable-prompt`'s `department`
argument (`Engineering`, `Sales`, `Marketing`, `Support`), closing Open Question 2 with the real
prompt and argument names.

## Capability declarations observed

| Server | resources | resources.subscribe | prompts | completions |
|---|---|---|---|---|
| server-filesystem@2026.8.31 | **absent** (`resources=None`) | n/a (no resources capability at all) | absent | absent |
| server-everything@2026.8.31 | present | **true** | present | present |
| live_mcp_server.py (CI fixture) | yes | false | yes | yes |

Full observed `server_capabilities` object for `server-everything`:
```
experimental=None logging=LoggingCapability() prompts=PromptsCapability(list_changed=True) resources=ResourcesCapability(subscribe=True, list_changed=True) tools=ToolsCapability(list_changed=True) completions=CompletionsCapability() extensions=None tasks=ServerTasksCapability(...)
```
`server-everything` mounted all eight synthetic capability tools
(`list_resources`/`read_resource`/`list_resource_templates`/`subscribe_resource`/
`unsubscribe_resource`/`list_prompts`/`get_prompt`/`complete`) alongside its thirteen remote
tools — twenty-one `mcp__everything__*` tools total, confirmed by the `TOOL NAMES` line captured
in the SC2 run above.

## Deviations and findings

1. **`server-filesystem@2026.8.31` does not implement the MCP resources capability at all** — not
   "exposes files only as resource templates" (the shape difference the plan anticipated as a
   still-passing outcome), but a `server_capabilities.resources` of `None` and a JSON-RPC
   `-32601 Method not found` for both `resources/list` and `resources/templates/list`. This is a
   genuine, verified fact about the currently published third-party package (re-verified via
   `npm view` immediately before this run, same version as Phase 10's D-11 pin), not an agent86
   defect — `_capability_tools`'s gate worked exactly as designed by mounting zero resource tools
   for a server that never declared the capability. Recorded rather than fixed; this is not a call
   site agent86 owns. `docs/mcp-conformance-matrix.md`'s `CAP-RESOURCES`/`CAP-RESOURCE-TEMPLATES`
   rows cite the CI fixture's live stdio round trip (plan 11-02) as their corpus evidence, not this
   server, and their reasoning cells name this finding explicitly.
2. **`server-everything@2026.8.31` returns 4 prompts, not the 3 the roadmap's own text
   anticipated.** `resource-prompt` (a prompt embedding a resource reference) is present alongside
   the three prompts the roadmap named. Recorded as observed; no roadmap or planning document is
   edited to retroactively match this number.
3. **`get_prompt("resource-prompt", ...)` failed with a real MCPError** when supplied a placeholder
   argument value the server's own validation rejected (`resourceType` must be `Text` or `Blob`).
   This is the server enforcing its own argument constraints, not an agent86 defect — confirmed by
   `MCPGetPromptTool`'s try/except returning a soft `ToolResult` error rather than raising, exactly
   as the unit-tested contract for every other capability tool requires.
4. No other deviations. Both scripts ran to completion in a single attempt each; `npx.cmd` needed
   no retry or fallback to bare `npx`, matching Phase 10's MCP-07 finding.
