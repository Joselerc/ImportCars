# Prompt para Cursor — Transporte, modo auditoría, panel admin y seguimiento de mercado

Cuatro bloques de trabajo. El **A** es una corrección de datos. El **B** hace verificable el cálculo. El **C** es un panel admin nuevo. El **D** es inteligencia de mercado (velocidad de venta y precios). Respeta en todo momento la separación ya establecida: producto público (cliente) vs. herramientas internas; el `fiscal_engine` es fuente única y no se duplica.

---

## BLOQUE A — Corregir el coste de transporte (subestimado)

El valor por defecto actual (~550 €) corresponde a conducir el coche con placas de exportación, no al transporte profesional en camión. El coste real de mercado del transporte en camión Alemania → España para un turismo estándar es **800–1.200 €** (verificado con competidores del sector e importadores logísticos). El valor bajo distorsiona el ahorro: en coches de margen fino convierte un "ahorras 452 €" en pérdida real, lo que daña la confianza del cliente.

- Sustituye el valor por defecto por una **estimación por tramos** en `CostesConfig`/tablas, no un fijo: base ~900 € turismo estándar, con incremento para SUV/monovolumen y para deportivo/gama alta. Deja el parámetro preparado para afinar por distancia (origen en Alemania → destino en España) más adelante.
- Mientras no haya cálculo por distancia, **peca por arriba** (~900–950 € por defecto): mejor una sorpresa buena en el presupuesto formal que una mala.
- Esto es un ajuste de parámetro de coste, **no** de fórmula fiscal. No toques el resto del `fiscal_engine`.
- Actualiza los tests que dependan del valor de transporte.

---

## BLOQUE B — Modo auditoría (activable por el admin, oculto para el cliente)

Objetivo: que el fundador pueda verificar qué hace el sistema y con qué compara, sin ensuciar la vista del cliente. **Dos modos**: vista normal (cliente, como está hoy) y vista auditoría (interna). Actívala del modo más simple y seguro (parámetro protegido, sesión de admin, o disponible solo dentro del panel admin del Bloque C). En modo cliente **no cambia nada**: sin jerga, sin break-even, sin comparables crudos.

En **modo auditoría** hay que mostrar:

### B1 — Comparables de coches.net: resumen + detalle desplegable
- Resumen: precio medio, **rango mínimo–máximo** y número de comparables.
- Lista desplegable con **cada coche comparable**: precio, kilómetros, año, versión/motorización, combustible, cambio (manual/automático) y **enlace al anuncio en coches.net**.
- **Criterios de match usados** (marca, modelo, versión, rango de año, combustible, y si se consideraron km/cambio) y **nivel de comparación aplicado** (exact/near/broad).
- Propósito: permitir juzgar de un vistazo si la comparación es legítima (que no mezcle un GTI con un Golf normal, ni un diésel con un gasolina, ni años/km dispares). Ver también el Bloque B3.

### B2 — Cada fila del desglose fiscal: abrible para ver fórmula y números
Al desplegar una fila, mostrar los **números intermedios reales** que ya calcula el `fiscal_engine` (exponerlos, no recalcular):
- **IEDMT**: valor de tablas del BOE (con el **ID/fila del BOE** que resolvió `resolver_valor_tablas`), coeficiente de depreciación por antigüedad, IVA histórico e IEDMT histórico usados en el denominador, base tras minoración, tipo aplicado (con recargo autonómico si aplica) y cuota.
- **ITP**: base = max(precio, valor tablas depreciado), tipo por CCAA, cuota.
- **IVTM**: CVF usado (y si vino de ficha o se estimó), tarifa base del tramo, coeficiente municipal, prorrateo por trimestres, cuota.
- **IVA**: si aplica (nuevo/ROI), base y tipo.
- Arquitectura: ampliar `ResultadoFiscal`/`LineaCoste` para **exponer** estos valores intermedios y el ID de la fila del BOE. No duplicar lógica ni recalcular fuera del motor. La vista cliente sigue mostrando solo etiqueta, importe y nota corta.

