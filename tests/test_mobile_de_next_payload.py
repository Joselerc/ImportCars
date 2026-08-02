import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from import_cars.data import (
    get_cochesnet_model_id_by_name,
    get_cochesnet_models_for_make,
)
from import_cars.filters import UnifiedFilters
from import_cars.scrapers.mobile_de_http import MobileDeHttpScraper

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "mobile_de"
    / "search_results_next_payload.html"
)


def test_extracts_and_normalizes_next_search_results_fixture() -> None:
    scraper = MobileDeHttpScraper()
    payload = scraper._extract_next_search_results(FIXTURE.read_text(encoding="utf-8"))
    listings = scraper._extract_summary_listings(payload)

    assert payload["numResultsTotal"] == 2
    assert [item.listing_id for item in listings] == ["123456789", "987654321"]

    x5 = listings[0]
    assert x5.make == "BMW"
    assert x5.model == "X5"
    assert x5.title == "BMW X5 xDrive30d"
    assert x5.price_eur == 31_900
    assert x5.price_net_eur == 26_806.72
    assert x5.vat_deductible is True
    assert x5.mileage_km == 82_500
    assert x5.first_registration.year == 2020
    assert x5.first_registration.month == 3
    assert x5.power_kw == 195
    assert x5.power_hp == 265
    assert x5.engine_displacement_cc == 2_993
    assert x5.seller.type == "dealer"


def test_search_uses_summary_payload_without_detail_n_plus_one(monkeypatch) -> None:
    scraper = MobileDeHttpScraper()
    html = FIXTURE.read_text(encoding="utf-8")

    monkeypatch.setattr(scraper, "_get", lambda _url: SimpleNamespace(text=html))

    def details_must_not_be_called(*_args, **_kwargs):
        raise AssertionError(
            "No debe consultar fichas cuando el payload contiene los anuncios"
        )

    monkeypatch.setattr(scraper, "_fetch_details_parallel", details_must_not_be_called)

    result = scraper.search(UnifiedFilters(make="BMW"), limit=1)

    assert [item.listing_id for item in result.listings] == ["123456789"]
    assert result.total_listings == 2


def test_extracts_current_next_detail_payload() -> None:
    listing = {
        "id": 456794709,
        "title": "BMW X5 xDrive30d",
        "shortTitle": "BMW X5",
        "subTitle": "xDrive30d M SPORT/LEDER",
        "make": {"localized": "BMW"},
        "model": {"localized": "X5"},
        "price": {
            "grs": {"amount": 61900, "currency": "EUR"},
            "nt": {"amount": 52016.81, "currency": "EUR"},
            "vat": 19,
        },
        "contact": {"enumType": "DEALER", "name": "Autohaus"},
        "attributes": [
            {"tag": "trimLine", "value": "xDrive30d"},
            {"tag": "cylinder", "value": "6"},
            {"tag": "mileage", "value": "89.000 km"},
            {"tag": "cubicCapacity", "value": "2.993 ccm"},
            {"tag": "power", "value": "210 kW (286 cv)"},
            {"tag": "fuel", "value": "Diesel"},
            {"tag": "firstRegistration", "value": "10/2020"},
            {"tag": "co2Emissions", "value": "162 g/km"},
            {"tag": "damageCondition", "value": "Ocasión, Vehículo accidentado"},
        ],
    }
    decoded = f'1e:[["$","component",null,{{"listing":{json.dumps(listing)}}}]]'
    html = f"<script>self.__next_f.push([1,{json.dumps(decoded)}])</script>"

    result = MobileDeHttpScraper()._extract_next_detail_listing(
        html,
        "456794709",
        "https://www.mobile.de/details.html?id=456794709",
    )

    assert result is not None
    assert result.make == "BMW"
    assert result.model == "X5"
    assert result.version == "xDrive30d M SPORT/LEDER"
    assert result.metadata.source_trim_line == "xDrive30d"
    assert result.cylinders == 6
    assert result.price_eur == 61_900
    assert result.price_net_eur == 52_016.81
    assert result.vat_deductible is True
    assert result.first_registration.month == 10
    assert result.engine_displacement_cc == 2_993
    assert result.power_kw == 210
    assert result.co2_original_g_km == 162
    assert result.accident_free is False
    assert result.damage_condition == "Ocasión, Vehículo accidentado"


def test_coches_net_model_catalog_resolves_bmw_x5() -> None:
    models = get_cochesnet_models_for_make("BMW")

    assert any(item["label"] == "X5" for item in models)
    assert get_cochesnet_model_id_by_name("BMW", "X5") is not None


def _electric_detail_html(listing_id: str, attributes: list[dict]) -> str:
    listing = {
        "id": int(listing_id),
        "title": "Peugeot 5008 E-5008 GT Elektromotor 210",
        "subTitle": "E-5008 GT Elektromotor 210",
        "make": {"localized": "Peugeot"},
        "model": {"localized": "5008"},
        "price": {"grs": {"amount": 54550, "currency": "EUR"}},
        "attributes": attributes,
    }
    decoded = f'1e:[["$","component",null,{{"listing":{json.dumps(listing)}}}]]'
    return f"<script>self.__next_f.push([1,{json.dumps(decoded)}])</script>"


@pytest.mark.parametrize(
    "electric_attributes",
    [
        [
            {"tag": "envkv.engineType", "value": "Motor eléctrico"},
            {"tag": "envkv.otherEnergySource", "value": "Electricidad"},
            {"tag": "battery", "value": "Batería comprada"},
            {"tag": "batteryCapacity", "value": "73 kWh"},
        ],
        [{"tag": "envkv.engineType", "value": "Elektromotor"}],
        [{"tag": "batteryCapacity", "value": "55 kWh"}],
    ],
)
def test_electric_detail_is_detected_without_standard_fuel(
    electric_attributes: list[dict],
) -> None:
    result = MobileDeHttpScraper()._extract_next_detail_listing(
        _electric_detail_html("460350611", electric_attributes),
        "460350611",
        "https://www.mobile.de/details.html?id=460350611",
    )

    assert result is not None
    assert result.fuel_type == "Eléctrico"


def test_electric_metadata_is_preserved_from_json() -> None:
    result = MobileDeHttpScraper()._extract_next_detail_listing(
        _electric_detail_html(
            "460350611",
            [
                {"tag": "envkv.engineType", "value": "Motor eléctrico"},
                {"tag": "envkv.otherEnergySource", "value": "Electricidad"},
                {"tag": "battery", "value": "Batería comprada"},
                {"tag": "batteryCapacity", "value": "73,5 kWh"},
            ],
        ),
        "460350611",
        "https://www.mobile.de/details.html?id=460350611",
    )

    assert result is not None
    assert result.engine_type == "Motor eléctrico"
    assert result.energy_source == "Electricidad"
    assert result.battery_info == "Batería comprada"
    assert result.battery_capacity_kwh == 73.5


def test_unregistered_new_condition_is_preserved_from_json() -> None:
    result = MobileDeHttpScraper()._extract_next_detail_listing(
        _electric_detail_html(
            "460350611",
            [
                {"tag": "damageCondition", "value": "Nuevo, Sin accidentes"},
                {"tag": "envkv.engineType", "value": "Motor eléctrico"},
            ],
        ),
        "460350611",
        "https://www.mobile.de/details.html?id=460350611",
    )

    assert result is not None
    assert result.first_registration is None
    assert result.unregistered_new is True
