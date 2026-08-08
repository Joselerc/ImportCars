from datetime import UTC, datetime

import pytest

from import_cars.analysis.opportunity import (
    apply_opportunity_analysis,
    match_decision,
    match_level,
)
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
    mileage_km: int = 60_000,
    transmission: str | None = "automatic",
    battery_capacity_kwh: float | None = None,
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
        mileage_km=mileage_km,
        transmission=transmission,
        battery_capacity_kwh=battery_capacity_kwh,
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


@pytest.mark.parametrize(
    ("mileage_delta", "expected_level"),
    [
        (15_000, "exact"),
        (15_001, "near"),
        (35_000, "near"),
        (35_001, "broad"),
        (60_000, "broad"),
        (60_001, None),
    ],
)
def test_mileage_thresholds_define_each_match_level(
    mileage_delta: int,
    expected_level: str | None,
) -> None:
    target = listing(
        "de-km",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
        mileage_km=100_000,
    )
    candidate = listing(
        "es-km",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=40_000,
        mileage_km=100_000 + mileage_delta,
    )

    assert match_level(target, candidate) == expected_level


def test_exact_requires_same_transmission_but_near_allows_mismatch() -> None:
    target = listing(
        "de-auto",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
        transmission="automatic",
    )
    manual = listing(
        "es-manual",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=40_000,
        transmission="manual",
    )

    assert match_level(target, manual) == "near"


@pytest.mark.parametrize(
    ("candidate_battery", "expected_level", "expected_outcome"),
    [
        (77.0, "exact", "match"),
        (58.3, "broad", "relaxed"),
        (None, "broad", "unavailable"),
    ],
)
def test_electric_exact_and_near_require_equivalent_battery_capacity(
    candidate_battery: float | None,
    expected_level: str,
    expected_outcome: str,
) -> None:
    target = listing(
        "de-ev3",
        source="mobile_de",
        title="Kia EV3 Air Long Range",
        price=31_000,
        fuel="electric",
        power_hp=204,
        displacement_cc=0,
        battery_capacity_kwh=81.4,
    ).model_copy(update={"make": "Kia", "model": "EV3"})
    candidate = listing(
        "es-ev3",
        source="autoscout24",
        title="Kia EV3 Air Long Range",
        price=36_000,
        fuel="electric",
        power_hp=204,
        displacement_cc=0,
        battery_capacity_kwh=candidate_battery,
    ).model_copy(update={"make": "Kia", "model": "EV3"})

    decision = match_decision(target, candidate)

    assert decision.level == expected_level
    assert decision.checks["battery"].outcome == expected_outcome


def test_phev_near_requires_equivalent_battery_capacity() -> None:
    target = listing(
        "de-phev",
        source="mobile_de",
        title="BMW X5 xDrive50e",
        price=60_000,
        fuel="phev",
        power_hp=489,
        displacement_cc=2_998,
        mileage_km=40_000,
        battery_capacity_kwh=25.7,
    )
    candidate = listing(
        "es-phev",
        source="coches_net",
        title="BMW X5 xDrive50e",
        price=70_000,
        fuel="phev",
        power_hp=489,
        displacement_cc=2_998,
        mileage_km=60_000,
        battery_capacity_kwh=18.0,
    )

    assert match_level(target, candidate) == "broad"


def test_named_engine_family_conflict_is_rejected_even_from_broad() -> None:
    target = listing(
        "de-thp",
        source="mobile_de",
        title="Peugeot 5008 1.6 THP Allure",
        price=18_000,
        power_hp=165,
        displacement_cc=1_598,
        fuel="gasoline",
    ).model_copy(update={"make": "Peugeot", "model": "5008"})
    puretech = listing(
        "es-puretech",
        source="coches_net",
        title="Peugeot 5008 1.6 PureTech EAT8",
        price=23_000,
        power_hp=180,
        displacement_cc=1_598,
        fuel="gasoline",
    ).model_copy(update={"make": "Peugeot", "model": "5008"})

    assert match_level(target, puretech) is None


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
