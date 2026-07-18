from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class Address(SQLModel, table=False):
    street: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = Field(default="", alias="postalCode")
    country: str = ""


class Property(SQLModel, table=True):
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
