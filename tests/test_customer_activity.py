from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from import_cars.persistence.customer_activity import (
    calculation_detail,
    erase_personal_data,
    record_calculation,
)
from import_cars.services.leads import PublicLeadInput, save_public_lead


def _record(database: Path, *, simulated: bool = False) -> tuple[str, str]:
    visitor = "anonymous-visitor-with-enough-entropy"
    calculation_id = record_calculation(
        anonymous_id=visitor,
        request_data={
            "make": "BMW",
            "model": "320d",
            "version": "M Sport",
            "first_registration": "2021-05-01",
            "purchase_price": 25_000,
            "autonomous_community": "Madrid",
            "municipality": "Madrid",
        },
        public_result={
            "vehicle_label": "BMW 320d M Sport · 2021",
            "final_price_eur": 29_800,
            "spanish_market_price_eur": 34_000,
            "savings_eur": 4_200,
            "savings_pct": 12.35,
            "market_match_level": "exact",
            "market_sample_size": 1,
            "warnings": [],
            "fiscal_version": "Orden HAC/1501/2025",
        },
        audit={
            "market": {
                "comparables": [
                    {
                        "source": "coches_net",
                        "listing_id": "es-1",
                        "price_eur": 34_000,
                        "used_for_price": True,
                    }
                ],
                "savings_sanity_filter": {"applied": False},
            },
            "boe": {"selected_row_id": 55, "co2_source": "listing"},
            "vat": {"case": "usado_particular", "spanish_vat_eur": 0},
            "registration": {"source": "listing"},
            "fiscal_breakdown": [
                {"key": "iedmt", "formula": "base × tipo", "intermediates": []}
            ],
        },
        source_url="https://www.mobile.de/details.html?id=1",
        simulated=simulated,
        database_path=database,
    )
    return calculation_id, visitor


def test_records_immutable_fiscal_and_market_snapshots_without_ip(tmp_path: Path) -> None:
    database = tmp_path / "activity.sqlite3"
    calculation_id, _visitor = _record(database)

    detail = calculation_detail(calculation_id, database_path=database)
    assert detail is not None
    assert detail["market_snapshot"]["comparables"][0]["listing_id"] == "es-1"
    assert detail["fiscal_snapshot"]["fiscal_breakdown"][0]["formula"] == "base × tipo"
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(customer_calculations)")
        }
        stored = connection.execute(
            "SELECT market_snapshot_json FROM customer_calculations WHERE id = ?",
            (calculation_id,),
        ).fetchone()[0]
    assert "ip" not in columns and "ip_address" not in columns
    assert json.loads(stored)["comparables"][0]["price_eur"] == 34_000


def test_erasure_removes_pii_and_unlinks_lead_but_keeps_calculation(tmp_path: Path) -> None:
    database = tmp_path / "activity.sqlite3"
    calculation_id, visitor = _record(database)
    save_public_lead(
        PublicLeadInput(
            email="cliente@example.com",
            phone="600000000",
            vehicle_label="BMW 320d M Sport · 2021",
            final_price_eur=29_800,
            calculation_id=calculation_id,
            consent=True,
        ),
        anonymous_id=visitor,
        database_path=database,
    )

    assert erase_personal_data("CLIENTE@example.com", database_path=database) == 1
    with sqlite3.connect(database) as connection:
        lead = connection.execute(
            "SELECT email, phone, calculation_id, anonymous_id, status FROM public_leads"
        ).fetchone()
        calculation_count = connection.execute(
            "SELECT COUNT(*) FROM customer_calculations"
        ).fetchone()[0]
    assert lead == (None, None, None, None, "erased")
    assert calculation_count == 1


def test_lead_cannot_link_another_visitors_calculation(tmp_path: Path) -> None:
    database = tmp_path / "activity.sqlite3"
    calculation_id, _visitor = _record(database)
    save_public_lead(
        PublicLeadInput(
            email="cliente@example.com",
            vehicle_label="BMW 320d",
            final_price_eur=29_800,
            calculation_id=calculation_id,
            consent=True,
        ),
        anonymous_id="different-visitor-identifier-value",
        database_path=database,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT calculation_id, anonymous_id FROM public_leads"
        ).fetchone() == (None, None)


def test_legacy_lead_table_is_upgraded_and_can_be_erased(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE public_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                vehicle_label TEXT NOT NULL,
                final_price_eur NUMERIC NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'new'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO public_leads (
                created_at, email, phone, vehicle_label, final_price_eur
            ) VALUES ('2026-01-01', 'legacy@example.com', '600000000', 'Audi A4', 25000)
            """
        )

    assert erase_personal_data("legacy@example.com", database_path=database) == 1
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT email, phone, status, personal_data_erased_at FROM public_leads"
        ).fetchone()
    assert row[0] == ""
    assert row[1] is None
    assert row[2] == "erased"
    assert row[3]
