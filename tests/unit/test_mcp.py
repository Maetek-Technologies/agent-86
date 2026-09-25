"""Phase 6 — MCP client wiring (no live server)."""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import logging
import time
from dataclasses import dataclass
from typing import Any

import pytest

from agent86.config import MCPServerConfig, load_config
from agent86.tools.mcp_client import (
    MCPListResourcesTool,
    MCPManager,
    MCPServerUnavailable,
    MCPTool,
    _open_transport,
    _sanitize,
    build_mcp,
    describe_start_failure,
)
from agent86.types import ToolCall


def test_build_mcp_none_without_servers():
    assert build_mcp(load_config()) is None


def test_manager_start_is_noop_without_servers():
    m = MCPManager({})
    m.start()
    assert m.tools() == []
    m.close()


def test_sanitize_tool_name():
    assert _sanitize("my server.do/thing") == "my_server_do_thing"


def test_mcp_tool_name_and_delegation():
    class FakeManager:
        def __init__(self):
            self.called = None

        def call_tool(self, server, tool, arguments):
            self.called = (server, tool, arguments)
            return "result text"

    mgr = FakeManager()
    schema = {"type": "object", "properties": {}}
    tool = MCPTool(mgr, "myserver", "do_thing", "does a thing", schema)
    assert tool.name == "mcp__myserver__do_thing"
    assert tool.spec().side_effecting is True

    res = tool.run(ToolCall(id="1", name=tool.name, arguments={"x": 1}), ctx=None)
    assert res.ok and res.content == "result text"
    assert mgr.called == ("myserver", "do_thing", {"x": 1})


def test_mcp_tool_run_handles_error():
    class FailManager:
        def call_tool(self, *a):
            raise RuntimeError("boom")

    tool = MCPTool(FailManager(), "s", "t", "", {})
    res = tool.run(ToolCall(id="1", name="x", arguments={}), ctx=None)
    assert not res.ok and "boom" in (res.error or "")


# --- transport config: inference & validation ------------------------------- #


def test_transport_defaults_to_stdio_for_command():
    assert MCPServerConfig(command="mcp-server").transport == "stdio"


def test_transport_defaults_to_http_for_url():
    assert MCPServerConfig(url="https://example.com/mcp").transport == "http"


def test_transport_streamable_http_alias_normalizes():
    cfg = MCPServerConfig(url="https://x/mcp", transport="streamable-http")
    assert cfg.transport == "http"


def test_transport_sse_explicit():
    assert MCPServerConfig(url="https://x/sse", transport="sse").transport == "sse"


def test_rejects_both_command_and_url():
    with pytest.raises(ValueError, match="both"):
        MCPServerConfig(command="x", url="https://y/mcp")


def test_rejects_neither_command_nor_url():
    with pytest.raises(ValueError, match="command.*stdio.*url|url.*sse"):
        MCPServerConfig()


def test_rejects_unknown_transport():
    with pytest.raises(ValueError, match="unknown MCP transport"):
        MCPServerConfig(url="https://x", transport="carrier-pigeon")


def test_rejects_stdio_without_command():
    with pytest.raises(ValueError):
        MCPServerConfig(url="https://x", transport="stdio")


def test_rejects_http_without_url():
    with pytest.raises(ValueError):
        MCPServerConfig(command="x", transport="http")


def test_open_transport_selects_client_per_transport():
    # stdio -> a stdio_client context manager; url transports -> their respective clients.
    stdio_cm = _open_transport(MCPServerConfig(command="echo", args=["hi"]))
    assert "stdio" in type(stdio_cm).__module__ or hasattr(stdio_cm, "__aenter__")

    sse_cm = _open_transport(MCPServerConfig(url="https://x/sse", transport="sse"))
    assert hasattr(sse_cm, "__aenter__")

    http_cm = _open_transport(MCPServerConfig(url="https://x/mcp", transport="http"))
    assert hasattr(http_cm, "__aenter__")


# --- Wave 0 scaffolds: ToolRegistry.unregister + per-server MCPManager lifecycle (MCP-01) ----- #


def test_registry_unregister_removes_a_tool():
    from agent86.tools.registry import ToolRegistry

    registry = ToolRegistry()
    tool = MCPTool(FakeManager(), "srv", "do_thing", "does a thing", {})
    registry.register(tool)
    assert registry.unregister(tool.name) is True
    assert tool.name not in registry.names()
    assert registry.get(tool.name) is None


def test_registry_unregister_unknown_returns_false():
    from agent86.tools.registry import ToolRegistry

    registry = ToolRegistry()
    assert registry.unregister("nope") is False


class FakeManager:
    def __init__(self):
        self.called = None

    def call_tool(self, server, tool, arguments):
        self.called = (server, tool, arguments)
        return "result text"


def test_manager_start_server_registers_tools_for_lookup(monkeypatch):
    from contextlib import asynccontextmanager

    import agent86.tools.mcp_client as mcp_client

    @asynccontextmanager
    async def _fake_open_transport(cfg, env_passthrough=None):
        yield (object(), object())

    class _FakeTool:
        def __init__(self, name):
            self.name = name
            self.description = f"does {name}"
            self.inputSchema = {}

    class _FakeListed:
        tools = [_FakeTool("alpha"), _FakeTool("beta")]

    class _FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def initialize(self):
            return None

        async def list_tools(self):
            return _FakeListed()

    monkeypatch.setattr(mcp_client, "_open_transport", _fake_open_transport)
    monkeypatch.setattr(mcp_client, "ClientSession", _FakeSession, raising=False)

    manager = MCPManager({})
    cfg = MCPServerConfig(command="npx")
    tools = manager.start_server("srv", cfg)
    assert len(tools) == 2
    assert {t.name for t in tools} == {t.name for t in manager.tools_for("srv")}


def test_manager_stop_server_drops_its_tools(monkeypatch):
    from contextlib import asynccontextmanager

    import agent86.tools.mcp_client as mcp_client

    @asynccontextmanager
    async def _fake_open_transport(cfg, env_passthrough=None):
        yield (object(), object())

    class _FakeTool:
        def __init__(self, name):
            self.name = name
            self.description = f"does {name}"
            self.inputSchema = {}

    class _FakeListed:
        tools = [_FakeTool("alpha")]

    class _FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def initialize(self):
            return None

        async def list_tools(self):
            return _FakeListed()

    monkeypatch.setattr(mcp_client, "_open_transport", _fake_open_transport)
    monkeypatch.setattr(mcp_client, "ClientSession", _FakeSession, raising=False)

    manager = MCPManager({})
    cfg = MCPServerConfig(command="npx")
    manager.start_server("srv", cfg)
    manager.stop_server("srv")
    assert manager.tools_for("srv") == []
    assert "srv" not in manager._sessions


def test_manager_start_server_without_mcp_package_raises_with_note(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *a, **k):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError("no module named mcp")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    manager = MCPManager({})
    cfg = MCPServerConfig(command="npx")
    with pytest.raises(RuntimeError):
        manager.start_server("srv", cfg)
    assert manager.note is not None and 'pip install "agent86[mcp]"' in manager.note


# --- ${VAR} resolution at the transport boundary (D-17/D-25, plan 04-04) --------------------- #


def test_resolve_server_secrets_expands_env_and_headers(monkeypatch):
    from agent86.tools.mcp_client import _resolve_server_secrets

    monkeypatch.setenv("A86_T", "sekret")
    cfg = MCPServerConfig(
        command="npx",
        env={"TOKEN": "${A86_T}"},
        headers={"Authorization": "Bearer ${A86_T}"},
    )
    resolved = _resolve_server_secrets(cfg)
    assert resolved.env == {"TOKEN": "sekret"}
    assert resolved.headers == {"Authorization": "Bearer sekret"}
    # original cfg is untouched
    assert cfg.env == {"TOKEN": "${A86_T}"}
    assert cfg.headers == {"Authorization": "Bearer ${A86_T}"}


def test_resolve_server_secrets_never_expands_command(monkeypatch):
    from agent86.tools.mcp_client import _resolve_server_secrets

    monkeypatch.setenv("A86_T", "sekret")
    cfg = MCPServerConfig(command="${A86_T}")
    resolved = _resolve_server_secrets(cfg)
    assert resolved.command == "${A86_T}"


def test_resolve_server_secrets_overrides_win(monkeypatch):
    from agent86.tools.mcp_client import _resolve_server_secrets

    monkeypatch.setenv("A86_T", "from-env")
    cfg = MCPServerConfig(command="npx", env={"TOKEN": "${A86_T}"})
    resolved = _resolve_server_secrets(cfg, overrides={"A86_T": "typed"})
    assert resolved.env == {"TOKEN": "typed"}


def test_resolve_server_secrets_missing_raises(monkeypatch):
    from agent86.secrets import MissingSecretRef
    from agent86.tools.mcp_client import _resolve_server_secrets

    monkeypatch.delenv("A86_MISSING", raising=False)
    cfg = MCPServerConfig(command="npx", env={"TOKEN": "${A86_MISSING}"})
    with pytest.raises(MissingSecretRef):
        _resolve_server_secrets(cfg)


def test_unresolved_var_refs_lists_only_missing_names(monkeypatch):
    from agent86.tools.mcp_client import unresolved_var_refs

    monkeypatch.setenv("A86_HAVE", "yes")
    monkeypatch.delenv("A86_MISSING", raising=False)
    cfg = MCPServerConfig(
        command="npx",
        env={"A": "${A86_HAVE}"},
        headers={"Authorization": "Bearer ${A86_MISSING}"},
    )
    assert unresolved_var_refs(cfg) == ["A86_MISSING"]


