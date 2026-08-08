from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from ..enrichment.signature import (
    build_engine_key,
    build_model_key,
    build_variant_key,
    normalize_fuel_category,
    normalize_text,
)
from ..models import NormalizedListing

BATTERY_MATCH_TOLERANCE_KWH = 5.0


def _listing_year(listing: NormalizedListing) -> int | None:
    return (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )


def build_market_key(listing: NormalizedListing) -> str:
    make = normalize_text(listing.make)
    fuel = normalize_fuel_category(listing.fuel_type)
    return f"{make}|{build_model_key(listing.model)}|{fuel or 'na'}"


def _preferred_break_even(
    listing: NormalizedListing, break_even_data: dict[str, float]
) -> float | None:
    if listing.seller and listing.seller.type == "private":
        return break_even_data.get("particular")
    return (
        break_even_data.get("empresa_iva")
        or break_even_data.get("empresa_margen")
        or break_even_data.get("particular")
    )


@dataclass(frozen=True)
class CriterionDecision:
    outcome: str
    note: str


@dataclass(frozen=True)
class ComparableMatchDecision:
    level: str | None
    checks: dict[str, CriterionDecision]


def _transmission_kind(listing: NormalizedListing) -> str | None:
    value = normalize_text(
        listing.transmission or listing.metadata.source_transmission
    )
    if value in {"automatic", "automatico", "automatik"}:
        return "automatic"
    if value in {"manual", "cambio_manual", "schaltgetriebe"}:
        return "manual"
    if value in {"semi_automatic", "semiautomatico"}:
        return "semi_automatic"
    return None


def _power_hp(listing: NormalizedListing) -> int | None:
    if listing.power_hp is not None:
        return listing.power_hp
    if listing.power_kw is not None:
        return round(listing.power_kw * 1.35962)
    return None


