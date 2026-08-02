"""
CLI mejorado para scraping con filtros y exportación
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import orjson
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Configurar console para Windows
console = Console(force_terminal=True, legacy_windows=False)

from .analysis import apply_opportunity_analysis
from .enrichment import Co2Enricher
from .exporters import ExcelExporter, CSVExporter
from .filters import (
    UnifiedFilters,
    FuelType,
    Transmission,
    SortBy,
    PriceRange,
    YearRange,
    MileageRange,
    PowerRange,
)
from .matching import equivalent_vehicle_criteria
from .scrapers import CochesNetScraper, MobileDeHttpScraper
from .services import break_even_scenarios

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = typer.Typer(
    help="Scraper CLI avanzado para mobile.de y coches.net con filtros y exportación"
)
co2_enricher = Co2Enricher()


def _parse_fuel_types(fuel_types_str: Optional[str]) -> Optional[List[FuelType]]:
    """Parsea tipos de combustible desde string separado por comas"""
    if not fuel_types_str:
        return None

    fuel_map = {
        "gasolina": FuelType.GASOLINE,
        "gasoline": FuelType.GASOLINE,
        "diesel": FuelType.DIESEL,
        "electrico": FuelType.ELECTRIC,
        "electric": FuelType.ELECTRIC,
        "hibrido": FuelType.HYBRID,
        "hybrid": FuelType.HYBRID,
        "lpg": FuelType.LPG,
        "cng": FuelType.CNG,
    }

    types = []
    for fuel_str in fuel_types_str.lower().split(","):
        fuel_str = fuel_str.strip()
        if fuel_str in fuel_map:
            types.append(fuel_map[fuel_str])
        else:
            console.print(
                f"[yellow]Advertencia: Tipo de combustible desconocido '{fuel_str}' ignorado[/yellow]"
            )

    return types if types else None


def _parse_transmissions(
    transmissions_str: Optional[str],
) -> Optional[List[Transmission]]:
    """Parsea tipos de transmisión desde string separado por comas"""
    if not transmissions_str:
        return None

    trans_map = {
        "manual": Transmission.MANUAL,
        "automatico": Transmission.AUTOMATIC,
        "automatic": Transmission.AUTOMATIC,
        "semiautomatico": Transmission.SEMI_AUTOMATIC,
        "semi_automatic": Transmission.SEMI_AUTOMATIC,
    }

    types = []
    for trans_str in transmissions_str.lower().split(","):
        trans_str = trans_str.strip()
        if trans_str in trans_map:
            types.append(trans_map[trans_str])
        else:
            console.print(
                f"[yellow]Advertencia: Tipo de transmisión desconocido '{trans_str}' ignorado[/yellow]"
            )

    return types if types else None


def _parse_sort_by(sort_str: Optional[str]) -> SortBy:
    """Parsea criterio de ordenación"""
    if not sort_str:
        return SortBy.RELEVANCE

    sort_map = {
        "relevancia": SortBy.RELEVANCE,
        "relevance": SortBy.RELEVANCE,
        "precio_asc": SortBy.PRICE_LOW_TO_HIGH,
        "price_asc": SortBy.PRICE_LOW_TO_HIGH,
        "precio_desc": SortBy.PRICE_HIGH_TO_LOW,
        "price_desc": SortBy.PRICE_HIGH_TO_LOW,
        "año_desc": SortBy.YEAR_NEW_TO_OLD,
        "year_desc": SortBy.YEAR_NEW_TO_OLD,
        "año_asc": SortBy.YEAR_OLD_TO_NEW,
        "year_asc": SortBy.YEAR_OLD_TO_NEW,
        "km_asc": SortBy.MILEAGE_LOW_TO_HIGH,
        "mileage_asc": SortBy.MILEAGE_LOW_TO_HIGH,
        "km_desc": SortBy.MILEAGE_HIGH_TO_LOW,
        "mileage_desc": SortBy.MILEAGE_HIGH_TO_LOW,
    }

    return sort_map.get(sort_str.lower(), SortBy.RELEVANCE)


def _enrich_listings(listings):
    enriched = co2_enricher.enrich(listings)
    inferred = sum(
        1
        for listing in enriched
        if listing.co2_source_type == "memory"
    )
    if inferred:
        console.print(
            f"[cyan]CO2 completado automaticamente en {inferred} anuncios[/cyan]"
        )
    return enriched


async def _scrape_with_filters(
    scraper_class,
    filters: UnifiedFilters,
    limit: Optional[int] = None,
    export_format: Optional[str] = None,
    export_filename: Optional[str] = None,
) -> None:
    """Ejecuta scraping con filtros y opcionalmente exporta resultados"""

    scraper = scraper_class()

    # Detectar nombre del source
    if scraper_class == MobileDeHttpScraper:
        source_name = "mobile.de"
    else:
        source_name = "coches.net"

    console.print(f"[blue]Scrapeando {source_name}...[/blue]")

    try:
        # Detectar si el scraper es async o sync
        import inspect

        if inspect.iscoroutinefunction(scraper.search):
            result = await scraper.search(query=filters, limit=limit)
        else:
            # Scraper síncrono (como MobileDeHttpScraper)
            result = scraper.search(query=filters, limit=limit)

        result.listings = _enrich_listings(result.listings)

        if not result.listings:
            console.print(
                f"[yellow]No se encontraron resultados para los filtros especificados en {source_name}[/yellow]"
            )
            return

        console.print(
            f"[green]Encontrados {len(result.listings)} anuncios en {source_name}[/green]"
        )

        # Mostrar tabla resumen
        table = Table(title=f"Resumen de resultados - {source_name}")
        table.add_column("Campo", style="cyan")
        table.add_column("Valor", style="magenta")

        table.add_row("Total anuncios", str(len(result.listings)))
        table.add_row("Página actual", str(result.result_page))
        table.add_row("Anuncios por página", str(result.result_page_size))
        table.add_row("Hay más páginas", "Sí" if result.has_next else "No")

        if result.listings:
            prices = [l.price_eur for l in result.listings if l.price_eur]
            if prices:
                table.add_row(
                    "Precio promedio", f"{sum(prices) / len(prices):,.0f} EUR"
                )
                table.add_row("Precio mínimo", f"{min(prices):,.0f} EUR")
                table.add_row("Precio máximo", f"{max(prices):,.0f} EUR")

        console.print(table)

        # Exportar si se especifica formato
        if export_format:
            if export_format.lower() == "excel":
                exporter = ExcelExporter()
                filepath = exporter.export_listings(result.listings, export_filename)
                console.print(f"[green]Exportado a Excel: {filepath}[/green]")
            elif export_format.lower() == "csv":
                exporter = CSVExporter()
                filepath = exporter.export_listings(result.listings, export_filename)
                console.print(f"[green]Exportado a CSV: {filepath}[/green]")
            else:
                console.print(
                    f"[red]Formato de exportación no soportado: {export_format}[/red]"
                )
        else:
            # Mostrar JSON en consola si no hay exportación
            for listing in result.listings[
                :5
            ]:  # Solo mostrar primeros 5 para no saturar
                print(
                    orjson.dumps(
                        listing.model_dump(mode="json"), option=orjson.OPT_INDENT_2
                    ).decode("utf-8")
                )

            if len(result.listings) > 5:
                console.print(
                    f"[dim]... y {len(result.listings) - 5} anuncios más[/dim]"
                )
                console.print(
                    "[dim]Usa --export-format para guardar todos los resultados[/dim]"
                )

    except Exception as e:
        console.print(f"[red]Error durante el scraping: {e}[/red]")
        logger.exception("Error detallado:")


@app.command("mobile-de")
def mobile_de(
    # Paginación
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(24, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    # Filtros básicos
    make: Optional[str] = typer.Option(
        None, help="Marca del vehículo (ej: BMW, Mercedes-Benz)"
    ),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    # Rangos de precios
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    # Rangos de años
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    # Rangos de kilometraje
    min_mileage: Optional[int] = typer.Option(None, help="Kilometraje mínimo"),
    max_mileage: Optional[int] = typer.Option(None, help="Kilometraje máximo"),
    # Rangos de potencia
    min_power: Optional[int] = typer.Option(None, help="Potencia mínima en HP"),
    max_power: Optional[int] = typer.Option(None, help="Potencia máxima en HP"),
    # Características
    fuel_types: Optional[str] = typer.Option(
        None,
        help="Tipos de combustible separados por comas (gasolina,diesel,electrico,hibrido)",
    ),
    transmissions: Optional[str] = typer.Option(
        None,
        help="Tipos de transmisión separados por comas (manual,automatico,semiautomatico)",
    ),
    # Ubicación
    country: Optional[str] = typer.Option(None, help="Código de país (ej: DE, ES)"),
    # Vendedor
    dealer_only: bool = typer.Option(False, help="Solo concesionarios"),
    private_only: bool = typer.Option(False, help="Solo particulares"),
    # Ordenación
    sort_by: Optional[str] = typer.Option(
        None,
        help="Ordenar por (relevancia,precio_asc,precio_desc,año_desc,año_asc,km_asc,km_desc)",
    ),
    # Exportación
    export_format: Optional[str] = typer.Option(
        None, help="Formato de exportación (excel, csv)"
    ),
    export_filename: Optional[str] = typer.Option(
        None, help="Nombre del archivo de exportación"
    ),
) -> None:
    """Scraper para mobile.de con filtros avanzados"""

    # Construir filtros
    filters = UnifiedFilters(
        page=page,
        page_size=page_size,
        make=make,
        model=model,
        price_range=PriceRange(min_price=min_price, max_price=max_price)
        if min_price or max_price
        else None,
        year_range=YearRange(min_year=min_year, max_year=max_year)
        if min_year or max_year
        else None,
        mileage_range=MileageRange(min_mileage=min_mileage, max_mileage=max_mileage)
        if min_mileage or max_mileage
        else None,
        power_range=PowerRange(min_power_hp=min_power, max_power_hp=max_power)
        if min_power or max_power
        else None,
        fuel_types=_parse_fuel_types(fuel_types),
        transmissions=_parse_transmissions(transmissions),
        country_code=country,
        dealer_only=dealer_only if dealer_only else None,
        private_only=private_only if private_only else None,
        sort_by=_parse_sort_by(sort_by),
    )

    # Usar el nuevo scraper HTTP (más rápido)
    asyncio.run(
        _scrape_with_filters(
            MobileDeHttpScraper, filters, limit, export_format, export_filename
        )
    )


@app.command("coches-net")
def coches_net(
    # Paginación
    page: int = typer.Option(1, min=1, help="Número de página"),
    page_size: int = typer.Option(30, min=1, max=200, help="Resultados por página"),
    limit: Optional[int] = typer.Option(None, help="Máximo de anuncios a devolver"),
    # Filtros básicos
    make: Optional[str] = typer.Option(
        None, help="Marca del vehículo (ej: BMW, Mercedes-Benz)"
    ),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    # Rangos de precios
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    # Rangos de años
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    # Rangos de kilometraje
    min_mileage: Optional[int] = typer.Option(None, help="Kilometraje mínimo"),
    max_mileage: Optional[int] = typer.Option(None, help="Kilometraje máximo"),
    # Rangos de potencia
    min_power: Optional[int] = typer.Option(None, help="Potencia mínima en HP"),
    max_power: Optional[int] = typer.Option(None, help="Potencia máxima en HP"),
    # Características
    fuel_types: Optional[str] = typer.Option(
        None,
        help="Tipos de combustible separados por comas (gasolina,diesel,electrico,hibrido)",
    ),
    transmissions: Optional[str] = typer.Option(
        None,
        help="Tipos de transmisión separados por comas (manual,automatico,semiautomatico)",
    ),
    # Vendedor
    dealer_only: bool = typer.Option(False, help="Solo concesionarios"),
    private_only: bool = typer.Option(False, help="Solo particulares"),
    # Ordenación
    sort_by: Optional[str] = typer.Option(
        None,
        help="Ordenar por (relevancia,precio_asc,precio_desc,año_desc,año_asc,km_asc,km_desc)",
    ),
    # Exportación
    export_format: Optional[str] = typer.Option(
        None, help="Formato de exportación (excel, csv)"
    ),
    export_filename: Optional[str] = typer.Option(
        None, help="Nombre del archivo de exportación"
    ),
) -> None:
    """Scraper para coches.net con filtros avanzados"""

    # Construir filtros
    filters = UnifiedFilters(
        page=page,
        page_size=page_size,
        make=make,
        model=model,
        price_range=PriceRange(min_price=min_price, max_price=max_price)
        if min_price or max_price
        else None,
        year_range=YearRange(min_year=min_year, max_year=max_year)
        if min_year or max_year
        else None,
        mileage_range=MileageRange(min_mileage=min_mileage, max_mileage=max_mileage)
        if min_mileage or max_mileage
        else None,
        power_range=PowerRange(min_power_hp=min_power, max_power_hp=max_power)
        if min_power or max_power
        else None,
        fuel_types=_parse_fuel_types(fuel_types),
        transmissions=_parse_transmissions(transmissions),
        dealer_only=dealer_only if dealer_only else None,
        private_only=private_only if private_only else None,
        sort_by=_parse_sort_by(sort_by),
    )

    asyncio.run(
        _scrape_with_filters(
            CochesNetScraper, filters, limit, export_format, export_filename
        )
    )


@app.command("compare")
def compare(
    # Filtros básicos (aplicados a ambas fuentes)
    make: Optional[str] = typer.Option(None, help="Marca del vehículo"),
    model: Optional[str] = typer.Option(None, help="Modelo del vehículo"),
    min_price: Optional[float] = typer.Option(None, help="Precio mínimo en EUR"),
    max_price: Optional[float] = typer.Option(None, help="Precio máximo en EUR"),
    min_year: Optional[int] = typer.Option(None, help="Año mínimo"),
    max_year: Optional[int] = typer.Option(None, help="Año máximo"),
    # Configuración
    limit: Optional[int] = typer.Option(50, help="Máximo de anuncios por fuente"),
    export_filename: Optional[str] = typer.Option(
        None, help="Nombre del archivo de comparación"
    ),
) -> None:
    """Compara precios entre mobile.de y coches.net con los mismos filtros"""

    async def _compare():
        # Construir filtros comunes
        filters = UnifiedFilters(
            make=make,
            model=model,
            price_range=PriceRange(min_price=min_price, max_price=max_price)
            if min_price or max_price
            else None,
            year_range=YearRange(min_year=min_year, max_year=max_year)
            if min_year or max_year
            else None,
        )

        console.print(
            "[bold blue]Comparando precios entre mobile.de y coches.net...[/bold blue]"
        )

        # Scraper ambas fuentes en paralelo
        mobile_scraper = MobileDeHttpScraper()
        coches_scraper = CochesNetScraper()

        loop = asyncio.get_event_loop()
        mobile_task = loop.run_in_executor(
            None, lambda: mobile_scraper.search(query=filters, limit=limit)
        )
        mobile_result, coches_result = await asyncio.gather(
            mobile_task,
            coches_scraper.search(query=filters, limit=limit),
            return_exceptions=True,
        )

        # Procesar resultados
        all_listings = []

        if isinstance(mobile_result, Exception):
            console.print(f"[red]Error en mobile.de: {mobile_result}[/red]")
        else:
            mobile_result.listings = _enrich_listings(mobile_result.listings)
            all_listings.extend(mobile_result.listings)
            console.print(
                f"[green]mobile.de: {len(mobile_result.listings)} anuncios[/green]"
            )

        if isinstance(coches_result, Exception):
            console.print(f"[red]Error en coches.net: {coches_result}[/red]")
        else:
            coches_result.listings = _enrich_listings(coches_result.listings)
            all_listings.extend(coches_result.listings)
            console.print(
                f"[green]coches.net: {len(coches_result.listings)} anuncios[/green]"
            )

        if not all_listings:
            console.print(
                "[yellow]No se encontraron anuncios en ninguna fuente[/yellow]"
            )
            return

        mobile_listings = [l for l in all_listings if l.source == "mobile_de"]
        coches_listings = [l for l in all_listings if l.source == "coches_net"]
        break_even_data = {}
        for listing in mobile_listings:
            scenarios = break_even_scenarios(listing)
            if scenarios:
                break_even_data[listing.listing_id] = scenarios

        opportunities = apply_opportunity_analysis(
            mobile_listings, coches_listings, break_even_data
        )

        # Exportar comparación
        exporter = ExcelExporter()
        filename = (
            export_filename
            or f"comparacion_precios_{make or 'todos'}_{model or 'modelos'}"
        )
        filepath = exporter.export_listings(all_listings, filename)

        console.print(f"[green]Comparación exportada a: {filepath}[/green]")

        # Mostrar estadísticas
        table = Table(title="Comparación de Precios")
        table.add_column("Fuente", style="cyan")
        table.add_column("Anuncios", style="magenta")
        table.add_column("Precio Promedio", style="green")
        table.add_column("Precio Mínimo", style="yellow")
        table.add_column("Precio Máximo", style="red")

        for source_name, listings in [
            ("mobile.de", mobile_listings),
            ("coches.net", coches_listings),
        ]:
            if listings:
                prices = [l.price_eur for l in listings if l.price_eur]
                if prices:
                    table.add_row(
                        source_name,
                        str(len(listings)),
                        f"{sum(prices) / len(prices):,.0f} EUR",
                        f"{min(prices):,.0f} EUR",
                        f"{max(prices):,.0f} EUR",
                    )
                else:
                    table.add_row(source_name, str(len(listings)), "N/A", "N/A", "N/A")
            else:
                table.add_row(source_name, "0", "N/A", "N/A", "N/A")

        console.print(table)

        if opportunities:
            opp_table = Table(title="Top Oportunidades")
            opp_table.add_column("Modelo", style="cyan")
            opp_table.add_column("Muestras ES", justify="right")
            opp_table.add_column("Precio ES medio", justify="right", style="green")
            opp_table.add_column("Break-even", justify="right", style="magenta")
            opp_table.add_column("Margen", justify="right", style="yellow")
            opp_table.add_column("Score", justify="right", style="red")
            for opp in opportunities[:5]:
                listing = opp["listing"]
                opp_table.add_row(
                    f"{listing.make} {listing.model}",
                    str(listing.es_sample_size or 0),
                    f"{listing.es_market_avg:,.0f} EUR"
                    if listing.es_market_avg
                    else "N/A",
                    f"{listing.best_break_even:,.0f} EUR"
                    if listing.best_break_even
                    else "N/A",
                    f"{listing.potential_margin_avg:,.0f} EUR"
                    if listing.potential_margin_avg
                    else "N/A",
                    f"{listing.import_ready_score:,.0f}"
                    if listing.import_ready_score is not None
                    else "N/A",
                )
            console.print(opp_table)

    asyncio.run(_compare())


@app.command("comparar")
def comparar(
    # ========== PARÁMETROS COMUNES (modo simple) ==========
    make: Optional[str] = typer.Option(
        None, help="Marca (modo simple, aplica a ambos)"
    ),
    model: Optional[str] = typer.Option(
        None, help="Modelo (modo simple, aplica a ambos)"
    ),
    fuel_types: Optional[str] = typer.Option(None, help="Combustibles (modo simple)"),
    transmissions: Optional[str] = typer.Option(
        None, help="Transmisiones (modo simple)"
    ),
    limit: Optional[int] = typer.Option(50, help="Límite por fuente (modo simple)"),
    # ========== ALEMANIA (mobile.de) - Parámetros específicos ==========
    de_make: Optional[str] = typer.Option(None, help="Marca para Alemania"),
    de_model: Optional[str] = typer.Option(None, help="Modelo para Alemania"),
    de_min_price: Optional[float] = typer.Option(
        None, help="Precio mínimo Alemania (EUR)"
    ),
    de_max_price: Optional[float] = typer.Option(
        None, help="Precio máximo Alemania (EUR)"
    ),
    de_min_year: Optional[int] = typer.Option(None, help="Año mínimo Alemania"),
    de_max_year: Optional[int] = typer.Option(None, help="Año máximo Alemania"),
    de_min_mileage: Optional[int] = typer.Option(
        None, help="Kilometraje mínimo Alemania"
    ),
    de_max_mileage: Optional[int] = typer.Option(
        None, help="Kilometraje máximo Alemania"
    ),
    de_min_power: Optional[int] = typer.Option(
        None, help="Potencia mínima Alemania (HP)"
    ),
    de_max_power: Optional[int] = typer.Option(
        None, help="Potencia máxima Alemania (HP)"
    ),
    de_fuel_types: Optional[str] = typer.Option(None, help="Combustibles Alemania"),
    de_transmissions: Optional[str] = typer.Option(None, help="Transmisiones Alemania"),
    de_dealer_only: bool = typer.Option(False, help="Solo concesionarios Alemania"),
    de_private_only: bool = typer.Option(False, help="Solo particulares Alemania"),
    de_limit: Optional[int] = typer.Option(None, help="Límite de anuncios Alemania"),
    # ========== ESPAÑA (coches.net) - Parámetros específicos ==========
    es_make: Optional[str] = typer.Option(None, help="Marca para España"),
    es_model: Optional[str] = typer.Option(None, help="Modelo para España"),
    es_min_price: Optional[float] = typer.Option(
        None, help="Precio mínimo España (EUR)"
    ),
    es_max_price: Optional[float] = typer.Option(
        None, help="Precio máximo España (EUR)"
    ),
    es_min_year: Optional[int] = typer.Option(None, help="Año mínimo España"),
    es_max_year: Optional[int] = typer.Option(None, help="Año máximo España"),
    es_min_mileage: Optional[int] = typer.Option(
        None, help="Kilometraje mínimo España"
    ),
    es_max_mileage: Optional[int] = typer.Option(
        None, help="Kilometraje máximo España"
    ),
    es_min_power: Optional[int] = typer.Option(
        None, help="Potencia mínima España (HP)"
    ),
    es_max_power: Optional[int] = typer.Option(
        None, help="Potencia máxima España (HP)"
    ),
    es_fuel_types: Optional[str] = typer.Option(None, help="Combustibles España"),
    es_transmissions: Optional[str] = typer.Option(None, help="Transmisiones España"),
    es_dealer_only: bool = typer.Option(False, help="Solo concesionarios España"),
    es_private_only: bool = typer.Option(False, help="Solo particulares España"),
    es_limit: Optional[int] = typer.Option(None, help="Límite de anuncios España"),
    # ========== EXPORTACIÓN ==========
    export_filename: Optional[str] = typer.Option(
        None, help="Nombre del CSV de salida"
    ),
) -> None:
    """
    Compara anuncios entre mobile.de (Alemania) y coches.net (España)

    Modos de uso:
    1. Simple: --make "BMW" --model "X5" --de-max-price 30000 --es-max-price 40000
    2. Avanzado: --de-make "BMW" --de-model "X5" --es-make "BMW" --es-model "X5 xDrive"
    """

    import csv
    from datetime import datetime

    async def _comparar():
        # ========== DETERMINAR MODO ==========
        modo_avanzado = any(
            [
                de_make,
                de_model,
                de_min_price,
                de_max_price,
                es_make,
                es_model,
                es_min_price,
                es_max_price,
            ]
        )

        if modo_avanzado:
            console.print(
                "[bold yellow]Modo avanzado: Parametros especificos por pais[/bold yellow]"
            )
        else:
            console.print(
                "[bold blue]Modo simple: Mismos parametros para ambos paises[/bold blue]"
            )

        # ========== CONSTRUIR FILTROS ALEMANIA ==========
        if modo_avanzado:
            de_filters = UnifiedFilters(
                make=de_make,
                model=de_model,
                price_range=PriceRange(min_price=de_min_price, max_price=de_max_price)
                if de_min_price or de_max_price
                else None,
                year_range=YearRange(min_year=de_min_year, max_year=de_max_year)
                if de_min_year or de_max_year
                else None,
                mileage_range=MileageRange(
                    min_mileage=de_min_mileage, max_mileage=de_max_mileage
                )
                if de_min_mileage or de_max_mileage
                else None,
                power_range=PowerRange(
                    min_power_hp=de_min_power, max_power_hp=de_max_power
                )
                if de_min_power or de_max_power
                else None,
                fuel_types=_parse_fuel_types(de_fuel_types),
                transmissions=_parse_transmissions(de_transmissions),
                dealer_only=de_dealer_only if de_dealer_only else None,
                private_only=de_private_only if de_private_only else None,
            )
            de_limit_final = de_limit or limit
        else:
            de_filters = UnifiedFilters(
                make=make,
                model=model,
                fuel_types=_parse_fuel_types(fuel_types),
                transmissions=_parse_transmissions(transmissions),
            )
            de_limit_final = limit

        # ========== CONSTRUIR FILTROS ESPAÑA ==========
        if modo_avanzado:
            es_filters = UnifiedFilters(
                make=es_make,
                model=es_model,
                price_range=PriceRange(min_price=es_min_price, max_price=es_max_price)
                if es_min_price or es_max_price
                else None,
                year_range=YearRange(min_year=es_min_year, max_year=es_max_year)
                if es_min_year or es_max_year
                else None,
                mileage_range=MileageRange(
                    min_mileage=es_min_mileage, max_mileage=es_max_mileage
                )
                if es_min_mileage or es_max_mileage
                else None,
                power_range=PowerRange(
                    min_power_hp=es_min_power, max_power_hp=es_max_power
                )
                if es_min_power or es_max_power
                else None,
                fuel_types=_parse_fuel_types(es_fuel_types),
                transmissions=_parse_transmissions(es_transmissions),
                dealer_only=es_dealer_only if es_dealer_only else None,
                private_only=es_private_only if es_private_only else None,
            )
            es_limit_final = es_limit or limit
        else:
            es_filters = UnifiedFilters(
                make=make,
                model=model,
                fuel_types=_parse_fuel_types(fuel_types),
                transmissions=_parse_transmissions(transmissions),
            )
            es_limit_final = limit

        if not equivalent_vehicle_criteria(de_filters, es_filters):
            raise typer.BadParameter(
                "La comparación exige el mismo vehículo y especificaciones técnicas en mobile.de y coches.net. "
                "Solo pueden variar el precio, el vendedor y el límite por mercado."
            )

        console.print("\n" + "=" * 80)
        console.print("INICIANDO BUSQUEDA COMPARATIVA")
        console.print("=" * 80)

        # ========== SCRAPING PARALELO ==========
        mobile_listings = []
        coches_listings = []

        # Solo scrapear si hay filtros definidos
        tasks = []

        if de_filters.make or modo_avanzado:
            console.print(
                f"\n[bold blue]Buscando en mobile.de (Alemania)...[/bold blue]"
            )
            if de_filters.make:
                console.print(f"   Marca: {de_filters.make}")
            if de_filters.model:
                console.print(f"   Modelo: {de_filters.model}")

            mobile_scraper = MobileDeHttpScraper()
            # MobileDeHttpScraper es síncrono, ejecutarlo en un executor
            import concurrent.futures

            loop = asyncio.get_event_loop()
            mobile_task = loop.run_in_executor(
                None,
                lambda: mobile_scraper.search(query=de_filters, limit=de_limit_final),
            )
            tasks.append(("mobile", mobile_task))

        if es_filters.make or modo_avanzado:
            console.print(
                f"\n[bold blue]Buscando en coches.net (Espana)...[/bold blue]"
            )
            if es_filters.make:
                console.print(f"   Marca: {es_filters.make}")
            if es_filters.model:
                console.print(f"   Modelo: {es_filters.model}")

            coches_scraper = CochesNetScraper()
            coches_task = coches_scraper.search(query=es_filters, limit=es_limit_final)
            tasks.append(("coches", coches_task))

        if not tasks:
            console.print(
                "[yellow]No se especificaron filtros. Usa --make o parametros especificos (--de-make, --es-make)[/yellow]"
            )
            return

        # Ejecutar scraping en paralelo
        results = await asyncio.gather(
            *[task for _, task in tasks], return_exceptions=True
        )

        # Procesar resultados
        for (source, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                console.print(f"[red]Error en {source}: {result}[/red]")
            else:
                if source == "mobile":
                    mobile_listings = _enrich_listings(result.listings)
                    console.print(
                        f"[green]mobile.de: {len(mobile_listings)} anuncios encontrados[/green]"
                    )
                else:
                    coches_listings = _enrich_listings(result.listings)
                    console.print(
                        f"[green]coches.net: {len(coches_listings)} anuncios encontrados[/green]"
                    )

        if not mobile_listings and not coches_listings:
            console.print(
                "[yellow]No se encontraron anuncios en ninguna fuente[/yellow]"
            )
            return

        # ========== CALCULAR BREAK-EVEN PARA ALEMANIA ==========
        console.print("\n" + "=" * 80)
        console.print("CALCULANDO COSTES DE IMPORTACION (Alemania -> Espana)")
        console.print("=" * 80)

        # Diccionario para almacenar break-even por listing_id
        break_even_data = {}

        for listing in mobile_listings:
            scenarios = break_even_scenarios(listing)
            if scenarios:
                break_even_data[listing.listing_id] = scenarios

        oportunidades = apply_opportunity_analysis(
            mobile_listings, coches_listings, break_even_data
        )

        # ========== GUARDAR EN CSV ==========
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = export_filename or f"comparacion_{timestamp}.csv"
        if not filename.endswith(".csv"):
            filename += ".csv"

        output_dir = Path("exports")
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / filename

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Encabezados
            writer.writerow(
                [
                    "source",
                    "title",
                    "make",
                    "model",
                    "variant_key",
                    "vehicle_signature",
                    "year",
                    "mileage_km",
                    "fuel_type",
                    "transmission",
                    "power_hp",
                    "price_eur",
                    "seller_type",
                    "break_even_particular",
                    "break_even_empresa_iva",
                    "break_even_empresa_margen",
                    "co2_g_km",
                    "co2_original_g_km",
                    "co2_inferred_g_km",
                    "co2_source_type",
                    "co2_confidence",
                    "market_key",
                    "comparable_match_level",
                    "es_market_avg",
                    "es_market_median",
                    "es_market_min",
                    "es_sample_size",
                    "es_exact_sample_size",
                    "es_near_sample_size",
                    "es_broad_sample_size",
                    "image_url",
                    "best_break_even",
                    "potential_margin_avg",
                    "potential_margin_min",
                    "opportunity_score",
                    "url",
                ]
            )

            # Datos de Alemania
            for listing in mobile_listings:
                be_data = break_even_data.get(listing.listing_id, {})
                writer.writerow(
                    [
                        "mobile_de",
                        listing.title or "",
                        listing.make or "",
                        listing.model or "",
                        listing.variant_key or "",
                        listing.vehicle_signature or "",
                        listing.first_registration.year
                        if listing.first_registration
                        else "",
                        listing.mileage_km or "",
                        listing.fuel_type or "",
                        listing.transmission or "",
                        listing.power_hp or "",
                        listing.price_eur or "",
                        listing.seller.type if listing.seller else "",
                        be_data.get("particular", ""),
                        be_data.get("empresa_iva", ""),
                        be_data.get("empresa_margen", ""),
                        listing.co2_emissions_g_km or "",
                        listing.co2_original_g_km or "",
                        listing.co2_inferred_g_km or "",
                        listing.co2_source_type or "",
                        listing.co2_confidence
                        if listing.co2_confidence is not None
                        else "",
                        listing.market_key or "",
                        listing.comparable_match_level or "",
                        listing.es_market_avg or "",
                        listing.es_market_median or "",
                        listing.es_market_min or "",
                        listing.es_sample_size or "",
                        listing.es_exact_sample_size or "",
                        listing.es_near_sample_size or "",
                        listing.es_broad_sample_size or "",
                        str(listing.images[0]) if listing.images else "",
                        listing.best_break_even or "",
                        listing.potential_margin_avg or "",
                        listing.potential_margin_min or "",
                        listing.import_ready_score or "",
                        str(listing.url),
                    ]
                )

            # Datos de España
            for listing in coches_listings:
                writer.writerow(
                    [
                        "coches_net",
                        listing.title or "",
                        listing.make or "",
                        listing.model or "",
                        listing.variant_key or "",
                        listing.vehicle_signature or "",
                        listing.first_registration.year
                        if listing.first_registration
                        else "",
                        listing.mileage_km or "",
                        listing.fuel_type or "",
                        listing.transmission or "",
                        listing.power_hp or "",
                        listing.price_eur or "",
                        listing.seller.type if listing.seller else "",
                        "",  # No hay break-even para España
                        "",
                        "",
                        listing.co2_emissions_g_km or "",
                        listing.co2_original_g_km or "",
                        listing.co2_inferred_g_km or "",
                        listing.co2_source_type or "",
                        listing.co2_confidence
                        if listing.co2_confidence is not None
                        else "",
                        listing.market_key or "",
                        listing.comparable_match_level or "",
                        listing.es_market_avg or "",
                        listing.es_market_median or "",
                        listing.es_market_min or "",
                        listing.es_sample_size or "",
                        listing.es_exact_sample_size or "",
                        listing.es_near_sample_size or "",
                        listing.es_broad_sample_size or "",
                        str(listing.images[0]) if listing.images else "",
                        listing.best_break_even or "",
                        listing.potential_margin_avg or "",
                        listing.potential_margin_min or "",
                        listing.import_ready_score or "",
                        str(listing.url),
                    ]
                )

        console.print(f"\n[green]CSV guardado en: {filepath}[/green]")

        # ========== RESUMEN COMPARATIVO ==========
        console.print("\n" + "=" * 80)
        console.print("RESUMEN COMPARATIVO")
        console.print("=" * 80)

        table = Table(title="Comparacion de Mercados")
        table.add_column("Pais", style="cyan", justify="center")
        table.add_column("Anuncios", style="magenta", justify="right")
        table.add_column("Precio Promedio", style="green", justify="right")
        table.add_column("Precio Minimo", style="yellow", justify="right")
        table.add_column("Precio Maximo", style="red", justify="right")

        # Alemania
        if mobile_listings:
            prices_de = [l.price_eur for l in mobile_listings if l.price_eur]
            if prices_de:
                table.add_row(
                    "Alemania",
                    str(len(mobile_listings)),
                    f"{sum(prices_de) / len(prices_de):,.0f} EUR",
                    f"{min(prices_de):,.0f} EUR",
                    f"{max(prices_de):,.0f} EUR",
                )

        # Espana
        if coches_listings:
            prices_es = [l.price_eur for l in coches_listings if l.price_eur]
            if prices_es:
                table.add_row(
                    "Espana",
                    str(len(coches_listings)),
                    f"{sum(prices_es) / len(prices_es):,.0f} EUR",
                    f"{min(prices_es):,.0f} EUR",
                    f"{max(prices_es):,.0f} EUR",
                )

        console.print(table)

        # Mostrar oportunidades (si hay datos de ambos mercados)
        if mobile_listings and coches_listings:
            console.print("\n" + "=" * 80)
            console.print("ANALISIS DE OPORTUNIDADES")
            console.print("=" * 80)

            if oportunidades:
                opp_table = Table(title="Top 5 Oportunidades")
                opp_table.add_column("Modelo", style="cyan")
                opp_table.add_column("Muestras ES", style="white", justify="right")
                opp_table.add_column("Precio ES medio", style="yellow", justify="right")
                opp_table.add_column("Match", style="white", justify="center")
                opp_table.add_column("Break-even", style="magenta", justify="right")
                opp_table.add_column("Margen", style="green", justify="right")
                opp_table.add_column("Rentabilidad", style="red", justify="right")
                opp_table.add_column("Score", style="blue", justify="right")

                for opp in oportunidades[:5]:
                    listing = opp["listing"]
                    opp_table.add_row(
                        f"{listing.make} {listing.model}",
                        str(listing.es_sample_size or 0),
                        f"{listing.es_market_avg:,.0f} EUR"
                        if listing.es_market_avg
                        else "N/A",
                        listing.comparable_match_level or "N/A",
                        f"{opp['break_even']:,.0f} EUR",
                        f"{opp['margen']:,.0f} EUR",
                        f"{opp['rentabilidad']:.1f}%",
                        f"{listing.import_ready_score:,.0f}"
                        if listing.import_ready_score is not None
                        else "N/A",
                    )

                console.print(opp_table)
            else:
                console.print(
                    "[yellow]No se encontraron oportunidades rentables con estos filtros[/yellow]"
                )

        console.print("\n[bold green]Comparacion completada[/bold green]")

    asyncio.run(_comparar())


@app.command("filtros")
def show_filters():
    """Muestra todas las opciones de filtro disponibles para coches.net y mobile.de"""
    console.print("\n[bold blue]OPCIONES DE FILTRO DISPONIBLES[/bold blue]\n")

    # Marcas disponibles
    console.print("[bold green]MARCAS DISPONIBLES:[/bold green]")
    marcas = [
        "Audi",
        "BMW",
        "Mercedes-Benz",
        "Volkswagen",
        "Ford",
        "Toyota",
        "Nissan",
        "Hyundai",
        "Kia",
        "Peugeot",
        "Renault",
        "Citroën",
        "Opel",
        "Seat",
        "Skoda",
        "Fiat",
        "Honda",
        "Mazda",
        "Volvo",
        "Jaguar",
        "Land-Rover",
        "Porsche",
        "Mini",
        "Smart",
        "Jeep",
        "Chevrolet",
        "Cadillac",
        "Chrysler",
        "Dodge",
        "Tesla",
        "Lexus",
        "Infiniti",
        "Subaru",
        "Suzuki",
        "Mitsubishi",
        "MG",
        "BYD",
        "Cupra",
        "Dacia",
        "Corvette",
    ]

    # Mostrar marcas en columnas
    table = Table(show_header=False, box=None, padding=(0, 2))
    for i in range(0, len(marcas), 4):
        row = marcas[i : i + 4]
        while len(row) < 4:
            row.append("")
        table.add_row(*row)
    console.print(table)

    # Tipos de combustible
    console.print("\n[bold green]TIPOS DE COMBUSTIBLE:[/bold green]")
    console.print("• gasolina, diesel, electrico, hibrido, lpg, cng")

    # Tipos de transmisión
    console.print("\n[bold green]TIPOS DE TRANSMISION:[/bold green]")
    console.print("• manual, automatica")

    # Rangos de filtros
    console.print("\n[bold green]RANGOS DE PRECIO:[/bold green]")
    console.print("• --min-price: Precio mínimo en EUR (ej: 5000)")
    console.print("• --max-price: Precio máximo en EUR (ej: 50000)")

    console.print("\n[bold green]RANGOS DE AÑO:[/bold green]")
    console.print("• --min-year: Año mínimo (ej: 2010)")
    console.print("• --max-year: Año máximo (ej: 2023)")

    console.print("\n[bold green]RANGOS DE KILOMETRAJE:[/bold green]")
    console.print("• --min-mileage: Kilometraje mínimo (ej: 10000)")
    console.print("• --max-mileage: Kilometraje máximo (ej: 150000)")

    console.print("\n[bold green]RANGOS DE POTENCIA:[/bold green]")
    console.print("• --min-power: Potencia mínima en HP (ej: 100)")
    console.print("• --max-power: Potencia máxima en HP (ej: 300)")

    # Opciones de vendedor
    console.print("\n[bold green]TIPO DE VENDEDOR:[/bold green]")
    console.print("• --dealer-only: Solo concesionarios")
    console.print("• --private-only: Solo particulares")

    # Opciones de ordenación
    console.print("\n[bold green]ORDENACION:[/bold green]")
    console.print("• --sort-by: relevancia, precio, año, kilometraje")

    # Opciones de exportación
    console.print("\n[bold green]EXPORTACION:[/bold green]")
    console.print("• --export-format: excel, csv")
    console.print("• --export-filename: nombre_archivo.xlsx")

    # Ejemplos de uso
    console.print("\n[bold yellow]EJEMPLOS DE USO:[/bold yellow]")
    console.print(
        "\n[dim]# Mercedes-Benz entre 2015-2020, máximo 30k EUR, solo automáticos:[/dim]"
    )
    console.print(
        '[cyan]python -m src.import_cars.cli coches-net --make "Mercedes-Benz" --min-year 2015 --max-year 2020 --max-price 30000 --transmissions automatica --export-format excel --export-filename mercedes.xlsx[/cyan]'
    )

    console.print("\n[dim]# BMW diésel, máximo 100k km, solo concesionarios:[/dim]")
    console.print(
        '[cyan]python -m src.import_cars.cli coches-net --make "BMW" --fuel-types diesel --max-mileage 100000 --dealer-only --limit 20[/cyan]'
    )

    console.print("\n[dim]# Comparar precios entre coches.net y mobile.de:[/dim]")
    console.print(
        '[cyan]python -m src.import_cars.cli compare --make "Audi" --model "A4" --min-year 2018[/cyan]'
    )


if __name__ == "__main__":
    app()
