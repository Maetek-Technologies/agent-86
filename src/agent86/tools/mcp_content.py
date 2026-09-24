"""Model-facing rendering of MCP result content (MCP-25) and the prompt-side cap (MCP-22).

Pure functions, no I/O and no top-level ``mcp`` import (it is an optional extra): the SDK's
content classes are imported lazily inside :func:`render_content_block`. Neither function
raises — a tool result must never raise into the loop (CLAUDE.md), so an unknown or malformed
block degrades to a named marker, never ``str(block)`` (the Python repr).
"""

from __future__ import annotations

from typing import Any

_UNKNOWN = "unknown"


def _field(obj: Any, name: str) -> str:
    """Read ``obj.name`` for display, falling back to ``unknown`` for ``None``/empty."""
    value = getattr(obj, name, None)
    if value is None or value == "":
        return _UNKNOWN
    return str(value)


def _generic(block: Any) -> str:
    """The fallback marker for any block this module does not specifically know how to render."""
    try:
        kind = type(block).__name__
    except Exception:  # noqa: BLE001 - type() does not raise, but stay defensive here too
        kind = "unknown"
    return f"[non-text content block: {kind} — not inlined]"


def render_content_block(block: Any) -> str:
    """Render one ``CallToolResult`` content block as prompt text.

    A duck-typed ``.text`` string is honoured first (existing fake-object tests rely on this).
    ``ImageContent``/``AudioContent``/binary ``EmbeddedResource``/``ResourceLink`` become named
    markers describing mime type and base64 length — the base64 payload itself is never
    inlined, whatever its size. An unknown or future block type, or any attribute access that
    raises, degrades to :func:`_generic` rather than propagating an exception.
    """
    try:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
        try:
            from mcp import types as mcp_types
        except ImportError:
            return _generic(block)
        if isinstance(block, mcp_types.ImageContent):
            return (
                f"[image content: mime_type={_field(block, 'mime_type')} "
                f"base64_len={len(block.data or '')} — not inlined]"
            )
        if isinstance(block, mcp_types.AudioContent):
            return (
                f"[audio content: mime_type={_field(block, 'mime_type')} "
                f"base64_len={len(block.data or '')} — not inlined]"
            )
        if isinstance(block, mcp_types.EmbeddedResource):
            resource = block.resource
            header = (
                f"embedded resource uri={_field(resource, 'uri')} "
                f"mime_type={_field(resource, 'mime_type')}"
            )
            if isinstance(resource, mcp_types.TextResourceContents):
                return f"[{header}]\n{resource.text}"
            blob_len = len(getattr(resource, "blob", None) or "")
            return f"[{header} base64_len={blob_len} — not inlined]"
        if isinstance(block, mcp_types.ResourceLink):
            return (
                f"[resource link uri={_field(block, 'uri')} name={_field(block, 'name')} "
                f"mime_type={_field(block, 'mime_type')} size={_field(block, 'size')}]"
            )
        return _generic(block)
    except Exception:  # noqa: BLE001 - a tool result must never raise into the loop
        return _generic(block)


def truncate_result(text: str, limit: int, server: str) -> str:
    """Cut ``text`` at ``limit`` characters with a visible marker (ADR 0004).

    Never drops silently and never raises: a non-positive ``limit`` is clamped to 0. Text at or
    under the limit is returned unchanged.
    """
    limit = max(0, int(limit))
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return (
        f"{text[:limit]}\n…[truncated {dropped} chars: result exceeded "
        f"max_result_chars={limit} for MCP server '{server}'; raise max_result_chars under "
        f"[mcp.servers.{server}] to see more]"
    )
