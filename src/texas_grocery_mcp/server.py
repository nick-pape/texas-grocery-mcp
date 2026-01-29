"""Texas Grocery MCP Server - FastMCP entry point."""

from fastmcp import FastMCP

mcp = FastMCP(
    name="texas-grocery-mcp",
    version="0.1.0",
)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
