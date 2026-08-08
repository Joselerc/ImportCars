"""Build and execute a deliberately diverse 100-ad live validation matrix."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from run_real_calculator_matrix import (
    CSV_FIELDS,
    _candidate_payload,
    _empty_row,
    _run_target,
    _write_csv,
)

from fiscal_engine import es_nuevo_fiscal
from import_cars.enrichment.signature import build_engine_key, normalize_fuel_category
from import_cars.filters import (
    FuelType,
    MileageRange,
    PriceRange,
    UnifiedFilters,
    YearRange,
)
from import_cars.scrapers import MobileDeHttpScraper
from import_cars.services.market_reference import SpanishMarketReferenceService

MAKES = [
    "Fiat",
    "Mercedes-Benz",
    "Audi",
    "Toyota",
    "BMW",
    "Hyundai",
    "Seat",
    "Cupra",
    "Volkswagen",
    "Peugeot",
    "Renault",
    "Skoda",
    "Opel",
    "Ford",
    "Volvo",
    "Kia",
    "Nissan",
    "Mazda",
    "Dacia",
    "Citroen",
]

BAND_QUOTAS = {
    "barato": {
        "gasoline": 10,
        "diesel": 8,
        "lpg": 1,
        "cng": 1,
    },
    "medio": {
        "gasoline": 18,
        "diesel": 14,
        "hybrid": 8,
        "phev": 3,
        "electric": 5,
        "lpg": 1,
        "cng": 1,
    },
    "caro": {
        "gasoline": 2,
        "diesel": 3,
        "hybrid": 7,
        "phev": 7,
        "electric": 10,
        "lpg": 1,
    },
}

NEW_QUOTAS = {
    "gasoline": 1,
    "diesel": 1,
    "hybrid": 2,
    "phev": 3,
    "electric": 5,
}

PRICE_RANGES = {
    "barato": PriceRange(max_price=2_999),
    "medio": PriceRange(min_price=3_000, max_price=30_000),
    "caro": PriceRange(min_price=30_001, max_price=150_000),
}

SEARCH_FUELS = {
    "gasoline": FuelType.GASOLINE,
    "diesel": FuelType.DIESEL,
    "hybrid": FuelType.HYBRID,
    "phev": FuelType.HYBRID,
    "electric": FuelType.ELECTRIC,
    "lpg": FuelType.LPG,
    "cng": FuelType.CNG,
}

PUBLIC_FUELS = {
    "gasoline": "gasolina",
    "diesel": "diesel",
    "hybrid": "hibrido",
    "phev": "phev",
    "electric": "electrico",
    "lpg": "glp",
    "cng": "gnc",
}


@dataclass(frozen=True, slots=True)
class Slot:
    price_band: str
    fuel: str
    seller: str
    fiscally_new: bool
    preferred_make: str


def _slots() -> list[Slot]:
    slots: list[Slot] = []
    new_used = {fuel: 0 for fuel in NEW_QUOTAS}
    index = 0
    for price_band, fuels in BAND_QUOTAS.items():
        for fuel, count in fuels.items():
            for ordinal in range(count):
                fiscally_new = (
                    price_band == "caro"
                    and fuel in NEW_QUOTAS
                    and new_used[fuel] < NEW_QUOTAS[fuel]
                )
                if fiscally_new:
                    new_used[fuel] += 1
                    seller = "profesional_iva"
                elif price_band == "barato":
                    seller = "particular" if ordinal % 2 == 0 else "profesional_margen"
                elif price_band == "medio":
                    seller = (
                        "particular"
                        if index % 7 == 0
                        else "profesional_iva"
                        if index % 5 == 0
                        else "profesional_margen"
                    )
                else:
                    seller = "profesional_iva" if ordinal % 2 == 0 else "profesional_margen"
                slots.append(
                    Slot(
                        price_band=price_band,
                        fuel=fuel,
                        seller=seller,
                        fiscally_new=fiscally_new,
                        preferred_make=MAKES[(index * 7 + ordinal) % len(MAKES)],
                    )
                )
                index += 1
    if len(slots) != 100:
        raise RuntimeError(f"La matriz debe contener 100 huecos, no {len(slots)}")
    return slots


def _price_matches(price: float | None, band: str) -> bool:
    if price is None:
        return False
    if band == "barato":
        return price < 3_000
    if band == "medio":
        return 3_000 <= price <= 30_000
    return price > 30_000


def _is_fiscally_new(listing) -> bool:
    registration = listing.first_registration
    registration_date = (
        date(registration.year, registration.month or 1, 1) if registration else None
    )
    return es_nuevo_fiscal(
        registration_date,
        listing.mileage_km,
        nuevo_sin_matricular=listing.unregistered_new,
    )


class CandidateSelector:
    def __init__(self, excluded_ids: set[str]) -> None:
        self.mobile = MobileDeHttpScraper()
        self.excluded_ids = excluded_ids
        self.selected_ids: set[str] = set()
        self.search_cache: dict[tuple, list[str]] = {}
        self.detail_cache: dict[str, Any] = {}

    async def _search(
        self,
        *,
        make: str | None,
        slot: Slot,
        seller: str | None,
        fuel: str,
    ) -> list[str]:
        key = (make, slot.price_band, fuel, seller, slot.fiscally_new)
        if key in self.search_cache:
            return self.search_cache[key]
        filters = UnifiedFilters(
            make=make,
            country_code="DE",
            price_range=PRICE_RANGES[slot.price_band],
            year_range=(
                YearRange(min_year=2025, max_year=2026)
                if slot.fiscally_new
                else YearRange(min_year=2000, max_year=2025)
            ),
            mileage_range=(
                MileageRange(max_mileage=5_999)
                if slot.fiscally_new
                else MileageRange(max_mileage=300_000)
            ),
            fuel_types=[SEARCH_FUELS[fuel]],
            private_only=seller == "particular",
            dealer_only=seller in {"profesional_iva", "profesional_margen"},
            page_size=30,
        )
        try:
            result = await asyncio.to_thread(self.mobile.search, filters, 30)
            ids = [listing.listing_id for listing in result.listings]
        except Exception as exc:  # noqa: BLE001 - try the next controlled query
            print(f"  búsqueda fallida {key}: {type(exc).__name__}: {exc}", flush=True)
            ids = []
        if not ids and seller == "particular":
            # mobile.de omite la ubicación en bastantes fichas de particulares.
            # El scraper productivo las rechaza correctamente al reaplicar cn=DE,
            # pero aquí la propia URL ya acota Alemania: conservamos sus IDs para
            # auditar después el detalle real y el tipo de vendedor.
            try:
                url = self.mobile._build_search_url(filters, 1)
                response = await asyncio.to_thread(self.mobile._get, url)
                ids = self.mobile._extract_ids_from_listing(response.text)
            except Exception as exc:  # noqa: BLE001 - siguiente consulta controlada
                print(
                    f"  fallback particulares fallido {key}: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )
        self.search_cache[key] = ids
        return ids

    async def _detail(self, listing_id: str):
        if listing_id not in self.detail_cache:
            self.detail_cache[listing_id] = await asyncio.to_thread(
                self.mobile.get_listing,
                listing_id,
            )
        return self.detail_cache[listing_id]

    async def choose(self, slot: Slot):
        preferred_index = MAKES.index(slot.preferred_make)
        makes = [
            MAKES[(preferred_index + offset) % len(MAKES)]
            for offset in range(6)
        ] + [None]
        seller_options = [slot.seller, None]
        fuel_options = [slot.fuel]
        if slot.fuel in {"lpg", "cng"}:
            # These fuels are deliberately attempted first. If the market has no
            # complete real ad, preserve the 100-row total with a petrol rescue.
            fuel_options.append("gasoline")

        for fuel in fuel_options:
            for seller in seller_options:
                for make in makes:
                    for listing_id in await self._search(
                        make=make,
                        slot=slot,
                        seller=seller,
                        fuel=fuel,
                    ):
                        if (
                            listing_id in self.excluded_ids
                            or listing_id in self.selected_ids
                        ):
                            continue
                        listing = await self._detail(listing_id)
                        if listing is None or not _price_matches(
                            listing.price_eur,
                            slot.price_band,
                        ):
                            continue
                        normalized_fuel = normalize_fuel_category(listing.fuel_type)
                        if normalized_fuel != fuel:
                            continue
                        payload, missing = await asyncio.to_thread(
                            _candidate_payload,
                            listing,
                        )
                        if missing or bool(_is_fiscally_new(listing)) != slot.fiscally_new:
                            continue
                        if seller is not None and payload["seller_type"] != seller:
                            continue
                        return listing
        return None


def _read_ids(paths: list[Path]) -> set[str]:
    ids: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            ids.update(
                row["id_mobile_de"]
                for row in csv.DictReader(handle)
                if row.get("id_mobile_de")
            )
    return ids


def _validate_output(path: Path, excluded_ids: set[str]) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if reader.fieldnames != CSV_FIELDS:
        raise RuntimeError("Las columnas no coinciden con la matriz de 35")
    if len(rows) != 100:
        raise RuntimeError(f"Se esperaban 100 filas y se encontraron {len(rows)}")
    ids = [row["id_mobile_de"] for row in rows]
    if len(set(ids)) != 100 or "" in ids:
        raise RuntimeError("Los 100 IDs deben existir y ser únicos")
    overlap = set(ids) & excluded_ids
    if overlap:
        raise RuntimeError(f"Se reutilizaron IDs anteriores: {sorted(overlap)}")
    if any(row["estado"].startswith("sin_anuncio") for row in rows):
        raise RuntimeError("Las 100 filas deben corresponder a anuncios reales")


async def _main(output: Path, exclude_paths: list[Path]) -> int:
    excluded_ids = _read_ids(exclude_paths)
    selector = CandidateSelector(excluded_ids)
    market = SpanishMarketReferenceService(ttl_seconds=0)
    rows: list[dict[str, Any]] = []

    for index, slot in enumerate(_slots(), start=1):
        print(
            f"[{index:03d}/100] {slot.price_band} {slot.fuel} "
            f"{slot.seller} nuevo={slot.fiscally_new}",
            flush=True,
        )
        listing = await selector.choose(slot)
        if listing is None:
            row = _empty_row(index, slot.preferred_make, "sin candidato")
            row["estado"] = "sin_anuncio_calculable"
            row["detalle_incidencia"] = (
                f"No apareció un anuncio completo para {slot.price_band}/"
                f"{slot.fuel}/{slot.seller}/nuevo={slot.fiscally_new}"
            )
        else:
            row = await _run_target(
                test_number=index,
                make=listing.make or slot.preferred_make,
                model=listing.model or listing.title or "sin modelo",
                candidates=1,
                mobile=selector.mobile,
                market=market,
                listing_id=listing.listing_id,
            )
            if row["estado"].startswith("calculado"):
                selector.selected_ids.add(listing.listing_id)
        rows.append(row)
        _write_csv(output, rows)
        print(
            f"  -> {row['id_mobile_de']} {row['estado']} "
            f"BOE={row['boe_fila_id']} mercado={row['nivel_comparables'] or '-'}",
            flush=True,
        )

    _validate_output(output, excluded_ids)
    print(
        json.dumps(
            {
                "output": str(output.resolve()),
                "rows": len(rows),
                "unique_ids": len(selector.selected_ids),
                "excluded_previous_ids": len(excluded_ids),
                "completed_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
        )
    )
    return 0


async def _repair_particulars(output: Path, exclude_paths: list[Path]) -> int:
    excluded_ids = _read_ids(exclude_paths)
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 100:
        raise RuntimeError("La reparación exige una matriz previa de 100 filas")

    selector = CandidateSelector(excluded_ids)
    selector.selected_ids.update(row["id_mobile_de"] for row in rows)
    market = SpanishMarketReferenceService(ttl_seconds=0)
    replacements = 0
    # Las sondas incorporan el canal particular y los dos tramos de GNC. Si falta
    # CO₂, la fila se conserva como pendiente: ese es el flujo real del usuario.
    probe_indexes = {1, 11, 20, 22, 43, 64, 70}
    public_fuels = {
        "gasoline": "gasolina",
        "diesel": "diesel",
        "electric": "electrico",
        "cng": "gnc",
    }
    for index, slot in enumerate(_slots(), start=1):
        if index not in probe_indexes:
            continue
        current = rows[index - 1]
        if (
            current["combustible"] == public_fuels.get(slot.fuel, slot.fuel)
            and (
                (slot.seller == "particular" and current["tipo_vendedor"] == "particular")
                or (
                    slot.seller != "particular"
                    and current["tipo_vendedor"].startswith("profesional_")
                )
            )
        ):
            continue
        print(f"[particular {index:03d}] {slot.price_band} {slot.fuel}", flush=True)
        listing = None
        for listing_id in await selector._search(
            make=None,
            slot=slot,
            seller=slot.seller,
            fuel=slot.fuel,
        ):
            if listing_id in selector.selected_ids or listing_id in excluded_ids:
                continue
            candidate = await selector._detail(listing_id)
            if (
                candidate is not None
                and candidate.seller is not None
                and (
                    (slot.seller == "particular" and candidate.seller.type == "private")
                    or (slot.seller != "particular" and candidate.seller.type == "dealer")
                )
                and _price_matches(candidate.price_eur, slot.price_band)
                and normalize_fuel_category(candidate.fuel_type) == slot.fuel
                and not _is_fiscally_new(candidate)
            ):
                listing = candidate
                break
        if listing is None:
            print("  -> sin particular completo; se conserva la fila", flush=True)
            continue
        payload, missing = await asyncio.to_thread(_candidate_payload, listing)
        if missing:
            registration = listing.first_registration
            row = _empty_row(
                index,
                listing.make or slot.preferred_make,
                listing.model or listing.title or "sin modelo",
            )
            row.update(
                {
                    "estado": "pendiente_datos_anuncio",
                    "id_mobile_de": listing.listing_id,
                    "url_mobile_de": str(listing.url),
                    "titulo": listing.title or "",
                    "marca_extraida": listing.make or "",
                    "modelo_extraido": listing.model or "",
                    "version_extraida": listing.version or "",
                    "primera_matriculacion": (
                        f"{registration.year:04d}-{registration.month or 1:02d}"
                        if registration
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
                    "cambio": payload.get("transmission") or "",
                    "carroceria": payload.get("body_type") or "",
                    "clave_motor_matching": build_engine_key(listing),
                    "co2_g_km": payload.get("co2_gkm") or "",
                    "fuente_co2": payload.get("co2_source") or "",
                    "danado_accidentado": bool(payload.get("damaged")),
                    "detalle_incidencia": "Faltan datos: " + ", ".join(missing),
                }
            )
        else:
            row = await _run_target(
                test_number=index,
                make=listing.make or slot.preferred_make,
                model=listing.model or listing.title or "sin modelo",
                candidates=1,
                mobile=selector.mobile,
                market=market,
                listing_id=listing.listing_id,
            )
        rows[index - 1] = row
        selector.selected_ids.add(listing.listing_id)
        replacements += 1
        _write_csv(output, rows)
        print(f"  -> {listing.listing_id} incorporado ({row['estado']})", flush=True)
    _validate_output(output, excluded_ids)
    print(json.dumps({"particulares_incorporados": replacements}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/audits/validacion_real_100_nuevos_2026-08-08.csv"),
    )
    parser.add_argument(
        "--exclude-csv",
        type=Path,
        action="append",
        required=True,
    )
    parser.add_argument("--repair-particulars", action="store_true")
    args = parser.parse_args()
    target = _repair_particulars if args.repair_particulars else _main
    return asyncio.run(target(args.output, args.exclude_csv))


if __name__ == "__main__":
    sys.exit(main())
