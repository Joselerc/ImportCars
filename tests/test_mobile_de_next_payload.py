from pathlib import Path
from types import SimpleNamespace

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


def test_coches_net_model_catalog_resolves_bmw_x5() -> None:
    models = get_cochesnet_models_for_make("BMW")

    assert any(item["label"] == "X5" for item in models)
    assert get_cochesnet_model_id_by_name("BMW", "X5") is not None
