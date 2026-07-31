"""
Coches.net model mappings by make.
Loaded from coches.net API data.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

# Path to the JSON file
MODELS_FILE = (
    Path(__file__).parent.parent.parent.parent
    / "data"
    / "cochesnet_models_by_make.json"
)


def load_models() -> List[Dict]:
    """Load models from JSON file (list format)"""
    if not MODELS_FILE.exists():
        return []

    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# Cache the models to avoid re-reading the file
_MODELS_CACHE: Optional[List[Dict]] = None


def get_make_by_name(make_name: str) -> Optional[Dict]:
    """
    Get make data by name.

    Args:
        make_name: The make name (e.g., "BMW", "Mercedes-Benz")

    Returns:
        Make dictionary with 'id', 'label', and 'models' keys, or None if not found
    """
    global _MODELS_CACHE

    if _MODELS_CACHE is None:
        _MODELS_CACHE = load_models()

    make_name_lower = make_name.lower().strip()

    # Exact match first
    for make in _MODELS_CACHE:
        if make["label"].lower() == make_name_lower:
            return make

    # Partial match
    for make in _MODELS_CACHE:
        if make_name_lower in make["label"].lower():
            return make

    return None


def get_models_for_make(make_name: str) -> List[Dict[str, str]]:
    """
    Get all models for a specific make name.

    Args:
        make_name: The make name (e.g., "BMW", "Mercedes-Benz")

    Returns:
        List of model dictionaries with 'id' and 'label' keys
    """
    make = get_make_by_name(make_name)
    if make:
        return make.get("models", [])
    return []


def get_model_id_by_name(make_name: str, model_name: str) -> Optional[str]:
    """
    Get model ID by model name for a specific make.
    Case-insensitive search.

    Args:
        make_name: The make name (e.g., "BMW", "Mercedes-Benz")
        model_name: The model name to search for (e.g., "X5", "Serie 3")

    Returns:
        Model ID if found, None otherwise
    """
    models = get_models_for_make(make_name)
    model_name_lower = model_name.lower().strip()

    # Exact match first
    for model in models:
        if model["label"].lower() == model_name_lower:
            return model["id"]

    # Partial match (contains)
    for model in models:
        if model_name_lower in model["label"].lower():
            return model["id"]

    return None


def get_make_id_by_name(make_name: str) -> Optional[str]:
    """
    Get make ID by name.

    Args:
        make_name: The make name (e.g., "BMW", "Mercedes-Benz")

    Returns:
        Make ID if found, None otherwise
    """
    make = get_make_by_name(make_name)
    if make:
        return make["id"]
    return None


def get_all_make_names() -> List[str]:
    """
    Get all make names.

    Returns:
        List of make names sorted alphabetically
    """
    global _MODELS_CACHE

    if _MODELS_CACHE is None:
        _MODELS_CACHE = load_models()

    return sorted([make["label"] for make in _MODELS_CACHE])


def get_all_model_names_for_make(make_name: str) -> List[str]:
    """
    Get all model names for a specific make.

    Args:
        make_name: The make name

    Returns:
        List of model names sorted alphabetically
    """
    models = get_models_for_make(make_name)
    return sorted([m["label"] for m in models])


# Export for convenience
COCHES_NET_MODELS_BY_MAKE = load_models()
