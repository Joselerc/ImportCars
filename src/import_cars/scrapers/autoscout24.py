from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from selectolax.parser import HTMLParser

from ..enrichment.signature import normalize_fuel_category
from ..filters import UnifiedFilters
from ..matching import listing_matches_filters
from ..models import (
    ListingMetadata,
    Location,
    NormalizedListing,
    Price,
    Registration,
    SearchResult,
    Seller,
)
from .base import BaseScraper

_FUEL_ROUTE = {
    "gasoline": "ft_gasolina",
    "diesel": "ft_diésel",
    "electric": "ft_eléctrico",
    "hybrid": "ve_hybrid",
    "hybrid_gasoline": "ve_hybrid",
    "hybrid_diesel": "ve_hybrid",
    "lpg": "ft_autogás-glp",
    "cng": "ft_gas-natural-gnc",
    "hydrogen": "ft_hidrógeno",
    "ethanol": "ft_etanol",
}


def _slug(value: str | None) -> str:
    if not value:
        return ""
    ascii_value = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\d[\d.\s]*", str(value).replace("\u00a0", " "))
    return int(re.sub(r"\D", "", match.group(0))) if match else None


def _registration(value: str | None) -> Registration | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})[-/](\d{4})", value)
    return (
        Registration(year=int(match.group(2)), month=int(match.group(1)))
        if match
        else None
    )


