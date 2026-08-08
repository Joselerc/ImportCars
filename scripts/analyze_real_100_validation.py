"""Cross-check the live 100-ad CSV and annotate reproducible incidences."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

from import_cars.enrichment.signature import normalize_fuel_category
from import_cars.fiscal_data.resolver import (
    _BRAND_ALIASES,
    POWER_TOLERANCE_KW,
    _fuel_code,
    _fuel_for_query,
    _model_head,
    _normalize,
)
from import_cars.persistence.paths import fiscal_database_path


def _number(value: str) -> float | None:
    try:
        return float(value) if value != "" else None
    except (TypeError, ValueError):
        return None


def _year(value: str) -> int | None:
    if not value or value == "nuevo_sin_matricular":
        return datetime.now(UTC).year
    try:
        return int(value[:4])
    except ValueError:
        return None


def _fallback_cause(connection: sqlite3.Connection, row: dict[str, str]) -> str:
    brand = _normalize(row["marca_extraida"]).upper()
    brand = _BRAND_ALIASES.get(brand, brand)
    query = _normalize(f"{row['modelo_extraido']} {row['version_extraida']}")
    model_head = _model_head(query)
    year = _year(row["primera_matriculacion"])
    displacement = _number(row["cilindrada_cc"])
    power = _number(row["potencia_kw"])
    fuel = _fuel_for_query(row["combustible"], query)
    if year is None:
        return "fecha_ausente"

    all_rows = connection.execute(
        """
        SELECT v.model_type, v.commercial_start, v.commercial_end,
               v.displacement_cc, v.fuel_code, v.power_kw
        FROM boe_valores AS v
        JOIN boe_dataset_versions AS d ON d.id = v.dataset_id
        WHERE UPPER(v.brand) = ? AND v.category = 'passenger_vehicle'
          AND d.exercise = (SELECT MAX(exercise) FROM boe_dataset_versions)
        """,
        (brand,),
    ).fetchall()
    model_rows = [
        item for item in all_rows if _model_head(_normalize(item[0])) == model_head
    ]
    if not model_rows:
        return "modelo_ausente_o_nomenclatura"
    period_rows = [
        item
        for item in model_rows
        if (item[1] is None or item[1] <= year)
        and (item[2] is None or item[2] >= year)
    ]
    if not period_rows:
        ranges = sorted({f"{item[1] or '?'}-{item[2] or '?'}" for item in model_rows})
        return f"vigencia_comercial (BOE: {', '.join(ranges[:4])})"
    no_displacement = fuel in {"ELC", "H"}
    displacement_rows = [
        item
        for item in period_rows
        if (no_displacement and item[3] in (None, 0))
        or (not no_displacement and displacement is not None and item[3] == int(displacement))
    ]
    if not displacement_rows:
        available = sorted({item[3] for item in period_rows if item[3] is not None})
        return f"cilindrada (anuncio {displacement:g}; BOE {available[:8]})"
    fuel_rows = [item for item in displacement_rows if _fuel_code(item[4]) == fuel]
    if not fuel_rows:
        available = sorted({_fuel_code(item[4]) or "?" for item in displacement_rows})
        return f"combustible (anuncio {fuel}; BOE {available})"
    power_rows = [
        item
        for item in fuel_rows
        if item[5] is not None
        and power is not None
        and abs(float(item[5]) - power) <= POWER_TOLERANCE_KW
    ]
    if not power_rows:
        available = sorted({item[5] for item in fuel_rows if item[5] is not None})
        nearest = sorted(available, key=lambda value: abs(float(value) - (power or 0)))[:5]
        return f"potencia (anuncio {power:g} kW; BOE más próximos {nearest})"
    return "desconocida_tras_filtro_tecnico"


def analyze(path: Path, *, write: bool) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    connection = sqlite3.connect(f"file:{fiscal_database_path().resolve()}?mode=ro", uri=True)
    causes: Counter[str] = Counter()
    incidence_groups: dict[str, list[str]] = {}
    for row in rows:
        incidence = row["detalle_incidencia"]
        if row["boe_usa_fallback"] == "True":
            cause = _fallback_cause(connection, row)
            causes[cause.split(" (")[0]] += 1
            incidence = f"Fallback BOE: {cause}"
            incidence_groups.setdefault("fallback_boe", []).append(
                f"{row['id_mobile_de']} {row['marca_extraida']} {row['modelo_extraido']}: {cause}"
            )
        elif row["estado"] == "pendiente_datos_anuncio":
            incidence_groups.setdefault("dato_ausente", []).append(
                f"{row['id_mobile_de']} {row['marca_extraida']} {row['modelo_extraido']}: {incidence}"
            )
        savings = _number(row["ahorro_eur"])
        market = _number(row["mercado_es_mediana_eur"])
        if savings is not None and savings < 0:
            incidence_groups.setdefault("ahorro_negativo", []).append(
                f"{row['id_mobile_de']} {row['marca_extraida']} {row['modelo_extraido']}: {savings:.2f} €"
            )
        if savings is not None and market and abs(savings) / market > 0.5:
            incidence_groups.setdefault("ahorro_desproporcionado", []).append(
                f"{row['id_mobile_de']} {row['marca_extraida']} {row['modelo_extraido']}: "
                f"{savings:.2f} € ({abs(savings) / market:.1%} del mercado)"
            )
        row["detalle_incidencia"] = incidence
    connection.close()

    calculated = [row for row in rows if row["estado"].startswith("calculado")]
    fallback_rows = [row for row in rows if row["boe_usa_fallback"] == "True"]
    savings_rows = [row for row in calculated if row["ahorro_eur"]]
    fuel_other = [
        row
        for row in rows
        if row["combustible"] == "otro"
        and normalize_fuel_category(row["combustible_origen"]) != "other"
    ]
    used = [row for row in calculated if row["caso_iva"].startswith("usado_")]
    new = [row for row in calculated if row["caso_iva"] == "nuevo_iva_espanol"]
    vat_used_failures = [row for row in used if (_number(row["iva_espanol_eur"]) or 0) != 0]
    vat_new_failures = [row for row in new if (_number(row["iva_espanol_eur"]) or 0) <= 0]
    net_base_failures = []
    for row in new:
        base = _number(row["base_iva_eur"])
        net = _number(row["precio_alemania_neto_eur"])
        gross = _number(row["precio_alemania_bruto_eur"])
        expected = net if net is not None else (gross / 1.19 if gross else None)
        if base is None or expected is None or abs(base - expected) > 0.02:
            net_base_failures.append(row)

    if write:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)

    result: dict[str, object] = {
        "rows": len(rows),
        "unique_ids": len({row["id_mobile_de"] for row in rows}),
        "states": Counter(row["estado"] for row in rows),
        "price_bands": Counter(
            "barato"
            if (_number(row["precio_alemania_bruto_eur"]) or 0) < 3000
            else "caro"
            if (_number(row["precio_alemania_bruto_eur"]) or 0) > 30000
            else "medio"
            for row in rows
        ),
        "fuels": Counter(row["combustible"] for row in rows),
        "sellers": Counter(row["tipo_vendedor"] for row in rows),
        "makes": Counter(row["marca_extraida"] for row in rows),
        "fallback_count": len(fallback_rows),
        "fallback_denominator": len(calculated),
        "fallback_pct": round(100 * len(fallback_rows) / len(calculated), 2),
        "fallback_causes": causes,
        "fuel_misclassified_count": len(fuel_other),
        "fuel_misclassified_pct": round(100 * len(fuel_other) / len(rows), 2),
        "savings_shown": len(savings_rows),
        "savings_hidden": len(rows) - len(savings_rows),
        "market_levels": Counter(row["nivel_comparables"] or "hidden" for row in rows),
        "vat_cases": Counter(row["caso_iva"] or "pending" for row in rows),
        "used_vat_failures": len(vat_used_failures),
        "new_vat_failures": len(vat_new_failures),
        "new_net_base_failures": len(net_base_failures),
        "missing_fields": Counter(
            field
            for row in rows
            for field in (
                "cilindros",
                "cambio",
                "carroceria",
                "co2_g_km",
                "primera_matriculacion",
            )
            if not row[field]
        ),
        "final_price_min": min(_number(row["precio_final_espana_eur"]) for row in calculated),
        "final_price_median": median(
            _number(row["precio_final_espana_eur"]) for row in calculated
        ),
        "final_price_max": max(_number(row["precio_final_espana_eur"]) for row in calculated),
        "incidences": incidence_groups,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--write-incidences", action="store_true")
    args = parser.parse_args()
    result = analyze(args.csv_path, write=args.write_incidences)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
