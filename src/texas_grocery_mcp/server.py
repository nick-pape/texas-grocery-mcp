"""Texas Grocery MCP Server - FastMCP entry point."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import structlog
from fastmcp import FastMCP

from texas_grocery_mcp.observability.health import health_live, health_ready
from texas_grocery_mcp.observability.logging import configure_logging
from texas_grocery_mcp.tools.cart import (
    cart_add,
    cart_add_many,
    cart_add_with_retry,
    cart_check_auth,
    cart_get,
    cart_remove,
)
from texas_grocery_mcp.tools.coupon import (
    coupon_categories,
    coupon_clip,
    coupon_clipped,
    coupon_list,
    coupon_search,
)
from texas_grocery_mcp.tools.product import product_get, product_search, product_search_batch
from texas_grocery_mcp.tools.session import (
    session_clear,
    session_clear_credentials,
    session_refresh,
    session_save_credentials,
    session_save_instructions,
    session_status,
)
from texas_grocery_mcp.tools.store import (
    store_change,
    store_get_default,
    store_search,
)
from texas_grocery_mcp.utils.config import get_settings

# Configure logging before anything else
configure_logging()

logger = structlog.get_logger()


async def _reese84_keepwarm_loop(interval_s: int) -> None:
    """Background task: proactively renew reese84 so the session stays warm while
    idle, instead of relying solely on the lazy ensure_session refresh before each
    tool call. Refreshes once shortly after startup (so the MCP is in a good state
    immediately), then every ``interval_s`` seconds.

    ADAPTIVE BACKOFF (critical): HEB's Incapsula anti-bot flags accounts that get
    hammered — once it's hot it returns HTTP 401 to the headless refresh, and
    refreshing on a FIXED cadence into a hot account keeps it hot and prolongs the
    lockout (we caused exactly this during testing). So on any refresh failure we
    back off exponentially (up to ~1h) to let the account cool, and reset to the
    base cadence once a refresh succeeds. A well-behaved client must self-cool, not
    self-cook. The lazy ensure_session refresh still serves on-demand tool calls,
    and a real-Chrome re-capture revives a fully-cooled-but-expired session.
    Never crashes the server.
    """
    from texas_grocery_mcp.auth.browser_refresh import (
        is_playwright_available,
        refresh_session_with_browser,
    )

    settings = get_settings()
    base = interval_s
    cap = max(3600, base)  # max cool-off between attempts when hot (~1h)
    failures = 0
    # Short initial delay so the server finishes coming up; then refresh each
    # iteration (immediate first cycle = good state right away). Background task,
    # never blocks startup.
    await asyncio.sleep(5)
    while True:
        delay = base
        try:
            auth_path = settings.auth_state_path
            if not auth_path.exists() or not is_playwright_available():
                failures = 0  # nothing to do — not a failure, don't back off
            else:
                result = await refresh_session_with_browser(
                    auth_path=auth_path, headless=True, timeout=30000
                )
                failures = 0
                logger.info(
                    "keepwarm: reese84 refreshed",
                    elapsed_seconds=result.get("elapsed_seconds"),
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001 - keep-warm must never crash the server
            # Includes LoginRequiredError / BrowserRefreshError (e.g. HTTP 401 when
            # the account is hot). Back off so we stop feeding the anti-bot flag.
            failures += 1
            delay = min(base * 2**failures, cap)
            logger.warning(
                "keepwarm: refresh failed; backing off to let the account cool",
                error=str(e),
                consecutive_failures=failures,
                next_retry_s=delay,
            )
        await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """Lifespan hook for startup/shutdown tasks.

    On startup:
    - Checks session status
    - Auto-refreshes if enabled and session needs refresh
    """
    settings = get_settings()

    # Startup: Check and refresh session if needed
    if settings.auto_refresh_on_startup:
        try:
            from texas_grocery_mcp.auth.session import get_session_status

            status = get_session_status()
            logger.info(
                "Startup session check",
                authenticated=status["authenticated"],
                needs_refresh=status["needs_refresh"],
                time_remaining_hours=status["time_remaining_hours"],
            )

            # Auto-refresh if needed
            if status["needs_refresh"] or (
                status["time_remaining_hours"] is not None
                and status["time_remaining_hours"] < settings.auto_refresh_threshold_hours
            ):
                logger.info("Startup auto-refresh triggered")
                try:
                    result = await session_refresh(headless=True)
                    if result.get("success"):
                        logger.info(
                            "Startup session refresh successful",
                            elapsed_seconds=result.get("elapsed_seconds"),
                        )
                    else:
                        logger.warning(
                            "Startup session refresh failed",
                            error=result.get("error"),
                            error_type=result.get("error_type"),
                        )
                except Exception as e:
                    logger.warning("Startup session refresh error", error=str(e))

        except Exception as e:
            logger.warning("Startup session check failed", error=str(e))

    # Background keep-warm: proactively renew reese84 while idle, instead of only
    # the lazy ensure_session refresh before each tool call.
    keepwarm_task: asyncio.Task[None] | None = None
    if settings.reese84_keepwarm_interval_s > 0:
        keepwarm_task = asyncio.create_task(
            _reese84_keepwarm_loop(settings.reese84_keepwarm_interval_s)
        )
        logger.info(
            "reese84 keep-warm loop started",
            interval_s=settings.reese84_keepwarm_interval_s,
        )

    yield  # Server runs here

    # Shutdown
    if keepwarm_task is not None:
        keepwarm_task.cancel()
        with suppress(asyncio.CancelledError):
            await keepwarm_task
    logger.info("MCP server shutting down")

MCP_INSTRUCTIONS = """
## Texas Grocery MCP - Session Management

