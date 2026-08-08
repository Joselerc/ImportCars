from __future__ import annotations

import sqlite3
from pathlib import Path

from import_cars.fiscal_data import resolver_diagnostico_valor_tablas


def _peugeot_database(path: Path) -> Path:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE boe_dataset_versions (
                id INTEGER PRIMARY KEY,
                exercise INTEGER NOT NULL,
                order_code TEXT NOT NULL
            );
            CREATE TABLE boe_valores (
                id INTEGER PRIMARY KEY,
                dataset_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                brand TEXT NOT NULL,
                model_type TEXT NOT NULL,
                commercial_start INTEGER,
                commercial_end INTEGER,
                displacement_cc INTEGER,
                cylinders INTEGER,
                fuel_code TEXT NOT NULL,
                power_kw INTEGER,
                fiscal_hp NUMERIC,
                power_cv INTEGER NOT NULL,
                value_eur INTEGER NOT NULL
            );
            INSERT INTO boe_dataset_versions VALUES (1, 2026, 'HAC/1501/2025');
            """
        )
        exact = [
            (41648, "5008 1.6 THP S&S Allure Aut.", 2017, 2018, 24_300),
            (41647, "5008 1.6 THP S&S Allure 7 pl. EAT6", 2013, 2017, 24_700),
            (41650, "5008 1.6 THP S&S GT Line Aut.", 2017, 2018, 26_100),
            (41641, "5008 1.6 Pure Tech S&S GT -Line EAT6", 2017, 2018, 27_600),
        ]
        connection.executemany(
            """
            INSERT INTO boe_valores VALUES (
                ?, 1, 'passenger_vehicle', 'PEUGEOT', ?, ?, ?,
                1598, 4, 'G', 121, 11.64, 165, ?
            )
            """,
            exact,
        )
        other = [
            (
                50_000 + index,
                f"5008 variante técnica {index}",
                2013,
                2020,
                1560,
                4,
                "D",
                80 + index,
                11.48,
                100 + index,
                18_000 + index * 100,
            )
            for index in range(49)
        ]
        connection.executemany(
            """
            INSERT INTO boe_valores VALUES (
                ?, 1, 'passenger_vehicle', 'PEUGEOT', ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            """,
            other,
        )
        connection.executemany(
            """
            INSERT INTO boe_valores VALUES (
                ?, 1, 'passenger_vehicle', 'PEUGEOT', ?, 2024, NULL,
                NULL, NULL, 'Elc', 157, 20.2, 210, ?
            )
            """,
            [
                (42091, "E-5008 Allure Eléctrico", 37_200),
                (42093, "E-5008 GT Eléctrico", 41_100),
            ],
        )
    return path


def _resolve(database: Path, **overrides):
    inputs = {
        "marca": "Peugeot",
        "modelo": "5008 1.6 THP Allure GT-LINE/PANO/7-SITZER",
        "fecha": 2017,
        "displacement_cc": 1598,
        "power_kw": 121,
        "fuel_code": "Gasolina",
        "cylinders": 4,
        "transmission": "Automático",
        "database_path": database,
    }
    inputs.update(overrides)
    return resolver_diagnostico_valor_tablas(**inputs)


def test_peugeot_hard_filter_reduces_53_rows_to_four(tmp_path: Path) -> None:
    audit = _resolve(_peugeot_database(tmp_path / "fiscal.sqlite3"))

    assert audit.base_candidate_count == 53
    assert audit.technical_candidate_count == 4
    assert audit.transmission_candidate_count == 4
    assert {candidate.row_id for candidate in audit.candidates} == {
        41641,
        41647,
        41648,
        41650,
    }
    assert audit.resolution is not None
    assert audit.resolution.row_id == 41650
    assert audit.confidence_label == "non_conclusive"
    assert audit.price_spread_pct == 13.58


def test_manual_override_selects_an_exact_candidate(tmp_path: Path) -> None:
    audit = _resolve(
        _peugeot_database(tmp_path / "fiscal.sqlite3"),
        selected_row_id=41647,
    )

    assert audit.resolution is not None
    assert audit.resolution.row_id == 41647
    assert audit.resolution.manually_selected is True
    assert audit.confidence_label == "manual"
    selected = next(candidate for candidate in audit.candidates if candidate.selected)
    assert "manualmente" in selected.decision


def test_no_technical_candidate_returns_none_and_explicit_warning(tmp_path: Path) -> None:
    audit = _resolve(
        _peugeot_database(tmp_path / "fiscal.sqlite3"),
        power_kw=999,
    )

    assert audit.base_candidate_count == 53
    assert audit.technical_candidate_count == 0
    assert audit.resolution is None
    assert audit.confidence_label == "none"
    assert "Ninguna fila" in audit.warning


def test_power_filter_accepts_two_kw_but_rejects_three_kw(
    tmp_path: Path,
) -> None:
    database = _peugeot_database(tmp_path / "fiscal.sqlite3")

    within_tolerance = _resolve(database, power_kw=119)
    outside_tolerance = _resolve(database, power_kw=118)

    assert within_tolerance.technical_candidate_count == 4
    assert within_tolerance.resolution is not None
    assert outside_tolerance.technical_candidate_count == 0
    assert outside_tolerance.resolution is None


def test_plain_gasoline_etsi_query_matches_official_gye_row(tmp_path: Path) -> None:
    database = _peugeot_database(tmp_path / "fiscal.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO boe_valores VALUES (
                42097, 1, 'passenger_vehicle', 'PEUGEOT',
                '5008 1.5 eTSI DSG', 2024, NULL,
                1498, 4, 'GyE', 110, 12.1, 150, 40500
            )
            """
        )

    audit = resolver_diagnostico_valor_tablas(
        "Peugeot",
        "5008 1.5 eTSI DSG",
        2025,
        displacement_cc=1498,
        power_kw=110,
        fuel_code="Gasolina",
        cylinders=4,
        transmission="Automático",
        database_path=database,
    )

    assert audit.technical_candidate_count == 1
    assert audit.resolution is not None
    assert audit.resolution.row_id == 42097