### B3 — Aviso de calidad de la comparación (nota de producto, importante)
La validez del ahorro depende de que los comparables coincidan de verdad en las variables que mueven el precio: **kilómetros, año, combustible (gasolina/diésel) y cambio (manual/automático)**, además de marca/modelo/versión. Preocupación explícita del fundador.
- **Ahora (verificable):** el modo auditoría debe dejar ver esas variables en cada comparable y los criterios de match, para poder detectar comparaciones malas observando coches reales.
- **Mejora futura (no la implementes a ciegas todavía):** afinar la política de emparejamiento para que km, combustible y cambio pesen adecuadamente y se excluyan comparables no homologables. Primero se hace visible, se observa con casos reales, y luego se decide el ajuste fino. Deja el código del match preparado para endurecer estos criterios, pero no cambies su comportamiento sin validación.
- Si tras aplicar criterios estrictos quedan muy pocos comparables, el producto debe **decirlo** (p. ej. "comparación orientativa, pocos comparables") en lugar de mostrar un ahorro con falsa precisión.

---

## BLOQUE C — Panel admin (web aparte, con login, dentro del mismo proyecto)

Panel de administración **separado** del producto público y del dashboard interno de oportunidades. Cuatro capas. Construir las cuatro, sabiendo que 3 y 4 se llenan con tráfico real (por eso, generar datos simulados para validarlas, ver más abajo).

### Seguridad y RGPD (requisito, no opcional)
- **Login real** (no una URL "secreta"). Autenticación con sesión; credenciales fuera del código (variables de entorno).
- El panel maneja datos personales (emails, teléfonos de leads): **consentimiento** explícito registrado en el formulario público, capacidad de **borrar** los datos de una persona a petición (derecho de supresión), y no exponer datos personales fuera del panel autenticado.
- Registrar solo lo necesario; si se guarda IP o identificadores, documentarlo.

### Capa 1 — Actividad de clientes (cálculos)
Registrar **todos** los cálculos, incluidos los de visitantes anónimos (sin datos personales). Guardar todos anónimos y vincular datos personales solo cuando el usuario los deja (gate/lead).
- Por cada cálculo: coche introducido (URL o datos manuales), precio final, ahorro, y **los comparables exactos mostrados, congelados en ese momento** (coches.net cambia a diario; hay que conservar lo que el cliente vio, no una recreación posterior). Esto también protege ante discusiones sobre un presupuesto.
- Guardar el `ResultadoFiscal` con sus intermedios (los del Bloque B2) para poder auditar a posteriori.

### Capa 2 — Embudo de conversión
Métricas por etapa: visitas → cálculos → leads (dejan datos) → contactos WhatsApp → (más adelante) contratados. Mostrar **dónde se cae la gente** entre etapas, no solo totales. Preparar el modelo para marcar manualmente un lead como "contratado" (cierre), para poder medir conversión final.

### Capa 3 — Inteligencia de mercado (demanda de clientes)
Agregados a partir de la Capa 1: coches/marcas más buscados, modelos con más ahorro medio, provincias de origen de la demanda. Sirve para decidir especialización y contenido. Se llena con volumen → validar con datos simulados.

### Capa 4 — Salud del sistema y protección
- Cálculos con **avisos** (CO₂ sin confirmar, sin comparables, sin fila BOE), cálculos con **ahorro negativo o anómalamente alto** (habría cazado el bug del transporte al instante).
- Estado de los **scrapers** (mobile.de, coches.net): último barrido correcto, tasa de error, detección de bloqueos. El fundador debe enterarse antes que el cliente.
- Se valida con datos simulados.

---

## BLOQUE D — Seguimiento de mercado: velocidad de venta y precios

Enfoque elegido: **el barrido periódico del opportunity finder guarda lo que ve, y la venta se deduce sola** comparando barridos consecutivos (un anuncio que estaba y deja de estar ≈ vendido). Sin trabajo manual. Es inteligencia de mercado y vive con el opportunity finder y su base de datos (la persistencia y el `price_history` que ya existen), **no** con los cálculos de clientes: son sistemas separados que el panel admin luego muestra juntos.

