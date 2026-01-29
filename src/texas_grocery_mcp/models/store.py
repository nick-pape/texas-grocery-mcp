"""Store data models."""

from pydantic import BaseModel, Field


class StoreHours(BaseModel):
    """Store operating hours."""

    monday: str = Field(alias="mon", default="6am-11pm")
    tuesday: str = Field(alias="tue", default="6am-11pm")
    wednesday: str = Field(alias="wed", default="6am-11pm")
    thursday: str = Field(alias="thu", default="6am-11pm")
    friday: str = Field(alias="fri", default="6am-11pm")
    saturday: str = Field(alias="sat", default="6am-11pm")
    sunday: str = Field(alias="sun", default="6am-11pm")

    model_config = {"populate_by_name": True}


class Store(BaseModel):
    """HEB store information."""

    store_id: str = Field(description="Unique store identifier")
    name: str = Field(description="Store display name")
    address: str = Field(description="Full street address")
    phone: str | None = Field(default=None, description="Store phone number")
    distance_miles: float | None = Field(
        default=None, description="Distance from search location"
    )
    hours: StoreHours | None = Field(default=None, description="Operating hours")
    services: list[str] = Field(
        default_factory=list,
        description="Available services (curbside, delivery, pharmacy)",
    )
    latitude: float | None = Field(default=None, description="Store latitude")
    longitude: float | None = Field(default=None, description="Store longitude")
