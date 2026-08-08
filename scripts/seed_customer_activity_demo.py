"""Create unmistakably simulated C1 records for local visual review."""

from __future__ import annotations

import argparse
import random
import sqlite3

from import_cars.persistence import customer_database_path
from import_cars.persistence.customer_activity import record_calculation

VEHICLES = (
    ("Volkswagen", "Golf", "2.0 TDI Style", 18_900, 23_650, "exact", 8),
    ("Seat", "León", "1.5 eTSI FR", 22_400, 25_900, "near", 5),
    ("BMW", "320d", "M Sport", 27_500, 34_200, "exact", 11),
    ("Audi", "A4", "40 TDI S line", 29_800, 35_100, "near", 4),
    ("Mercedes-Benz", "Clase C", "C 220 d", 31_200, 37_900, "exact", 7),
    ("Toyota", "Corolla", "2.0 Hybrid", 24_600, 27_300, "broad", 3),
    ("Hyundai", "Tucson", "1.6 T-GDI HEV", 27_100, 31_400, "near", 6),
    ("Cupra", "Formentor", "1.5 TSI", 25_900, 30_200, "exact", 9),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=16)
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    path = customer_database_path()
    if args.clear and path.exists():
        with sqlite3.connect(path) as connection:
            connection.execute("DELETE FROM public_leads WHERE simulated = 1")
            connection.execute("DELETE FROM customer_calculations WHERE simulated = 1")
    random.seed(41)
    for index in range(max(0, args.count)):
        make, model, version, purchase, market, level, sample = VEHICLES[index % len(VEHICLES)]
        final = purchase + random.choice((3_900, 4_200, 4_650))
        savings = market - final
        comparable_price = market + random.choice((-700, -250, 0, 350, 800))
        record_calculation(
            anonymous_id=f"demo-anonymous-visitor-{index:04d}",
            request_data={
                "make": make,
                "model": model,
                "version": version,
                "first_registration": "2021-05-01",
                "purchase_price": purchase,
                "autonomous_community": random.choice(("Madrid", "Cataluña", "Andalucía", "Valencia")),
                "municipality": "Dato simulado",
            },
            public_result={
                "vehicle_label": f"{make} {model} {version} · 2021",
                "final_price_eur": final,
                "spanish_market_price_eur": market,
                "savings_eur": savings,
                "savings_pct": round(savings / market * 100, 2),
                "market_match_level": level,
                "market_sample_size": sample,
                "warnings": [] if level != "broad" else ["Ahorro orientativo: comparables amplios."],
                "fiscal_version": "Orden HAC/1501/2025",
            },
            audit={
                "market": {
                    "comparables": [{
                        "listing_id": f"demo-es-{index}", "source": "coches_net" if index % 2 else "autoscout24",
                        "title": f"{make} {model} {version}", "url": "https://example.invalid/anuncio-simulado",
                        "price_eur": comparable_price, "mileage_km": 72_000 + index * 1_100,
                        "year": 2021, "version": version, "fuel": "diesel" if "d" in version.casefold() else "gasolina",
                        "transmission": "automatic", "battery_capacity_kwh": None,
                        "match_level": level, "used_for_price": True, "checks": [],
                    }],
                    "savings_sanity_filter": {"applied": False},
                },
                "boe": {"selected_row_id": 10_000 + index, "confidence": "alta", "technical_candidate_count": 1, "co2_value_gkm": 129, "co2_source": "listing"},
                "vat": {"case": "usado_profesional", "reason": "Vehículo usado con factura", "tax_base_eur": 0, "spanish_vat_eur": 0},
                "registration": {"source": "listing"},
                "fiscal_breakdown": [{"key": "transporte", "label": "Transporte profesional", "amount_eur": 950, "formula": "Tarifa por carrocería", "intermediates": []}],
            },
            source_url="https://example.invalid/anuncio-alemania-simulado",
            simulated=True,
        )
    print(f"Creados {max(0, args.count)} cálculos simulados en {path}")


if __name__ == "__main__":
    main()
