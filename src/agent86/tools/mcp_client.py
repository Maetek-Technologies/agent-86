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
import contextvars
import logging
import os
import random
import re
import tempfile
import threading
import warnings
from collections import deque
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Generic, Literal, NamedTuple, TextIO, TypeVar, cast

from pydantic import BaseModel, Field

from agent86.config import (
    DEFAULT_MCP_CALL_TIMEOUT_S,
    DEFAULT_MCP_MAX_RESULT_CHARS,
    Config,
    MCPServerConfig,
)
from agent86.tools.base import EmptyArgs, Tool, ToolContext
from agent86.types import ToolCall, ToolResult, ToolSpec

logger = logging.getLogger(__name__)

_NAME_RE = re.compile(r"[^A-Za-z0-9_-]")

#: Reconnect budget after a mid-session drop (MCP-23). Deliberately NOT per-server config:
#: MCP-21 made the connect/call timeouts configurable (MCPServerConfig.connect_timeout_s /
#: call_timeout_s); the reconnect attempt count and backoff window stay fixed module constants.
_MAX_RECONNECT_ATTEMPTS = 5
_RECONNECT_BASE_DELAY_S = 0.5
_RECONNECT_MAX_DELAY_S = 30.0

#: Bounded event log behind `notes_since` — a live, forever-running session must not grow this
#: unboundedly; 500 note events is generous for any realistic outage history.
_NOTE_EVENT_LIMIT = 500

#: PEP 678 note prefix marking a stdio start failure's captured child stderr tail (Task 2).
_STDERR_NOTE_PREFIX = "agent86-mcp-stderr:\n"
#: Per-attempt hand-off for the stdio child's stderr capture file (Task 2). A ContextVar, not a
#: new `_open_transport` parameter: many tests replace `_open_transport` with a bare
#: `(cfg, env_passthrough=None)` fake, and an asyncio task carries its own context, so the value
#: set in one server's `_serve_once` is only ever seen by that same server's `_open_transport`.
_STDIO_ERRLOG: contextvars.ContextVar[TextIO | None] = contextvars.ContextVar(
    "agent86_mcp_stdio_errlog", default=None
)


def _sanitize(name: str) -> str:
    return _NAME_RE.sub("_", name)[:64]


def _reconnect_backoff(
    attempt: int, *, jitter: Callable[[float, float], float] | None = None
) -> float:
    """Exponential backoff with equal jitter: half the window fixed, half random.

    Same shape as ``agent86.cognitive.retry.backoff_delay`` — duplicated rather than imported
    so the Tools tier takes no dependency on the Cognitive tier. Attempt 1 waits 0.5-1 s; the
    default budget of 5 attempts waits at most ~31 s in total.
    """
    window = min(_RECONNECT_BASE_DELAY_S * (2**attempt), _RECONNECT_MAX_DELAY_S)
    rand = jitter or random.uniform
    return window / 2 + rand(0.0, window / 2)


class MCPServerUnavailable(RuntimeError):
    """A call named an MCP server with no live session. The message always names the server.

    A RuntimeError subclass so every existing ``except RuntimeError`` / ``pytest.raises(
    RuntimeError)`` keeps working."""

    def __init__(self, server: str, message: str) -> None:
        super().__init__(message)
        self.server = server


class MCPTimeout(TimeoutError):
    """An MCP connect or call exceeded its per-server budget (MCP-21).

    The message names the server and the config field to raise, so a slow-but-legitimate
    server can be told apart from a hung one by config rather than a code change.
    """

    def __init__(self, server: str, message: str) -> None:
        super().__init__(message)
        self.server = server


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


