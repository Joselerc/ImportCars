from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from import_cars.fiscal_data import install_boe_dataset, parse_boe_xml
from import_cars.services.market_reference import MarketReference
from import_cars.services.public_calculator import (
    PublicCalculationInput,
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
