"""Central paths for the three deliberately independent SQLite systems."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FISCAL_DATABASE_PATH = PROJECT_ROOT / "data" / "import_cars.sqlite3"
DEFAULT_CUSTOMER_DATABASE_PATH = PROJECT_ROOT / "data" / "customer_activity.sqlite3"
DEFAULT_MARKET_DATABASE_PATH = PROJECT_ROOT / "data" / "market_tracking.sqlite3"


@dataclass(frozen=True, slots=True)
class PersistencePaths:
    """Physical databases kept separate even when one process reads all three."""

    fiscal: Path
    customer_activity: Path
    market_tracking: Path

    def validate_separation(self) -> None:
        resolved = {
            self.fiscal.resolve(),
            self.customer_activity.resolve(),
            self.market_tracking.resolve(),
        }
        if len(resolved) != 3:
            raise ValueError("Las tres bases SQLite deben usar rutas distintas")


def fiscal_database_path() -> Path:
    configured = os.getenv("IMPORT_CARS_FISCAL_DATABASE_PATH")
    legacy = os.getenv("IMPORT_CARS_DATABASE_PATH")
    return Path(configured or legacy or DEFAULT_FISCAL_DATABASE_PATH)


def customer_database_path() -> Path:
    configured = os.getenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH")
    return Path(configured or DEFAULT_CUSTOMER_DATABASE_PATH)


def market_database_path() -> Path:
    configured = os.getenv("IMPORT_CARS_MARKET_DATABASE_PATH")
    return Path(configured or DEFAULT_MARKET_DATABASE_PATH)


def persistence_paths() -> PersistencePaths:
    paths = PersistencePaths(
        fiscal=fiscal_database_path(),
        customer_activity=customer_database_path(),
        market_tracking=market_database_path(),
    )
    paths.validate_separation()
    return paths
