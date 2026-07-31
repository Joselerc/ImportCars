"""
Scraper HTTP para mobile.de usando curl_cffi
Mucho más rápido que Playwright (sin navegador)
"""

import html
import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from curl_cffi import requests as cffi
from curl_cffi.requests.errors import RequestsError
from selectolax.parser import HTMLParser
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..config import ScraperSettings, get_settings
from ..filters import UnifiedFilters
from ..matching import listing_matches_filters
from ..models import (
    Consumption,
    ListingMetadata,
    Location,
    NormalizedListing,
    Price,
    Registration,
    SearchResult,
    Seller,
)
from ..utils import build_mobile_de_search_url


class MobileDeHttpScraper:
    """Scraper HTTP rápido para mobile.de usando curl_cffi"""

    def __init__(self, settings: ScraperSettings | None = None):
        self.settings = settings or get_settings()
        self.source = "mobile_de"

        self._thread_local = threading.local()
        self.session = self._new_session()
        self._thread_local.session = self.session

        # Headers realistas
        self.headers = {
            "user-agent": self.settings.user_agent,
            "accept-language": "es-ES,es;q=0.9",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    def _new_session(self):
        return cffi.Session(
            impersonate="chrome",
            timeout=self.settings.request_timeout,
        )

    def _session_for_current_thread(self):
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = self._new_session()
            self._thread_local.session = session
        return session

    def _get(self, url: str):
        retryer = Retrying(
            stop=stop_after_attempt(max(1, self.settings.max_retries)),
            wait=wait_exponential_jitter(initial=0.5, max=8),
            retry=retry_if_exception_type(RequestsError),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                proxy = (
                    random.choice(self.settings.proxy_pool)
                    if self.settings.proxy_pool
                    else None
                )
                response = self._session_for_current_thread().get(
                    url,
                    headers=self.headers,
                    proxy=str(proxy) if proxy else None,
                )
                response.raise_for_status()
                return response
        raise RuntimeError(f"No se pudo recuperar {url}")

    def _build_search_url(self, filters: UnifiedFilters, page: int = 1) -> str:
        """Construir URL de búsqueda con filtros usando el URL builder"""
        return build_mobile_de_search_url(filters, page)

    def search(
        self, query: UnifiedFilters | None = None, limit: int | None = None
    ) -> SearchResult:
        """Buscar anuncios con filtros"""
        filters = query or UnifiedFilters()
        all_listings = []
        page = filters.page
        first_page = page
        total_available = None
        desired_count = limit or filters.page_size

        print("Iniciando busqueda HTTP en mobile.de...")

        while True:
            url = self._build_search_url(filters, page)
            print(f"Pagina {page}: {url}")

            # Obtener HTML de la página de listado
            response = self._get(url)

            search_payload = self._extract_next_search_results(response.text)

            # Extraer total de resultados (solo en la primera página)
            if page == first_page:
                total_available = (
                    search_payload.get("numResultsTotal")
                    if search_payload
                    else self._extract_total_results(response.text)
                )
                if total_available:
                    print(f"Total de anuncios disponibles: {total_available}")

            summary_listings = self._extract_summary_listings(search_payload)
            if summary_listings:
                listings = [
                    listing
                    for listing in summary_listings
                    if self._matches_filters(listing, filters)
                ]
                print(
                    f"   OK - {len(summary_listings)} anuncios encontrados en Next.js"
                )
            else:
                # Fallback para estructuras antiguas basadas en enlaces del DOM.
                ids = self._extract_ids_from_listing(response.text)
                print(f"   INFO - fallback DOM: {len(ids)} IDs encontrados")
                listings = [
                    listing
                    for listing in self._fetch_details_parallel(
                        ids, max_workers=self.settings.concurrency
                    )
                    if self._matches_filters(listing, filters)
                ]

            if not summary_listings and not listings:
                print("   ADVERTENCIA: No se encontraron mas anuncios")
                break

            remaining = desired_count - len(all_listings)
            all_listings.extend(listings[:remaining])

            print(
                f"   OK - {len(listings)} anuncios procesados (Total: {len(all_listings)}"
                + (f"/{total_available}" if total_available else "")
                + ")"
            )

            # Verificar límite
            if len(all_listings) >= desired_count:
                break

            # Verificar si hay más páginas
            if summary_listings:
                inspected = (page - first_page + 1) * len(summary_listings)
                has_next = total_available is not None and inspected < total_available
            else:
                has_next = self._has_next_page(response.text)
            if not has_next:
                print("   INFO: No hay mas paginas")
                break

            if page - first_page + 1 >= self.settings.max_pages:
                print(f"   INFO: Limite de {self.settings.max_pages} paginas alcanzado")
                break

            page += 1
            pause_min = min(self.settings.page_pause_min, self.settings.page_pause_max)
            pause_max = max(self.settings.page_pause_min, self.settings.page_pause_max)
            time.sleep(random.uniform(pause_min, pause_max))

        print(
            f"\nScraping completado: {len(all_listings)} anuncios extraidos"
            + (f" de {total_available} totales" if total_available else "")
        )

        return SearchResult(
            listings=all_listings,
            total_listings=total_available or len(all_listings),
            result_page=page,
            result_page_size=len(all_listings),
            has_next=False,
        )

    def _extract_next_search_results(self, html_content: str) -> dict | None:
        """Extrae ``searchResults`` de los chunks RSC embebidos por Next.js."""
        decoded = self._decode_next_chunks(html_content)
        marker = '"searchResults":'
        start = decoded.find(marker)
        if start < 0:
            return None

        try:
            payload, _ = json.JSONDecoder().raw_decode(decoded, start + len(marker))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _decode_next_chunks(html_content: str) -> str:
        """Decode the string chunks used by the current Next.js RSC pages."""

        chunks = []
        pattern = re.compile(
            r'self\.__next_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)',
            re.DOTALL,
        )
        for match in pattern.finditer(html_content):
            try:
                chunks.append(json.loads(match.group(1)))
            except (json.JSONDecodeError, TypeError):
                continue
        return "".join(chunks)

    def _extract_next_detail_listing(
        self, html_content: str, vehicle_id: str, url: str
    ) -> NormalizedListing | None:
        """Normalize the canonical listing object embedded in a detail page."""

        decoded = self._decode_next_chunks(html_content)
        marker = '"listing":'
        position = 0
        payload = None
        while True:
            position = decoded.find(marker, position)
            if position < 0:
                break
            try:
                candidate, _ = json.JSONDecoder().raw_decode(
                    decoded, position + len(marker)
                )
            except json.JSONDecodeError:
                position += len(marker)
                continue
            if isinstance(candidate, dict) and str(candidate.get("id")) == vehicle_id:
                payload = candidate
                break
            position += len(marker)
        if payload is None:
            return None

        attributes = {
            item.get("tag"): item.get("value")
            for item in payload.get("attributes") or []
            if isinstance(item, dict) and item.get("tag")
        }
        price = payload.get("price") or {}
        gross = price.get("grs") or price.get("gross") or {}
        net = price.get("net") or {}
        price_eur = gross.get("amount")
        registration = None
        match = re.search(r"(\d{1,2})/(\d{4})", attributes.get("firstRegistration") or "")
        if match:
            registration = Registration(year=int(match.group(2)), month=int(match.group(1)))

        power_kw = None
        power_hp = None
        power_match = re.search(
            r"(\d+)\s*kW(?:\s*\((\d+)\s*(?:cv|PS|hp)\))?",
            attributes.get("power") or "",
            re.IGNORECASE,
        )
        if power_match:
            power_kw = int(power_match.group(1))
            power_hp = int(power_match.group(2)) if power_match.group(2) else round(power_kw * 1.35962)

        co2 = None
        for tag, value in attributes.items():
            if "co2" in tag.casefold():
                co2 = self._localized_integer(str(value))
                if co2 is not None:
                    break
        contact = payload.get("contact") or {}
        rating = contact.get("rating") or {}
        phones = contact.get("phones") or []
        seller = Seller(
            type="dealer" if contact.get("enumType") == "DEALER" else "private",
            name=contact.get("name"),
            rating=rating.get("score"),
            rating_count=rating.get("totalCount") or rating.get("count"),
            phone=phones[0].get("number") if phones else None,
        )
        image_urls = []
        for image in payload.get("images") or []:
            uri = image.get("uri") if isinstance(image, dict) else None
            if uri:
                image_urls.append(uri if uri.startswith("http") else f"https://{uri}")
        make = payload.get("make") or {}
        model = payload.get("model") or {}

        return NormalizedListing(
            listing_id=vehicle_id,
            source=self.source,
            url=url,
            scraped_at=datetime.now(UTC),
            title=payload.get("title"),
            make=make.get("localized"),
            model=model.get("localized"),
            version=attributes.get("trimLine") or payload.get("subTitle"),
            price_eur=float(price_eur) if price_eur is not None else None,
            price_net_eur=float(net.get("amount")) if net.get("amount") is not None else None,
            price_original=(
                Price(amount=float(price_eur), currency_code=gross.get("currency") or "EUR")
                if price_eur is not None
                else None
            ),
            vat_deductible=net.get("amount") is not None,
            mileage_km=self._localized_integer(attributes.get("mileage")),
            first_registration=registration,
            fuel_type=attributes.get("fuel"),
            transmission=attributes.get("transmission"),
            power_hp=power_hp,
            power_kw=power_kw,
            engine_displacement_cc=self._localized_integer(attributes.get("cubicCapacity")),
            body_type=attributes.get("category"),
            color_exterior=attributes.get("color"),
            emission_class=attributes.get("emissionClass"),
            co2_emissions_g_km=co2,
            co2_original_g_km=co2,
            co2_source_type="listing" if co2 is not None else None,
            co2_confidence=1.0 if co2 is not None else 0.0,
            images=image_urls,
            seller=seller,
            previous_owners=self._localized_integer(attributes.get("numberOfPreviousOwners")),
            metadata=ListingMetadata(vehicle_id=vehicle_id),
        )

    def _extract_summary_listings(
        self, payload: dict | None
    ) -> list[NormalizedListing]:
        """Normaliza los anuncios disponibles en la propia página de resultados."""
        if not payload:
            return []

        listings = []
        for item in payload.get("listings", []):
            listing = self._summary_to_listing(item)
            if listing is not None:
                listings.append(listing)
        return listings

    def _summary_to_listing(self, item: dict) -> NormalizedListing | None:
        try:
            listing_id = item.get("id") or item.get("listingId")
            if not listing_id:
                return None

            attributes = item.get("attr") or {}
            make_data = item.get("make") or {}
            model_data = item.get("model") or {}
            price_data = item.get("price") or {}
            gross = price_data.get("grs") or price_data.get("gross") or {}
            net = price_data.get("net") or {}
            price_eur = gross.get("amount") or self._localized_number(item.get("p"))
            price_net_eur = net.get("amount")

            registration = None
            registration_match = re.search(
                r"(\d{1,2})/(\d{4})", attributes.get("fr") or ""
            )
            if registration_match:
                month, year = registration_match.groups()
                registration = Registration(year=int(year), month=int(month))

            power_kw = None
            power_hp = None
            power_match = re.search(
                r"(\d+)\s*kW(?:\s*\((\d+)\s*(?:cv|PS|hp)\))?",
                attributes.get("pw") or "",
                re.IGNORECASE,
            )
            if power_match:
                power_kw = int(power_match.group(1))
                power_hp = (
                    int(power_match.group(2))
                    if power_match.group(2)
                    else round(power_kw * 1.35962)
                )

            contact = item.get("contact") or {}
            rating = contact.get("rating") or {}
            phones = contact.get("phones") or []
            seller = Seller(
                type="dealer"
                if contact.get("enumType") == "DEALER"
                else "private"
                if contact
                else "unknown",
                name=contact.get("name"),
                rating=rating.get("score"),
                rating_count=rating.get("totalCount") or rating.get("count"),
                phone=phones[0].get("number") if phones else None,
            )

            lat_long = contact.get("latLong") or {}
            location = Location(
                country_code=attributes.get("cn") or contact.get("country"),
                city=attributes.get("loc"),
                postal_code=attributes.get("z"),
                latitude=lat_long.get("lat"),
                longitude=lat_long.get("lon"),
            )

            image_urls = []
            for image in item.get("images") or []:
                uri = image.get("uri") if isinstance(image, dict) else None
                if uri:
                    image_urls.append(
                        uri if uri.startswith("http") else f"https://{uri}"
                    )

            title = " ".join(
                part.strip()
                for part in (item.get("shortTitle"), item.get("subTitle"))
                if part and part.strip()
            )
            created = item.get("created")
            publish_date = datetime.fromtimestamp(created, tz=UTC) if created else None

            return NormalizedListing(
                listing_id=str(listing_id),
                source=self.source,
                url=f"https://www.mobile.de/es/veh%C3%ADculos/detalles.html?id={listing_id}",
                scraped_at=datetime.now(UTC),
                title=title or None,
                make=make_data.get("localized") or item.get("makeName"),
                model=model_data.get("localized") or item.get("modelName"),
                price_eur=float(price_eur) if price_eur is not None else None,
                price_net_eur=float(price_net_eur)
                if price_net_eur is not None
                else None,
                price_original=(
                    Price(
                        amount=float(price_eur),
                        currency_code=gross.get("currency") or "EUR",
                    )
                    if price_eur is not None
                    else None
                ),
                vat_deductible=bool(price_net_eur) if price_eur is not None else None,
                mileage_km=self._localized_integer(attributes.get("ml")),
                first_registration=registration,
                fuel_type=attributes.get("ft"),
                transmission=attributes.get("tr"),
                power_hp=power_hp,
                power_kw=power_kw,
                engine_displacement_cc=self._localized_integer(attributes.get("cc")),
                body_type=attributes.get("c"),
                color_exterior=attributes.get("ecol"),
                emission_class=attributes.get("emc"),
                images=image_urls,
                location=location,
                seller=seller,
                metadata=ListingMetadata(
                    vehicle_id=str(listing_id),
                    publish_date=publish_date,
                ),
            )
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _localized_integer(value: str | None) -> int | None:
        if not value:
            return None
        match = re.search(r"\d[\d.\s]*", value.replace("\u00a0", " "))
        return int(re.sub(r"\D", "", match.group(0))) if match else None

    @staticmethod
    def _localized_number(value: str | None) -> float | None:
        integer = MobileDeHttpScraper._localized_integer(value)
        return float(integer) if integer is not None else None

    def _extract_total_results(self, html_content: str) -> int | None:
        """Extraer el número total de resultados de la búsqueda"""
        # Método 1: Buscar en el JSON embebido de Next.js
        match = re.search(r'"numResultsTotal":(\d+)', html_content)
        if match:
            return int(match.group(1))

        # Método 2: Buscar en el texto visible (fallback)
        match = re.search(r"(\d+)\s*resultados?", html_content, re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _extract_ids_from_listing(self, html_content: str) -> list[str]:
        """Extraer IDs de anuncios del HTML de listado"""
        tree = HTMLParser(html_content)
        ids = []
        seen = set()

        for node in tree.css("a[href*='detalles.html?id=']"):
            href = node.attributes.get("href", "")
            match = re.search(r"detalles\.html\?id=(\d{6,})", href)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                ids.append(match.group(1))

        return ids

    def _matches_filters(
        self, listing: NormalizedListing, filters: UnifiedFilters
    ) -> bool:
        """Filtra resultados HTTP para evitar anuncios ajenos a la búsqueda."""
        return listing_matches_filters(listing, filters)

    def _has_next_page(self, html_content: str) -> bool:
        """Verificar si hay página siguiente"""
        tree = HTMLParser(html_content)
        next_link = tree.css_first('a[rel="next"]')
        return next_link is not None

    def _fetch_details_parallel(
        self, ids: list[str], max_workers: int = 10
    ) -> list[NormalizedListing]:
        """Obtener detalles de múltiples anuncios en paralelo"""
        listings = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {
                executor.submit(self._fetch_detail, id_): id_ for id_ in ids
            }

            for future in as_completed(future_to_id):
                try:
                    listing = future.result()
                    if listing:
                        listings.append(listing)
                except Exception as e:  # noqa: BLE001 - cada future debe aislar su fallo
                    id_ = future_to_id[future]
                    print(f"      ERROR en ID {id_}: {e}")

        return listings

    def _fetch_detail(self, vehicle_id: str) -> NormalizedListing | None:
        """Obtener detalles de un anuncio específico"""
        url = f"https://www.mobile.de/es/veh%C3%ADculos/detalles.html?id={vehicle_id}"

        try:
            response = self._get(url)

            return self._parse_detail_page(response.text, vehicle_id, url)

        except (AttributeError, RequestsError, TypeError, ValueError) as e:
            print(f"      ERROR obteniendo detalle {vehicle_id}: {e}")
            return None

    def get_listing(self, vehicle_id: str) -> NormalizedListing | None:
        """Public on-demand detail lookup used by the customer URL parser."""

        return self._fetch_detail(vehicle_id)

    def _parse_detail_page(
        self, html_content: str, vehicle_id: str, url: str
    ) -> NormalizedListing | None:
        """Parsear página de detalle completa"""
        embedded = self._extract_next_detail_listing(html_content, vehicle_id, url)
        if embedded is not None:
            return embedded

        tree = HTMLParser(html.unescape(html_content))
        images = self._extract_images(tree, html_content)

        # Título - h2.typography_headline__yJCAO
        title = None
        title_node = tree.css_first("h2.typography_headline__yJCAO")
        if title_node:
            title = title_node.text(strip=True)

        # Subtítulo/Modelo - div.MainCtaBox_subTitle__wYybO
        subtitle = None
        subtitle_node = tree.css_first("div.MainCtaBox_subTitle__wYybO")
        if subtitle_node:
            subtitle = subtitle_node.text(strip=True)

        # Precio - div.MainPriceArea_mainPrice__xCkfs
        price_eur = None
        price_node = tree.css_first("div.MainPriceArea_mainPrice__xCkfs")
        if not price_node:
            price_node = tree.css_first('span[data-testid="prime-price"]')
        if not price_node:
            price_node = tree.css_first("span.PriceLabel_mainPrice__3SZut")
        if price_node:
            price_text = price_node.text(strip=True)
            # Eliminar espacios no separables y extraer números
            price_match = re.search(
                r"([0-9\.]+)", price_text.replace("\u00a0", "").replace(" ", "")
            )
            if price_match:
                # Formato alemán: punto como separador de miles, sin decimales
                price_eur = float(price_match.group(1).replace(".", ""))

        # Extraer información del vendedor
        seller_info = self._extract_seller_info(tree)

        # Extraer datos de KeyFeatures (mileage, power, fuel, transmission, first_registration, previous_owners)
        tech_data = self._extract_key_features(tree)

        # Marca del título
        make = None
        if title:
            make = title.split()[0] if title.split() else None

        # Modelo: combinar título + subtítulo
        model = None
        if title and subtitle:
            # Título sin la marca
            title_without_make = (
                " ".join(title.split()[1:]) if len(title.split()) > 1 else ""
            )
            model = f"{title_without_make} {subtitle}".strip()
        elif title:
            model = " ".join(title.split()[1:]) if len(title.split()) > 1 else title

        # Registro
        registration = None
        if tech_data.get("first_registration"):
            reg_match = re.match(r"(\d{1,2})/(\d{4})", tech_data["first_registration"])
            if reg_match:
                month, year = reg_match.groups()
                registration = Registration(year=int(year), month=int(month))

        # Precio neto (estimado)
        price_net_eur = None
        if price_eur:
            vat_rate = 1.19  # IVA alemán por defecto
            price_net_eur = round(price_eur / vat_rate, 2)

        # Preparar consumo (convertir float a objeto Consumption si existe)
        consumption = None
        if tech_data.get("consumption_l_100km"):
            consumption = Consumption(combined=tech_data["consumption_l_100km"])

        # Preparar metadata con pegatina de emisiones
        from ..models import ListingMetadata

        metadata = ListingMetadata()
        if tech_data.get("emissions_sticker"):
            metadata.environment_badge = tech_data["emissions_sticker"]

        return NormalizedListing(
            listing_id=vehicle_id,
            source=self.source,
            url=url,
            scraped_at=datetime.now(UTC),
            title=f"{title} {subtitle}".strip() if subtitle else title,
            make=make,
            model=model,
            price_eur=price_eur,
            price_net_eur=price_net_eur,
            price_original=Price(amount=price_eur, currency_code="EUR")
            if price_eur
            else None,
            mileage_km=tech_data.get("mileage_km"),
            first_registration=registration,
            fuel_type=tech_data.get("fuel_type"),
            transmission=tech_data.get("transmission"),
            power_hp=tech_data.get("power_hp"),
            power_kw=tech_data.get("power_kw"),
            engine_displacement_cc=tech_data.get("cubic_capacity_ccm"),
            co2_emissions_g_km=tech_data.get("co2_emissions_g_km"),
            consumption_l_100km=consumption,
            description=tech_data.get("description"),
            images=images,
            doors=tech_data.get("doors"),
            color_exterior=tech_data.get("color_exterior"),
            previous_owners=tech_data.get("previous_owners"),
            seller=seller_info,
            metadata=metadata,
        )

    def _extract_images(self, tree: HTMLParser, html_content: str) -> list[str]:
        """Extraer imágenes relevantes del anuncio."""
        candidates: list[str] = []
        seen = set()

        def add(url: str | None) -> None:
            if not url or url in seen:
                return
            if not url.startswith("http"):
                return
            lowered = url.lower()
            if any(
                token in lowered
                for token in ("logo", "icon", "sprite", "dealer-rating")
            ):
                return
            seen.add(url)
            candidates.append(url)

        for node in tree.css("meta[property='og:image'], meta[name='twitter:image']"):
            add(node.attributes.get("content"))

        for node in tree.css("img"):
            add(node.attributes.get("src"))
            add(node.attributes.get("data-src"))

        for match in re.findall(
            r'https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*',
            html_content,
            re.IGNORECASE,
        ):
            add(match)

        return candidates[:8]

    def _extract_seller_info(self, tree: HTMLParser) -> dict | None:
        """Extraer información del vendedor"""
        from ..models import Seller

        # Buscar el contenedor del vendedor
        seller_container = tree.css_first(
            "div.MainSellerInfo_titleAndRatingBlock__rDi0i"
        )
        if not seller_container:
            return None

        # Extraer el texto del label
        label_node = seller_container.css_first("div.typography_label__EkjGc")
        if not label_node:
            return None

        label_text = label_node.text(strip=True)

        # Determinar tipo de vendedor
        # Buscar patrones en español y alemán
        is_private = any(
            keyword in label_text.lower()
            for keyword in [
                "vendedor particular",
                "particular",
                "privat",
                "private seller",
                "privatverkäufer",
            ]
        )

        seller_type = "private" if is_private else "dealer"
        seller_name = None
        rating = None
        rating_count = None

        if not is_private:
            # Si es concesionario, buscar el nombre en el enlace
            link_node = label_node.css_first("a.link_Link__B0oSi")
            if link_node:
                seller_name = link_node.text(strip=True)

            # Buscar rating
            rating_node = seller_container.css_first(
                "div.ratingStars_RatingStars__fKi_d"
            )
            if rating_node:
                # Extraer rating del label sr-only
                sr_label = rating_node.css_first(
                    "span.ratingStars_SrOnlyRatingStarsLabel__03fSs"
                )
                if sr_label:
                    rating_text = sr_label.text(strip=True)
                    # Formato: "4.6 estrellas" o "4.6 stars"
                    rating_match = re.search(r"(\d+\.?\d*)", rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))

        return Seller(
            type=seller_type, name=seller_name, rating=rating, rating_count=rating_count
        )

    def _extract_key_features(self, tree: HTMLParser) -> dict[str, Any]:
        """Extraer datos de KeyFeatures usando los selectores específicos"""
        data = {}

        # Kilometraje - div[data-testid="vip-key-features-list-item-mileage"]
        mileage_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-mileage"] div.KeyFeatures_value__8LVNc'
        )
        if mileage_node:
            km_text = mileage_node.text(strip=True)
            km_match = re.search(r"(\d{1,3}(?:\.\d{3})*)", km_text)
            if km_match:
                data["mileage_km"] = int(km_match.group(1).replace(".", ""))

        # Potencia - div[data-testid="vip-key-features-list-item-power"]
        power_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-power"] div.KeyFeatures_value__8LVNc'
        )
        if power_node:
            power_text = power_node.text(strip=True)
            # Formato: "162 kW (220 cv)"
            kw_match = re.search(
                r"(\d+)\s*kW\s*\((\d+)\s*cv\)", power_text, re.IGNORECASE
            )
            if kw_match:
                data["power_kw"] = int(kw_match.group(1))
                data["power_hp"] = int(kw_match.group(2))

        # Combustible - div[data-testid="vip-key-features-list-item-fuel"]
        fuel_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-fuel"] div.KeyFeatures_value__8LVNc'
        )
        if fuel_node:
            data["fuel_type"] = fuel_node.text(strip=True)

        # Transmisión - div[data-testid="vip-key-features-list-item-transmission"]
        transmission_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-transmission"] div.KeyFeatures_value__8LVNc'
        )
        if transmission_node:
            trans_text = transmission_node.text(strip=True)
            if "manual" in trans_text.lower():
                data["transmission"] = "Manual"
            elif "automát" in trans_text.lower():
                data["transmission"] = "Automático"
            else:
                data["transmission"] = trans_text

        # Primera matriculación - div[data-testid="vip-key-features-list-item-firstRegistration"]
        first_reg_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-firstRegistration"] div.KeyFeatures_value__8LVNc'
        )
        if first_reg_node:
            data["first_registration"] = first_reg_node.text(strip=True)

        # Propietarios anteriores - div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"]
        owners_node = tree.css_first(
            'div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"] div.KeyFeatures_value__8LVNc'
        )
        if owners_node:
            owners_text = owners_node.text(strip=True)
            owners_match = re.search(r"(\d+)", owners_text)
            if owners_match:
                data["previous_owners"] = int(owners_match.group(1))

        # CO2 - dt[data-testid="envkv.co2Emissions-item"] + dd siguiente
        co2_dt = tree.css_first('dt[data-testid="envkv.co2Emissions-item"]')
        if co2_dt:
            # El dd viene inmediatamente después del dt
            parent = co2_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(co2_dt)
                    # El siguiente elemento debería ser el dd
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == "dd":
                            co2_text = dd_node.text(strip=True)
                            # Formato: "139 g/km"
                            co2_match = re.search(
                                r"(\d+)\s*g/km", co2_text, re.IGNORECASE
                            )
                            if co2_match:
                                data["co2_emissions_g_km"] = int(co2_match.group(1))
                except (ValueError, AttributeError):
                    pass

        # Consumo - dt[data-testid="envkv.consumptionDetails.fuel-item"] + dd siguiente
        consumption_dt = tree.css_first(
            'dt[data-testid="envkv.consumptionDetails.fuel-item"]'
        )
        if consumption_dt:
            parent = consumption_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(consumption_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == "dd":
                            cons_text = dd_node.text(strip=True)
                            # Formato: "6,0 l/100km"
                            cons_match = re.search(
                                r"(\d+[,.]?\d*)\s*l/100\s*km", cons_text, re.IGNORECASE
                            )
                            if cons_match:
                                data["consumption_l_100km"] = float(
                                    cons_match.group(1).replace(",", ".")
                                )
                except (ValueError, AttributeError):
                    pass

        # Cilindrada - dt[data-testid="cubicCapacity-item"] + dd siguiente
        cubic_dt = tree.css_first('dt[data-testid="cubicCapacity-item"]')
        if cubic_dt:
            parent = cubic_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(cubic_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == "dd":
                            cubic_text = dd_node.text(strip=True)
                            # Formato: "1.984 ccm" o "1.984 cm³"
                            cubic_match = re.search(
                                r"(\d{1,3}(?:\.\d{3})*)", cubic_text
                            )
                            if cubic_match:
                                data["cubic_capacity_ccm"] = int(
                                    cubic_match.group(1).replace(".", "")
                                )
                except (ValueError, AttributeError):
                    pass

        # Pegatina de emisiones - dt[data-testid="emissionsSticker-item"] + dd siguiente
        sticker_dt = tree.css_first('dt[data-testid="emissionsSticker-item"]')
        if sticker_dt:
            parent = sticker_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(sticker_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == "dd":
                            sticker_text = dd_node.text(strip=True)
                            # Formato: "4 (Verde)"
                            data["emissions_sticker"] = sticker_text
                except (ValueError, AttributeError):
                    pass

        # Descripción del vehículo - div[data-testid="vip-vehicle-description-text"]
        desc_node = tree.css_first('div[data-testid="vip-vehicle-description-text"]')
        if desc_node:
            # Obtener HTML completo y procesar
            desc_html = desc_node.html
            # Convertir <br> a saltos de línea
            desc_text = re.sub(r"<br\s*/?>", "\n", desc_html)
            # Eliminar tags HTML
            desc_text = re.sub(r"<[^>]+>", "", desc_text)
            # Decodificar entidades HTML
            desc_text = html.unescape(desc_text)
            data["description"] = desc_text.strip()

        # Si no se encontró CO2 con el selector específico, buscar en texto general
        full_text = tree.text(strip=True)
        if "co2_emissions_g_km" not in data:
            co2_match = re.search(r"(\d+)\s*g/km", full_text, re.IGNORECASE)
            if co2_match:
                data["co2_emissions_g_km"] = int(co2_match.group(1))

        # Si no se encontró consumo, buscar en texto general
        if "consumption_l_100km" not in data:
            cons_match = re.search(
                r"(\d+[,.]?\d*)\s*l/100\s*km", full_text, re.IGNORECASE
            )
            if cons_match:
                data["consumption_l_100km"] = float(
                    cons_match.group(1).replace(",", ".")
                )

        # Puertas
        doors_match = re.search(r"(\d)\s*Puertas", full_text, re.IGNORECASE)
        if doors_match:
            data["doors"] = int(doors_match.group(1))

        # Color exterior
        color_match = re.search(
            r"Color exterior[:\s]+([A-Za-zñáéíóú\s]+?)(?:\n|Tapizado|Interior|$)",
            full_text,
            re.IGNORECASE,
        )
        if color_match:
            data["color_exterior"] = color_match.group(1).strip()

        return data
