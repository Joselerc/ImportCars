"""Small, transactional and dependency-free SQLite migration runner."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Migration:
    component: str
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.component.strip():
            raise ValueError("La migración necesita un componente")
        if self.version < 1:
            raise ValueError("La versión de migración debe ser positiva")
        if not self.statements:
            raise ValueError("La migración debe contener al menos una sentencia")


_MIGRATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    component TEXT NOT NULL,
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    PRIMARY KEY (component, version)
)
"""


def apply_migrations(
    database_path: str | Path,
    *,
    component: str,
    migrations: Iterable[Migration],
) -> tuple[int, ...]:
    """Apply one component's ordered migrations exactly once."""

    ordered = sorted(migrations, key=lambda migration: migration.version)
    if any(migration.component != component for migration in ordered):
        raise ValueError("Todas las migraciones deben pertenecer al componente indicado")
    versions = [migration.version for migration in ordered]
    if len(versions) != len(set(versions)):
        raise ValueError("No puede haber versiones de migración duplicadas")

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    applied_now: list[int] = []
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(_MIGRATION_SCHEMA)
        applied = {
            int(row[0])
            for row in connection.execute(
                "SELECT version FROM schema_migrations WHERE component = ?",
                (component,),
            )
        }
        for migration in ordered:
            if migration.version in applied:
                continue
            with connection:
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (component, version, name, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        component,
                        migration.version,
                        migration.name,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            applied_now.append(migration.version)
    return tuple(applied_now)
