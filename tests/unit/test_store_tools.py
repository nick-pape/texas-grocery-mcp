"""Tests for store tools."""

import pytest
import respx
from httpx import Response


@pytest.fixture(autouse=True)
def reset_store_state():
    """Reset global store state before each test."""
    from texas_grocery_mcp.tools import store as store_module
    store_module._default_store_id = None
    store_module._graphql_client = None
    yield
    store_module._default_store_id = None
    store_module._graphql_client = None


@pytest.fixture
def mock_store_response():
    """Mock GraphQL store response."""
    return {
        "data": {
            "searchStoresByAddress": {
                "stores": [
                    {
                        "store": {
                            "id": "590",
                            "name": "H-E-B Mueller",
                            "address1": "1801 E 51st St",
                            "city": "Austin",
                            "state": "TX",
                            "postalCode": "78723",
                        },
                        "distance": 2.3,
                    }
                ]
            }
        }
    }


@pytest.mark.asyncio
@respx.mock
async def test_store_search_tool(mock_store_response):
    """store_search should return formatted stores."""
    from texas_grocery_mcp.tools.store import store_search

    respx.post("https://www.heb.com/graphql").mock(
        return_value=Response(200, json=mock_store_response)
    )

    result = await store_search(address="Austin, TX")

    assert len(result["stores"]) == 1
    assert result["stores"][0]["store_id"] == "590"
    assert result["stores"][0]["name"] == "H-E-B Mueller"


def test_store_set_default():
    """store_set_default should save store ID."""
    from texas_grocery_mcp.tools.store import store_get_default, store_set_default

    result = store_set_default(store_id="590")

    assert result["success"] is True
    assert result["store_id"] == "590"

    default = store_get_default()
    assert default["store_id"] == "590"


def test_store_get_default_none():
    """store_get_default should return None when not set."""
    from texas_grocery_mcp.tools import store as store_module

    # Reset the default
    store_module._default_store_id = None

    result = store_module.store_get_default()

    assert result["store_id"] is None
    assert "not set" in result["message"].lower()
