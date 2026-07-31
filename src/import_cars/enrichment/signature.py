from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

from ..models import NormalizedListing


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return "na"
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return value or "na"


def normalize_fuel_category(value: Optional[str]) -> str:
    normalized = normalize_text(value)
    mapping = {
        "benzin": "gasoline",
        "gasolina": "gasoline",
        "petrol": "gasoline",
        "diesel": "diesel",
        "diesel_mild_hybrid": "hybrid_diesel",
        "di_esel": "diesel",
        "electrico": "electric",
        "elektrisch": "electric",
        "electric": "electric",
        "hybrid": "hybrid",
        "hibrido": "hybrid",
        "hybrid_gasoline": "hybrid_gasoline",
        "hybrid_petrol": "hybrid_gasoline",
        "hibrido_gasolina": "hybrid_gasoline",
        "hybrid_diesel": "hybrid_diesel",
        "hibrido_diesel": "hybrid_diesel",
        "lpg": "lpg",
        "glp": "lpg",
        "cng": "cng",
        "gnc": "cng",
    }
    return mapping.get(normalized, normalized)


def _normalize_number(value: Optional[Any]) -> str:
    return "na" if value in (None, "") else str(value)


def build_model_key(value: Optional[str]) -> str:
    tokens = [
        token for token in normalize_text(value).split("_") if token and token != "na"
    ]
    if not tokens:
        return "na"
    if len(tokens) >= 2 and (tokens[0] in {"clase", "serie"} or len(tokens[0]) == 1):
        return "_".join(tokens[:2])
    return tokens[0]


def build_variant_key(listing: NormalizedListing) -> str:
    text = normalize_text(" ".join(filter(None, [listing.model, listing.title])))
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