def match_decision(
    target: NormalizedListing,
    candidate: NormalizedListing,
) -> ComparableMatchDecision:
    """Clasifica un comparable con una política estricta y auditable."""

    checks: dict[str, CriterionDecision] = {}
    target_make = normalize_text(target.make)
    candidate_make = normalize_text(candidate.make)
    make_matches = target_make != "na" and target_make == candidate_make
    checks["make"] = CriterionDecision(
        "match" if make_matches else "mismatch",
        "Marca normalizada coincidente." if make_matches else "La marca no coincide.",
    )
    target_model = build_model_key(target.model)
    candidate_model = build_model_key(candidate.model)
    model_matches = target_model != "na" and target_model == candidate_model
    checks["model"] = CriterionDecision(
        "match" if model_matches else "mismatch",
        "Familia de modelo coincidente."
        if model_matches
        else "La familia de modelo no coincide.",
    )
    target_fuel = normalize_fuel_category(target.fuel_type)
    candidate_fuel = normalize_fuel_category(candidate.fuel_type)
    fuel_matches = target_fuel != "na" and target_fuel == candidate_fuel
    checks["fuel"] = CriterionDecision(
        "match" if fuel_matches else "mismatch",
        "Combustible coincidente."
        if fuel_matches
        else "El combustible no coincide o no está disponible.",
    )
    if not (make_matches and model_matches and fuel_matches):
        return ComparableMatchDecision(None, checks)

    target_engine = build_engine_key(target)
    candidate_engine = build_engine_key(candidate)
    known_engine_conflict = (
        target_engine != "na"
        and candidate_engine != "na"
        and target_engine != candidate_engine
    )

    target_cc = target.engine_displacement_cc
    candidate_cc = candidate.engine_displacement_cc
    cc_delta = (
        abs(target_cc - candidate_cc)
        if target_cc is not None and candidate_cc is not None
        else None
    )
    target_power = _power_hp(target)
    candidate_power = _power_hp(candidate)
    power_delta = (
        abs(target_power - candidate_power)
        if target_power is not None and candidate_power is not None
        else None
    )
    same_engine_key = target_engine != "na" and target_engine == candidate_engine
    electric = target_fuel == "electric"
    exact_motor = (
        same_engine_key
        and (electric or (cc_delta is not None and cc_delta <= 150))
        and power_delta is not None
        and power_delta <= 15
    )
    near_motor = (
        same_engine_key
        and (electric or (cc_delta is not None and cc_delta <= 300))
        and power_delta is not None
        and power_delta <= 30
    )
    beyond_technical_limit = (
        (cc_delta is not None and cc_delta > 500)
        or (
            power_delta is not None
            and target_power is not None
            and power_delta > max(60, int(target_power * 0.25))
        )
    )
    if known_engine_conflict:
        checks["version"] = CriterionDecision(
            "mismatch",
            f"Motorización incompatible: {target_engine} frente a {candidate_engine}.",
        )
        return ComparableMatchDecision(None, checks)
    if beyond_technical_limit:
        checks["version"] = CriterionDecision(
            "mismatch",
            "La diferencia técnica de cilindrada o potencia es demasiado grande.",
        )
        return ComparableMatchDecision(None, checks)

    target_year = _listing_year(target)
    candidate_year = _listing_year(candidate)
    year_delta = (
        abs(target_year - candidate_year)
        if target_year is not None and candidate_year is not None
        else None
    )
    if year_delta is None:
        checks["year"] = CriterionDecision(
            "unavailable",
            "No se puede comparar la generación porque falta el año.",
        )
        return ComparableMatchDecision(None, checks)

    target_mileage = target.mileage_km
    candidate_mileage = candidate.mileage_km
    mileage_delta = (
        abs(target_mileage - candidate_mileage)
        if target_mileage is not None and candidate_mileage is not None
        else None
    )
    if mileage_delta is None:
        checks["mileage"] = CriterionDecision(
            "unavailable",
            "No entra en ningún nivel porque falta el kilometraje.",
        )
        return ComparableMatchDecision(None, checks)

    target_transmission = _transmission_kind(target)
    candidate_transmission = _transmission_kind(candidate)
    transmission_matches = (
        target_transmission is not None
        and target_transmission == candidate_transmission
    )

    battery_required = target_fuel in {"electric", "phev"}
    target_battery = target.battery_capacity_kwh
    candidate_battery = candidate.battery_capacity_kwh
    battery_delta = (
        abs(target_battery - candidate_battery)
        if target_battery is not None and candidate_battery is not None
        else None
    )
    battery_matches = (
        not battery_required
        or battery_delta is not None
        and battery_delta <= BATTERY_MATCH_TOLERANCE_KWH
    )

    if (
        exact_motor
        and year_delta <= 1
        and mileage_delta <= 15_000
        and transmission_matches
        and battery_matches
    ):
        level = "exact"
    elif (
        near_motor
        and year_delta <= 2
        and mileage_delta <= 35_000
        and battery_matches
    ):
        level = "near"
    elif year_delta <= 4 and mileage_delta <= 60_000:
        level = "broad"
    else:
        level = None

    if (exact_motor and level == "exact") or (near_motor and level == "near"):
        engine_outcome = "match"
    elif same_engine_key:
        engine_outcome = "relaxed"
    else:
        engine_outcome = "unavailable"
    checks["version"] = CriterionDecision(
        engine_outcome,
        (
            f"Motorización {target_engine} coincidente; diferencia de potencia "
            f"{power_delta} CV."
            if same_engine_key
            else "Motorización no identificable en ambos anuncios; solo permite nivel amplio."
        ),
    )
    checks["year"] = CriterionDecision(
        "match" if level in {"exact", "near"} else "relaxed" if level == "broad" else "mismatch",
        f"Diferencia de {year_delta} año(s); límites: exact 1, near 2, broad 4.",
    )
    formatted_mileage_delta = f"{mileage_delta:,}".replace(",", ".")
    checks["mileage"] = CriterionDecision(
        "match" if level else "mismatch",
        f"Diferencia de {formatted_mileage_delta} km; límites: exact 15.000, "
        "near 35.000, broad 60.000.",
    )
    if target_transmission is None or candidate_transmission is None:
        transmission_outcome = "unavailable"
        transmission_note = "Falta el cambio en uno de los anuncios; nunca puede ser exact."
    elif transmission_matches:
        transmission_outcome = "match"
        transmission_note = "Mismo tipo de cambio."
    else:
        transmission_outcome = "relaxed" if level in {"near", "broad"} else "mismatch"
        transmission_note = (
            "Cambio distinto: admitido con menor calidad en near/broad; nunca ajusta el precio."
        )
    checks["transmission"] = CriterionDecision(
        transmission_outcome,
        transmission_note,
    )
    if not battery_required:
        battery_outcome = "unavailable"
        battery_note = "La batería no interviene en vehículos no eléctricos/PHEV."
    elif battery_delta is None:
        battery_outcome = "unavailable"
        battery_note = (
            "Falta la capacidad de batería en uno de los anuncios; "
            "solo puede alcanzar nivel broad."
        )
    elif battery_matches:
        battery_outcome = "match"
        battery_note = (
            f"Diferencia de {battery_delta:.1f} kWh; tolerancia máxima "
            f"±{BATTERY_MATCH_TOLERANCE_KWH:.0f} kWh."
        )
    else:
        battery_outcome = "relaxed" if level == "broad" else "mismatch"
        battery_note = (
            f"Baterías incompatibles: diferencia de {battery_delta:.1f} kWh; "
            "solo se admite como broad orientativo."
        )
    checks["battery"] = CriterionDecision(battery_outcome, battery_note)
    return ComparableMatchDecision(level, checks)


