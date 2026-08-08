from datetime import UTC, datetime

import pytest

from import_cars.models import NormalizedListing, Registration, SearchResult
from import_cars.services import SpanishMarketReferenceService


def listing(
    listing_id: str,
    *,
    source: str,
    title: str,
    price: float,
    power_hp: int = 265,
    mileage_km: int = 60_000,
    transmission: str | None = "automatic",
) -> NormalizedListing:
    return NormalizedListing(
        listing_id=listing_id,
        source=source,
        url=f"https://example.com/{listing_id}",
        scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        title=title,
        make="BMW",
        model="X5",
        price_eur=price,
        first_registration=Registration(year=2020, month=6),
        fuel_type="diesel",
        mileage_km=mileage_km,
        transmission=transmission,
        power_hp=power_hp,
        engine_displacement_cc=2_993,
    )


@pytest.mark.asyncio
async def test_market_reference_prefers_exact_matches_and_uses_short_cache() -> None:
    calls = 0
    candidates = [
        listing("es-1", source="coches_net", title="BMW X5 xDrive30d", price=40_000),
        listing(
            "es-2",
            source="coches_net",
            title="BMW X5 xDrive30d",
            price=42_000,
            transmission=None,
        ),
        listing(
            "es-wrong-version",
            source="coches_net",
            title="BMW X5 xDrive40d",
            price=47_000,
            power_hp=286,
        ),
    ]

    class ScraperStub:
        async def search(self, *, query, limit):
            nonlocal calls
            calls += 1
            assert query.make == "BMW"
            assert query.model == "X5"
            assert query.mileage_range.min_mileage == 0
            assert query.mileage_range.max_mileage == 120_000
            assert limit == 50
            return SearchResult(listings=candidates)

    service = SpanishMarketReferenceService(
        ttl_seconds=60,
        scraper_factory=ScraperStub,
    )
    target = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
    )

    first = await service.get_reference(target)
    second = await service.get_reference(target)

    assert first.match_level == "exact"
    assert first.sample_size == 1
    assert first.median_eur == 40_000
    assert first.confidence == "high"
    assert [item.listing_id for item in first.comparables] == ["es-1"]
    assert first.comparables[0].mileage_km == 60_000
    assert first.comparables[0].year == 2020
    assert first.comparables[0].fuel == "diesel"
    assert first.comparables[0].transmission == "automatic"
    assert first.comparables[0].url.endswith("/es-1")
    criteria = {item.key: item for item in first.criteria}
    assert criteria["fuel"].status == "used"
    assert criteria["mileage"].status == "used"
    assert criteria["transmission"].status == "used"
    checks = {item.key: item for item in first.comparables[0].checks}
    assert checks["mileage"].status == "used"
    assert checks["mileage"].outcome == "match"
    assert checks["transmission"].status == "used"
    assert checks["transmission"].outcome == "match"
    assert first.cached is False
    assert second.cached is True
    assert calls == 1


@pytest.mark.asyncio
async def test_near_prefers_same_transmission_without_price_adjustment() -> None:
    candidates = [
        listing(
            "es-manual",
            source="coches_net",
            title="BMW X5 xDrive30d",
            price=40_000,
            mileage_km=80_000,
            transmission="manual",
        ),
        listing(
            "es-auto",
            source="coches_net",
            title="BMW X5 xDrive30d",
            price=44_000,
            mileage_km=80_000,
            transmission="automatic",
        ),
    ]

    class ScraperStub:
        async def search(self, *, query, limit):
            return SearchResult(listings=candidates)

    target = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
        mileage_km=60_000,
        transmission="automatic",
    )
    result = await SpanishMarketReferenceService(
        ttl_seconds=0,
        scraper_factory=ScraperStub,
    ).get_reference(target)

    assert result.match_level == "near"
    assert result.sample_size == 1
    assert result.median_eur == 44_000
    comparables = {item.listing_id: item for item in result.comparables}
    assert comparables["es-auto"].used_for_price is True
    assert comparables["es-manual"].used_for_price is False
    assert "no entran en la mediana" in result.quality_warning


@pytest.mark.asyncio
async def test_broad_reference_is_explicitly_orientative() -> None:
    candidate = listing(
        "es-broad",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=41_000,
        mileage_km=110_000,
    )

    class ScraperStub:
        async def search(self, *, query, limit):
            return SearchResult(listings=[candidate])

    target = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
        mileage_km=60_000,
    )
    result = await SpanishMarketReferenceService(
        ttl_seconds=0,
        scraper_factory=ScraperStub,
    ).get_reference(target)

    assert result.match_level == "broad"
    assert result.median_eur == 41_000
    assert result.confidence == "low"
    assert "ahorro es orientativo" in result.quality_warning


@pytest.mark.asyncio
async def test_marketplaces_are_combined_and_cross_posted_car_is_deduplicated() -> None:
    coches_duplicate = listing(
        "coches-duplicate",
        source="coches_net",
        title="BMW X5 xDrive30d",
        price=40_000,
    )
    scout_duplicate = listing(
        "scout-duplicate",
        source="autoscout24",
        title="BMW X5 xDrive30d",
        price=40_000,
    )
    scout_unique = listing(
        "scout-unique",
        source="autoscout24",
        title="BMW X5 xDrive30d",
        price=44_000,
        mileage_km=61_000,
    )

    class CochesStub:
        async def search(self, *, query, limit):
            return SearchResult(listings=[coches_duplicate])

    class ScoutStub:
        async def search(self, *, query, limit):
            return SearchResult(listings=[scout_duplicate, scout_unique])

    target = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
    )
    result = await SpanishMarketReferenceService(
        ttl_seconds=0,
        scraper_factories=(CochesStub, ScoutStub),
    ).get_reference(target)

    assert result.source == "coches_net+autoscout24"
    assert result.sample_size == 2
    assert result.median_eur == 42_000
    assert {item.source for item in result.comparables} == {
        "coches_net",
        "autoscout24",
    }


@pytest.mark.asyncio
async def test_one_marketplace_failure_does_not_hide_the_other_source() -> None:
    candidate = listing(
        "scout-only",
        source="autoscout24",
        title="BMW X5 xDrive30d",
        price=41_500,
    )

    class BrokenCochesStub:
        async def search(self, *, query, limit):
            raise RuntimeError("coches.net temporalmente no disponible")

    class ScoutStub:
        async def search(self, *, query, limit):
            return SearchResult(listings=[candidate])

    target = listing(
        "de-1",
        source="mobile_de",
        title="BMW X5 xDrive30d",
        price=30_000,
    )
    result = await SpanishMarketReferenceService(
        ttl_seconds=0,
        scraper_factories=(BrokenCochesStub, ScoutStub),
    ).get_reference(target)

    assert result.source == "autoscout24"
    assert result.sample_size == 1
    assert result.median_eur == 41_500
    assert result.comparables[0].source == "autoscout24"
