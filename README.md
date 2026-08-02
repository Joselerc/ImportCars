# 🚗 Import Cars Scraper

Sistema avanzado de scraping para **mobile.de** y **coches.net** con filtros unificados, exportación a Excel/CSV y comparación de precios entre mercados.

## 🎯 Características Principales

### ✅ Completado
- **Sistema de Filtros Unificado**: Filtros consistentes para ambas plataformas
- **Scraping de coches.net**: HTTP directo a API interna (completamente funcional)
- **Exportación Avanzada**: Excel y CSV con campos unificados
- **CLI Intuitivo**: Interfaz de línea de comandos con Rich UI
- **Comparación de Mercados**: Análisis paralelo entre fuentes
- **Campos Unificados**: Estructura de datos consistente para comparación
- **Manejo de Errores**: Logging detallado y manejo robusto de excepciones

### 🔧 En Desarrollo
- **Scraping de mobile.de**: Requiere ajustes en selectores/filtros
- **Fecha de Publicación mobile.de**: Extracción de metadatos de publicación

## 🚀 Instalación

```bash
# Clonar repositorio
git clone https://github.com/Joselerc/carscrapper
cd ImportCarsProject

# Instalar dependencias
pip install -e .

# Instalar navegadores para Playwright (solo para mobile.de)
playwright install chromium
```

## Despliegue en Vercel

La interfaz FastAPI se puede desplegar como una función Python de Vercel. El
repositorio incluye `api/index.py` y `vercel.json`; basta con importar el
repositorio en Vercel y desplegar la rama `main`.

El endpoint de comprobación es `/api/health`. Las ejecuciones de scraping se
limitan a 60 segundos y los CSV generados en Vercel son temporales: para
conservar informes entre ejecuciones hay que conectar almacenamiento externo.

## 📊 Uso Básico

### Scraping Simple
```bash
# coches.net - 10 anuncios
python -m src.import_cars.cli coches-net --limit 10

# mobile.de - 10 anuncios (en desarrollo)
python -m src.import_cars.cli mobile-de --limit 10
```

### Filtros Avanzados
```bash
# BMW entre 20k-50k EUR, 2020+, solo automáticos
python -m src.import_cars.cli coches-net \
  --make "BMW" \
  --min-price 20000 --max-price 50000 \
  --min-year 2020 \
  --transmissions "automatico" \
  --limit 50

# Coches eléctricos de concesionarios
python -m src.import_cars.cli coches-net \
  --fuel-types "electrico" \
  --dealer-only \
  --limit 30
```

### Exportación
```bash
# Exportar a Excel
python -m src.import_cars.cli coches-net \
  --make "Mercedes-Benz" \
  --export-format excel \
  --export-filename "mercedes_analisis" \
  --limit 100

# Exportar a CSV
python -m src.import_cars.cli coches-net \
  --max-price 25000 \
  --export-format csv \
  --limit 200
```

### Comparación de Mercados
```bash
# Comparar BMW Serie 3 entre ambas fuentes
python -m src.import_cars.cli compare \
  --make "BMW" --model "Serie 3" \
  --limit 50 \
  --export-filename "bmw_serie3_comparacion"

# Análisis de mercado 20k-40k EUR
python -m src.import_cars.cli compare \
  --min-price 20000 --max-price 40000 \
  --limit 100
```

## 🔍 Filtros Disponibles

### Básicos
- `--make`: Marca (BMW, Mercedes-Benz, Audi, etc.)
- `--model`: Modelo específico
- `--min-price` / `--max-price`: Rango de precios en EUR
- `--min-year` / `--max-year`: Rango de años
- `--min-mileage` / `--max-mileage`: Rango de kilometraje

### Técnicos
- `--fuel-types`: Combustible (gasolina,diesel,electrico,hibrido)
- `--transmissions`: Transmisión (manual,automatico,semiautomatico)
- `--min-power` / `--max-power`: Rango de potencia en HP

### Vendedor y Ubicación
- `--dealer-only`: Solo concesionarios
- `--private-only`: Solo particulares
- `--country`: Código de país (DE, ES)

### Ordenación
- `--sort-by`: Criterio (relevancia,precio_asc,precio_desc,año_desc,año_asc,km_asc,km_desc)

## 📁 Estructura de Datos Exportados

Los archivos Excel/CSV contienen campos unificados:

### Identificación
- `listing_id`, `source`, `url`, `scraped_at`

### Vehículo
- `title`, `make`, `model`, `year`, `month`

### Precios
- `price_gross_eur` (Precio Bruto)
- `price_net_eur` (Precio Neto)
- `original_price`, `original_currency`

### Técnico
- `mileage_km`, `power_hp`, `power_kw`, `engine_displacement_cc`
- `fuel_type`, `transmission`, `body_type`, `doors`, `seats`

### Emisiones y Consumo
- `co2_emissions_g_km`
- `consumption_combined_l_100km`, `consumption_urban_l_100km`, `consumption_highway_l_100km`

### Ubicación y Vendedor
- `country_code`, `region`, `province`, `city`
- `seller_type`, `seller_name`, `seller_rating`, `seller_phone`

### Metadatos
- `publish_date`, `certified`, `exportable`

## 🏗️ Arquitectura del Sistema

### Scrapers
- **`MobileDeScraper`**: Playwright + HTML parsing (en desarrollo)
- **`CochesNetScraper`**: HTTP directo a API interna (funcional)

### Filtros
- **`UnifiedFilters`**: Sistema de filtros tipado y validado
- **`FilterTranslator`**: Traducción a formatos específicos de cada plataforma

### Exportadores
- **`ExcelExporter`**: Exportación con formato y estilos
- **`CSVExporter`**: Exportación simple a CSV

