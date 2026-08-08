"""Thin adapters between scraped listings and the canonical fiscal engine."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fiscal_engine import (
    Combustible,
    Operacion,
    TipoCarroceria,
    TipoComprador,
    TipoVendedor,
    Vehiculo,
    break_even_compraventa,
)

from ..enrichment.body_type import normalize_body_type
from ..enrichment.signature import normalize_fuel_category
from ..fiscal_data import resolver_registro_valor_tablas
from ..models import NormalizedListing


class FiscalInputError(ValueError):
    """Raised when a listing lacks mandatory fiscal inputs."""


_FUEL_MAP = {
    "gasoline": Combustible.GASOLINA,
    "diesel": Combustible.DIESEL,
    "electric": Combustible.ELECTRICO,
    "hybrid": Combustible.HIBRIDO,
    "phev": Combustible.HIBRIDO_ENCHUFABLE,
    "lpg": Combustible.GLP,
}


def _registration_date(listing: NormalizedListing) -> date:
    if listing.first_registration:
        return date(
            listing.first_registration.year,
            listing.first_registration.month or 1,
            1,
        )
    if listing.production_year:
        return date(listing.production_year, 1, 1)
    if listing.unregistered_new:
        return datetime.now(UTC).date()
    raise FiscalInputError("El anuncio no incluye fecha de primera matriculacion")


def _co2(listing: NormalizedListing) -> int | None:
    return (
        listing.co2_emissions_g_km
        if listing.co2_emissions_g_km is not None
        else listing.co2_original_g_km
        if listing.co2_original_g_km is not None
        else listing.co2_inferred_g_km
    )


def _model_description(listing: NormalizedListing) -> str:
    model = (listing.model or "").strip()
    version = (listing.version or "").strip()
    if version and version.casefold() not in model.casefold():
        return f"{model} {version}".strip()
    return model or (listing.title or "").strip()


def vehicle_from_listing(listing: NormalizedListing) -> Vehiculo:
    """Build the fiscal-engine input and enrich it with one exact BOE row."""

    if listing.price_eur is None or listing.price_eur <= 0:
        raise FiscalInputError("El anuncio no incluye un precio valido")
    if not listing.make:
        raise FiscalInputError("El anuncio no incluye marca")
    model = _model_description(listing)
    if not model:
        raise FiscalInputError("El anuncio no incluye modelo")

    registration_date = _registration_date(listing)
    normalized_fuel = normalize_fuel_category(listing.fuel_type)
    resolution = resolver_registro_valor_tablas(
        listing.make,
        model,
        registration_date,
        displacement_cc=listing.engine_displacement_cc,
        power_kw=listing.power_kw,
        fuel_code={
            "gasoline": "G",
            "diesel": "D",
            "electric": "Elc",
            "hybrid": "Hybrid",
            "phev": "PHEV",
            "lpg": "GLP",
        }.get(normalized_fuel),
        cylinders=listing.cylinders,
        transmission=listing.transmission,
    )
    displacement = listing.engine_displacement_cc or (
        resolution.displacement_cc if resolution else None
    )
    if displacement is None:
        raise FiscalInputError(
            "El anuncio no incluye cilindrada y no se pudo resolver en el BOE"
        )

    fuel = _FUEL_MAP.get(normalized_fuel, Combustible.OTRO)
    co2 = _co2(listing)
    confidence = listing.co2_confidence
    if confidence is None:
        confidence = 1.0 if listing.co2_original_g_km is not None else 0.0
    body_type = normalize_body_type(listing.body_type)

    return Vehiculo(
        marca=listing.make,
        modelo=model,
        fecha_primera_matriculacion=registration_date,
        precio_compra=listing.price_eur,
        precio_neto=listing.price_net_eur,
        iva_aleman_desglosable=bool(listing.vat_deductible),
        nuevo_sin_matricular=listing.unregistered_new,
        combustible=fuel,
        cilindrada_cc=displacement,
        co2_gkm=co2,
        kilometros=listing.mileage_km,
        potencia_kw=listing.power_kw or (resolution.power_kw if resolution else None),
        cvf=resolution.fiscal_hp if resolution else None,
        valor_tablas_nuevo=resolution.value_eur if resolution else None,
        co2_confianza=confidence,
        carroceria=TipoCarroceria(body_type) if body_type else None,
        boe_fila_id=resolution.row_id if resolution else None,
        boe_orden=resolution.order_code if resolution else None,
        boe_ejercicio=resolution.exercise if resolution else None,
        boe_modelo_resuelto=resolution.model_type if resolution else None,
    )


def break_even_scenarios(
    listing: NormalizedListing,
    *,
    comunidad_autonoma: str = "Madrid",
    municipio: str = "Madrid",
) -> dict[str, float]:
    """Calculate the three internal purchase scenarios with fiscal_engine."""

    try:
        vehicle = vehicle_from_listing(listing)
    except FiscalInputError:
        return {}

    scenarios = {
        "particular": TipoVendedor.PARTICULAR,
        "empresa_iva": TipoVendedor.PROFESIONAL_IVA,
        "empresa_margen": TipoVendedor.PROFESIONAL_MARGEN,
    }
    return {
        key: break_even_compraventa(
            vehicle,
            Operacion(
                tipo_vendedor=seller_type,
                tipo_comprador=TipoComprador.EMPRESA_ROI,
                comunidad_autonoma=comunidad_autonoma,
                municipio=municipio,
            ),
        )["break_even"]
        for key, seller_type in scenarios.items()
    }


__all__ = [
    "FiscalInputError",
    "break_even_scenarios",
    "vehicle_from_listing",
]
