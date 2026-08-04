from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from import_cars import webapp
from import_cars.enrichment import co2_memory
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
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_USERNAME", "operator")
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_PASSWORD", "secret")
    monkeypatch.setattr(webapp, "market_reference_service", MarketStub())
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        page = await client.get("/calculadora")
        assert page.status_code == 200
        assert "Cuánto te cuesta" in page.text
        assert 'id="m_body"' in page.text

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
                "cylinders": 4,
                "co2_gkm": 148,
                "mileage_km": 40_000,
                "power_kw": 125,
                "transmission": "manual",
                "seller_type": "particular",
                "autonomous_community": "Madrid",
                "municipality": "Madrid",
                "co2_confirmed": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "vehicle_label",
        "final_price_eur",
        "spanish_market_price_eur",
        "savings_eur",
        "savings_pct",
        "market_sample_size",
        "market_confidence",
        "market_cached",
        "breakdown",
        "warnings",
        "fiscal_version",
        "boe_model_match",
        "boe_confidence",
    }
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
        cylinders=6,
        power_kw=195,
        co2_original_g_km=162,
        seller=Seller(type="dealer"),
        vat_deductible=True,
        body_type="SUV / Off-road",
        transmission="automatic",
        accident_free=False,
        damage_condition="Ocasión, Vehículo accidentado",
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
    assert payload["body_type"] == "suv"
    assert payload["transmission"] == "automatic"
    assert payload["damaged"] is True
    assert payload["damage_condition"] == "Ocasión, Vehículo accidentado"
    assert payload["registration_source"] == "listing"
    assert any("dañado o accidentado" in warning for warning in payload["risk_warnings"])
    assert payload["missing_fields"] == []


@pytest.mark.asyncio
async def test_public_url_parser_guides_missing_co2_without_learning_user_value(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(co2_memory, "MEMORY_PATH", tmp_path / "co2_memory.json")
    listing = NormalizedListing(
        listing_id="missing-co2",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=missing-co2",
        scraped_at=datetime.now(UTC),
        make="Volkswagen",
        model="Golf",
        version="1.5 TSI Style",
        price_eur=20_000,
        first_registration=Registration(year=2021, month=5),
        fuel_type="Gasolina",
        engine_displacement_cc=1498,
        power_kw=110,
        seller=Seller(type="dealer"),
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=missing-co2"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert "co2_gkm" in payload["missing_fields"]
    assert "Volkswagen Golf 1.5 TSI Style 2021" in payload["co2_prompt"]
    assert "no se guardará" in payload["co2_prompt"]
    assert not co2_memory.MEMORY_PATH.exists()


@pytest.mark.asyncio
async def test_parser_keeps_damage_warning_visible_while_requesting_co2(
    monkeypatch,
) -> None:
    listing = NormalizedListing(
        listing_id="damaged-missing-co2",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=damaged-missing-co2",
        scraped_at=datetime.now(UTC),
        make="BMW",
        model="X5",
        version="xDrive30d",
        price_eur=18_900,
        first_registration=Registration(year=2017, month=4),
        fuel_type="Diésel",
        engine_displacement_cc=2_993,
        power_kw=190,
        accident_free=False,
        damage_condition="Ocasión, Vehículo accidentado",
        seller=Seller(type="dealer"),
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=damaged-missing-co2"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert "co2_gkm" in payload["missing_fields"]
    assert "CO₂" in payload["co2_prompt"]
    assert any("dañado o accidentado" in warning for warning in payload["risk_warnings"])


@pytest.mark.asyncio
async def test_parser_requests_unknown_registration_without_guessing(
    monkeypatch,
) -> None:
    listing = NormalizedListing(
        listing_id="missing-registration",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=missing-registration",
        scraped_at=datetime.now(UTC),
        make="Audi",
        model="A4",
        version="2.0 TDI",
        production_year=2026,
        price_eur=22_000,
        fuel_type="Diésel",
        engine_displacement_cc=1_968,
        power_kw=110,
        co2_original_g_km=130,
        seller=Seller(type="dealer"),
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=missing-registration"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["first_registration"] is None
    assert payload["registration_source"] is None
    assert "first_registration" in payload["missing_fields"]
    assert "Audi A4 2.0 TDI 2026" in payload["registration_prompt"]
    assert "solo en tu cálculo" in payload["registration_prompt"]


@pytest.mark.asyncio
async def test_public_parser_preserves_net_price_and_unregistered_new_status(
    monkeypatch,
) -> None:
    listing = NormalizedListing(
        listing_id="460350611",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=460350611",
        scraped_at=datetime.now(UTC),
        make="Peugeot",
        model="5008",
        version="E-5008 GT Elektromotor 210",
        price_eur=54_550,
        price_net_eur=45_840.34,
        vat_deductible=True,
        unregistered_new=True,
        fuel_type="Eléctrico",
        engine_displacement_cc=None,
        power_kw=157,
        co2_emissions_g_km=0,
        co2_original_g_km=0,
        co2_source_type="listing",
        body_type="SUV/Off-road/Pickup",
        transmission="Automático",
        seller=Seller(type="dealer"),
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=460350611"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["purchase_price"] == 54_550
    assert payload["purchase_price_net"] == 45_840.34
    assert payload["vat_deductible"] is True
    assert payload["unregistered_new"] is True
    assert payload["registration_source"] == "unregistered_new"
    assert payload["first_registration"] is None
    assert payload["seller_type"] == "profesional_iva"
    assert "first_registration" not in payload["missing_fields"]


@pytest.mark.asyncio
async def test_public_parser_treats_low_mileage_dealer_vehicle_as_new_vat(
    monkeypatch,
) -> None:
    listing = NormalizedListing(
        listing_id="new-by-mileage",
        source="mobile_de",
        url="https://www.mobile.de/details.html?id=123456789",
        scraped_at=datetime.now(UTC),
        make="Volkswagen",
        model="Golf",
        version="1.5 TSI",
        first_registration=Registration(year=2020, month=1),
        mileage_km=5_999,
        price_eur=23_800,
        fuel_type="Gasolina",
        engine_displacement_cc=1_498,
        power_kw=110,
        seller=Seller(type="dealer"),
    )
    monkeypatch.setattr(webapp, "parse_listing_url", lambda url: listing)
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/public/parse-listing",
            json={"url": "https://www.mobile.de/details.html?id=123456789"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["vat_deductible"] is False
    assert payload["seller_type"] == "profesional_iva"


@pytest.mark.asyncio
async def test_public_lead_endpoint_persists_consent(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "local.sqlite3"
    monkeypatch.setenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH", str(database))
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
