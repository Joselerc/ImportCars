from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from import_cars import webapp
from import_cars.persistence.customer_activity import record_calculation
from import_cars.services.admin_auth import hash_admin_password, verify_admin_password


def test_admin_passwords_use_argon2id() -> None:
    password_hash = hash_admin_password("una-clave-larga-y-segura")
    assert password_hash.startswith("$argon2id$")
    assert verify_admin_password(password_hash, "una-clave-larga-y-segura")
    assert not verify_admin_password(password_hash, "clave-incorrecta")


@pytest.mark.asyncio
async def test_admin_requires_real_session_and_renders_simulation_warning(
    tmp_path: Path, monkeypatch
) -> None:
    database = tmp_path / "activity.sqlite3"
    monkeypatch.setenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH", str(database))
    monkeypatch.setenv("IMPORT_CARS_ADMIN_USERNAME", "fundador")
    monkeypatch.setenv(
        "IMPORT_CARS_ADMIN_PASSWORD_HASH", hash_admin_password("una-clave-larga-y-segura")
    )
    monkeypatch.setenv("IMPORT_CARS_ADMIN_COOKIE_SECURE", "false")
    record_calculation(
        anonymous_id="anonymous-demo-visitor-identifier",
        request_data={"make": "Seat", "model": "León", "version": "1.5 TSI", "first_registration": "2021-01-01", "purchase_price": 18_000, "autonomous_community": "Madrid", "municipality": "Madrid"},
        public_result={"vehicle_label": "Seat León 1.5 TSI · 2021", "final_price_eur": 22_000, "spanish_market_price_eur": 24_000, "savings_eur": 2_000, "savings_pct": 8.3, "market_match_level": "near", "market_sample_size": 3, "warnings": [], "fiscal_version": "Orden HAC/1501/2025"},
        audit={"market": {"comparables": [], "savings_sanity_filter": {"applied": False}}, "boe": {"selected_row_id": 1, "co2_source": "listing"}, "vat": {}, "registration": {}, "fiscal_breakdown": []},
        simulated=True,
        database_path=database,
    )
    transport = httpx.ASGITransport(app=webapp.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=True) as client:
        protected = await client.get("/admin")
        assert protected.url.path == "/admin/login"
        assert "Inicia sesión" in protected.text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', protected.text).group(1)
        logged_in = await client.post(
            "/admin/login",
            data={"username": "fundador", "password": "una-clave-larga-y-segura", "csrf_token": csrf},
        )
        assert logged_in.url.path == "/admin"
        assert "DATOS SIMULADOS" in logged_in.text
        assert "Seat León" in logged_in.text
        assert logged_in.headers["x-frame-options"] == "DENY"
        assert "no-store" in logged_in.headers["cache-control"]
        detail_path = re.search(
            r'href="(/admin/calculations/[^"]+)"', logged_in.text
        ).group(1)
        detail = await client.get(detail_path)
        assert detail.status_code == 200
        assert "Resultado fiscal congelado" in detail.text
        assert "Comparables congelados" in detail.text


@pytest.mark.asyncio
async def test_admin_rejects_invalid_login_csrf(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("IMPORT_CARS_CUSTOMER_DATABASE_PATH", str(tmp_path / "activity.sqlite3"))
    monkeypatch.setenv("IMPORT_CARS_ADMIN_USERNAME", "fundador")
    monkeypatch.setenv("IMPORT_CARS_ADMIN_PASSWORD_HASH", hash_admin_password("una-clave-larga-y-segura"))
    monkeypatch.setenv("IMPORT_CARS_ADMIN_COOKIE_SECURE", "false")
    transport = httpx.ASGITransport(app=webapp.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/admin/login",
            data={"username": "fundador", "password": "una-clave-larga-y-segura", "csrf_token": "wrong"},
        )
    assert response.status_code == 403
