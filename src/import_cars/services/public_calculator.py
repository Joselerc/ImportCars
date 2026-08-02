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

from ..fiscal_data import resolver_diagnostico_valor_tablas
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
    cylinders: int | None = Field(None, ge=1, le=24)
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
    transmission: Literal["manual", "automatic", "semi_automatic"] | None = None
    cvf: float | None = Field(None, ge=0, le=200)
    seller_type: Literal["particular", "profesional_iva", "profesional_margen"]
    autonomous_community: str = Field(min_length=1, max_length=80)
    municipality: str = Field(min_length=1, max_length=120)
    co2_confirmed: bool = False
    damaged: bool = False
    damage_condition: str | None = Field(None, max_length=160)

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
    boe_confidence: str


class AuditCalculationInput(PublicCalculationInput):
    boe_row_id_override: int | None = Field(None, ge=1)


class FiscalAuditLine(BaseModel):
    key: str
    label: str
    amount_eur: float
    formula: str
    intermediates: list[dict[str, str | int | float | bool | None]]


class CalculationAudit(BaseModel):
    market: dict
    boe: dict
    fiscal_breakdown: list[FiscalAuditLine]


class AuditCalculationResult(PublicCalculationResult):
    audit: CalculationAudit


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

_BOE_FUEL_CODES = {
    "gasolina": "G",
    "diesel": "D",
    "electrico": "Elc",
    "hibrido": "H",
    "phev": "H",
    "glp": "GLP",
    "otro": "Otro",
}


def _effective_co2(data: PublicCalculationInput) -> float | None:
    """Pure battery-electric vehicles have guaranteed zero tailpipe CO2."""

    return 0.0 if data.fuel == "electrico" else data.co2_gkm


def _market_target(data: PublicCalculationInput) -> NormalizedListing:
    co2 = _effective_co2(data)
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
        cylinders=data.cylinders,
        body_type=data.body_type,
        transmission=data.transmission,
        co2_original_g_km=round(co2) if co2 is not None else None,
        co2_confidence=(
            1.0
            if data.fuel == "electrico" or data.co2_confirmed
            else 0.5
            if co2 is not None
            else 0.0
        ),
        seller=Seller(type="private" if data.seller_type == "particular" else "dealer"),
    )


