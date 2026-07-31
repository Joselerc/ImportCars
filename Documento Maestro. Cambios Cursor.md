# Documento maestro de cambios — ImportCars

**Para:** ejecución en Cursor
**Objetivo:** reparar lo que está roto, sanear riesgos de seguridad y **construir el nuevo producto de cara al cliente** (calculadora de precio final), **sin eliminar** la lógica actual del detector de oportunidades.

---

## 0. Principio rector (leer antes de tocar nada)

Este repositorio contiene hoy un **detector de oportunidades de arbitraje para un dealer**: le das un modelo y te dice si comprando en Alemania y revendiendo en España habría margen. Ese producto **se conserva íntegro** como herramienta interna de sourcing (y posible producto futuro: sección de "chollos" para clientes, o producto vendible a otros importadores).

En paralelo se construye un **producto nuevo, distinto y separado**: una calculadora pública orientada al **cliente final que quiere importar su propio coche para conducirlo**. Su número protagonista no es el margen ni el break-even, sino el **precio final del coche puesto en España, matriculado y a nombre del cliente**, más **cuánto se ahorra frente a comprarlo en España**.

### Reglas duras para esta ejecución
1. **No eliminar** la lógica del detector de oportunidades: `analysis/opportunity.py`, el scoring, break-even, comparables, el dashboard interno, la CLI de comparación. Todo se queda.
2. **Sí eliminar** únicamente lo que es basura o riesgo (perfil de navegador, artefactos de debug, código muerto explícitamente marcado abajo).
3. **Reutilizar** el motor de datos común (scrapers, enriquecimiento CO₂, modelos Pydantic) para ambos productos. Una sola fuente de verdad.
4. El **motor fiscal** se reescribe orientado al **coste del cliente** (no solo break-even), pero **manteniendo** las funciones actuales que usa el opportunity finder, para no romperlo.
5. Trabajo **incremental y verificable con tests**; no borrar cambios de trabajo existentes.

---

## 1. Arquitectura objetivo (dos caras, un motor)

```
                 ┌──────────────────────────────────────┐
                 │        MOTOR COMÚN (reutilizado)       │
                 │  Scrapers DE + ES · Enriquecimiento    │
                 │  CO2 · Modelos Pydantic · fiscal_engine│
                 └──────────────┬───────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                ▼                                ▼
   ┌─────────────────────────┐      ┌──────────────────────────────┐
   │ INTERNO (se conserva)    │      │ PÚBLICO (nuevo)               │
   │ Opportunity finder:      │      │ Calculadora de precio final:  │
   │ dashboard, scoring,      │      │ URL/manual → precio final →   │
   │ break-even, comparables  │      │ ahorro vs España → desglose → │
   │ margen. Herramienta de   │      │ captura de lead → WhatsApp.   │
   │ sourcing / futuro producto│      │ Sin jerga de margen.          │
   └─────────────────────────┘      └──────────────────────────────┘
```

El scraping se **desacopla de la web** (worker + persistencia); la web solo lee resultados. Esto resuelve de raíz los problemas de la API pública costosa y de serverless, y sirve a ambas caras.

---

## 2. Bloque A — Seguridad (URGENTE, antes que nada)

> Fuente: hallazgo P0 de Cursor + auditoría propia. Esto no espera a decisiones de producto.

**A1. Purgar el perfil de navegador del repositorio y del historial de Git.**
- `playwright-coches-net-profile/` contiene bases de datos de Chrome, cookies y datos de sesión, y **está rastreado por Git**. `.vercelignore`/`.gitignore` no bastan: sigue en el historial de GitHub.
- Acciones: eliminar el directorio del working tree; añadirlo a `.gitignore`; **reescribir el historial** para borrarlo de todos los commits (`git filter-repo --path playwright-coches-net-profile --invert-paths` o BFG); forzar push del historial limpio; **rotar/invalidar** cualquier sesión o cookie que haya estado ahí (volver a hacer login en coches.net desde cero).
- Criterio de aceptación: el repositorio y su historial no contienen cookies, perfiles ni dumps de navegación. `git log --all -- playwright-coches-net-profile/` no devuelve nada.