class _EOFWatchStream:
    """Wrap a transport read stream; call ``on_eof`` once when the stream ends.

    The SDK never tells a ClientSession's owner that the transport died: on a killed stdio
    server the dispatcher's read loop simply reaches end-of-stream, fans ``Connection closed``
    out to pending requests, and returns — nothing reaches ``message_handler``. Watching the
    stream ClientSession reads from is the one transport-agnostic place that end is visible.
    """

    def __init__(self, inner: Any, on_eof: Callable[[], None]) -> None:
        import anyio  # lazy: only ever constructed inside _serve_once, where mcp is installed

        self._inner = inner
        self._on_eof = on_eof
        self._fired = False
        self._closed_errors = (
            anyio.EndOfStream,
            anyio.ClosedResourceError,
            anyio.BrokenResourceError,
        )

    @property
    def last_context(self) -> Any:
        return getattr(self._inner, "last_context", None)

    def _fire(self) -> None:
        if not self._fired:
            self._fired = True
            self._on_eof()

    async def receive(self) -> Any:
        try:
            return await self._inner.receive()
        except self._closed_errors:
            self._fire()
            raise

    def __aiter__(self) -> _EOFWatchStream:
        return self

    async def __anext__(self) -> Any:
        try:
            return await self._inner.__anext__()
        except StopAsyncIteration:
            self._fire()
            raise
        except self._closed_errors:
            self._fire()
            raise

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            close()

    async def aclose(self) -> None:
        await self._inner.aclose()

    async def __aenter__(self) -> _EOFWatchStream:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        # Deliberately does NOT fire self._on_eof: a deliberate teardown cancels the dispatcher
        # rather than draining it to EOF, and must not be reported as a drop.
        await self._inner.aclose()


