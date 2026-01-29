"""Tests for data models."""

import pytest


def test_store_model_required_fields():
    """Store model should require essential fields."""
    from texas_grocery_mcp.models import Store

    store = Store(
        store_id="590",
        name="H-E-B Mueller",
        address="1801 E 51st St, Austin, TX 78723",
    )

    assert store.store_id == "590"
    assert store.name == "H-E-B Mueller"
    assert store.address == "1801 E 51st St, Austin, TX 78723"


def test_product_model_minimal_fields():
    """Product model should work with minimal fields."""
    from texas_grocery_mcp.models import Product

    product = Product(
        sku="123456",
        name="HEB Whole Milk",
        price=3.49,
        available=True,
    )

    assert product.sku == "123456"
    assert product.price == 3.49


def test_product_model_full_fields():
    """Product model should accept all optional fields."""
    from texas_grocery_mcp.models import Product

    product = Product(
        sku="123456",
        name="HEB Whole Milk",
        price=3.49,
        available=True,
        brand="H-E-B",
        size="1 gallon",
        price_per_unit="$3.49/gal",
        image_url="https://example.com/milk.jpg",
        aisle="5",
        section="Dairy",
        on_sale=True,
        original_price=4.29,
    )

    assert product.brand == "H-E-B"
    assert product.on_sale is True


def test_cart_item_calculates_subtotal():
    """CartItem should calculate subtotal from price and quantity."""
    from texas_grocery_mcp.models import CartItem

    item = CartItem(
        sku="123456",
        name="HEB Whole Milk",
        price=3.49,
        quantity=2,
    )

    assert item.subtotal == 6.98


def test_error_response_structure():
    """ErrorResponse should have proper structure."""
    from texas_grocery_mcp.models import ErrorResponse

    error = ErrorResponse(
        code="HEB_API_TIMEOUT",
        category="external",
        message="HEB API request timed out",
        retry_after_seconds=30,
        suggestions=["Try again in 30 seconds"],
    )

    assert error.error is True
    assert error.category == "external"
    assert error.retry_after_seconds == 30
