"""A minimal live MCP server used by the live-transport integration test.

Run as a subprocess: ``python live_mcp_server.py <transport> <port>`` where transport is
``streamable-http`` or ``sse``. Exposes three trivial tools, three resources (one text, one
binary, one template), one prompt and one completion handler, so the test can assert tool
discovery and a real call round trip over the wire alongside the CAP-RESOURCES/CAP-PROMPTS/
CAP-COMPLETION gates Phase 11 adds. The binary resource exists so a client is proven to render a
visible marker for it, never inline its base64 into ``ToolResult.content``. ``get_env`` is the
SEC-04 probe: it echoes this server process's own environment, letting a stdio-driven test prove
the subprocess received ``SandboxPolicy.scrubbed_env()`` rather than the host environment.
``AGENT86_LIVE_MCP_PID_FILE``, if set, makes this process write its own PID to that path
immediately before serving, so a lifecycle test can find and kill it mid-session (MCP-26/23).
``AGENT86_LIVE_MCP_EXTRA_TOOLS=1`` mounts five additional opt-in tools (``sleep_for``,
``big_text``, ``tiny_image``, ``tiny_audio``, ``mixed_blocks``) that exercise Phase 13's
per-server timeouts, the result cap, and real ImageContent/AudioContent/EmbeddedResource/
ResourceLink content blocks — gated behind the env var so the fixture's default tool set, which
several tests assert exactly, is unchanged.

Built on ``mcp.server.mcpserver.MCPServer`` — the SDK's own server API since mcp 2.0, which
serves both transports as ASGI apps over uvicorn. (``mcp.server.fastmcp`` is gone: FastMCP
moved out of the SDK, which is what left this test permanently skipped.)
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

#: The two Phase 13 content-block probes (see AGENT86_LIVE_MCP_EXTRA_TOOLS below). Importable by
#: the test so it can assert their base64 never appears in a rendered marker.
IMAGE_BYTES = b"\x89PNG\r\n\x1a\nagent86-image-probe"
AUDIO_BYTES = b"RIFF\x00\x00\x00\x00WAVEagent86-audio-probe"

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

    # Opt-in, test-only (Phase 13): tools that exercise per-server timeouts, the result cap and
    # non-text content blocks. Behind an env flag so the default tool set — asserted exactly by
    # several tests — is unchanged.
    if os.environ.get("AGENT86_LIVE_MCP_EXTRA_TOOLS") == "1":
        import anyio
        from mcp.server.mcpserver import Audio, Image
        from mcp.types import BlobResourceContents, EmbeddedResource, ResourceLink

        @mcp.tool()
        async def sleep_for(seconds: float) -> str:
            """Sleep, then answer — the call_timeout_s probe."""
            await anyio.sleep(seconds)
            return "slept"

        @mcp.tool()
        def big_text(n: int) -> str:
            """Return n characters — the max_result_chars probe."""
            return "x" * n

        @mcp.tool()
        def tiny_image():
            """A real ImageContent block."""
            return Image(data=IMAGE_BYTES, format="png")

        @mcp.tool()
        def tiny_audio():
            """A real AudioContent block."""
            return Audio(data=AUDIO_BYTES, format="wav")

        @mcp.tool()
        def mixed_blocks():
            """Text, an embedded binary resource and a resource link in one result."""
            return [
                "before",
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri="res://agent86/blob.bin",
                        mime_type="application/octet-stream",
                        blob=base64.b64encode(b"agent86-embedded-probe").decode(),
                    ),
                ),
                ResourceLink(
                    type="resource_link",
                    name="greeting",
                    uri="res://agent86/greeting.txt",
                    mime_type="text/plain",
                ),
            ]

    # Opt-in, test-only: lets a lifecycle test find and kill THIS process mid-session (MCP-26/23).
    # A file, not a tool, so the fixture's tool set — which several tests assert exactly — is
    # unchanged.
    pid_file = os.environ.get("AGENT86_LIVE_MCP_PID_FILE")
    if pid_file:
        Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")

    # host/port are per-transport run options in mcp 2.0, not constructor settings.
    mcp.run(transport=transport, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
