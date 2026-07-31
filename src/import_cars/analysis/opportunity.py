from __future__ import annotations

from statistics import median
from typing import Dict, List, Optional

from ..models import NormalizedListing
from ..enrichment.signature import build_model_key, build_variant_key, normalize_fuel_category, normalize_text


def _listing_year(listing: NormalizedListing) -> Optional[int]:
    return listing.first_registration.year if listing.first_registration else listing.production_year


def build_market_key(listing: NormalizedListing) -> str:
    make = normalize_text(listing.make)
    fuel = normalize_fuel_category(listing.fuel_type)
    return f"{make}|{build_model_key(listing.model)}|{fuel or 'na'}"


def _preferred_break_even(listing: NormalizedListing, break_even_data: Dict[str, float]) -> Optional[float]:
    if listing.seller and listing.seller.type == "private":
        return break_even_data.get("particular")
    return break_even_data.get("empresa_iva") or break_even_data.get("empresa_margen") or break_even_data.get("particular")


def _match_level(target: NormalizedListing, candidate: NormalizedListing) -> Optional[str]:
    if build_market_key(target) != build_market_key(candidate):
        return None

    target_variant = build_variant_key(target)
    candidate_variant = build_variant_key(candidate)
    same_variant = target_variant != "na" and candidate_variant != "na" and target_variant == candidate_variant

    target_year = _listing_year(target)
    candidate_year = _listing_year(candidate)
    year_delta = abs(target_year - candidate_year) if target_year and candidate_year else None
    if year_delta is not None and year_delta > 4:
        return None

    cc_delta = None
    if target.engine_displacement_cc and candidate.engine_displacement_cc:
        cc_delta = abs(target.engine_displacement_cc - candidate.engine_displacement_cc)
        if cc_delta > 500:
            return None

    power_delta = None
    if target.power_hp and candidate.power_hp:
        power_delta = abs(target.power_hp - candidate.power_hp)
        if power_delta > max(60, int(target.power_hp * 0.25)):
            return None

    if same_variant and year_delta is not None and cc_delta is not None and power_delta is not None and year_delta <= 1 and cc_delta <= 150 and power_delta <= 15:
        return "exact"
    if same_variant and year_delta is not None and cc_delta is not None and power_delta is not None and year_delta <= 2 and cc_delta <= 300 and power_delta <= 30:
        return "near"
    if year_delta is not None and cc_delta is not None and power_delta is not None and year_delta <= 2 and cc_delta <= 200 and power_delta <= 20:
        return "near"
    return "broad" if same_variant or year_delta is not None else None


def apply_opportunity_analysis(
    mobile_listings: List[NormalizedListing],
    coches_listings: List[NormalizedListing],
    break_even_data: Dict[str, Dict[str, float]],
) -> List[dict]:
    opportunities = []

    for listing in mobile_listings:
        listing.variant_key = build_variant_key(listing)
        listing.market_key = build_market_key(listing)
    for listing in coches_listings:
        listing.variant_key = build_variant_key(listing)
        listing.market_key = build_market_key(listing)

    market_buckets: Dict[str, List[NormalizedListing]] = {}
    for item in coches_listings:
        if item.price_eur is not None:
            market_buckets.setdefault(item.market_key, []).append(item)

    for listing in mobile_listings:
        exact = []
        near = []
        broad = []
        for item in market_buckets.get(listing.market_key, []):
            level = _match_level(listing, item)
            if level == "exact":
                exact.append(item)
            elif level == "near":
                near.append(item)
            elif level == "broad":
                broad.append(item)

        listing.es_exact_sample_size = len(exact)
        listing.es_near_sample_size = len(near)
        listing.es_broad_sample_size = len(broad)

        comparables = exact or near or broad
        listing.comparable_match_level = "exact" if exact else "near" if near else "broad" if broad else None
        prices = [item.price_eur for item in comparables if item.price_eur is not None]
        listing.es_sample_size = len(prices)
        if not prices:
            continue

        listing.es_market_avg = round(sum(prices) / len(prices), 2)
        listing.es_market_median = round(median(prices), 2)
        listing.es_market_min = round(min(prices), 2)

        be_data = break_even_data.get(listing.listing_id, {})
        preferred_break_even = _preferred_break_even(listing, be_data)
        candidates = [value for value in be_data.values() if value is not None]
        if preferred_break_even is None and not candidates:
            continue

        listing.best_break_even = round(preferred_break_even if preferred_break_even is not None else min(candidates), 2)
        listing.potential_margin_avg = round(listing.es_market_avg - listing.best_break_even, 2)
        listing.potential_margin_min = round(listing.es_market_min - listing.best_break_even, 2)

        safety_gap = max(0, listing.best_break_even - listing.es_market_min)
        listing.import_ready_score = round(
            listing.potential_margin_avg
            + min(listing.es_sample_size, 5) * 300
            + (listing.co2_confidence or 0) * 200
            + (600 if listing.comparable_match_level == "exact" else 250 if listing.comparable_match_level == "near" else 0)
            - safety_gap * 0.35,
            2,
        )

        if listing.potential_margin_avg > 0:
            opportunities.append({
                "listing": listing,
                "break_even": listing.best_break_even,
                "margen": listing.potential_margin_avg,
                "rentabilidad": (listing.potential_margin_avg / listing.best_break_even) * 100 if listing.best_break_even else 0,
                "muestras_es": listing.es_sample_size,
            })

    opportunities.sort(key=lambda item: (item["listing"].import_ready_score or 0), reverse=True)
    return opportunities
