from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from ..data import (
    COCHES_NET_FUEL_TYPES,
    COCHES_NET_MAKES,
    COCHES_NET_TRANSMISSION_TYPES,
    get_cochesnet_model_id_by_name,
)
from ..filters import FilterTranslator, UnifiedFilters
from ..matching import listing_matches_filters
from ..models import (
    ListingMetadata,
    Location,
    NormalizedListing,
    Price,
    Registration,
    SearchResult,
    Seller,
)
from .base import BaseScraper

logger = logging.getLogger(__name__)


class CochesNetScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://web.gw.coches.net"
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "es-ES,es;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://www.coches.net",
            "Referer": "https://www.coches.net/",
            "Sec-Ch-Ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?1",
            "Sec-Ch-Ua-Platform": '"Android"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Sec-Gpc": "1",
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
            "X-Adevinta-Channel": "web-mobile",
            "X-Adevinta-Page-Url": "https://www.coches.net/search/",
            "X-Adevinta-Referer": "https://www.coches.net/search/",
            "X-Schibsted-Tenant": "coches",
        }

    async def search(
        self,
        query: dict,
        limit: int | None = None,
    ) -> SearchResult:
        # Convertir query a UnifiedFilters si no lo es ya
        if isinstance(query, dict):
            filters = UnifiedFilters(**query)
        else:
            filters = query

        # Construir el payload basado en los filtros
        payload = self._build_search_payload(filters)

        response_data = await self._fetch_results_page(payload)
        if not response_data:
            logger.error("No se pudo obtener datos de la API de coches.net.")
            return SearchResult(
                listings=[], total_listings=0, result_page=filters.page, has_next=False
            )

        # Extraer y mostrar el total de resultados disponibles
        meta = response_data.get("meta", {})
        total_results = meta.get("totalResults", 0)
        if total_results > 0:
            print(f"Total de anuncios disponibles: {total_results}")

        return self._parse_response(
            response_data, filters.page, filters.page_size, limit, filters
        )

    def _build_search_payload(self, filters: UnifiedFilters) -> dict[str, Any]:
        """
        Construye el JSON payload para POST /search/listing basado en la petición real
        """
        # Estructura base del payload
        payload = {
            "pagination": {"page": filters.page, "size": filters.page_size},
            "sort": {
                "order": "desc" if filters.sort_order.value == "desc" else "asc",
                "term": FilterTranslator.translate_sort_by(
                    filters.sort_by, "coches_net"
                ),
            },
            "filters": {
                "batteryCapacity": {"from": None, "to": None},
                "bodyTypeIds": [],
                "categories": {"category1Ids": [2500]},  # Coches
                "chargingTimeFastMode": {"from": None, "to": None},
                "chargingTimeStandardMode": {"from": None, "to": None},
                "commitmentMonths": [],
                "contractId": 0,
                "drivenWheelsIds": [],
                "electricAutonomy": {"from": None, "to": None},
                "entry": None,
                "environmentalLabels": [],
                "equipments": [],
                "fee": {"from": None, "to": None},
                "fuelTypeIds": [],
                "hasOnlineFinancing": None,
                "hasPhoto": None,
                "hasReservation": None,
                "hasStock": None,
                "hasWarranty": None,
                "hp": {"from": None, "to": None},
                "isCertified": False,
                "km": {"from": None, "to": None},
                "luggageCapacity": {"from": None, "to": None},
                "maxTerms": None,
                "offerTypeIds": [0, 1, 2, 3, 4, 5],  # Todos los tipos de oferta
                "onlyPeninsula": False,
                "price": {"from": None, "to": None},
                "priceRank": [],
                "provinceIds": [],
                "rating": {"from": None, "to": None},
                "searchText": None,
                "sellerTypeId": 0,  # Todos los vendedores
                "targetBuyer": None,
                "transmissionTypeId": 0,  # Todas las transmisiones
                "vehicles": [],
                "year": {"from": None, "to": None},
            },
        }

        # Marca y modelo
        if filters.make:
            make_id = COCHES_NET_MAKES.get(filters.make.upper())
            if make_id:
                vehicle_filter = {
                    "make": filters.make.upper(),
                    "makeId": make_id,
                    "model": None,
                    "modelId": 0,
                }

                # Si se especifica modelo, buscar su ID
                if filters.model:
                    model_id = get_cochesnet_model_id_by_name(
                        filters.make, filters.model
                    )
                    if model_id:
                        vehicle_filter["model"] = filters.model.upper()
                        vehicle_filter["modelId"] = int(model_id)

                payload["filters"]["vehicles"] = [vehicle_filter]

        # Rango de precios
        if filters.price_range:
            if filters.price_range.min_price:
                payload["filters"]["price"]["from"] = int(filters.price_range.min_price)
            if filters.price_range.max_price:
                payload["filters"]["price"]["to"] = int(filters.price_range.max_price)

        # Rango de años
        if filters.year_range:
            if filters.year_range.min_year:
                payload["filters"]["year"]["from"] = filters.year_range.min_year
            if filters.year_range.max_year:
                payload["filters"]["year"]["to"] = filters.year_range.max_year

        # Rango de kilometraje
        if filters.mileage_range:
            if filters.mileage_range.min_mileage:
                payload["filters"]["km"]["from"] = filters.mileage_range.min_mileage
            if filters.mileage_range.max_mileage:
                payload["filters"]["km"]["to"] = filters.mileage_range.max_mileage

        # Rango de potencia
        if filters.power_range:
            if filters.power_range.min_power_hp:
                payload["filters"]["hp"]["from"] = filters.power_range.min_power_hp
            if filters.power_range.max_power_hp:
                payload["filters"]["hp"]["to"] = filters.power_range.max_power_hp

        # Tipos de combustible
        if filters.fuel_types:
            fuel_type_ids = []
            for fuel_type in filters.fuel_types:
                fuel_id = COCHES_NET_FUEL_TYPES.get(fuel_type.value)
                if fuel_id:
                    fuel_type_ids.append(fuel_id)
            if fuel_type_ids:
                payload["filters"]["fuelTypeIds"] = fuel_type_ids

        # Transmisión
        if filters.transmissions and len(filters.transmissions) == 1:
            trans_id = COCHES_NET_TRANSMISSION_TYPES.get(filters.transmissions[0].value)
            if trans_id:
                payload["filters"]["transmissionTypeId"] = trans_id

        # Tipo de vendedor
        if filters.dealer_only:
            payload["filters"]["sellerTypeId"] = 1
        elif filters.private_only:
            payload["filters"]["sellerTypeId"] = 2

        return payload

    def _extract_images(self, payload: Any) -> list[str]:
        urls: list[str] = []
        seen = set()

        def add(value: Any) -> None:
            if not isinstance(value, str) or value in seen:
                return
            lowered = value.lower()
            if not value.startswith("http"):
                return
            if not any(
                token in lowered
                for token in ("image", "photo", "jpg", "jpeg", "png", "webp")
            ):
                return
            seen.add(value)
            urls.append(value)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if isinstance(value, str) and any(
                        token in key.lower()
                        for token in ("image", "photo", "gallery", "pic")
                    ):
                        add(value)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            else:
                add(node)

        walk(payload)
        return urls[:8]

    async def _fetch_results_page(
        self, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        # Headers específicos basados en la petición real
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "es-ES,es;q=0.9",
            "origin": "https://www.coches.net",
            "referer": "https://www.coches.net/",
            "sec-ch-ua": '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36",
            "x-adevinta-channel": "web-mobile",
            "x-adevinta-page-url": "https://www.coches.net/search/",
            "x-adevinta-referer": "https://www.coches.net/search/",
            "x-schibsted-tenant": "coches",
        }

        async with httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=30.0
        ) as client:
            try:
                url = "/search/listing"
                logger.info(f"Realizando petición POST a {url} con payload: {payload}")
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info("Petición exitosa. Parseando JSON.")
                json_data = response.json()
                logger.info(
                    "Respuesta JSON recibida con %s items",
                    len(json_data.get("items", [])),
                )
                return json_data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Error HTTP al obtener resultados: {e.response.status_code} - {e.response.text}"
                )
                return None
            except httpx.RequestError as e:
                logger.error(f"Error de red al obtener resultados: {e}")
                return None

    def _parse_response(
        self,
        data: dict[str, Any],
        page_num: int,
        page_size: int,
        limit: int | None = None,
        filters: UnifiedFilters | None = None,
    ) -> SearchResult:
        """Parsea la respuesta JSON del endpoint /listing y convierte a NormalizedListing"""
        items = data.get("items", [])
        meta = data.get("meta", {})

        total_results = meta.get("totalResults", 0)
        total_pages = meta.get("totalPages", 0)
        has_next = page_num < total_pages

        listings = []
        for item_data in items:
            listing = self._to_listing(item_data)
            if listing and self._matches_filters(listing, filters):
                listings.append(listing)
                if limit and len(listings) >= limit:
                    break

        logger.info(f"Procesados {len(listings)} anuncios de {len(items)} elementos")

        return SearchResult(
            listings=listings,
            total_listings=total_results,
            result_page=page_num,
            result_page_size=len(listings),
            has_next=has_next,
        )

    def _matches_filters(
        self, listing: NormalizedListing, filters: UnifiedFilters | None
    ) -> bool:
        """Verifica si un listing cumple exactamente con los filtros especificados"""
        return listing_matches_filters(listing, filters)

    def _to_listing(self, data: dict[str, Any]) -> NormalizedListing | None:
        """Convierte un elemento JSON de coches.net a NormalizedListing"""
        try:
            listing_id = data.get("id")
            if not listing_id:
                return None

            # URL del anuncio
            url_path = data.get("url", "")
            url = (
                f"https://www.coches.net{url_path}"
                if url_path.startswith("/")
                else url_path
            )

            # Precio - estructura del endpoint /listing
            price_data = data.get("price", {})
            price_eur = price_data.get("amount")

            # Registro
            year = data.get("year")
            registration = Registration(year=year) if year else None

            # Ubicación
            location_data = data.get("location", {})
            location = None
            if location_data:
                location = Location(
                    country_code="ES",
                    region=location_data.get("regionLiteral"),
                    province=location_data.get("mainProvince"),
                    city=location_data.get("cityLiteral"),
                    postal_code=None,
                )

            # Vendedor
            seller_data = data.get("seller", {})
            seller = None
            if seller_data:
                seller = Seller(
                    type="dealer" if seller_data.get("isProfessional") else "private",
                    name=seller_data.get("name"),
                    phone=data.get("phone"),  # El teléfono está en el nivel superior
                )

            # Fechas de publicación
            creation_date = data.get("creationDate")
            published_date = data.get("publishedDate")

            # Usar publishedDate si existe, sino creationDate
            publish_date = None
            source_date = published_date or creation_date
            if source_date:
                try:
                    publish_date = datetime.fromisoformat(source_date)
                except (TypeError, ValueError):
                    logger.debug("Fecha de publicación no válida: %r", source_date)

            # Crear metadata con fecha de publicación
            metadata = ListingMetadata(publish_date=publish_date)

            return NormalizedListing(
                listing_id=str(listing_id),
                source="coches_net",
                url=url,
                scraped_at=datetime.now(UTC),
                title=data.get("title"),
                make=data.get("make"),
                model=data.get("model"),
                price_eur=price_eur,
                price_original=Price(amount=price_eur, currency_code="EUR")
                if price_eur
                else None,
                mileage_km=data.get("km"),
                first_registration=registration,
                power_hp=data.get("hp"),
                power_kw=int(data.get("hp") / 1.36) if data.get("hp") else None,
                fuel_type=data.get("fuelType"),
                engine_displacement_cc=data.get("cubicCapacity"),
                images=self._extract_images(data),
                location=location,
                seller=seller,
                metadata=metadata,
            )

        except (AttributeError, TypeError, ValueError) as exc:
            logger.error("Error procesando elemento: %s", exc)
        return None


__all__ = ["CochesNetScraper"]
