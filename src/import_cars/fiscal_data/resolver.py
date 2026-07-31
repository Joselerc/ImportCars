"""Resolve official BOE vehicle values without implementing tax formulas."""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "import_cars.sqlite3"

_BRAND_ALIASES = {
    "VW": "VOLKSWAGEN",
    "MERCEDES BENZ": "MERCEDES",
    "MERCEDES-BENZ": "MERCEDES",
}


@dataclass(frozen=True, slots=True)
class BoeValueResolution:
    """The exact official row selected for one vehicle."""

    value_eur: float
    brand: str
    model_type: str
    commercial_start: int | None
    commercial_end: int | None
    displacement_cc: int | None
    power_kw: int | None
    fiscal_hp: float | None
    power_cv: int
    order_code: str
    exercise: int
    confidence: float


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    normalized = " ".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))
    return re.sub(r"\b(\d+)\s+([a-z])\b", r"\1\2", normalized)


def _database_path(database_path: str | Path | None) -> Path:
    if database_path is not None:
        return Path(database_path)
    configured = os.getenv("IMPORT_CARS_DATABASE_PATH")
    return Path(configured) if configured else DEFAULT_DATABASE_PATH


def _similarity(
    query: str,
    candidate: str,
    *,
    displacement_cc: int | None,
    candidate_displacement_cc: int | None,
    power_kw: float | None,
    candidate_power_kw: int | None,
) -> float:
    if query == candidate:
        text_score = 1.5
    else:
        query_tokens = set(query.split())
        candidate_tokens = set(candidate.split())
        overlap = len(query_tokens & candidate_tokens)
        recall = overlap / len(query_tokens) if query_tokens else 0.0
        precision = overlap / len(candidate_tokens) if candidate_tokens else 0.0
        ratio = SequenceMatcher(None, query, candidate).ratio()
        text_score = 0.45 * ratio + 0.40 * recall + 0.15 * precision
        if candidate.startswith(query):
            text_score += 0.15
        elif query in candidate:
            text_score += 0.10

    technical_score = 0.0
    if displacement_cc is not None and candidate_displacement_cc is not None:
        delta = abs(displacement_cc - candidate_displacement_cc)
        technical_score += max(0.0, 0.25 * (1 - delta / 500))
    if power_kw is not None and candidate_power_kw is not None:
        delta = abs(power_kw - candidate_power_kw)
        technical_score += max(0.0, 0.50 * (1 - delta / 50))
    return text_score + technical_score


def resolver_registro_valor_tablas(
    marca: str,
    modelo: str,
    fecha: date | int,
    *,
    displacement_cc: int | None = None,
    power_kw: float | None = None,
    database_path: str | Path | None = None,
) -> BoeValueResolution | None:
    """Resolve an unambiguous Annex I row by make, model/version and year.

    Technical fields are optional tie-breakers. Ambiguous matches deliberately
    return ``None`` so ``fiscal_engine`` can expose its existing warning instead
    of silently applying the value of a different trim.
    """

    if not marca.strip() or not modelo.strip():
        return None
    year = fecha if isinstance(fecha, int) else fecha.year
    path = _database_path(database_path)
    if not path.is_file():
        return None

    normalized_brand = _normalize(marca).upper()
    normalized_brand = _BRAND_ALIASES.get(normalized_brand, normalized_brand)
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            """
            SELECT
                v.brand, v.model_type, v.commercial_start, v.commercial_end,
                v.displacement_cc, v.power_kw, v.fiscal_hp, v.power_cv,
                v.value_eur, d.order_code, d.exercise
            FROM boe_valores AS v
            JOIN boe_dataset_versions AS d ON d.id = v.dataset_id
            WHERE UPPER(v.brand) = ?
              AND v.category = 'passenger_vehicle'
              AND d.exercise = (SELECT MAX(exercise) FROM boe_dataset_versions)
              AND (v.commercial_start IS NULL OR v.commercial_start <= ?)
              AND (v.commercial_end IS NULL OR v.commercial_end >= ?)
            """,
            (normalized_brand, year, year),
        ).fetchall()

    query = _normalize(modelo)
    normalized_make_in_model = _normalize(marca)
    if query.startswith(f"{normalized_make_in_model} "):
        query = query[len(normalized_make_in_model) + 1 :]
    model_head = query.split()[0] if query else ""
    ranked = []
    for row in rows:
        candidate = _normalize(row[1])
        if not candidate or candidate.split()[0] != model_head:
            continue
        score = _similarity(
            query,
            candidate,
            displacement_cc=displacement_cc,
            candidate_displacement_cc=row[4],
            power_kw=power_kw,
            candidate_power_kw=row[5],
        )
        ranked.append((score, row))
    ranked.sort(key=lambda item: (item[0], item[1][8]), reverse=True)
    if not ranked or ranked[0][0] < 0.65:
        return None

    best_score, best = ranked[0]
    if len(ranked) > 1:
        second_score, second = ranked[1]
        if best_score - second_score < 0.04 and best[8] != second[8]:
            return None

    return BoeValueResolution(
        value_eur=float(best[8]),
        brand=best[0],
        model_type=best[1],
        commercial_start=best[2],
        commercial_end=best[3],
        displacement_cc=best[4],
        power_kw=best[5],
        fiscal_hp=float(best[6]) if best[6] is not None else None,
        power_cv=best[7],
        order_code=best[9],
        exercise=best[10],
        confidence=round(best_score, 4),
    )


def resolver_valor_tablas(
    marca: str,
    modelo: str,
    fecha: date | int,
    *,
    displacement_cc: int | None = None,
    power_kw: float | None = None,
    database_path: str | Path | None = None,
) -> float | None:
    """Return the official new value for one unambiguous BOE match."""

    resolution = resolver_registro_valor_tablas(
        marca,
        modelo,
        fecha,
        displacement_cc=displacement_cc,
        power_kw=power_kw,
        database_path=database_path,
    )
    return resolution.value_eur if resolution else None


__all__ = [
    "DEFAULT_DATABASE_PATH",
    "BoeValueResolution",
    "resolver_registro_valor_tablas",
    "resolver_valor_tablas",
]
