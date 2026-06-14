"""CODEGLANCE MCP server — exposes codeglance_scan() as an MCP tool."""
from __future__ import annotations

import json

from codeglance.core import build_map


def serve() -> int:
    """Start an MCP stdio server. Requires the optional mcp extra:
        pip install "cognis-codeglance[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Install the MCP extra: pip install 'cognis-codeglance[mcp]'")
        return 1
    app = FastMCP("codeglance")

    @app.tool()
    def codeglance_scan(target: str) -> str:
        """Repo onboarding map — architecture + hotspots. Returns JSON."""
        if not target or not isinstance(target, str):
            raise ValueError(
                f"target must be a non-empty string, got {target!r}"
            )
        try:
            rmap = build_map(target)
        except (FileNotFoundError, NotADirectoryError, OSError) as exc:
            raise ValueError(str(exc)) from exc
        return json.dumps(rmap.to_dict())

    app.run()
    return 0
