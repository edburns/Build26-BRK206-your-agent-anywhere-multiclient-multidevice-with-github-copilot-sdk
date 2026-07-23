from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Address(SQLModel, table=False):
    """Address value object matching the C# Address shape."""

    street: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = Field(default="", alias="postalCode")
    country: str = ""


class Property(SQLModel, table=True):
    """Property entity — address fields are flattened for DB storage
    (mirrors C# EF Core ``OwnsOne``), but ``to_api_dict()`` returns the
    nested camelCase shape that matches the C# demo and seed JSON."""

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = ""
    status: str = ""
    price: int = 0
    currency: str = ""

    street: str = ""
    city: str = Field(default="", index=True)
    province: str = ""
    postal_code: str = ""
    country: str = ""

    bedrooms: int = Field(default=0, index=True)
    bathrooms: int = 0
    square_footage: int = 0
    lot_size_square_footage: Optional[int] = None
    year_built: int = 0
    parking_spaces: int = 0
    short_description: str = ""
    full_description: str = ""
    key_features: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    listed_date: str = ""
    waterfront: bool = Field(default=False, index=True)

    def to_api_dict(self) -> dict[str, Any]:
        """Return a camelCase dict with nested ``address``,
        matching the C# ``Property``/``Address`` JSON shape."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "price": self.price,
            "currency": self.currency,
            "address": {
                "street": self.street,
                "city": self.city,
                "province": self.province,
                "postalCode": self.postal_code,
                "country": self.country,
            },
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "squareFootage": self.square_footage,
            "lotSizeSquareFootage": self.lot_size_square_footage,
            "yearBuilt": self.year_built,
            "parkingSpaces": self.parking_spaces,
            "shortDescription": self.short_description,
            "fullDescription": self.full_description,
            "keyFeatures": self.key_features,
            "listedDate": self.listed_date,
            "waterfront": self.waterfront,
        }
