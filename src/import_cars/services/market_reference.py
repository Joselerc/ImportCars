from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field

from ..analysis import match_decision, preferred_level_matches
from ..enrichment.signature import (
    build_engine_key,
    build_vehicle_signature,
    normalize_fuel_category,
    normalize_text,
)
from ..filters import FuelType, MileageRange, PowerRange, UnifiedFilters, YearRange
from ..models import NormalizedListing, SearchResult
from ..scrapers.autoscout24 import AutoScout24Scraper
from ..scrapers.base import BaseScraper
from ..scrapers.coches_net import CochesNetScraper

logger = logging.getLogger(__name__)


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
    outcome: Literal["match", "mismatch", "relaxed", "unavailable"] = "unavailable"
    note: str = ""


class MarketComparableAudit(BaseModel):
    listing_id: str
    source: str = "coches_net"
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
    used_for_price: bool = True
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
    quality_warning: str | None = None
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
    variant = build_engine_key(target)
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
            rule="Misma motorización obligatoria en exact/near; un conflicto conocido se descarta también en broad.",
            note="Si falta la identidad de motor, el coche solo puede entrar como broad.",
        ),
        _criterion(
            "year",
            "Año",
            year,
            used=year is not None,
            rule="Límites por nivel: exact ±1, near ±2, broad ±4 años."
            if year
            else "Sin año objetivo no se calcula referencia.",
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
            used=target.mileage_km is not None,
            rule="Filtro obligatorio: exact ±15.000, near ±35.000, broad ±60.000 km.",
            note="Si falta el kilometraje en cualquiera de los anuncios, no se usa como comparable.",
        ),
        _criterion(
            "transmission",
            "Cambio",
            target.transmission or target.metadata.source_transmission,
            used=bool(target.transmission or target.metadata.source_transmission),
            rule="Exact exige el mismo cambio; near lo prefiere; broad solo lo informa.",
            note="Nunca se aplica una corrección monetaria por el cambio.",
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
    outcome: str = "unavailable",
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
        outcome=outcome,
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
    decision,
    *,
    used_for_price: bool,
) -> MarketComparableAudit:
    target_variant = build_engine_key(target)
    candidate_variant = build_engine_key(candidate)
    target_year = _listing_year(target)
    candidate_year = _listing_year(candidate)
    return MarketComparableAudit(
        listing_id=candidate.listing_id,
        source=candidate.source,
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
        used_for_price=used_for_price,
        checks=[
            _check(
                "make", "Marca", target.make, candidate.make, policy_uses=True,
                outcome=decision.checks["make"].outcome,
                note=decision.checks["make"].note,
            ),
            _check(
                "model", "Modelo", target.model, candidate.model, policy_uses=True,
                outcome=decision.checks["model"].outcome,
                note=decision.checks["model"].note,
            ),
            _check(
                "version",
                "Motorización / versión",
                target_variant,
                candidate_variant,
                policy_uses=True,
                outcome=decision.checks["version"].outcome,
                note=decision.checks["version"].note,
            ),
            _check(
                "year", "Año", target_year, candidate_year, policy_uses=True,
                outcome=decision.checks["year"].outcome,
                note=decision.checks["year"].note,
            ),
            _check(
                "fuel",
                "Combustible",
                normalize_fuel_category(target.fuel_type),
                normalize_fuel_category(candidate.fuel_type),
                policy_uses=True,
                outcome=decision.checks["fuel"].outcome,
                note=decision.checks["fuel"].note,
            ),
            _check(
                "mileage",
                "Kilómetros",
                target.mileage_km,
                candidate.mileage_km,
                policy_uses=True,
                outcome=decision.checks["mileage"].outcome,
                note=decision.checks["mileage"].note,
            ),
            _check(
                "transmission",
                "Cambio",
                target.transmission or target.metadata.source_transmission,
                candidate.transmission or candidate.metadata.source_transmission,
                policy_uses=level != "broad",
                outcome=decision.checks["transmission"].outcome,
                note=decision.checks["transmission"].note,
            ),
            _check(
                "power",
                "Potencia",
                target.power_hp,
                candidate.power_hp,
                policy_uses=True,
                outcome="match" if level in {"exact", "near"} else "relaxed",
                note="La potencia forma parte de la comprobación técnica del motor.",
            ),
            _check(
                "displacement",
                "Cilindrada",
                target.engine_displacement_cc,
                candidate.engine_displacement_cc,
                policy_uses=True,
                outcome="match" if level in {"exact", "near"} else "relaxed",
                note="La cilindrada forma parte de la comprobación técnica del motor.",
            ),
        ],
    )


