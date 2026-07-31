from datetime import UTC, datetime

import pytest

from import_cars.analysis.opportunity import apply_opportunity_analysis
from import_cars.models import NormalizedListing, Registration, Seller


def listing(
    listing_id: str,
    *,
    source: str,
    title: str,
    price: float,
    year: int = 2020,
    fuel: str = "diesel",
    power_hp: int = 265,
    displacement_cc: int = 2_993,
    seller_type: str = "dealer",
) -> NormalizedListing:
    return NormalizedListing(
        listing_id=listing_id,
        source=source,
        url=f"https://example.com/{listing_id}",
        scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        title=title,
        make="BMW",
        model="X5",
        price_eur=price,
        first_registration=Registration(year=year, month=6),
        fuel_type=fuel,
        power_hp=power_hp,
        engine_displacement_cc=displacement_cc,
        seller=Seller(type=seller_type),
    )


def test_exact_comparables_drive_market_values_margin_and_score() -> None:
    german = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=25_000,
    )
    german.co2_confidence = 0.8
    spanish = [
        listing(
            "es-1",
            source="coches_net",
            title="BMW X5 xDrive30d",
            price=40_000,
        ),
        listing(
            "es-2",
            source="coches_net",
            title="BMW X5 xDrive30d",
            price=42_000,
            year=2021,
            power_hp=258,
        ),
    ]

    opportunities = apply_opportunity_analysis(
        [german],
        spanish,
        {
            "de-1": {
                "particular": 31_000,
                "empresa_iva": 30_000,
                "empresa_margen": 30_500,
            }
        },
    )

    assert len(opportunities) == 1
    assert german.comparable_match_level == "exact"
    assert german.es_exact_sample_size == 2
    assert german.es_market_avg == 41_000
    assert german.es_market_median == 41_000
    assert german.es_market_min == 40_000
    assert german.best_break_even == 30_000
    assert german.potential_margin_avg == 11_000
    assert german.potential_margin_min == 10_000
    assert german.import_ready_score == 72.67
    assert opportunities[0]["rentabilidad"] == pytest.approx(36.6666667)


def test_private_seller_uses_particular_break_even() -> None:
    german = listing(
        "de-private",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=25_000,
        seller_type="private",
    )
    spanish = listing(
        "es-1",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=40_000,
    )

    apply_opportunity_analysis(
        [german],
        [spanish],
        {"de-private": {"particular": 32_000, "empresa_iva": 29_000}},
    )

    assert german.best_break_even == 32_000


def test_non_homologable_listings_are_not_used_as_comparables() -> None:
    german = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=25_000,
    )
    wrong_fuel = listing(
        "es-petrol",
        source="coches_net",
        title="BMW X5 xDrive40i",
        price=45_000,
        fuel="gasoline",
    )
    distant_engine = listing(
        "es-engine",
        source="coches_net",
        title="BMW X5 xDrive25d",
        price=39_000,
        power_hp=150,
        displacement_cc=1_995,
    )

    opportunities = apply_opportunity_analysis(
        [german],
        [wrong_fuel, distant_engine],
        {"de-1": {"empresa_iva": 30_000}},
    )

    assert opportunities == []
    assert german.es_sample_size == 0
    assert german.comparable_match_level is None


def test_different_known_engine_variants_never_match() -> None:
    german = listing(
        "de-30d",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=25_000,
        power_hp=265,
    )
    spanish = listing(
        "es-40d",
        source="coches_net",
        title="BMW X5 xDrive40d",
        price=45_000,
        power_hp=286,
    )

    opportunities = apply_opportunity_analysis(
        [german],
        [spanish],
        {"de-30d": {"empresa_iva": 31_000}},
    )

    assert opportunities == []
    assert german.es_sample_size == 0


def test_opportunities_are_sorted_by_import_ready_score() -> None:
    first = listing(
        "de-low",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=29_000,
    )
    second = listing(
        "de-high",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=24_000,
    )
    spanish = listing(
        "es-1",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=40_000,
    )

    opportunities = apply_opportunity_analysis(
        [first, second],
        [spanish],
        {
            "de-low": {"empresa_iva": 35_000},
            "de-high": {"empresa_iva": 29_000},
        },
    )

    assert [item["listing"].listing_id for item in opportunities] == [
        "de-high",
        "de-low",
    ]
