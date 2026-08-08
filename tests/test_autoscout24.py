from __future__ import annotations

import json

import pytest

from import_cars.filters import (
    FuelType,
    MileageRange,
    PowerRange,
    UnifiedFilters,
    YearRange,
)
from import_cars.scrapers.autoscout24 import AutoScout24Scraper


def _html_with_listing() -> str:
    payload = {
        "props": {
            "pageProps": {
                "numberOfResults": 1,
                "numberOfPages": 1,
                "listings": [
                    {
                        "id": "as24-ev3",
                        "evBanner": {"type": "electric", "label": "Eléctrico"},
                        "images": ["https://images.example/ev3.jpg"],
                        "price": {"priceRaw": 30_500},
                        "url": "/anuncios/kia-ev3-as24-ev3",
                        "vehicle": {
                            "make": "Kia",
                            "model": "EV3",
                            "motorTypeName": "EV3 81,4 kWh",
                            "modelVersionInput": "Air Long Range",
                            "offerType": "U",
                            "transmission": "Automático",
                            "fuel": "Eléctrico",
                            "mileageInKm": "1.200 km",
                        },
                        "location": {
                            "countryCode": "ES",
                            "zip": "28001",
                            "city": "Madrid",
                        },
                        "seller": {
                            "id": "dealer-1",
                            "type": "Dealer",
                            "companyName": "Concesionario abierto",
                        },
                        "tracking": {
                            "firstRegistration": "04-2026",
                            "mileage": "1200",
                        },
                        "vehicleDetails": [
                            {"iconName": "speedometer", "data": "150 kW (204 CV)"}
                        ],
                    }
                ],
            }
        }
    }
    return f'<html><script id="__NEXT_DATA__">{json.dumps(payload)}</script></html>'


def test_search_url_sends_spanish_market_and_technical_filters() -> None:
    scraper = AutoScout24Scraper()
    filters = UnifiedFilters(
        make="Kia",
        model="EV3",
        fuel_types=[FuelType.ELECTRIC],
        year_range=YearRange(min_year=2024, max_year=2026),
        mileage_range=MileageRange(min_mileage=0, max_mileage=60_000),
        power_range=PowerRange(min_power_hp=144, max_power_hp=264),
    )

    url = scraper._build_search_url(filters, 2)

    assert "/lst/kia/ev3/ft_el%C3%A9ctrico?" in url
    assert "cy=E" in url
    assert "damaged_listing=exclude" in url
    assert "fregfrom=2024" in url and "fregto=2026" in url
    assert "kmfrom=0" in url and "kmto=60000" in url
    assert "powerfrom=105" in url and "powerto=195" in url
    assert "page=2" in url


@pytest.mark.asyncio
async def test_structured_next_payload_becomes_normalized_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scraper = AutoScout24Scraper()

    async def fetch_page(_url: str) -> str:
        return _html_with_listing()

    monkeypatch.setattr(scraper, "_fetch_page", fetch_page)
    result = await scraper.search(
        UnifiedFilters(
            make="Kia",
            model="EV3",
            fuel_types=[FuelType.ELECTRIC],
            year_range=YearRange(min_year=2024, max_year=2026),
            mileage_range=MileageRange(max_mileage=60_000),
        ),
        limit=50,
    )

    assert result.total_listings == 1
    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.source == "autoscout24"
    assert listing.listing_id == "as24-ev3"
    assert listing.version == "Air Long Range"
    assert listing.price_eur == 30_500
    assert listing.mileage_km == 1_200
    assert listing.first_registration.year == 2026
    assert listing.first_registration.month == 4
    assert listing.fuel_type == "Eléctrico"
    assert listing.transmission == "Automático"
    assert listing.power_kw == 150
    assert listing.power_hp == 204
    assert listing.engine_displacement_cc is None
    assert listing.battery_capacity_kwh == 81.4
    assert listing.seller.name == "Concesionario abierto"


def test_hybrid_litre_displacement_is_derived_but_battery_size_is_not() -> None:
    scraper = AutoScout24Scraper()
    hybrid = scraper._to_listing(
        {
            "id": "hybrid",
            "evBanner": {"type": "hybrid"},
            "price": {"priceRaw": 20_000},
            "url": "/anuncios/hybrid",
            "vehicle": {
                "make": "Ford",
                "model": "Focus",
                "motorTypeName": "1.0 EcoBoost",
                "modelVersionInput": "1.0 EcoBoost MHEV ST-Line",
                "fuel": "Electro/Gasolina",
            },
        }
    )
    electric = scraper._to_listing(
        {
            "id": "electric",
            "evBanner": {"type": "electric"},
            "price": {"priceRaw": 30_000},
            "url": "/anuncios/electric",
            "vehicle": {
                "make": "Kia",
                "model": "EV3",
                "motorTypeName": "EV3 58,3 kWh",
                "fuel": "Eléctrico",
            },
        }
    )

    assert hybrid.engine_displacement_cc == 1_000
    assert hybrid.battery_capacity_kwh is None
    assert hybrid.fuel_type == "Híbrido"
    assert electric.engine_displacement_cc is None
    assert electric.battery_capacity_kwh == 58.3
