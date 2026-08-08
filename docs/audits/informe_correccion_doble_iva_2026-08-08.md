# Corrección del doble conteo de IVA — 8 de agosto de 2026

## Cambio aplicado

El caso `nuevo_iva_espanol` usa ahora la misma base neta para dos finalidades:

1. como componente «Precio del coche» del desglose y del coste final;
2. como base sobre la que se calcula y suma una sola vez el IVA español.

Si el anuncio publica el neto, se usa ese importe. Si solo publica el bruto de un
profesional con IVA desglosable, se usa `bruto ÷ 1,19`. Para un nuevo sin IVA
alemán desglosable, el precio permanece intacto. Los vehículos usados continúan
sumando el precio real pagado y cero IVA español.

No se ha modificado el matching de comparables ni ninguna lógica del Bloque C.

## Ford Focus 443938979

Reprocesado con el anuncio vivo y el pool combinado de coches.net y AutoScout24.
La referencia española continúa en 18.990 €, por lo que la variación procede
exclusivamente de retirar el IVA alemán del componente de adquisición.

| Concepto | Antes | Después | Diferencia |
|---|---:|---:|---:|
| Precio del coche en el total | 31.980,00 € | 26.873,95 € | −5.106,05 € |
| IVA español | 5.643,53 € | 5.643,53 € | 0,00 € |
| Componente coche + IVA español | 37.623,53 €* | 32.517,48 € | −5.106,05 € |
| Precio final en España | 40.581,85 € | 35.475,80 € | −5.106,05 € |
| Ahorro frente a 18.990 € | −21.591,85 € | −16.485,80 € | +5.106,05 € |
| Ahorro porcentual | −113,70 % | −86,81 % | +26,89 puntos |

\* El valor anterior sumaba el bruto alemán, que ya incluía IVA alemán, y el IVA
español. El valor posterior suma 26.873,95 € + 5.643,53 € = 32.517,48 €.

El porcentaje todavía no es creíble porque el Focus continúa calculándose con
comparables `broad` de versiones, carrocerías y kilometrajes heterogéneos. Esa es
la causa A, expresamente fuera del alcance de esta corrección.

## Regresión de vehículos usados

| Caso real | Régimen | Precio pagado | Final antes | Final después |
|---|---|---:|---:|---:|
| Mercedes-Benz EQA 250 — 461570243 | Usado a particular | 27.380,00 € | 30.805,97 € | 30.805,97 € |
| BMW 218i Cabrio — 462278574 | Usado, régimen de margen | 14.990,00 € | 18.369,18 € | 18.369,18 € |
| Volkswagen Golf GTI Clubsport — 451486327 | Usado, régimen de margen | 24.900,00 € | 27.982,37 € | 27.982,37 € |

Los tres mantienen el precio pagado como componente de adquisición, IVA español
cero y el mismo coste final al céntimo.

## Nuevo profesional sin neto publicado

Caso controlado: Volkswagen ID.3 nuevo, bruto alemán de 37.890 € e IVA
desglosable, sin precio neto publicado.

| Concepto | Resultado |
|---|---:|
| Neto calculado (`37.890 ÷ 1,19`) | 31.840,34 € |
| IVA español (`neto × 21 %`) | 6.686,47 € |
| Neto + IVA español | 38.526,81 € |
| Precio final anterior | 46.707,55 € |
| Precio final corregido | 40.657,89 € |
| Doble conteo eliminado | 6.049,66 € |

La auditoría registra `bruto_dividido_1_19` como fuente de la base y muestra
31.840,34 € como precio de adquisición. El bruto no vuelve a sumarse al total.
