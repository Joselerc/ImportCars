from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field

from ..analysis import match_level
from ..enrichment.signature import (
    build_variant_key,
    build_vehicle_signature,
    normalize_fuel_category,
)
from ..filters import FuelType, PowerRange, UnifiedFilters, YearRange
from ..models import NormalizedListing
from ..scrapers.coches_net import CochesNetScraper


class MatchCriterionAudit(BaseModel):
    key: str
    label: str
    target_value: str | float | None
    status: Literal["used", "not_used", "unavailable"]
    rule: str
    note: str = ""


class ComparableCheckAudit(BaseModel):
    key: str
    label: str
    target_value: str | float | None
    comparable_value: str | float | None
    status: Literal["used", "not_used", "unavailable"]
    note: str = ""


class MarketComparableAudit(BaseModel):
    listing_id: str
    title: str | None
    url: str
    price_eur: float
    mileage_km: int | None
    year: int | None
    version: str | None
    fuel: str | None
    transmission: str | None
    power_hp: int | None
    displacement_cc: int | None
    match_level: str
    checks: list[ComparableCheckAudit]


class MarketReference(BaseModel):
    source: str = "coches_net"
    country_code: str = "ES"
    match_level: str | None = None
    sample_size: int = 0
    average_eur: float | None = None
    median_eur: float | None = None
    minimum_eur: float | None = None
    maximum_eur: float | None = None
    confidence: str = "insufficient"
    fetched_at: datetime
    cached: bool = False
    criteria: list[MatchCriterionAudit] = Field(default_factory=list)
    comparables: list[MarketComparableAudit] = Field(default_factory=list)


def _listing_year(listing: NormalizedListing) -> int | None:
    if listing.first_registration:
        return listing.first_registration.year
    return listing.production_year


def _criterion(
    key: str,
    label: str,
    value: str | float | None,
    *,
    used: bool,
    rule: str,
    note: str = "",
) -> MatchCriterionAudit:
    status = "used" if used else "unavailable" if value in (None, "", "na") else "not_used"
    return MatchCriterionAudit(
        key=key,
        label=label,
        target_value=value,
        status=status,
        rule=rule,
        note=note,
    )


def _criteria_audit(target: NormalizedListing) -> list[MatchCriterionAudit]:
    """Describe la política vigente sin participar en su decisión."""

    year = _listing_year(target)
    variant = build_variant_key(target)
    fuel = normalize_fuel_category(target.fuel_type)
    return [
        _criterion(
            "make",
            "Marca",
            target.make,
            used=bool(target.make),
            rule="Igualdad normalizada en búsqueda y match.",
        ),
        _criterion(
            "model",
            "Modelo",
            target.model,
            used=bool(target.model),
            rule="Familia de modelo normalizada en búsqueda y match.",
        ),
        _criterion(
            "version",
            "Versión / motorización",
            variant if variant != "na" else target.version,
            used=variant != "na",
            rule="La clave de variante se compara cuando ambos anuncios permiten extraerla.",
            note="Si un comparable no aporta una variante reconocible, este criterio no puede aplicarse a ese coche.",
        ),
        _criterion(
            "year",
            "Año",
            year,
            used=year is not None,
            rule=f"Búsqueda entre {year - 4} y {year + 4}; el nivel final limita la diferencia." if year else "Sin año objetivo.",
        ),
        _criterion(
            "fuel",
            "Combustible",
            fuel if fuel != "na" else target.fuel_type,
            used=fuel != "na",
            rule="Igualdad de categoría normalizada en búsqueda y match.",
        ),
        _criterion(
            "mileage",
            "Kilómetros",
            target.mileage_km,
            used=False,
            rule="La política vigente no filtra ni clasifica por kilómetros.",
            note="Se muestran para revisión, pero todavía no intervienen en el match.",
        ),
        _criterion(
            "transmission",
            "Cambio",
            target.transmission,
            used=False,
            rule="La política vigente no filtra ni clasifica por tipo de cambio.",
            note="Se muestra para revisión; puede faltar en el anuncio de origen.",
        ),
        _criterion(
            "power",
            "Potencia",
            target.power_hp,
            used=target.power_hp is not None,
            rule="Filtro ±25% (mínimo ±60 CV) y tolerancia por nivel cuando ambos anuncios tienen el dato.",
        ),
        _criterion(
            "displacement",
            "Cilindrada",
            target.engine_displacement_cc,
            used=target.engine_displacement_cc is not None,
            rule="Tolerancia por nivel cuando ambos anuncios tienen el dato; máximo absoluto de 500 cc.",
        ),
    ]


def _check(
    key: str,
    label: str,
    target_value: str | float | None,
    comparable_value: str | float | None,
    *,
    policy_uses: bool,
    note: str = "",
) -> ComparableCheckAudit:
    available = target_value not in (None, "", "na") and comparable_value not in (
        None,
        "",
        "na",
    )
    status = "used" if policy_uses and available else "not_used" if available else "unavailable"
    return ComparableCheckAudit(
        key=key,
        label=label,
        target_value=target_value,
        comparable_value=comparable_value,
        status=status,
        note=(
            note
            if available
            else "No pudo aplicarse porque falta el dato en uno de los anuncios."
        ),
    )