**A2. Retirar artefactos de debug y datos del repo.**
- Eliminar y gitignorar: `debug_*.html`, `debug_*.png`, `test_curl_cffi_output.html`, `mobile_de_html_full.txt`, `src/debug_*`, `exports/*.csv|xlsx`, `__pycache__/`, `.venv/`, `mobilede_models_fetch.log`.
- Conservar un fixture pequeño y anonimizado del HTML de mobile.de para tests (ver B1), no el dump de 1 MB.
- Criterio: el repo pesa una fracción de lo actual; `git status` limpio; no hay binarios ni dumps.

---

## 3. Bloque B — Reparación que desbloquea todo

> Sin datos no hay producto (ni interno ni público). Esto es lo segundo.

**B1. Arreglar el extractor de mobile.de (está roto contra el HTML actual).**
- Problema confirmado: `_extract_ids_from_listing()` busca anchors `detalles.html?id=` en el DOM y **devuelve 0**, aunque el HTML contiene ~24 anuncios. mobile.de sirve los datos en el **payload de Next.js** (`__NEXT_DATA__` / estado embebido), no en anchors navegables.
- Acción: parsear el JSON embebido de Next.js del HTML de listado y extraer de ahí los anuncios (id, precio, año, km, combustible, potencia, y lo que traiga estructurado). Mantener el parseo del DOM como **fallback**.
- Beneficio doble: además de reparar, **elimina el patrón N+1** (una petición de detalle por anuncio). Con los datos del listado se pre-filtra y solo se pide el detalle del top-N que pasa el corte (el detalle se necesita sobre todo para CO₂ y vendedor).
- Añadir: backoff exponencial con jitter entre reintentos y pausas entre páginas (usar `tenacity`, ya está en deps); conectar la rotación de proxies de `ScraperSettings` a la sesión curl_cffi (hoy se ignora).
- Criterio de aceptación: un test sobre un **fixture local** del HTML actual recupera los ~24 IDs, y cada anuncio conserva ID y URL válidos. Un barrido real de un modelo devuelve >0 anuncios.

**B2. Consolidar los dos scrapers de mobile.de.**
- Hay dos implementaciones: `mobile_de.py` (Playwright, obsoleta, con `if i >= 2: break` que corta a 3 anuncios, selectores frágiles y prints de debug) y `mobile_de_http.py` (curl_cffi, la buena).
- Acción: dejar la HTTP como única vía. **No borrar** la Playwright de golpe si el opportunity finder la referencia en algún flujo; en su lugar, marcarla como deprecada y retirar su uso del CLI, o reducirla a utilidad de bootstrap de cookies si hiciera falta. Quitar el `if i >= 2: break` y los artefactos de debug en cualquier caso.
- Criterio: un solo scraper de mobile.de en el camino activo; sin límite artificial de 3 anuncios; sin escritura de ficheros de debug en disco.

**B3. Corregir la sesión curl_cffi compartida entre hilos.**
- `_fetch_details_parallel()` reutiliza `self.session` dentro de un `ThreadPoolExecutor` → posibles condiciones de carrera y cookies compartidas.
- Acción: una sesión por hilo (o un pool de sesiones), no una compartida.
- Criterio: sin errores intermitentes en barridos paralelos; test de concurrencia básico.

---

## 4. Bloque C — Motor fiscal correcto (base de los dos productos)

> Fuente: auditoría propia (errores E1–E7) + hallazgo P1 de Cursor. Se reescribe **orientado al coste del cliente**, conservando lo que usa el opportunity finder.

**C1. Crear un paquete `fiscal_engine` como única fuente de verdad.**
- Lo consumen: el opportunity finder (interno), la calculadora pública (nueva) y los presupuestos. Hoy `import_calculator.py` está hardcodeado a Madrid y con errores graves.

