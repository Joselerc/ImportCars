from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from import_cars import webapp
from import_cars.fiscal_data import install_boe_dataset, parse_boe_xml
from import_cars.scrapers.coches_net import CochesNetScraper
from import_cars.services.market_reference import (
    ComparableCheckAudit,
    MarketComparableAudit,
    MarketReference,
    MatchCriterionAudit,
)
from import_cars.services.public_calculator import (
    PublicCalculationInput,
    calculate_for_audit,
)

FIXTURE = Path(__file__).parent / "fixtures" / "boe" / "hac_sample.xml"


def test_coches_net_transmission_is_observable_without_feeding_matching() -> None:
    listing = CochesNetScraper()._to_listing(
        {
            "id": "70788338",
            "title": "FIAT 500 1.2 8v Mirror",
            "url": "/fiat-500-70788338.aspx",
            "price": {"amount": 9_990},
            "make": "FIAT",
            "model": "500",
            "year": 2018,
            "km": 115_000,
            "fuelType": "Gasolina",
            "cubicCapacity": 1242,
            "hp": 69,
            "transmissionTypeId": 2,
        }
    )

    assert listing is not None
    assert listing.version == "1.2 8v Mirror"
    assert listing.transmission is None
    assert listing.metadata.source_transmission == "manual"


def market_reference() -> MarketReference:
    return MarketReference(
        match_level="exact",
        sample_size=1,
        average_eur=39_900,
        median_eur=39_900,
        minimum_eur=39_900,
        maximum_eur=39_900,
        confidence="high",
        fetched_at=datetime.now(UTC),
        criteria=[
            MatchCriterionAudit(
                key="mileage",
                label="Kilómetros",
                target_value=40_000,
                status="not_used",
                rule="La política vigente no filtra por kilómetros.",
            )
        ],
        comparables=[
            MarketComparableAudit(
                listing_id="es-1",
                title="ABARTH 124 1.4 Spider",
                url="https://www.coches.net/abarth-124-es-1.aspx",
                price_eur=39_900,
                mileage_km=52_000,
                year=2018,
                version="1.4 Spider",
                fuel="Gasolina",
                transmission="manual",
                power_hp=170,
                displacement_cc=1368,
                match_level="exact",
                checks=[
                    ComparableCheckAudit(
                        key="mileage",
                        label="Kilómetros",
                        target_value=40_000,
                        comparable_value=52_000,
                        status="not_used",
                        note="Dato visible, no usado por la política actual.",
                    )
                ],
            )
        ],
    )


class MarketStub:
    async def get_reference(self, target):
        return market_reference()


def calculation_input() -> PublicCalculationInput:
    return PublicCalculationInput(
        make="Abarth",
        model="124",
        version="1.4 Spider",
        first_registration=date(2018, 5, 1),
        purchase_price=25_000,
        fuel="gasolina",
        displacement_cc=1368,
        cylinders=4,
        co2_gkm=148,
        mileage_km=40_000,
        power_kw=125,
        body_type="deportivo_gama_alta",
        transmission="manual",
        seller_type="particular",
        autonomous_community="Madrid",
        municipality="Madrid",
        co2_confirmed=True,
    )


@pytest.mark.asyncio
async def test_audit_result_exposes_real_fiscal_trace_and_frozen_comparables(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_audit(
        calculation_input(),
        market_service=MarketStub(),
    )

    assert result.audit.market["sample_size"] == 1
    assert result.audit.market["minimum_eur"] == 39_900
    assert result.audit.market["maximum_eur"] == 39_900
    assert result.audit.market["comparables"][0]["mileage_km"] == 52_000
    assert result.audit.market["comparables"][0]["transmission"] == "manual"
    assert result.audit.boe["technical_candidate_count"] == 1
    assert result.audit.boe["candidates"][0]["selected"] is True
    assert "pocos comparables" in result.audit.market["quality_warning"]

    fiscal = {line.key: line for line in result.audit.fiscal_breakdown}
    iedmt = {item["key"]: item for item in fiscal["iedmt"].intermediates}
    assert fiscal["iedmt"].formula
    assert iedmt["boe_fila_id"]["value"] is not None
    assert iedmt["valor_tablas_nuevo"]["value"] == 33_400
    assert iedmt["coeficiente_depreciacion"]["value"] > 0
    assert iedmt["iva_historico"]["value"] == 21
    assert iedmt["base_iedmt"]["value"] > 0
    assert iedmt["tipo_iedmt_aplicado"]["value"] == pytest.approx(4.75)

    itp = {item["key"]: item for item in fiscal["itp"].intermediates}
    assert itp["base_itp"]["value"] == 25_000
    ivtm = {item["key"]: item for item in fiscal["ivtm"].intermediates}
    assert ivtm["cvf"]["note"] == "Aportada por la ficha o la fila del BOE"
    assert ivtm["trimestres_restantes"]["value"] in {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_audit_surface_is_protected_and_public_contract_stays_clean(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_USERNAME", "operator")
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_PASSWORD", "secret")
    monkeypatch.setattr(webapp, "market_reference_service", MarketStub())
    transport = httpx.ASGITransport(app=webapp.app)

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        assert (await client.get("/calculadora")).status_code == 200
        assert (await client.get("/calculadora/auditoria")).status_code == 401
        assert (
            await client.post(
                "/api/internal/calculate-audit",
                json=calculation_input().model_dump(mode="json"),
            )
        ).status_code == 401

        public = await client.post(
            "/api/public/calculate",
            json=calculation_input().model_dump(mode="json"),
        )
        audit_page = await client.get(
            "/calculadora/auditoria", auth=("operator", "secret")
        )
        audit = await client.post(
            "/api/internal/calculate-audit",
            auth=("operator", "secret"),
            json=calculation_input().model_dump(mode="json"),
        )

    assert public.status_code == 200
    assert "audit" not in public.json()
    assert "comparables" not in public.text
    assert audit_page.status_code == 200
    assert "Modo auditoría interno" in audit_page.text
    assert 'id="m_transmission"' in audit_page.text
    assert audit.status_code == 200
    assert audit.json()["audit"]["market"]["comparables"][0]["listing_id"] == "es-1"
