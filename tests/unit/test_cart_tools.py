"""Tests for cart tools."""

import pytest


@pytest.fixture(autouse=True)
def reset_auth_state():
    """Reset auth state before each test."""
    from texas_grocery_mcp.auth.session import _reset_auth_state
    _reset_auth_state()
    yield
    _reset_auth_state()


def test_cart_add_without_confirm_returns_preview():
    """cart_add without confirm should return preview."""
    from texas_grocery_mcp.tools.cart import cart_add

    import texas_grocery_mcp.auth.session as session_module
    session_module._is_authenticated = True

    result = cart_add(product_id="123456", quantity=2)

    assert result["preview"] is True
    assert result["action"] == "add_to_cart"
    assert "confirm" in result["message"].lower()


def test_cart_add_requires_auth():
    """cart_add should require authentication."""
    from texas_grocery_mcp.tools.cart import cart_add

    result = cart_add(product_id="123456", quantity=1)

    assert result["auth_required"] is True
    assert "instructions" in result


def test_cart_check_auth_returns_status():
    """cart_check_auth should return auth status."""
    from texas_grocery_mcp.tools.cart import cart_check_auth

    result = cart_check_auth()

    assert "authenticated" in result
    assert isinstance(result["authenticated"], bool)
