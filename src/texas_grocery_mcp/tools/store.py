"""Store-related MCP tools."""

from typing import Annotated

from pydantic import Field

from texas_grocery_mcp.clients.graphql import HEBGraphQLClient

# Module-level state for default store
_default_store_id: str | None = None
_graphql_client: HEBGraphQLClient | None = None


def _get_client() -> HEBGraphQLClient:
    """Get or create GraphQL client."""
    global _graphql_client
    if _graphql_client is None:
        _graphql_client = HEBGraphQLClient()
    return _graphql_client


async def store_search(
    address: Annotated[str, Field(description="Address or zip code to search near")],
    radius_miles: Annotated[
        int, Field(description="Search radius in miles", ge=1, le=100)
    ] = 25,
) -> dict:
    """Search for HEB stores near an address.

    Returns stores sorted by distance, including store ID, name,
    address, and distance from the search location.
    """
    client = _get_client()
    stores = await client.search_stores(address=address, radius_miles=radius_miles)

    return {
        "stores": [
            {
                "store_id": s.store_id,
                "name": s.name,
                "address": s.address,
                "distance_miles": s.distance_miles,
                "phone": s.phone,
            }
            for s in stores
        ],
        "count": len(stores),
    }


def store_set_default(
    store_id: Annotated[str, Field(description="Store ID to set as default", min_length=1)],
) -> dict:
    """Set the default store for future operations.

    The default store is used when no store_id is provided to other tools.
    """
    global _default_store_id
    _default_store_id = store_id.strip()

    return {
        "success": True,
        "store_id": _default_store_id,
        "message": f"Default store set to {_default_store_id}",
    }


def store_get_default() -> dict:
    """Get the currently set default store.

    Returns the default store ID if set, otherwise indicates no default.
    """
    if _default_store_id is None:
        return {
            "store_id": None,
            "message": "Default store not set. Use store_set_default to set one.",
        }

    return {
        "store_id": _default_store_id,
        "message": f"Default store is {_default_store_id}",
    }


def get_default_store_id() -> str | None:
    """Get default store ID for internal use."""
    return _default_store_id
