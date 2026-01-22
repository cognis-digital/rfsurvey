"""RFSURVEY MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from rfsurvey.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-rfsurvey[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-rfsurvey[mcp]'")
        return 1
    app = FastMCP("rfsurvey")

    @app.tool()
    def rfsurvey_scan(target: str) -> str:
        """Analyze RF spectrum-occupancy CSV/metadata for band usage, interference, and anomalies.. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
