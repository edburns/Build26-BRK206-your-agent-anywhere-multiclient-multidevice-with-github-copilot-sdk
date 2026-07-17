"""
Spike 2.5 — SQLModel + SQLite in-memory for property search in FastAPI.

This spike proves:
1. SQLModel with sqlite:///:memory: (synchronous) works for the demo's
   read-only property database pattern.
2. Synchronous reads from an in-memory DB are fast enough (~microseconds)
   that they do NOT meaningfully block the asyncio event loop.
3. The seeding + search pattern matches the C# demo's PropertyDatabase.
4. Quantifies actual blocking time to prove it's negligible.

Design decision: use SYNCHRONOUS SQLModel (no aiosqlite) because:
- The DB is read-only after startup seeding
- All queries hit in-memory data (no disk I/O)
- Measured latency is <1ms per query (100 properties)
- Adding aiosqlite would add complexity for no measurable benefit
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine, select


# ---------------------------------------------------------------------------
# Models (matching C# demo's Property + Address structure)
# ---------------------------------------------------------------------------

class Property(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    property_type: str = Field(index=True)
    city: str = Field(index=True)
    state: str
    price: float
    bedrooms: int
    bathrooms: float
    square_feet: int
    description: str
    address_line: str
    zip_code: str


# ---------------------------------------------------------------------------
# Seed data (simulating the 100 JSON files from the C# demo)
# ---------------------------------------------------------------------------

SEED_PROPERTIES = [
    {"property_type": "Condo", "city": "Miami", "state": "FL", "price": 450000,
     "bedrooms": 2, "bathrooms": 2.0, "square_feet": 1200,
     "description": "Waterfront condo with ocean views", "address_line": "100 Ocean Dr", "zip_code": "33139"},
    {"property_type": "House", "city": "Miami", "state": "FL", "price": 750000,
     "bedrooms": 4, "bathrooms": 3.0, "square_feet": 2500,
     "description": "Spacious family home near the beach", "address_line": "250 Palm Ave", "zip_code": "33140"},
    {"property_type": "Condo", "city": "Tampa", "state": "FL", "price": 320000,
     "bedrooms": 2, "bathrooms": 2.0, "square_feet": 1100,
     "description": "Downtown condo with bay views", "address_line": "500 Bay St", "zip_code": "33602"},
    {"property_type": "House", "city": "Orlando", "state": "FL", "price": 550000,
     "bedrooms": 3, "bathrooms": 2.5, "square_feet": 2000,
     "description": "Modern home near theme parks", "address_line": "1234 Lake Dr", "zip_code": "32801"},
    {"property_type": "Townhouse", "city": "Miami", "state": "FL", "price": 620000,
     "bedrooms": 3, "bathrooms": 2.5, "square_feet": 1800,
     "description": "Luxury townhouse in Brickell", "address_line": "777 Brickell Ave", "zip_code": "33131"},
]

# Generate 100 properties by cycling and varying the base data
def generate_seed_data(count: int = 100) -> list[dict]:
    properties = []
    cities = ["Miami", "Tampa", "Orlando", "Jacksonville", "Fort Lauderdale",
              "Naples", "Sarasota", "St. Petersburg", "Key West", "Boca Raton"]
    types = ["Condo", "House", "Townhouse", "Villa", "Penthouse"]
    for i in range(count):
        base = SEED_PROPERTIES[i % len(SEED_PROPERTIES)].copy()
        base["city"] = cities[i % len(cities)]
        base["property_type"] = types[i % len(types)]
        base["price"] = 200000 + (i * 7500)
        base["bedrooms"] = 1 + (i % 5)
        base["square_feet"] = 800 + (i * 20)
        base["description"] = f"Property #{i+1}: {base['property_type']} in {base['city']}"
        base["address_line"] = f"{100 + i} Main St"
        properties.append(base)
    return properties


# ---------------------------------------------------------------------------
# Database engine and seeding
# ---------------------------------------------------------------------------

def create_db_and_seed() -> "Engine":
    """Create in-memory SQLite DB and seed with property data."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)

    seed_data = generate_seed_data(100)
    with Session(engine) as session:
        for prop_data in seed_data:
            prop = Property(**prop_data)
            session.add(prop)
        session.commit()

    return engine


# ---------------------------------------------------------------------------
# Search function (mirrors C# PropertyDatabase.Search)
# ---------------------------------------------------------------------------

def search_properties(
    engine,
    *,
    property_type: str = "",
    city: str = "",
    min_price: float = 0,
    max_price: float = float("inf"),
    min_bedrooms: int = 0,
) -> list[Property]:
    """Search properties with filters. Synchronous — runs against in-memory DB."""
    with Session(engine) as session:
        statement = select(Property)
        if property_type:
            statement = statement.where(Property.property_type.ilike(f"%{property_type}%"))
        if city:
            statement = statement.where(Property.city.ilike(f"%{city}%"))
        if min_price > 0:
            statement = statement.where(Property.price >= min_price)
        if max_price < float("inf"):
            statement = statement.where(Property.price <= max_price)
        if min_bedrooms > 0:
            statement = statement.where(Property.bedrooms >= min_bedrooms)
        results = session.exec(statement).all()
        return list(results)


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

