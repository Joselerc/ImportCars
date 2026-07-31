"""
Mobile.de model mappings by make.
Auto-generated from mobile.de API.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

# Path to the JSON file
MODELS_FILE = (
    Path(__file__).parent.parent.parent.parent / "data" / "mobilede_models_by_make.json"
)


def load_models() -> Dict[str, List[Dict[str, any]]]:
    """Load models from JSON file"""
    if not MODELS_FILE.exists():
        return {}

    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Cache the models to avoid re-reading the file
_MODELS_CACHE: Optional[Dict[str, List[Dict[str, any]]]] = None


def get_models_for_make(make_id: int) -> List[Dict[str, any]]:
    """
    Get all models for a specific make ID.

    Args:
        make_id: The make ID (e.g., 3500 for BMW)

    Returns:
        List of model dictionaries with 'id' and 'name' keys
    """
    global _MODELS_CACHE

    if _MODELS_CACHE is None:
        _MODELS_CACHE = load_models()

    return _MODELS_CACHE.get(str(make_id), [])


def get_model_id_by_name(make_id: int, model_name: str) -> Optional[int]:
    """
    Get model ID by model name for a specific make.
    Case-insensitive search.

    Args:
        make_id: The make ID (e.g., 3500 for BMW)
        model_name: The model name to search for (e.g., "X5", "Serie 3")

    Returns:
        Model ID if found, None otherwise
    """
    models = get_models_for_make(make_id)
    model_name_lower = model_name.lower().strip()

    # Exact match first
    for model in models:
        if model["name"].lower() == model_name_lower:
            return model["id"]

    # Partial match (contains)
    for model in models:
        if model_name_lower in model["name"].lower():
            return model["id"]

    return None


def get_all_model_names_for_make(make_id: int) -> List[str]:
    """
    Get all model names for a specific make.

    Args:
        make_id: The make ID

    Returns:
        List of model names sorted alphabetically
    """
    models = get_models_for_make(make_id)
    return sorted([m["name"] for m in models])


# Export for convenience
MOBILE_DE_MODELS_BY_MAKE = load_models()
