"""Public, customer-facing calculation service backed only by fiscal_engine."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from fiscal_engine import (
    Combustible,
    CostesConfig,
    Operacion,
    TipoCarroceria,
    TipoVendedor,
    Vehiculo,
    calcular,
)

from ..fiscal_data import resolver_registro_valor_tablas
from ..models import NormalizedListing, Registration, Seller
from .market_reference import SpanishMarketReferenceService


class PublicCalculationInput(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    version: str | None = Field(None, max_length=160)
    first_registration: date
    purchase_price: float = Field(gt=0, le=5_000_000)
    fuel: Literal["gasolina", "diesel", "electrico", "hibrido", "phev", "glp", "otro"]
    displacement_cc: int = Field(ge=0, le=20_000)
    co2_gkm: float | None = Field(None, ge=0, le=1_000)
    mileage_km: int | None = Field(None, ge=0, le=5_000_000)
    power_kw: float | None = Field(None, ge=0, le=2_000)
    body_type: Literal[
        "turismo",
        "familiar",
        "suv",
        "monovolumen",
        "deportivo_gama_alta",
        "otro",
    ] | None = None
    cvf: float | None = Field(None, ge=0, le=200)
    seller_type: Literal["particular", "profesional_iva", "profesional_margen"]
    autonomous_community: str = Field(min_length=1, max_length=80)
    municipality: str = Field(min_length=1, max_length=120)
    co2_confirmed: bool = False

    @model_validator(mode="after")
    def validate_vehicle(self):
        if self.first_registration > datetime.now(UTC).date():
            raise ValueError("La primera matriculacion no puede estar en el futuro")
        if self.fuel != "electrico" and self.displacement_cc == 0:
            raise ValueError("La cilindrada es obligatoria para vehiculos no electricos")
        return self


class PublicCalculationResult(BaseModel):
    vehicle_label: str
    final_price_eur: float
    spanish_market_price_eur: float | None
    savings_eur: float | None
    savings_pct: float | None
    market_sample_size: int
    market_confidence: str
    market_cached: bool
    breakdown: list[dict[str, str | float]]
    warnings: list[str]
    fiscal_version: str
    boe_model_match: str | None


_FUEL_MAP = {
    "gasolina": Combustible.GASOLINA,
    "diesel": Combustible.DIESEL,
    "electrico": Combustible.ELECTRICO,
    "hibrido": Combustible.HIBRIDO,
    "phev": Combustible.HIBRIDO_ENCHUFABLE,
    "glp": Combustible.GLP,
    "otro": Combustible.OTRO,
}

_SELLER_MAP = {
    "particular": TipoVendedor.PARTICULAR,
    "profesional_iva": TipoVendedor.PROFESIONAL_IVA,
    "profesional_margen": TipoVendedor.PROFESIONAL_MARGEN,
}


def _market_target(data: PublicCalculationInput) -> NormalizedListing:
    return NormalizedListing(
        listing_id="public-calculation",
        source="manual",
        url="https://example.invalid/manual",
        scraped_at=datetime.now(UTC),
        make=data.make,
        model=data.model,
        version=data.version,
        title=" ".join(filter(None, [data.make, data.model, data.version])),
        price_eur=data.purchase_price,
        mileage_km=data.mileage_km,
        first_registration=Registration(
            year=data.first_registration.year,
            month=data.first_registration.month,
        ),
        fuel_type=data.fuel,
        power_kw=int(data.power_kw) if data.power_kw is not None else None,
        power_hp=round(data.power_kw * 1.35962) if data.power_kw is not None else None,
        engine_displacement_cc=data.displacement_cc,
        body_type=data.body_type,
        co2_original_g_km=round(data.co2_gkm) if data.co2_gkm is not None else None,
        co2_confidence=1.0 if data.co2_confirmed else 0.5 if data.co2_gkm is not None else 0.0,
        seller=Seller(type="private" if data.seller_type == "particular" else "dealer"),
    )


async def calculate_for_customer(
    data: PublicCalculationInput,
    *,
    market_service: SpanishMarketReferenceService,
) -> PublicCalculationResult:
    """Return only customer-facing totals, explanations and risk warnings."""

    target = _market_target(data)
    market = None
    market_warning = None
    try:
        market = await market_service.get_reference(target)
    except Exception:  # noqa: BLE001 - la consulta de mercado nunca invalida el calculo
        market_warning = (
            "No hemos podido consultar ahora el mercado espanol. "
            "El coste fiscal si esta calculado; reintenta para obtener el ahorro."
        )

    resolution = resolver_registro_valor_tablas(
        data.make,
        " ".join(filter(None, [data.model, data.version])),
        data.first_registration,
        displacement_cc=data.displacement_cc,
        power_kw=data.power_kw,
    )
    vehicle = Vehiculo(
        marca=data.make,
        modelo=" ".join(filter(None, [data.model, data.version])),
        fecha_primera_matriculacion=data.first_registration,
        precio_compra=data.purchase_price,
        combustible=_FUEL_MAP[data.fuel],
        cilindrada_cc=data.displacement_cc,
        co2_gkm=data.co2_gkm,
        kilometros=data.mileage_km,
        potencia_kw=data.power_kw,
        cvf=data.cvf if data.cvf is not None else resolution.fiscal_hp if resolution else None,
        valor_tablas_nuevo=resolution.value_eur if resolution else None,
        co2_confianza=1.0 if data.co2_confirmed else 0.5 if data.co2_gkm is not None else 0.0,
        carroceria=TipoCarroceria(data.body_type) if data.body_type else None,
    )
    market_price = market.median_eur if market else None
    fees = float(os.getenv("IMPORT_CARS_MANAGEMENT_FEE", "900"))
    result = calcular(
        vehicle,
        Operacion(
            tipo_vendedor=_SELLER_MAP[data.seller_type],
            comunidad_autonoma=data.autonomous_community,
            municipio=data.municipality,
        ),
        CostesConfig(honorarios_gestion=fees),
        precio_mercado_es=market_price,
    )

    warnings = list(result.avisos)
    if data.mileage_km is None:
        warnings.append(
            "El anuncio no aporta kilometraje. Confírmalo: por debajo de 6.000 km "
            "el vehículo puede tener la consideración fiscal de nuevo."
        )
    if not data.version:
        warnings.append(
            "Falta la versión o motorización exacta. Añádela para afinar la tabla "
            "del BOE y los comparables españoles."
        )
    if data.cvf is None and resolution is None:
        warnings.append(
            "La potencia fiscal no está confirmada; el IVTM se ha estimado desde la cilindrada."
        )
    if market_warning:
        warnings.append(market_warning)
    if market_price is not None and data.purchase_price < market_price * 0.55:
        warnings.append(
            "El precio del anuncio es inusualmente bajo frente al mercado espanol. "
            "Conviene verificar historial, kilometraje, danos y documentacion."
        )

    return PublicCalculationResult(
        vehicle_label=(
            f"{' '.join(filter(None, [data.make, data.model, data.version]))} "
            f"· {data.first_registration.year}"
        ),
        final_price_eur=round(result.coste_cliente_final, 2),
        spanish_market_price_eur=round(market_price, 2) if market_price is not None else None,
        savings_eur=round(result.ahorro_absoluto, 2) if result.ahorro_absoluto is not None else None,
        savings_pct=round(result.ahorro_pct, 2) if result.ahorro_pct is not None else None,
        market_sample_size=market.sample_size if market else 0,
        market_confidence=market.confidence if market else "unavailable",
        market_cached=market.cached if market else False,
        breakdown=[
            {
                "key": line.clave,
                "label": line.etiqueta,
                "amount_eur": round(line.importe, 2),
                "note": line.nota,
            }
            for line in result.desglose_cliente
        ],
        warnings=warnings,
        fiscal_version=result.version_tablas,
        boe_model_match=resolution.model_type if resolution else None,
    )


__all__ = [
    "PublicCalculationInput",
    "PublicCalculationResult",
    "calculate_for_customer",
]