def _power(details: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    for detail in details:
        if detail.get("iconName") != "speedometer":
            continue
        value = str(detail.get("data") or "")
        match = re.search(r"(\d+)\s*kW(?:\s*\((\d+)\s*(?:CV|PS|hp)\))?", value, re.IGNORECASE)
        if match:
            kw = int(match.group(1))
            hp = int(match.group(2)) if match.group(2) else round(kw * 1.35962)
            return kw, hp
    return None, None


def _displacement(vehicle: dict[str, Any], fuel: str | None) -> int | None:
    if normalize_fuel_category(fuel) == "electric":
        return None
    text = " ".join(
        str(vehicle.get(key) or "")
        for key in ("motorTypeName", "modelVersionInput", "modelVersionCustom")
    )
    match = re.search(r"(?:^|\s)(\d{1,2})[.,](\d)(?:\s|[A-Za-z])", text)
    if not match:
        return None
    return int(match.group(1)) * 1_000 + int(match.group(2)) * 100


class AutoScout24Scraper(BaseScraper):
    """Read AutoScout24 Spain's structured Next.js search payload."""

    base_url = "https://www.autoscout24.es"

    def __init__(self) -> None:
        super().__init__()
        self.headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/142.0.0.0 Safari/537.36"
            ),
        }

    def _build_search_url(self, filters: UnifiedFilters, page: int) -> str:
        parts = ["lst"]
        if filters.make:
            parts.append(_slug(filters.make))
        if filters.model:
            parts.append(_slug(filters.model))
        if filters.fuel_types and len(filters.fuel_types) == 1:
            route = _FUEL_ROUTE.get(filters.fuel_types[0].value)
            if route:
                parts.append(route)

        params: dict[str, str | int] = {
            "atype": "C",
            "cy": "E",
            "damaged_listing": "exclude",
            "desc": 0,
            "sort": "standard",
            "ustate": "N,U",
        }
        if page > 1:
            params["page"] = page
        if filters.year_range:
            if filters.year_range.min_year is not None:
                params["fregfrom"] = filters.year_range.min_year
            if filters.year_range.max_year is not None:
                params["fregto"] = filters.year_range.max_year
        if filters.mileage_range:
            if filters.mileage_range.min_mileage is not None:
                params["kmfrom"] = filters.mileage_range.min_mileage
            if filters.mileage_range.max_mileage is not None:
                params["kmto"] = filters.mileage_range.max_mileage
        if filters.power_range:
            params["powertype"] = "kw"
            if filters.power_range.min_power_hp is not None:
                params["powerfrom"] = math.floor(
                    filters.power_range.min_power_hp / 1.35962
                )
            if filters.power_range.max_power_hp is not None:
                params["powerto"] = math.ceil(
                    filters.power_range.max_power_hp / 1.35962
                )
        path = "/".join(quote(part, safe="-") for part in parts)
        return f"{self.base_url}/{path}?{urlencode(params)}"

    async def _fetch_page(self, url: str) -> str:
        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=self.settings.request_timeout,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    @staticmethod
    def _page_payload(html: str) -> dict[str, Any] | None:
        node = HTMLParser(html).css_first("script#__NEXT_DATA__")
        if node is None:
            return None
        try:
            data = json.loads(node.text())
        except (json.JSONDecodeError, TypeError):
            return None
        page = data.get("props", {}).get("pageProps")
        return page if isinstance(page, dict) else None

    def _to_listing(self, item: dict[str, Any]) -> NormalizedListing | None:
        try:
            listing_id = str(item["id"])
            vehicle = item.get("vehicle") or {}
            details = item.get("vehicleDetails") or []
            tracking = item.get("tracking") or {}
            price_eur = (item.get("price") or {}).get("priceRaw")
            if price_eur is None:
                return None

            ev_type = str((item.get("evBanner") or {}).get("type") or "").casefold()
            fuel = vehicle.get("fuel")
            if ev_type == "electric":
                fuel = "Eléctrico"
            elif ev_type in {"hybrid", "plugin-hybrid", "plug-in-hybrid"}:
                fuel = "Híbrido"

            registration = _registration(tracking.get("firstRegistration"))
            if registration is None:
                for detail in details:
                    if detail.get("iconName") == "calendar":
                        registration = _registration(str(detail.get("data") or ""))
                        break
            power_kw, power_hp = _power(details)
            mileage = _integer(tracking.get("mileage") or vehicle.get("mileageInKm"))
            version = (
                vehicle.get("modelVersionInput")
                or vehicle.get("modelVersionCustom")
                or vehicle.get("motorTypeName")
            )
            make = vehicle.get("make")
            model = vehicle.get("model") or vehicle.get("modelGroup")
            title = " ".join(str(value) for value in (make, model, version) if value)

            seller_data = item.get("seller") or {}
            seller_type = str(seller_data.get("type") or "").casefold()
            location_data = item.get("location") or {}
            relative_url = str(item.get("url") or "")
            url = (
                f"{self.base_url}{relative_url}"
                if relative_url.startswith("/")
                else relative_url
            )
            return NormalizedListing(
                listing_id=listing_id,
                source="autoscout24",
                url=url,
                scraped_at=datetime.now(UTC),
                title=title or None,
                make=make,
                model=model,
                version=version,
                price_eur=float(price_eur),
                price_original=Price(amount=float(price_eur), currency_code="EUR"),
                mileage_km=mileage,
                first_registration=registration,
                fuel_type=fuel,
                transmission=vehicle.get("transmission"),
                power_hp=power_hp,
                power_kw=power_kw,
                engine_displacement_cc=_displacement(vehicle, fuel),
                images=list(item.get("images") or [])[:8],
                location=(
                    Location(
                        country_code=location_data.get("countryCode") or "ES",
                        city=location_data.get("city"),
                        postal_code=location_data.get("zip"),
                    )
                    if location_data
                    else Location(country_code="ES")
                ),
                seller=Seller(
                    type="private" if seller_type == "private" else "dealer",
                    name=seller_data.get("companyName") or seller_data.get("contactName"),
                    dealer_id=str(seller_data.get("id") or "") or None,
                ),
                metadata=ListingMetadata(
                    vehicle_id=listing_id,
                    advert_type=vehicle.get("offerType"),
                    source_transmission=vehicle.get("transmission"),
                    source_trim_line=version,
                ),
            )
        except (KeyError, TypeError, ValueError):
            return None

    async def search(
        self,
        query: dict[str, Any] | UnifiedFilters,
        limit: int | None = None,
    ) -> SearchResult:
        filters = UnifiedFilters(**query) if isinstance(query, dict) else query
        desired = limit or filters.page_size
        page = filters.page
        listings: list[NormalizedListing] = []
        total = 0
        total_pages = 1

        while page <= total_pages and len(listings) < desired:
            html = await self._fetch_page(self._build_search_url(filters, page))
            payload = self._page_payload(html)
            if payload is None:
                break
            total = int(payload.get("numberOfResults") or 0)
            total_pages = max(1, int(payload.get("numberOfPages") or 1))
            for item in payload.get("listings") or []:
                listing = self._to_listing(item)
                if listing and listing_matches_filters(listing, filters):
                    listings.append(listing)
                    if len(listings) >= desired:
                        break
            page += 1

        return SearchResult(
            listings=listings,
            total_listings=total,
            result_page=max(filters.page, page - 1),
            result_page_size=len(listings),
            has_next=page <= total_pages,
        )


__all__ = ["AutoScout24Scraper"]