# --- v0.7: stdio env scrubbing, note accumulation, readOnlyHint, restart -------------------- #


def _fake_tool(name, annotations=None, schema=None):
    class _T:
        pass

    t = _T()
    t.name = name
    t.description = f"does {name}"
    t.input_schema = schema or {"type": "object", "properties": {}}
    t.annotations = annotations
    return t


class _FakeResourcesCap:
    """Stand-in for mcp.types.ResourcesCapability."""

    def __init__(self, subscribe: bool = False, list_changed: bool = False):
        self.subscribe = subscribe
        self.list_changed = list_changed


class _FakePromptsCap:
    """Stand-in for mcp.types.PromptsCapability."""

    def __init__(self, list_changed: bool = False):
        self.list_changed = list_changed


class _FakeCompletionsCap:
    """Stand-in for mcp.types.CompletionsCapability (an empty marker class on the SDK)."""


class _FakeCaps:
    """Stand-in for mcp.types.ServerCapabilities.

    `None` for a field is the SDK's own "this server does not support it" signal, so the
    defaults here are all `None` — a bare `_FakeCaps()` is a server that advertises nothing.
    """

    def __init__(self, resources=None, prompts=None, completions=None, tools=None):
        self.resources = resources
        self.prompts = prompts
        self.completions = completions
        self.tools = tools


def _fake_result(**fields):
    """A duck-typed stand-in for any SDK result model: `_fake_result(resources=[...])`."""

    class _R:
        pass

    r = _R()
    for key, value in fields.items():
        setattr(r, key, value)
    return r


def _install_fake_transport(
    monkeypatch, tools, *, capabilities=None, responses=None, calls=None, init_delay: float = 0.0
):
    """Wire a fake transport + session that lists ``tools``. Returns the recorded configs.

    ``capabilities``  -> the object served as ``session.server_capabilities`` (a ``_FakeCaps``);
                         ``None`` means the attribute is absent entirely, which is what the
                         pre-Phase-11 fake did and what a capability gate must treat as "no
                         extra tools".
    ``responses``     -> {method_name: value_or_callable} answering the resource/prompt/
                         completion methods. A callable is invoked with the call's arguments.
                         An ``Exception`` VALUE is raised instead of returned, so a test can
                         drive the never-raise contract.
    ``calls``         -> an optional list the fake session appends ``(method, args, kwargs)``
                         to, so a test can assert what actually went over the wire.
    ``init_delay``    -> seconds ``initialize()`` sleeps before returning, so a test can exceed
                         a short ``connect_timeout_s``.
    """
    from contextlib import asynccontextmanager

    import agent86.tools.mcp_client as mcp_client

    seen: list = []

    @asynccontextmanager
    async def _fake_open_transport(cfg, env_passthrough=None):
        seen.append((cfg, env_passthrough))
        yield (object(), object())

    class _FakeListed:
        pass

    class _FakeSession:
        def __init__(self, *a, **k):
            if capabilities is not None:
                self.server_capabilities = capabilities

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def initialize(self):
            if init_delay:
                await asyncio.sleep(init_delay)
            return None

        async def list_tools(self):
            listed = _FakeListed()
            listed.tools = tools
            return listed

        async def _answer(self, method, *args, **kwargs):
            if calls is not None:
                calls.append((method, args, kwargs))
            value = (responses or {}).get(method)
            if callable(value):
                value = value(*args, **kwargs)
            if inspect.isawaitable(value):
                value = await value
            if isinstance(value, Exception):
                raise value
            return value

        async def call_tool(self, tool, arguments, **kw):
            return await self._answer("call_tool", tool, arguments, **kw)

        async def list_resources(self, **kw):
            return await self._answer("list_resources", **kw)

        async def list_resource_templates(self, **kw):
            return await self._answer("list_resource_templates", **kw)

        async def read_resource(self, uri, **kw):
            return await self._answer("read_resource", uri, **kw)

        async def subscribe_resource(self, uri, **kw):
            return await self._answer("subscribe_resource", uri, **kw)

        async def unsubscribe_resource(self, uri, **kw):
            return await self._answer("unsubscribe_resource", uri, **kw)

        async def list_prompts(self, **kw):
            return await self._answer("list_prompts", **kw)

        async def get_prompt(self, name, arguments=None, **kw):
            return await self._answer("get_prompt", name, arguments, **kw)

        async def complete(self, ref, argument, context_arguments=None):
            return await self._answer("complete", ref, argument, context_arguments)

    monkeypatch.setattr(mcp_client, "_open_transport", _fake_open_transport)
    monkeypatch.setattr(mcp_client, "ClientSession", _FakeSession, raising=False)
    return seen


