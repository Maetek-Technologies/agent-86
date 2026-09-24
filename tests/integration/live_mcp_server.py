"""A minimal live MCP server used by the live-transport integration test.

Run as a subprocess: ``python live_mcp_server.py <transport> <port>`` where transport is
``streamable-http`` or ``sse``. Exposes three trivial tools, three resources (one text, one
binary, one template), one prompt and one completion handler, so the test can assert tool
discovery and a real call round trip over the wire alongside the CAP-RESOURCES/CAP-PROMPTS/
CAP-COMPLETION gates Phase 11 adds. The binary resource exists so a client is proven to render a
visible marker for it, never inline its base64 into ``ToolResult.content``. ``get_env`` is the
SEC-04 probe: it echoes this server process's own environment, letting a stdio-driven test prove
the subprocess received ``SandboxPolicy.scrubbed_env()`` rather than the host environment.

Built on ``mcp.server.mcpserver.MCPServer`` — the SDK's own server API since mcp 2.0, which
serves both transports as ASGI apps over uvicorn. (``mcp.server.fastmcp`` is gone: FastMCP
moved out of the SDK, which is what left this test permanently skipped.)
"""

from __future__ import annotations

import os
import sys

from mcp.server.mcpserver import MCPServer

#: The completion values `complete_argument` offers for the `review_code` prompt's `style`
#: argument. A module constant so a test can import it instead of re-spelling the list.
STYLE_COMPLETIONS = ["concise", "thorough", "security-focused"]


def main() -> None:
    transport, port = sys.argv[1], int(sys.argv[2])
    mcp = MCPServer("agent86-live-test")

    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two integers and return the sum."""
        return a + b

    @mcp.tool()
    def shout(text: str) -> str:
        """Uppercase the given text."""
        return text.upper()

    @mcp.tool()
    def get_env() -> dict[str, str]:
        """Echo this server process's own environment, for SEC-04 verification."""
        return dict(os.environ)

    @mcp.resource("res://agent86/greeting.txt", mime_type="text/plain")
    def greeting_resource() -> str:
        """A static text resource — the CAP-RESOURCES read path."""
        return "hello from the agent86 live test server"

    @mcp.resource("res://agent86/blob.bin", mime_type="application/octet-stream")
    def blob_resource() -> bytes:
        """A static BINARY resource. Its base64 must never be inlined into ToolResult.content."""
        return b"\x00\x01\x02agent86-binary-probe\xff"

    @mcp.resource("res://agent86/echo/{word}", mime_type="text/plain")
    def echo_resource(word: str) -> str:
        """A resource TEMPLATE (the {word} parameter) — the CAP-RESOURCE-TEMPLATES path."""
        return f"echo: {word}"

    @mcp.prompt(name="review_code", description="Review a file in a given style.")
    def review_code(path: str, style: str) -> str:
        """A two-argument prompt; `style` is the argument the completion handler completes."""
        return f"Review the file at {path} in a {style} style."

    @mcp.completion()
    async def complete_argument(ref, argument, context):
        """Suggest STYLE_COMPLETIONS for review_code's `style` argument, prefix-filtered."""
        from mcp.types import Completion, PromptReference

        if (
            isinstance(ref, PromptReference)
            and ref.name == "review_code"
            and argument.name == "style"
        ):
            values = [s for s in STYLE_COMPLETIONS if s.startswith(argument.value or "")]
            return Completion(values=values, total=len(values), has_more=False)
        return None

    # host/port are per-transport run options in mcp 2.0, not constructor settings.
    mcp.run(transport=transport, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
