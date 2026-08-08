from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Browser, Page, expect, sync_playwright

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
        "spanish_market_price_eur": 24_000,
        "savings_eur": 4_325,
        "savings_pct": 18.02,
        "market_sample_size": 1,
        "market_match_level": "near",
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
                "source": "coches_net+autoscout24",
                "match_level": "near",
                "sample_size": 1,
                "average_eur": 24_000,
                "median_eur": 24_000,
                "minimum_eur": 24_000,
                "maximum_eur": 24_000,
                "confidence": "medium",
                "cached": False,
                "quality_warning": None,
                "savings_sanity_filter": {
                    "applied": False,
                    "threshold_pct": 35,
                    "calculated_savings_eur": 4325,
                    "calculated_savings_pct": 18.02,
                },
                "criteria": [],
                "comparables": [
                    {
                        "listing_id": "es-market-1",
                        "source": "autoscout24",
                        "title": "PEUGEOT 5008 GTLine 1.6L THP EAT6",
                        "url": "https://www.autoscout24.es/anuncios/peugeot-5008-es-market-1",
                        "price_eur": 24_000,
                        "mileage_km": 99_500,
                        "year": 2018,
                        "version": "GTLine 1.6L THP EAT6",
                        "fuel": "Gasolina",
                        "transmission": "automatic",
                        "power_hp": 165,
                        "displacement_cc": 1598,
                        "battery_capacity_kwh": None,
                        "match_level": "near",
                        "used_for_price": True,
                        "checks": [
                            {
                                "key": "version",
                                "label": "Motorización / versión",
                                "target_value": "1600:thp",
                                "comparable_value": "1600:thp",
                                "status": "used",
                                "outcome": "match",
                                "note": "Motorización THP coincidente.",
                            },
                            {
                                "key": "mileage",
                                "label": "Kilómetros",
                                "target_value": 82_500,
                                "comparable_value": 99_500,
                                "status": "used",
                                "outcome": "match",
                                "note": "Diferencia de 17.000 km; nivel near.",
                            },
                            {
                                "key": "transmission",
                                "label": "Cambio",
                                "target_value": "automatic",
                                "comparable_value": "automatic",
                                "status": "used",
                                "outcome": "match",
                                "note": "Mismo tipo de cambio.",
                            },
                        ],
                    }
                ],
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
    expect(expandable).to_have_count(2)
    expandable.first.locator("summary").click()
    assert expandable.first.get_attribute("open") is not None
    assert "Base imponible × tipo IEDMT" in expandable.first.inner_text()

    market_comparable = page.locator("#audit-comparables details").first
    market_comparable.locator("summary").click()
    assert "COINCIDE" in market_comparable.inner_text()
    assert "Diferencia de 17.000 km" in market_comparable.inner_text()
    assert "AutoScout24" in market_comparable.inner_text()
    assert "Batería" in market_comparable.inner_text()
    assert "Filtro de cordura" in page.locator("#audit-summary").inner_text()
    assert "nivel cercano" in page.locator("#r_es").inner_text()

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

    expect(page.locator("#manual-status")).to_contain_text("No encontramos el CO₂")
    warning_box = page.locator("#preflight-risk-box")
    assert warning_box.is_visible()
    assert "dañado o accidentado" in warning_box.inner_text()
    page.close()


def test_url_flow_preserves_battery_capacity_for_market_matching(
    calculator_server: str,
    browser: Browser,
) -> None:
    page: Page = browser.new_page()
    listing = {
        "source": "mobile_de",
        "source_url": "https://suchen.mobile.de/auto-inserat/kia-ev3/460264044.html",
        "title": "Kia EV3 Earth Long Range",
        "make": "Kia",
        "model": "EV3",
        "version": "Earth Long Range",
        "first_registration": "2025-04",
        "registration_source": "listing",
        "purchase_price": 35_000,
        "purchase_price_net": None,
        "vat_deductible": False,
        "unregistered_new": False,
        "fuel": "electrico",
        "displacement_cc": 0,
        "cylinders": None,
        "co2_gkm": 0,
        "mileage_km": 12_000,
        "power_kw": 150,
        "battery_capacity_kwh": 81.4,
        "body_type": "suv",
        "transmission": "automatic",
        "seller_type": "profesional_margen",
        "co2_confirmed": True,
        "co2_source": "electric_zero",
        "damaged": False,
        "damage_condition": None,
        "missing_fields": [],
        "co2_prompt": None,
        "registration_prompt": None,
        "risk_warnings": [],
    }
    page.route(
        "**/api/public/parse-listing",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(listing),
        ),
    )

    def calculate_route(route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_audit_payload()),
        )

    page.route("**/api/public/calculate", calculate_route)
    page.goto(f"{calculator_server}/calculadora")
    page.locator("#urlInput").fill(listing["source_url"])
    with page.expect_request("**/api/public/calculate") as request_info:
        page.locator("#url-submit").click()

    assert request_info.value.post_data_json["battery_capacity_kwh"] == 81.4
    page.close()
