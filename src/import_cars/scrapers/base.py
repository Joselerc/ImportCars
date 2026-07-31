from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, List, Optional

from ..config import ScraperSettings, get_settings
from ..models import NormalizedListing, SearchResult


class BaseScraper(ABC):
    def __init__(self, *, settings: Optional[ScraperSettings] = None) -> None:
        self.settings = settings or get_settings()

    @abstractmethod
    async def search(
        self, *, query: dict[str, Any], limit: Optional[int] = None
    ) -> SearchResult:
        """Fetch a single results page for the provided query."""

    async def iterate(
        self, *, query: dict[str, Any], limit: Optional[int] = None
    ) -> AsyncIterator[NormalizedListing]:
        fetched = 0
        page = 1
        while True:
            page_result = await self.search(query=query | {"page": page}, limit=limit)
            for listing in page_result.listings:
                yield listing
                fetched += 1
                if limit is not None and fetched >= limit:
                    return
            if not page_result.has_next or not page_result.listings:
                return
            page += 1

    async def gather(
        self, *, query: dict[str, Any], limit: Optional[int] = None
    ) -> List[NormalizedListing]:
        return [item async for item in self.iterate(query=query, limit=limit)]

    async def bounded_gather(
        self,
        *,
        queries: List[dict[str, Any]],
        limit_per_query: Optional[int] = None,
        semaphore: Optional[asyncio.Semaphore] = None,
    ) -> List[NormalizedListing]:
        semaphore = semaphore or asyncio.Semaphore(self.settings.concurrency)
        results: List[NormalizedListing] = []

        async def _run(single_query: dict[str, Any]) -> None:
            async with semaphore:
                async for listing in self.iterate(
                    query=single_query, limit=limit_per_query
                ):
                    results.append(listing)

        await asyncio.gather(*(_run(q) for q in queries))
        return results


__all__ = ["BaseScraper"]
