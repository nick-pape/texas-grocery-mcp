"""Texas Grocery MCP Server - FastMCP entry point."""

from fastmcp import FastMCP

from texas_grocery_mcp.tools.cart import cart_add, cart_check_auth, cart_get, cart_remove
from texas_grocery_mcp.tools.product import product_search
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

# Register product tools
mcp.tool(annotations={"readOnlyHint": True})(product_search)

# Register cart tools (destructive operations require confirmation)
mcp.tool(annotations={"readOnlyHint": True})(cart_check_auth)
mcp.tool(annotations={"readOnlyHint": True})(cart_get)
mcp.tool(annotations={"destructiveHint": True})(cart_add)
mcp.tool(annotations={"destructiveHint": True})(cart_remove)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
