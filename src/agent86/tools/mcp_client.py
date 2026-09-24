"""MCP client (Tier 4) — mount external Model Context Protocol server tools.

agent86 acts as an MCP *client*: for each configured server it opens a transport, lists its
tools, and wraps each as a first-class :class:`Tool` in the registry — so MCP tools get the
same schema advertisement, approval gating, and observability as built-ins.

Three transports are supported: ``stdio`` (spawn a local subprocess), ``sse``, and ``http``
(streamable HTTP) — the last two connect to a remote ``url`` with optional auth ``headers``.
The MCP Python SDK is async and its sessions are long-lived; this manager runs a dedicated
background event loop so the synchronous harness can call MCP tools via
``run_coroutine_threadsafe``. Everything degrades gracefully: no servers configured, or the
``mcp`` package missing, yields zero tools and a note rather than an error.
"""

from __future__ import annotations

import asyncio
import re
import threading
import warnings
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

from agent86.config import Config, MCPServerConfig
from agent86.tools.base import EmptyArgs, Tool, ToolContext
from agent86.types import ToolCall, ToolResult, ToolSpec

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize(name: str) -> str:
    return _NAME_RE.sub("_", name)[:64]


class MCPTool(Tool[EmptyArgs]):
    """A registry tool backed by a remote MCP server tool."""

    Args = EmptyArgs  # unused: spec() and run() are overridden (schema comes from the server)

    def __init__(self, manager: MCPManager, server: str, tool_name: str,
                 description: str, input_schema: dict, read_only: bool = False):
        self._manager = manager
        self._server = server
        self._tool = tool_name
        self.name = _sanitize(f"mcp__{server}__{tool_name}")
        self.description = f"{description or tool_name} (MCP: {server})"
        # External side effects -> gated by the approval gate, unless the server's own
        # annotations say the tool only reads (readOnlyHint). Asking the user to approve a
        # read is noise that trains them to approve everything.
        self.side_effecting = not read_only
        self._schema = input_schema or {"type": "object", "properties": {}}

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name=self.name, description=self.description,
            parameters=self._schema, side_effecting=self.side_effecting,
        )

    def execute(self, args: EmptyArgs, ctx: ToolContext) -> ToolResult:  # pragma: no cover
        raise NotImplementedError  # run() is overridden; execute is never called

    def run(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        try:
            text = self._manager.call_tool(self._server, self._tool, call.arguments)
        except Exception as exc:
            return ToolResult(
                call_id=call.id, name=self.name, ok=False, error=f"MCP call failed: {exc}"
            )
        return ToolResult(call_id=call.id, name=self.name, content=text)


_TArgs = TypeVar("_TArgs", bound=BaseModel)


class _MCPCapabilityTool(Tool[_TArgs], Generic[_TArgs]):
    """Base for the synthetic per-server tools wrapping a non-``tools/*`` MCP capability.

    Where :class:`MCPTool` takes its name, description and JSON Schema from the remote server,
    these are agent86's own: a fixed verb, a local Pydantic ``Args`` model, and construction
    only for a server whose advertised ``ServerCapabilities`` declares the feature
    (``_capability_tools``). They implement ``execute`` rather than overriding ``run``, so they
    inherit argument validation and the never-raise backstop from :class:`Tool`.
    """

    #: Appended to ``mcp__{server}__`` to form the tool name.
    verb: str = ""
    #: The description's first sentence; the server name is appended automatically.
    summary: str = ""

    def __init__(self, manager: MCPManager, server: str) -> None:
        self._manager = manager
        self._server = server
        self.name = _sanitize(f"mcp__{server}__{self.verb}")
        self.description = f"{self.summary} (MCP: {server})"

    def _ok(self, payload: tuple[str, dict[str, Any]]) -> ToolResult:
        text, metadata = payload
        return ToolResult(call_id="", name=self.name, content=text, metadata=metadata)

    def _failed(self, exc: Exception) -> ToolResult:
        # Same wording as MCPTool.run, so the model sees one MCP failure shape, not two.
        return ToolResult(call_id="", name=self.name, ok=False, error=f"MCP call failed: {exc}")


class _ResourceUriArgs(BaseModel):
    uri: str = Field(
        description="The resource URI, exactly as returned by the list_resources tool."
    )


class _GetPromptArgs(BaseModel):
    name: str = Field(description="Prompt name, exactly as returned by the list_prompts tool.")
    arguments: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Values for the prompt's arguments, keyed by argument name. "
            "Omit or pass {} for a prompt that takes none."
        ),
    )


