from import_cars.enrichment.battery import extract_battery_capacity_kwh
from import_cars.scrapers.coches_net import CochesNetScraper


def test_battery_capacity_prefers_structured_numeric_field() -> None:
    payload = {
        "vehicle": {"motorTypeName": "EV3 58,3 kWh"},
        "batteryCapacity": "81.4",
    }

    assert extract_battery_capacity_kwh(payload) == 81.4


def test_battery_capacity_is_extracted_from_nested_marketplace_text() -> None:
    payload = {"vehicle": {"motorTypeName": "Proace Electric 75 kWh Long"}}

    assert extract_battery_capacity_kwh(payload) == 75.0


def test_coches_net_listing_maps_declared_battery_capacity() -> None:
    listing = CochesNetScraper()._to_listing(
        {
            "id": "ev3-es",
            "url": "/coches-segunda-mano/kia-ev3-81-4-kwh.htm",
            "title": "Kia EV3 Earth Long Range 81,4 kWh",
            "make": "Kia",
            "model": "EV3",
            "year": 2025,
            "price": {"amount": 37_900},
            "km": 8_000,
            "hp": 204,
            "fuelType": "Eléctrico",
        }
    )

    assert listing is not None
    assert listing.battery_capacity_kwh == 81.4
