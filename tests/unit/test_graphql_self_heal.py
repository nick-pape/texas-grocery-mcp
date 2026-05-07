"""Tests for the persisted-query self-heal flow on HEBGraphQLClient.

Covers:
- Stale-hash error → rediscover → rotate → retry once → success.
- Self-heal disabled via settings → error propagates.
- Rediscovery returns no useful hashes → original error propagates.
- Recursion guard: self-heal does not loop forever even if the second
  attempt also returns PersistedQueryNotFound.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import respx
from httpx import Response

from texas_grocery_mcp.clients import graphql as gql_module
from texas_grocery_mcp.clients.graphql import (
    HashStore,
    HEBGraphQLClient,
)

# NOTE: do NOT bind PersistedQueryNotFoundError at module load — another
# test in the suite (test_client_throttlers_use_settings) reloads
# graphql_module via importlib.reload, which creates fresh class identities.
# Bound references would no longer match isinstance checks against the
# reloaded class. Always read it as gql_module.PersistedQueryNotFoundError.


@pytest.fixture
def reset_persisted_queries():
    """Replace the module-level HashStore with a fresh one per test, restore after."""
    original = gql_module.PERSISTED_QUERIES
    fresh = HashStore(
        defaults={"cartEstimated": "STALE_HASH"},
        cache_path=None,  # in-memory only — no file IO during tests
    )
    gql_module.PERSISTED_QUERIES = fresh
    try:
        yield fresh
    finally:
        gql_module.PERSISTED_QUERIES = original


@pytest.fixture
def client():
    return HEBGraphQLClient()


def _stale_response() -> Response:
    return Response(
        200,
        json={"errors": [{"message": "PersistedQueryNotFound"}]},
    )


def _success_response(data: dict[str, Any]) -> Response:
    return Response(200, json={"data": data})


@pytest.mark.asyncio
@respx.mock
async def test_self_heal_rediscover_rotate_retry(client, reset_persisted_queries):
    """Stale hash → rediscovery returns new hash → rotate → second call succeeds."""
    route = respx.post("https://www.heb.com/graphql").mock(
        side_effect=[_stale_response(), _success_response({"cart": {"itemCount": 0}})]
    )

    fake_rediscover = AsyncMock(return_value={"cartEstimated": "FRESH_HASH"})
    with patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover):
        result = await client._execute_persisted_query("cartEstimated", {"x": 1})

    assert result == {"cart": {"itemCount": 0}}
    assert reset_persisted_queries["cartEstimated"] == "FRESH_HASH"
    fake_rediscover.assert_awaited_once()
    assert route.call_count == 2  # one stale, one retry

    # Second request used the rotated hash.
    second_payload = route.calls[1].request.read().decode()
    assert "FRESH_HASH" in second_payload
    assert "STALE_HASH" not in second_payload


@pytest.mark.asyncio
@respx.mock
async def test_self_heal_disabled_propagates_error(client, reset_persisted_queries):
    """When hash_self_heal_enabled=False, the original error bubbles up."""
    respx.post("https://www.heb.com/graphql").mock(return_value=_stale_response())

    fake_rediscover = AsyncMock(return_value={"cartEstimated": "FRESH_HASH"})
    with (
        patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover),
        patch("texas_grocery_mcp.clients.graphql.get_settings") as mock_settings,
    ):
        mock_settings.return_value.hash_self_heal_enabled = False

        with pytest.raises(gql_module.PersistedQueryNotFoundError):
            await client._execute_persisted_query("cartEstimated", {"x": 1})

    fake_rediscover.assert_not_awaited()
    assert reset_persisted_queries["cartEstimated"] == "STALE_HASH"


@pytest.mark.asyncio
@respx.mock
async def test_rediscovery_misses_op_propagates_error(client, reset_persisted_queries):
    """If rediscovery doesn't observe the rotated op, raise the original error."""
    respx.post("https://www.heb.com/graphql").mock(return_value=_stale_response())

    # Sweep returned hashes for OTHER operations but not the one we need.
    fake_rediscover = AsyncMock(return_value={"unrelatedOp": "some_hash"})
    with (
        patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover),
        pytest.raises(gql_module.PersistedQueryNotFoundError),
    ):
        await client._execute_persisted_query("cartEstimated", {"x": 1})

    fake_rediscover.assert_awaited_once()


@pytest.mark.asyncio
@respx.mock
async def test_rediscovery_returns_empty_propagates_error(client, reset_persisted_queries):
    respx.post("https://www.heb.com/graphql").mock(return_value=_stale_response())

    fake_rediscover = AsyncMock(return_value={})
    with (
        patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover),
        pytest.raises(gql_module.PersistedQueryNotFoundError),
    ):
        await client._execute_persisted_query("cartEstimated", {"x": 1})


@pytest.mark.asyncio
@respx.mock
async def test_rediscovery_raises_propagates_original_error(client, reset_persisted_queries):
    """If Playwright rediscovery itself errors, surface the GraphQL error.

    The rediscovery exception is swallowed by ``_try_self_heal``; the
    original ``PersistedQueryNotFoundError`` propagates to the caller.
    """
    respx.post("https://www.heb.com/graphql").mock(return_value=_stale_response())

    fake_rediscover = AsyncMock(side_effect=RuntimeError("playwright not installed"))
    with (
        patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover),
        pytest.raises(gql_module.PersistedQueryNotFoundError),
    ):
        await client._execute_persisted_query("cartEstimated", {"x": 1})


@pytest.mark.asyncio
@respx.mock
async def test_self_heal_no_infinite_loop_on_repeated_failure(client, reset_persisted_queries):
    """Even if the rotated hash STILL returns PersistedQueryNotFound, don't recurse."""
    route = respx.post("https://www.heb.com/graphql").mock(
        side_effect=[_stale_response(), _stale_response(), _stale_response()]
    )

    fake_rediscover = AsyncMock(return_value={"cartEstimated": "ALSO_STALE"})
    with (
        patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover),
        pytest.raises(gql_module.PersistedQueryNotFoundError),
    ):
        await client._execute_persisted_query("cartEstimated", {"x": 1})

    # Two requests: original (stale) + one retry (also stale, but we don't loop).
    assert route.call_count == 2
    fake_rediscover.assert_awaited_once()


@pytest.mark.asyncio
@respx.mock
async def test_self_heal_with_client_variant(client, reset_persisted_queries):
    """The cookie-bearing variant has the same self-heal behavior."""
    import httpx

    route = respx.post("https://www.heb.com/graphql").mock(
        side_effect=[_stale_response(), _success_response({"cart": {"itemCount": 5}})]
    )

    fake_rediscover = AsyncMock(return_value={"cartEstimated": "FRESH_HASH"})
    with patch("texas_grocery_mcp.clients.hash_rediscover.rediscover_hashes", fake_rediscover):
        async with httpx.AsyncClient() as auth_client:
            result = await client._execute_persisted_query_with_client(
                auth_client, "cartEstimated", {"x": 1}
            )

    assert result == {"cart": {"itemCount": 5}}
    assert reset_persisted_queries["cartEstimated"] == "FRESH_HASH"
    assert route.call_count == 2
