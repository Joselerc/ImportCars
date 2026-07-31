"""Ingest official vehicle values from a BOE XML publication.

The loader deliberately does not implement tax formulas. It preserves the
official Annex I values, Annex IV percentages and the accompanying legal note
so the separately supplied ``fiscal_engine`` can remain the single source of
truth for calculations.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_BOE_XML_URL = "https://www.boe.es/eli/es/o/2025/12/17/hac1501/dof/spa/xml"


class BoeParseError(ValueError):
    """Raised when a BOE document does not have the expected official shape."""


@dataclass(frozen=True, slots=True)
class BoeVehicleValue:
    category: str
    brand: str
    model_type: str
    commercial_start: int | None
    commercial_end: int | None
    displacement_cc: int | None
    cylinders: int | None
    fuel_code: str
    power_kw: int | None
    fiscal_hp: Decimal | None
    power_cv: int
    value_eur: int


@dataclass(frozen=True, slots=True)
class BoeGenericValueBand:
    category: str
    criterion_label: str
    value_eur: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class BoeDepreciationBand:
    category: str
    usage_label: str
    percentage: int
    ordinal: int


@dataclass(frozen=True, slots=True)
class BoeDataset:
    boe_id: str
    order_code: str
    exercise: int
    publication_date: str
    effective_date: str
    source_url: str
    source_sha256: str
    vehicle_values: tuple[BoeVehicleValue, ...]
    generic_value_bands: tuple[BoeGenericValueBand, ...]
    depreciation_bands: tuple[BoeDepreciationBand, ...]
    depreciation_note: str


@dataclass(frozen=True, slots=True)
class BoeLoadSummary:
    dataset_id: int
    order_code: str
    exercise: int
    vehicle_count: int
    generic_band_count: int
    depreciation_band_count: int


def _text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _metadata(root: ET.Element, name: str) -> str:
    value = _text(root.find(f"./metadatos/{name}"))
    if not value:
        raise BoeParseError(f"Falta el metadato obligatorio del BOE: {name}")
    return value


def _date(value: str, field_name: str) -> str:
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8])).isoformat()
    except (TypeError, ValueError) as exc:
        raise BoeParseError(f"Fecha BOE no valida en {field_name}: {value!r}") from exc


def _integer(value: str, *, optional: bool = False) -> int | None:
    normalized = value.strip().replace(".", "")
    if not normalized and optional:
        return None
    try:
        return int(normalized)
    except ValueError as exc:
        raise BoeParseError(f"Entero BOE no valido: {value!r}") from exc


def _decimal(value: str, *, optional: bool = False) -> Decimal | None:
    normalized = value.strip().replace(".", "").replace(",", ".")
    if not normalized and optional:
        return None
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise BoeParseError(f"Decimal BOE no valido: {value!r}") from exc


def _annex_positions(children: list[ET.Element]) -> dict[str, int]:
    positions = {
        _text(element): index
        for index, element in enumerate(children)
        if element.tag == "p" and _text(element) in {"ANEXO I", "ANEXO II", "ANEXO IV"}
    }
    missing = {"ANEXO I", "ANEXO II", "ANEXO IV"} - positions.keys()
    if missing:
        raise BoeParseError(f"No se encontraron los anexos requeridos: {sorted(missing)}")
    return positions


def _exercise(children: list[ET.Element], annex_one_start: int) -> int:
    for element in children[annex_one_start + 1 :]:
        if element.tag == "table":
            break
        match = re.search(r"Valores para el ejercicio\s+(\d{4})", _text(element))
        if match:
            return int(match.group(1))
    raise BoeParseError("No se encontro el ejercicio fiscal del Anexo I")


def _vehicle_rows(table: ET.Element, category: str) -> list[BoeVehicleValue]:
    heading = _text(table.find("thead"))
    brand_match = re.search(r"Marca:\s*(.+?)\s+Modelo-Tipo", heading)
    if not brand_match:
        return []

    brand = brand_match.group(1).strip()
    values: list[BoeVehicleValue] = []
    for row_number, row in enumerate(table.findall("./tbody/tr"), start=1):
        cells = [_text(cell) for cell in row.findall("td")]
        if len(cells) != 10:
            raise BoeParseError(
                f"Fila {row_number} de {brand} tiene {len(cells)} columnas; se esperaban 10"
            )
        values.append(
            BoeVehicleValue(
                category=category,
                brand=brand,
                model_type=cells[0],
                commercial_start=_integer(cells[1], optional=True),
                commercial_end=_integer(cells[2], optional=True),
                displacement_cc=_integer(cells[3], optional=True),
                cylinders=_integer(cells[4], optional=True),
                fuel_code=cells[5],
                power_kw=_integer(cells[6], optional=True),
                fiscal_hp=_decimal(cells[7], optional=True),
                power_cv=_integer(cells[8]),
                value_eur=_integer(cells[9]),
            )
        )
    return values


def _generic_rows(table: ET.Element, category: str) -> list[BoeGenericValueBand]:
    values: list[BoeGenericValueBand] = []
    for ordinal, row in enumerate(table.findall("./tbody/tr")):
        cells = [_text(cell) for cell in row.findall("td")]
        if len(cells) != 2:
            raise BoeParseError(
                f"Fila {ordinal + 1} de {category} tiene {len(cells)} columnas; se esperaban 2"
            )
        values.append(
            BoeGenericValueBand(
                category=category,
                criterion_label=cells[0],
                value_eur=_integer(cells[1]),
                ordinal=ordinal,
            )
        )
    return values


def _parse_annex_one(
    children: list[ET.Element], start: int, end: int
) -> tuple[list[BoeVehicleValue], list[BoeGenericValueBand]]:
    vehicle_values: list[BoeVehicleValue] = []
    generic_bands: list[BoeGenericValueBand] = []
    category = "passenger_vehicle"
    generic_categories = {
        "ciclomotores y motocicletas electricos": "electric_motorcycle",
        "ciclomotores y motocicletas de motor de combustion": "combustion_motorcycle",
        "quads": "quad",
        "buggys": "buggy",
    }

    for element in children[start + 1 : end]:
        value = _text(element)
        folded = value.casefold().replace("é", "e").replace("ó", "o")
        if element.tag == "p" and element.attrib.get("class") == "centro_negrita":
            if "autocaravanas" in folded:
                category = "motorhome"
            else:
                for label, mapped_category in generic_categories.items():
                    if label in folded:
                        category = mapped_category
                        break
        elif element.tag == "table":
            rows = _vehicle_rows(element, category)
            if rows:
                vehicle_values.extend(rows)
            elif category in generic_categories.values():
                generic_bands.extend(_generic_rows(element, category))

    if not vehicle_values:
        raise BoeParseError("El Anexo I no contiene valores de vehiculos")
    if not generic_bands:
        raise BoeParseError("El Anexo I no contiene las tablas genericas esperadas")
    return vehicle_values, generic_bands


def _parse_annex_four(
    children: list[ET.Element], start: int
) -> tuple[list[BoeDepreciationBand], str]:
    bands: list[BoeDepreciationBand] = []
    note = ""
    table_number = 0
    for element in children[start + 1 :]:
        if element.tag == "p" and _text(element).startswith("ANEXO "):
            break
        if element.tag == "table":
            category = "conventional_vehicle" if table_number == 0 else "motorhome"
            for ordinal, row in enumerate(element.findall("./tbody/tr")):
                cells = [_text(cell) for cell in row.findall("td")]
                if len(cells) != 2:
                    raise BoeParseError(
                        f"Fila {ordinal + 1} del Anexo IV tiene {len(cells)} columnas"
                    )
                bands.append(
                    BoeDepreciationBand(
                        category=category,
                        usage_label=cells[0],
                        percentage=_integer(cells[1]),
                        ordinal=ordinal,
                    )
                )
            table_number += 1
        elif table_number >= 2 and element.tag == "p" and _text(element):
            note = _text(element)

    if table_number != 2 or not bands:
        raise BoeParseError(
            f"El Anexo IV contiene {table_number} tablas; se esperaban exactamente 2"
        )
    if not note:
        raise BoeParseError("No se encontro la nota legal posterior a las tablas del Anexo IV")
    return bands, note


def parse_boe_xml(xml: bytes, *, source_url: str = DEFAULT_BOE_XML_URL) -> BoeDataset:
    """Parse an official BOE XML payload into immutable source records."""

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise BoeParseError("El documento descargado no es XML BOE valido") from exc
    if root.tag != "documento":
        raise BoeParseError(f"Raiz XML BOE inesperada: {root.tag!r}")

    text_root = root.find("texto")
    if text_root is None:
        raise BoeParseError("El XML BOE no contiene el bloque texto")
    children = list(text_root)
    positions = _annex_positions(children)
    exercise = _exercise(children, positions["ANEXO I"])
    vehicle_values, generic_bands = _parse_annex_one(
        children, positions["ANEXO I"], positions["ANEXO II"]
    )
    depreciation_bands, depreciation_note = _parse_annex_four(
        children, positions["ANEXO IV"]
    )

    return BoeDataset(
        boe_id=_metadata(root, "identificador"),
        order_code=_metadata(root, "numero_oficial"),
        exercise=exercise,
        publication_date=_date(_metadata(root, "fecha_publicacion"), "fecha_publicacion"),
        effective_date=_date(_metadata(root, "fecha_vigencia"), "fecha_vigencia"),
        source_url=source_url,
        source_sha256=hashlib.sha256(xml).hexdigest(),
        vehicle_values=tuple(vehicle_values),
        generic_value_bands=tuple(generic_bands),
        depreciation_bands=tuple(depreciation_bands),
        depreciation_note=depreciation_note,
    )


def download_boe_xml(url: str = DEFAULT_BOE_XML_URL, *, timeout: float = 60.0) -> bytes:
    """Download an official BOE XML document for an explicit annual load."""

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ImportCars BOE annual loader/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS boe_dataset_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boe_id TEXT NOT NULL,
    order_code TEXT NOT NULL,
    exercise INTEGER NOT NULL,
    publication_date TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    depreciation_note TEXT NOT NULL,
    vehicle_count INTEGER NOT NULL,
    generic_band_count INTEGER NOT NULL,
    depreciation_band_count INTEGER NOT NULL,
    UNIQUE(order_code, exercise)
);

CREATE TABLE IF NOT EXISTS boe_valores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL REFERENCES boe_dataset_versions(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_boe_valores_lookup
    ON boe_valores(dataset_id, brand, model_type, commercial_start, commercial_end);
CREATE INDEX IF NOT EXISTS idx_boe_valores_power
    ON boe_valores(dataset_id, power_kw, power_cv);

CREATE TABLE IF NOT EXISTS boe_generic_value_bands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL REFERENCES boe_dataset_versions(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    criterion_label TEXT NOT NULL,
    value_eur INTEGER NOT NULL,
    ordinal INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS boe_depreciation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL REFERENCES boe_dataset_versions(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    usage_label TEXT NOT NULL,
    percentage INTEGER NOT NULL,
    ordinal INTEGER NOT NULL
);
"""


