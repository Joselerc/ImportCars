"""Normalize portal-specific body labels without using make or brand."""

from __future__ import annotations

import unicodedata


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char))
        .casefold()
        .replace("-", " ")
        .replace("/", " ")
        .split()
    )


def _matches(body: str, patterns: tuple[str, ...]) -> bool:
    words = set(body.split())
    return any(pattern in body if " " in pattern else pattern in words for pattern in patterns)


def normalize_body_type(value: str | None) -> str | None:
    """Return one transport category, or ``None`` when it is unknown."""

    if not value:
        return None
    body = _plain(value)
    if _matches(body, ("suv", "offroad", "todoterreno", "gelandewagen")):
        return "suv"
    if _matches(body, ("monovolumen", "minivan", "multi purpose", "van")):
        return "monovolumen"
    if _matches(
        body,
        (
            "deportivo",
            "sports car",
            "sportscar",
            "sportwagen",
            "coupe",
            "cabrio",
            "roadster",
        ),
    ):
        return "deportivo_gama_alta"
    if _matches(body, ("familiar", "estate", "estatecar", "station wagon", "kombi")):
        return "familiar"
    if _matches(
        body,
        (
            "turismo",
            "berlina",
            "sedan",
            "saloon",
            "limousine",
            "hatchback",
            "compact",
            "small car",
            "smallcar",
        ),
    ):
        return "turismo"
    return None


__all__ = ["normalize_body_type"]