def _comparable_audit(
    target: NormalizedListing,
    candidate: NormalizedListing,
    level: str,
) -> MarketComparableAudit:
    target_variant = build_variant_key(target)
    candidate_variant = build_variant_key(candidate)
    target_year = _listing_year(target)
    candidate_year = _listing_year(candidate)
    return MarketComparableAudit(
        listing_id=candidate.listing_id,
        title=candidate.title,
        url=str(candidate.url),
        price_eur=float(candidate.price_eur),
        mileage_km=candidate.mileage_km,
        year=candidate_year,
        version=candidate.version or candidate.title,
        fuel=candidate.fuel_type,
        transmission=candidate.transmission or candidate.metadata.source_transmission,
        power_hp=candidate.power_hp,
        displacement_cc=candidate.engine_displacement_cc,
        match_level=level,
        checks=[
            _check("make", "Marca", target.make, candidate.make, policy_uses=True),
            _check("model", "Modelo", target.model, candidate.model, policy_uses=True),
            _check(
                "version",
                "Versión",
                target_variant,
                candidate_variant,
                policy_uses=True,
            ),
            _check("year", "Año", target_year, candidate_year, policy_uses=True),
            _check(
                "fuel",
                "Combustible",
                normalize_fuel_category(target.fuel_type),
                normalize_fuel_category(candidate.fuel_type),
                policy_uses=True,
            ),
            _check(
                "mileage",
                "Kilómetros",
                target.mileage_km,
                candidate.mileage_km,
                policy_uses=False,
                note="Dato visible, no usado por la política actual.",
            ),
            _check(
                "transmission",
                "Cambio",
                target.transmission,
                candidate.transmission or candidate.metadata.source_transmission,
                policy_uses=False,
                note="Dato visible, no usado por la política actual.",
            ),
            _check(
                "power",
                "Potencia",
                target.power_hp,
                candidate.power_hp,
                policy_uses=True,
            ),
            _check(
                "displacement",
                "Cilindrada",
                target.engine_displacement_cc,
                candidate.engine_displacement_cc,
                policy_uses=True,
            ),
        ],
    )


class SpanishMarketReferenceService:
    """Consulta coches.net bajo demanda y conserva una caché corta en memoria."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 900,
        scraper_factory: Callable[[], CochesNetScraper] = CochesNetScraper,
    ) -> None:
        self.ttl_seconds = max(0, ttl_seconds)
        self.scraper_factory = scraper_factory
        self._cache: dict[str, tuple[float, MarketReference]] = {}
        self._lock = asyncio.Lock()

    async def get_reference(self, target: NormalizedListing) -> MarketReference:
        if not target.make or not target.model:
            raise ValueError(
                "Se necesitan marca y modelo para buscar comparables en España"
            )

        key = build_vehicle_signature(target)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            return cached[1].model_copy(update={"cached": True})

        async with self._lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return cached[1].model_copy(update={"cached": True})

            reference = await self._fetch_reference(target)
            self._cache[key] = (now + self.ttl_seconds, reference)
            return reference

    async def _fetch_reference(self, target: NormalizedListing) -> MarketReference:
        filters = self._build_filters(target)
        result = await self.scraper_factory().search(
            query=filters, limit=filters.page_size
        )

        buckets: dict[str, list[NormalizedListing]] = {
            "exact": [],
            "near": [],
            "broad": [],
        }
        for candidate in result.listings:
            level = match_level(target, candidate)
            if level:
                buckets[level].append(candidate)

        selected_level = next(
            (level for level in ("exact", "near", "broad") if buckets[level]),
            None,
        )
        selected = buckets[selected_level] if selected_level else []
        priced = [item for item in selected if item.price_eur is not None]
        prices = [item.price_eur for item in priced]
        fetched_at = datetime.now(UTC)
        criteria = _criteria_audit(target)

        if not prices:
            return MarketReference(fetched_at=fetched_at, criteria=criteria)

        confidence = {
            "exact": "high",
            "near": "medium",
            "broad": "low",
        }[selected_level]
        return MarketReference(
            match_level=selected_level,
            sample_size=len(prices),
            average_eur=round(sum(prices) / len(prices), 2),
            median_eur=round(median(prices), 2),
            minimum_eur=round(min(prices), 2),
            maximum_eur=round(max(prices), 2),
            confidence=confidence,
            fetched_at=fetched_at,
            criteria=criteria,
            comparables=[
                _comparable_audit(target, candidate, selected_level)
                for candidate in priced
            ],
        )

    @staticmethod
    def _build_filters(target: NormalizedListing) -> UnifiedFilters:
        year = (
            target.first_registration.year
            if target.first_registration
            else target.production_year
        )
        year_range = YearRange(min_year=year - 4, max_year=year + 4) if year else None

        power_range = None
        if target.power_hp:
            tolerance = max(60, round(target.power_hp * 0.25))
            power_range = PowerRange(
                min_power_hp=max(0, target.power_hp - tolerance),
                max_power_hp=target.power_hp + tolerance,
            )

        fuel_category = normalize_fuel_category(target.fuel_type)
        fuel_types = None
        try:
            fuel_types = [FuelType(fuel_category)] if fuel_category != "na" else None
        except ValueError:
            fuel_types = None

        return UnifiedFilters(
            make=target.make,
            model=target.model,
            year_range=year_range,
            power_range=power_range,
            fuel_types=fuel_types,
            page_size=50,
        )


__all__ = [
    "ComparableCheckAudit",
    "MarketComparableAudit",
    "MarketReference",
    "MatchCriterionAudit",
    "SpanishMarketReferenceService",
]
