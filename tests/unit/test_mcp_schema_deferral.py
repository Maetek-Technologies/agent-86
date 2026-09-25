"""Tests for MCP tool schema deferral until first use (ADR 0003, MCP-20).

Task 1 covers materialisation on ``MCPTool`` itself (spec/run before and after first use) and
the provider-shape round trip (Pitfall 1). Task 2 extends this file with the same-turn budget
proof.
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from typing import Any

from agent86.cognitive.anthropic_provider import AnthropicProvider
from agent86.cognitive.base import ModelProvider
from agent86.cognitive.ollama_provider import OllamaProvider
from agent86.cognitive.openai_provider import OpenAIProvider
from agent86.config import load_config
from agent86.memory.working import count_spec_tokens
from agent86.orchestration.loop import Harness
from agent86.tools.mcp_client import MCPListResourcesTool, MCPTool
from agent86.types import Completion, CompletionDelta, CompletionRequest, ToolCall, ToolSpec, Usage


class _RecordingManager:
    """A minimal MCPManager stand-in: records every ``call_tool`` invocation."""

    def __init__(self, result: str = "ok", error: Exception | None = None):
        self.calls: list[tuple[str, str, dict]] = []
        self._result = result
        self._error = error

    def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        self.calls.append((server, tool, arguments))
        if self._error is not None:
            raise self._error
        return self._result


_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
    "required": ["query"],
}


def test_materializ_never_called_tool_advertises_stub():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    spec = tool.spec()
    assert spec.parameters == {"type": "object", "properties": {}}
    assert spec.description.endswith(" [argument schema loads on first call]")
    assert spec.name == "mcp__alpha__search"
    assert tool.materialized is False


def test_materializ_after_first_call_real_schema():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    result = tool.run(ToolCall(id="1", name=tool.name, arguments={"query": "q"}), ctx=None)
    assert result.ok
    assert result.metadata == {"schema_materialized": True}

    spec = tool.spec()
    assert spec.parameters == _SCHEMA
    assert not spec.description.endswith(" [argument schema loads on first call]")

    result2 = tool.run(ToolCall(id="2", name=tool.name, arguments={"query": "q2"}), ctx=None)
    assert result2.metadata == {}


def test_materializ_on_failed_first_call():
    tool = MCPTool(
        _RecordingManager(error=RuntimeError("boom")), "alpha", "search", "Search", _SCHEMA
    )
    result = tool.run(ToolCall(id="1", name=tool.name, arguments={"query": "q"}), ctx=None)
    assert result.ok is False
    assert "MCP call failed: boom" in (result.error or "")
    assert result.metadata == {"schema_materialized": True}
    assert tool.spec().parameters == _SCHEMA


def test_materializ_missing_required_short_circuits():
    manager = _RecordingManager()
    tool = MCPTool(manager, "alpha", "search", "Search", _SCHEMA)

    result = tool.run(ToolCall(id="1", name=tool.name, arguments={}), ctx=None)
    assert result.ok is False
    assert "missing required argument(s): query" in (result.error or "")
    assert "mcp__alpha__search" in (result.error or "")
    assert manager.calls == []
    assert tool.spec().parameters == _SCHEMA

    # Second use: the precheck only ever fires on first use — a second omission still reaches
    # the server (ADR 0003's reconnect ruling: history already shows what arguments were used).
    tool.run(ToolCall(id="2", name=tool.name, arguments={}), ctx=None)
    assert manager.calls


def test_materializ_argumentless_tool_is_never_deferred():
    for schema in ({"type": "object", "properties": {}}, {}):
        tool = MCPTool(_RecordingManager(), "alpha", "noop", "Noop", schema)
        assert tool.materialized is True
        assert not tool.spec().description.endswith(" [argument schema loads on first call]")


def test_materializ_stub_is_a_fresh_dict():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    spec = tool.spec()
    spec.parameters["x"] = 1
    assert tool.spec().parameters == {"type": "object", "properties": {}}


def test_materializ_capability_tools_not_deferred():
    tool = MCPListResourcesTool(_RecordingManager(), "alpha")
    assert not tool.spec().description.endswith(" [argument schema loads on first call]")


def test_mcp_stub_schema_matches_toolspec_default():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    assert tool.spec().parameters == ToolSpec(name="x", description="y").parameters


def test_mcp_stub_schema_anthropic_shape():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    wire = AnthropicProvider._to_tools([tool.spec()])
    assert wire[0]["input_schema"] == {"type": "object", "properties": {}}

    tool.run(ToolCall(id="1", name=tool.name, arguments={"query": "q"}), ctx=None)
    wire2 = AnthropicProvider._to_tools([tool.spec()])
    assert wire2[0]["input_schema"] == _SCHEMA


def test_mcp_stub_schema_openai_shape():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    wire = OpenAIProvider._to_tools([tool.spec()])
    assert wire[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    tool.run(ToolCall(id="1", name=tool.name, arguments={"query": "q"}), ctx=None)
    wire2 = OpenAIProvider._to_tools([tool.spec()])
    assert wire2[0]["function"]["parameters"] == _SCHEMA


def test_mcp_stub_schema_ollama_shape():
    tool = MCPTool(_RecordingManager(), "alpha", "search", "Search", _SCHEMA)
    wire = OllamaProvider._to_tools([tool.spec()])
    assert wire[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    tool.run(ToolCall(id="1", name=tool.name, arguments={"query": "q"}), ctx=None)
    wire2 = OllamaProvider._to_tools([tool.spec()])
    assert wire2[0]["function"]["parameters"] == _SCHEMA


# --- Task 2: the same-turn budget proof (ADR 0003 SC2, RESEARCH Pitfall 4) ------------------- #


class _BudgetRecordingProvider(ModelProvider):
    """Records every request plus the budget resolved for it; drives one tool_use, then text."""

    name = "anthropic"

    def __init__(self, model: str = "claude-opus-4-8"):
        self.model = model
        self.calls: list[tuple[CompletionRequest, int]] = []
        self.harness: Any = None  # set by the test after the Harness exists

    def stream(self, request: CompletionRequest) -> Iterator[CompletionDelta]:
        self.calls.append((request, self.harness.working.max_tokens))
        if len(self.calls) == 1:
            yield CompletionDelta(
                done=True,
                completion=Completion(
                    text="",
                    tool_calls=[
                        ToolCall(id="1", name="mcp__alpha__search", arguments={"query": "q"})
                    ],
                    usage=Usage(input_tokens=5, output_tokens=2),
                    model=self.model,
                    stop_reason="tool_use",
                ),
            )
        else:
            yield CompletionDelta(text="done")
            yield CompletionDelta(
                done=True,
                completion=Completion(
                    text="done",
                    usage=Usage(input_tokens=6, output_tokens=1),
                    model=self.model,
                    stop_reason="end_turn",
                ),
            )


def test_budget_shrinks_in_the_step_that_materialises():
    provider = _BudgetRecordingProvider()
    harness = Harness(load_config(), provider=provider, memory=None)
    provider.harness = harness

    manager = _RecordingManager()
    big_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "x" * 2000},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }
    # read_only=True: side_effecting stays False, so the approval gate never blocks this test.
    tool = MCPTool(manager, "alpha", "search", "Search", big_schema, read_only=True)
    harness.registry.register(tool)

    list(harness.run_turn("go", harness.new_session()))

    assert len(provider.calls) == 2
    (req0, budget0), (req1, budget1) = provider.calls

    def spec_for(req: CompletionRequest) -> ToolSpec:
        return next(s for s in req.tools if s.name == "mcp__alpha__search")

    assert spec_for(req0).parameters == {"type": "object", "properties": {}}
    assert spec_for(req1).parameters == big_schema

    delta = count_spec_tokens(req1.tools) - count_spec_tokens(req0.tools)
    assert delta > 0
    assert budget0 - budget1 == delta
    assert manager.calls == [("alpha", "search", {"query": "q"})]


def test_budget_hook_unchanged():
    sig = inspect.signature(Harness._context_budget)
    assert list(sig.parameters) == ["self", "system_content", "specs"]
    assert inspect.getsource(Harness).count("self._context_budget(") == 2
