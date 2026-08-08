# Validación real ampliada: 100 anuncios nuevos de mobile.de

Fecha de ejecución: 8 de agosto de 2026. El Bloque C permanece pausado.

## Alcance y composición

- 100 anuncios reales, 100 IDs únicos y 0 coincidencias con los 35 anuncios de la tanda anterior.
- Precio: 20 baratos (<3.000 €), 50 medios (3.000–30.000 €) y 30 caros (>30.000 €).
- Combustible: 30 gasolina, 25 diésel, 15 híbridos, 10 PHEV, 15 eléctricos, 3 GLP y 2 GNC.
- Vendedor: 6 particulares, 63 profesionales en margen y 31 profesionales con IVA desglosado.
- 20 marcas distintas. Las más representadas son Volkswagen (12), Nissan (9), BMW/Seat/Audi (7 cada una) y Volvo/Opel/Fiat/Renault/Ford (6 cada una).
- 94 anuncios completaron el cálculo. Se conservaron otros 6 como casos reales pendientes de datos, en vez de inventar su CO₂: cinco carecen de CO₂ y uno carece además de cilindrada.

## Cambios verificados

1. El filtro BOE admite ahora una desviación máxima de ±2 kW, manteniendo cilindrada y combustible exactos. En esta tanda rescató 7 identificaciones que con potencia exacta habrían caído a fallback.
2. Los códigos BOE `GyE`, `DyE` y `SyE` se normalizan como híbrido. También se reconocen `PHEV`, gas (`S`), hidrógeno (`H`) y combustible flexible (`M`).
3. Si mobile.de declara gasolina o diésel pero el texto de versión identifica explícitamente un híbrido (`Hybrid`, `MHEV`, `eTSI`, etc.), el resolver busca la familia híbrida del BOE. No cruza un coche de combustión ordinario con un híbrido.
4. La validación descubrió y corrigió un caso nuevo de entrada: mobile.de publica GNC como `Gas natural`, sin las siglas CNG/GNC. Ya se normaliza como GNC y la búsqueda local deja de descartarlo.

Comprobaciones de control:

- Peugeot 5008 461062598: se mantienen 53 candidatas base y 4 técnicas; se elige la fila 41650 (`5008 1.6 THP S&S GT Line Aut.`). La ampliación a ±2 kW no reabre la ambigüedad.
- Fiat Tipo 451433142: 96 kW frente a 97 kW en BOE; pasa a 4 candidatas técnicas y resuelve la fila 14605.
- Cupra León eTSI 453309686: mobile.de lo etiqueta como gasolina, pero la versión `eTSI` activa el cruce híbrido; queda en 2 candidatas y resuelve la fila 12307.
- Hyundai Kona 445221853: 104 frente a 101 kW son 3 kW de diferencia. Permanece correctamente en fallback porque supera el límite aprobado de ±2 kW.
- Toyota Corolla 461103888: el JSON del anuncio contiene realmente `112 kW (152 CV)`; no es un error de conversión del parser. El BOE más cercano compatible tiene 132 kW, por lo que no se fuerza el cruce.

## Resultados cuantitativos

| Métrica | Resultado |
|---|---:|
| Cálculos completos | 94/100 |
| Identificación BOE | 63/94 (67,02%) |
| Fallback BOE | 31/94 (32,98%) |
| Combustible clasificado indebidamente como `otro` | 0/100 (0%) |
| Ahorro mostrado | 43/100 |
| Ahorro oculto | 57/100 |
| Comparables exact | 15 |
| Comparables near | 7 |
| Comparables broad | 21 |
| Sin nivel de mercado | 57 (incluye los 6 pendientes) |

Los 31 fallbacks del informe son exactamente las 31 filas con `boe_usa_fallback=True` en el CSV. Las 6 filas pendientes no se cuentan como fallback porque el motor todavía no puede ejecutarse sin el dato solicitado.

## Causas de los 31 fallbacks del BOE

| Causa primaria | Casos | Lectura |
|---|---:|---|
| Cilindrada | 9 | Incluye diferencias pequeñas (1332/1333, 1498/1500, 1598/1599) y modelos eléctricos/comerciales cuya cabecera colisiona con variantes de combustión. |
| Combustible | 8 | Principalmente PHEV frente a `GyE/Hybrid`, GLP que el BOE conserva como gasolina y algún anuncio cuya variante no coincide con la familia BOE. |
| Potencia | 7 | En híbridos aparece un patrón de potencia del motor térmico frente a potencia total del sistema; las discrepancias son grandes y no deben cubrirse con tolerancia. |
| Vigencia comercial | 4 | Año del anuncio fuera del intervalo de las filas BOE con la misma cabecera de modelo. |
| Modelo ausente o nomenclatura | 3 | Incluye dos ausencias reales y un fallo de segmentación de modelo (`Seat Terra`, procedente de `Terramar`). |

### Potencia (7)

