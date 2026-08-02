from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Price(BaseModel):
    amount: float = Field(..., description="Amount in the listing currency")
    currency_code: str = Field(..., min_length=3, max_length=3)


class Registration(BaseModel):
    year: int
    month: int | None = None


class Consumption(BaseModel):
    combined: float | None = None
    urban: float | None = None
    highway: float | None = None


class Location(BaseModel):
    country_code: str | None = Field(None, min_length=2, max_length=2)
    region: str | None = None
    province: str | None = None
    city: str | None = None
    postal_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class Seller(BaseModel):
    type: str | None = Field(None, description="dealer | private | unknown")
    name: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    phone: str | None = None
    email: str | None = None
    vat_number: str | None = None
    dealer_id: str | None = None


class Financing(BaseModel):
    available: bool = False
    amount: float | None = None
    rate: float | None = None
    duration_months: int | None = None


class ListingMetadata(BaseModel):
    advert_type: str | None = None
    vehicle_id: str | None = None
    price_history: list[dict] | None = None
    environment_badge: str | None = None
    hsn_tsn: str | None = None
    delivery_options: list[str] | None = None
    certified: bool | None = None
    publish_date: datetime | None = None
    update_date: datetime | None = None
    exportable: bool | None = None
    # Dato observado en origen para auditoría; no participa en el matching.
    source_transmission: str | None = None


class NormalizedListing(BaseModel):
    listing_id: str
    source: str
    url: HttpUrl
    scraped_at: datetime
    title: str | None = None
    make: str | None = None
    model: str | None = None
    version: str | None = None
    price_eur: float | None = Field(None, description="Precio Bruto (Gross)")
    price_net_eur: float | None = Field(None, description="Precio Neto (Net)")
    price_original: Price | None = None
    vat_deductible: bool | None = None
    mileage_km: int | None = None
    first_registration: Registration | None = None
    production_year: int | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    power_hp: int | None = None
    power_kw: int | None = None
    engine_displacement_cc: int | None = None
    body_type: str | None = None
    doors: int | None = None
    seats: int | None = None
    color_exterior: str | None = None
    color_interior: str | None = None
    interior_material: str | None = None
    emission_class: str | None = None
    co2_emissions_g_km: int | None = None
    co2_original_g_km: int | None = None
    co2_inferred_g_km: int | None = None
    co2_source_type: str | None = None
    co2_confidence: float | None = None
    consumption_l_100km: Consumption | None = None
    features: list[str] = Field(default_factory=list)
    description: str | None = None
    images: list[HttpUrl] = Field(default_factory=list)
    location: Location | None = None
    seller: Seller | None = None
    warranty_months: int | None = None
    inspection_valid_until: datetime | None = None
    previous_owners: int | None = None
    service_history: bool | None = None
    accident_free: bool | None = None
    metadata: ListingMetadata = Field(default_factory=ListingMetadata)
    vehicle_signature: str | None = None
    variant_key: str | None = None
    market_key: str | None = None
    comparable_match_level: str | None = None
    es_exact_sample_size: int | None = None
    es_near_sample_size: int | None = None
    es_broad_sample_size: int | None = None
    es_market_avg: float | None = None
    es_market_median: float | None = None
    es_market_min: float | None = None
    es_sample_size: int | None = None
    best_break_even: float | None = None
    potential_margin_avg: float | None = None
    potential_margin_min: float | None = None
    import_ready_score: float | None = None


class SearchResult(BaseModel):
    listings: list[NormalizedListing]
    total_listings: int | None = None
    result_page: int | None = None
    result_page_size: int | None = None
    has_next: bool | None = None


__all__ = [
    "Consumption",
    "Financing",
    "ListingMetadata",
    "Location",
    "NormalizedListing",
    "Price",
    "Registration",
    "SearchResult",
    "Seller",
]
