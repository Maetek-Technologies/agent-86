"""Tests for the pure MCP content-rendering and result-truncation helpers (MCP-22, MCP-25).

``truncate_result`` tests build no SDK objects and always run. Every test that constructs a real
``mcp.types`` instance calls ``pytest.importorskip("mcp.types")`` locally, matching the pattern in
``tests/unit/test_mcp.py::test_real_sdk_tool_object_is_understood`` — so the truncate tests still
run without the ``mcp`` extra installed.
"""

from __future__ import annotations

import pytest

from agent86.tools.mcp_content import render_content_block, truncate_result


def test_render_content_block_text():
    types = pytest.importorskip("mcp.types")
    block = types.TextContent(type="text", text="hello")
    assert render_content_block(block) == "hello"


def test_render_content_block_duck_typed_text():
    class Duck:
        text = "hi"

    assert render_content_block(Duck()) == "hi"


def test_render_content_block_image():
    types = pytest.importorskip("mcp.types")
    block = types.ImageContent(type="image", data="QUJDREVG", mime_type="image/png")
    out = render_content_block(block)
    assert out == "[image content: mime_type=image/png base64_len=8 — not inlined]"
    assert "QUJDREVG" not in out
    assert "ImageContent(" not in out


def test_render_content_block_audio():
    types = pytest.importorskip("mcp.types")
    block = types.AudioContent(type="audio", data="UklGRg==", mime_type="audio/wav")
    out = render_content_block(block)
    assert out == "[audio content: mime_type=audio/wav base64_len=8 — not inlined]"


def test_render_content_block_embedded_text_resource():
    types = pytest.importorskip("mcp.types")
    block = types.EmbeddedResource(
        type="resource",
        resource=types.TextResourceContents(
            uri="res://x/a.txt", mime_type="text/plain", text="body"
        ),
    )
    out = render_content_block(block)
    assert out == "[embedded resource uri=res://x/a.txt mime_type=text/plain]\nbody"


def test_render_content_block_embedded_blob_resource():
    types = pytest.importorskip("mcp.types")
    block = types.EmbeddedResource(
        type="resource",
        resource=types.BlobResourceContents(
            uri="res://x/p.png", mime_type="image/png", blob="QUJD"
        ),
    )
    out = render_content_block(block)
    assert out == (
        "[embedded resource uri=res://x/p.png mime_type=image/png base64_len=4 — not inlined]"
    )
    assert "QUJD" not in out


def test_render_content_block_resource_link():
    types = pytest.importorskip("mcp.types")
    block = types.ResourceLink(
        type="resource_link",
        name="readme",
        uri="file:///r.md",
        mime_type="text/markdown",
        size=120,
    )
    out = render_content_block(block)
    assert out == "[resource link uri=file:///r.md name=readme mime_type=text/markdown size=120]"

    block_unknown = types.ResourceLink(type="resource_link", name="readme", uri="file:///r.md")
    out_unknown = render_content_block(block_unknown)
    assert out_unknown == (
        "[resource link uri=file:///r.md name=readme mime_type=unknown size=unknown]"
    )


def test_render_content_block_unknown_type_never_repr():
    class Weird:
        pass

    out = render_content_block(Weird())
    assert out == "[non-text content block: Weird — not inlined]"
    assert "object at 0x" not in out


def test_render_content_block_never_raises():
    class Exploding:
        def __getattribute__(self, name):
            raise RuntimeError("boom")

    out = render_content_block(Exploding())
    assert out.startswith("[non-text content block:")


def test_render_content_block_missing_mime_is_unknown():
    types = pytest.importorskip("mcp.types")
    block = types.ImageContent(type="image", data="", mime_type="")
    out = render_content_block(block)
    assert "mime_type=unknown base64_len=0" in out


def test_truncate_result_under_limit_unchanged():
    assert truncate_result("abc", 3, "srv") == "abc"


def test_truncate_result_over_limit_has_visible_marker():
    out = truncate_result("x" * 10_050, 10_000, "srv")
    assert out.startswith("x" * 10_000)
    assert out[10_000:] == (
        "\n…[truncated 50 chars: result exceeded max_result_chars=10000 for MCP server 'srv'; "
        "raise max_result_chars under [mcp.servers.srv] to see more]"
    )


def test_truncate_result_never_raises_on_bad_limit():
    out_zero = truncate_result("abc", 0, "srv")
    assert "…[truncated 3 chars" in out_zero
    out_negative = truncate_result("abc", -5, "srv")
    assert "…[truncated 3 chars" in out_negative