**C2. Corregir las fórmulas (errores confirmados):**
- **Base imponible ≠ precio del anuncio.** Implementar el valor de tablas oficiales de Hacienda depreciado por antigüedad, con la **minoración** del art. 5: `BI_IEDMT = ValorTablas × coef_antigüedad / (1 + IVA_histórico + IEDMT_histórico)`. ITP sobre `max(precio, valor_tablas_depreciado)`. Esto exige un **input nuevo: fecha de 1ª matriculación** (hoy ni se recibe).
- **IVTM real por CVF** calculado desde la cilindrada (ya está en el modelo) × coeficiente municipal, **prorrateado** el primer año. Hoy usa `IVTM_MADRID=224` fijo e **ignora el parámetro `cvf`** que recibe.
- **Añadir la tasa de la DGT** (99,77 €), hoy ausente.
- **ITP por comunidad autónoma** (tabla configurable con cuotas fijas donde existan), no 4% fijo. Añadir el recargo autonómico del IEDMT.
- **Corregir la lógica IVA/REBU:** `EmpresaIVA` y `EmpresaMargen` hoy dan el mismo resultado, y REBU se aplica mal. REBU (IVA sobre margen) solo cuando la compra es sin IVA deducible; compra neta con ROI → IVA sobre total. Esto es lógica del **producto interno**; documentarla bien pero no mezclarla con el producto público.
- **Traducción jurada** como coste opcional (evitable con contrato bilingüe), no fijo.

**C3. Añadir el "modo cliente final" (lo que necesita el producto público):**
- Salida orientada al cliente: **coste total puesto en España** = coche + transporte + impuestos que paga el cliente + ITV + tasas DGT + IVTM + honorarios de gestión. Sin "margen" ni "break-even" en esta vista.
- **Comparación con el mercado español**: precio mediano del mismo modelo/año/km en coches.net (ya lo calcula el análisis) → **ahorro en euros**. Este es el segundo número clave del producto.
- Los honorarios de gestión son una **tarifa fija visible** (ver Bloque D, decisión de negocio: 900 € por defecto, configurable).

**C4. Mantener compatibilidad con el opportunity finder.**
- Las funciones que hoy usa `analysis/opportunity.py` (break-even por tipo de compra) deben seguir existiendo y funcionando, ahora con números correctos. El opportunity finder **no se toca en su lógica**; solo se beneficia de un motor fiscal arreglado.

**C5. Datos y mantenimiento:**
- Tablas del BOE (Anexo I precios medios + Anexo IV depreciación) en SQLite, versionadas por año (2026: Orden HAC/1501/2025). La Orden se publica cada enero; dejar un script de carga anual.
- Coeficientes IVTM municipales y tipos ITP por CCAA en datos configurables.
- Cada resultado hacia un cliente lleva la versión de tablas usada ("cálculo según Orden HAC/1501/2025") y un **flag de confianza del CO₂** (si es inferido, avisar de "confirmar CoC antes de comprar").

**C6. Tests de verdad (pytest):**
- La calculadora es donde un bug cuesta dinero real. Sustituir los `test_*.py` (scripts manuales con prints) por pytest con casos validados. Incluir el caso del Honda Civic 1.8 de 2006 y al menos un eléctrico (IEDMT 0%) y un coche en frontera de tramo de CO₂ (119/121 g/km).
- Criterio: `cvf`, base imponible, IVA/REBU, ITP, IEDMT y gastos regionales quedan separados y auditables; suite verde.

---

## 5. Bloque D — Producto público nuevo (la calculadora de cliente)

> Es un producto **nuevo**, no un retoque del dashboard. Referencia visual y de copy: el archivo `prototipo-calculadora.html` (adjunto por el usuario). Reproducir su estructura, tono y recorrido; los números del prototipo son de ejemplo y se sustituyen por el `fiscal_engine` real.

