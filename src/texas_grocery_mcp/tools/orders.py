"""HEB order history tools — past/active orders + per-order detail.

Mobile/bearer only (the order operations live on HEB's mobile API, no Incapsula).
Both are read-only.
"""

from typing import TYPE_CHECKING, Annotated, Any

import structlog
from pydantic import Field

from texas_grocery_mcp.auth.session import ensure_session
from texas_grocery_mcp.state import StateManager

if TYPE_CHECKING:
    from texas_grocery_mcp.clients.graphql import HEBGraphQLClient

logger = structlog.get_logger()


def _get_client() -> "HEBGraphQLClient":
    """Get or create the shared GraphQL client."""
    return StateManager.get_graphql_client_sync()


@ensure_session
async def get_order_history(
    status: Annotated[
        str | None,
        Field(
            description="Filter to one status ('ACTIVE' or 'COMPLETED'). Omit to get both, merged."
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Maximum orders to return (default 10).", ge=1, le=50),
    ] = 10,
) -> dict[str, Any]:
    """List your recent H-E-B orders (active + completed).

    Returns each order's ``order_id``, ``status``, fulfillment type, store, pickup/
    delivery date, ``total``, and item count. Pass an ``order_id`` to
    ``get_order_details`` for the full line items.
    """
    client = _get_client()
    return await client.get_order_history(status=status, limit=limit)


@ensure_session
async def get_order_details(
    order_id: Annotated[
        str,
        Field(description="Order ID from get_order_history (e.g. 'HEB24702750622')"),
    ],
) -> dict[str, Any]:
    """Get full detail for one H-E-B order: line items, quantities, prices, and totals.

    Returns the order's items (name, quantity, price), subtotal/tax/total, status,
    fulfillment type, store, and timeslot.
    """
    client = _get_client()
    return await client.get_order_details(order_id=order_id)
