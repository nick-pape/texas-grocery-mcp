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
# Add a URL when a new operation rotates and isn't captured here.
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
    urls: tuple[str, ...] = DEFAULT_DISCOVERY_URLS,
    page_timeout_ms: int = DEFAULT_PAGE_TIMEOUT_MS,
    overall_timeout_s: float = DEFAULT_OVERALL_TIMEOUT_S,
) -> dict[str, str]:
    """Sweep HEB pages, capture persisted-query hashes from outgoing GraphQL.

    Returns a dict of ``operationName -> sha256Hash`` for every operation
    observed. May be partial if a tracked op doesn't fire during the sweep.
    """
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
