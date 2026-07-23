import json
from pathlib import Path

from python_agent_orchestrator.property_database import (
    create_engine_and_tables,
    search_properties,
    seed_database,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "properties"


def test_seed_database_loads_all_properties() -> None:
    engine = create_engine_and_tables()

    seeded = seed_database(engine, DATA_DIR)
    all_properties = search_properties(engine)

    assert seeded == 100
    assert len(all_properties) == 100


def test_search_properties_filters_match_expected_subsets() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)

    toronto_results = search_properties(engine, city="Toronto")
    assert toronto_results
    assert all(
        result["address"]["city"] == "Toronto" for result in toronto_results
    )

    miami_results = search_properties(engine, city="Miami")
    assert miami_results
    assert all(
        result["address"]["city"] == "Miami" for result in miami_results
    )

    waterfront_results = search_properties(engine, min_beds=3, waterfront=True)
    assert waterfront_results
    assert all(result["bedrooms"] >= 3 for result in waterfront_results)
    assert all(result["waterfront"] is True for result in waterfront_results)

    # Verify camelCase nested shape matches C# demo output
    sample = waterfront_results[0]
    assert "address" in sample and isinstance(sample["address"], dict)
    assert "postalCode" in sample["address"]
    assert "squareFootage" in sample
    assert "keyFeatures" in sample

    json.dumps(waterfront_results)


def test_search_properties_returns_empty_list_for_no_matches() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)

    no_results = search_properties(
        engine,
        city="NoSuchCity",
        min_beds=10,
        max_price=100_000,
        waterfront=True,
    )

    assert no_results == []


def test_search_properties_treats_any_city_as_no_city_filter() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)

    any_city_results = search_properties(engine, city="Any")
    unfiltered_results = search_properties(engine)

    assert any_city_results
    assert len(any_city_results) == len(unfiltered_results)


def test_search_properties_supports_text_contains() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)

    victorian_results = search_properties(engine, text_contains="Victorian")

    assert victorian_results
    assert all(
        "victorian" in (
            (
                f"{result['shortDescription']} {result['fullDescription']} "
                f"{result['address']['street']} {result['address']['city']} {result['type']}"
            ).lower()
        )
        for result in victorian_results
    )
