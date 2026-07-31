"""
Fuel type mappings for different scraping sources
"""

# Coches.net fuel type IDs
COCHES_NET_FUEL_TYPES = {
    "gasoline": 2,
    "diesel": 1,
    "electric": 3,
    "hybrid": 4,
    "hybrid_plug_in": 5,
    "lpg": 6,
    "cng": 7,
    "hydrogen": 8,
}

# Mobile.de fuel type codes (from URL parameters)
MOBILE_DE_FUEL_TYPES = {
    "gasoline": "PETROL",
    "diesel": "DIESEL",
    "electric": "ELECTRIC",
    "hybrid": "HYBRID",
    "lpg": "LPG",
    "cng": "CNG",
    "hydrogen": "HYDROGEN",
}
