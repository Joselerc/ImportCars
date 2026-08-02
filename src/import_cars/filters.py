"""
Sistema de filtros unificado para mobile.de y coches.net
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class SortBy(str, Enum):
    RELEVANCE = "relevance"
    PRICE_LOW_TO_HIGH = "price_asc"
    PRICE_HIGH_TO_LOW = "price_desc"
    YEAR_NEW_TO_OLD = "year_desc"
    YEAR_OLD_TO_NEW = "year_asc"
    MILEAGE_LOW_TO_HIGH = "mileage_asc"
    MILEAGE_HIGH_TO_LOW = "mileage_desc"


class FuelType(str, Enum):
    GASOLINE = "gasoline"
    DIESEL = "diesel"
    ELECTRIC = "electric"
    HYBRID = "hybrid"
    HYBRID_GASOLINE = "hybrid_gasoline"
    HYBRID_DIESEL = "hybrid_diesel"
    ETHANOL = "ethanol"
    LPG = "lpg"
    CNG = "cng"
    HYDROGEN = "hydrogen"


class Transmission(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SEMI_AUTOMATIC = "semi_automatic"


class BodyType(str, Enum):
    SEDAN = "sedan"
    HATCHBACK = "hatchback"
    STATION_WAGON = "station_wagon"
    SUV = "suv"
    COUPE = "coupe"
    CONVERTIBLE = "convertible"
    MINIVAN = "minivan"
    PICKUP = "pickup"
    OTHER = "other"


class PriceRange(BaseModel):
    min_price: float | None = Field(None, ge=0, description="Precio mínimo en EUR")
    max_price: float | None = Field(None, ge=0, description="Precio máximo en EUR")

    @model_validator(mode="after")
    def validate_order(self):
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price no puede ser mayor que max_price")
        return self


class YearRange(BaseModel):
    min_year: int | None = Field(None, ge=1900, le=2030, description="Año mínimo")
    max_year: int | None = Field(None, ge=1900, le=2030, description="Año máximo")

    @model_validator(mode="after")
    def validate_order(self):
        if (
            self.min_year is not None
            and self.max_year is not None
            and self.min_year > self.max_year
        ):
            raise ValueError("min_year no puede ser mayor que max_year")
        return self


class MileageRange(BaseModel):
    min_mileage: int | None = Field(None, ge=0, description="Kilometraje mínimo")
    max_mileage: int | None = Field(None, ge=0, description="Kilometraje máximo")

    @model_validator(mode="after")
    def validate_order(self):
        if (
            self.min_mileage is not None
            and self.max_mileage is not None
            and self.min_mileage > self.max_mileage
        ):
            raise ValueError("min_mileage no puede ser mayor que max_mileage")
        return self


class PowerRange(BaseModel):
    min_power_hp: int | None = Field(None, ge=0, description="Potencia mínima en HP")
    max_power_hp: int | None = Field(None, ge=0, description="Potencia máxima en HP")

    @model_validator(mode="after")
    def validate_order(self):
        if (
            self.min_power_hp is not None
            and self.max_power_hp is not None
            and self.min_power_hp > self.max_power_hp
        ):
            raise ValueError("min_power_hp no puede ser mayor que max_power_hp")
        return self


class UnifiedFilters(BaseModel):
    """
    Filtros unificados que se pueden aplicar a cualquier scraper.
    Cada scraper traducirá estos filtros a su formato específico.
    """

    # Paginación
    page: int = Field(1, ge=1, description="Número de página")
    page_size: int = Field(30, ge=1, le=200, description="Resultados por página")

    # Ordenación
    sort_by: SortBy = Field(SortBy.RELEVANCE, description="Criterio de ordenación")
    sort_order: SortOrder = Field(
        SortOrder.DESC, description="Orden ascendente o descendente"
    )

    # Filtros básicos
    make: str | None = Field(
        None, description="Marca del vehículo (ej: BMW, Mercedes-Benz)"
    )
    model: str | None = Field(
        None, description="Modelo del vehículo (ej: Serie 3, Clase C)"
    )
    version: str | None = Field(
        None, description="Versión o motorización (ej: xDrive30d)"
    )

    # Rangos de valores
    price_range: PriceRange | None = Field(None, description="Rango de precios")
    year_range: YearRange | None = Field(None, description="Rango de años")
    mileage_range: MileageRange | None = Field(None, description="Rango de kilometraje")
    power_range: PowerRange | None = Field(None, description="Rango de potencia")

    # Características del vehículo
    fuel_types: list[FuelType] | None = Field(None, description="Tipos de combustible")
    transmissions: list[Transmission] | None = Field(
        None, description="Tipos de transmisión"
    )
    body_types: list[BodyType] | None = Field(None, description="Tipos de carrocería")

    # Filtros específicos
    min_doors: int | None = Field(
        None, ge=2, le=5, description="Número mínimo de puertas"
    )
    max_doors: int | None = Field(
        None, ge=2, le=5, description="Número máximo de puertas"
    )
    min_seats: int | None = Field(
        None, ge=2, le=9, description="Número mínimo de asientos"
    )
    max_seats: int | None = Field(
        None, ge=2, le=9, description="Número máximo de asientos"
    )

    # Ubicación
    country_code: str | None = Field(
        None, min_length=2, max_length=2, description="Código de país (ej: DE, ES)"
    )
    region: str | None = Field(None, description="Región o estado")
    city: str | None = Field(None, description="Ciudad")

    # Vendedor
    dealer_only: bool | None = Field(None, description="Solo concesionarios")
    private_only: bool | None = Field(None, description="Solo particulares")

    # Otros
    with_images: bool | None = Field(None, description="Solo anuncios con imágenes")
    certified_only: bool | None = Field(None, description="Solo vehículos certificados")

    @model_validator(mode="after")
    def validate_consistency(self):
        if self.dealer_only and self.private_only:
            raise ValueError("dealer_only y private_only son excluyentes")
        if (
            self.min_doors is not None
            and self.max_doors is not None
            and self.min_doors > self.max_doors
        ):
            raise ValueError("min_doors no puede ser mayor que max_doors")
        if (
            self.min_seats is not None
            and self.max_seats is not None
            and self.min_seats > self.max_seats
        ):
            raise ValueError("min_seats no puede ser mayor que max_seats")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convierte los filtros a un diccionario, excluyendo valores None"""
        return self.model_dump(exclude_none=True, mode="python")


