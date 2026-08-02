from pathlib import Path

import pytest

from import_cars.scrapers.mobile_de_http import MobileDeHttpScraper
from import_cars.services.listing_url_parser import (
    ListingParseError,
    _parse_autoscout_html,
    parse_listing_url,
)

FIXTURE = Path(__file__).parent / "fixtures" / "autoscout24" / "listing.html"


def test_parses_autoscout_structured_data_fixture() -> None:
    listing = _parse_autoscout_html(
        FIXTURE.read_text(encoding="utf-8"),
        "https://www.autoscout24.de/angebote/bmw-x5-test-id",
    )

    assert listing.make == "BMW"
    assert listing.model == "X5 xDrive30d"
    assert listing.price_eur == 35_900
    assert listing.first_registration.year == 2020
    assert listing.first_registration.month == 5
    assert listing.engine_displacement_cc == 2993
    assert listing.power_kw == 195
    assert listing.co2_emissions_g_km == 162
    assert listing.vat_deductible is True
    assert listing.seller.type == "dealer"


@pytest.mark.parametrize(
    "url",
    [
        "http://www.mobile.de/details.html?id=123",
        "https://example.com/?id=123",
        "https://www.mobile.de/details.html",
    ],
)
def test_rejects_unsafe_or_incomplete_urls_without_network(url: str) -> None:
    with pytest.raises(ListingParseError):
        parse_listing_url(url)


@pytest.mark.parametrize(
    ("url", "expected_id"),
    [
        (
            "https://suchen.mobile.de/fahrzeuge/details.html?id=454069619",
            "454069619",
        ),
        (
            "https://suchen.mobile.de/auto-inserat/peugeot-5008-e-5008-gt-elektromotor-210-jena-lobeda/460350611.html",
            "460350611",
        ),
    ],
)
def test_mobile_listing_id_supports_query_and_auto_inserat_paths(
    monkeypatch, url: str, expected_id: str
) -> None:
    captured = []
    sentinel = object()

    def fake_get_listing(_self, listing_id: str):
        captured.append(listing_id)
        return sentinel

    monkeypatch.setattr(MobileDeHttpScraper, "get_listing", fake_get_listing)

    assert parse_listing_url(url) is sentinel
    assert captured == [expected_id]
