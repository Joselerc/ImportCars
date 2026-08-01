from __future__ import annotations

from datetime import date

import pytest

from fiscal_engine import (
    Combustible,
    CostesConfig,
    Operacion,
    TipoCarroceria,
    TipoVendedor,
    Vehiculo,
    break_even_compraventa,
    calcular,
    estimar_coste_transporte,
)
from import_cars.enrichment.body_type import normalize_body_type


def vehicle(body_type: TipoCarroceria | None, *, make: str = "Marca") -> Vehiculo:
    return Vehiculo(
        marca=make,
        modelo="Modelo",
        fecha_primera_matriculacion=date(2020, 1, 1),
        precio_compra=20_000,
        combustible=Combustible.GASOLINA,
        cilindrada_cc=1_500,
        co2_gkm=130,
        valor_tablas_nuevo=30_000,
        carroceria=body_type,
    )


@pytest.mark.parametrize(
    ("body_type", "expected"),
    [
        (None, 950),
        (TipoCarroceria.TURISMO, 950),
        (TipoCarroceria.FAMILIAR, 950),
        (TipoCarroceria.OTRO, 950),
        (TipoCarroceria.SUV, 1_100),
        (TipoCarroceria.MONOVOLUMEN, 1_100),
        (TipoCarroceria.DEPORTIVO_GAMA_ALTA, 1_200),
    ],
)
def test_transport_uses_the_approved_body_type_tiers(
    body_type: TipoCarroceria | None, expected: float
) -> None:
    assert estimar_coste_transporte(vehicle(body_type), CostesConfig()) == expected


def test_transport_never_uses_the_make_to_classify_the_vehicle() -> None:
    standard = CostesConfig()
    assert estimar_coste_transporte(
        vehicle(TipoCarroceria.TURISMO, make="Ferrari"), standard
    ) == estimar_coste_transporte(
        vehicle(TipoCarroceria.TURISMO, make="Dacia"), standard
    )


def test_explicit_transport_override_is_preserved() -> None:
    costs = CostesConfig(transporte=875)
    assert estimar_coste_transporte(vehicle(TipoCarroceria.SUV), costs) == 875


def test_client_and_opportunity_finder_share_the_same_transport() -> None:
    suv = vehicle(TipoCarroceria.SUV)
    operation = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR)

    client = calcular(suv, operation, referencia=date(2026, 8, 1))
    internal = break_even_compraventa(suv, operation, referencia=date(2026, 8, 1))

    assert client.transporte == 1_100
    assert internal["costes_fijos"] >= client.transporte
    assert internal["break_even"] == pytest.approx(
        client.coste_cliente_final - client.honorarios_gestion
    )
    transport_row = next(
        row for row in client.desglose_cliente if row.clave == "transporte"
    )
    assert transport_row.importe == 1_100
    assert "SUV" in transport_row.nota


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SUV / Off-road", "suv"),
        ("Monovolumen", "monovolumen"),
        ("Sports Car / Coupé", "deportivo_gama_alta"),
        ("SportsCar", "deportivo_gama_alta"),
        ("Station wagon", "familiar"),
        ("EstateCar", "familiar"),
        ("Sedan", "turismo"),
        ("SmallCar", "turismo"),
        ("Avant", None),
        (None, None),
    ],
)
def test_portal_body_types_are_normalized_without_brand_heuristics(
    raw: str | None, expected: str | None
) -> None:
    assert normalize_body_type(raw) == expected
