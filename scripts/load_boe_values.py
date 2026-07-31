"""Download and install an official annual BOE vehicle-value dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from import_cars.fiscal_data import DEFAULT_BOE_XML_URL, load_boe_year


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carga los anexos I y IV de una orden anual del BOE en SQLite."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("data/import_cars.sqlite3"),
        help="Ruta de la base SQLite local.",
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_BOE_XML_URL,
        help="URL XML oficial de la orden anual en boe.es.",
    )
    parser.add_argument(
        "--exercise",
        type=int,
        default=2026,
        help="Ejercicio esperado; evita cargar por error otro ano.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    summary = load_boe_year(
        args.database,
        source_url=args.url,
        expected_exercise=args.exercise,
        timeout=args.timeout,
    )
    print(
        f"Cargada {summary.order_code} (ejercicio {summary.exercise}): "
        f"{summary.vehicle_count} vehiculos, "
        f"{summary.generic_band_count} tramos genericos y "
        f"{summary.depreciation_band_count} tramos de depreciacion."
    )


if __name__ == "__main__":
    main()
