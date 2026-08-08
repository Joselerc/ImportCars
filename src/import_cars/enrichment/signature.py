from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..models import NormalizedListing


def normalize_text(value: str | None) -> str:
    if not value:
        return "na"
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value or "na"


def normalize_fuel_category(value: str | None) -> str:
    """Collapse noisy marketplace labels into one stable fuel category.

    mobile.de appends compatibility and energy-source notes to the base fuel
    (for example ``Gasolina, Indicado para E10``).  Classification must inspect
    semantic markers instead of requiring the complete label to equal a small
    alias table.  More specific categories intentionally run first: a hybrid
    label contains both ``gasolina`` and ``eléctrico`` but is still a hybrid.
    """

    normalized = normalize_text(value)
    if normalized == "na":
        return normalized

    tokens = set(normalized.split("_"))
    if tokens & {"lpg", "glp", "autogas", "flussiggas"}:
        return "lpg"
    if (
        tokens & {"cng", "gnc", "erdgas", "methan", "metano"}
        or "gas_natural" in normalized
    ):
        return "cng"
    if tokens & {"hydrogen", "hydrogenium", "hidrogeno", "wasserstoff"}:
        return "hydrogen"
    if tokens & {"ethanol", "etanol", "flexifuel"} or "flex_fuel" in normalized:
        return "ethanol"

    hybrid = bool(tokens & {"hybrid", "hibrido"}) or "mild_hybrid" in normalized
    if hybrid:
        if tokens & {"enchufable", "plugin", "plug"} or "plug_in" in normalized:
            return "phev"
        return "hybrid"

    if normalized == "di_esel" or any("diesel" in token for token in tokens):
        return "diesel"
    if tokens & {"gasolina", "gasoline", "benzin", "petrol"}:
        return "gasoline"
    if tokens & {"electrico", "elektrisch", "electric", "electricity", "strom"}:
        return "electric"
    return "other"


def _normalize_number(value: Any | None) -> str:
    return "na" if value in (None, "") else str(value)


def build_model_key(value: str | None) -> str:
    tokens = [
        token for token in normalize_text(value).split("_") if token and token != "na"
    ]
    if not tokens:
        return "na"
    if len(tokens) >= 2 and (tokens[0] in {"clase", "serie"} or len(tokens[0]) == 1):
        return "_".join(tokens[:2])
    return tokens[0]


def build_variant_key(listing: NormalizedListing) -> str:
    text = normalize_text(
        " ".join(filter(None, [listing.version, listing.title, listing.model]))
    )
    tokens = [token for token in text.split("_") if token and token != "na"]
    if not tokens:
        return "na"

    for token in tokens:
        match = re.search(r"(?:xdrive|sdrive)?(\d{2,3}[a-z]{1,2})$", token)
        if match:
            return match.group(1)

    for i, token in enumerate(tokens[:-1]):
        if token.isdigit() and tokens[i + 1] in {"d", "e", "i"}:
            return f"{token}{tokens[i + 1]}"
        if len(token) == 1 and tokens[i + 1].isdigit():
            suffix = (
                tokens[i + 2]
                if i + 2 < len(tokens) and tokens[i + 2] in {"d", "e", "i"}
                else ""
            )
            return f"{token}{tokens[i + 1]}{suffix}"

    for token in tokens:
        if re.fullmatch(r"[a-z]?\d{2,3}[a-z]?", token):
            return token

    return "na"


_ENGINE_FAMILY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(?:^|_)pure_?tech(?:_|$)", "puretech"),
    (r"(?:^|_)blue_?hdi(?:_|$)", "bluehdi"),
    (r"(?:^|_)e_?tsi(?:_|$)", "etsi"),
    (r"(?:^|_)e_?hybrid(?:_|$)", "ehybrid"),
    (r"(?:^|_)tfsi(?:_|$)", "tfsi"),
    (r"(?:^|_)tsi(?:_|$)", "tsi"),
    (r"(?:^|_)thp(?:_|$)", "thp"),
    (r"(?:^|_)hdi(?:_|$)", "hdi"),
    (r"(?:^|_)tce(?:_|$)", "tce"),
    (r"(?:^|_)dci(?:_|$)", "dci"),
    (r"(?:^|_)cdi(?:_|$)", "cdi"),
    (r"(?:^|_)crdi(?:_|$)", "crdi"),
    (r"(?:^|_)cdti(?:_|$)", "cdti"),
    (r"(?:^|_)multijet(?:_|$)", "multijet"),
    (r"(?:^|_)jtd(?:_|$)", "jtd"),
    (r"(?:^|_)ecoboost(?:_|$)", "ecoboost"),
    (r"(?:^|_)skyactiv(?:_|$)", "skyactiv"),
    (r"(?:^|_)d_?4d(?:_|$)", "d4d"),
)


def build_engine_key(listing: NormalizedListing) -> str:
    """Identidad conservadora de motorización para comparables de mercado.

    Combina la familia anunciada (THP, PureTech, TSI, 30d...) con la cilindrada
    estructurada. Una clave distinta es un conflicto real; la ausencia de clave
    solo permite llegar al nivel amplio.
    """

    fuel = normalize_fuel_category(listing.fuel_type)
    text = normalize_text(
        " ".join(filter(None, [listing.version, listing.title, listing.model]))
    )
    family = "electric" if fuel == "electric" else None
    if family is None:
        for pattern, value in _ENGINE_FAMILY_PATTERNS:
            if re.search(pattern, text):
                family = value
                break
    if family is None:
        variant = build_variant_key(listing)
        family = variant if variant != "na" else None
    if family is None:
        return "na"

    displacement = listing.engine_displacement_cc
    if displacement and fuel != "electric":
        displacement_band = int(round(displacement / 100.0) * 100)
        return f"{displacement_band}:{family}"
    return family


def build_vehicle_signature(listing: NormalizedListing) -> str:
    year = (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )
    return "|".join(
        [
            normalize_text(listing.make),
            build_model_key(listing.model),
            build_variant_key(listing),
            _normalize_number(year),
            normalize_fuel_category(listing.fuel_type),
            _normalize_number(listing.power_hp),
            _normalize_number(listing.engine_displacement_cc),
            normalize_text(listing.transmission),
        ]
    )


def build_co2_memory_key(listing: NormalizedListing) -> str | None:
    """Strict CO2 identity: make + model + advertised version + registration year."""

    year = (
        listing.first_registration.year
        if listing.first_registration
        else listing.production_year
    )
    if not listing.make or not listing.model or not listing.version or year is None:
        return None
    return "|".join(
        [
            normalize_text(listing.make),
            normalize_text(listing.model),
            normalize_text(listing.version),
            str(year),
        ]
    )
