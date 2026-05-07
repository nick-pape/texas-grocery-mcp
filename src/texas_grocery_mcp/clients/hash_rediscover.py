"""Auto-rediscovery of HEB GraphQL persisted-query hashes.

When HEB rotates a hash, ``_execute_persisted_query`` raises
``PersistedQueryNotFoundError``. The client catches it, calls
``rediscover_hashes()`` here, and retries the original request once
with the freshly-discovered hash.

The discovery flow:

1. Launch headless Chromium with the existing Playwright auth state
   (``auth_state_path`` — same auth.json the rest of the MCP uses).
2. Attach a request interceptor that filters for graphql POSTs and
   captures ``operationName`` + ``extensions.persistedQuery.sha256Hash``
   from the request body.
3. Navigate a predefined set of HEB pages whose page-load JavaScript
   issues each tracked operation. Capture as many hashes as fall out.
4. Return the discovered ``op -> hash`` mapping. Caller feeds it to
   ``HashStore.rotate()``.

Notes:
- Mutation operations (e.g., ``CouponClip``, ``SelectPickupFulfillment``)
  don't fire on page load — they need an active interaction. This sweep
  is best-effort: the caller may receive a partial dict if the rotated
  op only fires on a button click. For those, the next call site that
  hits the stale hash will trigger another rediscovery; if THAT one
  also can't see the op, manual hash refresh is the escape hatch.
- This module imports ``playwright.async_api`` lazily so projects that
  install texas-grocery-mcp without the ``[browser]`` extra still work
  (they just lose self-heal on hash rotation).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from playwright.async_api import Request

logger = structlog.get_logger()


# Pages whose first paint triggers each tracked GraphQL operation.
# Map operation_name -> tuple of URLs whose page-load JS fires that op.
# When the client knows which op rotated, we visit ONLY the relevant
# page(s) — typically one — instead of broadcasting the full sweep.
# Other ops that happen to fire on the same page get captured for free.
#
# Mutations that only fire on user clicks (cartItemV2,
# SelectPickupFulfillment, CouponClip) intentionally have no entry here
# — passive page-load can't trigger them. For those, the broadcast
# fallback runs but won't recover the hash; manual override is the
# escape hatch.
OPERATION_PAGES: dict[str, tuple[str, ...]] = {
    "ShopNavigation": ("https://www.heb.com/",),
    "alertEntryPoint": ("https://www.heb.com/",),
    "cartEstimated": ("https://www.heb.com/cart",),
    "typeaheadContent": ("https://www.heb.com/search?q=milk",),
    "StoreSearch": ("https://www.heb.com/store-locations",),
    # Non-default ops we've observed firing on these pages:
    "entryPoint": ("https://www.heb.com/",),
    "getFrequentlyPurchasedProducts": ("https://www.heb.com/cart",),
    "historicCashbackEstimate": ("https://www.heb.com/cart",),
    "shoppingListCarouselV2": ("https://www.heb.com/",),
}

# Used when no target_operation is given (or its op isn't in
# OPERATION_PAGES). Visit a small spread that exercises common ops.
DEFAULT_DISCOVERY_URLS: tuple[str, ...] = (
    "https://www.heb.com/",
    "https://www.heb.com/cart",
    "https://www.heb.com/search?q=milk",
    "https://www.heb.com/category/all-coupons/490005",
)

DEFAULT_PAGE_TIMEOUT_MS = 20_000
DEFAULT_OVERALL_TIMEOUT_S = 60.0


async def rediscover_hashes(
    *,
    auth_state_path: Path | None = None,
    target_operation: str | None = None,
    urls: tuple[str, ...] | None = None,
    page_timeout_ms: int = DEFAULT_PAGE_TIMEOUT_MS,
    overall_timeout_s: float = DEFAULT_OVERALL_TIMEOUT_S,
) -> dict[str, str]:
    """Sweep HEB pages, capture persisted-query hashes from outgoing GraphQL.

    When ``target_operation`` is given and known to ``OPERATION_PAGES``,
    only the pages associated with that op are visited — typically one
    page, ~5-10s instead of the full ~30-60s broadcast. Any *other* ops
    that happen to fire on the same page are captured opportunistically.

    When ``target_operation`` is None or unknown, falls back to
    ``DEFAULT_DISCOVERY_URLS`` (broadcast).

    ``urls`` overrides both selection paths (used for tests/debugging).

    Returns a dict of ``operationName -> sha256Hash`` for every operation
    observed. May be partial if the rotated op doesn't fire passively
    (mutations need an interactive flow we don't simulate here).
    """
    if urls is None:
        if target_operation and target_operation in OPERATION_PAGES:
            urls = OPERATION_PAGES[target_operation]
        else:
            urls = DEFAULT_DISCOVERY_URLS
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "rediscover_hashes requires Playwright. "
            "Install with `pip install texas-grocery-mcp[browser]`."
        ) from exc

    discovered: dict[str, str] = {}

    def _capture(request: Request) -> None:
        try:
            url = request.url
            if "graphql" not in url.lower():
                return
            raw = request.post_data
            if not raw:
                return
            try:
                body: Any = json.loads(raw)
            except json.JSONDecodeError:
                return
            if isinstance(body, list):
                # Apollo batched payload — walk each entry.
                for entry in body:
                    _record(entry, discovered)
            else:
                _record(body, discovered)
        except Exception as e:  # noqa: BLE001 — defensive; never crash the page
            logger.debug("rediscover: capture handler error", error=str(e))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            context_kwargs: dict[str, Any] = {}
            if auth_state_path and Path(auth_state_path).exists():
                context_kwargs["storage_state"] = str(auth_state_path)
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()
            page.on("request", _capture)

            async def _visit_all() -> None:
                for url in urls:
                    try:
                        await page.goto(
                            url,
                            wait_until="networkidle",
                            timeout=page_timeout_ms,
                        )
                    except Exception as e:  # noqa: BLE001
                        # Per-page failures are tolerated — we still get
                        # partial results from other pages.
                        logger.warning(
                            "rediscover: navigation failed",
                            url=url,
                            error=str(e),
                        )

            try:
                await asyncio.wait_for(_visit_all(), timeout=overall_timeout_s)
            except TimeoutError:
                logger.warning(
                    "rediscover: overall timeout reached, returning partial results",
                    captured=sorted(discovered),
                )
        finally:
            await browser.close()

    logger.info(
        "rediscover: captured persisted-query hashes",
        count=len(discovered),
        operations=sorted(discovered),
    )
    return discovered


def _record(body: Any, into: dict[str, str]) -> None:
    if not isinstance(body, dict):
        return
    op = body.get("operationName")
    extensions = body.get("extensions") or {}
    persisted = extensions.get("persistedQuery") or {}
    sha = persisted.get("sha256Hash")
    if isinstance(op, str) and isinstance(sha, str) and op and sha and op not in into:
        into[op] = sha
