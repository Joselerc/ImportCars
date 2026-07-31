from __future__ import annotations

import re

from .enrichment.signature import normalize_fuel_category, normalize_text
from .filters import UnifiedFilters
from .models import NormalizedListing


def _contains_normalized(haystack: str | None, needle: str) -> bool:
    normalized = normalize_text(haystack)
    return re.search(rf"(?:^|_){re.escape(needle)}(?:_|$)", normalized) is not None


def _matches_range(value, range_filter, minimum_name: str, maximum_name: str) -> bool:
    if value is None:
        return False
    minimum = getattr(range_filter, minimum_name)
    maximum = getattr(range_filter, maximum_name)
    return (minimum is None or value >= minimum) and (
        maximum is None or value <= maximum
    )


def listing_matches_filters(
    listing: NormalizedListing, filters: UnifiedFilters | None
) -> bool:
    """Aplica la misma política local de filtros a ambos mercados."""
    if filters is None:
        return True

    if filters.make and normalize_text(listing.make) != normalize_text(filters.make):
        return False

    if filters.model:
        desired_model = normalize_text(filters.model)
        if not (
            _contains_normalized(listing.model, desired_model)
            or _contains_normalized(listing.title, desired_model)
        ):
            return False

    if filters.version:
        desired_version = normalize_text(filters.version)
        if not (
            _contains_normalized(listing.version, desired_version)
            or _contains_normalized(listing.title, desired_version)
        ):
            return False

    if filters.price_range and not _matches_range(
        listing.price_eur,
        filters.price_range,
        "min_price",
        "max_price",
    ):
        return False

    year = (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )
    if filters.year_range and not _matches_range(
        year, filters.year_range, "min_year", "max_year"
    ):
        return False

    if filters.mileage_range and not _matches_range(
        listing.mileage_km,
        filters.mileage_range,
        "min_mileage",
        "max_mileage",
    ):
        return False

    if filters.power_range and not _matches_range(
        listing.power_hp,
        filters.power_range,
        "min_power_hp",
        "max_power_hp",
    ):
        return False

    if filters.fuel_types:
        accepted_fuels = {
            normalize_fuel_category(item.value) for item in filters.fuel_types
        }
        if normalize_fuel_category(listing.fuel_type) not in accepted_fuels:
            return False

    if filters.transmissions:
        transmission = normalize_text(listing.transmission)
        accepted = {normalize_text(item.value) for item in filters.transmissions}
        aliases = {
            "automatic": {"automatic", "automatico", "automatik"},
            "manual": {"manual", "cambio_manual", "schaltgetriebe"},
            "semi_automatic": {"semi_automatic", "semiautomatico"},
        }
        if not any(transmission in aliases.get(item, {item}) for item in accepted):
            return False

    if filters.body_types:
        accepted_bodies = {normalize_text(item.value) for item in filters.body_types}
        if normalize_text(listing.body_type) not in accepted_bodies:
            return False

    if filters.min_doors is not None and (
        listing.doors is None or listing.doors < filters.min_doors
    ):
        return False
    if filters.max_doors is not None and (
        listing.doors is None or listing.doors > filters.max_doors
    ):
        return False
    if filters.min_seats is not None and (
        listing.seats is None or listing.seats < filters.min_seats
    ):
        return False
    if filters.max_seats is not None and (
        listing.seats is None or listing.seats > filters.max_seats
    ):
        return False

    if filters.country_code:
        country = listing.location.country_code if listing.location else None
        if normalize_text(country) != normalize_text(filters.country_code):
            return False

    seller_type = normalize_text(listing.seller.type if listing.seller else None)
    if filters.dealer_only and seller_type != "dealer":
        return False
    if filters.private_only and seller_type != "private":
        return False
    if filters.with_images and not listing.images:
        return False
    return not (filters.certified_only and not listing.metadata.certified)


def _range_signature(value, minimum_name: str, maximum_name: str):
    if value is None:
        return None
    return (getattr(value, minimum_name), getattr(value, maximum_name))


def equivalent_vehicle_criteria(left: UnifiedFilters, right: UnifiedFilters) -> bool:
    """Compara los criterios que determinan si dos búsquedas son homologables.

    Los precios y el tipo de vendedor pueden variar por mercado; la identidad y
    las especificaciones del vehículo no.
    """
    left_identity = (
        normalize_text(left.make),
        normalize_text(left.model),
        normalize_text(left.version),
    )
    right_identity = (
        normalize_text(right.make),
        normalize_text(right.model),
        normalize_text(right.version),
    )
    if left_identity != right_identity:
        return False

    left_technical = (
        _range_signature(left.year_range, "min_year", "max_year"),
        _range_signature(left.mileage_range, "min_mileage", "max_mileage"),
        _range_signature(left.power_range, "min_power_hp", "max_power_hp"),
        frozenset(item.value for item in left.fuel_types or []),
        frozenset(item.value for item in left.transmissions or []),
        frozenset(item.value for item in left.body_types or []),
        left.min_doors,
        left.max_doors,
        left.min_seats,
        left.max_seats,
    )
    right_technical = (
        _range_signature(right.year_range, "min_year", "max_year"),
        _range_signature(right.mileage_range, "min_mileage", "max_mileage"),
        _range_signature(right.power_range, "min_power_hp", "max_power_hp"),
        frozenset(item.value for item in right.fuel_types or []),
        frozenset(item.value for item in right.transmissions or []),
        frozenset(item.value for item in right.body_types or []),
        right.min_doors,
        right.max_doors,
        right.min_seats,
        right.max_seats,
    )
    return left_technical == right_technical


__all__ = ["equivalent_vehicle_criteria", "listing_matches_filters"]