This MCP requires an authenticated HEB.com session for most operations.

### Before using cart, coupon, or store_change tools:
1. Call `session_status` to check authentication state
2. If `authenticated: false` or `needs_refresh: true`, call `session_refresh`
3. If session_refresh fails with headless mode, retry with `headless=False` for manual login

### Session states:
- `authenticated: true, needs_refresh: false` → Ready to use all tools
- `authenticated: true, refresh_recommended: true` → Works but consider refreshing soon
- `authenticated: false` or `needs_refresh: true` → Must refresh before cart/coupon operations

### Tools that work WITHOUT authentication:
- `store_search` - Find stores by address
- `product_search` / `product_search_batch` - Search products (uses local store default)
- `product_get` - Get detailed product info (ingredients, nutrition, warnings)
- `session_status` - Check session state
- `session_refresh` - Refresh/login

### Tools that REQUIRE authentication:
- `store_change` - Change store on HEB.com account
- `cart_get`, `cart_add`, `cart_add_many`, `cart_remove` - Cart operations
- `coupon_list`, `coupon_clip`, `coupon_clipped` - Coupon operations

### Typical workflow:
1. `session_status` → Check if authenticated
2. If not authenticated: `session_refresh(headless=False)` → User logs in via browser
3. `store_search("address")` → Find nearby stores
4. `store_change(store_id)` → Set preferred store
5. `product_search("query")` → Search for products
6. `cart_add(sku)` → Add to cart

### Automatic Login (Optional)
Save your HEB credentials once for automatic login when sessions expire:

1. `session_save_credentials(email, password)` → Store credentials securely
2. Now `session_refresh` will auto-login when session expires
3. `session_clear_credentials()` → Remove stored credentials if needed

### Human Handoff (Login/CAPTCHA/2FA/WAF)
When login requires human action (login form, CAPTCHA, 2FA, or a bot/WAF interstitial),
`session_refresh` returns immediately with:
- `status: "human_action_required"` - Clear indicator that human action is needed
- `action: "login" | "captcha" | "2fa" | "waf"` - What type of action is needed
- `screenshot_path: "/tmp/heb-login-<action>-123456.png"` - Screenshot of what's shown

**Workflow when human action is required:**
1. `session_refresh` returns with `status: "human_action_required"`
2. Read the screenshot at `screenshot_path` to see what's shown
3. Tell the user what's needed (log in, solve CAPTCHA, enter 2FA, or clear the WAF prompt)
4. User completes the action in the browser window that's open
5. User tells you "done" when finished
6. Call `session_refresh()` again to continue the login
7. Repeat until `status: "success"` or `status: "failed"`
"""

mcp = FastMCP(
    name="texas-grocery-mcp",
    version="0.2.0",
    instructions=MCP_INSTRUCTIONS,
    lifespan=lifespan,
)

# Register store tools
mcp.tool(annotations={"readOnlyHint": True})(store_search)
mcp.tool(annotations={"readOnlyHint": True})(store_get_default)
mcp.tool()(store_change)  # Changes store on HEB.com when authenticated, or sets local default

# Register product tools
mcp.tool(annotations={"readOnlyHint": True})(product_search)
mcp.tool(annotations={"readOnlyHint": True})(product_search_batch)
mcp.tool(annotations={"readOnlyHint": True})(product_get)

# Register coupon tools
mcp.tool(annotations={"readOnlyHint": True})(coupon_list)
mcp.tool(annotations={"readOnlyHint": True})(coupon_search)
mcp.tool(annotations={"readOnlyHint": True})(coupon_categories)
mcp.tool(annotations={"destructiveHint": True})(coupon_clip)
mcp.tool(annotations={"readOnlyHint": True})(coupon_clipped)

# Register cart tools (destructive operations require confirmation)
mcp.tool(annotations={"readOnlyHint": True})(cart_check_auth)
mcp.tool(annotations={"readOnlyHint": True})(cart_get)
mcp.tool(annotations={"destructiveHint": True})(cart_add)
mcp.tool(annotations={"destructiveHint": True})(cart_add_many)
mcp.tool(annotations={"destructiveHint": True})(cart_add_with_retry)
mcp.tool(annotations={"destructiveHint": True})(cart_remove)

# Register session tools
mcp.tool(annotations={"readOnlyHint": True})(session_status)
mcp.tool(annotations={"readOnlyHint": True})(session_save_instructions)
mcp.tool()(session_refresh)  # Uses embedded Playwright when available, falls back to commands
mcp.tool()(session_clear)
mcp.tool()(session_save_credentials)  # Store HEB credentials for auto-login
mcp.tool()(session_clear_credentials)  # Remove stored credentials

# Register health check tools
mcp.tool(annotations={"readOnlyHint": True})(health_live)
mcp.tool(annotations={"readOnlyHint": True})(health_ready)


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
