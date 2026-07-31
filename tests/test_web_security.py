import httpx
import pytest

from import_cars.webapp import app


@pytest.mark.asyncio
async def test_health_is_public_but_dashboard_uses_configured_basic_auth(
    monkeypatch,
) -> None:
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_USERNAME", "operador")
    monkeypatch.setenv("IMPORT_CARS_INTERNAL_PASSWORD", "clave-segura")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/health")).status_code == 200

        unauthorized = await client.get("/")
        assert unauthorized.status_code == 401
        assert unauthorized.headers["www-authenticate"] == "Basic"

        authorized = await client.get("/", auth=("operador", "clave-segura"))
        assert authorized.status_code == 200


@pytest.mark.asyncio
async def test_internal_dashboard_remains_available_on_local_test_client(
    monkeypatch,
) -> None:
    monkeypatch.delenv("IMPORT_CARS_INTERNAL_USERNAME", raising=False)
    monkeypatch.delenv("IMPORT_CARS_INTERNAL_PASSWORD", raising=False)
    transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 12345))

    async with httpx.AsyncClient(
        transport=transport, base_url="http://localhost"
    ) as client:
        assert (await client.get("/")).status_code == 200
