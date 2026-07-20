import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy import func
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from python_agent_orchestrator.models import Property

logger = logging.getLogger(__name__)


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
    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"Seed data directory does not exist: {data_path}")

    files = sorted(data_path.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON seed files found in: {data_path}")

    with Session(engine) as session:
        existing = session.exec(select(func.count()).select_from(Property)).one()
        if existing > 0:
            logger.info("Property database already seeded with %d record(s)", existing)
            return existing

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
    logger.info("Seeded property database with %d record(s) from %s", seed_count, data_path)

    return seed_count


_MAX_RESULTS = 100
_NO_CITY_FILTER_TOKENS = {
    "any",
    "any city",
    "all",
    "n/a",
    "na",
    "none",
    "no preference",
    "doesn't matter",
    "dont care",
    "does not matter",
}


def _normalize_city_filter(city: str | None) -> str | None:
    if city is None:
        return None
    normalized = city.strip()
    if not normalized:
        return None
    if normalized.lower() in _NO_CITY_FILTER_TOKENS:
        return None
    return normalized


def _normalize_text_filter(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = text.strip()
    return normalized or None


def search_properties(
    engine,
    city: str | None = None,
    min_beds: int | None = None,
    max_price: int | None = None,
    waterfront: bool | None = None,
    text_contains: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    statement = select(Property)

    city_filter = _normalize_city_filter(city)
    text_filter = _normalize_text_filter(text_contains)

    if city_filter:
        statement = statement.where(Property.city.ilike(f"%{city_filter}%"))
    if min_beds is not None:
        statement = statement.where(Property.bedrooms >= min_beds)
    if max_price is not None:
        statement = statement.where(Property.price <= max_price)
    if waterfront is not None:
        statement = statement.where(Property.waterfront == waterfront)
    if text_filter:
        pattern = f"%{text_filter}%"
        statement = statement.where(
            or_(
                Property.short_description.ilike(pattern),
                Property.full_description.ilike(pattern),
                Property.street.ilike(pattern),
                Property.city.ilike(pattern),
                Property.type.ilike(pattern),
            )
        )

    capped = max(1, min(limit, _MAX_RESULTS)) if limit is not None else _MAX_RESULTS
    statement = statement.order_by(Property.id).limit(capped)

    with Session(engine) as session:
        properties = session.exec(statement).all()

    return [property_item.to_api_dict() for property_item in properties]
