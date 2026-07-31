from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from import_cars.fiscal_data import BoeParseError, install_boe_dataset, parse_boe_xml

FIXTURE = Path(__file__).parent / "fixtures" / "boe" / "hac_sample.xml"


def test_parses_official_annexes_without_calculating_taxes() -> None:
    dataset = parse_boe_xml(FIXTURE.read_bytes(), source_url="https://www.boe.es/example.xml")

    assert dataset.boe_id == "BOE-A-2025-26357"
    assert dataset.order_code == "HAC/1501/2025"
    assert dataset.exercise == 2026
    assert dataset.publication_date == "2025-12-23"
    assert dataset.effective_date == "2026-01-01"
    assert len(dataset.vehicle_values) == 3
    assert dataset.vehicle_values[0].brand == "ABARTH"
    assert dataset.vehicle_values[0].fiscal_hp == Decimal("10.61")
    assert dataset.vehicle_values[0].value_eur == 33_400
    assert dataset.vehicle_values[1].displacement_cc is None
    assert dataset.vehicle_values[2].category == "motorhome"
    assert [band.category for band in dataset.generic_value_bands] == [
        "electric_motorcycle",
        "combustion_motorcycle",
        "quad",
        "buggy",
    ]
    assert [band.percentage for band in dataset.depreciation_bands] == [100, 84, 100, 87]
    assert "70 por 100" in dataset.depreciation_note


def test_install_is_atomic_and_replaces_the_same_annual_version(tmp_path: Path) -> None:
    dataset = parse_boe_xml(FIXTURE.read_bytes())
    database = tmp_path / "fiscal.sqlite3"

    first = install_boe_dataset(database, dataset)
    second = install_boe_dataset(database, dataset)

    assert first.dataset_id != second.dataset_id
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM boe_dataset_versions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM boe_valores").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM boe_generic_value_bands").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM boe_depreciation").fetchone()[0] == 4
        version = connection.execute(
            "SELECT order_code, exercise, vehicle_count FROM boe_dataset_versions"
        ).fetchone()
    assert version == ("HAC/1501/2025", 2026, 3)


def test_rejects_missing_required_annex() -> None:
    malformed = FIXTURE.read_bytes().replace(b"ANEXO IV", b"APENDICE IV")

    with pytest.raises(BoeParseError, match="ANEXO IV"):
        parse_boe_xml(malformed)
