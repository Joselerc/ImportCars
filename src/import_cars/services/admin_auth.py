"""Argon2id-backed administrator authentication and opaque sessions."""

from __future__ import annotations

import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from ..persistence import customer_database_path
from ..persistence.customer_activity import (
    hash_session_token,
    initialize_customer_database,
)

password_hasher = PasswordHasher()


class AdminConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdminSession:
    username: str
    csrf_token: str
    expires_at: datetime


def hash_admin_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    return password_hasher.hash(password)


def verify_admin_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _connection(database_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(database_path) if database_path is not None else customer_database_path()
    initialize_customer_database(path)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def sync_founder_from_environment(*, database_path: str | Path | None = None) -> None:
    username = os.getenv("IMPORT_CARS_ADMIN_USERNAME", "").strip().casefold()
    password_hash = os.getenv("IMPORT_CARS_ADMIN_PASSWORD_HASH", "").strip()
    if not username or not password_hash:
        raise AdminConfigurationError(
            "Configura IMPORT_CARS_ADMIN_USERNAME e IMPORT_CARS_ADMIN_PASSWORD_HASH."
        )
    if not password_hash.startswith("$argon2id$"):
        raise AdminConfigurationError("El hash del administrador debe usar Argon2id.")
    now = datetime.now(UTC).isoformat()
    with _connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO admin_users (username, password_hash, active, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                active = 1,
                updated_at = excluded.updated_at
            """,
            (username, password_hash, now, now),
        )


def authenticate(
    username: str,
    password: str,
    *,
    database_path: str | Path | None = None,
) -> tuple[str, AdminSession] | None:
    sync_founder_from_environment(database_path=database_path)
    normalized = username.strip().casefold()
    now = datetime.now(UTC)
    with _connection(database_path) as connection:
        security = connection.execute(
            "SELECT * FROM admin_login_security WHERE username = ?", (normalized,)
        ).fetchone()
        if security and security["locked_until"]:
            locked_until = datetime.fromisoformat(security["locked_until"])
            if locked_until > now:
                return None
        user = connection.execute(
            "SELECT * FROM admin_users WHERE username = ? AND active = 1", (normalized,)
        ).fetchone()
        valid = bool(user) and verify_admin_password(user["password_hash"], password)
        if not valid:
            attempts = int(security["failed_attempts"] if security else 0) + 1
            locked_until = now + timedelta(minutes=15) if attempts >= 5 else None
            connection.execute(
                """
                INSERT INTO admin_login_security (username, failed_attempts, locked_until, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    failed_attempts = excluded.failed_attempts,
                    locked_until = excluded.locked_until,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized,
                    attempts,
                    locked_until.isoformat() if locked_until else None,
                    now.isoformat(),
                ),
            )
            return None
        connection.execute(
            "DELETE FROM admin_login_security WHERE username = ?", (normalized,)
        )
        token = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        hours = max(1, min(int(os.getenv("IMPORT_CARS_ADMIN_SESSION_HOURS", "12")), 72))
        expires = now + timedelta(hours=hours)
        connection.execute(
            "DELETE FROM admin_sessions WHERE expires_at <= ?", (now.isoformat(),)
        )
        connection.execute(
            """
            INSERT INTO admin_sessions (
                token_hash, user_id, csrf_token, created_at, expires_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                hash_session_token(token),
                user["id"],
                csrf_token,
                now.isoformat(),
                expires.isoformat(),
                now.isoformat(),
            ),
        )
    return token, AdminSession(normalized, csrf_token, expires)


def get_session(
    token: str | None, *, database_path: str | Path | None = None
) -> AdminSession | None:
    if not token:
        return None
    now = datetime.now(UTC)
    with _connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT u.username, s.csrf_token, s.expires_at
            FROM admin_sessions s JOIN admin_users u ON u.id = s.user_id
            WHERE s.token_hash = ? AND u.active = 1
            """,
            (hash_session_token(token),),
        ).fetchone()
        if not row:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        if expires <= now:
            connection.execute(
                "DELETE FROM admin_sessions WHERE token_hash = ?",
                (hash_session_token(token),),
            )
            return None
        connection.execute(
            "UPDATE admin_sessions SET last_seen_at = ? WHERE token_hash = ?",
            (now.isoformat(), hash_session_token(token)),
        )
    return AdminSession(row["username"], row["csrf_token"], expires)


def revoke_session(token: str | None, *, database_path: str | Path | None = None) -> None:
    if not token:
        return
    with _connection(database_path) as connection:
        connection.execute(
            "DELETE FROM admin_sessions WHERE token_hash = ?", (hash_session_token(token),)
        )


__all__ = [
    "AdminConfigurationError",
    "AdminSession",
    "authenticate",
    "get_session",
    "hash_admin_password",
    "revoke_session",
    "sync_founder_from_environment",
    "verify_admin_password",
]
