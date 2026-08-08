"""Reproduce the original coches.net pools behind the five extreme savings."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from statistics import median

from import_cars.analysis import match_decision, preferred_level_matches
from import_cars.scrapers.coches_net import CochesNetScraper
from import_cars.scrapers.mobile_de_http import MobileDeHttpScraper
from import_cars.services.market_reference import SpanishMarketReferenceService

TARGET_IDS = (
    "443938979",  # Ford Focus
    "460264044",  # Kia EV3
    "438551969",  # Hyundai Tucson
    "453730130",  # Cupra Tavascan
    "414176502",  # Toyota Proace
)

FIELDS = (
    "target_id",
    "target_url",
    "target_title",
    "target_model",
    "target_version",
    "target_price_gross_eur",
    "target_price_net_eur",
    "target_year",
    "target_km",
    "target_fuel",
    "target_transmission",
    "target_power_hp",
    "target_displacement_cc",
    "match_level",
    "market_sample_size",
    "market_minimum_eur",
    "market_median_eur",
    "market_maximum_eur",
    "comparable_id",
    "source",
    "used_for_price",
    "comparable_title",
    "price_eur",
    "km",
    "year",
    "version",
    "fuel",
    "transmission",
    "power_hp",
    "displacement_cc",
    "url",
)


def _quartile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


async def run(output: Path) -> dict[str, dict[str, object]]:
    mobile = MobileDeHttpScraper()
    scraper = CochesNetScraper()
    rows: list[dict[str, object]] = []
    summary: dict[str, dict[str, object]] = {}
    for target_id in TARGET_IDS:
        target = await asyncio.to_thread(mobile.get_listing, target_id)
        if target is None:
            raise RuntimeError(f"No se pudo recuperar el anuncio {target_id}")
        filters = SpanishMarketReferenceService._build_filters(target)
        result = await scraper.search(query=filters, limit=filters.page_size)
        buckets = {"exact": [], "near": [], "broad": []}
        for candidate in result.listings:
            decision = match_decision(target, candidate)
            if decision.level:
                buckets[decision.level].append((candidate, decision))
        selected_level = next(
            (level for level in ("exact", "near", "broad") if buckets[level]),
            None,
        )
        selected = buckets[selected_level] if selected_level else []
        used = preferred_level_matches(selected, selected_level) if selected_level else []
        prices = [item.price_eur for item, _decision in used if item.price_eur is not None]
        used_ids = {item.listing_id for item, _decision in used}
        q1 = _quartile(prices, 0.25)
        q3 = _quartile(prices, 0.75)
        iqr = q3 - q1
        outliers = [
            price
            for price in prices
            if price < q1 - 1.5 * iqr or price > q3 + 1.5 * iqr
        ]
        summary[target_id] = {
            "title": target.title,
            "level": selected_level,
            "count": len(prices),
            "minimum": min(prices),
            "median": median(prices),
            "maximum": max(prices),
            "q1": q1,
            "q3": q3,
            "iqr_outliers": outliers,
        }
        for comparable, _decision in selected:
            registration = comparable.first_registration
            rows.append(
                {
                    "target_id": target_id,
                    "target_url": str(target.url),
                    "target_title": target.title,
                    "target_model": target.model,
                    "target_version": target.version,
                    "target_price_gross_eur": target.price_eur,
                    "target_price_net_eur": target.price_net_eur,
                    "target_year": target.first_registration.year,
                    "target_km": target.mileage_km,
                    "target_fuel": target.fuel_type,
                    "target_transmission": target.transmission,
                    "target_power_hp": target.power_hp,
                    "target_displacement_cc": target.engine_displacement_cc,
                    "match_level": selected_level,
                    "market_sample_size": len(prices),
                    "market_minimum_eur": min(prices),
                    "market_median_eur": median(prices),
                    "market_maximum_eur": max(prices),
                    "comparable_id": comparable.listing_id,
                    "source": comparable.source,
                    "used_for_price": comparable.listing_id in used_ids,
                    "comparable_title": comparable.title,
                    "price_eur": comparable.price_eur,
                    "km": comparable.mileage_km,
                    "year": registration.year if registration else comparable.production_year,
                    "version": comparable.version or comparable.title,
                    "fuel": comparable.fuel_type,
                    "transmission": comparable.transmission,
                    "power_hp": comparable.power_hp,
                    "displacement_cc": comparable.engine_displacement_cc,
                    "url": comparable.url,
                }
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/audits/diagnostico_ahorros_extremos_2026-08-08.csv"),
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.output)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
