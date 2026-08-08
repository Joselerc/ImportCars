# Validación final del matching: batería y filtro de cordura

Fecha: 8 de agosto de 2026.

## Alcance aplicado

- En eléctricos y PHEV, `exact` y `near` exigen que origen y comparable declaren
  una batería dentro de ±5 kWh. Sin dato o fuera del margen, el máximo posible
  es `broad`.
- El umbral de ahorro fiable es configurable mediante
  `IMPORT_CARS_MAX_RELIABLE_SAVINGS_PCT` y vale ±35 % por defecto.
- Fuera del umbral se conserva el precio final, se oculta el ahorro al cliente y
  la auditoría conserva el importe y porcentaje calculados junto al motivo.
- No se ha afinado ningún acabado o equipamiento de combustión.

## Método de comparación

Se reprocesaron los mismos 100 IDs en dos pasadas consecutivas:

1. commit anterior `a6998c3`, que ya contiene la corrección de doble IVA pero no
   batería ni filtro de cordura;
2. implementación nueva.

Ambas pasadas usaron la misma SQLite oficial del BOE. Se pudieron recalcular 93
anuncios en las dos; 7 ya no eran calculables por datos retirados/incompletos o
por un detalle que ahora devuelve 404. Al ser marketplaces vivos, la comparación
se ejecutó con pocos minutos de separación para minimizar cambios de inventario.

## Resultado global sobre los 100

| Métrica | Antes | Después |
|---|---:|---:|
| IDs conservados | 100 | 100 |
| Anuncios calculables | 93 | 93 |
| Comparaciones con ahorro calculado internamente | 57 | 61 |
| Ahorros fuera de ±35 % calculados internamente | 20 | 18 |
| Ahorros fuera de ±35 % visibles al cliente | 20 | **0** |
| Ahorros creíbles visibles al cliente | 37 | 43 |
| Ahorros ocultos por el filtro de cordura | 0 | **18** |
| Sin referencia de ahorro por falta de mercado homologable | 36 | 32 |

La batería hizo que 3 de los 20 ahorros anteriormente anómalos pasaran a un
rango creíble. Otros 17 siguieron siendo anómalos y quedaron ocultos. Además,
la normalización necesaria del literal interno `phev` permitió obtener cuatro
referencias `broad` que antes no se calculaban: tres resultaron creíbles y una
fue ocultada por el filtro. Por eso el estado final contiene 18 ahorros internos
anómalos, todos invisibles para el cliente.

## Cobertura de batería

Entre los 93 anuncios calculables había 25 eléctricos/PHEV. El origen declaraba
capacidad numérica en 15 (60 %). Tras el cambio:

- los 5 eléctricos/PHEV que alcanzaron `exact` o `near` tenían batería conocida;
- 13 quedaron en `broad`, con advertencia cuando faltaba el dato o no coincidía;
- 7 no tuvieron comparables dentro de `broad` y no mostraron ahorro.

La auditoría muestra los kWh del origen y de cada comparable, la diferencia, la
tolerancia y el resultado del criterio.

## Cuatro casos solicitados

| Caso | Antes | Después | Resultado |
|---|---|---|---|
| Ford Focus 443938979 | `broad`, 53 comparables, mediana 18.990 €, final 35.475,80 €, ahorro −16.485,80 € (−86,81 %) | Mismos datos internos; ahorro público oculto | El filtro evita publicar el −86,81 % sin tocar el precio final. No aplica batería por ser MHEV no enchufable. |
| Kia EV3 460264044 | `exact`, 42 comparables mezclados, mediana 33.900 €, final 48.027,21 €, ahorro −41,67 % | `exact`, 14 comparables de 81,4 kWh frente a origen de 81,0 kWh, mediana 36.990 €, ahorro −11.037,21 € (−29,84 %) | La batería elimina 28 comparables no equivalentes y devuelve el ahorro al rango permitido. |
| Hyundai Tucson 438551969 | `broad`, 23 comparables, mediana 32.990 €, final 43.241,76 €, ahorro −31,08 % | Sin cambios | Es un HEV no enchufable: la batería no interviene y el ahorro ya era creíble. |
| Toyota Proace 414176502 | `near`, 1 comparable, mediana 29.995 €, final 42.424,96 €, ahorro −41,44 % | `broad`; el único comparable declara 50 kWh frente a 75 kWh del origen; ahorro oculto | Deja de presentarse como comparación cercana y el filtro impide publicar la cifra anómala. |

## Regresión del grueso de negocio

Se aisló el subconjunto de usados de 3.000–30.000 €, no eléctricos/PHEV, con
ahorro previo dentro de ±35 %. Fueron 18 casos:

- 18/18 conservaron exactamente el mismo precio final al céntimo;
- 18/18 conservaron el mismo nivel de matching;
- 0/18 activaron el filtro de cordura.

Por tanto, estos dos cambios no alteran los usados de gama media que ya tenían
una comparación creíble.

## Archivos de evidencia

- `validacion_real_100_pre_bateria_cordura_2026-08-08.csv`: pasada de control
  inmediatamente anterior.
- `validacion_real_100_post_bateria_cordura_2026-08-08.csv`: resultado final.

El CSV posterior añade batería, ahorro interno, porcentaje interno, activación
del filtro y umbral. Así el dato oculto sigue siendo auditable sin exponerse en
el producto público.
