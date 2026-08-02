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
    assert [item.listing_id for item in first.comparables] == ["es-1", "es-2"]
    assert first.comparables[0].mileage_km == 60_000
    assert first.comparables[0].year == 2020
    assert first.comparables[0].fuel == "diesel"
    assert first.comparables[0].transmission == "automatic"
    assert first.comparables[0].url.endswith("/es-1")
    criteria = {item.key: item for item in first.criteria}
    assert criteria["fuel"].status == "used"
    assert criteria["mileage"].status == "not_used"
    assert criteria["transmission"].status == "not_used"
    checks = {item.key: item for item in first.comparables[0].checks}
    assert checks["mileage"].status == "not_used"
    assert checks["transmission"].status == "not_used"
    missing_checks = {item.key: item for item in first.comparables[1].checks}
    assert missing_checks["transmission"].status == "unavailable"
    assert "falta el dato" in missing_checks["transmission"].note
    assert first.cached is False
    assert second.cached is True
    assert calls == 1
