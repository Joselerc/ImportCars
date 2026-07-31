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
        power_hp=power_hp,
        engine_displacement_cc=2_993,
    )


@pytest.mark.asyncio
async def test_market_reference_prefers_exact_matches_and_uses_short_cache() -> None:
    calls = 0
    candidates = [
        listing("es-1", source="coches_net", title="BMW X5 xDrive30d", price=40_000),
        listing("es-2", source="coches_net", title="BMW X5 xDrive30d", price=42_000),
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
    assert first.sample_size == 2
    assert first.median_eur == 41_000
    assert first.confidence == "high"
    assert first.cached is False
    assert second.cached is True
    assert calls == 1