# --- Plan 12-01: a fake transport that can really die mid-session ---------------------------- #


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    """Poll ``predicate()`` every 10ms until it's truthy or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@dataclass
class _Up:
    """One successful connection: the tool list (and optional capabilities) it offers."""

    tools: list
    caps: object | None = None
    instructions: str | None = None


class _DyingTransport:
    """Controller for a fake transport whose live connection can really be dropped.

    Unlike ``_install_fake_transport``'s cooperative fake (whose ``__aexit__``/``close_event``
    behave synchronously), this wraps a real ``anyio`` memory object stream — closing its send
    side ends the receive side's iteration exactly the way a killed stdio subprocess ends
    ``stdout_reader``'s read loop (see 12-RESEARCH.md "The empirical correction"): no exception
    reaches ``message_handler``, the stream just ends.
    """

    def __init__(
        self,
        attempts: list,
        *,
        responses: dict | None = None,
        list_delay: float = 0.0,
    ) -> None:
        self.attempts = attempts
        self.responses = responses
        self.list_delay = list_delay
        self.connects = 0
        self.list_calls = 0
        # self.call_kwargs is populated by _Session.call_tool's `**kw` (via the `transport`
        # closure, not `self` — the inner class always refers to the outer instance that way).
        self.call_kwargs: list[dict] = []
        self.list_error: Exception | None = None
        self.senders: list = []
        self.handlers: list = []
        self._current: _Up | None = None

    def install(self, monkeypatch) -> _DyingTransport:
        from contextlib import asynccontextmanager

        import agent86.tools.mcp_client as mcp_client

        transport = self

        @asynccontextmanager
        async def _open(cfg, env_passthrough=None):
            import anyio

            n = transport.connects
            transport.connects += 1
            attempt = transport.attempts[min(n, len(transport.attempts) - 1)]
            if isinstance(attempt, Exception):
                raise attempt
            send, recv = anyio.create_memory_object_stream(16)
            transport.senders.append(send)
            transport._current = attempt
            try:
                yield (recv, object())
            finally:
                send.close()
                recv.close()

        class _Session:
            def __init__(self, read, write, *a, message_handler=None, **k):
                self._read = read
                transport.handlers.append(message_handler)
                current = transport._current
                self._tools = current.tools if current is not None else []
                caps = current.caps if current is not None else None
                if caps is not None:
                    self.server_capabilities = caps
                self._instructions = current.instructions if current is not None else None
                self._reader: asyncio.Future | None = None

            async def _drain(self) -> None:
                async for _ in self._read:
                    pass

            async def __aenter__(self):
                self._reader = asyncio.ensure_future(self._drain())
                return self

            async def __aexit__(self, *exc_info):
                if self._reader is not None:
                    self._reader.cancel()
                    import contextlib

                    with contextlib.suppress(BaseException):
                        await self._reader
                return False

            async def initialize(self):
                return _fake_result(instructions=self._instructions)

            async def list_tools(self):
                transport.list_calls += 1
                if transport.list_delay:
                    await asyncio.sleep(transport.list_delay)
                if transport.list_error is not None:
                    raise transport.list_error
                listed = _fake_result()
                listed.tools = self._tools
                return listed

            async def call_tool(self, tool, arguments, **kw):
                transport.call_kwargs.append(kw)
                value = (transport.responses or {}).get("call_tool", "ok")
                if callable(value):
                    value = value(tool, arguments)
                if isinstance(value, Exception):
                    raise value
                return _fake_result(content=[_fake_result(text=str(value))])

            async def list_resources(self, **kw):
                return _fake_result(resources=[])

        monkeypatch.setattr(mcp_client, "_open_transport", _open)
        monkeypatch.setattr(mcp_client, "ClientSession", _Session, raising=False)
        return self

    def kill(self, manager: MCPManager) -> None:
        """Close the current connection's read stream from the manager's own loop thread."""
        assert manager._loop is not None
        manager._loop.call_soon_threadsafe(self.senders[-1].close)

    def deliver(self, manager: MCPManager, exc: Exception) -> None:
        """Deliver ``exc`` to the currently-installed ``message_handler``, and wait for it."""
        assert manager._loop is not None
        asyncio.run_coroutine_threadsafe(self.handlers[-1](exc), manager._loop).result(timeout=5)

    def notify(self, manager: MCPManager, notification: Any) -> None:
        """Deliver ``notification`` (e.g. an ``mcp.types.ToolListChangedNotification()``) to the
        currently-installed ``message_handler`` on the manager's loop, and wait for the handler to
        finish (the handler awaits any re-fetch inline)."""
        assert manager._loop is not None
        asyncio.run_coroutine_threadsafe(self.handlers[-1](notification), manager._loop).result(
            timeout=5
        )

    def notify_nowait(self, manager: MCPManager, notification: Any) -> concurrent.futures.Future:
        """Like ``notify`` but returns the future instead of waiting — for race tests."""
        assert manager._loop is not None
        return asyncio.run_coroutine_threadsafe(self.handlers[-1](notification), manager._loop)


def test_dying_transport_notify_reaches_the_handler(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")], instructions="be nice")]).install(
        monkeypatch
    )
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(manager, types.ToolListChangedNotification())  # must not raise
        manager.call_tool("alpha", "a", {})
        assert transport.call_kwargs and isinstance(transport.call_kwargs[-1], dict)
        assert [t.name for t in manager.tools_for("alpha")] == ["mcp__alpha__a"]
    finally:
        manager.close()


def test_death_eof_clears_sessions_and_tools(monkeypatch):
    # This test predates reconnect (MCP-23, plan 12-03): its single _Up entry is reused on every
    # retry (per _DyingTransport's "the last element repeats" contract), which would make the
    # server reconnect successfully rather than the task ever finishing. Pin no-retry so this
    # stays a pure SC1 (death is observed, both dicts clear, the task ends) regression guard.
    import agent86.tools.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", 0)
    transport = _DyingTransport([_Up([_fake_tool("a"), _fake_tool("b")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: manager.tools_for("srv") == [])
        assert manager.tools() == []
        assert "srv" not in manager._sessions
        assert manager._tasks["srv"].done()
    finally:
        manager.close()


def test_death_clears_capability_tools_too(monkeypatch):
    caps = _FakeCaps(resources=_FakeResourcesCap(), prompts=_FakePromptsCap())
    transport = _DyingTransport([_Up([_fake_tool("a")], caps=caps)]).install(monkeypatch)
    manager = MCPManager({})
    try:
        tools = manager.start_server("srv", MCPServerConfig(command="npx"))
        assert len(tools) == 6  # 1 remote + 3 resource tools + 2 prompt tools
        transport.kill(manager)
        assert _wait_until(lambda: manager.tools_for("srv") == [])
        assert manager.tools() == []
    finally:
        manager.close()


def test_death_is_recorded_as_a_named_note(monkeypatch):
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(
            lambda: any("MCP server 'srv' disconnected" in n for n in manager.notes)
        )
    finally:
        manager.close()


def test_death_notifies_tools_changed_listener(monkeypatch):
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    seen: list = []
    manager.on_tools_changed = lambda s, removed, added: seen.append(
        (s, [t.name for t in removed], list(added))
    )
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: len(seen) == 1)
        assert seen == [("srv", ["mcp__srv__a"], [])]
    finally:
        manager.close()


def test_death_transport_exception_item_alone_is_not_death(monkeypatch):
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.deliver(manager, ValueError("bad line"))
        time.sleep(0.3)
        assert manager.tools_for("srv") != []
        assert "srv" in manager._sessions
    finally:
        manager.close()


def test_death_not_reported_for_stop_server(monkeypatch):
    _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    seen: list = []
    manager.on_tools_changed = lambda *a: seen.append(a)
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        manager.stop_server("srv")
        assert not any("disconnected" in n for n in manager.notes)
        assert seen == []
    finally:
        manager.close()


def test_named_server_error_after_death(monkeypatch):
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        tools = manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: "srv" not in manager._sessions)

        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("srv", "a", {})
        assert isinstance(excinfo.value, RuntimeError)
        assert "'srv'" in str(excinfo.value)
        assert "disconnected" in str(excinfo.value)

        mcp_tool = next(t for t in tools if t.name == "mcp__srv__a")
        result = mcp_tool.run(ToolCall(id="1", name=mcp_tool.name, arguments={}), ctx=None)
        assert result.ok is False
        assert "'srv'" in (result.error or "")

        list_resources_tool = MCPListResourcesTool(manager, "srv")
        result2 = list_resources_tool.run(
            ToolCall(id="2", name=list_resources_tool.name, arguments={}), ctx=None
        )
        assert result2.ok is False
        assert "'srv'" in (result2.error or "")
    finally:
        manager.close()


def test_named_server_error_never_connected():
    manager = MCPManager({})
    with pytest.raises(RuntimeError, match=r"^MCP server 'ghost' is not connected\.$"):
        manager.call_tool("ghost", "x", {})


def test_named_server_connection_closed_mid_call(monkeypatch):
    pytest.importorskip("mcp")
    from mcp.shared.exceptions import MCPError
    from mcp.types import CONNECTION_CLOSED

    exc = MCPError(CONNECTION_CLOSED, "Connection closed")
    transport = _DyingTransport([_Up([_fake_tool("a")])], responses={"call_tool": exc})
    transport.install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("srv", "a", {})
        assert "'srv'" in str(excinfo.value)
    finally:
        manager.close()


def test_named_server_healthy_error_is_not_rewritten(monkeypatch):
    pytest.importorskip("mcp")
    from mcp.shared.exceptions import MCPError

    exc = MCPError(-32602, "bad params")
    transport = _DyingTransport([_Up([_fake_tool("a")])], responses={"call_tool": exc})
    transport.install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        with pytest.raises(MCPError) as excinfo:
            manager.call_tool("srv", "a", {})
        assert "disconnected" not in str(excinfo.value)
        assert "bad params" in str(excinfo.value)
    finally:
        manager.close()


def test_fake_transport_without_capabilities_mounts_only_remote_tools(monkeypatch):
    """A session with no `server_capabilities` attribute must still mount cleanly.

    Guards the `getattr(session, "server_capabilities", None)` read plan 11-02 adds: an SDK or
    fake without the property must degrade to "no synthetic tools", never AttributeError.
    """
    _install_fake_transport(monkeypatch, [_fake_tool("alpha")])
    manager = MCPManager({})
    tools = manager.start_server("srv", MCPServerConfig(command="npx"))
    assert [t.name for t in tools] == ["mcp__srv__alpha"]
    manager.close()


def test_stdio_env_never_forwards_api_keys(monkeypatch):
    """A server declaring one env var used to receive the whole host environment."""
    from agent86.tools.mcp_client import stdio_env

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp-secret")
    cfg = MCPServerConfig(command="npx", env={"SERVER_MODE": "fast"})

    env = stdio_env(cfg)

    assert "ANTHROPIC_API_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "sk-ant-secret" not in "".join(env.values())
    assert env["SERVER_MODE"] == "fast"
    assert "PATH" in env  # the server can still find its own executables


def test_stdio_env_keeps_resolved_server_secret(monkeypatch):
    """A ${VAR} the server explicitly asked for still arrives — and nothing else does."""
    from agent86.tools.mcp_client import _resolve_server_secrets, stdio_env

    monkeypatch.setenv("A86_GH", "ghp-for-this-server")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    cfg = _resolve_server_secrets(MCPServerConfig(command="npx", env={"TOKEN": "${A86_GH}"}))

    env = stdio_env(cfg)

    assert env["TOKEN"] == "ghp-for-this-server"
    assert "ANTHROPIC_API_KEY" not in env


def test_stdio_env_honours_passthrough(monkeypatch):
    from agent86.tools.mcp_client import stdio_env

    monkeypatch.setenv("MY_BUILD_FLAVOUR", "debug")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    cfg = MCPServerConfig(command="npx")

    env = stdio_env(cfg, ["MY_BUILD_FLAVOUR", "ANTHROPIC_API_KEY"])

    assert env["MY_BUILD_FLAVOUR"] == "debug"
    assert "ANTHROPIC_API_KEY" not in env  # passthrough can't smuggle a credential


def test_stdio_transport_uses_scrubbed_env(monkeypatch):
    """The parameters handed to stdio_client carry the scrubbed env, not os.environ."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    cm = _open_transport(MCPServerConfig(command="echo", args=["hi"], env={"X": "1"}))
    params = cm.args[0]  # contextlib keeps the arguments the transport was built with
    assert params.env["X"] == "1"
    assert "ANTHROPIC_API_KEY" not in params.env
    assert "PATH" in params.env


def test_manager_passes_its_passthrough_to_the_transport(monkeypatch):
    seen = _install_fake_transport(monkeypatch, [_fake_tool("alpha")])
    manager = MCPManager({}, env_passthrough=["MY_BUILD_FLAVOUR"])
    manager.start_server("srv", MCPServerConfig(command="npx"))
    assert seen[0][1] == ["MY_BUILD_FLAVOUR"]
    manager.close()


def test_build_mcp_reads_env_passthrough_from_config(monkeypatch):
    seen = _install_fake_transport(monkeypatch, [_fake_tool("alpha")])
    cfg = load_config()
    cfg.mcp.enabled = True
    cfg.mcp_servers = {"srv": MCPServerConfig(command="npx")}
    try:
        cfg.sandbox.env_passthrough = ["MY_BUILD_FLAVOUR"]
    except (ValueError, AttributeError):  # config agent adds the field concurrently
        object.__setattr__(cfg.sandbox, "env_passthrough", ["MY_BUILD_FLAVOUR"])

    manager = build_mcp(cfg)
    assert manager is not None
    assert seen[0][1] == ["MY_BUILD_FLAVOUR"]
    manager.close()


def test_notes_accumulate_across_failing_servers(monkeypatch):
    """With several bad servers, one overwritten string hid every failure but the last."""
    from contextlib import asynccontextmanager

    import agent86.tools.mcp_client as mcp_client

    @asynccontextmanager
    async def _boom(cfg, env_passthrough=None):
        raise RuntimeError(f"cannot connect to {cfg.command}")
        yield  # pragma: no cover

    monkeypatch.setattr(mcp_client, "_open_transport", _boom)
    manager = MCPManager(
        {"alpha": MCPServerConfig(command="a"), "beta": MCPServerConfig(command="b")}
    )
    manager.start()

    assert len(manager.notes) == 2
    assert "alpha" in (manager.note or "") and "beta" in (manager.note or "")
    manager.close()