class SpanishMarketReferenceService:
    """Consulta marketplaces abiertos españoles y combina sus comparables."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 900,
        scraper_factory: Callable[[], BaseScraper] | None = None,
        scraper_factories: tuple[Callable[[], BaseScraper], ...] | None = None,
    ) -> None:
        if scraper_factory is not None and scraper_factories is not None:
            raise ValueError("Usa scraper_factory o scraper_factories, no ambos")
        self.ttl_seconds = max(0, ttl_seconds)
        self.scraper_factories = (
            scraper_factories
            if scraper_factories is not None
            else (scraper_factory,)
            if scraper_factory is not None
            else (CochesNetScraper, AutoScout24Scraper)
        )
        self._cache: dict[str, tuple[float, MarketReference]] = {}
        self._lock = asyncio.Lock()

    async def get_reference(self, target: NormalizedListing) -> MarketReference:
        if not target.make or not target.model:
            raise ValueError(
                "Se necesitan marca y modelo para buscar comparables en España"
            )

        key = (
            f"{build_vehicle_signature(target)}|engine:{build_engine_key(target)}"
            f"|km:{target.mileage_km if target.mileage_km is not None else 'na'}"
        )
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
        results = await asyncio.gather(
            *(self._search_source(factory, filters) for factory in self.scraper_factories)
        )
        pool = self._deduplicate(
            [listing for result in results for listing in result.listings]
        )
        source = self._source_label(pool)

        buckets: dict[str, list[tuple[NormalizedListing, object]]] = {
            "exact": [],
            "near": [],
            "broad": [],
        }
        for candidate in pool:
            decision = match_decision(target, candidate)
            if decision.level:
                buckets[decision.level].append((candidate, decision))

        selected_level = next(
            (level for level in ("exact", "near", "broad") if buckets[level]),
            None,
        )
        level_matches = buckets[selected_level] if selected_level else []
        priced_level = [
            (item, decision)
            for item, decision in level_matches
            if item.price_eur is not None
        ]
        priced = (
            preferred_level_matches(priced_level, selected_level)
            if selected_level
            else []
        )
        prices = [item.price_eur for item, _decision in priced]
        fetched_at = datetime.now(UTC)
        criteria = _criteria_audit(target)

        if not prices:
            return MarketReference(
                source=source,
                fetched_at=fetched_at,
                criteria=criteria,
                quality_warning=(
                    "No hay comparables suficientes dentro del nivel broad; "
                    "no se estima el ahorro."
                ),
            )

        confidence = {
            "exact": "high",
            "near": "medium",
            "broad": "low",
        }[selected_level]
        warning_parts = []
        if selected_level == "broad":
            warning_parts.append(
                "El ahorro es orientativo: solo hay comparables broad y no son versiones exactas."
            )
        if selected_level == "near" and len(priced) < len(priced_level):
            warning_parts.append(
                "En nivel near se priorizaron los anuncios con el mismo cambio; "
                "los demás quedan visibles pero no entran en la mediana."
            )
        if len(prices) < 3:
            warning_parts.append(
                f"La muestra usada tiene solo {len(prices)} "
                f"{'comparable' if len(prices) == 1 else 'comparables'}."
            )
        used_ids = {item.listing_id for item, _decision in priced}
        return MarketReference(
            source=source,
            match_level=selected_level,
            sample_size=len(prices),
            average_eur=round(sum(prices) / len(prices), 2),
            median_eur=round(median(prices), 2),
            minimum_eur=round(min(prices), 2),
            maximum_eur=round(max(prices), 2),
            confidence=confidence,
            fetched_at=fetched_at,
            quality_warning=" ".join(warning_parts) or None,
            criteria=criteria,
            comparables=[
                _comparable_audit(
                    target,
                    candidate,
                    selected_level,
                    decision,
                    used_for_price=candidate.listing_id in used_ids,
                )
                for candidate, decision in priced_level
            ],
        )

    @staticmethod
    async def _search_source(
        factory: Callable[[], BaseScraper],
        filters: UnifiedFilters,
    ) -> SearchResult:
        scraper = factory()
        try:
            return await scraper.search(query=filters, limit=filters.page_size)
        except Exception as exc:  # noqa: BLE001 - una fuente no bloquea la otra
            logger.warning(
                "No se pudieron obtener comparables desde %s: %s",
                scraper.__class__.__name__,
                exc,
            )
            return SearchResult(listings=[], total_listings=0, has_next=False)

    @staticmethod
    def _source_label(listings: list[NormalizedListing]) -> str:
        present = {listing.source for listing in listings}
        ordered = [
            source for source in ("coches_net", "autoscout24") if source in present
        ]
        ordered.extend(sorted(present - set(ordered)))
        return "+".join(ordered) or "coches_net+autoscout24"

    @staticmethod
    def _deduplicate(listings: list[NormalizedListing]) -> list[NormalizedListing]:
        """Remove repeated marketplace cards before matching and the median."""

        selected: dict[tuple, NormalizedListing] = {}
        for listing in listings:
            year = _listing_year(listing)
            key = (
                normalize_text(listing.make),
                normalize_text(listing.model),
                year,
                listing.mileage_km,
                round(float(listing.price_eur), 2)
                if listing.price_eur is not None
                else None,
                listing.power_hp,
                normalize_fuel_category(listing.fuel_type),
                normalize_text(
                    listing.transmission or listing.metadata.source_transmission
                ),
            )
            current = selected.get(key)
            if current is None:
                selected[key] = listing
                continue
            current_score = sum(
                value not in (None, "")
                for value in (
                    current.version,
                    current.engine_displacement_cc,
                    current.transmission,
                    current.seller.name if current.seller else None,
                )
            )
            candidate_score = sum(
                value not in (None, "")
                for value in (
                    listing.version,
                    listing.engine_displacement_cc,
                    listing.transmission,
                    listing.seller.name if listing.seller else None,
                )
            )
            if candidate_score > current_score:
                selected[key] = listing
        return list(selected.values())

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

        mileage_range = None
        if target.mileage_km is not None:
            mileage_range = MileageRange(
                min_mileage=max(0, target.mileage_km - 60_000),
                max_mileage=target.mileage_km + 60_000,
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
            mileage_range=mileage_range,
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
