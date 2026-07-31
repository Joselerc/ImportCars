"""Minimal local lead capture for the low-cost v1."""

from __future__ import annotations

import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ..fiscal_data import DEFAULT_DATABASE_PATH


class PublicLeadInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(None, max_length=40)
    vehicle_label: str = Field(min_length=1, max_length=240)
    final_price_eur: float = Field(gt=0, le=5_000_000)
    source_url: HttpUrl | None = None
    consent: Literal[True]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", cleaned):
            raise ValueError("Introduce un email valido")
        return cleaned

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


def save_public_lead(
    lead: PublicLeadInput,
    *,
    database_path: str | Path | None = None,
) -> None:
    """Store a consented contact request in the local SQLite v1 database."""

    path = Path(
        database_path
        or os.getenv("IMPORT_CARS_DATABASE_PATH")
        or DEFAULT_DATABASE_PATH
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS public_leads (
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
                created_at, email, phone, vehicle_label, final_price_eur, source_url
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                lead.email,
                lead.phone,
                lead.vehicle_label,
                lead.final_price_eur,
                str(lead.source_url) if lead.source_url else None,
            ),
        )


__all__ = ["PublicLeadInput", "save_public_lead"]
