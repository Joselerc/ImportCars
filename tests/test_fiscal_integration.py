from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from import_cars.fiscal_data import install_boe_dataset, parse_boe_xml
from import_cars.models import NormalizedListing, Registration
from import_cars.services.fiscal import break_even_scenarios, vehicle_from_listing

FIXTURE = Path(__file__).parent / "fixtures" / "boe" / "hac_sample.xml"


def _listing() -> NormalizedListing:
    return NormalizedListing(
        listing_id="de-abarth",
        source="mobile_de",
        url="https://suchen.mobile.de/fahrzeuge/details.html?id=123",
        scraped_at=datetime.now(UTC),
        make="Abarth",
        model="124",
        version="1.4 Spider",
        price_eur=25_000,
        mileage_km=40_000,
        first_registration=Registration(year=2018, month=5),
        fuel_type="gasoline",
        power_kw=125,
        engine_displacement_cc=1368,
        co2_original_g_km=148,
        co2_confidence=1.0,
    )


def test_listing_adapter_resolves_the_official_boe_value(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_DATABASE_PATH", str(database))

    vehicle = vehicle_from_listing(_listing())

    assert vehicle.valor_tablas_nuevo == 33_400
    assert vehicle.cvf == 10.61
    assert vehicle.fecha_primera_matriculacion.isoformat() == "2018-05-01"


def test_internal_scenarios_use_fiscal_engine_without_client_fees(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "fiscal.sqlite3"
    install_boe_dataset(database, parse_boe_xml(FIXTURE.read_bytes()))
    monkeypatch.setenv("IMPORT_CARS_DATABASE_PATH", str(database))

    scenarios = break_even_scenarios(_listing())

    assert set(scenarios) == {"particular", "empresa_iva", "empresa_margen"}
    assert scenarios["particular"] > scenarios["empresa_iva"]
    assert scenarios["empresa_iva"] == scenarios["empresa_margen"]


def test_internal_scenarios_skip_listings_without_mandatory_fiscal_data() -> None:
    listing = _listing().model_copy(
        update={"first_registration": None, "production_year": None}
    )

    assert break_even_scenarios(listing) == {}
