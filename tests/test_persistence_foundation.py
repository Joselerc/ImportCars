from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from import_cars.persistence import Migration, apply_migrations, persistence_paths


def _clear_database_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "IMPORT_CARS_DATABASE_PATH",
        "IMPORT_CARS_FISCAL_DATABASE_PATH",
        "IMPORT_CARS_CUSTOMER_DATABASE_PATH",
        "IMPORT_CARS_MARKET_DATABASE_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def test_persistence_paths_are_physically_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_database_environment(monkeypatch)
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(tmp_path / "fiscal.sqlite3"))
    monkeypatch.setenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH", str(tmp_path / "customer.sqlite3"))
    monkeypatch.setenv("IMPORT_CARS_MARKET_DATABASE_PATH", str(tmp_path / "market.sqlite3"))

    paths = persistence_paths()

    assert paths.fiscal.name == "fiscal.sqlite3"
    assert paths.customer_activity.name == "customer.sqlite3"
    assert paths.market_tracking.name == "market.sqlite3"


def test_legacy_database_path_only_aliases_the_fiscal_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_database_environment(monkeypatch)
    legacy = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("IMPORT_CARS_DATABASE_PATH", str(legacy))

    paths = persistence_paths()

    assert paths.fiscal == legacy
    assert paths.customer_activity != legacy
    assert paths.market_tracking != legacy


def test_rejects_accidentally_shared_database_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clear_database_environment(monkeypatch)
    shared = tmp_path / "shared.sqlite3"
    monkeypatch.setenv("IMPORT_CARS_FISCAL_DATABASE_PATH", str(shared))
    monkeypatch.setenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH", str(shared))
    monkeypatch.setenv("IMPORT_CARS_MARKET_DATABASE_PATH", str(tmp_path / "market.sqlite3"))

    with pytest.raises(ValueError, match="rutas distintas"):
        persistence_paths()


def test_migrations_are_ordered_versioned_and_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "component.sqlite3"
    migrations = (
        Migration(
            component="customer_activity",
            version=2,
            name="add_label",
            statements=("ALTER TABLE sample ADD COLUMN label TEXT",),
        ),
        Migration(
            component="customer_activity",
            version=1,
            name="create_sample",
            statements=("CREATE TABLE sample (id INTEGER PRIMARY KEY)",),
        ),
    )

    assert apply_migrations(
        database, component="customer_activity", migrations=migrations
    ) == (1, 2)
    assert apply_migrations(
        database, component="customer_activity", migrations=migrations
    ) == ()

    with sqlite3.connect(database) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(sample)")]
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    assert columns == ["id", "label"]
    assert versions == [(1,), (2,)]
