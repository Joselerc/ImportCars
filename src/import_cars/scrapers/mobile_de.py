from __future__ import annotations
import html
import logging
import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from selectolax.parser import HTMLParser

from ..config import ScraperSettings
from ..filters import UnifiedFilters
from ..models import (
    Consumption,
    Location,
    NormalizedListing,
    Price,
    Registration,
    SearchResult,
    Seller,
)
from .base import BaseScraper
from ..utils import build_mobile_de_search_url

SEARCH_URL = "https://www.mobile.de/es/categor%C3%ADa/veh%C3%ADculo/vhc:car,dmg:false"
logger = logging.getLogger(__name__)


class MobileDeScraper(BaseScraper):
    """
    Scraper para mobile.de que opera 100% con Playwright, navegando
    directamente a la página de resultados y parseando el HTML.
    """

    async def search(self, *, query: Dict[str, Any] | UnifiedFilters, limit: Optional[int] = None) -> SearchResult:
        # Compatibilidad con UnifiedFilters
        if isinstance(query, UnifiedFilters):
            page = query.page
            page_size = query.page_size
            search_url = build_mobile_de_search_url(query, page)
        else:
            page = int(query.get("page", 1))
            page_size = int(query.get("page_size", 24))
            search_url = SEARCH_URL

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.settings.headless,
                channel=self.settings.playwright_channel,
                slow_mo=self.settings.playwright_slow_mo or None,
            )
            context = await browser.new_context(
                locale="es-ES",
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                },
            )
            
            # Aplicar stealth a todas las páginas nuevas del contexto
            print("DEBUG: Aplicando playwright-stealth para evadir detección...")
            
            # El único método de scraping ahora es este.
            html, active_page = await self._fetch_results_page(
                context,
                url=search_url,
                page_number=page,
                page_size=page_size,
            )
            
            # Aplicar stealth a la página activa (ya aplicado en _fetch_results_page)
            # if active_page:
            #     stealth = Stealth()
            #     await stealth.apply_stealth_async(active_page)
            
            if not html:
                if active_page:
                    await active_page.close()
                await context.close()
                await browser.close()
                return SearchResult(listings=[], total_listings=0, result_page=page, has_next=False)

            # Pasar la página activa y los IDs interceptados para obtener HTML actualizado
            intercepted_ids = getattr(self, 'intercepted_vehicle_ids', [])
            print(f"DEBUG: Total de IDs interceptados: {len(intercepted_ids)}")
            data = await self._extract_listings_from_html(
                html,
                context,
                active_page,
                intercepted_ids,
                limit=limit,
            )
            
            # Cerrar la página después de extraer los datos
            if active_page:
                await active_page.close()
            
            await context.close()
            await browser.close()
            
            return self._parse_response(data, page_number=page, page_size=page_size)

    async def _fetch_results_page(
        self,
        context,
        *,
        url: str,
        page_number: int,
        page_size: int,
    ) -> tuple[Optional[str], Optional[object]]:
        """
        Navega a la página de resultados con Playwright y devuelve el contenido HTML y la página.
        """
        page = await context.new_page()
        
        # Aplicar stealth inmediatamente a la nueva página
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        # Lista para almacenar los IDs de los vehículos interceptados
        self.intercepted_vehicle_ids = []
        
        # Observar requests sin bloquearlos
        def handle_request(request):
            url = request.url
            # Buscar requests que contengan los IDs de vehículos
            if 'detalles.html' in url or 'id=' in url:
                print(f"DEBUG: Request capturado: {url[:100]}")
                # Extraer el ID de la URL
                match = re.search(r'[?&]id=(\d+)', url)
                if match:
                    vehicle_id = match.group(1)
                    if vehicle_id not in self.intercepted_vehicle_ids:
                        self.intercepted_vehicle_ids.append(vehicle_id)
                        print(f"DEBUG: ✓ ID capturado: {vehicle_id}")
        
        # Usar on("request") para observar sin bloquear
        page.on("request", handle_request)
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Aceptar cookies
            try:
                button = page.locator("button:has-text('Aceptar')")
                await button.wait_for(state="visible", timeout=7000)
                await button.click()
                print("DEBUG: Cookies aceptadas")
            except Exception:
                pass # Si no hay banner, asumimos que no es necesario

            # Esperar carga inicial
            await page.wait_for_timeout(2000)

            # *** HACER SCROLL GRADUAL AQUÍ PARA ACTIVAR LOS REQUESTS DE detalles.html ***
            print("DEBUG: Haciendo scroll gradual para activar lazy loading y capturar IDs...")
            
            # Obtener altura total de la página
            total_height = await page.evaluate("document.body.scrollHeight")
            viewport_height = await page.evaluate("window.innerHeight")
            
            # Scroll gradual en pasos para que cada anuncio se haga visible y dispare su request
            scroll_position = 0
            scroll_step = viewport_height * 0.8  # 80% del viewport
            
            while scroll_position < total_height:
                await page.evaluate(f"window.scrollTo(0, {scroll_position})")
                await page.wait_for_timeout(800)  # Esperar a que se disparen los requests
                scroll_position += scroll_step
                
                # Actualizar altura total por si se cargó más contenido
                total_height = await page.evaluate("document.body.scrollHeight")
            
            # Scroll al final para asegurar
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
            
            print(f"DEBUG: Scroll completado. IDs interceptados: {len(self.intercepted_vehicle_ids)}")
            print(f"DEBUG: IDs capturados: {self.intercepted_vehicle_ids[:10]}")

            html_content = await page.content()
            return html_content, page

        except Exception as e:
            logger.exception("Error durante la navegación con Playwright: %s", e)
            await page.close()
            return None, None

    async def _extract_listings_from_html(
        self,
        html_content: str,
        context,
        active_page=None,
        intercepted_ids=None,
        *,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Usar los IDs interceptados del Network durante el scroll en _fetch_results_page
        ids_from_js = intercepted_ids if intercepted_ids else []
        
        if active_page:
            print(f"DEBUG: Usando {len(ids_from_js)} IDs interceptados del Network")
            
            # Obtener HTML actualizado (ya hicimos scroll en _fetch_results_page)
            updated_html = await active_page.content()
            
            # Decodificar entidades HTML
            decoded_html = html.unescape(updated_html)
            tree = HTMLParser(decoded_html)
            print("DEBUG: Usando HTML actualizado de Playwright (decodificado)")
        else:
            # Decodificar entidades HTML también para el HTML inicial
            decoded_html = html.unescape(html_content)
            tree = HTMLParser(decoded_html)
            print("DEBUG: Usando HTML inicial (decodificado)")
        
        items = []
        
        # Selector actualizado para la nueva estructura de mobile.de
        listing_nodes = tree.css("a.BaseListing_containerLink___4jHz")
        print(f"DEBUG: Encontrados {len(listing_nodes)} anuncios en la página de resultados.")
        
        selected_nodes = listing_nodes[:limit] if limit else listing_nodes
        for i, node in enumerate(selected_nodes):
            print(f"DEBUG: Procesando anuncio {i+1}/{len(listing_nodes)}...")
            
            # Construir URL a partir del ID extraído con JavaScript
            if i < len(ids_from_js) and ids_from_js[i]:
                listing_id = ids_from_js[i]
                url = f"https://www.mobile.de/es/veh%C3%ADculos/detalles.html?id={listing_id}"
                print(f"DEBUG: URL construida con ID {listing_id}: {url}")
            else:
                # Fallback: intentar del HTML o generar ficticia
                href_attr = node.attributes.get("href", "")
                if href_attr and href_attr != "":
                    if href_attr.startswith("/"):
                        url = f"https://www.mobile.de{href_attr}"
                    else:
                        url = href_attr
                    print(f"DEBUG: URL del HTML: {url}")
                else:
                    testid = node.attributes.get("data-testid", "")
                    if testid:
                        testid_match = re.search(r"listing-(\d+)", testid)
                        if testid_match:
                            listing_num = testid_match.group(1)
                            url = f"https://www.mobile.de/listing-{listing_num}"
                        else:
                            url = f"https://www.mobile.de/listing-{i+1}"
                    else:
                        url = f"https://www.mobile.de/listing-{i+1}"
                    print(f"DEBUG: URL ficticia generada: {url}")
                
            # Generar un ID único basado en el data-testid o posición
            testid = node.attributes.get("data-testid", "")
            id_match = re.search(r"[?&]id=(\d+)", url)
            ad_id = id_match.group(1) if id_match else testid.replace("-link", "") if testid else f"mobile-de-{i+1}"

            title = node.css_first("h2.ListingTitle_title__p3CnA").text(strip=True) if node.css_first("h2.ListingTitle_title__p3CnA") else None
            # Limpiar el título de prefijos como "Patrocinado"
            if title:
                title = re.sub(r"^(Patrocinado|Sponsored)\s*", "", title, flags=re.IGNORECASE).strip()
            
            # --- Extracción de Marca y Modelo ---
            make = None
            model = None
            if title:
                # Lista de marcas conocidas para mejorar la precisión
                known_makes = [
                    "Mercedes-Benz", "BMW", "Audi", "Volkswagen", "Opel", "Ford", "Porsche",
                    "Skoda", "SEAT", "Renault", "Peugeot", "Citroën", "Fiat", "Toyota",
                    "Nissan", "Mazda", "Honda", "Hyundai", "Kia", "Volvo", "Tesla"
                ]
                # Limpiar el título de prefijos comunes como "Nuevo"
                clean_title = re.sub(r"^(Nuevo|New)\s*", "", title, flags=re.IGNORECASE).strip()
                
                for m in known_makes:
                    if clean_title.lower().startswith(m.lower()):
                        make = m
                        # El modelo es lo que sigue a la marca
                        model_part = clean_title[len(m):].strip()
                        # Tomamos las primeras palabras como modelo, evitando textos largos
                        model = " ".join(model_part.split()[:3])
                        break
            
            # --- Extracción de precio desde el listado ---
            price_text = node.css_first("span.PriceLabel_mainPrice__3SZut").text(strip=True) if node.css_first("span.PriceLabel_mainPrice__3SZut") else None
            price_bruto = None
            price_neto = None

            if price_text:
                # Extraer número del precio (ej: "18.950 €" -> 18950)
                price_match = re.search(r"([0-9\.,]+)", price_text.replace("\u00A0", ""))
                if price_match:
                    price_bruto = float(price_match.group(1).replace(".", "").replace(",", "."))
            
            details_node = node.css_first("div[data-testid='listing-details-attributes']")
            details_text = details_node.text(separator=" ", strip=True) if details_node else ""
            
            mileage_match = re.search(r"([0-9\.,]+)\s*km", details_text, re.IGNORECASE)
            mileage = int(mileage_match.group(1).replace(".", "").replace(",", "")) if mileage_match else None
            
            reg_match = re.search(r"(\d{2}/\d{4})", details_text)
            registration = None
            if reg_match:
                m_str, y_str = reg_match.group(1).split("/")
                if m_str and y_str:
                    registration = Registration(year=int(y_str), month=int(m_str))

            # Power (kW and HP) - Coger kW es más robusto y luego se convierte a CV
            power_kw_match = re.search(r"(\d+)\s*kW", details_text, re.IGNORECASE)
            power_kw = int(power_kw_match.group(1)) if power_kw_match else None
            power_hp = int(power_kw * 1.35962) if power_kw else None

            # --- Especificaciones técnicas ---
            fuel_type = None
            transmission = None
            body_type = None
            color_exterior = None
            doors = None

            if details_text:
                # Fuel Type por palabras clave
                fuel_types = ["Diesel", "Gasolina", "Eléctrico", "Híbrido"]
                for ft in fuel_types:
                    if re.search(r'\b' + ft + r'\b', details_text, re.IGNORECASE):
                        fuel_type = ft
                        break

            # Visitar página de detalle si tenemos una URL real
            detail_data = {}
            if url and url.startswith('https://www.mobile.de/es/veh') and i < 3:
                detail_data = await self._scrape_detail_page(context, url)

            # --- Lógica de IVA Dinámica ---
            location = detail_data.get("location")
            if price_bruto and not price_neto:
                vat_rate = 1.19 if location and location.get("country_code") == "DE" else 1.21
                price_neto = round(price_bruto / vat_rate, 2)
            elif price_neto and not price_bruto:
                vat_rate = 1.19 if location and location.get("country_code") == "DE" else 1.21
                price_bruto = round(price_neto * vat_rate, 2)

            items.append({
                "id": ad_id,
                "url": url,
                "title": title,
                "make": make,
                "model": model,
                "price_eur": price_bruto,
                "price_net_eur": price_neto,
                "mileageInKm": mileage,
                "firstRegistration": {"year": registration.year, "month": registration.month} if registration else None,
                "powerHp": power_hp,
                "powerKw": power_kw,
                "fuelType": fuel_type,
                "transmission": transmission,
                "bodyType": body_type,
                "doors": doors,
                "colorExterior": color_exterior,
                "co2Emissions": detail_data.get("co2_emissions_g_km"),
                "detail_data": detail_data,
            })
        
        if not items:
            logger.warning("No se encontraron anuncios en la página de resultados de mobile.de")

        # Comprobar si hay un enlace a la página siguiente para la paginación
        next_page_node = tree.css_first("a.pagination--item[rel='next']")
        has_next = next_page_node is not None

        return {"result": {"items": items, "total": len(items), "pageInfo": {"hasNextPage": has_next}}}

    async def _get_real_urls_with_javascript(self, context) -> List[str]:
        """
        Obtiene las URLs reales usando JavaScript después de que se carguen dinámicamente.
        """
        try:
            # Obtener la página actual del contexto
            pages = context.pages
            if not pages:
                print("DEBUG: No hay páginas disponibles en el contexto")
                return []
            
            page = pages[0]  # Usar la primera página (la actual)
            
            # Esperar a que las URLs se carguen dinámicamente
            await page.wait_for_timeout(2000)  # Esperar 2 segundos
            
            # Ejecutar JavaScript para obtener las URLs reales
            urls = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a.BaseListing_containerLink___4jHz');
                    const urls = [];
                    
                    links.forEach((link, index) => {
                        let url = link.href;
                        
                        // Si la URL es válida y no es la página actual
                        if (url && url !== window.location.href && url !== '') {
                            urls.push(url);
                        } else {
                            urls.push(null);
                        }
                    });
                    
                    return urls;
                }
            """)
            
            # Filtrar URLs válidas
            valid_urls = []
            for url in urls:
                if url and url.startswith('http'):
                    valid_urls.append(url)
                else:
                    valid_urls.append(None)
            
            print(f"DEBUG: JavaScript encontró {len(valid_urls)} URLs, {sum(1 for u in valid_urls if u)} válidas")
            
            return valid_urls
            
        except Exception as e:
            print(f"DEBUG: Error obteniendo URLs con JavaScript: {e}")
            return []

    async def _get_real_urls_from_page(self, context) -> List[str]:
        """
        Obtiene las URLs reales de los anuncios usando JavaScript desde la página actual.
        """
        try:
            # Obtener la página actual del contexto
            pages = context.pages
            if not pages:
                print("DEBUG: No hay páginas disponibles en el contexto")
                return []
            
            page = pages[0]  # Usar la primera página (la actual)
            
            # Ejecutar JavaScript para obtener las URLs reales
            urls = await page.evaluate("""
                () => {
                    const links = document.querySelectorAll('a.BaseListing_containerLink___4jHz');
                    const urls = [];
                    
                    links.forEach((link, index) => {
                        let url = link.getAttribute('href');
                        
                        // Si la URL es relativa, convertirla en absoluta
                        if (url && url.startsWith('/')) {
                            url = 'https://www.mobile.de' + url;
                        }
                        
                        urls.push(url);
                    });
                    
                    return urls;
                }
            """)
            
            # Filtrar URLs válidas
            valid_urls = [url for url in urls if url and url.startswith('http')]
            print(f"DEBUG: Obtenidas {len(valid_urls)} URLs reales de {len(urls)} anuncios")
            
            return valid_urls
            
        except Exception as e:
            print(f"DEBUG: Error obteniendo URLs reales: {e}")
            return []

    async def _scrape_detail_page(self, context, url: str) -> Dict[str, Any]:
        """
        Visita la página de detalle de un anuncio y extrae datos técnicos usando
        los selectores data-testid específicos de mobile.de.
        """
        page = await context.new_page()
        details = {}
        print(f"--- Visitando página de detalle: {url} ---")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            html = await page.content()
            tree = HTMLParser(html)

            # Buscar la lista de datos técnicos
            tech_data_list = tree.css_first("dl.DataList_alternatingColorsList__8ejqq")
            
            if not tech_data_list:
                print("DEBUG: No se encontró la lista de datos técnicos.")
                return details

            # Mapeo de data-testid a campos de nuestro modelo
            field_mapping = {
                "envkv.co2Emissions-item": "co2_emissions_g_km",
                "envkv.energyConsumption-item": "consumption_l_100km", 
                "cubicCapacity-item": "engine_displacement_cc",
                "numSeats-item": "seats",
                "doorCount-item": "doors",
                "transmission-item": "transmission",
                "color-item": "color_exterior",
                "interior-item": "color_interior",
                "emissionClass-item": "emission_class",
                "numberOfPreviousOwners-item": "previous_owners",
                "hu-item": "inspection_valid_until",
                "category-item": "body_type_detail"
            }
            
            # Extraer todos los pares dt/dd
            dt_elements = tech_data_list.css("dt[data-testid]")
            
            for dt in dt_elements:
                # Código corregido arriba
                testid = dt.attributes.get("data-testid")
                dd = dt.css_first("+ dd") # El elemento dd que sigue inmediatamente al dt
                
                if testid and dd:
                    field_name = field_mapping.get(testid)
                    if field_name:
                        value_text = dd.text(strip=True)
                        
                        # Limpieza y conversión de datos específicos
                        if field_name == "co2_emissions_g_km":
                            match = re.search(r"(\d+)", value_text)
                            details[field_name] = int(match.group(1)) if match else None
                        elif field_name == "consumption_l_100km":
                            match = re.search(r"([0-9\.,]+)\s*l/100km", value_text)
                            details[field_name] = float(match.group(1).replace(",", ".")) if match else None
                        elif field_name == "engine_displacement_cc":
                            match = re.search(r"([0-9\.,]+)\s*ccm", value_text)
                            details[field_name] = int(match.group(1).replace(".", "")) if match else None
                        elif field_name == "doors":
                            match = re.search(r"(\d+)", value_text)
                            details[field_name] = int(match.group(1)) if match else None
                        elif field_name == "previous_owners":
                            match = re.search(r"(\d+)", value_text)
                            details[field_name] = int(match.group(1)) if match else None
                        elif field_name == "inspection_valid_until":
                            match = re.search(r"(\d{2}/\d{4})", value_text)
                            if match:
                                m_str, y_str = match.group(1).split("/")
                                details[field_name] = {"year": int(y_str), "month": int(m_str)}
                            else:
                                details[field_name] = value_text # Guardar texto si no se puede parsear
                        else:
                            details[field_name] = value_text
                
            
            print(f"DEBUG: Datos de detalle extraídos: {details}")

        except Exception as e:
            print(f"Error procesando página de detalle {url}: {e}")
        finally:
            await page.close()
            
        return details

    def _parse_response(self, data: Dict[str, Any], *, page_number: int, page_size: int) -> SearchResult:
        search_data = data.get("result", {})
        listings_data = search_data.get("items", [])
        
        listings = []
        for item in listings_data:
            listing = self._to_listing(item)
            if listing is not None:
                listings.append(listing)

        return SearchResult(
            listings=listings,
            total_listings=search_data.get("total"),
            result_page=page_number,
            result_page_size=len(listings),
            has_next=search_data.get("pageInfo", {}).get("hasNextPage", False),
        )

    def _to_listing(self, node: Dict[str, Any]) -> Optional[NormalizedListing]:
        price_info = node.get("price") or {}
        amount = price_info.get("amount")

        reg_info = node.get("firstRegistration")
        registration = Registration(year=reg_info["year"], month=reg_info["month"]) if reg_info else None

        # Priorizar datos de la página de detalle si existen
        detail_data = node.get("detail_data", {})

        return NormalizedListing(
            listing_id=node.get("id"),
            source="mobile_de",
            url=node.get("url"),
            scraped_at=datetime.now(UTC),
            title=node.get("title"),
            make=node.get("make"),
            model=node.get("model"),
            price_eur=node.get("price_eur"),
            price_net_eur=node.get("price_net_eur"),
            price_original=Price(amount=node.get("price_eur"), currency_code="EUR") if node.get("price_eur") else None,
            mileage_km=node.get("mileageInKm"),
            first_registration=registration,
            power_hp=detail_data.get("power_hp", node.get("powerHp")),
            power_kw=node.get("powerKw"),
            fuel_type=detail_data.get("fuel_type", node.get("fuelType")),
            transmission=node.get("transmission"),
            body_type=detail_data.get("body_type", node.get("bodyType")),
            doors=detail_data.get("doors", node.get("doors")),
            seats=detail_data.get("seats"),
            color_exterior=detail_data.get("color_exterior", node.get("colorExterior")),
            co2_emissions_g_km=detail_data.get("co2_emissions_g_km"),
            consumption_l_100km=detail_data.get("consumption_l_100km"),
            description=detail_data.get("description"),
            seller=detail_data.get("seller"),
            location=detail_data.get("location"),
            engine_displacement_cc=detail_data.get("engine_displacement_cc"),
        )


__all__ = ["MobileDeScraper"]
