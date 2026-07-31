# fiscal_engine

Motor de cálculo fiscal de importación de vehículos DE → ES. **Fuente única de verdad** para impuestos y costes. Sustituye a la lógica de `import_calculator.py`.

## Qué resuelve (y qué corrige del código anterior)

- **Base imponible correcta**: no usa el precio del anuncio. IEDMT sobre el valor de tablas del BOE depreciado y **minorado** (`BI = VM / (1 + IVA_hist + IEDMT_hist)`); ITP sobre `max(precio, valor_tablas_depreciado)`.
- **IVTM real** por potencia fiscal (CVF) × coeficiente municipal, **prorrateado** por trimestres. (Antes: fijo en 224 €, ignorando el `cvf`.)
- **Tasa DGT** incluida (99,77 €). (Antes: ausente.)
- **ITP por comunidad autónoma** y **recargo autonómico del IEDMT**. (Antes: 4% fijo de Madrid.)
- **IVA** correcto: 21% en vehículos nuevos (modelo 309); adquisición intracomunitaria con ROI = efecto neto 0; usado a particular/margen = sin IVA español.
- **Fecha de 1ª matriculación** como entrada obligatoria (antes ni se recibía).

## Dos superficies, un cálculo

```python
from datetime import date
from fiscal_engine import calcular, break_even_compraventa
from fiscal_engine import Vehiculo, Operacion, CostesConfig, Combustible, TipoVendedor

v = Vehiculo(
    marca="Honda", modelo="Civic",
    fecha_primera_matriculacion=date(2006, 10, 1),
    precio_compra=1870,
    combustible=Combustible.GASOLINA,
    cilindrada_cc=1799,
    co2_gkm=152,
    kilometros=251000,
    valor_tablas_nuevo=20000,   # <- viene de data/import_cars.sqlite3 (BOE)
)
op = Operacion(tipo_vendedor=TipoVendedor.PARTICULAR,
               comunidad_autonoma="Madrid", municipio="Madrid")

# PRODUCTO PÚBLICO (cliente final):
r = calcular(v, op, precio_mercado_es=3800)
print(r.coste_cliente_final)   # coste total puesto en España
print(r.ahorro_absoluto)       # ahorro vs mercado ES
for linea in r.desglose_cliente:
    print(linea.etiqueta, linea.importe, linea.nota)

# OPPORTUNITY FINDER (dealer, interno):
be = break_even_compraventa(v, op)
print(be["break_even"])        # coste de reventa SIN honorarios de gestión
```

## Integración en el proyecto (para Cursor)

1. **Copiar** el paquete `fiscal_engine/` dentro de `src/import_cars/` (o como paquete hermano; ajustar imports).
2. **Conectar el valor de tablas del BOE**: el campo `Vehiculo.valor_tablas_nuevo` debe rellenarse consultando la base SQLite ya ingerida (`data/import_cars.sqlite3`, 70.886 vehículos) por marca/modelo/año. Si no se encuentra, dejar `None` (el motor estima y añade un aviso). Idealmente, añadir una función puente `resolver_valor_tablas(marca, modelo, fecha) -> float | None` en `fiscal_data/` que consulte la base.
3. **Sustituir** las llamadas a `import_calculator.calcular_costes_importacion(...)`:
   - En el **opportunity finder** → usar `break_even_compraventa(...)`. Devuelve `break_even` para calcular el margen como `precio_venta_es - break_even`. Mantener el contrato que ya espera `analysis/opportunity.py` con un adaptador fino si hace falta.
   - En la **calculadora pública** → usar `calcular(...)` y renderizar `desglose_cliente`, `coste_cliente_final`, `ahorro_absoluto`. **Nunca** exponer `break_even` ni márgenes en el producto público.
4. **Coeficientes municipales de IVTM y tipos ITP**: hoy están en `tablas.py` como diccionarios. Migrarlos a la base de datos / configuración cuando se amplíen municipios y CCAA.
5. **Depreciación y minoración**: las tablas de `tablas.py` (Anexo IV, tipos IEDMT) deben cuadrar con lo que Cursor cargó del BOE. La nota legal del 70% (uso profesional) ya está contemplada en `valor_mercado(..., uso_profesional=True)`.

## Notas de exactitud

- El **valor de tablas del BOE** es la pieza que da exactitud: el motor está preparado para recibirlo; conéctalo a la base ya ingerida.
- La estimación de **CVF desde cilindrada** es una aproximación; siempre es preferible el dato de la ficha técnica (`Vehiculo.cvf`). Cuando el scraper o el parser de anuncios pueda leer la CVF, pásala.
- Los tipos de ITP y recargos autonómicos deben **revisarse cada enero** con la nueva Orden y las leyes autonómicas.
- El motor **no es asesoramiento fiscal**: cada salida lleva `version_tablas` para trazabilidad, y el presupuesto formal debe confirmar cifras.

## Tests

```bash
python -m pytest tests/ -q
```

21 tests que cubren: depreciación y suelo del 10%, tramos y fronteras de CO2 (119/121, 160, 200), Honda Civic 2006 (minoración con IVA histórico 16%), eléctrico (IEDMT 0%), recargo autonómico (Cataluña), ITP por CCAA (Galicia/Madrid/Cantabria), régimen de vendedor (particular vs profesional), vehículo nuevo por meses y por km (IVA), IVTM por CVF y prorrateo (regresión del bug de los 224 € fijos), ahorro vs mercado ES, datos incompletos (CO2/valor de tablas ausentes), break-even sin honorarios (compatibilidad con el opportunity finder), traslado de residencia (exención) y origen extra-UE (arancel + IVA importación).