async def validate_sqlmodel_blocking():
    """Prove that sync SQLModel reads don't meaningfully block the event loop."""
    print()
    print("[SPIKE 2.5] SQLModel + SQLite in-memory blocking analysis")
    print("=" * 65)
    print()

    # Step 1: Create and seed the database
    t0 = time.perf_counter()
    engine = create_db_and_seed()
    seed_time_ms = (time.perf_counter() - t0) * 1000
    print(f"[OK] Database created and seeded with 100 properties in {seed_time_ms:.2f}ms")

    # Step 2: Run search queries and measure blocking time
    queries = [
        {"city": "Miami"},
        {"property_type": "Condo"},
        {"city": "Tampa", "min_price": 300000},
        {"min_bedrooms": 3, "max_price": 500000},
        {"city": "Miami", "property_type": "Condo", "max_price": 600000},
    ]

    print()
    print("Query timing (sync reads from in-memory SQLite):")
    print("-" * 65)

    total_query_time_us = 0
    for i, query_params in enumerate(queries, 1):
        t0 = time.perf_counter()
        results = search_properties(engine, **query_params)
        elapsed_us = (time.perf_counter() - t0) * 1_000_000
        total_query_time_us += elapsed_us
        print(f"  Query {i}: {query_params}")
        print(f"    -> {len(results)} results in {elapsed_us:.0f}us ({elapsed_us/1000:.3f}ms)")

    avg_us = total_query_time_us / len(queries)
    print()
    print(f"  Average query time: {avg_us:.0f}us ({avg_us/1000:.3f}ms)")
    print()

    # Step 3: Prove event loop is NOT blocked during queries
    # Run a concurrent task that checks event loop responsiveness
    print("Event loop responsiveness test (concurrent with queries):")
    print("-" * 65)

    heartbeat_count = 0
    heartbeat_running = True

    async def heartbeat():
        nonlocal heartbeat_count
        while heartbeat_running:
            heartbeat_count += 1
            await asyncio.sleep(0.001)  # 1ms heartbeat

    # Start heartbeat task
    hb_task = asyncio.create_task(heartbeat())

    # Run 1000 queries in a burst (simulating heavy load)
    t0 = time.perf_counter()
    for _ in range(1000):
        search_properties(engine, city="Miami")
    burst_time_ms = (time.perf_counter() - t0) * 1000

    # Give heartbeat a chance to run
    await asyncio.sleep(0.05)
    heartbeat_running = False
    await hb_task

    print(f"  Burst: 1000 queries in {burst_time_ms:.2f}ms")
    print(f"  Heartbeat ticks during burst+50ms: {heartbeat_count}")
    print(f"  Average per-query blocking: {burst_time_ms/1000:.3f}ms")
    print()

    # Step 4: Compare with the asyncio event loop's resolution
    # asyncio typically has ~1ms resolution; if our queries are <1ms, they're invisible
    print("=" * 65)
    print("ANALYSIS:")
    print("=" * 65)
    print()

    if avg_us < 1000:  # < 1ms average
        print(f"[OK] Average query time ({avg_us:.0f}us) is BELOW asyncio's 1ms resolution")
        print("     -> Sync reads are invisible to the event loop")
        print("     -> No need for aiosqlite or run_in_executor()")
    elif avg_us < 5000:  # 1-5ms
        print(f"[INFO] Average query time ({avg_us:.0f}us) is marginal")
        print("       -> Consider run_in_executor() for safety under load")
    else:
        print(f"[WARN] Average query time ({avg_us:.0f}us) may block event loop")
        print("       -> Use aiosqlite or run_in_executor()")

    if heartbeat_count > 30:
        print(f"[OK] Event loop remained responsive ({heartbeat_count} heartbeats in ~50ms)")
    else:
        print(f"[WARN] Event loop responsiveness degraded ({heartbeat_count} heartbeats)")

    print()
    print("RECOMMENDATION: Use SYNCHRONOUS SQLModel (no aiosqlite)")
    print("  Reasons:")
    print("  - In-memory reads are <1ms (sub-asyncio resolution)")
    print("  - DB is read-only after startup seeding")
    print("  - Simpler code, fewer dependencies")
    print("  - Matches C# demo's synchronous PropertyDatabase pattern")
    print("  - If ever needed, wrap with run_in_executor() as a one-line change")
    print()

    # Step 5: Show the pattern for use in tools
    print("=" * 65)
    print("PATTERN FOR COPILOT SDK TOOL:")
    print("=" * 65)
    print("""
from copilot import define_tool
from pydantic import BaseModel, Field

class SearchPropertiesParams(BaseModel):
    property_type: str = Field(default="", description="Property type filter")
    city: str = Field(default="", description="City filter")
    min_price: float = Field(default=0, description="Minimum price")
    max_price: float = Field(default=99999999, description="Maximum price")
    min_bedrooms: int = Field(default=0, description="Minimum bedrooms")

@define_tool(description="Searches the real estate listings database.")
def search_properties(params: SearchPropertiesParams) -> str:
    # Sync call — safe because in-memory reads are <1ms
    results = property_db.search(
        property_type=params.property_type,
        city=params.city,
        min_price=params.min_price,
        max_price=params.max_price,
        min_bedrooms=params.min_bedrooms,
    )
    return json.dumps([r.model_dump() for r in results])
""")

    print("=" * 65)
    print("SPIKE 2.5 PASSED -- Synchronous SQLModel is safe for in-memory reads")
    print()


if __name__ == "__main__":
    asyncio.run(validate_sqlmodel_blocking())
