from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import NormalizedListing
from .co2_memory import load_co2_memory, save_co2_memory, upsert_co2_memory
from .signature import (
    build_model_key,
    build_variant_key,
    build_vehicle_signature,
    normalize_fuel_category,
    normalize_text,
)


def _listing_year(listing: NormalizedListing) -> Optional[int]:
    return (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )


def _memory_payload(listing: NormalizedListing) -> Dict[str, Any]:
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


def _near_match_score(
    listing: NormalizedListing, entry: Dict[str, Any]
) -> Optional[int]:
    if normalize_text(listing.make) != normalize_text(entry.get("make")):
        return None
    if build_model_key(listing.model) != (entry.get("model_key") or "na"):
        return None
    listing_variant = build_variant_key(listing)
    entry_variant = entry.get("variant_key") or "na"
    if (
        listing_variant != "na"
        and entry_variant != "na"
        and listing_variant != entry_variant
    ):
        return None
    if (
        listing.fuel_type
        and entry.get("fuel_type")
        and normalize_fuel_category(listing.fuel_type)
        != normalize_fuel_category(entry.get("fuel_type"))
    ):
        return None
    if (
        listing.transmission
        and entry.get("transmission")
        and normalize_text(listing.transmission)
        != normalize_text(entry.get("transmission"))
    ):
        return None

    score = 0
    year = _listing_year(listing)
    if year and entry.get("year") is not None:
        delta = abs(year - int(entry["year"]))
        if delta > 1:
            return None
        score += delta * 10
    if listing.power_hp and entry.get("power_hp") is not None:
        delta = abs(listing.power_hp - int(entry["power_hp"]))
        if delta > 10:
            return None
        score += delta
    if (
        listing.engine_displacement_cc
        and entry.get("engine_displacement_cc") is not None
    ):
        delta = abs(
            listing.engine_displacement_cc - int(entry["engine_displacement_cc"])
        )
        if delta > 250:
            return None
        score += delta // 25
    return score


class Co2Enricher:
    def enrich(self, listings: List[NormalizedListing]) -> List[NormalizedListing]:
        memory = load_co2_memory()
        batch_memory = dict(memory)

        for listing in listings:
            listing.vehicle_signature = build_vehicle_signature(listing)
            listing.variant_key = build_variant_key(listing)
            if listing.co2_emissions_g_km is not None:
                listing.co2_original_g_km = listing.co2_emissions_g_km
                listing.co2_source_type = "original"
                listing.co2_confidence = 1.0
                upsert_co2_memory(
                    batch_memory,
                    signature=listing.vehicle_signature,
                    payload=_memory_payload(listing),
                    co2=listing.co2_emissions_g_km,
                )

        for listing in listings:
            if listing.co2_emissions_g_km is not None:
                continue

            exact = batch_memory.get(listing.vehicle_signature)
            if exact and exact.get("co2_avg") is not None:
                inferred = int(round(float(exact["co2_avg"])))
                listing.co2_inferred_g_km = inferred
                listing.co2_emissions_g_km = inferred
                listing.co2_source_type = "signature_exact"
                listing.co2_confidence = 0.9
                continue

            best_match = None
            best_score = None
            for entry in batch_memory.values():
                score = _near_match_score(listing, entry)
                if score is None:
                    continue
                if best_score is None or score < best_score:
                    best_match = entry
                    best_score = score

            if best_match and best_match.get("co2_avg") is not None:
                inferred = int(round(float(best_match["co2_avg"])))
                listing.co2_inferred_g_km = inferred
                listing.co2_emissions_g_km = inferred
                listing.co2_source_type = "signature_near"
                listing.co2_confidence = 0.6
            else:
                listing.co2_source_type = "missing"
                listing.co2_confidence = 0.0

        save_co2_memory(batch_memory)
        return listings
