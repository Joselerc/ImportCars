from urllib.parse import parse_qs, urlparse

import pytest

from import_cars.filters import FuelType, UnifiedFilters
from import_cars.utils import build_mobile_de_search_url


@pytest.mark.parametrize(
    ("fuel_type", "expected_code"),
    [
        (FuelType.ELECTRIC, "ELECTRICITY"),
        (FuelType.HYBRID_DIESEL, "HYBRID_DIESEL"),
        (FuelType.HYBRID_GASOLINE, "HYBRID"),
        (FuelType.HYBRID, "HYBRID"),
        (FuelType.ETHANOL, "ETHANOL"),
        (FuelType.HYDROGEN, "HYDROGENIUM"),
        (FuelType.LPG, "LPG"),
        (FuelType.CNG, "CNG"),
        (FuelType.GASOLINE, "PETROL"),
        (FuelType.DIESEL, "DIESEL"),
    ],
)
def test_mobile_search_uses_current_fuel_codes(
    fuel_type: FuelType, expected_code: str
) -> None:
    query = parse_qs(
        urlparse(
            build_mobile_de_search_url(UnifiedFilters(fuel_types=[fuel_type]))
        ).query
    )

    assert query["ft"] == [expected_code]


def test_mobile_opportunity_search_always_excludes_damaged_vehicles() -> None:
    query = parse_qs(urlparse(build_mobile_de_search_url(UnifiedFilters())).query)

    assert query["dam"] == ["false"]
