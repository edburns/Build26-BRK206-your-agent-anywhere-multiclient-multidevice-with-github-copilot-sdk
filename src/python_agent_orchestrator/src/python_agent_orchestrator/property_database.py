import json
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from python_agent_orchestrator.models import Property


def create_engine_and_tables():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _is_waterfront(property_data: dict[str, Any]) -> bool:
    text_values = [
        property_data.get("shortDescription", ""),
        property_data.get("fullDescription", ""),
        *property_data.get("keyFeatures", []),
    ]
    return any("waterfront" in str(value).lower() for value in text_values)


def seed_database(engine, data_dir: str | Path) -> int:
    """Seed the database from JSON files. Idempotent — skips if already seeded."""
    with Session(engine) as session:
        existing = session.exec(select(func.count()).select_from(Property)).one()
        if existing > 0:
            return existing

    files = sorted(Path(data_dir).glob("*.json"))

    with Session(engine) as session:
        seed_count = 0
        for file_path in files:
            property_data = json.loads(file_path.read_text(encoding="utf-8"))
            address = property_data.get("address", {})
            session.add(
                Property(
                    id=property_data.get("id"),
                    type=property_data.get("type", ""),
                    status=property_data.get("status", ""),
                    price=property_data.get("price", 0),
                    currency=property_data.get("currency", ""),
                    street=address.get("street", ""),
                    city=address.get("city", ""),
                    province=address.get("province", ""),
                    postal_code=address.get("postalCode", ""),
                    country=address.get("country", ""),
                    bedrooms=property_data.get("bedrooms", 0),
                    bathrooms=property_data.get("bathrooms", 0),
                    square_footage=property_data.get("squareFootage", 0),
                    lot_size_square_footage=property_data.get("lotSizeSquareFootage"),
                    year_built=property_data.get("yearBuilt", 0),
                    parking_spaces=property_data.get("parkingSpaces", 0),
                    short_description=property_data.get("shortDescription", ""),
                    full_description=property_data.get("fullDescription", ""),
                    key_features=property_data.get("keyFeatures", []),
                    listed_date=property_data.get("listedDate", ""),
                    waterfront=_is_waterfront(property_data),
                )
            )
            seed_count += 1

        session.commit()

    return seed_count


_MAX_RESULTS = 100


def search_properties(
    engine,
    city: str | None = None,
    min_beds: int | None = None,
    max_price: int | None = None,
    waterfront: bool | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(Property)

    if city:
        statement = statement.where(Property.city.ilike(f"%{city}%"))
    if min_beds is not None:
        statement = statement.where(Property.bedrooms >= min_beds)
    if max_price is not None:
        statement = statement.where(Property.price <= max_price)
    if waterfront is not None:
        statement = statement.where(Property.waterfront == waterfront)

    capped = max(1, min(limit, _MAX_RESULTS)) if limit is not None else _MAX_RESULTS
    statement = statement.order_by(Property.id).limit(capped)

    with Session(engine) as session:
        properties = session.exec(statement).all()

    return [property_item.to_api_dict() for property_item in properties]
