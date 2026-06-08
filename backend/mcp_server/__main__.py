# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
CLI entry point for Owlangs MCP Server.

Usage:
    python -m backend.mcp_server                             # stdio mode (default, for AI Agents)
    python -m backend.mcp_server --http --port 8100           # HTTP/SSE mode (multi-client)
    python -m backend.mcp_server --http --transport sse       # SSE mode
    python -m backend.mcp_server --http --transport streamable-http  # Streamable HTTP mode
"""

import sys
import argparse

from .service_layer import setup_path


def main():
    setup_path()

    parser = argparse.ArgumentParser(description="Owlangs MCP Server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run in HTTP mode (default: stdio mode)",
    )
    parser.add_argument(
        "--transport",
        type=str,
        default="streamable-http",
        choices=["sse", "streamable-http"],
        help="HTTP transport: 'sse' (SSE) or 'streamable-http' (Streamable HTTP, default)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8100,
        help="HTTP port (default: 8100)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="HTTP host (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    # Import here to ensure sys.path is set up first
    from .server import mcp

    if args.http:
        if args.transport == "sse":
            app = mcp.sse_app()
        else:
            app = mcp.streamable_http_app()

        import uvicorn
        print(f"Starting Owlangs MCP Server ({args.transport}) on {args.host}:{args.port}", file=sys.stderr)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    else:
        print("Starting Owlangs MCP Server in stdio mode", file=sys.stderr)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
