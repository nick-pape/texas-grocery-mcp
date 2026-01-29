"""Texas Grocery MCP Server - FastMCP entry point."""

from fastmcp import FastMCP

from texas_grocery_mcp.tools.store import (
    store_get_default,
    store_search,
    store_set_default,
)

mcp = FastMCP(
    name="texas-grocery-mcp",
    version="0.1.0",
)

# Register store tools
mcp.tool(annotations={"readOnlyHint": True})(store_search)
mcp.tool()(store_set_default)
mcp.tool(annotations={"readOnlyHint": True})(store_get_default)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