def test_read_only_hint_makes_a_tool_non_side_effecting(monkeypatch):
    class _Annotations:
        read_only_hint = True

    _install_fake_transport(
        monkeypatch,
        [_fake_tool("search", annotations=_Annotations()), _fake_tool("write_file")],
    )
    manager = MCPManager({})
    tools = {t._tool: t for t in manager.start_server("srv", MCPServerConfig(command="npx"))}

    assert tools["search"].side_effecting is False
    assert tools["search"].spec().side_effecting is False
    assert tools["write_file"].side_effecting is True
    manager.close()


def test_read_only_hint_accepts_the_wire_spelling():
    from agent86.tools.mcp_client import _is_read_only

    assert _is_read_only(_fake_tool("t", annotations={"readOnlyHint": True}))
    assert not _is_read_only(_fake_tool("t", annotations={"readOnlyHint": False}))
    assert not _is_read_only(_fake_tool("t"))


def test_tool_schema_reads_both_sdk_spellings():
    from agent86.tools.mcp_client import _tool_schema

    modern = _fake_tool("t", schema={"type": "object", "properties": {"a": {}}})
    assert _tool_schema(modern)["properties"] == {"a": {}}

    class _Legacy:
        inputSchema = {"type": "object", "properties": {"b": {}}}

    assert _tool_schema(_Legacy())["properties"] == {"b": {}}


def test_close_allows_a_later_restart(monkeypatch):
    _install_fake_transport(monkeypatch, [_fake_tool("alpha"), _fake_tool("beta")])
    manager = MCPManager({"srv": MCPServerConfig(command="npx")})

    manager.start()
    assert len(manager.tools()) == 2

    manager.close()
    assert manager.tools() == []

    manager.start()  # previously a silent no-op: _started was never reset
    assert len(manager.tools()) == 2
    manager.close()


# --- Plan 11-02: resource capability gating, blob non-inlining, wire fidelity ---------------- #


def test_resources_capability_mounts_the_three_read_tools(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("alpha")],
        capabilities=_FakeCaps(resources=_FakeResourcesCap(subscribe=False)),
    )
    manager = MCPManager({})
    names = [t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))]
    assert names == [
        "mcp__srv__alpha",  # the server's own tool comes FIRST (D-04)
        "mcp__srv__list_resources",
        "mcp__srv__read_resource",
        "mcp__srv__list_resource_templates",
    ]
    manager.close()


def test_absent_resources_capability_mounts_no_synthetic_tools(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("alpha")],
        capabilities=_FakeCaps(),  # everything None
    )
    manager = MCPManager({})
    names = [t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))]
    assert names == ["mcp__srv__alpha"]
    manager.close()


def test_resources_capability_subscribe_flag_gates_the_subscribe_tools(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("alpha")],
        capabilities=_FakeCaps(resources=_FakeResourcesCap(subscribe=True)),
    )
    manager = MCPManager({})
    names = {t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))}
    assert {
        "mcp__srv__list_resources",
        "mcp__srv__read_resource",
        "mcp__srv__list_resource_templates",
        "mcp__srv__subscribe_resource",
        "mcp__srv__unsubscribe_resource",
    } <= names
    manager.close()


def test_blob_resource_content_is_never_inlined(monkeypatch):
    blob = "QUJDREVGR0hJSg=="  # base64; must not appear in what the model sees
    contents = [
        _fake_result(uri="res://x/pic.png", mime_type="image/png", blob=blob),
    ]
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(resources=_FakeResourcesCap()),
        responses={"read_resource": lambda uri, **kw: _fake_result(contents=contents)},
    )
    manager = MCPManager({})
    tools = {t.name: t for t in manager.start_server("srv", MCPServerConfig(command="npx"))}
    result = tools["mcp__srv__read_resource"].run(
        ToolCall(id="1", name="mcp__srv__read_resource", arguments={"uri": "res://x/pic.png"}),
        ctx=None,
    )
    manager.close()
    assert result.ok
    assert blob not in result.content
    assert "image/png" in result.content and "not inlined" in result.content
    assert result.metadata["binary"] == [
        {"uri": "res://x/pic.png", "mime_type": "image/png", "base64_len": len(blob)}
    ]


def test_read_resource_sends_the_uri_over_the_wire(monkeypatch):
    calls: list = []
    contents = [_fake_result(uri="res://x/pic.png", text="hi")]
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(resources=_FakeResourcesCap()),
        responses={"read_resource": lambda uri, **kw: _fake_result(contents=contents)},
        calls=calls,
    )
    manager = MCPManager({})
    tools = {t.name: t for t in manager.start_server("srv", MCPServerConfig(command="npx"))}
    tools["mcp__srv__read_resource"].run(
        ToolCall(id="1", name="mcp__srv__read_resource", arguments={"uri": "res://x/pic.png"}),
        ctx=None,
    )
    manager.close()
    assert ("read_resource", ("res://x/pic.png",), {}) in calls


def test_read_resource_failure_is_a_soft_tool_result(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(resources=_FakeResourcesCap()),
        responses={"read_resource": RuntimeError("boom")},
    )
    manager = MCPManager({})
    tools = {t.name: t for t in manager.start_server("srv", MCPServerConfig(command="npx"))}
    result = tools["mcp__srv__read_resource"].run(
        ToolCall(id="1", name="mcp__srv__read_resource", arguments={"uri": "res://x"}),
        ctx=None,
    )
    manager.close()
    assert result.ok is False
    assert "boom" in (result.error or "")


def test_prompts_capability_mounts_the_prompt_tools(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("alpha")],
        capabilities=_FakeCaps(prompts=_FakePromptsCap()),
    )
    manager = MCPManager({})
    names = [t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))]
    assert names == [
        "mcp__srv__alpha",  # the server's own tool comes FIRST (D-04)
        "mcp__srv__list_prompts",
        "mcp__srv__get_prompt",
    ]
    manager.close()


def test_completions_capability_mounts_only_the_complete_tool(monkeypatch):
    _install_fake_transport(
        monkeypatch, [], capabilities=_FakeCaps(completions=_FakeCompletionsCap())
    )
    manager = MCPManager({})
    names = [t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))]
    assert names == ["mcp__srv__complete"]
    manager.close()


def test_absent_prompts_capability_mounts_no_prompt_tools(monkeypatch):
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("alpha")],
        capabilities=_FakeCaps(),  # everything None
    )
    manager = MCPManager({})
    names = [t.name for t in manager.start_server("srv", MCPServerConfig(command="npx"))]
    assert names == ["mcp__srv__alpha"]
    manager.close()


def test_non_text_prompt_block_is_marked_not_repred(monkeypatch):
    class _Img:
        pass

    messages = [_fake_result(role="user", content=_Img())]
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(prompts=_FakePromptsCap()),
        responses={
            "get_prompt": lambda name, arguments, **kw: _fake_result(
                description=None, messages=messages
            )
        },
    )
    manager = MCPManager({})
    tools = {t.name: t for t in manager.start_server("srv", MCPServerConfig(command="npx"))}
    result = tools["mcp__srv__get_prompt"].run(
        ToolCall(id="1", name="mcp__srv__get_prompt", arguments={"name": "review_code"}),
        ctx=None,
    )
    manager.close()
    assert result.ok
    assert "non-text content block:" in result.content
    assert "object at 0x" not in result.content
    assert "<" not in result.content


def test_complete_sends_a_prompt_reference_over_the_wire(monkeypatch):
    calls: list = []
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(completions=_FakeCompletionsCap()),
        responses={
            "complete": lambda ref, argument, context: _fake_result(
                completion=_fake_result(values=["concise"], total=1, has_more=False)
            )
        },
        calls=calls,
    )
    manager = MCPManager({})
    tool = manager.start_server("srv", MCPServerConfig(command="npx"))[0]
    result = tool.run(
        ToolCall(
            id="1",
            name="mcp__srv__complete",
            arguments={
                "ref_type": "prompt",
                "ref": "review_code",
                "argument_name": "style",
                "argument_value": "c",
            },
        ),
        ctx=None,
    )
    manager.close()
    assert result.ok and result.content == "concise"
    method, args, _ = next(c for c in calls if c[0] == "complete")
    ref, argument, _context = args
    assert ref.name == "review_code" and ref.type == "ref/prompt"
    assert argument == {"name": "style", "value": "c"}


# --- Plan 12-03: bounded reconnect after a drop (MCP-23) ------------------------------------- #


def _patch_reconnect(monkeypatch, *, max_attempts=3, backoff=lambda attempt: 0.0):
    """Every reconnect test wants a fast, deterministic budget unless it says otherwise."""
    import agent86.tools.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", max_attempts)
    monkeypatch.setattr(mcp_client, "_reconnect_backoff", backoff)


def test_reconnect_after_drop_restores_tools(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a]), _Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: "srv" in manager._sessions and transport.connects == 2)
        assert [t.name for t in manager.tools_for("srv")] == ["mcp__srv__a"]
        assert transport.connects == 2
        assert manager.call_tool("srv", "a", {}) == "ok"
        assert any("MCP server 'srv' reconnected" in n for n in manager.notes)
    finally:
        manager.close()