- 460059939 Opel Corsa: 64 kW; BOE más próximo 74.
- 451486327 Volkswagen Golf: 265 kW; BOE más próximos 221/199/195/173/169.
- 462124499 Opel Zafira Tourer: 125 kW; BOE más próximo 100.
- 460614203 BMW X3 híbrido: 135 kW en anuncio; BOE 215.
- 459375320 Volkswagen Golf PHEV: 150 kW; BOE 110.
- 456687535 Renault Espace híbrido: 96 kW; BOE 146.
- 442374340 Mazda CX-60 híbrido: 241 kW; BOE 143.

### Combustible (8)

- 461490635 Seat Altea: anuncio GLP; BOE gasolina.
- 460797060 Mercedes-Benz CLA 250 Shooting Brake: anuncio PHEV; BOE gasolina/híbrido.
- 460548033 Dacia Jogger: anuncio PHEV; BOE híbrido.
- 457262739 Nissan Murano: anuncio GLP; BOE gasolina.
- 461427997 BMW X5: anuncio diésel; BOE híbrido para la combinación técnica restante.
- 38437808323200 Volkswagen Passat: anuncio híbrido; BOE gasolina.
- 462012801 Volvo XC90: anuncio PHEV; BOE gasolina/híbrido.
- 457896348 Ford Tourneo Connect: anuncio GLP; BOE diésel para la combinación técnica restante.

### Cilindrada (9)

- 38652390957856 Nissan Townstar: 1332 frente a 1333 cm³.
- 452991233 Nissan NV200: 1598 frente a 1461 cm³.
- 460163892 Volkswagen Golf eTSI: 1498 frente a 1500/2000 cm³.
- 460222545 Nissan Juke híbrido: 1598 frente a 1599 cm³.
- 460160444 Ford Mustang Mach-E: 0; las filas con cabecera `Mustang` vigentes son de combustión.
- 458413176 Fiat Ducato: 2184 frente a 2287/2999 cm³.
- 450230196 Ford Explorer: 2956 frente a 3000 cm³.
- 460239222 Citroën Jumpy eléctrico: 0; las filas vigentes encontradas son de combustión.
- 452726229 Citroën SpaceTourer eléctrico: 0; las filas vigentes encontradas son de combustión.

### Vigencia o nomenclatura (7)

- Vigencia: 462297588 Fiat Grande Punto, 461734782 Renault Master, 434191000 Toyota Aygo X y 461145598 Toyota bZ4X.
- Ausencia/nomenclatura: 457377241 Volvo V70, 38557631405120 `Seat Terra` y 453730130 Cupra Tavascan.

## IVA

- 82 usados calculados: 0 casos con IVA español aplicado indebidamente.
- 12 nuevos: los 12 aplican IVA español y los 12 usan exactamente el neto publicado por mobile.de como base.
- 0 errores entre base declarada, base aplicada y cuota resultante.
- La ruta `bruto ÷ 1,19` no apareció en esta muestra real porque los 12 nuevos publicaban neto; queda cubierta por los tests automatizados.

## Matching y ahorro

- Se muestra ahorro en 43 casos: 15 exact, 7 near y 21 broad.
- Los 21 broad muestran el aviso orientativo obligatorio.
- Ninguna fila sin nivel de comparables expone un ahorro.
- Hay 27 ahorros negativos: no son un error aritmético; indican que importar cuesta más que la mediana española. Conviene tratarlos como resultado desfavorable, no como “ahorro”.
- Cinco resultados merecen revisión visual por magnitud: Renault Master 461734782 (+13.451,94 €, broad y fallback BOE), Renault Koleos 449327883 (−4.988,41 €, near con un comparable), Ford Focus 443938979 (−21.591,85 €, broad), Toyota Proace 414176502 (−18.751,05 €, near con un comparable) y Kia EV3 460264044 (−21.660,49 €, exact con 14 comparables).

## Patrones nuevos y prioridades propuestas

1. **Potencia híbrida no homogénea.** mobile.de y BOE alternan entre potencia térmica y potencia total del sistema. Es la causa más clara de discrepancias grandes y no debe resolverse aumentando la tolerancia.
2. **PHEV frente a híbrido BOE.** Separar `PHEV` de `GyE` es fiscalmente honesto, pero deja variantes reales sin casar cuando Hacienda solo usa una etiqueta híbrida. Requiere una regla específica y trazable, no un alias global.
3. **Cilindradas nominales.** Cinco casos parecen equivalencias de ficha (±1/2/4/44 cm³). Cilindrada sigue exacta como se pidió; sería el siguiente criterio a estudiar con evidencia por familia de motor.
4. **Segmentación de marca/modelo.** `Seat Terra` revela que el origen puede partir `CUPRA Terramar` incorrectamente. Debe corregirse en extracción, no relajando el resolver.
5. **Carrocería ausente.** Falta en 30 anuncios; el cálculo usa el tramo conservador previsto, pero reduce precisión de transporte.
6. **Particulares y CO₂.** Cinco de seis particulares quedaron pendientes porque la ficha no aporta CO₂. El flujo de petición al usuario está actuando como se diseñó y esos valores no entran en memoria.

## Integridad

- Las 58 columnas coinciden con la matriz anterior.
- Los 100 IDs son únicos y ajenos a la tanda de 35.
- La suma del desglose coincide con el precio final en los 94 cálculos.
- 168 tests pasan.

