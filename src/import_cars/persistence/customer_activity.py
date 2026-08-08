"""Customer activity persistence, isolated from fiscal and market databases."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .migrations import Migration, apply_migrations
from .paths import customer_database_path

COMPONENT = "customer_activity"
CONSENT_TEXT = (
    "Acepto que uséis estos datos para responder a mi solicitud de presupuesto."
)

MIGRATIONS = (
    Migration(
        component=COMPONENT,
        version=1,
        name="c1_activity_and_admin",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS customer_calculations (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                anonymous_id TEXT NOT NULL,
                source_mode TEXT NOT NULL,
                source_url TEXT,
                vehicle_label TEXT NOT NULL,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                version TEXT,
                first_registration TEXT,
                purchase_price_eur NUMERIC NOT NULL,
                autonomous_community TEXT NOT NULL,
                municipality TEXT NOT NULL,
                final_price_eur NUMERIC NOT NULL,
                spanish_market_price_eur NUMERIC,
                savings_eur NUMERIC,
                savings_pct NUMERIC,
                market_match_level TEXT,
                market_sample_size INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                boe_fallback INTEGER NOT NULL DEFAULT 0,
                co2_unconfirmed INTEGER NOT NULL DEFAULT 0,
                no_comparables INTEGER NOT NULL DEFAULT 0,
                savings_hidden INTEGER NOT NULL DEFAULT 0,
                request_json TEXT NOT NULL,
                public_result_json TEXT NOT NULL,
                fiscal_snapshot_json TEXT NOT NULL,
                market_snapshot_json TEXT NOT NULL,
                simulated INTEGER NOT NULL DEFAULT 0 CHECK (simulated IN (0, 1))
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS public_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                vehicle_label TEXT NOT NULL,
                final_price_eur NUMERIC NOT NULL,
                source_url TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                calculation_id TEXT,
                anonymous_id TEXT,
                consent_given INTEGER NOT NULL DEFAULT 1,
                consent_text TEXT,
                consent_at TEXT,
                personal_data_erased_at TEXT,
                simulated INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (calculation_id) REFERENCES customer_calculations(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS admin_login_security (
                username TEXT PRIMARY KEY,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_calculations_created ON customer_calculations(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_calculations_anonymous ON customer_calculations(anonymous_id)",
            "CREATE INDEX IF NOT EXISTS idx_leads_email ON public_leads(email)",
        ),
    ),
)

_LEGACY_LEAD_COLUMNS = {
    "calculation_id": "TEXT",
    "anonymous_id": "TEXT",
    "consent_given": "INTEGER NOT NULL DEFAULT 1",
    "consent_text": "TEXT",
    "consent_at": "TEXT",
    "personal_data_erased_at": "TEXT",
    "simulated": "INTEGER NOT NULL DEFAULT 0",
}


def _connect(database_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(database_path) if database_path is not None else customer_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_customer_database(database_path: str | Path | None = None) -> Path:
    path = Path(database_path) if database_path is not None else customer_database_path()
    apply_migrations(path, component=COMPONENT, migrations=MIGRATIONS)
    with _connect(path) as connection:
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(public_leads)")
        }
        for name, definition in _LEGACY_LEAD_COLUMNS.items():
            if name not in columns:
                connection.execute(
                    f"ALTER TABLE public_leads ADD COLUMN {name} {definition}"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_email ON public_leads(email)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_calculation ON public_leads(calculation_id)"
        )
    return path


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def record_calculation(
    *,
    anonymous_id: str,
    request_data: dict[str, Any],
    public_result: dict[str, Any],
    audit: dict[str, Any],
    source_url: str | None = None,
    simulated: bool = False,
    database_path: str | Path | None = None,
) -> str:
    """Persist the exact public result and immutable fiscal/market snapshots."""

    initialize_customer_database(database_path)
    calculation_id = str(uuid.uuid4())
    warnings = public_result.get("warnings") or []
    market = audit.get("market") or {}
    boe = audit.get("boe") or {}
    savings_filter = market.get("savings_sanity_filter") or {}
    fiscal_snapshot = {
        "boe": boe,
        "vat": audit.get("vat") or {},
        "registration": audit.get("registration") or {},
        "fiscal_breakdown": audit.get("fiscal_breakdown") or [],
        "fiscal_version": public_result.get("fiscal_version"),
    }
    source_mode = "url" if source_url else "manual"
    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO customer_calculations (
                id, created_at, anonymous_id, source_mode, source_url,
                vehicle_label, make, model, version, first_registration,
                purchase_price_eur, autonomous_community, municipality,
                final_price_eur, spanish_market_price_eur, savings_eur, savings_pct,
                market_match_level, market_sample_size, warning_count,
                boe_fallback, co2_unconfirmed, no_comparables, savings_hidden,
                request_json, public_result_json, fiscal_snapshot_json,
                market_snapshot_json, simulated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                calculation_id,
                datetime.now(UTC).isoformat(),
                anonymous_id,
                source_mode,
                source_url,
                public_result["vehicle_label"],
                request_data["make"],
                request_data["model"],
                request_data.get("version"),
                request_data.get("first_registration"),
                request_data["purchase_price"],
                request_data["autonomous_community"],
                request_data["municipality"],
                public_result["final_price_eur"],
                public_result.get("spanish_market_price_eur"),
                public_result.get("savings_eur"),
                public_result.get("savings_pct"),
                public_result.get("market_match_level"),
                public_result.get("market_sample_size", 0),
                len(warnings),
                int(boe.get("selected_row_id") is None),
                int(boe.get("co2_source") in {None, "user"}),
                int(not market.get("comparables")),
                int(bool(savings_filter.get("applied"))),
                _json(request_data),
                _json(public_result),
                _json(fiscal_snapshot),
                _json(market),
                int(simulated),
            ),
        )
    return calculation_id


def calculation_belongs_to_visitor(
    calculation_id: str,
    anonymous_id: str,
    *,
    database_path: str | Path | None = None,
) -> bool:
    initialize_customer_database(database_path)
    with _connect(database_path) as connection:
        return connection.execute(
            "SELECT 1 FROM customer_calculations WHERE id = ? AND anonymous_id = ?",
            (calculation_id, anonymous_id),
        ).fetchone() is not None


def erase_personal_data(
    email: str, *, database_path: str | Path | None = None
) -> int:
    """Erase contact details and unlink leads while retaining anonymous aggregates."""

    initialize_customer_database(database_path)
    normalized = email.strip().casefold()
    with _connect(database_path) as connection:
        email_column = next(
            row
            for row in connection.execute("PRAGMA table_info(public_leads)")
            if row["name"] == "email"
        )
        erased_email = "" if email_column["notnull"] else None
        cursor = connection.execute(
            """
            UPDATE public_leads
            SET email = ?, phone = NULL, calculation_id = NULL,
                anonymous_id = NULL, personal_data_erased_at = ?, status = 'erased'
            WHERE lower(email) = ? AND personal_data_erased_at IS NULL
            """,
            (erased_email, datetime.now(UTC).isoformat(), normalized),
        )
        return cursor.rowcount


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    calculations: int
    anonymous_visitors: int
    leads: int
    average_final_price: float | None
    average_savings: float | None
    simulated_records: int


def dashboard_data(*, database_path: str | Path | None = None) -> tuple[DashboardSummary, list[dict[str, Any]]]:
    initialize_customer_database(database_path)
    with _connect(database_path) as connection:
        aggregate = connection.execute(
            """
            SELECT COUNT(*) calculations, COUNT(DISTINCT anonymous_id) visitors,
                   AVG(final_price_eur) average_final, AVG(savings_eur) average_savings,
                   SUM(simulated) simulated_records
            FROM customer_calculations
            """
        ).fetchone()
        leads = connection.execute(
            "SELECT COUNT(*) FROM public_leads WHERE personal_data_erased_at IS NULL"
        ).fetchone()[0]
        rows = connection.execute(
            """
            SELECT c.*, EXISTS(
                SELECT 1 FROM public_leads l
                WHERE l.calculation_id = c.id AND l.personal_data_erased_at IS NULL
            ) AS has_lead
            FROM customer_calculations c
            ORDER BY c.created_at DESC LIMIT 100
            """
        ).fetchall()
    return (
        DashboardSummary(
            calculations=int(aggregate["calculations"] or 0),
            anonymous_visitors=int(aggregate["visitors"] or 0),
            leads=int(leads),
            average_final_price=aggregate["average_final"],
            average_savings=aggregate["average_savings"],
            simulated_records=int(aggregate["simulated_records"] or 0),
        ),
        [dict(row) for row in rows],
    )


def calculation_detail(
    calculation_id: str, *, database_path: str | Path | None = None
) -> dict[str, Any] | None:
    initialize_customer_database(database_path)
    with _connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM customer_calculations WHERE id = ?", (calculation_id,)
        ).fetchone()
        if row is None:
            return None
        lead = connection.execute(
            """
            SELECT id, email, phone, status, consent_at, consent_text
            FROM public_leads WHERE calculation_id = ? AND personal_data_erased_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            (calculation_id,),
        ).fetchone()
    result = dict(row)
    for key in (
        "request_json",
        "public_result_json",
        "fiscal_snapshot_json",
        "market_snapshot_json",
    ):
        result[key.removesuffix("_json")] = json.loads(result.pop(key))
    result["lead"] = dict(lead) if lead else None
    return result


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "CONSENT_TEXT",
    "DashboardSummary",
    "calculation_belongs_to_visitor",
    "calculation_detail",
    "dashboard_data",
    "erase_personal_data",
    "hash_session_token",
    "initialize_customer_database",
    "record_calculation",
]