def test_reconnect_repopulates_from_fresh_list_tools_and_capabilities(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    b = _fake_tool("b")
    transport = _DyingTransport(
        [_Up([a]), _Up([b], caps=_FakeCaps(prompts=_FakePromptsCap()))]
    ).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(
            lambda: (
                {t.name for t in manager.tools_for("srv")}
                == {"mcp__srv__b", "mcp__srv__list_prompts", "mcp__srv__get_prompt"}
            )
        )
        assert transport.list_calls == 2
    finally:
        manager.close()


def test_reconnect_gives_up_after_bounded_attempts(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a]), RuntimeError("refused")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: manager._tasks["srv"].done())
        assert transport.connects == 1 + 3
        assert manager._server_state["srv"] == "disconnected"
        assert manager.tools_for("srv") == []
        assert any("did not reconnect after 3 attempts" in n for n in manager.notes)
        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("srv", "a", {})
        assert "'srv'" in str(excinfo.value)
    finally:
        manager.close()


def test_reconnect_notes_each_attempt(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a]), RuntimeError("refused")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: manager._tasks["srv"].done())
        joined = "\n".join(manager.notes)
        assert "reconnecting (attempt 1 of 3)" in joined
        assert "(attempt 2 of 3)" in joined
        assert "(attempt 3 of 3)" in joined
    finally:
        manager.close()


def test_reconnect_error_names_server_while_reconnecting(monkeypatch):
    _patch_reconnect(monkeypatch, backoff=lambda attempt: 5.0)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: manager._server_state.get("srv") == "reconnecting")
        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("srv", "a", {})
        assert "'srv'" in str(excinfo.value)
        assert "is reconnecting" in str(excinfo.value)
    finally:
        t0 = time.monotonic()
        manager.close()
        assert time.monotonic() - t0 < 3.0


def test_reconnect_stop_during_backoff_is_not_retried(monkeypatch):
    _patch_reconnect(monkeypatch, backoff=lambda attempt: 5.0)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: manager._server_state.get("srv") == "reconnecting")
        t0 = time.monotonic()
        manager.stop_server("srv")
        assert time.monotonic() - t0 < 2.0
        time.sleep(0.3)
        assert transport.connects == 1
        assert "srv" not in manager._server_state
    finally:
        manager.close()


def test_reconnect_never_follows_stop_server(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        manager.stop_server("srv")
        time.sleep(0.3)
        assert transport.connects == 1
        assert not any("reconnecting" in n for n in manager.notes)
    finally:
        manager.close()


def test_reconnect_first_connect_failure_is_not_retried(monkeypatch):
    _patch_reconnect(monkeypatch)
    transport = _DyingTransport([RuntimeError("nope")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        with pytest.raises(RuntimeError, match="nope"):
            manager.start_server("srv", MCPServerConfig(command="npx"))
        assert transport.connects == 1
    finally:
        manager.close()


def test_reconnect_emits_removed_then_added_to_listener(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    b = _fake_tool("b")
    transport = _DyingTransport([_Up([a]), _Up([b])]).install(monkeypatch)
    manager = MCPManager({})
    seen: list = []
    manager.on_tools_changed = lambda s, removed, added: seen.append(
        (s, [t.name for t in removed], [t.name for t in added])
    )
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: len(seen) == 2)
        assert seen == [
            ("srv", ["mcp__srv__a"], []),
            ("srv", [], ["mcp__srv__b"]),
        ]
    finally:
        manager.close()


def test_reconnect_resets_budget_after_success(monkeypatch):
    _patch_reconnect(monkeypatch, max_attempts=1)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a]), _Up([a]), _Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: "srv" in manager._sessions and transport.connects == 2)
        transport.kill(manager)
        assert _wait_until(lambda: "srv" in manager._sessions and transport.connects == 3)
    finally:
        manager.close()


def test_reconnect_backoff_is_bounded_and_jittered():
    import agent86.tools.mcp_client as mcp_client

    assert mcp_client._reconnect_backoff(1, jitter=lambda lo, hi: hi) == 1.0
    assert mcp_client._reconnect_backoff(1, jitter=lambda lo, hi: lo) == 0.5
    assert (
        mcp_client._reconnect_backoff(20, jitter=lambda lo, hi: hi)
        == mcp_client._RECONNECT_MAX_DELAY_S
    )


# --- Plan 12-08 Task 1: note listeners, sequenced note log, server-status accessors --------- #


def test_note_listener_fires_for_every_event_even_duplicates():
    manager = MCPManager({})
    received: list[str] = []
    manager.add_note_listener(received.append)
    manager._add_note("x")
    manager._add_note("x")
    assert manager.notes == ["x"]  # notes/note keep their existing dedup
    assert received == ["x", "x"]  # the event log/listeners do NOT dedup
    assert manager.notes_since(0) == (2, ["x", "x"])
    assert manager.notes_since(1) == (2, ["x"])
    assert manager.note_seq == 2


def test_note_listener_exception_never_propagates():
    manager = MCPManager({})
    received: list[str] = []

    def _boom(message: str) -> None:
        raise RuntimeError("boom")

    manager.add_note_listener(_boom)
    manager.add_note_listener(received.append)
    manager._add_note("x")  # must not raise
    assert received == ["x"]  # the second listener still ran


def test_remove_note_listener_stops_delivery():
    manager = MCPManager({})
    received: list[str] = []
    manager.add_note_listener(received.append)
    manager._add_note("x")
    manager.remove_note_listener(received.append)
    manager._add_note("y")
    assert received == ["x"]
    manager.remove_note_listener(lambda m: None)  # unknown listener: a no-op, never raises


def test_repeated_outages_surface_every_reconnecting_note(monkeypatch):
    _patch_reconnect(monkeypatch)
    a = _fake_tool("a")
    transport = _DyingTransport([_Up([a]), _Up([a]), _Up([a])]).install(monkeypatch)
    manager = MCPManager({})
    received: list[str] = []
    manager.add_note_listener(received.append)
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        transport.kill(manager)
        assert _wait_until(lambda: "srv" in manager._sessions and transport.connects == 2)
        transport.kill(manager)
        assert _wait_until(lambda: "srv" in manager._sessions and transport.connects == 3)
        assert sum("reconnecting (attempt 1 of 3)" in m for m in received) == 2
        assert sum("reconnected" in m for m in received) == 2
    finally:
        manager.close()


def test_server_status_formats_each_state():
    manager = MCPManager({})
    manager.servers = {"idle": MCPServerConfig(command="x")}
    manager._server_state["reco"] = "reconnecting"
    manager._reconnect_attempt["reco"] = 2
    manager._disconnect_cause["reco"] = "c"
    assert manager.server_status("reco") == "reconnecting (attempt 2 of 5): c"

    manager._server_state["dead"] = "disconnected"
    manager._disconnect_cause["dead"] = "c"
    assert manager.server_status("dead") == "disconnected: c"

    manager._server_state["live"] = "connected"
    assert manager.server_status("live") is None
    assert manager.server_status("unknown") is None

    assert manager.server_statuses() == {
        "dead": "disconnected: c",
        "idle": "not connected",
        "reco": "reconnecting (attempt 2 of 5): c",
    }


# --- Plan 12-08 Task 2: ExceptionGroup unwrapping + the stdio child's stderr tail ------------ #


def test_describe_start_failure_unwraps_nested_exception_groups():
    exc = ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [ExceptionGroup("unhandled errors in a TaskGroup", [RuntimeError("Connection closed")])],
    )
    assert describe_start_failure(exc) == "RuntimeError: Connection closed"


def test_describe_start_failure_joins_distinct_leaves():
    exc = ExceptionGroup(
        "unhandled errors in a TaskGroup", [RuntimeError("a"), ValueError("a"), RuntimeError("a")]
    )
    # Three leaves, one duplicate description -> two unique, order-preserving, joined by "; ".
    assert describe_start_failure(exc) == "RuntimeError: a; ValueError: a"


def test_describe_start_failure_keeps_plain_exception_text():
    assert describe_start_failure(RuntimeError("boom")) == "boom"
    assert describe_start_failure(RuntimeError()) == "RuntimeError"


def test_describe_start_failure_appends_stderr_tail():
    import agent86.tools.mcp_client as mcp_client

    exc = RuntimeError("boom")
    exc.add_note(mcp_client._STDERR_NOTE_PREFIX + "line1\nboom-marker")
    result = describe_start_failure(exc)
    assert "boom-marker" in result
    assert "stderr" in result


def test_stderr_capture_tail_and_close():
    import os

    import agent86.tools.mcp_client as mcp_client

    capture = mcp_client._StderrCapture()
    for i in range(30):
        capture.handle.write(f"line{i}\n")
    capture.handle.flush()
    lines = capture.tail().splitlines()
    assert len(lines) == 20
    assert lines[0] == "line10"
    assert lines[-1] == "line29"
    capture.close()
    assert not os.path.exists(capture.path)
    assert capture.tail() == ""  # never raises, even once the file is gone


def test_start_note_has_no_taskgroup_wrapper(monkeypatch):
    from contextlib import asynccontextmanager

    import agent86.tools.mcp_client as mcp_client

    @asynccontextmanager
    async def _fake_open_transport(cfg, env_passthrough=None):
        raise ExceptionGroup("unhandled errors in a TaskGroup", [RuntimeError("refused")])
        yield  # pragma: no cover - unreachable; keeps this an async generator function

    monkeypatch.setattr(mcp_client, "_open_transport", _fake_open_transport)
    manager = MCPManager({"srv": MCPServerConfig(command="npx")})
    try:
        manager.start()
        joined = "\n".join(manager.notes)
        assert "RuntimeError: refused" in joined
        assert "TaskGroup" not in joined
    finally:
        manager.close()