def match_level(target: NormalizedListing, candidate: NormalizedListing) -> str | None:
    return match_decision(target, candidate).level


def preferred_level_matches(
    matches: list[tuple[NormalizedListing, ComparableMatchDecision]],
    level: str,
) -> list[tuple[NormalizedListing, ComparableMatchDecision]]:
    """En near, usa el mismo cambio cuando existe; nunca corrige su precio."""
    if level != "near":
        return matches
    same_transmission = [
        item
        for item in matches
        if item[1].checks.get("transmission")
        and item[1].checks["transmission"].outcome == "match"
    ]
    return same_transmission or matches


def apply_opportunity_analysis(
    mobile_listings: list[NormalizedListing],
    coches_listings: list[NormalizedListing],
    break_even_data: dict[str, dict[str, float]],
) -> list[dict]:
    opportunities = []

    for listing in mobile_listings:
        listing.variant_key = build_variant_key(listing)
        listing.market_key = build_market_key(listing)
    for listing in coches_listings:
        listing.variant_key = build_variant_key(listing)
        listing.market_key = build_market_key(listing)

    market_buckets: dict[str, list[NormalizedListing]] = {}
    for item in coches_listings:
        if item.price_eur is not None:
            market_buckets.setdefault(item.market_key, []).append(item)

    for listing in mobile_listings:
        exact: list[tuple[NormalizedListing, ComparableMatchDecision]] = []
        near: list[tuple[NormalizedListing, ComparableMatchDecision]] = []
        broad: list[tuple[NormalizedListing, ComparableMatchDecision]] = []
        for item in market_buckets.get(listing.market_key, []):
            decision = match_decision(listing, item)
            if decision.level == "exact":
                exact.append((item, decision))
            elif decision.level == "near":
                near.append((item, decision))
            elif decision.level == "broad":
                broad.append((item, decision))

        listing.es_exact_sample_size = len(exact)
        listing.es_near_sample_size = len(near)
        listing.es_broad_sample_size = len(broad)

        level_matches = exact or near or broad
        listing.comparable_match_level = (
            "exact" if exact else "near" if near else "broad" if broad else None
        )
        comparables = (
            preferred_level_matches(level_matches, listing.comparable_match_level)
            if listing.comparable_match_level
            else []
        )
        prices = [
            item.price_eur
            for item, _decision in comparables
            if item.price_eur is not None
        ]
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

        listing.best_break_even = round(
            preferred_break_even
            if preferred_break_even is not None
            else min(candidates),
            2,
        )
        listing.potential_margin_avg = round(
            listing.es_market_avg - listing.best_break_even, 2
        )
        listing.potential_margin_min = round(
            listing.es_market_min - listing.best_break_even, 2
        )

        safety_gap = max(0, listing.best_break_even - listing.es_market_min)
        margin_score = (
            min(
                50, max(0, listing.potential_margin_avg / listing.best_break_even * 100)
            )
            if listing.best_break_even
            else 0
        )
        sample_score = min(listing.es_sample_size, 5) / 5 * 20
        confidence_score = min(1, max(0, listing.co2_confidence or 0)) * 10
        match_score = (
            20
            if listing.comparable_match_level == "exact"
            else 10
            if listing.comparable_match_level == "near"
            else 0
        )
        safety_penalty = (
            min(20, safety_gap / listing.best_break_even * 100)
            if listing.best_break_even
            else 20
        )
        listing.import_ready_score = round(
            min(
                100,
                max(
                    0,
                    margin_score
                    + sample_score
                    + confidence_score
                    + match_score
                    - safety_penalty,
                ),
            ),
            2,
        )

        if listing.potential_margin_avg > 0:
            opportunities.append(
                {
                    "listing": listing,
                    "break_even": listing.best_break_even,
                    "margen": listing.potential_margin_avg,
                    "rentabilidad": (
                        listing.potential_margin_avg / listing.best_break_even
                    )
                    * 100
                    if listing.best_break_even
                    else 0,
                    "muestras_es": listing.es_sample_size,
                }
            )

    opportunities.sort(
        key=lambda item: item["listing"].import_ready_score or 0, reverse=True
    )
    return opportunities
