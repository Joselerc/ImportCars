from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

MEMORY_DIR = Path.home() / ".cache" / "import_cars"
MEMORY_PATH = MEMORY_DIR / "co2_memory.json"


def load_co2_memory() -> Dict[str, Dict[str, Any]]:
    if not MEMORY_PATH.exists():
        return {}
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_co2_memory(memory: Dict[str, Dict[str, Any]]) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_co2_memory(memory: Dict[str, Dict[str, Any]], *, signature: str, payload: Dict[str, Any], co2: int) -> None:
    entry = memory.get(signature)
    if entry is None:
        payload = payload | {"samples": 1, "co2_min": co2, "co2_max": co2, "co2_avg": float(co2)}
        memory[signature] = payload
        return

    samples = int(entry.get("samples", 0)) + 1
    avg = ((float(entry.get("co2_avg", co2)) * (samples - 1)) + co2) / samples
    entry["samples"] = samples
    entry["co2_min"] = min(int(entry.get("co2_min", co2)), co2)
    entry["co2_max"] = max(int(entry.get("co2_max", co2)), co2)
    entry["co2_avg"] = round(avg, 2)
