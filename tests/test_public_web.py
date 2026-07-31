from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from import_cars import webapp
from import_cars.fiscal_data import install_boe_dataset, parse_boe_xml
from import_cars.models import NormalizedListing, Registration, Seller
from import_cars.services.market_reference import MarketReference

FIXTURE = Path(__file__).parent / "fixtures" / "boe" / "hac_sample.xml"


class MarketStub:
    async def get_reference(self, target):
        return MarketReference(
            match_level="exact",
            sample_size=5,
            median_eur=42_000,
            confidence="high",
            fetched_at=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_public_page_and_calculation_do_not_require_internal_auth(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_DATABASE_PATH", str(database))
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_USERNAME", "operator")
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_PASSWORD", "secret")
    monkeypatch.setattr(webapp, "market_reference_service", MarketStub())
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        page = await client.get("/calculadora")
        assert page.status_code == 200
        assert "Cuánto te cuesta" in page.text

        response = await client.post(
            "/api/public/calculate",
            json={
                "make": "Abarth",
                "model": "124",
                "version": "1.4 Spider",
                "first_registration": "2018-05-01",
                "purchase_price": 25_000,
                "fuel": "gasolina",
                "displacement_cc": 1368,
                "co2_gkm": 148,
                "mileage_km": 40_000,
                "power_kw": 125,
                "seller_type": "particular",
                "autonomous_community": "Madrid",
                "municipality": "Madrid",
                "co2_confirmed": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["boe_model_match"] == "124 1.4 Spider"
    assert payload["spanish_market_price_eur"] == 42_000
    assert "break_even" not in response.text
    assert "potential_margin" not in response.text


@pytest.mark.asyncio
async def test_public_url_parser_returns_editable_fields(monkeypatch) -> None:
    listing = NormalizedListing(
        listing_id="123",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=123",
        scraped_at=datetime.now(UTC),
        make="BMW",
        model="X5",
        version="xDrive30d",
        price_eur=35_000,
        first_registration=Registration(year=2020, month=5),
        fuel_type="diesel",
        engine_displacement_cc=2993,
        power_kw=195,
        co2_original_g_km=162,
        seller=Seller(type="dealer"),
        vat_deductible=True,
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=123"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "X5"
    assert payload["version"] == "xDrive30d"
    assert payload["seller_type"] == "profesional_iva"
    assert payload["missing_fields"] == []


@pytest.mark.asyncio
async def test_public_lead_endpoint_persists_consent(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "local.sqlite3"
    monkeypatch.setenv("IMPORT_CARS_DATABASE_PATH", str(database))
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/public/leads",
            json={
                "email": "cliente@example.com",
                "vehicle_label": "BMW X5 · 2020",
                "final_price_eur": 38_500,
                "consent": True,
            },
        )

    assert response.status_code == 200
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM public_leads").fetchone()[0] == 1
