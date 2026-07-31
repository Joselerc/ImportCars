import sqlite3
from pathlib import Path

import pytest

from import_cars.services.leads import PublicLeadInput, save_public_lead


def test_saves_a_consented_lead_in_local_sqlite(tmp_path: Path) -> None:
    database = tmp_path / "local.sqlite3"
    save_public_lead(
        PublicLeadInput(
            email="CLIENTE@Example.com",
            phone=" 600 000 000 ",
            vehicle_label="BMW X5 · 2020",
            final_price_eur=38_500,
            source_url="https://www.mobile.de/details.html?id=123",
            consent=True,
        ),
        database_path=database,
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT email, phone, vehicle_label, status FROM public_leads"
        ).fetchone()
    assert row == ("cliente@example.com", "600 000 000", "BMW X5 · 2020", "new")


def test_rejects_lead_without_consent() -> None:
    with pytest.raises(ValueError):
        PublicLeadInput(
            email="cliente@example.com",
            vehicle_label="BMW X5",
            final_price_eur=38_500,
            consent=False,
        )
