"""Session management for HEB authentication.

Uses Playwright MCP's storage state for authentication.
"""

import json
from typing import Any

import structlog

from texas_grocery_mcp.utils.config import get_settings

logger = structlog.get_logger()

# Module state for testing
_is_authenticated: bool = False


def _reset_auth_state() -> None:
    """Reset authentication state. For testing only."""
    global _is_authenticated
    _is_authenticated = False


def is_authenticated() -> bool:
    """Check if user is authenticated.

    Checks for valid auth state file from Playwright MCP.
    """
    global _is_authenticated

    # Check override for testing
    if _is_authenticated:
        return True

    settings = get_settings()
    auth_path = settings.auth_state_path

    if not auth_path.exists():
        return False

    try:
        with open(auth_path) as f:
            state = json.load(f)

        # Check for HEB session cookies
        cookies = state.get("cookies", [])
        heb_cookies = [c for c in cookies if "heb.com" in c.get("domain", "")]

        if not heb_cookies:
            return False

        # Check if any session cookie is present
        session_cookies = [c for c in heb_cookies if "session" in c.get("name", "").lower()]
        return len(session_cookies) > 0

    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read auth state", error=str(e))
        return False


def get_auth_instructions() -> list[str]:
    """Get instructions for authenticating with Playwright MCP."""
    settings = get_settings()
    return [
        "1. Use Playwright MCP: browser_navigate('https://www.heb.com/login')",
        "2. Complete the login process in the browser",
        "3. Use Playwright MCP: browser_run_code to save storage state:",
        f"   await page.context().storageState({{ path: '{settings.auth_state_path}' }})",
        "4. Retry this operation",
    ]


def check_auth() -> dict[str, Any]:
    """Check authentication status and return appropriate response."""
    if is_authenticated():
        return {
            "authenticated": True,
            "message": "Authenticated with HEB",
        }

    return {
        "authenticated": False,
        "auth_required": True,
        "message": "Login required for cart operations",
        "instructions": get_auth_instructions(),
    }


def get_cookies() -> list[dict[str, Any]]:
    """Get cookies for authenticated requests."""
    settings = get_settings()
    auth_path = settings.auth_state_path

    if not auth_path.exists():
        return []

    try:
        with open(auth_path) as f:
            state = json.load(f)
        return [c for c in state.get("cookies", []) if "heb.com" in c.get("domain", "")]
    except (json.JSONDecodeError, OSError):
        return []
