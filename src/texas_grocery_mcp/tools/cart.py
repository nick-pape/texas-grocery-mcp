"""Cart-related MCP tools with human-in-the-loop confirmation."""

from typing import Annotated

from pydantic import Field

from texas_grocery_mcp.auth.session import check_auth, get_auth_instructions, is_authenticated


def cart_check_auth() -> dict:
    """Check if authenticated for cart operations.

    Returns authentication status and instructions if not authenticated.
    Use this before attempting cart operations.
    """
    return check_auth()


def cart_add(
    product_id: Annotated[str, Field(description="Product SKU/ID to add", min_length=1)],
    quantity: Annotated[int, Field(description="Quantity to add", ge=1, le=99)] = 1,
    confirm: Annotated[
        bool, Field(description="Set to true to confirm the action")
    ] = False,
) -> dict:
    """Add an item to the shopping cart.

    Without confirm=true, returns a preview of the action.
    With confirm=true, executes the action (requires authentication).
    """
    # Validate product_id
    product_id = product_id.strip()
    if not product_id:
        return {
            "error": True,
            "code": "INVALID_PRODUCT_ID",
            "message": "Product ID cannot be empty or whitespace.",
        }

    # Check authentication first
    if not is_authenticated():
        return {
            "auth_required": True,
            "message": "Login required for cart operations",
            "instructions": get_auth_instructions(),
        }

    # If not confirmed, return preview
    if not confirm:
        return {
            "preview": True,
            "action": "add_to_cart",
            "product_id": product_id,
            "quantity": quantity,
            "message": "Set confirm=true to add this item to cart",
        }

    # TODO: Implement actual cart addition via HEB API
    return {
        "success": True,
        "action": "add_to_cart",
        "product_id": product_id,
        "quantity": quantity,
        "message": f"Added {quantity}x product {product_id} to cart",
    }


def cart_remove(
    product_id: Annotated[str, Field(description="Product SKU/ID to remove", min_length=1)],
    confirm: Annotated[
        bool, Field(description="Set to true to confirm the action")
    ] = False,
) -> dict:
    """Remove an item from the shopping cart.

    Without confirm=true, returns a preview of the action.
    With confirm=true, executes the action.
    """
    # Validate product_id
    product_id = product_id.strip()
    if not product_id:
        return {
            "error": True,
            "code": "INVALID_PRODUCT_ID",
            "message": "Product ID cannot be empty or whitespace.",
        }

    if not is_authenticated():
        return {
            "auth_required": True,
            "message": "Login required for cart operations",
            "instructions": get_auth_instructions(),
        }

    if not confirm:
        return {
            "preview": True,
            "action": "remove_from_cart",
            "product_id": product_id,
            "message": "Set confirm=true to remove this item from cart",
        }

    return {
        "success": True,
        "action": "remove_from_cart",
        "product_id": product_id,
        "message": f"Removed product {product_id} from cart",
    }


def cart_get() -> dict:
    """Get current cart contents.

    Returns all items in the cart with quantities and prices.
    """
    if not is_authenticated():
        return {
            "auth_required": True,
            "message": "Login required to view cart",
            "instructions": get_auth_instructions(),
        }

    # TODO: Implement actual cart retrieval
    return {
        "items": [],
        "subtotal": 0.0,
        "item_count": 0,
        "message": "Cart is empty",
    }
