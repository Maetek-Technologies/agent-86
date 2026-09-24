"""v0.7 — startup tool-name collisions are recorded and logged, not silently swallowed."""

from __future__ import annotations

import logging
import threading
import time
import types

from pydantic import BaseModel

from agent86.config import load_config
from agent86.tools.base import Tool, ToolContext
from agent86.tools.registry import ToolRegistry, default_registry
from agent86.types import ToolCall, ToolResult


class _Stub(Tool["_Stub.Args"]):
    class Args(BaseModel):
        pass

    def __init__(self, name: str):
        self.name = name
        self.description = f"stub {name}"

    def execute(self, args: Args, ctx: ToolContext) -> ToolResult:  # pragma: no cover
        return ToolResult(call_id="", name=self.name, content="")


def test_registry_starts_with_no_collisions():
    assert ToolRegistry().collisions == []


def test_try_register_records_and_logs_a_collision(caplog):
    registry = ToolRegistry()
    assert registry.try_register(_Stub("search")) is True

    with caplog.at_level(logging.WARNING, logger="agent86.tools.registry"):
        assert registry.try_register(_Stub("search")) is False

    assert registry.collisions == ["search"]
    assert "search" in caplog.text and "not callable" in caplog.text
    assert registry.names().count("search") == 1


def test_collision_warning_mentions_name_truncation(caplog):
    long_name = "mcp__server__" + "t" * 60
    long_name = long_name[:64]
    registry = ToolRegistry()
    registry.try_register(_Stub(long_name))
    with caplog.at_level(logging.WARNING, logger="agent86.tools.registry"):
        registry.try_register(_Stub(long_name))
    assert "truncated to 64 characters" in caplog.text


def test_default_registry_reports_mcp_tools_it_could_not_mount(caplog):
    cfg = load_config()
    tools = [_Stub("mcp__a__search"), _Stub("mcp__a__search"), _Stub("read_file")]

    with caplog.at_level(logging.WARNING, logger="agent86.tools.registry"):
        registry = default_registry(cfg, mcp_tools=tools)

    # The duplicate across servers and the one shadowing a built-in are both reported.
    assert registry.collisions == ["mcp__a__search", "read_file"]
    assert "mcp__a__search" in caplog.text
    assert "read_file" in caplog.text
    # ...and the first registration of each name still won.
    assert registry.get("mcp__a__search") is tools[0]
    assert registry.get("read_file") is not tools[2]


def test_default_registry_has_no_collisions_for_distinct_names():
    registry = default_registry(load_config(), mcp_tools=[_Stub("mcp__a__x"), _Stub("mcp__b__x")])
    assert registry.collisions == []
    assert {"mcp__a__x", "mcp__b__x"}.issubset(set(registry.names()))


# --- MCP-26 precondition: identity-checked removal + cross-thread safety (plan 12-02) ---


class _LockCheckTool(Tool["_LockCheckTool.Args"]):
    """A tool whose ``execute`` proves the registry's lock is NOT held while it runs.

    Spawns a *different* thread that attempts a non-blocking acquire of the registry's own
    lock; if ``dispatch`` were still holding it during ``tool.run``, the acquire would fail.
    """

    class Args(BaseModel):
        pass

    def __init__(self, name: str, registry: ToolRegistry):
        self.name = name
        self.description = f"lock-check {name}"
        self._registry = registry

    def execute(self, args: Args, ctx: ToolContext) -> ToolResult:
        outcome: dict[str, bool] = {}

        def probe() -> None:
            acquired = self._registry._lock.acquire(blocking=False)
            if acquired:
                self._registry._lock.release()
            outcome["acquired"] = acquired

        prober = threading.Thread(target=probe)
        prober.start()
        prober.join(timeout=5)
        assert outcome.get("acquired") is True, "registry lock was held during tool.run"
        return ToolResult(call_id="", name=self.name, content="ok")


def test_registry_unregister_tool_removes_the_same_object():
    registry = ToolRegistry()
    owner = _Stub("x")
    registry.register(owner)

    assert registry.unregister_tool(owner) is True
    assert registry.get("x") is None


def test_registry_unregister_tool_leaves_a_different_owner():
    registry = ToolRegistry()
    owner = _Stub("x")
    impostor = _Stub("x")  # distinct object, same name, never registered
    registry.register(owner)

    assert registry.unregister_tool(impostor) is False
    assert registry.get("x") is owner


def test_registry_unregister_tool_unknown_is_false():
    registry = ToolRegistry()
    stranger = _Stub("x")

    assert registry.unregister_tool(stranger) is False


def test_registry_concurrent_mutation_and_reads():
    registry = ToolRegistry()
    stop = threading.Event()
    errors: list[BaseException] = []

    def mutate() -> None:
        try:
            deadline = time.monotonic() + 0.5
            i = 0
            while time.monotonic() < deadline and not stop.is_set():
                tool = _Stub(f"tool-{i % 50}")
                registry.try_register(tool)
                registry.unregister_tool(tool)
                i += 1
        except BaseException as exc:  # noqa: BLE001 - collected for the test's own assertion
            errors.append(exc)

    worker = threading.Thread(target=mutate)
    worker.start()
    try:
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            registry.specs()
            registry.names()
            registry.get("tool-0")
    except BaseException as exc:  # noqa: BLE001 - collected for the test's own assertion
        errors.append(exc)
    finally:
        stop.set()
        worker.join(timeout=5)

    assert errors == []


def test_registry_dispatch_does_not_hold_the_lock_during_run():
    registry = ToolRegistry()
    tool = _LockCheckTool("lockcheck", registry)
    registry.register(tool)
    call = ToolCall(id="1", name="lockcheck", arguments={})
    ctx = types.SimpleNamespace(allowed_tool=None, active_skill=None)

    result = registry.dispatch(call, ctx)

    assert result.ok
    assert result.content == "ok"
