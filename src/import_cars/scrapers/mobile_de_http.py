"""
Scraper HTTP para mobile.de usando curl_cffi
Mucho más rápido que Playwright (sin navegador)
"""
import html
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from curl_cffi import requests as cffi
from selectolax.parser import HTMLParser

from ..config import ScraperSettings, get_settings
from ..filters import UnifiedFilters
from ..models import (
    Consumption,
    Location,
    Price,
    Registration,
    SearchResult,
    NormalizedListing,
)
from ..utils import build_mobile_de_search_url
from ..utils.import_calculator import import_calculator, TipoCompra


class MobileDeHttpScraper:
    """Scraper HTTP rápido para mobile.de usando curl_cffi"""

    def __init__(self, settings: Optional[ScraperSettings] = None):
        self.settings = settings or get_settings()
        self.source = "mobile_de"
        
        # Crear sesión con fingerprint TLS de Chrome real
        self.session = cffi.Session(
            impersonate="chrome",
            timeout=self.settings.request_timeout,
        )
        
        # Headers realistas
        self.headers = {
            "user-agent": self.settings.user_agent,
            "accept-language": "es-ES,es;q=0.9",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }

    def _get(self, url: str):
        last_error = None
        for _ in range(max(1, self.settings.max_retries)):
            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                return response
            except Exception as exc:
                last_error = exc
        raise last_error

    def _build_search_url(self, filters: UnifiedFilters, page: int = 1) -> str:
        """Construir URL de búsqueda con filtros usando el URL builder"""
        return build_mobile_de_search_url(filters, page)

    def search(self, query: Optional[UnifiedFilters] = None, limit: Optional[int] = None) -> SearchResult:
        """Buscar anuncios con filtros"""
        filters = query or UnifiedFilters()
        all_listings = []
        page = 1
        total_available = None
        
        print(f"Iniciando busqueda HTTP en mobile.de...")
        
        while True:
            url = self._build_search_url(filters, page)
            print(f"Pagina {page}: {url}")
            
            # Obtener HTML de la página de listado
            response = self._get(url)
            
            # Extraer total de resultados (solo en la primera página)
            if page == 1:
                total_available = self._extract_total_results(response.text)
                if total_available:
                    print(f"Total de anuncios disponibles: {total_available}")
            
            # Extraer IDs de anuncios
            ids = self._extract_ids_from_listing(response.text)
            print(f"   OK - {len(ids)} IDs encontrados")
            
            if not ids:
                print("   ADVERTENCIA: No se encontraron mas anuncios")
                break
            
            # Obtener detalles de cada anuncio
            listings = [
                listing
                for listing in self._fetch_details_parallel(ids, max_workers=self.settings.concurrency)
                if self._matches_filters(listing, filters)
            ]
            all_listings.extend(listings)
            
            print(f"   OK - {len(listings)} anuncios procesados (Total: {len(all_listings)}" + (f"/{total_available}" if total_available else "") + ")")
            
            # Verificar límite
            if limit and len(all_listings) >= limit:
                all_listings = all_listings[:limit]
                break
            
            # Verificar si hay más páginas
            has_next = self._has_next_page(response.text)
            if not has_next:
                print("   INFO: No hay mas paginas")
                break
            
            page += 1
        
        print(f"\nScraping completado: {len(all_listings)} anuncios extraidos" + (f" de {total_available} totales" if total_available else ""))
        
        # Calcular costes de importación para cada anuncio
        if all_listings:
            print("\n" + "="*80)
            print("ANALISIS DE COSTES DE IMPORTACION (Alemania -> Espana)")
            print("="*80)
            self._print_import_analysis(all_listings)
        
        return SearchResult(
            listings=all_listings,
            total_listings=total_available or len(all_listings),
            result_page=page,
            result_page_size=len(all_listings),
            has_next=False,
        )

    def _extract_total_results(self, html_content: str) -> Optional[int]:
        """Extraer el número total de resultados de la búsqueda"""
        try:
            # Método 1: Buscar en el JSON embebido de Next.js
            match = re.search(r'"numResultsTotal":(\d+)', html_content)
            if match:
                return int(match.group(1))
            
            # Método 2: Buscar en el texto visible (fallback)
            match = re.search(r'(\d+)\s*resultados?', html_content, re.IGNORECASE)
            if match:
                return int(match.group(1))
            
            return None
        except Exception:
            return None

    def _extract_ids_from_listing(self, html_content: str) -> List[str]:
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

    def _matches_filters(self, listing: NormalizedListing, filters: UnifiedFilters) -> bool:
        """Filtra resultados HTTP para evitar anuncios ajenos a la búsqueda."""
        if filters.make and (listing.make or "").upper() != filters.make.upper():
            return False

        if filters.model:
            haystack = " ".join(filter(None, [listing.model, listing.title])).upper()
            if filters.model.upper() not in haystack:
                return False

        if filters.price_range and listing.price_eur is not None:
            if filters.price_range.min_price and listing.price_eur < filters.price_range.min_price:
                return False
            if filters.price_range.max_price and listing.price_eur > filters.price_range.max_price:
                return False

        if filters.year_range and listing.first_registration:
            year = listing.first_registration.year
            if filters.year_range.min_year and year < filters.year_range.min_year:
                return False
            if filters.year_range.max_year and year > filters.year_range.max_year:
                return False

        if filters.mileage_range and listing.mileage_km is not None:
            if filters.mileage_range.min_mileage and listing.mileage_km < filters.mileage_range.min_mileage:
                return False
            if filters.mileage_range.max_mileage and listing.mileage_km > filters.mileage_range.max_mileage:
                return False

        if filters.power_range and listing.power_hp is not None:
            if filters.power_range.min_power_hp and listing.power_hp < filters.power_range.min_power_hp:
                return False
            if filters.power_range.max_power_hp and listing.power_hp > filters.power_range.max_power_hp:
                return False

        return True

    def _has_next_page(self, html_content: str) -> bool:
        """Verificar si hay página siguiente"""
        tree = HTMLParser(html_content)
        next_link = tree.css_first('a[rel="next"]')
        return next_link is not None

    def _fetch_details_parallel(self, ids: List[str], max_workers: int = 10) -> List[NormalizedListing]:
        """Obtener detalles de múltiples anuncios en paralelo"""
        listings = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_id = {executor.submit(self._fetch_detail, id_): id_ for id_ in ids}
            
            for future in as_completed(future_to_id):
                try:
                    listing = future.result()
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    id_ = future_to_id[future]
                    print(f"      ERROR en ID {id_}: {e}")
        
        return listings

    def _fetch_detail(self, vehicle_id: str) -> Optional[NormalizedListing]:
        """Obtener detalles de un anuncio específico"""
        url = f"https://www.mobile.de/es/veh%C3%ADculos/detalles.html?id={vehicle_id}"
        
        try:
            response = self._get(url)
            
            return self._parse_detail_page(response.text, vehicle_id, url)
        
        except Exception as e:
            print(f"      ERROR obteniendo detalle {vehicle_id}: {e}")
            return None

    def _parse_detail_page(self, html_content: str, vehicle_id: str, url: str) -> Optional[NormalizedListing]:
        """Parsear página de detalle completa"""
        tree = HTMLParser(html.unescape(html_content))
        images = self._extract_images(tree, html_content)
        
        # Título - h2.typography_headline__yJCAO
        title = None
        title_node = tree.css_first('h2.typography_headline__yJCAO')
        if title_node:
            title = title_node.text(strip=True)
        
        # Subtítulo/Modelo - div.MainCtaBox_subTitle__wYybO
        subtitle = None
        subtitle_node = tree.css_first('div.MainCtaBox_subTitle__wYybO')
        if subtitle_node:
            subtitle = subtitle_node.text(strip=True)
        
        # Precio - div.MainPriceArea_mainPrice__xCkfs
        price_eur = None
        price_node = tree.css_first('div.MainPriceArea_mainPrice__xCkfs')
        if not price_node:
            price_node = tree.css_first('span[data-testid="prime-price"]')
        if not price_node:
            price_node = tree.css_first('span.PriceLabel_mainPrice__3SZut')
        if price_node:
            price_text = price_node.text(strip=True)
            # Eliminar espacios no separables y extraer números
            price_match = re.search(r"([0-9\.]+)", price_text.replace("\u00A0", "").replace(" ", ""))
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
            title_without_make = " ".join(title.split()[1:]) if len(title.split()) > 1 else ""
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
            scraped_at=datetime.now(timezone.utc),
            title=f"{title} {subtitle}".strip() if subtitle else title,
            make=make,
            model=model,
            price_eur=price_eur,
            price_net_eur=price_net_eur,
            price_original=Price(amount=price_eur, currency_code="EUR") if price_eur else None,
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

    def _extract_images(self, tree: HTMLParser, html_content: str) -> List[str]:
        """Extraer imágenes relevantes del anuncio."""
        candidates: List[str] = []
        seen = set()

        def add(url: Optional[str]) -> None:
            if not url or url in seen:
                return
            if not url.startswith("http"):
                return
            lowered = url.lower()
            if any(token in lowered for token in ("logo", "icon", "sprite", "dealer-rating")):
                return
            seen.add(url)
            candidates.append(url)

        for node in tree.css("meta[property='og:image'], meta[name='twitter:image']"):
            add(node.attributes.get("content"))

        for node in tree.css("img"):
            add(node.attributes.get("src"))
            add(node.attributes.get("data-src"))

        for match in re.findall(r'https://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*', html_content, re.IGNORECASE):
            add(match)

        return candidates[:8]

    def _extract_seller_info(self, tree: HTMLParser) -> Optional[dict]:
        """Extraer información del vendedor"""
        from ..models import Seller
        
        # Buscar el contenedor del vendedor
        seller_container = tree.css_first('div.MainSellerInfo_titleAndRatingBlock__rDi0i')
        if not seller_container:
            return None
        
        # Extraer el texto del label
        label_node = seller_container.css_first('div.typography_label__EkjGc')
        if not label_node:
            return None
        
        label_text = label_node.text(strip=True)
        
        # Determinar tipo de vendedor
        # Buscar patrones en español y alemán
        is_private = any(keyword in label_text.lower() for keyword in [
            'vendedor particular', 'particular', 'privat', 'private seller', 'privatverkäufer'
        ])
        
        seller_type = "private" if is_private else "dealer"
        seller_name = None
        rating = None
        rating_count = None
        
        if not is_private:
            # Si es concesionario, buscar el nombre en el enlace
            link_node = label_node.css_first('a.link_Link__B0oSi')
            if link_node:
                seller_name = link_node.text(strip=True)
            
            # Buscar rating
            rating_node = seller_container.css_first('div.ratingStars_RatingStars__fKi_d')
            if rating_node:
                # Extraer rating del label sr-only
                sr_label = rating_node.css_first('span.ratingStars_SrOnlyRatingStarsLabel__03fSs')
                if sr_label:
                    rating_text = sr_label.text(strip=True)
                    # Formato: "4.6 estrellas" o "4.6 stars"
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))
        
        return Seller(
            type=seller_type,
            name=seller_name,
            rating=rating,
            rating_count=rating_count
        )

    def _extract_key_features(self, tree: HTMLParser) -> Dict[str, Any]:
        """Extraer datos de KeyFeatures usando los selectores específicos"""
        data = {}
        
        # Kilometraje - div[data-testid="vip-key-features-list-item-mileage"]
        mileage_node = tree.css_first('div[data-testid="vip-key-features-list-item-mileage"] div.KeyFeatures_value__8LVNc')
        if mileage_node:
            km_text = mileage_node.text(strip=True)
            km_match = re.search(r"(\d{1,3}(?:\.\d{3})*)", km_text)
            if km_match:
                data["mileage_km"] = int(km_match.group(1).replace(".", ""))
        
        # Potencia - div[data-testid="vip-key-features-list-item-power"]
        power_node = tree.css_first('div[data-testid="vip-key-features-list-item-power"] div.KeyFeatures_value__8LVNc')
        if power_node:
            power_text = power_node.text(strip=True)
            # Formato: "162 kW (220 cv)"
            kw_match = re.search(r"(\d+)\s*kW\s*\((\d+)\s*cv\)", power_text, re.I)
            if kw_match:
                data["power_kw"] = int(kw_match.group(1))
                data["power_hp"] = int(kw_match.group(2))
        
        # Combustible - div[data-testid="vip-key-features-list-item-fuel"]
        fuel_node = tree.css_first('div[data-testid="vip-key-features-list-item-fuel"] div.KeyFeatures_value__8LVNc')
        if fuel_node:
            data["fuel_type"] = fuel_node.text(strip=True)
        
        # Transmisión - div[data-testid="vip-key-features-list-item-transmission"]
        transmission_node = tree.css_first('div[data-testid="vip-key-features-list-item-transmission"] div.KeyFeatures_value__8LVNc')
        if transmission_node:
            trans_text = transmission_node.text(strip=True)
            if "manual" in trans_text.lower():
                data["transmission"] = "Manual"
            elif "automát" in trans_text.lower():
                data["transmission"] = "Automático"
            else:
                data["transmission"] = trans_text
        
        # Primera matriculación - div[data-testid="vip-key-features-list-item-firstRegistration"]
        first_reg_node = tree.css_first('div[data-testid="vip-key-features-list-item-firstRegistration"] div.KeyFeatures_value__8LVNc')
        if first_reg_node:
            data["first_registration"] = first_reg_node.text(strip=True)
        
        # Propietarios anteriores - div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"]
        owners_node = tree.css_first('div[data-testid="vip-key-features-list-item-numberOfPreviousOwners"] div.KeyFeatures_value__8LVNc')
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
                        if dd_node.tag == 'dd':
                            co2_text = dd_node.text(strip=True)
                            # Formato: "139 g/km"
                            co2_match = re.search(r"(\d+)\s*g/km", co2_text, re.I)
                            if co2_match:
                                data["co2_emissions_g_km"] = int(co2_match.group(1))
                except (ValueError, AttributeError):
                    pass
        
        # Consumo - dt[data-testid="envkv.consumptionDetails.fuel-item"] + dd siguiente
        consumption_dt = tree.css_first('dt[data-testid="envkv.consumptionDetails.fuel-item"]')
        if consumption_dt:
            parent = consumption_dt.parent
            if parent:
                children = list(parent.iter())
                try:
                    dt_index = children.index(consumption_dt)
                    if dt_index + 1 < len(children):
                        dd_node = children[dt_index + 1]
                        if dd_node.tag == 'dd':
                            cons_text = dd_node.text(strip=True)
                            # Formato: "6,0 l/100km"
                            cons_match = re.search(r"(\d+[,.]?\d*)\s*l/100\s*km", cons_text, re.I)
                            if cons_match:
                                data["consumption_l_100km"] = float(cons_match.group(1).replace(",", "."))
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
                        if dd_node.tag == 'dd':
                            cubic_text = dd_node.text(strip=True)
                            # Formato: "1.984 ccm" o "1.984 cm³"
                            cubic_match = re.search(r"(\d{1,3}(?:\.\d{3})*)", cubic_text)
                            if cubic_match:
                                data["cubic_capacity_ccm"] = int(cubic_match.group(1).replace(".", ""))
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
                        if dd_node.tag == 'dd':
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
            co2_match = re.search(r"(\d+)\s*g/km", full_text, re.I)
            if co2_match:
                data["co2_emissions_g_km"] = int(co2_match.group(1))
        
        # Si no se encontró consumo, buscar en texto general
        if "consumption_l_100km" not in data:
            cons_match = re.search(r"(\d+[,.]?\d*)\s*l/100\s*km", full_text, re.I)
            if cons_match:
                data["consumption_l_100km"] = float(cons_match.group(1).replace(",", "."))
        
        # Puertas
        doors_match = re.search(r"(\d)\s*Puertas", full_text, re.I)
        if doors_match:
            data["doors"] = int(doors_match.group(1))
        
        # Color exterior
        color_match = re.search(r"Color exterior[:\s]+([A-Za-zñáéíóú\s]+?)(?:\n|Tapizado|Interior|$)", full_text, re.I)
        if color_match:
            data["color_exterior"] = color_match.group(1).strip()
        
        return data
    
    def _print_import_analysis(self, listings: List[NormalizedListing]) -> None:
        """Imprime análisis de costes de importación para cada anuncio"""
        
        for idx, listing in enumerate(listings, 1):
            print(f"\n{'-'*80}")
            print(f"ANUNCIO #{idx}")
            print(f"{'-'*80}")
            
            # Información básica
            print(f"Vehiculo: {listing.title}")
            print(f"URL: {listing.url}")
            print(f"Precio Alemania: {listing.price_eur:,.2f} EUR")
            
            # Tipo de vendedor
            seller_type_label = "Concesionario" if listing.seller and listing.seller.type == "dealer" else "Particular"
            seller_name = f" ({listing.seller.name})" if listing.seller and listing.seller.name else ""
            print(f"{seller_type_label}{seller_name}")
            
            # Datos técnicos relevantes
            if listing.mileage_km:
                print(f"Kilometraje: {listing.mileage_km:,} km")
            if listing.first_registration:
                print(f"Primera matriculacion: {listing.first_registration.month}/{listing.first_registration.year}")
            if listing.power_hp:
                print(f"Potencia: {listing.power_hp} CV")
            
            # CO2 y cálculo de costes
            if listing.co2_emissions_g_km:
                print(f"CO2: {listing.co2_emissions_g_km} g/km")
                self._calculate_and_print_import_costs(listing, listing.co2_emissions_g_km)
            else:
                print(f"ADVERTENCIA: CO2 no disponible")
                print(f"\nCalculando rangos segun posibles emisiones de CO2:")
                self._print_co2_scenarios(listing)
    
    def _calculate_and_print_import_costs(self, listing: NormalizedListing, co2: int) -> None:
        """Calcula y muestra los costes de importación para un CO2 específico"""
        
        if not listing.price_eur:
            print("❌ No se puede calcular (precio no disponible)")
            return
        
        # Determinar tipo de compra según el vendedor
        is_dealer = listing.seller and listing.seller.type == "dealer"
        
        print(f"\nCOSTES DE IMPORTACION:")
        
        if is_dealer:
            # Mostrar ambos casos de empresa
            print(f"\n  Caso 1: Compra a EMPRESA (IVA Aleman)")
            costes_iva = import_calculator.calcular_costes_importacion(
                listing.price_eur,
                TipoCompra.EMPRESA_IVA,
                co2
            )
            print(f"     Precio Alemania:    {listing.price_eur:>10,.2f}€")
            print(f"     + ITP:              {costes_iva['itp']:>10,.2f}€")
            print(f"     + IEDMT ({costes_iva['tasa_iedmt']}%):    {costes_iva['iedmt']:>10,.2f}€")
            print(f"     + Transporte:       {costes_iva['transporte']:>10,.2f}€")
            print(f"     + ITV:              {costes_iva['itv_tasa']:>10,.2f}€")
            print(f"     + Traducciones:     {costes_iva['traducciones']:>10,.2f}€")
            print(f"     + IVTM:             {costes_iva['ivtm']:>10,.2f}€")
            print(f"     + Placas:           {costes_iva['placas']:>10,.2f}€")
            print(f"     {'-'*36}")
            print(f"     = BREAK-EVEN:    {costes_iva['break_even']:>10,.2f} EUR")
            
            print(f"\n  Caso 2: Compra a EMPRESA (Regimen Margen 25a)")
            costes_margen = import_calculator.calcular_costes_importacion(
                listing.price_eur,
                TipoCompra.EMPRESA_MARGEN,
                co2
            )
            print(f"     Precio Alemania:    {listing.price_eur:>10,.2f}€")
            print(f"     + ITP:              {costes_margen['itp']:>10,.2f}€")
            print(f"     + IEDMT ({costes_margen['tasa_iedmt']}%):    {costes_margen['iedmt']:>10,.2f}€")
            print(f"     + Costes base:      {costes_margen['costes_base_total']:>10,.2f}€")
            print(f"     {'-'*36}")
            print(f"     = BREAK-EVEN:    {costes_margen['break_even']:>10,.2f} EUR")
            
            # Destacar el mejor
            print(f"\n  Rango de precio en Espana: {costes_iva['break_even']:,.2f} EUR - {costes_margen['break_even']:,.2f} EUR")
        else:
            # Particular
            print(f"\n  Compra a PARTICULAR")
            costes = import_calculator.calcular_costes_importacion(
                listing.price_eur,
                TipoCompra.PARTICULAR,
                co2
            )
            print(f"     Precio Alemania:    {listing.price_eur:>10,.2f}€")
            print(f"     + ITP (4%):         {costes['itp']:>10,.2f}€")
            print(f"     + IEDMT ({costes['tasa_iedmt']}%):    {costes['iedmt']:>10,.2f}€")
            print(f"     + Transporte:       {costes['transporte']:>10,.2f}€")
            print(f"     + ITV:              {costes['itv_tasa']:>10,.2f}€")
            print(f"     + Traducciones:     {costes['traducciones']:>10,.2f}€")
            print(f"     + IVTM:             {costes['ivtm']:>10,.2f}€")
            print(f"     + Placas:           {costes['placas']:>10,.2f}€")
            print(f"     {'-'*36}")
            print(f"     = BREAK-EVEN:    {costes['break_even']:>10,.2f} EUR")
    
    def _print_co2_scenarios(self, listing: NormalizedListing) -> None:
        """Muestra escenarios de coste según diferentes rangos de CO2"""
        
        if not listing.price_eur:
            print("❌ No se puede calcular (precio no disponible)")
            return
        
        is_dealer = listing.seller and listing.seller.type == "dealer"
        
        # Escenarios de CO2
        scenarios = [
            ("MEJOR CASO (CO2 <=120 g/km, IEDMT 0%)", 120),
            ("CASO MEDIO (CO2 121-159 g/km, IEDMT 4.75%)", 140),
            ("PEOR CASO (CO2 >=200 g/km, IEDMT 14.75%)", 200),
        ]
        
        print()
        for label, co2 in scenarios:
            print(f"  {'-'*76}")
            print(f"  {label}")
            print(f"  {'-'*76}")
            
            if is_dealer:
                # Mostrar rango para empresa
                costes_iva = import_calculator.calcular_costes_importacion(
                    listing.price_eur, TipoCompra.EMPRESA_IVA, co2
                )
                costes_margen = import_calculator.calcular_costes_importacion(
                    listing.price_eur, TipoCompra.EMPRESA_MARGEN, co2
                )
                print(f"  Precio:       {listing.price_eur:>10,.2f}€ + IEDMT ({costes_iva['tasa_iedmt']}%): {costes_iva['iedmt']:,.2f}€ + Costes: {costes_iva['costes_base_total']:,.2f}€")
                print(f"  Break-even: {costes_iva['break_even']:,.2f} EUR - {costes_margen['break_even']:,.2f} EUR")
            else:
                # Particular
                costes = import_calculator.calcular_costes_importacion(
                    listing.price_eur, TipoCompra.PARTICULAR, co2
                )
                print(f"  Precio:       {listing.price_eur:>10,.2f}€ + ITP: {costes['itp']:,.2f}€ + IEDMT ({costes['tasa_iedmt']}%): {costes['iedmt']:,.2f}€ + Costes: {costes['costes_base_total']:,.2f}€")
                print(f"  Break-even: {costes['break_even']:,.2f} EUR")

