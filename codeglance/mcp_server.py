"""CODEGLANCE MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from codeglance.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-codeglance[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-codeglance[mcp]'")
        return 1
    app = FastMCP("codeglance")

    @app.tool()
    def codeglance_scan(target: str) -> str:
        """Repo onboarding map — architecture + hotspots for humans and agents. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
