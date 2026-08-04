from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, sync_playwright

from import_cars.webapp import app


@pytest.fixture(scope="module")
def calculator_server() -> Iterator[str]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        raise RuntimeError("El servidor de prueba no arrancó")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


def _audit_payload(selected_row_id: int = 101) -> dict:
    candidates = [
        {
            "row_id": 101,
            "model_type": "5008 1.6 THP S&S Allure Aut.",
            "value_eur": 24_300,
            "commercial_start": 2017,
            "commercial_end": 2018,
            "displacement_cc": 1598,
            "cylinders": 4,
            "fuel_code": "G",
            "power_kw": 121,
            "power_cv": 165,
            "fiscal_hp": 11.64,
            "text_score": 0.84,
            "transmission_kind": "automatic",
            "transmission_compatible": True,
            "cylinders_compatible": True,
            "selected": selected_row_id == 101,
            "decision": "Elegida por similitud." if selected_row_id == 101 else "Candidata técnica.",
        },
        {
            "row_id": 202,
            "model_type": "5008 1.6 THP S&S GT Line Aut.",
            "value_eur": 26_100,
            "commercial_start": 2017,
            "commercial_end": 2018,
            "displacement_cc": 1598,
            "cylinders": 4,
            "fuel_code": "G",
            "power_kw": 121,
            "power_cv": 165,
            "fiscal_hp": 11.64,
            "text_score": 0.81,
            "transmission_kind": "automatic",
            "transmission_compatible": True,
            "cylinders_compatible": True,
            "selected": selected_row_id == 202,
            "decision": "Seleccionada manualmente por el auditor."
            if selected_row_id == 202
            else "Candidata técnica.",
        },
    ]
    return {
        "vehicle_label": "Peugeot 5008 1.6 THP Allure GT-Line · 2017",
        "final_price_eur": 19_675,
        "spanish_market_price_eur": None,
        "savings_eur": None,
        "savings_pct": None,
        "market_sample_size": 0,
        "market_confidence": "unavailable",
        "market_cached": False,
        "breakdown": [
            {"key": "iedmt", "label": "Impuesto de matriculación", "amount_eur": 633, "note": "133 g/km"},
            {"key": "ivtm", "label": "IVTM", "amount_eur": 17, "note": ""},
        ],
        "warnings": [],
        "fiscal_version": "Orden HAC/1501/2025",
        "boe_model_match": next(
            row["model_type"] for row in candidates if row["selected"]
        ),
        "boe_confidence": "manual" if selected_row_id == 202 else "non_conclusive",
        "audit": {
            "market": {
                "source": "coches_net",
                "match_level": None,
                "sample_size": 0,
                "average_eur": None,
                "median_eur": None,
                "minimum_eur": None,
                "maximum_eur": None,
                "confidence": "unavailable",
                "cached": False,
                "quality_warning": None,
                "criteria": [],
                "comparables": [],
            },
            "boe": {
                "query": "5008 1.6 THP Allure GT-LINE",
                "brand": "PEUGEOT",
                "year": 2017,
                "base_candidate_count": 53,
                "technical_candidate_count": 4,
                "transmission_candidate_count": 4,
                "confidence": "manual" if selected_row_id == 202 else "non_conclusive",
                "price_spread_pct": 13.58,
                "warning": "Identificación no concluyente.",
                "missing_technical_fields": [],
                "co2_value_gkm": 133,
                "co2_source": "listing",
                "selected_row_id": selected_row_id,
                "candidates": candidates,
            },
            "vat": {
                "case": "usado_profesional_margen",
                "reason": "Vehículo usado sin IVA español adicional.",
                "fiscal_condition": "usado",
                "seller_type": "profesional_margen",
                "buyer_type": "particular",
                "gross_price_eur": 16_750,
                "advertised_net_price_eur": None,
                "vat_deductible": False,
                "tax_base_eur": 0,
                "tax_base_source": "sin_iva_espanol_usado",
                "spanish_vat_eur": 0,
                "acquisition_price_eur": 16_750,
            },
            "registration": {
                "value": "2017-01-01",
                "source": "listing",
                "reason": "Fecha extraída del anuncio.",
            },
            "fiscal_breakdown": [
                {
                    "key": "iedmt",
                    "label": "Impuesto de matriculación",
                    "amount_eur": 633,
                    "formula": "Base imponible × tipo IEDMT",
                    "intermediates": [
                        {"key": "base", "label": "Base imponible", "value": 13_326, "unit": "EUR", "note": ""}
                    ],
                },
                {
                    "key": "ivtm",
                    "label": "IVTM",
                    "amount_eur": 17,
                    "formula": "Cuota municipal prorrateada",
                    "intermediates": [],
                },
            ],
        },
    }


