"""Self-contained MCP (Model Context Protocol) server for wavewatch."""

from __future__ import annotations

from .server import (
    TOOLS,
    build_response,
    handle_request,
    serve_stdio,
    tool_analyze_capture,
)

__all__ = [
    "handle_request",
    "build_response",
    "serve_stdio",
    "tool_analyze_capture",
    "TOOLS",
]