### D1 — Persistencia del histórico de anuncios
- Cada barrido hace **upsert** de los anuncios vistos (por `listing_id + source`) con fecha de primera vez visto y última vez visto.
- Cuando un anuncio deja de aparecer en barridos sucesivos, marcar `desaparecido` con fecha → **días en mercado** = última_vez_visto − primera_vez_visto. Interpretar como venta probable (con la cautela del punto D4).
- Guardar `price_history` por anuncio en cada barrido para detectar **bajadas de precio** (útil como palanca de negociación) y **tendencia de precio del modelo** (contenido de marketing: "los X han bajado un N% este trimestre").

### D2 — Frecuencia CONFIGURABLE desde el panel admin
- El fundador define desde el panel admin cada cuánto se ejecuta la comprobación/barrido (minutos, horas, días). No fijar la frecuencia a fuego.
- Empezar conservador para no saturar el scraping ni provocar bloqueos; permitir subir la resolución si se necesita. Respetar los límites, backoff y pausas ya implementados.
- Nota de resolución: cuanto más frecuente el barrido, más preciso el "días en mercado"; un barrido muy espaciado solo da una cota.

### D3 — Conjunto seguido estable (no solo lo que pega el cliente)
- Para que la velocidad de venta sea representativa, seguir un **conjunto estable de modelos objetivo** definido por el fundador (los que le interesan), no solo los anuncios que entran por la calculadora (muestra sesgada y mínima).
- Permitir gestionar esa lista de modelos objetivo desde el panel admin.

### D4 — Cautelas (mostrarlas en el panel, no ocultarlas)
- "Desaparecido" ≠ "vendido" con certeza a nivel de un coche (puede retirarse, caducar o republicarse con otra URL). Es fiable **en agregado** (muchos anuncios de un modelo desapareciendo rápido = modelo líquido), no coche a coche. El panel debe presentar la velocidad de venta como **estimación agregada**, con el número de anuncios en que se basa.
- La comparación de qué es "el mismo coche" arrastra la misma preocupación del Bloque B3 (km, año, combustible, cambio): agrupar por variantes homologables, no solo por modelo.

---

## Datos simulados para validar los paneles

Como las capas 3 y 4 y el seguimiento de mercado necesitan volumen, generar un **conjunto de datos de prueba (seed/fixtures)** que llene el panel admin con cálculos, leads, barridos históricos y anuncios aparecidos/desaparecidos, para poder ver los paneles funcionando y validar los agregados (embudo, velocidad de venta, tendencias). Debe ser claramente datos de prueba, aislados de datos reales y fáciles de borrar.

---

## Principios transversales (no romper)

- Producto público **sin cambios** de cara al cliente: sin jerga, sin break-even, sin comparables crudos, sin datos internos. Todo en **español correcto con tildes**.
- `fiscal_engine` = **fuente única**; exponer intermedios, nunca duplicar ni recalcular fórmulas fuera del motor.
- Mantener separados: cálculos de clientes (con leads) vs. seguimiento de mercado (con el opportunity finder). El panel admin los muestra; por debajo son sistemas distintos.
- **Seguridad primero**: login real y RGPD en el panel; nada de datos personales expuestos sin autenticar.
- Los **61 tests** siguen en verde; añadir tests para: transporte por tramos, intermedios fiscales expuestos, registro de cálculos, embudo, y detección de aparición/desaparición de anuncios.
- Trabajo incremental y verificable; no eliminar el opportunity finder ni su lógica.

---

## Orden sugerido
A (rápido, corrige exactitud) → B (hace verificable el cálculo) → C capas 1 y 2 (lo que se usa desde el primer cliente) → D (seguimiento de mercado) → C capas 3 y 4 + datos simulados (se llenan con volumen). Revisión visual en local por el fundador tras cada bloque con datos reales.