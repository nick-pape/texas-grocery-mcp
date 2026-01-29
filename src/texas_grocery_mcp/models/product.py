"""Product data models."""

from pydantic import BaseModel, Field


class ProductNutrition(BaseModel):
    """Nutritional information."""

    calories: int | None = None
    protein: str | None = None
    carbohydrates: str | None = None
    fat: str | None = None
    fiber: str | None = None
    sodium: str | None = None


class ProductCoupon(BaseModel):
    """Coupon applicable to product."""

    code: str
    discount: str
    expires: str | None = None


class Product(BaseModel):
    """HEB product information."""

    # Minimal fields (always returned)
    sku: str = Field(description="Product SKU/ID")
    name: str = Field(description="Product name")
    price: float = Field(description="Current price")
    available: bool = Field(description="In stock at store")

    # Standard fields (optional)
    brand: str | None = Field(default=None, description="Brand name")
    size: str | None = Field(default=None, description="Package size")
    price_per_unit: str | None = Field(default=None, description="Unit price display")
    image_url: str | None = Field(default=None, description="Product image URL")
    aisle: str | None = Field(default=None, description="Store aisle number")
    section: str | None = Field(default=None, description="Store section")

    # Extended fields (optional)
    nutrition: ProductNutrition | None = Field(default=None, description="Nutrition facts")
    ingredients: list[str] | None = Field(default=None, description="Ingredient list")
    on_sale: bool = Field(default=False, description="Currently on sale")
    original_price: float | None = Field(default=None, description="Price before sale")
    rating: float | None = Field(default=None, ge=0, le=5, description="Customer rating")
    coupons: list[ProductCoupon] = Field(
        default_factory=list, description="Applicable coupons"
    )
