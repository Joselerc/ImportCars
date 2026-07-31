from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from import_cars.filters import PowerRange, PriceRange, UnifiedFilters, YearRange
from import_cars.matching import equivalent_vehicle_criteria, listing_matches_filters
from import_cars.models import NormalizedListing, Registration
from import_cars.webapp import CalculatorRequest, CompareRequest


def test_rejects_inverted_ranges() -> None:
    with pytest.raises(ValidationError):
        PriceRange(min_price=30_000, max_price=20_000)
    with pytest.raises(ValidationError):
        YearRange(min_year=2022, max_year=2019)


def test_rejects_conflicting_seller_filters() -> None:
    with pytest.raises(ValidationError):
        UnifiedFilters(dealer_only=True, private_only=True)


def test_missing_value_does_not_silently_pass_requested_filter() -> None:
    listing = NormalizedListing(
        listing_id="missing-year",
        source="fixture",
        url="https://example.com/missing-year",
        scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        make="BMW",
        model="X5",
    )

    assert not listing_matches_filters(
        listing,
        UnifiedFilters(year_range=YearRange(min_year=2019, max_year=2021)),
    )


def test_version_filter_requires_same_motorization() -> None:
    listing = NormalizedListing(
        listing_id="x5-40d",
        source="fixture",
        url="https://example.com/x5-40d",
        scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        title="BMW X5 xDrive40d",
        make="BMW",
        model="X5",
        first_registration=Registration(year=2020),
    )

    assert not listing_matches_filters(
        listing,
        UnifiedFilters(make="BMW", model="X5", version="xDrive30d"),
    )


def test_pair_can_use_different_prices_but_not_different_power() -> None:
    german = UnifiedFilters(
        make="BMW",
        model="X5",
        version="xDrive30d",
        price_range=PriceRange(max_price=35_000),
        power_range=PowerRange(min_power_hp=250, max_power_hp=280),
    )
    spanish = UnifiedFilters(
        make="bmw",
        model="x5",
        version="xdrive30d",
        price_range=PriceRange(max_price=50_000),
        power_range=PowerRange(min_power_hp=250, max_power_hp=280),
    )

    assert equivalent_vehicle_criteria(german, spanish)
    assert not equivalent_vehicle_criteria(
        german,
        spanish.model_copy(
            update={"power_range": PowerRange(min_power_hp=330, max_power_hp=360)}
        ),
    )


def test_web_comparison_rejects_different_vehicle_criteria() -> None:
    with pytest.raises(ValidationError):
        CompareRequest(de_make="BMW", es_make="BMW", de_model="X5", es_model="X3")

    request = CompareRequest(
        make="BMW",
        model="X5",
        de_max_price=35_000,
        es_max_price=50_000,
    )
    assert request.de_max_price != request.es_max_price


def test_web_calculator_rejects_untrusted_numeric_and_seller_values() -> None:
    with pytest.raises(ValidationError):
        CalculatorRequest(purchase_price=-1)
    with pytest.raises(ValidationError):
        CalculatorRequest(purchase_price=20_000, seller_type="<script>")