def test_missing_cylinders_never_blocks_an_exact_technical_match(tmp_path: Path) -> None:
    audit = _resolve(
        _peugeot_database(tmp_path / "fiscal.sqlite3"),
        cylinders=None,
    )

    assert audit.technical_candidate_count == 4
    assert audit.resolution is not None
    assert "cylinders" not in audit.missing_technical_fields


def test_cylinders_are_only_an_optional_preference(tmp_path: Path) -> None:
    audit = _resolve(
        _peugeot_database(tmp_path / "fiscal.sqlite3"),
        cylinders=3,
    )

    assert audit.technical_candidate_count == 4
    assert audit.resolution is not None


def test_electric_model_resolves_without_displacement_or_cylinders(
    tmp_path: Path,
) -> None:
    audit = resolver_diagnostico_valor_tablas(
        "Peugeot",
        "5008 E-5008 GT Elektromotor 210",
        2025,
        displacement_cc=0,
        power_kw=157,
        fuel_code="Elc",
        cylinders=None,
        transmission="Automático",
        database_path=_peugeot_database(tmp_path / "fiscal.sqlite3"),
    )

    assert audit.technical_candidate_count == 2
    assert audit.resolution is not None
    assert audit.resolution.row_id == 42093
    assert audit.resolution.value_eur == 41_100


def test_hybrid_fuel_family_matches_official_gasoline_electric_code(
    tmp_path: Path,
) -> None:
    database = _peugeot_database(tmp_path / "fiscal.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO boe_valores VALUES (
                42095, 1, 'passenger_vehicle', 'PEUGEOT',
                '5008 Hybrid 180 e-EAT8', 2024, NULL,
                1598, 4, 'GyE', 110, 12.1, 180, 40100
            )
            """
        )

    audit = resolver_diagnostico_valor_tablas(
        "Peugeot",
        "5008 Hybrid 180 e-EAT8",
        2025,
        displacement_cc=1598,
        power_kw=110,
        fuel_code="Hybrid",
        cylinders=4,
        transmission="Automático",
        database_path=database,
    )

    assert audit.technical_candidate_count == 1
    assert audit.resolution is not None
    assert audit.resolution.row_id == 42095


def test_plug_in_hybrid_matches_official_phev_code(tmp_path: Path) -> None:
    database = _peugeot_database(tmp_path / "fiscal.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO boe_valores VALUES (
                42096, 1, 'passenger_vehicle', 'PEUGEOT',
                '5008 Hybrid PHEV 225 e-EAT8', 2024, NULL,
                1598, 4, 'PHEV', 133, 12.1, 225, 44500
            )
            """
        )

    audit = resolver_diagnostico_valor_tablas(
        "Peugeot",
        "5008 Hybrid PHEV 225 e-EAT8",
        2025,
        displacement_cc=1598,
        power_kw=133,
        fuel_code="PHEV",
        cylinders=4,
        transmission="Automático",
        database_path=database,
    )

    assert audit.technical_candidate_count == 1
    assert audit.resolution is not None
    assert audit.resolution.row_id == 42096
