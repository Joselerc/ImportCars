# Diagnóstico de ahorros extremos — 8 de agosto de 2026

> Estado posterior: la causa C descrita en este informe quedó corregida en el
> commit dedicado al doble conteo de IVA. La causa A continúa pendiente y el
> Bloque C sigue pausado. Véase `informe_correccion_doble_iva_2026-08-08.md`.

## Alcance y método

Este informe reproduce los comparables de coches.net que alimentaron los cinco
resultados extremos de la validación de 100 anuncios. No cambia el matching ni
el motor fiscal. La extracción se repitió contra los anuncios vivos, por lo que
un marketplace puede variar alguna unidad respecto al CSV de validación original.

El archivo `diagnostico_ahorros_extremos_2026-08-08.csv` contiene los 104
comparables recuperados, incluidos los 50 del Ford Focus, con precio, kilómetros,
año, versión/motor, combustible, cambio estructurado, potencia, cilindrada y URL.
La columna `used_for_price` identifica los anuncios que entraron en la mediana.

Para detectar precios corruptos se ha usado el criterio de Tukey: un precio sería
atípico si estuviera fuera de Q1 − 1,5×IQR o Q3 + 1,5×IQR. Ninguno de los cinco
conjuntos contiene un outlier según ese criterio.

## Caso principal: Ford Focus 443938979

### Vehículo alemán

| Campo | Valor |
|---|---|
| Versión anunciada | Titanium X Turnier · automático · navegación |
| Carrocería | Familiar (Turnier) |
| Año / km | 2026 / 1.050 km |
| Motor | 999 cc · 114 kW / 155 CV · híbrido gasolina |
| Precio bruto / neto | 31.980 € / 26.873,95 € |
| Clave de motor obtenida por el matching | `na` |
| Nivel finalmente usado | `broad` |

La clave queda en `na` porque el texto conservado por mobile.de contiene el
acabado (`Titanium X Turnier`) pero no la palabra `EcoBoost`. Aunque existen
cilindrada y potencia estructuradas, el nivel `broad` no exige una clave de motor
identificable.

### Comparables españoles realmente usados

- Se usaron 50 anuncios: mínimo 15.550 €, mediana 18.990 € y máximo 28.500 €.
- Los años van de 2022 a 2026 y los kilómetros de 2 a 60.776.
- El pool mezcla 125 y 155 CV, acabados ST-Line, ST-Line X y Active, y sobre todo
  carrocerías `5p`; no exige que sean familiares Turnier/Sportbreak.
- Coches.net no entrega el cambio en el campo estructurado de estos 50 resultados.
  Algunos textos contienen `Auto`, pero el matcher recibe el cambio como ausente;
  por ello no puede comparar realmente automático con automático en este pool.
- Los 50 precios están dentro de 15.550–28.500 €. Q1 es 17.490 €, Q3 es
  21.967,50 € y los límites de Tukey son 10.773,75–28.683,75 €. No hay precios
  corruptos ni estadísticamente atípicos.

El detalle fila a fila y los enlaces están en el CSV adjunto. Ejemplos que muestran
la heterogeneidad:

| Precio | Año | Km | Versión española | Observación |
|---:|---:|---:|---|---|
| 15.550 € | 2022 | 49.066 | 1.0 EcoBoost MHEV Active, 155 CV | 4 años más viejo; 48.016 km más |
| 16.599 € | 2022 | 53.633 | 1.0 EcoBoost MHEV ST-Line, 125 CV | Potencia, acabado, año y km distintos |
| 18.990 € | 2023 | 57.000 | 1.0 EcoBoost MHEV ST-Line, 155 CV | Da valor a la mediana; no es Turnier/Titanium X |
| 22.699 € | 2025 | 5.211 | ST-Line X 1.0 EcoBoost MHEV Auto, 155 CV | Técnicamente cercano, acabado/carrocería distintos |
| 27.900 € | 2026 | 10 | ST-Line X 1.0 EcoBoost MHEV Auto, 155 CV | Referencia nueva mucho más próxima al objetivo |
| 28.500 € | 2025 | 6.785 | 1.0 EcoBoost MHEV ST-Line Auto, 155 CV | No es un outlier; está dentro del rango estadístico |

**Diagnóstico del Focus:** domina la causa A. La mediana no está hundida por un
precio basura: se construye con una mayoría de Focus más antiguos, más rodados y
de otro acabado/carrocería. La ausencia de clave de motor y de cambio estructurado
obliga a `broad` y hace que todo el pool amplio entre en la mediana.

## Los otros cuatro casos

| Vehículo | Nivel / n | Rango y mediana | Outliers | Diagnóstico del pool |
|---|---:|---:|---:|---|
| Kia EV3 81 kWh | exact / 14 | 28.900–43.900 €; mediana 33.550 € | 0 | Mezcla Air, Earth y GT-Line, y Standard Range con Long Range. La clave eléctrica no representa la batería ni el acabado. Causa A. |
| Hyundai Tucson Impression 20th | broad / 25 (24 en la ejecución original) | 28.900–39.900 €; mediana viva 33.500 € (33.245 € originalmente) | 0 | El objetivo es Impression 20th; se mezcla con Maxx, Klass, Tecno, Black Line y N Line. La clave de motor cae además en `1600:20th`, un token de aniversario, y no identifica el HEV. Causa A. |
| Cupra Tavascan Endurance | exact / 14 | 34.644–44.500 €; mediana 37.445 € | 0 | Los comparables sí son Endurance 77 kWh; aquí el matching es razonable. El ahorro negativo extremo procede principalmente de la composición del coste final, no de A ni B. |
| Toyota Proace Electric 75 kWh | near / 1 | 29.995 € | No evaluable con n=1 | El único comparable es Shuttle 50 kWh VX L2. La batería difiere y el motor eléctrico genérico no la distingue. Causa A y muestra insuficiente. |

## Tercera distorsión independiente: composición del IVA en coches nuevos

Los cinco anuncios son fiscalmente nuevos, profesionales y con IVA desglosable.
La cuota española se calcula correctamente sobre el neto anunciado, pero el coste
final conserva como precio de adquisición el bruto alemán y después suma la cuota
española. En la práctica aparecen juntos el IVA alemán incluido en el bruto y el
IVA español. Esto no es causa A ni B y no se ha corregido en esta tarea.

| Vehículo | Bruto alemán | Neto anunciado | IVA español calculado | Exceso por conservar el bruto |
|---|---:|---:|---:|---:|
| Focus | 31.980 € | 26.873,95 € | 5.643,53 € | 5.106,05 € |
| Tucson | 38.880 € | 32.672,27 € | 6.861,18 € | 6.207,73 € |
| Proace | 39.590 € | 33.268,91 € | 6.986,47 € | 6.321,09 € |
| Tavascan | 42.990 € | 36.126,05 € | 7.586,47 € | 6.863,95 € |
| EV3 | 44.990 € | 37.806,72 € | 7.939,41 € | 7.183,28 € |

## Conclusión

Entre las dos hipótesis planteadas, **domina A: comparables mal emparejados o con
una granularidad insuficiente de versión, carrocería, batería y cambio**. No hay
evidencia de B: ningún pool contiene un precio atípico por IQR y el Focus no tiene
un anuncio basura aislado que hunda su mediana.

Hay además una causa C independiente que amplifica todos estos porcentajes en los
coches nuevos con IVA desglosable: la composición del precio final suma el IVA
español al bruto alemán. Quedan anotadas A y C para una decisión posterior. No se
ha alterado ninguna de esas dos lógicas durante este diagnóstico.
