"""A minimal live MCP server used by the live-transport integration test.

Run as a subprocess: ``python live_mcp_server.py <transport> <port>`` where transport is
``streamable-http`` or ``sse``. Exposes three trivial tools so the test can assert both tool
discovery and a real call round trip over the wire. ``get_env`` is the SEC-04 probe: it echoes
this server process's own environment, letting a stdio-driven test prove the subprocess received
``SandboxPolicy.scrubbed_env()`` rather than the host environment.

Built on ``mcp.server.mcpserver.MCPServer`` — the SDK's own server API since mcp 2.0, which
serves both transports as ASGI apps over uvicorn. (``mcp.server.fastmcp`` is gone: FastMCP
moved out of the SDK, which is what left this test permanently skipped.)
"""

from __future__ import annotations

import os
import sys

from mcp.server.mcpserver import MCPServer


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

    # host/port are per-transport run options in mcp 2.0, not constructor settings.
    mcp.run(transport=transport, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
