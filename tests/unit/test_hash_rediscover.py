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