def test_real_sdk_tool_object_is_understood():
    """Regression guard: mcp>=2 renamed Tool.inputSchema to input_schema.

    The fakes above would happily keep a wrong attribute name working, and the live-server
    test is skipped wherever FastMCP isn't installed — so assert against the real model.
    """
    types = pytest.importorskip("mcp.types")
    from agent86.tools.mcp_client import _is_read_only, _tool_schema

    tool = types.Tool(
        name="search",
        inputSchema={"type": "object", "properties": {"q": {"type": "string"}}},
        annotations=types.ToolAnnotations(readOnlyHint=True),
    )
    assert _tool_schema(tool)["properties"] == {"q": {"type": "string"}}
    assert _is_read_only(tool) is True
    assert _is_read_only(types.Tool(name="write", inputSchema={})) is False


# --- Phase 13 plan 02: per-server connect/call timeouts (MCP-21) ---------------------------- #


def test_call_timeout_uses_per_server_config(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    cfg = MCPServerConfig(command="npx", call_timeout_s=0.3)
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: asyncio.sleep(5)},
    )
    manager = MCPManager({"srv": cfg})
    try:
        manager.start_server("srv", cfg)
        t0 = time.monotonic()
        with pytest.raises(mcp_client.MCPTimeout):
            manager.call_tool("srv", "a", {})
        assert time.monotonic() - t0 < 2.0
    finally:
        manager.close()


def test_call_timeout_error_names_server_and_field(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    cfg = MCPServerConfig(command="npx", call_timeout_s=0.3)
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: asyncio.sleep(5)},
    )
    manager = MCPManager({"srv": cfg})
    try:
        tools = manager.start_server("srv", cfg)
        with pytest.raises(mcp_client.MCPTimeout) as excinfo:
            manager.call_tool("srv", "a", {})
        message = str(excinfo.value)
        assert "'srv'" in message
        assert "0.3s" in message
        assert "call_timeout_s" in message

        mcp_tool = next(t for t in tools if t.name == "mcp__srv__a")
        result = mcp_tool.run(ToolCall(id="1", name=mcp_tool.name, arguments={}), ctx=None)
        assert result.ok is False
        assert (result.error or "").startswith("MCP call failed: MCP server 'srv'")
    finally:
        manager.close()


def test_capability_call_timeout_uses_per_server_config(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    caps = _FakeCaps(prompts=_FakePromptsCap())
    cfg = MCPServerConfig(command="npx", call_timeout_s=0.3)
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        capabilities=caps,
        responses={"list_prompts": lambda **kw: asyncio.sleep(5)},
    )
    manager = MCPManager({"srv": cfg})
    try:
        manager.start_server("srv", cfg)
        t0 = time.monotonic()
        with pytest.raises(mcp_client.MCPTimeout) as excinfo:
            manager.list_prompts("srv")
        assert time.monotonic() - t0 < 2.0
        assert "call_timeout_s" in str(excinfo.value)
    finally:
        manager.close()


def test_call_timeout_default_is_120_when_server_unconfigured(monkeypatch):
    manager = MCPManager({})
    assert manager._call_timeout_for("ghost") == 120.0

    manager2 = MCPManager({"a": MCPServerConfig(command="x", call_timeout_s=7)})
    assert manager2._call_timeout_for("a") == 7.0

    _install_fake_transport(monkeypatch, [_fake_tool("t")])
    manager3 = MCPManager({})
    try:
        manager3.start_server("b", MCPServerConfig(command="npx", call_timeout_s=9))
        assert manager3._call_timeout_for("b") == 9.0
        manager3.stop_server("b")
        assert manager3._call_timeout_for("b") == 120.0
    finally:
        manager3.close()


def test_max_result_chars_lookup_follows_the_same_order(monkeypatch):
    manager = MCPManager({})
    assert manager._max_result_chars_for("ghost") == 8000

    manager2 = MCPManager({"a": MCPServerConfig(command="x", max_result_chars=123)})
    assert manager2._max_result_chars_for("a") == 123


def test_connect_timeout_uses_per_server_config(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    _install_fake_transport(monkeypatch, [_fake_tool("a")], init_delay=5)
    manager = MCPManager({})
    try:
        t0 = time.monotonic()
        with pytest.raises(mcp_client.MCPTimeout) as excinfo:
            manager.start_server("srv", MCPServerConfig(command="npx", connect_timeout_s=0.3))
        assert time.monotonic() - t0 < 2.0
        message = str(excinfo.value)
        assert "'srv'" in message
        assert "connect_timeout_s" in message
    finally:
        manager.close()


def test_explicit_start_server_timeout_overrides_config(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    _install_fake_transport(monkeypatch, [_fake_tool("a")], init_delay=5)
    manager = MCPManager({})
    try:
        t0 = time.monotonic()
        with pytest.raises(mcp_client.MCPTimeout):
            manager.start_server(
                "srv", MCPServerConfig(command="npx", connect_timeout_s=60), timeout=0.3
            )
        assert time.monotonic() - t0 < 2.0
    finally:
        manager.close()


def test_connect_timeout_cancels_orphaned_attempt(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    _install_fake_transport(monkeypatch, [_fake_tool("a")], init_delay=0.6)
    manager = MCPManager({})
    try:
        with pytest.raises(mcp_client.MCPTimeout):
            manager.start_server("srv", MCPServerConfig(command="npx", connect_timeout_s=0.2))
        time.sleep(1.2)
        assert "srv" not in manager._sessions
        assert manager.tools_for("srv") == []
        assert "srv" not in manager._tasks
        assert manager.server_status("srv") is None
    finally:
        manager.close()


def test_timeout_during_reconnect_backoff_names_reconnecting(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    a = _fake_tool("a")
    cfg = MCPServerConfig(command="npx", call_timeout_s=0.2)
    transport = _DyingTransport([_Up([a])]).install(monkeypatch)
    monkeypatch.setattr(mcp_client, "_reconnect_backoff", lambda attempt: 5.0)
    manager = MCPManager({})
    try:
        manager.start_server("srv", cfg)
        transport.kill(manager)
        assert _wait_until(lambda: manager._server_state.get("srv") == "reconnecting")
        t0 = time.monotonic()
        with pytest.raises(MCPServerUnavailable) as excinfo:
            manager.call_tool("srv", "a", {})
        assert time.monotonic() - t0 < 1.0
        assert "is reconnecting" in str(excinfo.value)
    finally:
        manager.close()


# --- Phase 13 plan 04: the result cap and non-text content rendering (MCP-22, MCP-25) -------- #


def test_call_tool_result_truncates_at_max_result_chars(monkeypatch):
    types = pytest.importorskip("mcp.types")
    cfg = MCPServerConfig(command="npx", max_result_chars=100)
    result = types.CallToolResult(content=[types.TextContent(type="text", text="y" * 250)])
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({"srv": cfg})
    try:
        manager.start_server("srv", cfg)
        out = manager.call_tool("srv", "a", {})
        assert out.startswith("y" * 100)
        assert "…[truncated 150 chars" in out
        assert "max_result_chars" in out
        assert "'srv'" in out
        assert out.count("y") == 100
    finally:
        manager.close()


def test_result_cap_default_8000_when_unconfigured(monkeypatch):
    types = pytest.importorskip("mcp.types")

    def _respond(tool, arguments, **kw):
        n = arguments["n"]
        return types.CallToolResult(content=[types.TextContent(type="text", text="a" * n)])

    _install_fake_transport(
        monkeypatch, [_fake_tool("a")], responses={"call_tool": _respond}
    )
    manager = MCPManager({})
    try:
        cfg = MCPServerConfig(command="npx")
        manager.start_server("srv", cfg)
        over = manager.call_tool("srv", "a", {"n": 8_500})
        assert "…[truncated 500 chars" in over

        exact = manager.call_tool("srv", "a", {"n": 8_000})
        assert "truncated" not in exact
        assert exact == "a" * 8_000
    finally:
        manager.close()


def test_truncated_error_result_keeps_error_prefix(monkeypatch):
    types = pytest.importorskip("mcp.types")
    cfg = MCPServerConfig(command="npx", max_result_chars=100)
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="z" * 300)], is_error=True
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({"srv": cfg})
    try:
        manager.start_server("srv", cfg)
        out = manager.call_tool("srv", "a", {})
        assert out.startswith("ERROR: " + "z" * 100)
        assert "…[truncated 200 chars" in out
    finally:
        manager.close()


def test_call_tool_error_result_is_prefixed_on_sdk2_is_error(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="boom")], is_error=True
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert out == "ERROR: boom"
    finally:
        manager.close()


def test_read_resource_truncates_at_max_result_chars(monkeypatch):
    cfg = MCPServerConfig(command="npx", max_result_chars=50)
    contents = [_fake_result(uri="res://x/a", text="r" * 120)]
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(resources=_FakeResourcesCap()),
        responses={"read_resource": lambda uri, **kw: _fake_result(contents=contents)},
    )
    manager = MCPManager({"srv": cfg})
    try:
        tools = {t.name: t for t in manager.start_server("srv", cfg)}
        result = tools["mcp__srv__read_resource"].run(
            ToolCall(id="1", name="mcp__srv__read_resource", arguments={"uri": "res://x/a"}),
            ctx=None,
        )
        assert result.ok
        assert result.content.startswith("r" * 50)
        assert "…[truncated 70 chars" in result.content
    finally:
        manager.close()


