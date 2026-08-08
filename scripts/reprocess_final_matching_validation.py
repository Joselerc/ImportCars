"""Reprocess the frozen 100-ad matrix after the final matching safeguards."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

from run_real_calculator_matrix import CSV_FIELDS, _run_target, _write_csv

from import_cars.scrapers import MobileDeHttpScraper
from import_cars.services.market_reference import SpanishMarketReferenceService


def _read_baseline(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 100:
        raise RuntimeError(f"Se esperaban 100 anuncios y se encontraron {len(rows)}")
    if any(not row.get("id_mobile_de") for row in rows):
        raise RuntimeError("Todas las filas base deben conservar su ID de mobile.de")
    return rows


def _validate(path: Path, expected_ids: list[str]) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if reader.fieldnames != CSV_FIELDS:
        raise RuntimeError("El CSV no conserva el contrato de auditoría ampliado")
    if [row["id_mobile_de"] for row in rows] != expected_ids:
        raise RuntimeError("El reprocesado no conserva los 100 IDs y su orden")


async def _main(baseline: Path, output: Path) -> int:
    baseline_rows = _read_baseline(baseline)
    mobile = MobileDeHttpScraper()
    market = SpanishMarketReferenceService(ttl_seconds=0)
    rows: list[dict[str, Any]] = []

    for index, old in enumerate(baseline_rows, start=1):
        listing_id = old["id_mobile_de"]
        print(f"[{index:03d}/100] {listing_id} {old['titulo']}", flush=True)
        row = await _run_target(
            test_number=index,
            make=old["marca_extraida"] or old["marca_solicitada"],
            model=old["modelo_extraido"] or old["modelo_solicitado"],
            candidates=1,
            mobile=mobile,
            market=market,
            listing_id=listing_id,
        )
        if not row["id_mobile_de"]:
            row.update(
                {
                    "id_mobile_de": listing_id,
                    "url_mobile_de": old["url_mobile_de"],
                    "titulo": old["titulo"],
                    "marca_extraida": old["marca_extraida"],
                    "modelo_extraido": old["modelo_extraido"],
                    "version_extraida": old["version_extraida"],
                }
            )
        rows.append(row)
        _write_csv(output, rows)
        print(
            f"  -> {row['estado']} batería={row['bateria_kwh'] or '-'} "
            f"mercado={row['nivel_comparables'] or '-'} "
            f"cordura={row['filtro_cordura_activado']}",
            flush=True,
        )

    expected_ids = [row["id_mobile_de"] for row in baseline_rows]
    _validate(output, expected_ids)
    calculated = [row for row in rows if row["estado"].startswith("calculado")]
    sanity = [row for row in calculated if row["filtro_cordura_activado"]]
    summary = {
        "output": str(output.resolve()),
        "rows": len(rows),
        "calculated": len(calculated),
        "public_savings": sum(row["ahorro_eur"] != "" for row in calculated),
        "sanity_filter_applied": len(sanity),
        "electric_or_phev_with_battery": sum(
            row["combustible"] in {"electrico", "phev"}
            and row["bateria_kwh"] != ""
            for row in calculated
        ),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return asyncio.run(_main(args.baseline, args.output))


if __name__ == "__main__":
    sys.exit(main())
