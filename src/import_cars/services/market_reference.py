from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from statistics import median

from pydantic import BaseModel

from ..analysis import match_level
from ..enrichment.signature import build_vehicle_signature, normalize_fuel_category
from ..filters import FuelType, PowerRange, UnifiedFilters, YearRange
from ..models import NormalizedListing
from ..scrapers.coches_net import CochesNetScraper


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
        prices = [item.price_eur for item in selected if item.price_eur is not None]
        fetched_at = datetime.now(UTC)

        if not prices:
            return MarketReference(fetched_at=fetched_at)

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


__all__ = ["MarketReference", "SpanishMarketReferenceService"]
