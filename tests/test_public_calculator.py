from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from import_cars.fiscal_data import install_boe_dataset, parse_boe_xml
from import_cars.services.market_reference import MarketReference
from import_cars.services.public_calculator import (
    AuditCalculationInput,
    PublicCalculationInput,
    calculate_for_audit,
    calculate_for_customer,
)

FIXTURE = Path(__file__).parent / "fixtures" / "boe" / "hac_sample.xml"


class MarketStub:
    async def get_reference(self, target):
        assert target.make == "Abarth"
        return MarketReference(
            match_level="exact",
            sample_size=7,
            median_eur=42_000,
            average_eur=42_500,
            minimum_eur=39_000,
            maximum_eur=46_000,
            confidence="high",
            fetched_at=datetime.now(UTC),
        )


class EmptyMarketStub:
    async def get_reference(self, target):
        return None


class NoComparableMarketStub:
    async def get_reference(self, target):
        return MarketReference(
            fetched_at=datetime.now(UTC),
            quality_warning=(
                "No hay comparables suficientes dentro del nivel broad; "
                "no se estima el ahorro."
            ),
        )


@pytest.mark.asyncio
async def test_public_result_uses_engine_and_never_exposes_internal_metrics(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_customer(
        PublicCalculationInput(
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
            transmission="manual",
            body_type="deportivo_gama_alta",
            seller_type="particular",
            autonomous_community="Madrid",
            municipality="Madrid",
            co2_confirmed=True,
        ),
        market_service=MarketStub(),
    )

    payload = result.model_dump()
    serialized_keys = " ".join(payload.keys()) + " " + " ".join(
        key for row in payload["breakdown"] for key in row
    )
    assert "break_even" not in serialized_keys
    assert "margin" not in serialized_keys
    assert "margen" not in serialized_keys
    assert result.boe_model_match == "124 1.4 Spider"
    assert result.boe_confidence == "high"
    assert not any("estimado desde el precio" in warning for warning in result.warnings)
    assert result.spanish_market_price_eur == 42_000
    assert result.savings_eur == pytest.approx(42_000 - result.final_price_eur, abs=0.01)
    assert any(row["key"] == "honorarios" for row in result.breakdown)
    transport = next(row for row in result.breakdown if row["key"] == "transporte")
    assert transport["amount_eur"] == 1_200
    assert "deportivo" in transport["note"]


@pytest.mark.asyncio
async def test_public_result_marks_price_based_fallback_when_no_boe_row(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_customer(
        PublicCalculationInput(
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
            power_kw=999,
            transmission="manual",
            seller_type="particular",
            autonomous_community="Madrid",
            municipality="Madrid",
            co2_confirmed=True,
        ),
        market_service=MarketStub(),
    )

    assert result.boe_model_match is None
    assert result.boe_confidence == "none"
    assert any(warning.startswith("ATENCIÓN") for warning in result.warnings)
    assert any("estimado desde el precio" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_no_broad_comparables_hides_savings_and_keeps_final_price(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_customer(
        PublicCalculationInput(
            make="Abarth",
            model="124",
            version="1.4 Spider",
            first_registration=date(2018, 5, 1),
            purchase_price=25_000,
            fuel="gasolina",
            displacement_cc=1368,
            co2_gkm=148,
            mileage_km=40_000,
            power_kw=125,
            transmission="manual",
            seller_type="particular",
            autonomous_community="Madrid",
            municipality="Madrid",
        ),
        market_service=NoComparableMarketStub(),
    )

    assert result.final_price_eur > 0
    assert result.market_match_level is None
    assert result.spanish_market_price_eur is None
    assert result.savings_eur is None
    assert any("No hay comparables suficientes" in warning for warning in result.warnings)


def test_public_input_requires_displacement_for_combustion_vehicle() -> None:
    with pytest.raises(ValueError, match="cilindrada"):
        PublicCalculationInput(
            make="BMW",
            model="X5",
            first_registration=date(2020, 1, 1),
            purchase_price=30_000,
            fuel="diesel",
            displacement_cc=0,
            seller_type="profesional_margen",
            autonomous_community="Madrid",
            municipality="Madrid",
        )


@pytest.mark.asyncio
async def test_damaged_listing_is_calculated_and_warned(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_customer(
        PublicCalculationInput(
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
            seller_type="particular",
            autonomous_community="Madrid",
            municipality="Madrid",
            damaged=True,
            damage_condition="Ocasión, Vehículo accidentado",
        ),
        market_service=MarketStub(),
    )

    assert result.final_price_eur > 0
    assert any("dañado o accidentado" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_pure_electric_without_reported_co2_uses_zero_iedmt(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_customer(
        PublicCalculationInput(
            make="Peugeot",
            model="E-5008",
            version="GT Elektromotor 210",
            first_registration=date(2025, 1, 1),
            purchase_price=54_550,
            fuel="electrico",
            displacement_cc=0,
            power_kw=157,
            seller_type="profesional_margen",
            autonomous_community="Madrid",
            municipality="Madrid",
        ),
        market_service=EmptyMarketStub(),
    )

    iedmt = next(row for row in result.breakdown if row["key"] == "iedmt")
    assert iedmt["amount_eur"] == 0
    assert "0 g/km" in iedmt["note"]
    assert not any("CO2 no acreditado" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_public_new_vehicle_uses_advertised_net_price_and_exposes_vat_audit(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(database))

    result = await calculate_for_audit(
        AuditCalculationInput(
            make="Peugeot",
            model="5008",
            version="E-5008 GT Elektromotor 210",
            first_registration=None,
            unregistered_new=True,
            purchase_price=54_550,
            purchase_price_net=45_840.34,
            vat_deductible=True,
            fuel="electrico",
            displacement_cc=0,
            cylinders=None,
            co2_gkm=0,
            mileage_km=16,
            power_kw=157,
            body_type="suv",
            transmission="automatic",
            seller_type="profesional_iva",
            autonomous_community="Madrid",
            municipality="Madrid",
            co2_confirmed=True,
            co2_source="listing",
        ),
        market_service=EmptyMarketStub(),
    )

    iva = next(row for row in result.breakdown if row["key"] == "iva")
    assert iva["amount_eur"] == pytest.approx(45_840.34 * 0.21, abs=0.01)
    assert result.audit.vat["tax_base_eur"] == 45_840.34
    assert result.audit.vat["tax_base_source"] == "neto_anuncio"
    assert result.audit.vat["case"] == "nuevo_iva_espanol"
    assert result.audit.vat["acquisition_price_eur"] == 45_840.34
    price = next(row for row in result.breakdown if row["key"] == "precio")
    assert price["amount_eur"] == 45_840.34
    assert result.audit.registration["source"] == "unregistered_new"