**Decisiones de negocio ya tomadas (no re-preguntar):**
- Entrada del coche: **dos vías visibles** — pegar URL de mobile.de/AutoScout24 (con extracción automática) **y** formulario manual (marca, modelo, año, precio, CO₂, vendedor, provincia).
- Honorarios: **tarifa fija visible** en el desglose (por defecto 900 €, configurable).

**D1. Recorrido del producto (según prototipo):**
1. **Hero** con propuesta clara y el input (URL / manual en pestañas).
2. **Resultado**: cifra grande = precio final en España; al lado, el ahorro vs. España en verde.
3. **Desglose línea a línea** en lenguaje de persona normal (no fiscalista): precio, transporte, IEDMT (con su tipo según CO₂), ITP (si particular), ITV+DGT+placas, IVTM, y **honorarios de gestión como línea transparente**. Cada concepto con micro-explicación.
4. **Captura de lead** (gate): la cifra se ve gratis; el PDF con desglose + análisis de riesgos del anuncio + presupuesto formal pide email/teléfono. CTA a WhatsApp.
5. **Secciones de confianza**: "tu dinero nunca pasa por nuestra cuenta" (flujo en 3 pasos), proceso en 5 pasos (~3 semanas), casos reales con cifras.

**D2. Parser de URL de anuncios:**
- Extraer del anuncio: precio, fecha 1ª matriculación, km, CO₂ (si consta), cilindrada, potencia, tipo de vendedor y —si es profesional— si el IVA es desglosable (dato para el caso fiscal). Fallback a formulario manual **siempre** (el parser es la pieza frágil).

**D3. Integración con el motor:**
- La calculadora pública llama al `fiscal_engine` en **modo cliente final**, no a la lógica de break-even. Nunca muestra "opportunity score", "margen" ni "break-even".
- Adaptar el cálculo a la **provincia/CCAA** del cliente (ITP y algún detalle cambian).

**D4. Alertas de riesgo del anuncio** (servicio y confianza):
- CO₂ no confirmado → aviso "confírmalo antes de comprar"; precio anormalmente bajo; datos incompletos. (El análisis con LLM puede venir después; de momento reglas simples.)

**Criterio de aceptación del bloque D:** un usuario pega una URL (o rellena el formulario) y obtiene precio final correcto + ahorro vs. España + desglose claro con honorarios visibles, y puede dejar sus datos / abrir WhatsApp. En ninguna pantalla del producto público aparece jerga de margen/arbitraje.

---

## 6. Bloque E — Desacoplar scraping de la web + persistencia

> Fuente: P0/P2 de Cursor (API pública costosa, serverless sin persistencia) + auditoría propia (web lanza CLI como subproceso).

**E1. Extraer la lógica a un servicio async llamable en proceso.**
- Hoy `/api/compare` hace `asyncio.create_subprocess_exec` lanzando el CLI entero y lee el CSV que ese proceso escribe. Sustituir por una función `run_comparison(filters) -> Result` que CLI y web llamen directamente. El CSV pasa a ser export opcional, no el canal entre capas.

**E2. Separar el worker de scraping de la petición web.**
- La web no debe bloquearse esperando un scraping de minutos. Patrón: la web encola/consulta; un worker ejecuta el scraping con límites de concurrencia, reintentos y guarda resultados. La web lee resultados persistidos.
- Esto además evita el problema serverless: **una función serverless no es un buen worker de scraping**. Si se despliega en Vercel, la web (ligera, lee resultados) puede ir ahí, pero el scraping corre en un worker con estado (o ejecución programada), no en la función serverless.

**E3. Persistencia (SQLite es suficiente para empezar).**
- Tablas: `listings` (upsert por listing_id+source), `price_history` (oro para marketing: "este modelo ha bajado un X% este trimestre"), `co2_reference` (hoy la memoria CO₂ vive en `~/.cache/` y se pierde en serverless y compite en concurrencia), `boe_valores`, `runs`.
- Los CSV en `/tmp` de Vercel no persisten: los informes duraderos necesitan la BD (o Blob/S3).
- Criterio: la web no bloquea esperando el scraping y puede consultar un resultado persistido; la memoria CO₂ deja de vivir en `~/.cache`.

