from __future__ import annotations

import re
from typing import Any

_KWH_PATTERN = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*kwh\b",
    re.IGNORECASE,
)
_CAPACITY_KEYS = {
    "batterycapacity",
    "batterycapacityinkwh",
    "batterycapacitykwh",
    "usablebatterycapacity",
}


def _valid_capacity(value: float) -> float | None:
    return round(value, 2) if 1 <= value <= 250 else None


def _from_text(value: Any, *, unit_required: bool = True) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    match = _KWH_PATTERN.search(text)
    if match:
        return _valid_capacity(float(match.group(1).replace(",", ".")))
    if not unit_required:
        try:
            return _valid_capacity(float(text.replace(",", ".")))
        except ValueError:
            return None
    return None


def extract_battery_capacity_kwh(payload: Any) -> float | None:
    """Read a declared traction-battery capacity from structured marketplace JSON."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = re.sub(r"[^a-z]", "", str(key).casefold())
            if normalized_key in _CAPACITY_KEYS:
                capacity = _from_text(value, unit_required=False)
                if capacity is not None:
                    return capacity
        for value in payload.values():
            capacity = extract_battery_capacity_kwh(value)
            if capacity is not None:
                return capacity
        return None
    if isinstance(payload, list):
        for value in payload:
            capacity = extract_battery_capacity_kwh(value)
            if capacity is not None:
                return capacity
        return None
    return _from_text(payload)


__all__ = ["extract_battery_capacity_kwh"]
