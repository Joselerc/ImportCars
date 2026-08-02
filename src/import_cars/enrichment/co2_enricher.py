from __future__ import annotations

from typing import Any

from ..models import NormalizedListing
from .co2_memory import load_co2_memory, save_co2_memory, upsert_co2_memory
from .signature import (
    build_co2_memory_key,
    build_model_key,
    build_variant_key,
    build_vehicle_signature,
    normalize_fuel_category,
    normalize_text,
)


def _listing_year(listing: NormalizedListing) -> int | None:
    return (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )


def _memory_payload(listing: NormalizedListing) -> dict[str, Any]:
    return {
        "make": listing.make,
        "model": listing.model,
        "model_key": build_model_key(listing.model),
        "variant_key": build_variant_key(listing),
        "year": _listing_year(listing),
        "fuel_type": normalize_fuel_category(listing.fuel_type),
        "power_hp": listing.power_hp,
        "engine_displacement_cc": listing.engine_displacement_cc,
        "transmission": normalize_text(listing.transmission),
    }


class Co2Enricher:
    def enrich(self, listings: list[NormalizedListing]) -> list[NormalizedListing]:
        memory = load_co2_memory()
        batch_memory = dict(memory)
        memory_changed = False

        for listing in listings:
            listing.vehicle_signature = build_vehicle_signature(listing)
            listing.variant_key = build_variant_key(listing)
            memory_key = build_co2_memory_key(listing)
            observed_in_listing = (
                listing.co2_emissions_g_km is not None
                and listing.co2_source_type in {"listing", "original"}
                and listing.source not in {"manual", "user", "public"}
            )
            if observed_in_listing:
                listing.co2_original_g_km = listing.co2_emissions_g_km
                listing.co2_source_type = "listing"
                listing.co2_confidence = 1.0
                if memory_key is not None:
                    upsert_co2_memory(
                        batch_memory,
                        signature=memory_key,
                        payload=_memory_payload(listing)
                        | {"version": listing.version},
                        co2=listing.co2_emissions_g_km,
                    )
                    memory_changed = True

        for listing in listings:
            if listing.co2_emissions_g_km is not None:
                continue

            if normalize_fuel_category(listing.fuel_type) == "electric":
                listing.co2_emissions_g_km = 0
                listing.co2_inferred_g_km = 0
                listing.co2_source_type = "electric_zero"
                listing.co2_confidence = 1.0
                continue

            memory_key = build_co2_memory_key(listing)
            exact = batch_memory.get(memory_key) if memory_key else None
            if exact and exact.get("co2_avg") is not None:
                inferred = round(float(exact["co2_avg"]))
                listing.co2_inferred_g_km = inferred
                listing.co2_emissions_g_km = inferred
                listing.co2_source_type = "memory"
                listing.co2_confidence = 0.9
                continue

            listing.co2_source_type = "missing"
            listing.co2_confidence = 0.0

        if memory_changed:
            save_co2_memory(batch_memory)
        return listings