---

## 7. Bloque F — Endurecimiento y calidad (en paralelo)

> Fuente: P1/P2 de Cursor + auditoría propia.

**F1. API y UI:**
- La API pública de comparación no puede disparar scraping ilimitado: añadir autenticación (al menos para el dashboard interno), rate limiting y cuota por IP. El opportunity finder es **herramienta interna** → protegerlo detrás de auth, no exponerlo público.
- **XSS**: `dashboard.js` interpola títulos, URLs, imágenes y metadatos con `innerHTML` sin escapar. Escapar o usar creación de nodos segura.

**F2. Validación de filtros:**
- `UnifiedFilters` permite `min > max` y `dealer_only + private_only` a la vez; los scrapers no siempre rechazan listings con el campo filtrado a `None`. Añadir validación cruzada y política explícita ante campos ausentes.
- Criterio: casos límite con tests; nunca se presenta un comparable débil como exacto.

**F3. Matching de comparables:**
- El nivel `broad` puede mezclar motorizaciones cuando faltan potencia o cilindrada. Endurecer la política de campos ausentes y normalizar el `import_ready_score` (hoy mezcla euros con bonus arbitrarios). Esto es del producto interno; mejora la calidad del sourcing.

**F4. Tests y CI:**
- `pytest -q` falla en collection: `test_curl_cffi.py` importa `bs4` no declarada y los `test_*.py` son scripts con red y escritura al importarse. Convertirlos en tests deterministas sin red (con fixtures) y mover a `tests/`.
- Añadir `bs4` a deps si se usa, o quitar el import. Resolver los 497 avisos de ruff de forma incremental (imports sin usar, `datetime` sin zona, f-strings innecesarios).
- Criterio: `pytest` limpio en CI, sin efectos de red/escritura en collection; lockfile de dependencias.

**F5. Higiene de UI del producto público:**
- Unificar idioma en **español** con tildes correctas (el dashboard actual mezcla inglés/español y le faltan acentos: "Ano", "comparacion"). Importa en un producto donde vendes confianza.

---

## 8. Secuencia de ejecución recomendada

| Fase | Bloque | Por qué en este orden |
|---|---|---|
| 1 | **A** (seguridad) | Riesgo activo de cookies/sesiones en el historial. No espera a nada. |
| 2 | **B** (reparar mobile.de) | Sin datos no funciona nada, ni interno ni público. |
| 3 | **C** (motor fiscal) | Base de los dos productos; sin números correctos el producto público hace daño. |
| 4 | **D** (calculadora pública) | El producto que genera negocio. Se apoya en C. |
| 5 | **E** (desacoplar + persistencia) | Arquitectura sana para ambas caras; resuelve serverless. |
| 6 | **F** (endurecer + calidad) | En paralelo desde el principio donde se pueda; cierre de calidad. |

---

## 9. Recordatorios finales para Cursor

- **No borres** el opportunity finder ni su lógica (scoring, break-even, comparables, dashboard interno, CLI de comparación). Es un activo y posible producto futuro (sección de chollos para clientes, o producto para otros importadores). Solo se retira basura y código muerto explícitamente listado (perfil Playwright, artefactos de debug, el `if i >= 2: break`, la implementación Playwright obsoleta del uso activo).
- **No mezcles** el producto público con la jerga interna: el cliente ve precio final y ahorro, nunca margen/arbitraje/score.
- El motor fiscal es **una sola fuente de verdad** compartida; corrígelo sin romper a quien ya lo usa.
- Trabaja **incrementalmente y con tests/fixtures**; no elimines cambios de trabajo existentes.
- Referencia visual y de copy del producto público: `prototipo-calculadora.html` (te lo pasa el usuario). Números del prototipo = de ejemplo; sustitúyelos por el `fiscal_engine` real. El nombre "Trayecto" es provisional.