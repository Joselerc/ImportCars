from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Price(BaseModel):
    amount: float = Field(..., description="Amount in the listing currency")
    currency_code: str = Field(..., min_length=3, max_length=3)


class Registration(BaseModel):
    year: int
    month: Optional[int] = None


class Consumption(BaseModel):
    combined: Optional[float] = None
    urban: Optional[float] = None
    highway: Optional[float] = None


class Location(BaseModel):
    country_code: Optional[str] = Field(None, min_length=2, max_length=2)
    region: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Seller(BaseModel):
    type: Optional[str] = Field(None, description="dealer | private | unknown")
    name: Optional[str] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    vat_number: Optional[str] = None
    dealer_id: Optional[str] = None


class Financing(BaseModel):
    available: bool = False
    amount: Optional[float] = None
    rate: Optional[float] = None
    duration_months: Optional[int] = None


class ListingMetadata(BaseModel):
    advert_type: Optional[str] = None
    vehicle_id: Optional[str] = None
    price_history: Optional[List[dict]] = None
    environment_badge: Optional[str] = None
    hsn_tsn: Optional[str] = None
    delivery_options: Optional[List[str]] = None
    certified: Optional[bool] = None
    publish_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    exportable: Optional[bool] = None


class NormalizedListing(BaseModel):
    listing_id: str
    source: str
    url: HttpUrl
    scraped_at: datetime
    title: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    price_eur: Optional[float] = Field(None, description="Precio Bruto (Gross)")
    price_net_eur: Optional[float] = Field(None, description="Precio Neto (Net)")
    price_original: Optional[Price] = None
    vat_deductible: Optional[bool] = None
    mileage_km: Optional[int] = None
    first_registration: Optional[Registration] = None
    production_year: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    power_hp: Optional[int] = None
    power_kw: Optional[int] = None
    engine_displacement_cc: Optional[int] = None
    body_type: Optional[str] = None
    doors: Optional[int] = None
    seats: Optional[int] = None
    color_exterior: Optional[str] = None
    color_interior: Optional[str] = None
    interior_material: Optional[str] = None
    emission_class: Optional[str] = None
    co2_emissions_g_km: Optional[int] = None
    co2_original_g_km: Optional[int] = None
    co2_inferred_g_km: Optional[int] = None
    co2_source_type: Optional[str] = None
    co2_confidence: Optional[float] = None
    consumption_l_100km: Optional[Consumption] = None
    features: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    images: List[HttpUrl] = Field(default_factory=list)
    location: Optional[Location] = None
    seller: Optional[Seller] = None
    warranty_months: Optional[int] = None
    inspection_valid_until: Optional[datetime] = None
    previous_owners: Optional[int] = None
    service_history: Optional[bool] = None
    accident_free: Optional[bool] = None
    metadata: ListingMetadata = Field(default_factory=ListingMetadata)
    vehicle_signature: Optional[str] = None
    variant_key: Optional[str] = None
    market_key: Optional[str] = None
    comparable_match_level: Optional[str] = None
    es_exact_sample_size: Optional[int] = None
    es_near_sample_size: Optional[int] = None
    es_broad_sample_size: Optional[int] = None
    es_market_avg: Optional[float] = None
    es_market_median: Optional[float] = None
    es_market_min: Optional[float] = None
    es_sample_size: Optional[int] = None
    best_break_even: Optional[float] = None
    potential_margin_avg: Optional[float] = None
    potential_margin_min: Optional[float] = None
    import_ready_score: Optional[float] = None


class SearchResult(BaseModel):
    listings: List[NormalizedListing]
    total_listings: Optional[int] = None
    result_page: Optional[int] = None
    result_page_size: Optional[int] = None
    has_next: Optional[bool] = None


__all__ = [
    "Price",
    "Registration",
    "Consumption",
    "Location",
    "Seller",
    "Financing",
    "ListingMetadata",
    "NormalizedListing",
    "SearchResult",
]
