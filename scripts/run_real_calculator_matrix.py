"""Run a reproducible 35-listing end-to-end validation against live sources.

The script deliberately uses the same adapters and services as the public
calculator.  It never fills missing CO2 or registration data: it tries another
real listing for the requested model and records the failure if none is usable.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from import_cars.enrichment.co2_enricher import Co2Enricher
from import_cars.enrichment.signature import build_engine_key
from import_cars.filters import MileageRange, PriceRange, UnifiedFilters, YearRange
from import_cars.scrapers import MobileDeHttpScraper
from import_cars.services.market_reference import SpanishMarketReferenceService
from import_cars.services.public_calculator import (
    AuditCalculationInput,
    calculate_for_audit,
)
from import_cars.webapp import _parsed_listing_payload

TARGETS = [
    ("Fiat", "500X"),
    ("Fiat", "500"),
    ("Fiat", "Tipo"),
    ("Fiat", "Panda"),
    ("Fiat", "500L"),
    ("Mercedes-Benz", "A 180"),
    ("Mercedes-Benz", "C 220"),
    ("Mercedes-Benz", "E 220"),
    ("Mercedes-Benz", "GLC 220"),
    ("Mercedes-Benz", "CLA 200"),
    ("Audi", "A3"),
    ("Audi", "A4"),
    ("Audi", "Q3"),
    ("Audi", "Q5"),
    ("Audi", "A1"),
    ("Toyota", "Yaris"),
    ("Toyota", "Corolla"),
    ("Toyota", "RAV 4"),
    ("Toyota", "C-HR"),
    ("BMW", "320"),
    ("BMW", "520"),
    ("BMW", "X1"),
    ("BMW", "X3"),
    ("Hyundai", "i30"),
    ("Hyundai", "TUCSON"),
    ("Hyundai", "KONA"),
    ("Hyundai", "i20"),
    ("Seat", "Leon"),
    ("Seat", "Ibiza"),
    ("Seat", "Ateca"),
    ("Seat", "Arona"),
    ("Cupra", "Formentor"),
    ("Cupra", "Leon"),
    ("Cupra", "Ateca"),
    ("Cupra", "Born"),
]


CSV_FIELDS = [
    "prueba",
    "fecha_ejecucion_utc",
    "marca_solicitada",
    "modelo_solicitado",
    "estado",
    "id_mobile_de",
    "url_mobile_de",
    "titulo",
    "marca_extraida",
    "modelo_extraido",
    "version_extraida",
    "primera_matriculacion",
    "km",
    "precio_alemania_bruto_eur",
    "precio_alemania_neto_eur",
    "iva_desglosable",
    "tipo_vendedor",
    "combustible_origen",
    "combustible",
    "potencia_kw",
    "cilindrada_cc",
    "cilindros",
    "bateria_kwh",
    "cambio",
    "carroceria",
    "clave_motor_matching",
    "co2_g_km",
    "fuente_co2",
    "danado_accidentado",
    "boe_fila_id",
    "boe_usa_fallback",
    "boe_modelo_resuelto",
    "boe_valor_nuevo_eur",
    "boe_confianza",
    "boe_candidatas_base",
    "boe_candidatas_tecnicas",
    "boe_candidatas_cambio",
    "caso_iva",
    "base_iva_eur",
    "iva_espanol_eur",
    "iedmt_eur",
    "itp_eur",
    "ivtm_eur",
    "transporte_eur",
    "honorarios_eur",
    "precio_final_espana_eur",
    "nivel_comparables",
    "confianza_mercado",
    "comparables_usados",
    "mercado_es_mediana_eur",
    "mercado_es_min_eur",
    "mercado_es_max_eur",
    "ahorro_eur",
    "ahorro_pct",
    "ahorro_calculado_interno_eur",
    "ahorro_calculado_interno_pct",
    "filtro_cordura_activado",
    "umbral_ahorro_fiable_pct",
    "aviso_calidad_mercado",
    "numero_avisos",
    "avisos",
    "desglose_json",
    "detalle_incidencia",
]


def _empty_row(test_number: int, make: str, model: str) -> dict[str, Any]:
    return {
        field: "" for field in CSV_FIELDS
    } | {
        "prueba": test_number,
        "fecha_ejecucion_utc": datetime.now(UTC).isoformat(),
        "marca_solicitada": make,
        "modelo_solicitado": model,
    }


def _line_amount(lines: list[dict[str, Any]], *needles: str) -> float | str:
    for line in lines:
        text = f"{line.get('key', '')} {line.get('label', '')}".casefold()
        if any(needle.casefold() in text for needle in needles):
            return float(line.get("amount_eur") or 0)
    return ""


def _selected_boe_value(boe: dict[str, Any]) -> float | str:
    selected = boe.get("selected_row_id")
    for candidate in boe.get("candidates") or []:
        if candidate.get("row_id") == selected:
            return float(candidate["value_eur"])
    return ""


def _candidate_payload(listing) -> tuple[dict[str, Any], list[str]]:
    enriched = Co2Enricher().enrich([listing])[0]
    payload = _parsed_listing_payload(enriched)
    missing = list(payload.pop("missing_fields", []))
    payload.pop("source", None)
    payload.pop("source_url", None)
    payload.pop("title", None)
    payload.update(
        {
            "autonomous_community": "Madrid",
            "municipality": "Madrid",
            "buyer_type": "particular",
        }
    )
    return payload, missing


async def _run_target(
    *,
    test_number: int,
    make: str,
    model: str,
    candidates: int,
    mobile: MobileDeHttpScraper,
    market: SpanishMarketReferenceService,
    listing_id: str | None = None,
) -> dict[str, Any]:
    row = _empty_row(test_number, make, model)
    failures: list[str] = []
    if listing_id:
        candidate_ids = [listing_id]
    else:
        try:
            summaries = await asyncio.to_thread(
                mobile.search,
                UnifiedFilters(
                    make=make,
                    model=model,
                    country_code="DE",
                    price_range=PriceRange(min_price=3_000, max_price=75_000),
                    year_range=YearRange(min_year=2014, max_year=2025),
                    mileage_range=MileageRange(max_mileage=200_000),
                    page_size=candidates,
                ),
                candidates,
            )
        except Exception as exc:  # noqa: BLE001 - retain source failures
            row["estado"] = "error_busqueda_mobile"
            row["detalle_incidencia"] = f"{type(exc).__name__}: {exc}"
            return row
        candidate_ids = [summary.listing_id for summary in summaries.listings]

    for candidate_id in candidate_ids:
        try:
            listing = await asyncio.to_thread(mobile.get_listing, candidate_id)
            if listing is None:
                failures.append(f"{candidate_id}: detalle no disponible")
                continue
            payload, missing = await asyncio.to_thread(_candidate_payload, listing)
            if missing:
                failures.append(f"{listing.listing_id}: faltan {','.join(missing)}")
                continue
            try:
                calculation_input = AuditCalculationInput.model_validate(payload)
            except ValidationError as exc:
                failures.append(f"{listing.listing_id}: entrada inválida ({exc.errors()[0]['msg']})")
                continue

            result = await calculate_for_audit(
                calculation_input,
                market_service=market,
            )
            audit = result.audit.model_dump(mode="json")
            boe = audit["boe"]
            vat = audit["vat"]
            market_audit = audit["market"]
            breakdown = [line.model_dump(mode="json") for line in result.audit.fiscal_breakdown]
            public_lines = result.breakdown
            registration = listing.first_registration
            row.update(
                {
                    "estado": "calculado_boe" if boe.get("selected_row_id") else "calculado_fallback_boe",
                    "id_mobile_de": listing.listing_id,
                    "url_mobile_de": str(listing.url),
                    "titulo": listing.title or "",
                    "marca_extraida": listing.make or "",
                    "modelo_extraido": listing.model or "",
                    "version_extraida": listing.version or "",
                    "primera_matriculacion": (
                        f"{registration.year:04d}-{registration.month or 1:02d}"
                        if registration
                        else "nuevo_sin_matricular"
                        if listing.unregistered_new
                        else ""
                    ),
                    "km": listing.mileage_km if listing.mileage_km is not None else "",
                    "precio_alemania_bruto_eur": listing.price_eur or "",
                    "precio_alemania_neto_eur": listing.price_net_eur or "",
                    "iva_desglosable": bool(listing.vat_deductible),
                    "tipo_vendedor": payload["seller_type"],
                    "combustible_origen": listing.fuel_type or "",
                    "combustible": payload["fuel"],
                    "potencia_kw": listing.power_kw if listing.power_kw is not None else "",
                    "cilindrada_cc": payload["displacement_cc"],
                    "cilindros": listing.cylinders if listing.cylinders is not None else "",
                    "bateria_kwh": (
                        listing.battery_capacity_kwh
                        if listing.battery_capacity_kwh is not None
                        else ""
                    ),
                    "cambio": payload.get("transmission") or "",
                    "carroceria": payload.get("body_type") or "",
                    "clave_motor_matching": build_engine_key(listing),
                    "co2_g_km": payload.get("co2_gkm") if payload.get("co2_gkm") is not None else "",
                    "fuente_co2": payload.get("co2_source") or "",
                    "danado_accidentado": bool(payload.get("damaged")),
                    "boe_fila_id": boe.get("selected_row_id") or "",
                    "boe_usa_fallback": not bool(boe.get("selected_row_id")),
                    "boe_modelo_resuelto": result.boe_model_match or "",
                    "boe_valor_nuevo_eur": _selected_boe_value(boe),
                    "boe_confianza": result.boe_confidence,
                    "boe_candidatas_base": boe.get("base_candidate_count", 0),
                    "boe_candidatas_tecnicas": boe.get("technical_candidate_count", 0),
                    "boe_candidatas_cambio": boe.get("transmission_candidate_count", 0),
                    "caso_iva": vat.get("case") or "",
                    "base_iva_eur": vat.get("tax_base_eur") or 0,
                    "iva_espanol_eur": vat.get("spanish_vat_eur") or 0,
                    "iedmt_eur": _line_amount(public_lines, "iedmt", "matriculación"),
                    "itp_eur": _line_amount(public_lines, "itp", "transmisiones"),
                    "ivtm_eur": _line_amount(public_lines, "ivtm", "circulación"),
                    "transporte_eur": _line_amount(public_lines, "transporte"),
                    "honorarios_eur": _line_amount(public_lines, "honorarios"),
                    "precio_final_espana_eur": result.final_price_eur,
                    "nivel_comparables": result.market_match_level or "",
                    "confianza_mercado": result.market_confidence,
                    "comparables_usados": result.market_sample_size,
                    "mercado_es_mediana_eur": market_audit.get("median_eur") or "",
                    "mercado_es_min_eur": market_audit.get("minimum_eur") or "",
                    "mercado_es_max_eur": market_audit.get("maximum_eur") or "",
                    "ahorro_eur": result.savings_eur if result.savings_eur is not None else "",
                    "ahorro_pct": result.savings_pct if result.savings_pct is not None else "",
                    "ahorro_calculado_interno_eur": (
                        market_audit["savings_sanity_filter"].get(
                            "calculated_savings_eur"
                        )
                        if market_audit.get("savings_sanity_filter")
                        else ""
                    ),
                    "ahorro_calculado_interno_pct": (
                        market_audit["savings_sanity_filter"].get(
                            "calculated_savings_pct"
                        )
                        if market_audit.get("savings_sanity_filter")
                        else ""
                    ),
                    "filtro_cordura_activado": bool(
                        market_audit.get("savings_sanity_filter", {}).get("applied")
                    ),
                    "umbral_ahorro_fiable_pct": market_audit.get(
                        "savings_sanity_filter", {}
                    ).get("threshold_pct", ""),
                    "aviso_calidad_mercado": market_audit.get("quality_warning") or "",
                    "numero_avisos": len(result.warnings),
                    "avisos": " | ".join(result.warnings),
                    "desglose_json": json.dumps(breakdown, ensure_ascii=False, separators=(",", ":")),
                    "detalle_incidencia": "",
                }
            )
            return row
        except Exception as exc:  # noqa: BLE001 - try another real ad and report why
            failures.append(f"{candidate_id}: {type(exc).__name__}: {exc}")

    row["estado"] = "sin_anuncio_calculable"
    row["detalle_incidencia"] = " | ".join(failures[:12]) or "La búsqueda no devolvió anuncios"
    return row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _validate_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if reader.fieldnames != CSV_FIELDS:
        raise RuntimeError("Las columnas del CSV final no coinciden con el contrato")
    if len(rows) != len(TARGETS):
        raise RuntimeError(f"Se esperaban {len(TARGETS)} filas y se encontraron {len(rows)}")
    if [int(row["prueba"]) for row in rows] != list(range(1, len(TARGETS) + 1)):
        raise RuntimeError("La numeración de las pruebas no es correlativa")


async def _main(output: Path, candidates: int, input_csv: Path | None = None) -> int:
    mobile = MobileDeHttpScraper()
    market = SpanishMarketReferenceService(ttl_seconds=0)
    baseline_rows: list[dict[str, str]] | None = None
    if input_csv:
        with input_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            baseline_rows = list(csv.DictReader(handle))
        if len(baseline_rows) != len(TARGETS):
            raise RuntimeError(
                f"La matriz base debe contener {len(TARGETS)} filas, no "
                f"{len(baseline_rows)}"
            )
    rows: list[dict[str, Any]] = []
    for index, (make, model) in enumerate(TARGETS, start=1):
        print(f"[{index:02d}/{len(TARGETS)}] {make} {model}", flush=True)
        row = await _run_target(
            test_number=index,
            make=make,
            model=model,
            candidates=candidates,
            mobile=mobile,
            market=market,
            listing_id=(baseline_rows[index - 1]["id_mobile_de"] if baseline_rows else None),
        )
        rows.append(row)
        _write_csv(output, rows)
        print(
            f"  -> {row['estado']} | final={row['precio_final_espana_eur']} "
            f"| BOE={row['boe_fila_id']} | mercado={row['nivel_comparables']} "
            f"({row['comparables_usados']})",
            flush=True,
        )

    _validate_csv(output)
    calculated = sum(row["estado"].startswith("calculado") for row in rows)
    boe = sum(row["estado"] == "calculado_boe" for row in rows)
    savings = sum(row["ahorro_eur"] != "" for row in rows)
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "rows": len(rows),
                "calculated": calculated,
                "boe_resolved": boe,
                "with_savings": savings,
            },
            ensure_ascii=False,
        )
    )
    return 0 if calculated == len(TARGETS) else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports/validacion_real_35_modelos.csv"),
    )
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="Reprocesa exactamente los IDs de una matriz anterior.",
    )
    args = parser.parse_args()
    if len(TARGETS) != 35:
        raise RuntimeError(f"La matriz debe contener 35 casos, no {len(TARGETS)}")
    return asyncio.run(_main(args.output, max(1, args.candidates), args.input_csv))


if __name__ == "__main__":
    sys.exit(main())