### CLI
- **Rich UI**: Tablas, colores y progreso visual
- **Validación**: Parámetros tipados y validados
- **Logging**: Información detallada de ejecución

## 🎯 Casos de Uso para Importación

### Búsqueda de Oportunidades
```bash
# Coches alemanes baratos para importar
python -m src.import_cars.cli mobile-de \
  --country "DE" \
  --max-price 25000 \
  --min-year 2019 \
  --dealer-only \
  --sort-by "precio_asc" \
  --export-format excel \
  --limit 200

# Comparar con mercado español
python -m src.import_cars.cli compare \
  --min-year 2019 \
  --max-price 35000 \
  --limit 150 \
  --export-filename "oportunidades_importacion"
```

### Análisis por Marca
```bash
# Análisis completo de Audi
python -m src.import_cars.cli compare \
  --make "Audi" \
  --min-year 2018 \
  --limit 150 \
  --export-filename "analisis_audi"
```

## 🔮 Integración con UI Futura

El sistema está diseñado para facilitar la integración con una interfaz web:

### Filtros Estructurados
- Todos los filtros están tipados con Pydantic
- Validación automática de parámetros
- Enums para valores predefinidos

### API-Ready
- Respuestas JSON consistentes
- Paginación integrada
- Manejo de errores estructurado

### Mapeo UI
- **Dropdowns**: Marcas, combustibles, transmisiones
- **Sliders**: Rangos de precios, años, potencia
- **Checkboxes**: Opciones booleanas
- **Inputs**: Límites específicos

## Datos fiscales oficiales del BOE

La carga anual guarda en SQLite los datos fuente de los anexos I y IV. No
calcula impuestos: esa responsabilidad corresponde exclusivamente al paquete
`fiscal_engine`.

```bash
python scripts/load_boe_values.py \
  --database data/import_cars.sqlite3 \
  --exercise 2026
```

Para otro ejercicio hay que indicar también con `--url` el XML oficial de la
orden anual publicado en `boe.es`. La carga valida el ejercicio, registra la
orden y su huella SHA-256, y reemplaza atómicamente solo esa misma versión.

## Calculadora pública

La ruta `/calculadora` acepta un enlace de mobile.de/AutoScout24 o los datos
manuales. Consulta coches.net bajo demanda, aplica el motor fiscal y muestra
únicamente precio final, ahorro, desglose, honorarios y avisos para el cliente.
El transporte profesional se estima por carrocería: 950 € para turismo, familiar
o tipo desconocido; 1.100 € para SUV/monovolumen; y 1.200 € para deportivo o
gama alta declarada. La marca nunca determina el tramo.

```bash
import-cars-web
# http://127.0.0.1:8000/calculadora
```

La superficie interna `/calculadora/auditoria` usa la misma protección HTTP
Basic que el dashboard (`IMPORT_CARS_INTERNAL_USERNAME` y
`IMPORT_CARS_INTERNAL_PASSWORD`; en localhost se permite acceso sin configurar
credenciales). Muestra los comparables seleccionados con su anuncio, variables
disponibles y criterios usados/no usados, además de los intermedios que devuelve
el propio `fiscal_engine`. El endpoint público no serializa esta información.

Las solicitudes de presupuesto con consentimiento se guardan en la tabla
`public_leads` de la SQLite de actividad de clientes. Las fuentes del BOE y el
seguimiento periódico de mercado usan bases físicamente separadas; consulta
`docs/architecture/persistence-boundaries.md`. El dashboard interno conserva
su autenticación Basic de forma independiente.

## 📈 Estadísticas del Proyecto

### Funcionalidad Completada
- ✅ Sistema de filtros unificado (100%)
- ✅ Scraper coches.net (100%)
- ✅ Exportación Excel/CSV (100%)
- ✅ CLI avanzado (100%)
- ✅ Comparación de mercados (100%)
- ✅ Scraper mobile.de HTTP con payload Next.js y fallback DOM
- ✅ Datos BOE 2026 versionados en SQLite local
- ✅ `fiscal_engine` integrado como única fuente de cálculo
- ✅ Calculadora pública con referencia española bajo demanda

### Archivos Clave
- `src/import_cars/filters.py` - Sistema de filtros
- `src/import_cars/scrapers/coches_net.py` - Scraper funcional
- `src/import_cars/scrapers/mobile_de_http.py` - Scraper HTTP principal
- `src/import_cars/scrapers/mobile_de.py` - Vía Playwright de diagnóstico/fallback
- `src/import_cars/fiscal_data/boe.py` - Ingesta anual de datos oficiales
- `src/import_cars/services/public_calculator.py` - Cálculo orientado al cliente
- `src/import_cars/exporters.py` - Exportación de datos
- `src/import_cars/cli.py` - Interfaz de línea de comandos
- `examples/usage_examples.md` - Ejemplos de uso

## 🚧 Próximos Pasos

1. **Revisar visualmente la calculadora pública** en un navegador conectado
2. **Rotar la sesión de coches.net** y limpiar el historial después de la confirmación
3. **Aplazar infraestructura persistente** hasta validar la necesidad de la v2

## 🤝 Contribución

El proyecto está estructurado para facilitar contribuciones:

- **Modular**: Cada scraper es independiente
- **Tipado**: Pydantic para validación
- **Testeable**: Estructura preparada para tests
- **Documentado**: Código auto-documentado

---

**Estado**: ✅ Comparación equivalente mobile.de + coches.net | ✅ Motor fiscal y calculadora pública integrados

**Objetivo**: Identificar oportunidades de importación de vehículos entre mercados alemán y español.
