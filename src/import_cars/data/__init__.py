"""
Data mappings for car makes, models, fuel types, transmissions, etc.
"""

from .coches_net_makes import COCHES_NET_MAKES
from .mobile_de_makes import MOBILE_DE_MAKES
from .fuel_mappings import COCHES_NET_FUEL_TYPES, MOBILE_DE_FUEL_TYPES
from .transmission_mappings import (
    COCHES_NET_TRANSMISSION_TYPES,
    MOBILE_DE_TRANSMISSION_TYPES,
)

# Mobile.de models
from .mobile_de_models import (
    MOBILE_DE_MODELS_BY_MAKE,
    get_models_for_make as get_mobilede_models_for_make,
    get_model_id_by_name as get_mobilede_model_id_by_name,
    get_all_model_names_for_make as get_all_mobilede_model_names_for_make,
)

# Coches.net models
from .coches_net_models import (
    COCHES_NET_MODELS_BY_MAKE,
    get_models_for_make as get_cochesnet_models_for_make,
    get_model_id_by_name as get_cochesnet_model_id_by_name,
    get_make_id_by_name as get_cochesnet_make_id_by_name,
    get_all_model_names_for_make as get_all_cochesnet_model_names_for_make,
)

__all__ = [
    "COCHES_NET_MAKES",
    "MOBILE_DE_MAKES",
    "COCHES_NET_FUEL_TYPES",
    "MOBILE_DE_FUEL_TYPES",
    "COCHES_NET_TRANSMISSION_TYPES",
    "MOBILE_DE_TRANSMISSION_TYPES",
    # Mobile.de models
    "MOBILE_DE_MODELS_BY_MAKE",
    "get_mobilede_models_for_make",
    "get_mobilede_model_id_by_name",
    "get_all_mobilede_model_names_for_make",
    # Coches.net models
    "COCHES_NET_MODELS_BY_MAKE",
    "get_cochesnet_models_for_make",
    "get_cochesnet_model_id_by_name",
    "get_cochesnet_make_id_by_name",
    "get_all_cochesnet_model_names_for_make",
]