class FilterTranslator:
    """
    Clase base para traducir filtros unificados al formato específico de cada scraper
    """

    @staticmethod
    def translate_fuel_type(fuel_type: FuelType, target_format: str) -> str:
        """Traduce tipos de combustible al formato del scraper específico"""
        translations = {
            "mobile_de": {
                FuelType.GASOLINE: "Gasolina",
                FuelType.DIESEL: "Diesel",
                FuelType.ELECTRIC: "Eléctrico",
                FuelType.HYBRID: "Híbrido",
                FuelType.HYBRID_GASOLINE: "Híbrido (Gasolina)",
                FuelType.HYBRID_DIESEL: "Híbrido (Diesel)",
                FuelType.ETHANOL: "Etanol",
                FuelType.LPG: "Gas licuado",
                FuelType.CNG: "Gas natural",
                FuelType.HYDROGEN: "Hidrógeno",
            },
            "coches_net": {
                FuelType.GASOLINE: "gasoline",
                FuelType.DIESEL: "diesel",
                FuelType.ELECTRIC: "electric",
                FuelType.HYBRID: "hybrid",
                FuelType.HYBRID_GASOLINE: "hybrid_gasoline",
                FuelType.HYBRID_DIESEL: "hybrid_diesel",
                FuelType.LPG: "lpg",
                FuelType.CNG: "cng",
            },
        }
        return translations.get(target_format, {}).get(fuel_type, fuel_type.value)

    @staticmethod
    def translate_transmission(transmission: Transmission, target_format: str) -> str:
        """Traduce tipos de transmisión al formato del scraper específico"""
        translations = {
            "mobile_de": {
                Transmission.MANUAL: "Manual",
                Transmission.AUTOMATIC: "Automático",
                Transmission.SEMI_AUTOMATIC: "Semiautomático",
            },
            "coches_net": {
                Transmission.MANUAL: "manual",
                Transmission.AUTOMATIC: "automatic",
                Transmission.SEMI_AUTOMATIC: "semi_automatic",
            },
        }
        return translations.get(target_format, {}).get(transmission, transmission.value)

    @staticmethod
    def translate_sort_by(sort_by: SortBy, target_format: str) -> str:
        """Traduce criterios de ordenación al formato del scraper específico"""
        translations = {
            "mobile_de": {
                SortBy.RELEVANCE: "relevance",
                SortBy.PRICE_LOW_TO_HIGH: "price.asc",
                SortBy.PRICE_HIGH_TO_LOW: "price.desc",
                SortBy.YEAR_NEW_TO_OLD: "year.desc",
                SortBy.YEAR_OLD_TO_NEW: "year.asc",
                SortBy.MILEAGE_LOW_TO_HIGH: "mileage.asc",
                SortBy.MILEAGE_HIGH_TO_LOW: "mileage.desc",
            },
            "coches_net": {
                SortBy.RELEVANCE: "relevance",
                SortBy.PRICE_LOW_TO_HIGH: "price",
                SortBy.PRICE_HIGH_TO_LOW: "price",
                SortBy.YEAR_NEW_TO_OLD: "year",
                SortBy.YEAR_OLD_TO_NEW: "year",
                SortBy.MILEAGE_LOW_TO_HIGH: "mileage",
                SortBy.MILEAGE_HIGH_TO_LOW: "mileage",
            },
        }
        return translations.get(target_format, {}).get(sort_by, sort_by.value)


__all__ = [
    "BodyType",
    "FilterTranslator",
    "FuelType",
    "MileageRange",
    "PowerRange",
    "PriceRange",
    "SortBy",
    "SortOrder",
    "Transmission",
    "UnifiedFilters",
    "YearRange",
]
