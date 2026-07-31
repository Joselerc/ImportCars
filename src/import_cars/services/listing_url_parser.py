"""On-demand parser for public mobile.de and AutoScout24 listing URLs."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from curl_cffi import requests as cffi
from curl_cffi.requests.errors import RequestsError
from selectolax.parser import HTMLParser

from ..config import get_settings
from ..models import NormalizedListing, Registration, Seller
from ..scrapers.mobile_de_http import MobileDeHttpScraper


class ListingParseError(ValueError):
    """Raised when an allowed listing cannot be read reliably."""


_ALLOWED_HOSTS = {
    "mobile.de": "mobile",
    "www.mobile.de": "mobile",
    "suchen.mobile.de": "mobile",
    "autoscout24.de": "autoscout",
    "www.autoscout24.de": "autoscout",
    "autoscout24.com": "autoscout",
    "www.autoscout24.com": "autoscout",
}


def _number(value) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, dict):
        value = value.get("value") or value.get("valueReference")
    if value is None:
        return None
    match = re.search(r"-?[\d.,]+", str(value))
    if not match:
        return None
    normalized = match.group(0).replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _name(value) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        return _name(value.get("name"))
    return None


def _objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _registration(value) -> Registration | None:
    if not value:
        return None
    match = re.search(r"(?:(\d{1,2})\D+)?((?:19|20)\d{2})", str(value))
    if not match:
        return None
    month = int(match.group(1)) if match.group(1) else None
    return Registration(year=int(match.group(2)), month=month)


def _parse_autoscout_html(html: str, url: str) -> NormalizedListing:
    tree = HTMLParser(html)
    candidates = []
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            candidates.extend(_objects(json.loads(node.text())))
        except (json.JSONDecodeError, TypeError):
            continue
    vehicle = next(
        (
            item
            for item in candidates
            if str(item.get("@type", "")).casefold()
            in {"vehicle", "car", "product"}
            and (item.get("offers") or item.get("vehicleModelDate") or item.get("mileageFromOdometer"))
        ),
        None,
    )
    if vehicle is None:
        raise ListingParseError(
            "AutoScout24 no ha publicado datos estructurados suficientes; usa el formulario manual."
        )

    offers = vehicle.get("offers") if isinstance(vehicle.get("offers"), dict) else {}
    price = _number(offers.get("price") or vehicle.get("price"))
    if price is None:
        raise ListingParseError("No se pudo leer el precio del anuncio")
    title = _name(vehicle.get("name")) or "Anuncio AutoScout24"
    brand = _name(vehicle.get("brand") or vehicle.get("manufacturer"))
    model = _name(vehicle.get("model"))
    if not model and brand and title.casefold().startswith(brand.casefold()):
        model = title[len(brand) :].strip()

    engine = vehicle.get("vehicleEngine") if isinstance(vehicle.get("vehicleEngine"), dict) else {}
    displacement = _number(
        vehicle.get("vehicleEngineDisplacement") or engine.get("engineDisplacement")
    )
    power = _number(engine.get("enginePower") or vehicle.get("enginePower"))
    page_text = " ".join(tree.root.text(separator=" ").split())
    co2_match = re.search(
        r"CO(?:\s*2|₂)[^\d]{0,30}(\d{1,3})\s*g/km",
        page_text,
        re.IGNORECASE,
    )
    co2 = int(co2_match.group(1)) if co2_match else None
    fuel = _name(vehicle.get("fuelType"))
    mileage = _number(vehicle.get("mileageFromOdometer"))
    seller_data = offers.get("seller") if isinstance(offers.get("seller"), dict) else {}
    seller_is_dealer = str(seller_data.get("@type", "")).casefold() == "organization"
    vat_deductible = bool(
        re.search(r"MwSt\.?\s*ausweisbar|VAT\s+deductible", page_text, re.IGNORECASE)
    )
    listing_id = urlparse(url).path.rstrip("/").split("/")[-1] or "autoscout24"

    return NormalizedListing(
        listing_id=listing_id,
        source="autoscout24",
        url=url,
        scraped_at=datetime.now(UTC),
        title=title,
        make=brand,
        model=model,
        price_eur=price,
        vat_deductible=vat_deductible,
        mileage_km=int(mileage) if mileage is not None else None,
        first_registration=_registration(
            vehicle.get("dateVehicleFirstRegistered") or vehicle.get("vehicleModelDate")
        ),
        fuel_type=fuel,
        power_kw=int(power) if power is not None else None,
        engine_displacement_cc=int(displacement) if displacement is not None else None,
        co2_emissions_g_km=co2,
        co2_original_g_km=co2,
        co2_source_type="listing" if co2 is not None else None,
        co2_confidence=1.0 if co2 is not None else 0.0,
        seller=Seller(
            type="dealer" if seller_is_dealer else "private",
            name=_name(seller_data),
        ),
    )


def parse_listing_url(url: str) -> NormalizedListing:
    """Fetch one allow-listed listing; callers always retain manual fallback."""

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ListingParseError("Solo se admiten enlaces HTTPS de mobile.de o AutoScout24")
    source = _ALLOWED_HOSTS[parsed.hostname]
    if source == "mobile":
        listing_id = (parse_qs(parsed.query).get("id") or [None])[0]
        if not listing_id or not listing_id.isdigit():
            raise ListingParseError("El enlace de mobile.de no contiene un identificador valido")
        listing = MobileDeHttpScraper().get_listing(listing_id)
        if listing is None:
            raise ListingParseError(
                "mobile.de no ha devuelto los datos del anuncio; usa el formulario manual."
            )
        return listing

    settings = get_settings()
    try:
        response = cffi.get(
            url,
            headers={
                "User-Agent": settings.user_agent,
                "Accept-Language": "es-ES,es;q=0.9",
            },
            timeout=settings.request_timeout,
            impersonate="chrome",
        )
    except RequestsError as exc:
        raise ListingParseError(
            "No se pudo conectar con AutoScout24; usa el formulario manual."
        ) from exc
    if response.status_code != 200:
        raise ListingParseError(f"AutoScout24 ha respondido con HTTP {response.status_code}")
    return _parse_autoscout_html(response.text, url)


__all__ = ["ListingParseError", "parse_listing_url"]
