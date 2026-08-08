"""Minimal local lead capture for the low-cost v1."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from ..persistence import customer_database_path
from ..persistence.customer_activity import (
    CONSENT_TEXT,
    calculation_belongs_to_visitor,
    initialize_customer_database,
)


class PublicLeadInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    phone: str | None = Field(None, max_length=40)
    vehicle_label: str = Field(min_length=1, max_length=240)
    final_price_eur: float = Field(gt=0, le=5_000_000)
    source_url: HttpUrl | None = None
    calculation_id: str | None = Field(None, max_length=64)
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
    anonymous_id: str | None = None,
    database_path: str | Path | None = None,
) -> None:
    """Store explicit consent and link only calculations owned by this visitor."""

    path = Path(database_path) if database_path is not None else customer_database_path()
    initialize_customer_database(path)
    linked_calculation = None
    if (
        lead.calculation_id
        and anonymous_id
        and calculation_belongs_to_visitor(
            lead.calculation_id, anonymous_id, database_path=path
        )
    ):
        linked_calculation = lead.calculation_id
    import sqlite3

    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            INSERT INTO public_leads (
                created_at, email, phone, vehicle_label, final_price_eur, source_url,
                calculation_id, anonymous_id, consent_given, consent_text, consent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                now,
                lead.email,
                lead.phone,
                lead.vehicle_label,
                lead.final_price_eur,
                str(lead.source_url) if lead.source_url else None,
                linked_calculation,
                anonymous_id if linked_calculation else None,
                CONSENT_TEXT,
                now,
            ),
        )


__all__ = ["PublicLeadInput", "save_public_lead"]