def test_audit_rows_expand_and_boe_candidate_recalculates(
    calculator_server: str,
    browser: Browser,
) -> None:
    page = browser.new_page()
    requests: list[dict] = []

    def calculate_route(route) -> None:
        request = route.request.post_data_json or {}
        requests.append(request)
        selected = int(request.get("boe_row_id_override") or 101)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_audit_payload(selected)),
        )

    page.route("**/api/internal/calculate-audit", calculate_route)
    page.goto(f"{calculator_server}/calculadora?audit=1")
    assert page.url.endswith("/calculadora/auditoria")
    page.get_by_role("tab", name="Meter datos a mano").click()
    page.locator("#manual-submit").click()

    expandable = page.locator('details[data-audit-expandable="true"]')
    assert expandable.count() == 2
    expandable.first.locator("summary").click()
    assert expandable.first.get_attribute("open") is not None
    assert "Base imponible × tipo IEDMT" in expandable.first.inner_text()

    selector = page.locator('.boe-select[data-boe-row-id="202"]')
    assert selector.is_visible()
    selector.click()
    page.wait_for_function("() => document.querySelector('.boe-select[data-boe-row-id=\"202\"]')?.disabled")
    assert requests[-1]["boe_row_id_override"] == 202
    page.close()


def test_damage_warning_coexists_with_missing_co2_prompt(
    calculator_server: str,
    browser: Browser,
) -> None:
    page: Page = browser.new_page()
    listing = {
        "source": "mobile_de",
        "source_url": "https://www.mobile.de/details.html?id=damaged-missing-co2",
        "title": "BMW X5 xDrive30d",
        "make": "BMW",
        "model": "X5",
        "version": "xDrive30d",
        "first_registration": "2017-04-01",
        "registration_source": "listing",
        "purchase_price": 18_900,
        "purchase_price_net": None,
        "vat_deductible": False,
        "unregistered_new": False,
        "fuel": "diesel",
        "displacement_cc": 2_993,
        "cylinders": 6,
        "co2_gkm": None,
        "mileage_km": 120_000,
        "power_kw": 190,
        "body_type": "suv",
        "transmission": "automatic",
        "seller_type": "profesional_margen",
        "co2_confirmed": False,
        "co2_source": None,
        "damaged": True,
        "damage_condition": "Ocasión, Vehículo accidentado",
        "missing_fields": ["co2_gkm"],
        "co2_prompt": "No encontramos el CO₂ para BMW X5 xDrive30d 2017. Introdúcelo en g/km.",
        "registration_prompt": None,
        "risk_warnings": [
            "ATENCIÓN: el anuncio marca el vehículo como dañado o accidentado."
        ],
    }
    page.route(
        "**/api/public/parse-listing",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(listing),
        ),
    )
    page.goto(f"{calculator_server}/calculadora")
    page.locator("#urlInput").fill(listing["source_url"])
    page.locator("#url-submit").click()

    assert "No encontramos el CO₂" in page.locator("#manual-status").inner_text()
    warning_box = page.locator("#preflight-risk-box")
    assert warning_box.is_visible()
    assert "dañado o accidentado" in warning_box.inner_text()
    page.close()