async def _calculate(
    data: PublicCalculationInput,
    *,
    market_service: SpanishMarketReferenceService,
    include_audit: bool,
    selected_boe_row_id: int | None = None,
) -> PublicCalculationResult | AuditCalculationResult:
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

    boe_audit = resolver_diagnostico_valor_tablas(
        data.make,
        " ".join(filter(None, [data.model, data.version])),
        data.first_registration,
        displacement_cc=data.displacement_cc,
        power_kw=data.power_kw,
        fuel_code=_BOE_FUEL_CODES[data.fuel],
        cylinders=data.cylinders,
        transmission=data.transmission,
        selected_row_id=selected_boe_row_id,
    )
    resolution = boe_audit.resolution
    effective_co2 = _effective_co2(data)
    vehicle = Vehiculo(
        marca=data.make,
        modelo=" ".join(filter(None, [data.model, data.version])),
        fecha_primera_matriculacion=data.first_registration,
        precio_compra=data.purchase_price,
        combustible=_FUEL_MAP[data.fuel],
        cilindrada_cc=data.displacement_cc,
        co2_gkm=effective_co2,
        kilometros=data.mileage_km,
        potencia_kw=data.power_kw,
        cvf=data.cvf if data.cvf is not None else resolution.fiscal_hp if resolution else None,
        valor_tablas_nuevo=resolution.value_eur if resolution else None,
        co2_confianza=(
            1.0
            if data.fuel == "electrico" or data.co2_confirmed
            else 0.5
            if effective_co2 is not None
            else 0.0
        ),
        carroceria=TipoCarroceria(data.body_type) if data.body_type else None,
        boe_fila_id=resolution.row_id if resolution else None,
        boe_orden=resolution.order_code if resolution else None,
        boe_ejercicio=resolution.exercise if resolution else None,
        boe_modelo_resuelto=resolution.model_type if resolution else None,
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
    if boe_audit.warning:
        warnings.append(boe_audit.warning)
    if resolution is None:
        warnings.append(
            "ATENCIÓN: no se ha encontrado ninguna fila técnicamente compatible en el BOE. "
            "El valor como nuevo se ha estimado desde el precio del anuncio; confirma la "
            "versión antes de usar este cálculo en un presupuesto formal."
        )
    if data.mileage_km is None:
        warnings.append(
            "El anuncio no aporta kilometraje. Confírmalo: por debajo de 6.000 km "
            "el vehículo puede tener la consideración fiscal de nuevo."
        )
    if data.damaged:
        detail = f" ({data.damage_condition})" if data.damage_condition else ""
        warnings.append(
            "ATENCIÓN: el anuncio marca el vehículo como dañado o accidentado"
            f"{detail}. El cálculo se mantiene, pero revisa el alcance de los daños "
            "y solicita una inspección antes de comprar."
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
    if market and 0 < market.sample_size < 3:
        warnings.append(
            f"Comparación orientativa: solo hay {market.sample_size} "
            f"{'comparable' if market.sample_size == 1 else 'comparables'} disponible"
            ". Revisa los anuncios antes de valorar el ahorro como definitivo."
        )
    if market_price is not None and data.purchase_price < market_price * 0.55:
        warnings.append(
            "El precio del anuncio es inusualmente bajo frente al mercado espanol. "
            "Conviene verificar historial, kilometraje, danos y documentacion."
        )

    public_result = PublicCalculationResult(
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
        boe_confidence=boe_audit.confidence_label,
    )
    if not include_audit:
        return public_result

    return AuditCalculationResult(
        **public_result.model_dump(),
        audit=CalculationAudit(
            market={
                "source": market.source if market else "coches_net",
                "match_level": market.match_level if market else None,
                "sample_size": market.sample_size if market else 0,
                "average_eur": market.average_eur if market else None,
                "median_eur": market.median_eur if market else None,
                "minimum_eur": market.minimum_eur if market else None,
                "maximum_eur": market.maximum_eur if market else None,
                "confidence": market.confidence if market else "unavailable",
                "cached": market.cached if market else False,
                "quality_warning": (
                    "Comparación orientativa: hay muy pocos comparables."
                    if market and 0 < market.sample_size < 3
                    else None
                ),
                "criteria": [
                    criterion.model_dump(mode="json")
                    for criterion in market.criteria
                ] if market else [],
                "comparables": [
                    comparable.model_dump(mode="json")
                    for comparable in market.comparables
                ] if market else [],
            },
            boe={
                "query": boe_audit.query,
                "brand": boe_audit.normalized_brand,
                "year": boe_audit.year,
                "base_candidate_count": boe_audit.base_candidate_count,
                "technical_candidate_count": boe_audit.technical_candidate_count,
                "transmission_candidate_count": boe_audit.transmission_candidate_count,
                "confidence": boe_audit.confidence_label,
                "price_spread_pct": boe_audit.price_spread_pct,
                "warning": boe_audit.warning,
                "missing_technical_fields": list(boe_audit.missing_technical_fields),
                "selected_row_id": resolution.row_id if resolution else None,
                "candidates": [
                    {
                        "row_id": candidate.row_id,
                        "model_type": candidate.model_type,
                        "value_eur": candidate.value_eur,
                        "commercial_start": candidate.commercial_start,
                        "commercial_end": candidate.commercial_end,
                        "displacement_cc": candidate.displacement_cc,
                        "cylinders": candidate.cylinders,
                        "fuel_code": candidate.fuel_code,
                        "power_kw": candidate.power_kw,
                        "power_cv": candidate.power_cv,
                        "fiscal_hp": candidate.fiscal_hp,
                        "text_score": candidate.text_score,
                        "transmission_kind": candidate.transmission_kind,
                        "transmission_compatible": candidate.transmission_compatible,
                        "cylinders_compatible": candidate.cylinders_compatible,
                        "selected": candidate.selected,
                        "decision": candidate.decision,
                    }
                    for candidate in boe_audit.candidates
                ],
            },
            fiscal_breakdown=[
                FiscalAuditLine(
                    key=line.clave,
                    label=line.etiqueta,
                    amount_eur=round(line.importe, 2),
                    formula=line.formula,
                    intermediates=[
                        {
                            "key": value.clave,
                            "label": value.etiqueta,
                            "value": value.valor,
                            "unit": value.unidad,
                            "note": value.nota,
                        }
                        for value in line.intermedios
                    ],
                )
                for line in result.desglose_cliente
            ],
        ),
    )


async def calculate_for_customer(
    data: PublicCalculationInput,
    *,
    market_service: SpanishMarketReferenceService,
) -> PublicCalculationResult:
    result = await _calculate(
        data,
        market_service=market_service,
        include_audit=False,
    )
    assert isinstance(result, PublicCalculationResult)
    return result


async def calculate_for_audit(
    data: AuditCalculationInput,
    *,
    market_service: SpanishMarketReferenceService,
) -> AuditCalculationResult:
    result = await _calculate(
        data,
        market_service=market_service,
        include_audit=True,
        selected_boe_row_id=getattr(data, "boe_row_id_override", None),
    )
    assert isinstance(result, AuditCalculationResult)
    return result


__all__ = [
    "AuditCalculationInput",
    "AuditCalculationResult",
    "PublicCalculationInput",
    "PublicCalculationResult",
    "calculate_for_audit",
    "calculate_for_customer",
]
