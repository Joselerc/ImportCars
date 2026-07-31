"""
URL builder utilities for different scraping sources
"""

from typing import Optional
from ..filters import UnifiedFilters
from ..data import (
    MOBILE_DE_MAKES,
    MOBILE_DE_FUEL_TYPES,
    MOBILE_DE_TRANSMISSION_TYPES,
    get_mobilede_model_id_by_name,
)


def build_mobile_de_search_url(filters: UnifiedFilters, page: int = 1) -> str:
    """
    Build mobile.de search URL from UnifiedFilters

    URL format: https://www.mobile.de/es/vehículos/buscar.html?params
    Parameters:
    - ms=MAKE_CODE;;MODEL_CODE (e.g., ms=3500;;21 for BMW Serie 3)
    - p=MIN:MAX (price range, e.g., p=1000:30000)
    - fr=MIN:MAX (first registration year, e.g., fr=2000:2020)
    - ml=MIN:MAX (mileage, e.g., ml=1000:20000)
    - cn=COUNTRY (e.g., cn=DE)
    - ft=FUEL_TYPE (e.g., ft=PETROL)
    - pw=MIN:MAX (power in kW, e.g., pw=100:250)
    - tr=TRANSMISSION (e.g., tr=AUTOMATIC_GEAR, tr=MANUAL_GEAR)
    - pageNumber=N (pagination, starts at 1)
    """
    base_url = "https://www.mobile.de/es/veh%C3%ADculos/buscar.html"

    params = [
        "isSearchRequest=true",
        "ref=quickSearch",
        "s=Car",
        "vc=Car",
    ]

    # Marca y modelo (ms=MAKE_CODE;;MODEL_CODE)
    if filters.make:
        make_code = MOBILE_DE_MAKES.get(filters.make.upper())
        if make_code:
            # Si se proporciona modelo, buscar su ID
            if filters.model:
                model_id = get_mobilede_model_id_by_name(make_code, filters.model)
                if model_id:
                    params.append(
                        f"ms={make_code}%3B{model_id}%3B"
                    )  # %3B es ; URL-encoded
                else:
                    # Si no se encuentra el modelo, solo usar la marca
                    params.append(f"ms={make_code}%3B%3B")
            else:
                # Solo marca sin modelo
                params.append(f"ms={make_code}%3B%3B")

    # Precio (p=MIN:MAX)
    if filters.price_range:
        if filters.price_range.min_price and filters.price_range.max_price:
            params.append(
                f"p={int(filters.price_range.min_price)}%3A{int(filters.price_range.max_price)}"
            )
        elif filters.price_range.min_price:
            params.append(f"p={int(filters.price_range.min_price)}%3A")
        elif filters.price_range.max_price:
            params.append(f"p=%3A{int(filters.price_range.max_price)}")

    # Primera matriculación (fr=MIN:MAX)
    if filters.year_range:
        if filters.year_range.min_year and filters.year_range.max_year:
            params.append(
                f"fr={filters.year_range.min_year}%3A{filters.year_range.max_year}"
            )
        elif filters.year_range.min_year:
            params.append(f"fr={filters.year_range.min_year}%3A")
        elif filters.year_range.max_year:
            params.append(f"fr=%3A{filters.year_range.max_year}")

    # Kilometraje (ml=MIN:MAX)
    if filters.mileage_range:
        if filters.mileage_range.min_mileage and filters.mileage_range.max_mileage:
            params.append(
                f"ml={filters.mileage_range.min_mileage}%3A{filters.mileage_range.max_mileage}"
            )
        elif filters.mileage_range.min_mileage:
            params.append(f"ml={filters.mileage_range.min_mileage}%3A")
        elif filters.mileage_range.max_mileage:
            params.append(f"ml=%3A{filters.mileage_range.max_mileage}")

    # País (cn=COUNTRY_CODE)
    if filters.country_code:
        params.append(f"cn={filters.country_code.upper()}")

    # Tipo de combustible (ft=FUEL_TYPE)
    if filters.fuel_types:
        for fuel_type in filters.fuel_types:
            fuel_code = MOBILE_DE_FUEL_TYPES.get(fuel_type.value)
            if fuel_code:
                params.append(f"ft={fuel_code}")

    # Potencia (pw=MIN:MAX) - Convertir de HP a kW
    if filters.power_range:
        min_kw = (
            int(filters.power_range.min_power_hp / 1.36)
            if filters.power_range.min_power_hp
            else None
        )
        max_kw = (
            int(filters.power_range.max_power_hp / 1.36)
            if filters.power_range.max_power_hp
            else None
        )

        if min_kw and max_kw:
            params.append(f"pw={min_kw}%3A{max_kw}")
        elif min_kw:
            params.append(f"pw={min_kw}%3A")
        elif max_kw:
            params.append(f"pw=%3A{max_kw}")

    # Transmisión (tr=TRANSMISSION_TYPE)
    if filters.transmissions:
        for transmission in filters.transmissions:
            trans_code = MOBILE_DE_TRANSMISSION_TYPES.get(transmission.value)
            if trans_code:
                params.append(f"tr={trans_code}")

    # Tipo de vendedor (st=DEALER o st=FSBO)
    if filters.dealer_only:
        params.append("st=DEALER")
    elif filters.private_only:
        params.append("st=FSBO")

    # Paginación (pageNumber=N)
    if page > 1:
        params.append(f"pageNumber={page}")

    return f"{base_url}?{'&'.join(params)}"