class _CompleteArgs(BaseModel):
    ref_type: Literal["prompt", "resource"] = Field(
        description=(
            "'prompt' to complete a prompt argument, 'resource' to complete a resource-template "
            "variable."
        )
    )
    ref: str = Field(
        description=(
            "For ref_type='prompt', the prompt name from list_prompts. For ref_type='resource', "
            "the uri_template from list_resource_templates."
        )
    )
    argument_name: str = Field(description="Which argument or template variable to complete.")
    argument_value: str = Field(
        default="",
        description="The partial value typed so far. Pass '' to ask for every suggestion.",
    )


class MCPListResourcesTool(_MCPCapabilityTool[EmptyArgs]):
    """resources/list."""

    verb = "list_resources"
    summary = (
        "List the resources this MCP server exposes, as "
        "'uri | name | mime_type | description' rows. Read one with read_resource."
    )
    Args = EmptyArgs

    def execute(self, args: EmptyArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(self._manager.list_resources(self._server))
        except Exception as exc:  # noqa: BLE001 - a tool never raises into the loop
            return self._failed(exc)


class MCPListResourceTemplatesTool(_MCPCapabilityTool[EmptyArgs]):
    """resources/templates/list."""

    verb = "list_resource_templates"
    summary = (
        "List this MCP server's resource TEMPLATES — parameterised URIs like "
        "'res://x/{id}' that read_resource can be called with once the parameters are filled in."
    )
    Args = EmptyArgs

    def execute(self, args: EmptyArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(self._manager.list_resource_templates(self._server))
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


class MCPReadResourceTool(_MCPCapabilityTool[_ResourceUriArgs]):
    """resources/read."""

    verb = "read_resource"
    summary = (
        "Read one resource from this MCP server by URI. Text content is returned inline; "
        "binary content is summarised by mime type and size and is NOT returned as base64."
    )
    Args = _ResourceUriArgs

    def execute(self, args: _ResourceUriArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(self._manager.read_resource(self._server, args.uri))
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


class MCPSubscribeResourceTool(_MCPCapabilityTool[_ResourceUriArgs]):
    """resources/subscribe. Approval-gated (D-03)."""

    verb = "subscribe_resource"
    summary = (
        "Ask this MCP server to track changes to one resource URI. Note: update "
        "notifications are not delivered to the model yet, so this records intent only."
    )
    Args = _ResourceUriArgs
    # Creates server-side state, and — until MCP-24 delivers the notification — an unapproved
    # background subscription would be invisible to the user. Approval-gated on purpose (D-03).
    side_effecting = True

    def execute(self, args: _ResourceUriArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(self._manager.subscribe_resource(self._server, args.uri))
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


class MCPUnsubscribeResourceTool(_MCPCapabilityTool[_ResourceUriArgs]):
    """resources/unsubscribe. The release half of subscribe_resource (D-01)."""

    verb = "unsubscribe_resource"
    summary = "Stop tracking changes to one resource URI on this MCP server."
    Args = _ResourceUriArgs
    side_effecting = True

    def execute(self, args: _ResourceUriArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(
                self._manager.subscribe_resource(self._server, args.uri, subscribe=False)
            )
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


class MCPListPromptsTool(_MCPCapabilityTool[EmptyArgs]):
    """prompts/list."""

    verb = "list_prompts"
    summary = (
        "List the prompt templates this MCP server offers, as 'name | arguments | description' "
        "rows. Fetch one with get_prompt."
    )
    Args = EmptyArgs

    def execute(self, args: EmptyArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(self._manager.list_prompts(self._server))
        except Exception as exc:  # noqa: BLE001 - a tool never raises into the loop
            return self._failed(exc)


class MCPGetPromptTool(_MCPCapabilityTool[_GetPromptArgs]):
    """prompts/get."""

    verb = "get_prompt"
    summary = (
        "Fetch one prompt template from this MCP server, rendered with the arguments you supply, "
        "as a '[role]: text' transcript."
    )
    Args = _GetPromptArgs

    def execute(self, args: _GetPromptArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(
                self._manager.get_prompt(self._server, args.name, args.arguments or None)
            )
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


class MCPCompleteTool(_MCPCapabilityTool[_CompleteArgs]):
    """completion/complete."""

    verb = "complete"
    summary = (
        "Ask this MCP server for valid values of one prompt argument or resource-template "
        "variable, optionally filtered by a partial value."
    )
    Args = _CompleteArgs

    def execute(self, args: _CompleteArgs, ctx: ToolContext) -> ToolResult:
        try:
            return self._ok(
                self._manager.complete(
                    self._server,
                    args.ref_type,
                    args.ref,
                    args.argument_name,
                    args.argument_value,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return self._failed(exc)


def _get_client_session() -> Any:
    """Return ``mcp.ClientSession``, looked up through this module's own globals first.

    Tests monkeypatch ``mcp_client.ClientSession`` (with ``raising=False``) to inject a fake
    session without a real transport; checking ``globals()`` first (before falling back to a
    fresh ``from mcp import ClientSession``) lets that monkeypatch take effect even though the
    real import happens lazily, per server, inside ``_serve``.
    """
    cached = globals().get("ClientSession")
    if cached is not None:
        return cached
    from mcp import ClientSession as _ClientSession

    return _ClientSession


def _tool_schema(tool: Any) -> dict:
    """The tool's JSON Schema, under either SDK spelling (``input_schema`` in mcp>=2)."""
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None)
    return schema or {}


def _is_read_only(tool: Any) -> bool:
    """True when the server annotates the tool with ``readOnlyHint``.

    A hint from a remote server is advisory, so it can only ever *relax* the approval gate
    for a tool the user already chose to mount — never grant anything else.
    """
    ann = getattr(tool, "annotations", None)
    if ann is None:
        return False
    if isinstance(ann, dict):
        value = ann.get("readOnlyHint", ann.get("read_only_hint"))
    else:
        value = getattr(ann, "read_only_hint", None)
        if value is None:
            value = getattr(ann, "readOnlyHint", None)
    return value is True


def _capability_tools(manager: MCPManager, server: str, caps: Any) -> list[Tool]:
    """The synthetic tools a server's advertised ``ServerCapabilities`` entitle it to.

    Gating registration (rather than gating the call) is the point: a server that never declared
    ``resources`` answers ``resources/list`` with a JSON-RPC "method not found", and advertising
    a tool that can only ever fail trains the model to distrust its tool list. Mirrors
    ``_is_read_only``'s philosophy — a server-declared signal only ever changes what agent86
    *offers* for a server the user already chose to mount.
    """
    extra: list[Tool] = []
    if caps is None:
        return extra
    resources = getattr(caps, "resources", None)
    if resources is not None:
        extra.append(MCPListResourcesTool(manager, server))
        extra.append(MCPReadResourceTool(manager, server))
        extra.append(MCPListResourceTemplatesTool(manager, server))
        if getattr(resources, "subscribe", False):
            extra.append(MCPSubscribeResourceTool(manager, server))
            extra.append(MCPUnsubscribeResourceTool(manager, server))
    if getattr(caps, "prompts", None) is not None:
        extra.append(MCPListPromptsTool(manager, server))
        extra.append(MCPGetPromptTool(manager, server))
    if getattr(caps, "completions", None) is not None:
        # CompletionsCapability is an empty marker class on the SDK — its presence IS the signal.
        extra.append(MCPCompleteTool(manager, server))
    return extra


class MCPManager:
    def __init__(
        self,
        servers: dict[str, MCPServerConfig],
        env_passthrough: list[str] | None = None,
    ):
        self.servers = servers
        #: Every degradation seen since construction, oldest first. ``note`` renders them all —
        #: with several bad servers, overwriting one string hid every failure but the last.
        self.notes: list[str] = []
        self.note: str | None = None
        self.env_passthrough = list(env_passthrough or [])
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._sessions: dict[str, Any] = {}
        self._tasks: dict[str, Any] = {}  # name -> asyncio.Task (owns its own stack)
        self._close_events: dict[str, Any] = {}  # name -> asyncio.Event
        self._server_tools: dict[str, list[Tool]] = {}
        self._started = False

    def _add_note(self, message: str) -> None:
        """Record a degradation without erasing the previous one."""
        if message not in self.notes:
            self.notes.append(message)
        self.note = "\n".join(self.notes)

    def _ensure_loop(self) -> None:
        """Start the background event loop, lazily importing `mcp`. Raises if it is missing.

        Every entry point (bulk `start`, per-server `start_server`) funnels through here so the
        degrade-with-a-note contract is identical no matter which one the caller used.
        """
        if self._loop is not None:
            return
        try:
            from contextlib import AsyncExitStack  # noqa: F401 - import probe

            from mcp import ClientSession  # noqa: F401 - import probe
        except ImportError as exc:
            message = (
                'mcp package not installed; MCP tools unavailable (pip install "agent86[mcp]").'
            )
            self._add_note(message)
            raise RuntimeError(message) from exc
        self._started = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def start_server(
        self,
        name: str,
        cfg: MCPServerConfig,
        timeout: float = 30.0,
        overrides: dict[str, str] | None = None,
    ) -> list[Tool]:
        """Open one server's transport and return its tools. Blocks the caller until ready.

        Raises on connection failure or timeout — the connection-test modal surfaces it verbatim
        (D-19/D-20). On success the server's owning task stays parked until `stop_server`.
        """
        self._ensure_loop()
        assert self._loop is not None
        if name in self._tasks:
            self.stop_server(name)
        resolved = _resolve_server_secrets(cfg, overrides)
        fut = asyncio.run_coroutine_threadsafe(self._launch(name, resolved), self._loop)
        try:
            tools = fut.result(timeout=timeout)
        except Exception:
            self._tasks.pop(name, None)
            self._close_events.pop(name, None)
            self._server_tools.pop(name, None)
            raise
        return tools

    async def _launch(self, name: str, cfg: MCPServerConfig) -> list[Tool]:
        close_event = asyncio.Event()
        ready: asyncio.Future = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(self._serve(name, cfg, ready, close_event))
        self._tasks[name] = task
        self._close_events[name] = close_event
        return await ready

    async def _serve(
        self, name: str, cfg: MCPServerConfig, ready: asyncio.Future, close_event: asyncio.Event
    ) -> None:
        """The server's owning task: opens its OWN AsyncExitStack and lets it unwind here.

        anyio binds each transport's cancel scope to the task that entered it, so `aclose()` may
        only run in that same task (python-sdk issues #79/#922). Parking on `close_event` and
        letting the `async with` unwind in place is what makes per-server teardown legal.
        """
        from contextlib import AsyncExitStack

        ClientSession = _get_client_session()

        try:
            async with AsyncExitStack() as stack:
                streams = await stack.enter_async_context(
                    _open_transport(cfg, self.env_passthrough)
                )
                # sse/stdio yield (read, write); streamable HTTP yields a 3rd
                # get_session_id we don't need — take the first two either way.
                read, write = streams[0], streams[1]
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                listed = await session.list_tools()
                tools: list[Tool] = [
                    MCPTool(
                        self,
                        name,
                        t.name,
                        t.description or "",
                        _tool_schema(t),
                        read_only=_is_read_only(t),
                    )
                    for t in listed.tools
                ]
                # Capability-gated synthetic tools, appended AFTER the server's own (D-04): a
                # server exposing a real tool called e.g. "read_resource" keeps the name, and
                # agent86's synthetic one is reported as a collision by ToolRegistry rather
                # than shadowing it. Read through getattr so a session object without the
                # property (an older SDK, or a test fake) degrades to "no synthetic tools".
                tools.extend(
                    _capability_tools(self, name, getattr(session, "server_capabilities", None))
                )
                self._sessions[name] = session
                self._server_tools[name] = tools
                if not ready.done():
                    ready.set_result(tools)
                await close_event.wait()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the caller verbatim
            if not ready.done():
                ready.set_exception(exc)
        finally:
            self._sessions.pop(name, None)

    def stop_server(self, name: str, timeout: float = 10.0) -> None:
        """Signal one server's owning task to unwind its own stack, then wait for it."""
        close_event = self._close_events.pop(name, None)
        task = self._tasks.pop(name, None)
        self._server_tools.pop(name, None)
        if close_event is None or task is None or self._loop is None:
            return

        async def _stop() -> None:
            close_event.set()
            await task  # awaiting a task from another task is fine — no scope is exited here

        try:
            asyncio.run_coroutine_threadsafe(_stop(), self._loop).result(timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - a stuck teardown must not wedge the app
            self._add_note(f"MCP server '{name}' did not shut down cleanly: {exc}")
        self._sessions.pop(name, None)

    def tools_for(self, name: str) -> list[Tool]:
        return list(self._server_tools.get(name, []))

    def tools(self) -> list[Tool]:
        return [tool for tools in self._server_tools.values() for tool in tools]

    def start(self) -> None:
        if self._started or not self.servers:
            return
        try:
            self._ensure_loop()
        except RuntimeError:
            return  # note already set by _ensure_loop
        for name, cfg in self.servers.items():
            try:
                self.start_server(name, cfg)
            except Exception as exc:  # noqa: BLE001 - one bad server degrades to a note
                self._add_note(f"MCP server '{name}' failed to start: {exc}")

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        if self._loop is None or server not in self._sessions:
            raise RuntimeError("MCP session not available")
        session = self._sessions[server]

        async def _call() -> str:
            result = await session.call_tool(tool, arguments)
            return _content_to_text(result)

        return asyncio.run_coroutine_threadsafe(_call(), self._loop).result(timeout=120)

    def _on_session(
        self,
        server: str,
        call: Callable[[Any], Coroutine[Any, Any, Any]],
        timeout: float = 120,
    ) -> Any:
        """Run ``call(session)`` on the MCP event loop and return its result.

        The synchronous entry point every capability call site shares — same guard, same
        ``run_coroutine_threadsafe(...).result(timeout=...)`` shape ``call_tool`` already uses.
        The 120-second default is deliberately the same hardcoded number: per-server
        configurable timeouts are MCP-21 (workstream C), and a second timeout knob here would
        pre-empt that ruling.
        """
        if self._loop is None or server not in self._sessions:
            raise RuntimeError("MCP session not available")
        session = self._sessions[server]
        return asyncio.run_coroutine_threadsafe(call(session), self._loop).result(timeout=timeout)

    def list_resources(self, server: str) -> tuple[str, dict[str, Any]]:
        """``resources/list`` — a single page, matching ``list_tools()``'s existing behaviour.

        ``next_cursor`` is deliberately ignored: CAP-PAGINATION is workstream C, and building a
        cursor loop here would be the only paginated call in the client.
        """

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            result = await session.list_resources()
            resources = list(getattr(result, "resources", None) or [])
            return _resources_to_text(resources), {"count": len(resources)}

        return self._on_session(server, _call)

    def list_resource_templates(self, server: str) -> tuple[str, dict[str, Any]]:
        """``resources/templates/list`` — single page, same reasoning as list_resources."""

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            result = await session.list_resource_templates()
            templates = list(getattr(result, "resource_templates", None) or [])
            return _resource_templates_to_text(templates), {"count": len(templates)}

        return self._on_session(server, _call)

    def read_resource(self, server: str, uri: str) -> tuple[str, dict[str, Any]]:
        """``resources/read``. Binary contents are marked, never inlined (D-02)."""

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            result = await session.read_resource(uri)
            text, meta = _resource_contents_to_text(list(getattr(result, "contents", None) or []))
            return text, {"uri": uri, **meta}

        return self._on_session(server, _call)

    def subscribe_resource(
        self, server: str, uri: str, *, subscribe: bool = True
    ) -> tuple[str, dict[str, Any]]:
        """``resources/subscribe`` / ``resources/unsubscribe``.

        Both SDK methods are ``@deprecated`` relative to protocol revision ``2026-07-28``, which
        replaces them with ``Client.listen()``. agent86's client negotiates ``2025-11-25``
        (Phase 10, D-01), for which these ARE the correct calls — the deprecation is a forward
        notice about a revision this client cannot speak, not a defect. Do not delete these call
        sites; that would silently drop CAP-RESOURCE-SUBSCRIBE. The warning (a ``UserWarning``
        subclass, shown by default) is silenced for exactly this call and nowhere else.
        """

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            from mcp.shared.exceptions import MCPDeprecationWarning

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", MCPDeprecationWarning)
                if subscribe:
                    await session.subscribe_resource(uri)
                else:
                    await session.unsubscribe_resource(uri)
            verb = "Subscribed to" if subscribe else "Unsubscribed from"
            return (
                f"{verb} {uri}. Note: resource update notifications are not delivered to the "
                f"model yet (tracked as MCP-24), so this records intent on the server only.",
                {"uri": uri, "subscribed": subscribe},
            )

        return self._on_session(server, _call)

    def list_prompts(self, server: str) -> tuple[str, dict[str, Any]]:
        """``prompts/list`` — a single page, matching list_tools()/list_resources() (MCP-21/C)."""

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            result = await session.list_prompts()
            prompts = list(getattr(result, "prompts", None) or [])
            return _prompts_to_text(prompts), {"count": len(prompts)}

        return self._on_session(server, _call)

    def get_prompt(
        self, server: str, name: str, arguments: dict[str, str] | None = None
    ) -> tuple[str, dict[str, Any]]:
        """``prompts/get``. The server's own description, if any, heads the transcript."""

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            result = await session.get_prompt(name, arguments or None)
            text, meta = _prompt_messages_to_text(list(getattr(result, "messages", None) or []))
            description = getattr(result, "description", None)
            if description:
                text = f"{description}\n\n{text}"
            return text, {"prompt": name, **meta}

        return self._on_session(server, _call)

    def complete(
        self,
        server: str,
        ref_type: str,
        ref: str,
        argument_name: str,
        argument_value: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """``completion/complete`` for a prompt argument or a resource-template variable.

        ``ref_type`` selects the SDK's reference union explicitly (D-08): ``"prompt"`` builds a
        ``PromptReference(name=ref)``, anything else a ``ResourceTemplateReference(uri=ref)``.
        ``context_arguments`` is deliberately not exposed — no corpus server demands it, and a
        minimal surface is easier to widen later than to narrow.
        """

        async def _call(session: Any) -> tuple[str, dict[str, Any]]:
            from mcp import types as mcp_types

            reference = (
                mcp_types.PromptReference(name=ref)
                if ref_type == "prompt"
                else mcp_types.ResourceTemplateReference(uri=ref)
            )
            result = await session.complete(
                reference, {"name": argument_name, "value": argument_value}
            )
            text, meta = _completion_to_text(getattr(result, "completion", None))
            return text, {"ref_type": ref_type, "ref": ref, "argument": argument_name, **meta}

        return self._on_session(server, _call)

    def close(self) -> None:
        """Shut every server down and return the manager to a restartable state.

        ``_started`` is reset (and the loop/thread handles dropped) so a later ``start()``
        actually reconnects — before, close() left the flag set and start() returned silently,
        so toggling MCP off and on again ended up with no tools and no explanation.
        """
        if self._loop is not None:
            for name in list(self._tasks):
                self.stop_server(name)
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread:
                self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._started = False
        self._sessions.clear()
        self._tasks.clear()
        self._close_events.clear()
        self._server_tools.clear()


@asynccontextmanager
async def _streamable_http(url: str, headers: dict[str, str]) -> Any:
    """Streamable-HTTP transport, owning the httpx client's lifecycle.

    The SDK's ``streamable_http_client`` takes a caller-provided client (the older all-in-one
    ``streamablehttp_client`` is deprecated) — and in mcp>=2 that client is an
    ``httpx2.AsyncClient``, not an ``httpx`` one. Building it with the SDK's own
    ``create_mcp_http_client`` keeps the types honest (no cast, no ignore) and picks up the
    recommended MCP timeouts for free. Yields the transport's stream tuple.
    """
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    async with create_mcp_http_client(headers=headers or None) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            yield streams


def _resolve_server_secrets(
    cfg: MCPServerConfig, overrides: dict[str, str] | None = None
) -> MCPServerConfig:
    """Return a COPY of ``cfg`` with every ``${VAR}`` resolved (D-17/D-25).

    Applied to ``args``, ``env`` values, ``url``, and ``headers`` values — resolved fresh at
    connect time, never cached back into config. ``command`` is deliberately NOT expanded: letting
    an env var or keyring entry decide which executable is spawned is a foot-gun with no use case
    in this phase's scope.

    Raises :class:`agent86.secrets.MissingSecretRef` for the first unresolved name; the caller
    turns that into a masked key prompt (D-18) rather than connecting with an empty credential.
    """
    from agent86.secrets import expand_var_refs

    return cfg.model_copy(
        update={
            "args": [expand_var_refs(a, overrides) for a in cfg.args],
            "env": {k: expand_var_refs(v, overrides) for k, v in cfg.env.items()},
            "url": expand_var_refs(cfg.url, overrides) if cfg.url else cfg.url,
            "headers": {k: expand_var_refs(v, overrides) for k, v in cfg.headers.items()},
        }
    )


def unresolved_var_refs(cfg: MCPServerConfig, overrides: dict[str, str] | None = None) -> list[str]:
    """Every ${VAR} name in args/env/url/headers that neither an override, the environment, nor
    the OS keyring can supply — in stable sorted order, so the caller prompts predictably."""
    from agent86.secrets import find_var_refs, resolve_api_key

    overrides = overrides or {}
    texts = [*cfg.args, *cfg.env.values(), cfg.url or "", *cfg.headers.values()]
    missing = [
        name
        for name in sorted(find_var_refs(*texts))
        if name not in overrides and resolve_api_key(name, name) is None
    ]
    return missing


def stdio_env(cfg: MCPServerConfig, env_passthrough: list[str] | None = None) -> dict[str, str]:
    """The environment a stdio MCP server subprocess gets.

    It used to be ``{**os.environ, **cfg.env}`` as soon as a server declared *any* env var —
    which handed a third-party subprocess every API key on the machine. Now it is the same
    scrubbed environment tool subprocesses get (platform allowlist + the user's
    ``sandbox.env_passthrough``, credential-looking names refused), with the server's own
    ``cfg.env`` layered on top. Those values have already had their ``${VAR}`` references
    resolved by ``_resolve_server_secrets``, so a server that genuinely needs a credential
    still gets exactly the one it asked for — and nothing else.
    """
    from agent86.tools.sandbox.policy import SandboxPolicy

    policy = SandboxPolicy(workspace=Path.cwd(), env_passthrough=list(env_passthrough or []))
    env = policy.scrubbed_env()
    env.update(cfg.env)
    return env


def _open_transport(cfg: MCPServerConfig, env_passthrough: list[str] | None = None) -> Any:
    """Return the async transport context manager for a server's configured transport.

    ``cfg`` is expected to already be ``${VAR}``-resolved (see ``_resolve_server_secrets``) —
    this function does no expansion of its own.

    Imports are lazy and per-transport so a server that only uses stdio never pulls in the
    HTTP transports (and vice versa). The caller enters the returned context on the MCP loop.
    """
    # The config validator guarantees command/url are set for their transport; assert the
    # invariant so the type checker can narrow away the Optional.
    if cfg.transport == "stdio":
        assert cfg.command is not None
        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(
            command=cfg.command,
            args=cfg.args,
            env=stdio_env(cfg, env_passthrough),
        )
        return stdio_client(params)
    assert cfg.url is not None
    if cfg.transport == "sse":
        from mcp.client.sse import sse_client

        return sse_client(cfg.url, headers=cfg.headers or None)
    # "http" -> streamable HTTP (the modern successor to the SSE transport)
    return _streamable_http(cfg.url, cfg.headers)


def _content_to_text(result: Any) -> str:
    parts: list[str] = []
    for chunk in getattr(result, "content", None) or []:
        text = getattr(chunk, "text", None)
        parts.append(text if text is not None else str(chunk))
    body = "\n".join(parts) if parts else "(no content)"
    if getattr(result, "isError", False):
        return f"ERROR: {body}"
    return body


def _row(*cells: object) -> str:
    """One pipe-delimited table row with whitespace-collapsed cells."""
    return " | ".join(" ".join(str(c if c is not None else "").split()) for c in cells)


def _resources_to_text(resources: list[Any]) -> str:
    """``uri | name | mime_type | description``, one line per resource."""
    if not resources:
        return "(no resources)"
    lines = ["uri | name | mime_type | description"]
    for r in resources:
        lines.append(
            _row(
                getattr(r, "uri", ""),
                getattr(r, "name", ""),
                getattr(r, "mime_type", None) or "unknown",
                getattr(r, "description", None) or "",
            )
        )
    return "\n".join(lines)


def _resource_templates_to_text(templates: list[Any]) -> str:
    """``uri_template | name | mime_type | description``, one line per template."""
    if not templates:
        return "(no resource templates)"
    lines = ["uri_template | name | mime_type | description"]
    for t in templates:
        lines.append(
            _row(
                getattr(t, "uri_template", "") or getattr(t, "uriTemplate", ""),
                getattr(t, "name", ""),
                getattr(t, "mime_type", None) or "unknown",
                getattr(t, "description", None) or "",
            )
        )
    return "\n".join(lines)


def _resource_contents_to_text(contents: list[Any]) -> tuple[str, dict[str, Any]]:
    """Flatten ``ReadResourceResult.contents``, NEVER inlining a base64 blob.

    Returns ``(content_text, metadata)``. A text part is rendered verbatim; a binary part
    becomes a one-line marker naming its mime type and base64 length, with the same facts
    recorded under ``metadata["binary"]``. The base64 itself is carried nowhere (D-02): it is
    unusable to the model as text, unbounded in size, and bounding an MCP result is ADR 0004 /
    MCP-22's question, not this one's. Representing non-text content properly is
    CAP-CONTENT-BLOCKS / MCP-25.
    """
    if not contents:
        return "(no content)", {}
    parts: list[str] = []
    binary: list[dict[str, Any]] = []
    for item in contents:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
            continue
        descriptor: dict[str, Any] = {
            "uri": str(getattr(item, "uri", "") or ""),
            "mime_type": str(getattr(item, "mime_type", None) or "unknown"),
            "base64_len": len(getattr(item, "blob", None) or ""),
        }
        binary.append(descriptor)
        parts.append(
            f"[binary resource uri={descriptor['uri']} "
            f"mime_type={descriptor['mime_type']} "
            f"base64_len={descriptor['base64_len']} — not inlined]"
        )
    metadata: dict[str, Any] = {"binary": binary} if binary else {}
    return "\n".join(parts), metadata


def _prompts_to_text(prompts: list[Any]) -> str:
    """``name | arguments | description``, one line per prompt; ``*`` marks a required argument."""
    if not prompts:
        return "(no prompts)"
    lines = ["name | arguments | description"]
    for p in prompts:
        arguments = list(getattr(p, "arguments", None) or [])
        rendered = (
            ", ".join(
                f"{getattr(a, 'name', '')}{'*' if getattr(a, 'required', False) else ''}"
                for a in arguments
            )
            or "(none)"
        )
        lines.append(_row(getattr(p, "name", ""), rendered, getattr(p, "description", None) or ""))
    lines.append("(* = required argument; pass them to get_prompt as the `arguments` object)")
    return "\n".join(lines)


def _prompt_messages_to_text(messages: list[Any]) -> tuple[str, dict[str, Any]]:
    """Render ``GetPromptResult.messages`` as a ``[role]: text`` transcript.

    A non-text content block (image, audio, embedded resource, resource link) becomes a NAMED
    marker — never ``str(block)``, the Python repr that ``_content_to_text`` falls back to and
    that CAP-CONTENT-BLOCKS / ADR 0004 record as a defect (D-07). Repairing that older path is
    MCP-25, workstream C; this is new code and simply does not have the bug.
    """
    if not messages:
        return "(no messages)", {}
    lines: list[str] = []
    non_text: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        raw_role = getattr(message, "role", "")
        role = str(getattr(raw_role, "value", raw_role) or "unknown")
        content = getattr(message, "content", None)
        text = getattr(content, "text", None)
        if text is not None:
            lines.append(f"[{role}]: {text}")
            continue
        kind = type(content).__name__
        non_text.append({"index": index, "role": role, "type": kind})
        lines.append(f"[{role}]: [non-text content block: {kind} — not inlined]")
    metadata: dict[str, Any] = {"non_text_blocks": non_text} if non_text else {}
    return "\n".join(lines), metadata


def _completion_to_text(completion: Any) -> tuple[str, dict[str, Any]]:
    """One suggestion per line, with the server's total/has_more hints in the metadata."""
    values = [str(v) for v in (getattr(completion, "values", None) or [])]
    metadata: dict[str, Any] = {
        "count": len(values),
        "total": getattr(completion, "total", None),
        "has_more": getattr(completion, "has_more", None),
    }
    return ("\n".join(values) if values else "(no suggestions)"), metadata


def build_mcp(config: Config) -> MCPManager | None:
    """Start MCP servers from config, or return None if disabled / none configured.

    Per-server ``enabled = false`` (D-09) is filtered here rather than inside ``MCPManager``, so
    ``MCPManager.servers`` only ever holds servers that are supposed to be running — bulk
    ``start()`` has no separate check to forget (RESEARCH Pitfall 5).
    """
    if not config.mcp.enabled or not config.mcp_servers:
        return None
    enabled = {name: cfg for name, cfg in config.mcp_servers.items() if cfg.enabled}
    if not enabled:
        return None
    manager = MCPManager(
        enabled, env_passthrough=list(getattr(config.sandbox, "env_passthrough", []) or [])
    )
    manager.start()
    return manager


__all__ = [
    "MCPCompleteTool",
    "MCPGetPromptTool",
    "MCPListPromptsTool",
    "MCPListResourceTemplatesTool",
    "MCPListResourcesTool",
    "MCPManager",
    "MCPReadResourceTool",
    "MCPSubscribeResourceTool",
    "MCPTool",
    "MCPUnsubscribeResourceTool",
    "build_mcp",
    "stdio_env",
    "_resolve_server_secrets",
    "unresolved_var_refs",
]