def test_get_prompt_truncates_at_max_result_chars(monkeypatch):
    cfg = MCPServerConfig(command="npx", max_result_chars=40)
    messages = [_fake_result(role="user", content=_fake_result(text="m" * 200))]
    _install_fake_transport(
        monkeypatch,
        [],
        capabilities=_FakeCaps(prompts=_FakePromptsCap()),
        responses={
            "get_prompt": lambda name, arguments, **kw: _fake_result(
                description=None, messages=messages
            )
        },
    )
    manager = MCPManager({"srv": cfg})
    try:
        tools = {t.name: t for t in manager.start_server("srv", cfg)}
        result = tools["mcp__srv__get_prompt"].run(
            ToolCall(id="1", name="mcp__srv__get_prompt", arguments={"name": "review_code"}),
            ctx=None,
        )
        assert result.ok
        assert "…[truncated " in result.content
        assert "max_result_chars" in result.content
    finally:
        manager.close()


def test_call_tool_image_content_block_renders_marker(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[types.ImageContent(type="image", data="QUJDREVGR0g=", mime_type="image/png")]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert out == "[image content: mime_type=image/png base64_len=12 — not inlined]"
        assert "QUJDREVGR0g=" not in out
        assert "ImageContent(" not in out
    finally:
        manager.close()


def test_call_tool_audio_content_block_renders_marker(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[types.AudioContent(type="audio", data="QUJDREVGR0g=", mime_type="audio/wav")]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert out == "[audio content: mime_type=audio/wav base64_len=12 — not inlined]"
        assert "QUJDREVGR0g=" not in out
    finally:
        manager.close()


def test_call_tool_embedded_text_resource_is_inlined(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[
            types.EmbeddedResource(
                type="resource",
                resource=types.TextResourceContents(
                    uri="res://x/a.txt", mime_type="text/plain", text="inner"
                ),
            )
        ]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert "[embedded resource uri=" in out
        assert out.endswith("inner")
    finally:
        manager.close()


def test_call_tool_embedded_blob_resource_not_inlined(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[
            types.EmbeddedResource(
                type="resource",
                resource=types.BlobResourceContents(
                    uri="res://x/p.png", mime_type="image/png", blob="QUJD"
                ),
            )
        ]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert "base64_len=4 — not inlined" in out
        assert "QUJD" not in out
    finally:
        manager.close()


def test_call_tool_resource_link_renders_fields(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[
            types.ResourceLink(
                type="resource_link",
                name="readme",
                uri="file:///r.md",
                mime_type="text/markdown",
                size=120,
            )
        ]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert "[resource link uri=" in out
        assert "name=" in out
    finally:
        manager.close()


def test_call_tool_mixed_content_blocks_join_in_order(monkeypatch):
    types = pytest.importorskip("mcp.types")
    result = types.CallToolResult(
        content=[
            types.TextContent(type="text", text="before"),
            types.ImageContent(type="image", data="QUJD", mime_type="image/png"),
            types.TextContent(type="text", text="after"),
        ]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        lines = out.split("\n")
        assert lines[0] == "before"
        assert lines[-1] == "after"
        assert any("image content" in line for line in lines)
    finally:
        manager.close()


def test_call_tool_unknown_content_block_never_repr(monkeypatch):
    class Weird:
        pass

    result = _fake_result(content=[Weird()])
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({})
    try:
        manager.start_server("srv", MCPServerConfig(command="npx"))
        out = manager.call_tool("srv", "a", {})
        assert out == "[non-text content block: Weird — not inlined]"
    finally:
        manager.close()


def test_call_tool_images_are_never_inlined_even_under_cap(monkeypatch):
    types = pytest.importorskip("mcp.types")
    cfg = MCPServerConfig(command="npx", max_result_chars=1_000_000)
    data = "Q" * 5_000
    result = types.CallToolResult(
        content=[types.ImageContent(type="image", data=data, mime_type="image/png")]
    )
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        responses={"call_tool": lambda tool, arguments, **kw: result},
    )
    manager = MCPManager({"srv": cfg})
    try:
        manager.start_server("srv", cfg)
        out = manager.call_tool("srv", "a", {})
        assert data not in out
    finally:
        manager.close()


# --- Plan 14-03: server instructions capture + prompt_catalog ------------------------------- #


def test_instructions_captured_per_server(monkeypatch):
    _DyingTransport([_Up([_fake_tool("a")], instructions="Prefer a.")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert manager.server_instructions("alpha") == "Prefer a."
        catalog = manager.prompt_catalog()
        assert len(catalog) == 1
        server, tools, instructions = catalog[0]
        assert server == "alpha"
        assert [t.name for t in tools] == ["mcp__alpha__a"]
        assert instructions == "Prefer a."
    finally:
        manager.close()


def test_instructions_blank_is_none(monkeypatch):
    _DyingTransport([_Up([_fake_tool("a")], instructions="   ")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert manager.server_instructions("alpha") is None
    finally:
        manager.close()


def test_instructions_absent_when_initialize_returns_none(monkeypatch):
    _install_fake_transport(monkeypatch, [_fake_tool("a")])
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert manager.server_instructions("alpha") is None
    finally:
        manager.close()


def test_instructions_cleared_on_stop_and_death(monkeypatch):
    _DyingTransport([_Up([_fake_tool("a")], instructions="x")]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert manager.server_instructions("alpha") == "x"
        manager.stop_server("alpha")
        assert manager.server_instructions("alpha") is None
        assert "alpha" not in [s for s, _, _ in manager.prompt_catalog()]
    finally:
        manager.close()

    import agent86.tools.mcp_client as mcp_client

    monkeypatch.setattr(mcp_client, "_MAX_RECONNECT_ATTEMPTS", 0)
    transport = _DyingTransport(
        [_Up([_fake_tool("a")], instructions="x"), ConnectionError("down")]
    ).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert manager.server_instructions("alpha") == "x"
        transport.kill(manager)
        assert _wait_until(lambda: "alpha" not in manager._sessions)
        assert manager.server_instructions("alpha") is None
    finally:
        manager.close()


def test_prompt_catalog_sorted_by_server(monkeypatch):
    _install_fake_transport(monkeypatch, [_fake_tool("z")])
    manager = MCPManager({})
    try:
        manager.start_server("zeta", MCPServerConfig(command="x"))
        manager.start_server("alpha", MCPServerConfig(command="x"))
        assert [s for s, _, _ in manager.prompt_catalog()] == ["alpha", "zeta"]
    finally:
        manager.close()


def test_prompt_catalog_feeds_the_system_message(monkeypatch):
    from agent86.config import load_config
    from agent86.orchestration.loop import Harness
    from tests.support import TextProvider

    harness = Harness(load_config(), provider=TextProvider("hi"), memory=None)
    manager = harness.ensure_mcp()
    _DyingTransport(
        [_Up([_fake_tool("a", schema={"type": "object", "properties": {"q": {"type": "string"}}})],
             instructions="Prefer a.")]
    ).install(monkeypatch)
    cfg = MCPServerConfig(command="x")
    try:
        manager.start_server("alpha", cfg)
        harness.add_mcp_server("alpha", cfg)

        content = harness._system_content(None)
        assert "- alpha: mcp__alpha__a" in content
        assert "Prefer a." in content

        tool = harness.registry.get("mcp__alpha__a")
        assert tool is not None
        assert tool.spec().parameters == {"type": "object", "properties": {}}
    finally:
        manager.close()


# --- Plan 14-04, Task 1: list_changed routes into a guarded, identity-preserving refetch ----- #


def test_list_changed_adds_and_removes_tools(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a"), _fake_tool("b")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append(
            (s, [t.name for t in r], [t.name for t in a])
        )
        up.tools[:] = [_fake_tool("a"), _fake_tool("c")]
        transport.notify(manager, types.ToolListChangedNotification())
        assert [t.name for t in manager.tools_for("alpha")] == [
            "mcp__alpha__a",
            "mcp__alpha__c",
        ]
        assert events == [("alpha", ["mcp__alpha__b"], ["mcp__alpha__c"])]
        assert any(
            "MCP server 'alpha' changed its tool list" in n and "mcp__alpha__c" in n
            for n in manager.notes
        )
    finally:
        manager.close()


def test_list_changed_keeps_unchanged_tool_identity(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a"), _fake_tool("b")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        a_before = manager.tools_for("alpha")[0]
        a_before._materialized = True
        up.tools[:] = [_fake_tool("a"), _fake_tool("b"), _fake_tool("c")]
        transport.notify(manager, types.ToolListChangedNotification())
        a_after = manager.tools_for("alpha")[0]
        assert a_after is a_before
        assert a_after.materialized is True
    finally:
        manager.close()


def test_list_changed_replaces_redefined_tool(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append(
            (s, [t.name for t in r], [t.name for t in a])
        )
        a_before = manager.tools_for("alpha")[0]
        new_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        up.tools[:] = [_fake_tool("a", schema=new_schema)]
        transport.notify(manager, types.ToolListChangedNotification())
        a_after = manager.tools_for("alpha")[0]
        assert a_after is not a_before
        assert events[-1] == ("alpha", ["mcp__alpha__a"], ["mcp__alpha__a"])
    finally:
        manager.close()


def test_list_changed_no_diff_no_event(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a"), _fake_tool("b")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append((s, r, a))
        calls_before = transport.list_calls
        transport.notify(manager, types.ToolListChangedNotification())
        assert events == []
        assert transport.list_calls == calls_before + 1
    finally:
        manager.close()


def test_list_changed_reuses_capability_tools(monkeypatch):
    types = pytest.importorskip("mcp.types")
    caps = _FakeCaps(resources=_FakeResourcesCap())
    up = _Up([_fake_tool("a")], caps=caps)
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append(
            (s, [t.name for t in r], [t.name for t in a])
        )
        list_resources_tool = next(
            t for t in manager.tools_for("alpha") if t.name == "mcp__alpha__list_resources"
        )
        up.tools[:] = [_fake_tool("a"), _fake_tool("b")]
        transport.notify(manager, types.ToolListChangedNotification())
        after = manager.tools_for("alpha")
        assert any(t is list_resources_tool for t in after)
        assert not any("mcp__alpha__list_resources" in added for (_s, _r, added) in events)
    finally:
        manager.close()


def test_list_changed_resource_and_prompt_siblings_refetch(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append((s, r, a))
        calls_before = transport.list_calls
        transport.notify(manager, types.ResourceListChangedNotification())
        transport.notify(manager, types.PromptListChangedNotification())
        assert transport.list_calls == calls_before + 2
        _seq, messages = manager.notes_since(0)
        assert any("MCP server 'alpha': its resource list changed." in m for m in messages)
        assert any("MCP server 'alpha': its prompt list changed." in m for m in messages)
        assert "MCP server 'alpha': its resource list changed." not in manager.notes
        assert "MCP server 'alpha': its prompt list changed." not in manager.notes
        assert events == []
    finally:
        manager.close()


def test_list_changed_racing_stop_does_not_resurrect(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up], list_delay=0.3).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append((s, r, a))
        up.tools.append(_fake_tool("z"))
        fut = transport.notify_nowait(manager, types.ToolListChangedNotification())
        manager.stop_server("alpha")
        fut.result(timeout=5)
        assert "alpha" not in manager._server_tools
        assert manager.tools_for("alpha") == []
        assert not any(a for (_s, _r, a) in events)
    finally:
        manager.close()


def test_list_changed_racing_death_does_not_resurrect(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up, ConnectionError("down")], list_delay=0.3).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        up.tools.append(_fake_tool("z"))
        fut = transport.notify_nowait(manager, types.ToolListChangedNotification())
        transport.kill(manager)
        fut.result(timeout=5)
        assert _wait_until(lambda: "alpha" not in manager._sessions)
        assert "mcp__alpha__z" not in [t.name for t in manager.tools()]
    finally:
        manager.close()


def test_list_changed_refetch_failure_is_a_note_not_a_raise(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up]).install(monkeypatch)
    manager = MCPManager({})
    events: list = []
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.on_tools_changed = lambda s, r, a: events.append((s, r, a))
        before = manager.tools_for("alpha")
        transport.list_error = RuntimeError("list broke")
        transport.notify(manager, types.ToolListChangedNotification())  # must not raise
        assert any(
            "re-listing tools after tools/list_changed failed" in n and "list broke" in n
            for n in manager.notes
        )
        assert manager.tools_for("alpha") == before
        assert events == []
    finally:
        manager.close()


def test_list_changed_back_to_back_serialized(monkeypatch):
    types = pytest.importorskip("mcp.types")
    up = _Up([_fake_tool("a")])
    transport = _DyingTransport([up], list_delay=0.2).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        up.tools[:] = [_fake_tool("a"), _fake_tool("b")]
        fut1 = transport.notify_nowait(manager, types.ToolListChangedNotification())
        fut2 = transport.notify_nowait(manager, types.ToolListChangedNotification())
        fut1.result(timeout=5)
        fut2.result(timeout=5)
        names = [t.name for t in manager.tools_for("alpha")]
        assert sorted(names) == ["mcp__alpha__a", "mcp__alpha__b"]
        assert len(names) == len(set(names))
    finally:
        manager.close()


# --- Plan 14-04, Task 2: request/observe progress; route logging + resource-updated ---------- #


def test_progress_notification_requested_on_call_tool(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.call_tool("alpha", "a", {})
        assert transport.call_kwargs[-1]["progress_callback"] is mcp_client._request_progress
    finally:
        manager.close()


def test_progress_notification_not_requested_for_capability_calls(monkeypatch):
    calls: list = []
    _install_fake_transport(
        monkeypatch,
        [_fake_tool("a")],
        capabilities=_FakeCaps(resources=_FakeResourcesCap()),
        responses={"list_resources": _fake_result(resources=[])},
        calls=calls,
    )
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        manager.list_resources("alpha")
        method, args, kw = calls[-1]
        assert method == "list_resources"
        assert "progress_callback" not in kw
    finally:
        manager.close()


def test_progress_notification_is_observed_as_live_note(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(
                    progress_token=1, progress=1, total=3, message="step 1"
                )
            ),
        )
        assert manager.last_progress("alpha") == (1.0, 3.0, "step 1")
        _seq, messages = manager.notes_since(0)
        assert any("MCP server 'alpha': progress 1/3 — step 1" in m for m in messages)
        assert not any("MCP server 'alpha': progress 1/3 — step 1" in n for n in manager.notes)
    finally:
        manager.close()


def test_progress_notification_throttled(monkeypatch):
    import agent86.tools.mcp_client as mcp_client

    types = pytest.importorskip("mcp.types")
    monkeypatch.setattr(mcp_client, "_PROGRESS_NOTE_INTERVAL_S", 60)
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(progress_token=1, progress=1, total=3)
            ),
        )
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(progress_token=1, progress=2, total=3)
            ),
        )
        _seq, messages = manager.notes_since(0)
        assert len(messages) == 1
        assert "progress 1/3" in messages[0]
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(progress_token=1, progress=3, total=3)
            ),
        )
        _seq, messages = manager.notes_since(0)
        assert len(messages) == 2
        assert "progress 3/3" in messages[1]
        assert manager.last_progress("alpha") == (3.0, 3.0, None)
    finally:
        manager.close()


def test_progress_notification_without_total(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(progress_token=1, progress=5, total=None)
            ),
        )
        _seq, messages = manager.notes_since(0)
        note = messages[0]
        assert "progress 5" in note
        assert "/" not in note.split("progress 5", 1)[1]
    finally:
        manager.close()


def test_progress_notification_message_is_clipped(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        long_message = "line one\nline two\n" + ("x" * 1000)
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(
                    progress_token=1, progress=1, total=3, message=long_message
                )
            ),
        )
        _seq, messages = manager.notes_since(0)
        note = messages[0]
        assert "\n" not in note
        message_part = note.split("— ", 1)[1]
        assert len(message_part) <= 200
        assert message_part.endswith("…")
    finally:
        manager.close()


def test_logging_notification_goes_to_python_logger(monkeypatch, caplog):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    caplog.set_level(logging.DEBUG, logger="agent86.tools.mcp_client")
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.LoggingMessageNotification(
                params=types.LoggingMessageNotificationParams(
                    level="warning", logger="lg", data="disk low"
                )
            ),
        )
        records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("MCP server 'alpha' [lg]: disk low" in r.getMessage() for r in records)
        _seq, messages = manager.notes_since(0)
        assert not any("disk low" in m for m in messages)
    finally:
        manager.close()


@pytest.mark.parametrize(
    "mcp_level,py_level",
    [
        ("emergency", logging.CRITICAL),
        ("notice", logging.INFO),
        ("debug", logging.DEBUG),
        ("error", logging.ERROR),
    ],
)
def test_logging_notification_level_mapping(monkeypatch, caplog, mcp_level, py_level):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    caplog.set_level(logging.DEBUG, logger="agent86.tools.mcp_client")
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.LoggingMessageNotification(
                params=types.LoggingMessageNotificationParams(
                    level=mcp_level, logger="lg", data="hi"
                )
            ),
        )
        matching = [r for r in caplog.records if "MCP server 'alpha' [lg]: hi" in r.getMessage()]
        assert matching and matching[-1].levelno == py_level
    finally:
        manager.close()


def test_resource_updated_notification_is_a_live_note(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        transport.notify(
            manager,
            types.ResourceUpdatedNotification(
                params=types.ResourceUpdatedNotificationParams(uri="res://agent86/greeting.txt")
            ),
        )
        _seq, messages = manager.notes_since(0)
        expected = (
            "MCP server 'alpha': subscribed resource updated: res://agent86/greeting.txt; "
            "re-read it with mcp__alpha__read_resource."
        )
        assert any(expected in m for m in messages)
        assert not any(expected in n for n in manager.notes)
    finally:
        manager.close()


def test_unrouted_notification_is_ignored(monkeypatch):
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))
        seq_before = manager.note_seq
        transport.notify(manager, object())  # must not raise
        assert manager.note_seq == seq_before
    finally:
        manager.close()


def test_notification_handler_never_raises(monkeypatch):
    types = pytest.importorskip("mcp.types")
    transport = _DyingTransport([_Up([_fake_tool("a")])]).install(monkeypatch)
    manager = MCPManager({})
    try:
        manager.start_server("alpha", MCPServerConfig(command="x"))

        def _boom(name, params):
            raise RuntimeError("boom")

        monkeypatch.setattr(manager, "_on_progress", _boom)
        transport.notify(
            manager,
            types.ProgressNotification(
                params=types.ProgressNotificationParams(progress_token=1, progress=1, total=3)
            ),
        )  # must not raise
    finally:
        manager.close()
