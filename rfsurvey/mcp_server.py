"""RFSURVEY MCP server — exposes analyze() as an MCP tool for Cognis.Studio."""
from __future__ import annotations

import json

from rfsurvey.core import SurveyError, analyze


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
    def rfsurvey_scan(csv_text: str) -> str:
        """Analyze RF spectrum-occupancy CSV for band usage and anomalies.

        Returns JSON findings, or a JSON error object on bad input.
        """
        try:
            report = analyze(csv_text)
            return json.dumps(report.to_dict())
        except SurveyError as exc:
            return json.dumps({"error": str(exc)})

    app.run()
    return 0
