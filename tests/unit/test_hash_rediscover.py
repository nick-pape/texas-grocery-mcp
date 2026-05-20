"""Tests for hash_rediscover URL selection logic.

The actual Playwright sweep isn't exercised here — that needs a live
browser. We test that the URL-selection logic picks the right pages
based on the target_operation argument.
"""

from texas_grocery_mcp.clients.hash_rediscover import (
    DEFAULT_DISCOVERY_URLS,
    OPERATION_PAGES,
)


def test_known_operations_have_dedicated_pages():
    """Default-tracked ops should each have at least one URL."""
    for op in (
        "ShopNavigation",
        "alertEntryPoint",
        "cartEstimated",
        "typeaheadContent",
    ):
        assert op in OPERATION_PAGES, f"{op} missing from OPERATION_PAGES"
        urls = OPERATION_PAGES[op]
        assert urls, f"{op} has empty URL list"
        assert all(u.startswith("https://www.heb.com/") for u in urls)


def test_mutations_intentionally_absent():
    """Mutation ops can't be captured by passive page-load.

    The OPERATION_PAGES map should NOT include them — the targeted
    sweep would silently fail. Caller still gets the broadcast fallback
    (which also can't recover them, but at least the contract is honest).
    """
    for op in ("cartItemV2", "SelectPickupFulfillment", "CouponClip"):
        assert op not in OPERATION_PAGES, (
            f"{op} is a mutation; passive page-load can't capture it. "
            "Don't add it to OPERATION_PAGES — that would silently fail."
        )


def test_broadcast_covers_common_ops():
    """The broadcast fallback should hit the most-rotated common ops.

    Niche ops (e.g., StoreSearch on /store-locations) intentionally need
    a targeted sweep — we don't pad the broadcast with every op's page
    because that bloats the fallback latency for no win.
    """
    must_be_covered_by_broadcast = (
        "ShopNavigation",
        "cartEstimated",
        "typeaheadContent",
    )
    for op in must_be_covered_by_broadcast:
        op_urls = OPERATION_PAGES[op]
        assert any(u in DEFAULT_DISCOVERY_URLS for u in op_urls), (
            f"{op}'s pages {op_urls} aren't in DEFAULT_DISCOVERY_URLS — "
            "broadcast fallback won't catch a rotation"
        )


def test_mutation_flows_registry_keys_have_no_operation_pages_entry():
    """A mutation registered for active discovery MUST NOT also be in
    OPERATION_PAGES. The two registries are mutually exclusive — passive
    page-load can't capture mutations; if it could, we wouldn't need
    the click flow. Having both leads to silent failure.
    """
    from texas_grocery_mcp.clients.hash_rediscover import MUTATION_FLOWS

    for op in MUTATION_FLOWS:
        assert op not in OPERATION_PAGES, (
            f"{op} is in MUTATION_FLOWS — it must NOT also be in "
            "OPERATION_PAGES. Choose one discovery path per operation."
        )


def test_mutation_flows_contains_select_pickup_fulfillment():
    """SelectPickupFulfillment is the load-bearing mutation: store_change,
    cart_add, cart_remove all need its hash. Confirm we ship an active
    flow for it."""
    from texas_grocery_mcp.clients.hash_rediscover import MUTATION_FLOWS

    assert "SelectPickupFulfillment" in MUTATION_FLOWS
    flow = MUTATION_FLOWS["SelectPickupFulfillment"]
    assert callable(flow)


async def test_discover_mutation_hash_unknown_op_raises():
    """Unknown operation_name is a programming error, not silent return."""
    import pytest

    from texas_grocery_mcp.clients.hash_rediscover import discover_mutation_hash

    with pytest.raises(KeyError, match="no MUTATION_FLOWS entry"):
        await discover_mutation_hash("UnregisteredOperation")