def install_boe_dataset(database_path: str | Path, dataset: BoeDataset) -> BoeLoadSummary:
    """Atomically replace one annual BOE dataset in a local SQLite database."""

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(_SCHEMA)
        with connection:
            connection.execute(
                "DELETE FROM boe_dataset_versions WHERE order_code = ? AND exercise = ?",
                (dataset.order_code, dataset.exercise),
            )
            cursor = connection.execute(
                """
                INSERT INTO boe_dataset_versions (
                    boe_id, order_code, exercise, publication_date, effective_date,
                    source_url, source_sha256, downloaded_at, depreciation_note,
                    vehicle_count, generic_band_count, depreciation_band_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset.boe_id,
                    dataset.order_code,
                    dataset.exercise,
                    dataset.publication_date,
                    dataset.effective_date,
                    dataset.source_url,
                    dataset.source_sha256,
                    datetime.now(UTC).isoformat(),
                    dataset.depreciation_note,
                    len(dataset.vehicle_values),
                    len(dataset.generic_value_bands),
                    len(dataset.depreciation_bands),
                ),
            )
            dataset_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO boe_valores (
                    dataset_id, category, brand, model_type, commercial_start,
                    commercial_end, displacement_cc, cylinders, fuel_code,
                    power_kw, fiscal_hp, power_cv, value_eur
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        dataset_id,
                        row.category,
                        row.brand,
                        row.model_type,
                        row.commercial_start,
                        row.commercial_end,
                        row.displacement_cc,
                        row.cylinders,
                        row.fuel_code,
                        row.power_kw,
                        str(row.fiscal_hp) if row.fiscal_hp is not None else None,
                        row.power_cv,
                        row.value_eur,
                    )
                    for row in dataset.vehicle_values
                ),
            )
            connection.executemany(
                """
                INSERT INTO boe_generic_value_bands (
                    dataset_id, category, criterion_label, value_eur, ordinal
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (dataset_id, row.category, row.criterion_label, row.value_eur, row.ordinal)
                    for row in dataset.generic_value_bands
                ),
            )
            connection.executemany(
                """
                INSERT INTO boe_depreciation (
                    dataset_id, category, usage_label, percentage, ordinal
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (dataset_id, row.category, row.usage_label, row.percentage, row.ordinal)
                    for row in dataset.depreciation_bands
                ),
            )

    return BoeLoadSummary(
        dataset_id=dataset_id,
        order_code=dataset.order_code,
        exercise=dataset.exercise,
        vehicle_count=len(dataset.vehicle_values),
        generic_band_count=len(dataset.generic_value_bands),
        depreciation_band_count=len(dataset.depreciation_bands),
    )


def load_boe_year(
    database_path: str | Path,
    *,
    source_url: str = DEFAULT_BOE_XML_URL,
    expected_exercise: int | None = None,
    timeout: float = 60.0,
) -> BoeLoadSummary:
    """Download, validate and atomically install one official annual dataset."""

    dataset = parse_boe_xml(
        download_boe_xml(source_url, timeout=timeout),
        source_url=source_url,
    )
    if expected_exercise is not None and dataset.exercise != expected_exercise:
        raise BoeParseError(
            f"El XML contiene el ejercicio {dataset.exercise}, no {expected_exercise}"
        )
    return install_boe_dataset(database_path, dataset)