def _describe(exc: BaseException) -> str:
    """Unwrap a BaseExceptionGroup to its first leaf and render "Type: message"."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    text = str(exc)
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _leaf_exceptions(exc: BaseException) -> list[BaseException]:
    """Every leaf of a (possibly nested) BaseExceptionGroup, depth-first, order-preserving."""
    if isinstance(exc, BaseExceptionGroup):
        leaves: list[BaseException] = []
        for sub in exc.exceptions:
            leaves.extend(_leaf_exceptions(sub))
        return leaves
    return [exc]


def describe_start_failure(exc: BaseException) -> str:
    """Render a start failure for a human — never the SDK's bare ``unhandled errors in a
    TaskGroup`` wrapper text.

    A non-group exception keeps the format ``start()`` has always used (``str(exc)``, falling
    back to the class name when the exception carries no message). A
    ``BaseExceptionGroup`` — what anyio's task groups always raise, often nested — is unwrapped
    to EVERY distinct leaf (order-preserving, duplicate descriptions collapsed), joined by
    ``"; "``: a TaskGroup can legitimately carry more than one real cause.

    If ``exc`` carries a PEP 678 note starting with ``_STDERR_NOTE_PREFIX`` (see
    ``_StderrCapture``/``_serve_once``), the child's captured stderr tail is appended — with an
    extra, named fix when the failure was the SDK's own CONNECTION_CLOSED (the child almost
    certainly exited during startup, and the fix is usually its command/args).
    """
    if isinstance(exc, BaseExceptionGroup):
        leaves = _leaf_exceptions(exc)
        seen: list[str] = []
        for leaf in leaves:
            described = _describe(leaf)
            if described not in seen:
                seen.append(described)
        message = "; ".join(seen)
        is_connection_closed = any(_is_connection_closed(leaf) for leaf in leaves)
    else:
        message = str(exc) or type(exc).__name__
        is_connection_closed = _is_connection_closed(exc)

    tail: str | None = None
    for note in getattr(exc, "__notes__", None) or []:
        if isinstance(note, str) and note.startswith(_STDERR_NOTE_PREFIX):
            tail = note[len(_STDERR_NOTE_PREFIX) :]
            break
    if tail:
        indented = "\n".join(f"  {line}" for line in tail.splitlines())
        if is_connection_closed:
            message += (
                "\nThe server process exited during startup. Its stderr (last lines):\n"
                f"{indented}\n"
                "Check this server's command/args — e.g. the interpreter it runs may be "
                "missing the server's package."
            )
        else:
            message += f"\nServer stderr (last lines):\n{indented}"
    return message


class _StderrCapture:
    """Capture a stdio MCP child's stderr to a temp file (Task 2, `_STDIO_ERRLOG`).

    Windows' ``create_windows_process`` hands the SDK's ``errlog`` straight to
    ``anyio.open_process(stderr=...)``, which needs a real ``fileno()`` — a pipe or a
    ``StringIO`` does not work there — so a temp file is used instead of either.
    """

    def __init__(self) -> None:
        self._file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            errors="replace",
            delete=False,
            prefix="agent86-mcp-",
            suffix=".stderr",
        )
        self.path = self._file.name

    @property
    def handle(self) -> TextIO:
        return cast(TextIO, self._file)

    def tail(self, max_lines: int = 20, max_bytes: int = 2048) -> str:
        """The last `max_lines` lines written so far, secrets redacted. Never raises.

        Reads through a SEPARATE handle opened fresh on every call: on Windows the child's
        inherited handle shares `self._file`'s own write position, so reading back through the
        same object would not see what the child actually wrote.
        """
        try:
            with open(self.path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                start = max(0, size - max_bytes)
                f.seek(start)
                data = f.read()
            text = data.decode("utf-8", "replace")
            lines = text.splitlines()
            if start > 0 and lines:
                lines = lines[1:]  # the read may have started mid-line; drop the partial one
            while lines and not lines[-1].strip():
                lines.pop()
            text = "\n".join(lines[-max_lines:])
            try:
                from agent86.guardrails.scanners import redact

                text = redact(text, pii=False)[0]
            except Exception:  # noqa: BLE001 - a redaction failure must not hide the tail
                pass
            return text
        except OSError:
            return ""

    def close(self) -> None:
        """Best-effort cleanup. A leftover temp file (Windows may still hold it) is acceptable;
        a raise here is not."""
        with suppress(OSError):
            self._file.close()
        with suppress(OSError):
            os.unlink(self.path)


class _SessionEnd(NamedTuple):
    """The result of one _serve_once attempt. ``cause is None`` means a deliberate stop."""

    cause: str | None
    tools: list[Tool]
    stderr_tail: str = ""


def _is_connection_closed(exc: BaseException) -> bool:
    """True only for the SDK's own local end-of-connection fan-out (code CONNECTION_CLOSED).

    Decided on the error CODE the dispatcher stamps when its read stream ends, never on the
    exception type alone: MCPError is also what a healthy server's ordinary JSON-RPC error
    raises (research Pitfall 3), and that must reach the model unchanged.
    """
    try:
        from mcp.shared import exceptions as mcp_exceptions
        from mcp.types import CONNECTION_CLOSED
    except ImportError:
        return False
    error_cls = getattr(mcp_exceptions, "MCPError", None) or getattr(
        mcp_exceptions, "McpError", None
    )
    if error_cls is None or not isinstance(exc, error_cls):
        return False
    return getattr(getattr(exc, "error", None), "code", None) == CONNECTION_CLOSED


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
        self._active_cfg: dict[str, MCPServerConfig] = {}  # name -> cfg start_server() launched
        self._server_state: dict[str, str] = {}  # name -> "connected"|"reconnecting"|"disconnected"
        self._disconnect_cause: dict[str, str] = {}  # name -> human-readable reason for last drop
        self._reconnect_attempt: dict[str, int] = {}  # name -> current attempt (used by 12-03)
        #: Called on the MCP loop thread as (server, removed_tools, added_tools) when a server's
        #: tool set changes WITHOUT the user asking (a drop, and in 12-03 a reconnect). Harness
        #: wires it to its ToolRegistry (12-04). Never called for start_server/stop_server —
        #: those callers already update the registry themselves.
        self.on_tools_changed: Callable[[str, list[Tool], list[Tool]], None] | None = None
        # Push-hook plumbing for surfacing notes live (Task 3): a bounded, non-deduped event
        # log plus a listener list, both guarded by one lock. `close()` deliberately does not
        # clear these — a caller's wiring (e.g. Harness._wire_mcp) must survive a close/start
        # cycle, exactly like `on_tools_changed` already does.
        self._notes_lock = threading.Lock()
        self._note_seq = 0
        self._note_events: deque[tuple[int, str]] = deque(maxlen=_NOTE_EVENT_LIMIT)
        self._note_listeners: list[Callable[[str], None]] = []

    def _add_note(self, message: str) -> None:
        """Record a degradation without erasing the previous one.

        Runs on whichever thread added the note — usually the MCP loop thread (`_serve`,
        `_serve_once`, `_on_drop`, `_emit_tools_changed`'s failure path), but also the caller's
        own thread (`start`, `stop_server`, `_ensure_loop`) — so every listener registered via
        `add_note_listener` must be thread-safe and non-blocking, and must never call back into
        `_add_note` itself (that would recurse under `_notes_lock`).

        `notes`/`note` keep their existing dedup (startup-note rendering and pre-existing tests
        depend on it seeing each distinct message once). The event log behind `notes_since`
        does NOT dedup — every call appends and fires listeners, so a repeat outage (the same
        "reconnecting (attempt 1 of N)" text twice) is never swallowed.
        """
        with self._notes_lock:
            if message not in self.notes:
                self.notes.append(message)
            self.note = "\n".join(self.notes)
            self._note_seq += 1
            self._note_events.append((self._note_seq, message))
            listeners = list(self._note_listeners)
        for listener in listeners:
            try:
                listener(message)
            except Exception:  # noqa: BLE001 - a listener failure must never wedge _add_note
                logger.debug("MCP note listener failed", exc_info=True)

    def add_note_listener(self, listener: Callable[[str], None]) -> None:
        """Register ``listener(message)`` to be called on every `_add_note`, repeats included.

        Called on whichever thread adds the note (see `_add_note`'s docstring) — the listener
        must be thread-safe and non-blocking. No-op if `listener` (by equality — a bound method
        compares equal across separate attribute accesses) is already registered.
        """
        with self._notes_lock:
            if listener not in self._note_listeners:
                self._note_listeners.append(listener)

    def remove_note_listener(self, listener: Callable[[str], None]) -> None:
        """Stop delivering notes to `listener`. A no-op if it was never registered."""
        with self._notes_lock:
            if listener in self._note_listeners:
                self._note_listeners.remove(listener)

    @property
    def note_seq(self) -> int:
        """The sequence number of the most recent note event (0 if none yet)."""
        with self._notes_lock:
            return self._note_seq

    def notes_since(self, seq: int) -> tuple[int, list[str]]:
        """Every note event strictly after `seq`, in order — NOT deduped.

        Returns ``(current_seq, messages)``; a caller polls by remembering `current_seq` and
        passing it back next time. Only the most recent `_NOTE_EVENT_LIMIT` events are kept.
        """
        with self._notes_lock:
            return self._note_seq, [m for s, m in self._note_events if s > seq]

    def server_status(self, name: str) -> str | None:
        """A human-readable non-connected status for `name`, or None if connected/unknown.

        The small public accessor the TUI/`--plain` use for `/tools` and its equivalents —
        callers must not read `_server_state`/`_disconnect_cause`/`_reconnect_attempt` directly.
        """
        state = self._server_state.get(name)
        if state == "reconnecting":
            attempt = self._reconnect_attempt.get(name, 1)
            cause = self._disconnect_cause.get(name, "the transport closed")
            return f"reconnecting (attempt {attempt} of {_MAX_RECONNECT_ATTEMPTS}): {cause}"
        if state == "disconnected":
            cause = self._disconnect_cause.get(name, "the transport closed")
            return f"disconnected: {cause}"
        return None

    def server_statuses(self) -> dict[str, str]:
        """Every known server that is NOT currently connected, name -> status text, sorted.

        "Known" means configured (`self.servers`) or previously seen dropping/reconnecting
        (`self._server_state`) — a server with neither a live session nor a recorded state
        (never started, or stopped) reports as ``"not connected"``. Connected servers are
        omitted entirely.
        """
        names = sorted(set(list(self.servers)) | set(list(self._server_state)))
        statuses: dict[str, str] = {}
        for name in names:
            status = self.server_status(name)
            if status is not None:
                statuses[name] = status
                continue
            if name not in self._sessions and self._server_state.get(name) != "connected":
                statuses[name] = "not connected"
        return statuses

    def _server_cfg(self, server: str) -> MCPServerConfig | None:
        """The cfg governing ``server``'s limits: the one actually launched, else configured."""
        return self._active_cfg.get(server) or self.servers.get(server)

    def _call_timeout_for(self, server: str) -> float:
        cfg = self._server_cfg(server)
        return cfg.call_timeout_s if cfg is not None else DEFAULT_MCP_CALL_TIMEOUT_S

    def _max_result_chars_for(self, server: str) -> int:
        cfg = self._server_cfg(server)
        return cfg.max_result_chars if cfg is not None else DEFAULT_MCP_MAX_RESULT_CHARS

    def _emit_tools_changed(self, name: str, removed: list[Tool], added: list[Tool]) -> None:
        """Call ``on_tools_changed`` if set. Never raises — this runs on the loop thread."""
        if self.on_tools_changed is None:
            return
        try:
            self.on_tools_changed(name, removed, added)
        except Exception as exc:  # noqa: BLE001 - a listener failure must not wedge the manager
            self._add_note(f"MCP server '{name}': tool-registry update failed: {exc}")

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
        timeout: float | None = None,
        overrides: dict[str, str] | None = None,
    ) -> list[Tool]:
        """Open one server's transport and return its tools. Blocks the caller until ready.

        Raises on connection failure or timeout — the connection-test modal surfaces it verbatim
        (D-19/D-20). On success the server's owning task stays parked until `stop_server`.
        ``timeout`` defaults to ``cfg.connect_timeout_s``; an explicit value (the TUI connection
        test's own cap) wins.
        """
        self._ensure_loop()
        assert self._loop is not None
        if name in self._tasks:
            self.stop_server(name)
        resolved = _resolve_server_secrets(cfg, overrides)
        budget = timeout if timeout is not None else cfg.connect_timeout_s
        self._active_cfg[name] = cfg
        fut = asyncio.run_coroutine_threadsafe(self._launch(name, resolved), self._loop)
        try:
            tools = fut.result(timeout=budget)
        except Exception as exc:
            timed_out = isinstance(exc, TimeoutError) and not fut.done()
            if timed_out:
                self._abort_launch(name, fut)
            self._tasks.pop(name, None)
            self._close_events.pop(name, None)
            self._server_tools.pop(name, None)
            self._active_cfg.pop(name, None)
            if timed_out:
                raise MCPTimeout(
                    name,
                    f"MCP server '{name}' did not finish connecting within {budget:g}s "
                    f"(connect_timeout_s); if it is slow rather than hung, raise "
                    f"connect_timeout_s under [mcp.servers.{name}].",
                ) from exc
            raise
        return tools

    def _abort_launch(self, name: str, fut: Any) -> None:
        """Cancel a first connect that overran its budget, so it can never mount tools later.

        Runs the pop+cancel ON the loop thread: `_launch` registers the task synchronously on
        that thread, so doing it there cannot interleave with `_launch` half-way through.
        """
        fut.cancel()
        loop = self._loop
        if loop is None:
            return

        async def _abort() -> None:
            task = self._tasks.pop(name, None)
            self._close_events.pop(name, None)
            if task is not None:
                task.cancel()

        with suppress(Exception):
            asyncio.run_coroutine_threadsafe(_abort(), loop).result(timeout=5)

    async def _launch(self, name: str, cfg: MCPServerConfig) -> list[Tool]:
        close_event = asyncio.Event()
        ready: asyncio.Future = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(self._serve(name, cfg, ready, close_event))
        self._tasks[name] = task
        self._close_events[name] = close_event
        return await ready

    async def _serve_once(
        self,
        name: str,
        cfg: MCPServerConfig,
        ready: asyncio.Future,
        close_event: asyncio.Event,
        reconnecting: bool = False,
    ) -> _SessionEnd:
        """One connection attempt: opens its OWN AsyncExitStack and lets it unwind here.

        anyio binds each transport's cancel scope to the task that entered it, so `aclose()` may
        only run in that same task (python-sdk issues #79/#922). Parking on `close_event` (raced
        against the transport's own end-of-stream signal) and letting the `async with` unwind in
        place is what makes per-server teardown legal.
        """
        from contextlib import AsyncExitStack

        ClientSession = _get_client_session()

        died = asyncio.Event()
        last_error: list[BaseException] = []

        async def _on_message(message: Any) -> None:
            if isinstance(message, Exception):
                # Recorded for the note only — a single malformed line is not a death (see
                # 12-RESEARCH.md: a real transport drop is observed as end-of-stream, not an
                # Exception item delivered here). Server notifications stay dropped exactly as
                # the SDK default does; list_changed routing is MCP-24.
                last_error[:] = [message]

        connected = False
        tools: list[Tool] = []
        dropped_cause: str | None = None
        # Initialized unconditionally: the final `return` below reads `stderr_tail` on every
        # exit path (sse/http, a deliberate stop, and a stdio drop alike), not only stdio.
        stderr_tail = ""
        capture: _StderrCapture | None = None
        if cfg.transport == "stdio":
            try:
                capture = _StderrCapture()
            except OSError:
                capture = None  # fall back to the terminal, exactly as before this plan
        token = _STDIO_ERRLOG.set(capture.handle if capture is not None else None)
        try:
            async with AsyncExitStack() as stack:
                streams = await stack.enter_async_context(
                    _open_transport(cfg, self.env_passthrough)
                )
                # sse/stdio yield (read, write); streamable HTTP yields a 3rd
                # get_session_id we don't need — take the first two either way.
                read = _EOFWatchStream(streams[0], died.set)
                write = streams[1]
                session = await stack.enter_async_context(
                    ClientSession(read, write, message_handler=_on_message)
                )
                await session.initialize()
                listed = await session.list_tools()
                tools = [
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
                self._server_state[name] = "connected"
                connected = True
                if not ready.done():
                    ready.set_result(tools)
                if reconnecting and not close_event.is_set():
                    self._reconnect_attempt.pop(name, None)
                    self._disconnect_cause.pop(name, None)
                    self._add_note(
                        f"MCP server '{name}' reconnected; {len(tools)} tool(s) re-registered."
                    )
                    self._emit_tools_changed(name, [], tools)

                stop_wait = asyncio.ensure_future(close_event.wait())
                died_wait = asyncio.ensure_future(died.wait())
                try:
                    await asyncio.wait({stop_wait, died_wait}, return_when=asyncio.FIRST_COMPLETED)
                finally:
                    stop_wait.cancel()
                    died_wait.cancel()
                # Leaving the `async with` normally here (never raising out of it) keeps anyio's
                # task groups from wrapping our own signal in an ExceptionGroup. A deliberate
                # stop wins a same-tick race because close_event.is_set() is checked after wait.
                if not close_event.is_set():
                    dropped_cause = "the transport closed"
                    if last_error:
                        dropped_cause += f" after {_describe(last_error[0])}"
        except Exception as exc:
            if connected and not close_event.is_set():
                # A post-connect failure escaping the transport's own task group is a drop.
                dropped_cause = _describe(exc)
            elif not connected:
                # Connect-time failure — the caller (start_server) decides what to do. The
                # `async with` has already unwound here, so the child (if any) has exited and
                # its stderr is flushed — attach the tail as a PEP 678 note for
                # `describe_start_failure` to read back out at the `start()` call site.
                if capture is not None and (tail := capture.tail()):
                    exc.add_note(_STDERR_NOTE_PREFIX + tail)
                raise
            # else: teardown noise after a deliberate stop (research Pitfall 2) — swallow it.
        finally:
            # SC1: both dicts cleared in the same place, on every exit path.
            self._sessions.pop(name, None)
            self._server_tools.pop(name, None)
            if dropped_cause is not None:
                # Set HERE, atomically with the two pops above — not left for `_serve`'s later
                # `_on_drop` call — so a caller on another thread that polls `_sessions` (or
                # `server_status()`) for "the session is gone" never observes that with no
                # reason attached. The stderr-capture I/O below is a real (GIL-releasing)
                # syscall on Windows; without this, that alone was enough to let another thread
                # observe an empty `_sessions` next to a still-unset `_server_state`. `_on_drop`
                # (back in `_serve`) re-sets both — harmless — and owns the note/emit.
                self._server_state[name] = "disconnected"
                self._disconnect_cause[name] = dropped_cause
            _STDIO_ERRLOG.reset(token)
            if capture is not None:
                if dropped_cause is not None:
                    # A short tail for the mid-session drop note (_on_drop) — the full 20-line
                    # tail already went into the start-failure note above, when applicable.
                    stderr_tail = capture.tail(max_lines=3, max_bytes=512)
                capture.close()
        return _SessionEnd(dropped_cause, tools, stderr_tail)

    async def _serve(
        self, name: str, cfg: MCPServerConfig, ready: asyncio.Future, close_event: asyncio.Event
    ) -> None:
        """Own one server for its whole life: connect, park, and on a drop reconnect (MCP-23).

        A first-connect failure is surfaced to start_server() and never retried. A drop after a
        successful connect is retried up to _MAX_RECONNECT_ATTEMPTS times with backoff; a
        successful reconnect resets that budget. stop_server()/close() set close_event, which wins
        over any drop and also cuts a backoff sleep short — a deliberate stop is never retried.
        Secrets are NOT re-resolved per attempt: cfg was resolved once by start_server(); rotating
        credentials are workstream B's concern.
        """
        attempt = 0
        reconnecting = False
        while True:
            try:
                end = await self._serve_once(
                    name, cfg, ready, close_event, reconnecting=reconnecting
                )
            except BaseException as exc:  # noqa: BLE001
                if not ready.done():
                    if isinstance(exc, asyncio.CancelledError):
                        # An orphaned connect's own task was cancelled by _abort_launch
                        # (MCP-21's connect-timeout budget) — ready may already be cancelled
                        # too (Task.cancel() cancels the future it's parked on); do not try to
                        # set an exception on a future that may already be done/cancelled.
                        return
                    ready.set_exception(exc)  # first connect: unchanged, no retry
                    return
                if not isinstance(exc, Exception) or close_event.is_set():
                    return  # cancellation / interpreter exit, or a stop that raced the attempt
                cause = _describe(exc)  # a reconnect attempt failed to connect
            else:
                if end.cause is None:  # deliberate stop_server()/close()
                    if reconnecting:
                        # These tools reached the registry via on_tools_changed, not via the
                        # caller that is stopping us — take them back out (identity-checked, so
                        # harmless if remove_mcp_server already did).
                        self._emit_tools_changed(name, end.tools, [])
                    return
                cause = end.cause
                attempt = 0  # it was connected: this outage gets a fresh budget
                self._on_drop(name, cause, end.tools, end.stderr_tail)
            attempt += 1
            if attempt > _MAX_RECONNECT_ATTEMPTS:
                self._server_state[name] = "disconnected"
                self._disconnect_cause[name] = cause
                self._reconnect_attempt.pop(name, None)
                self._add_note(
                    f"MCP server '{name}' disconnected and did not reconnect after "
                    f"{_MAX_RECONNECT_ATTEMPTS} attempts: {cause}"
                )
                return
            self._server_state[name] = "reconnecting"
            self._reconnect_attempt[name] = attempt
            self._disconnect_cause[name] = cause
            self._add_note(
                f"MCP server '{name}' disconnected ({cause}); reconnecting "
                f"(attempt {attempt} of {_MAX_RECONNECT_ATTEMPTS})."
            )
            try:
                await asyncio.wait_for(close_event.wait(), timeout=_reconnect_backoff(attempt))
                return  # stop_server() during the backoff
            except TimeoutError:
                pass
            reconnecting = True

    def _on_drop(self, name: str, cause: str, tools: list[Tool], stderr_tail: str = "") -> None:
        """Record and announce a mid-session drop (not a deliberate stop_server()/close())."""
        self._server_state[name] = "disconnected"
        self._disconnect_cause[name] = cause
        note = (
            f"MCP server '{name}' disconnected ({cause}); its {len(tools)} tool(s) were "
            "unregistered."
        )
        if stderr_tail:
            # Appended to the NOTE only — never to `_disconnect_cause`, which is model-facing
            # via `_unavailable_error` and must stay the short, stable cause string.
            joined = " | ".join(stderr_tail.splitlines())[:300]
            note += f" Last server stderr: {joined}"
        self._add_note(note)
        self._emit_tools_changed(name, tools, [])

    def stop_server(self, name: str, timeout: float = 10.0) -> None:
        """Signal one server's owning task to unwind its own stack, then wait for it."""
        close_event = self._close_events.pop(name, None)
        task = self._tasks.pop(name, None)
        self._server_tools.pop(name, None)
        self._server_state.pop(name, None)
        self._disconnect_cause.pop(name, None)
        self._reconnect_attempt.pop(name, None)
        self._active_cfg.pop(name, None)
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
        # A snapshot: the loop thread mutates _server_tools asynchronously, and iterating the
        # live dict from the main thread could raise "dictionary changed size during iteration".
        return [tool for tools in list(self._server_tools.values()) for tool in tools]

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
                self._add_note(
                    f"MCP server '{name}' failed to start: {describe_start_failure(exc)}"
                )

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _unavailable_error(
        self, server: str, cause: BaseException | None = None
    ) -> MCPServerUnavailable:
        """The single source of every "no live session" message (exact strings; MCP-26 SC2).

        Tests and plan 12-03's reconnect loop depend on these exact strings — change them there
        too if you change them here.
        """
        state = self._server_state.get(server)
        if state == "reconnecting":
            reason = self._disconnect_cause.get(server, "the transport closed")
            attempt = self._reconnect_attempt.get(server, 1)
            message = (
                f"MCP server '{server}' disconnected ({reason}) and is reconnecting "
                f"(attempt {attempt} of {_MAX_RECONNECT_ATTEMPTS}); try again shortly."
            )
        elif state == "disconnected":
            reason = self._disconnect_cause.get(server, "the transport closed")
            message = (
                f"MCP server '{server}' disconnected ({reason}); its tools are unavailable "
                "until it is restarted from /config mcp."
            )
        elif state == "connected" and cause is not None:
            message = (
                f"MCP server '{server}' closed the connection during the call "
                f"({_describe(cause)})."
            )
        else:
            message = f"MCP server '{server}' is not connected."
        return MCPServerUnavailable(server, message)

    def _await_result(self, server: str, fut: Any, what: str) -> Any:
        """Wait for ``fut`` within the server's call_timeout_s; name the server on every failure."""
        budget = self._call_timeout_for(server)
        try:
            return fut.result(timeout=budget)
        except Exception as exc:
            if isinstance(exc, TimeoutError) and not fut.done():
                fut.cancel()  # don't leave the request running on the loop
                if self._server_state.get(server) != "connected":
                    raise self._unavailable_error(server, exc) from exc
                raise MCPTimeout(
                    server,
                    f"MCP server '{server}' did not answer {what} within {budget:g}s "
                    f"(call_timeout_s); if it is slow rather than hung, raise call_timeout_s "
                    f"under [mcp.servers.{server}].",
                ) from exc
            if self._server_state.get(server) != "connected" or _is_connection_closed(exc):
                raise self._unavailable_error(server, exc) from exc
            raise

    def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        loop = self._loop
        session = self._sessions.get(server)
        if loop is None or session is None:
            raise self._unavailable_error(server)

        async def _call() -> str:
            result = await session.call_tool(tool, arguments)
            return _content_to_text(result)

        return self._await_result(
            server, asyncio.run_coroutine_threadsafe(_call(), loop), f"'{tool}'"
        )

    def _on_session(
        self,
        server: str,
        call: Callable[[Any], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Run ``call(session)`` on the MCP event loop and return its result.

        The synchronous entry point every capability call site shares — same guard, same
        ``run_coroutine_threadsafe(...).result(timeout=...)`` shape ``call_tool`` already uses.
        The budget is the server's ``call_timeout_s`` (MCP-21), shared with ``call_tool``.
        Unavailable-session errors name the server (MCP-26).
        """
        loop = self._loop
        session = self._sessions.get(server)
        if loop is None or session is None:
            raise self._unavailable_error(server)
        return self._await_result(
            server, asyncio.run_coroutine_threadsafe(call(session), loop), "a capability request"
        )

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
        self._server_state.clear()
        self._disconnect_cause.clear()
        self._reconnect_attempt.clear()


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
        # `_STDIO_ERRLOG` is a ContextVar, not a new parameter here: many tests replace
        # `_open_transport` with a bare `(cfg, env_passthrough=None)` fake, so the call site in
        # `_serve_once` must keep calling this function with exactly those two arguments. When
        # unset (a direct caller, e.g. a unit test that calls this function itself), the default
        # path is byte-for-byte unchanged — the SDK's own `errlog=sys.stderr`.
        errlog = _STDIO_ERRLOG.get()
        return stdio_client(params, errlog=errlog) if errlog is not None else stdio_client(params)
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
    "MCPServerUnavailable",
    "MCPSubscribeResourceTool",
    "MCPTool",
    "MCPUnsubscribeResourceTool",
    "build_mcp",
    "describe_start_failure",
    "stdio_env",
    "_resolve_server_secrets",
    "unresolved_var_refs",
]
