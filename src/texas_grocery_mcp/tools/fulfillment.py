"""HEB curbside checkout tools — pickup timeslots + reservation.

Mobile/bearer only (the timeslot + reserve operations live on HEB's mobile API).
Reserving a slot is a soft commitment: it holds the pickup time for the current
cart with a "place your order by" deadline; no payment is taken here.
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
async def get_curbside_slots(
    store_id: Annotated[
        str | None,
        Field(description="Store ID. Uses the default store if not provided."),
    ] = None,
    days: Annotated[
        int,
        Field(description="Days ahead to search for slots (default 14).", ge=1, le=30),
    ] = 14,
) -> dict[str, Any]:
    """List available HEB curbside pickup timeslots for a store.

    Returns each slot's ``slot_id``, ``date``, time window, ``fee``, and
    ``available`` flag. Pass an available slot's ``slot_id`` + ``date`` to
    ``reserve_curbside_slot`` to hold that pickup time for the current cart.
    """
    client = _get_client()
    return await client.get_curbside_slots(store_id=store_id, days=days)


@ensure_session
async def reserve_curbside_slot(
    slot_id: Annotated[str, Field(description="Slot ID from get_curbside_slots")],
    date: Annotated[
        str,
        Field(description="Slot date from get_curbside_slots (e.g. '2026-05-25')"),
    ],
    store_id: Annotated[
        str | None,
        Field(description="Store ID. Uses the default store if not provided."),
    ] = None,
    confirm: Annotated[
        bool,
        Field(description="Must be true to actually reserve. Without it, returns a preview."),
    ] = False,
) -> dict[str, Any]:
    """Reserve (hold) a curbside pickup timeslot for the current cart.

    Holds the slot with a "place your order by" deadline — **no payment is taken
    here**. Without ``confirm=true`` this returns a preview instead of reserving.
    """
    if not confirm:
        return {
            "preview": True,
            "action": "reserve_curbside_slot",
            "slot_id": slot_id,
            "date": date,
            "store_id": store_id,
            "message": "Preview only. Call again with confirm=true to hold this pickup slot.",
        }
    client = _get_client()
    return await client.reserve_curbside_slot(slot_id=slot_id, date=date, store_id=store_id)
