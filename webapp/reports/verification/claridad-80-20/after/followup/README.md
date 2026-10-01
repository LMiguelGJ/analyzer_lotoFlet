# CI04 — recheck visual tras corrección de tabla

**Resultado acotado:** **PASS** del defecto original («Estrategias» y fecha fragmentadas a 390 px); **FAIL visual parcial** del conjunto por nuevo recorte local de «Acciones» a 1280 px. No se alteraron fuentes, tests, configuración, tracker, capturas anteriores ni directorio de datos base. El fallo inicial `assistant reported an error` no trae una causa técnica verificable en esta evidencia; se conservaron los artefactos parciales, se comprobó el proceso propio y se continuó sin relanzar servidor. Un intento de opción `--raw` de `playwright-cli` devolvió `unknown '--raw' option`; se usó `run-code` normal, pero no se atribuye ese error CLI al fallo inicial de sesión.

## Procedencia

Se reutilizó el servidor propio ya activo en `127.0.0.1:8791` sobre **copia** `OS_TEMP/ci-80-20-harness/followup-data`, creada recursivamente desde `OS_TEMP/ci-80-20-harness/data` cuando el puerto estaba libre (1 archivo). El directorio base quedó sin POST ni borrado. La copia tenía 0 plantillas al consultar la API. Un POST público a `/api/v1/configurations`, con `Origin` local de mismo origen, creó **una** plantilla sintética: «Plantilla frío conservadora» (objeto de biblioteca) y estrategia distinta «Fríos plano» (`selector=system`, `system=cold`, `coverage=20`, `staking=flat`; ID de copia en `fixture-provenance.json`). Una primera solicitud sin `Origin` fue rechazada **403** sin mutación; luego la creación fue **201** y GET confirmó 1 plantilla. Los experimentos existentes son los dos de la copia, sin modificaciones. Esta nueva muestra de biblioteca **no es pareja de datos idéntica** a `before/` ni dato real del usuario; `before/library-1280.png` era de hecho una pantalla vacía, pese a su README descriptivo.

Assets recompilados desde el frontend actual con Vite 7.3.6; Chromium headless vía `playwright-cli` (sin navegador MCP nativo disponible). PID Python real **34916**, ejecutable `<python-install>/python.exe` (identidad absoluta comprobada/redactada), comando `-B -m laboratorio.app`, launcher 42360. Antes de cerrar se reconfirmaron nombre, ruta, comando y propiedad del listener `127.0.0.1:8791`. Se detuvo **solo PID 34916** y se observó PID ausente y **0 listeners** en 8791 (`runtime.json`). Browser propio `ci04followup` cerrado; no se tocó ningún proceso ajeno.

## Mediciones del DOM real (`matrix.json`)

Método: viewport `ancho × 900`, `documentElement.clientWidth/scrollWidth`; región `[role=region].data-table-region` `clientWidth/scrollWidth`; `<table>` ancho; `getComputedStyle(...).whiteSpace`; recuento de líneas mediante rectángulos de nodos de texto en Chromium. No es un resultado jsdom. Capturas `experiments-{390,1280}.png`, `comparison-{390,1280}.png`, `library-{390,1280}.png` y estados enfocados/editor draft adicionales.

| Ancho | Documento client/scroll | Experimentos región client/scroll | Comparación región client/scroll | «Estrategias» / fecha / nombre largo |
|---:|---:|---:|---:|---|
| 390 | 390/390 | 332/1075 | 332/1037 | 1 / 1 / 2 líneas |
| 799 | 799/799 | 741/1075 | 741/1037 | 1 / 1 / 2 líneas |
| 1100 | 1100/1100 | 832/1075 | 832/1037 | 1 / 1 / 2 líneas |
| 1280 | 1280/1280 | 1012/1075 | 1012/1037 | 1 / 1 / 2 líneas |

El encabezado «Estrategias» tiene `white-space: nowrap`, una sola línea y ancho ~117 px en los cuatro anchos. La fecha real «30 sept de 2026, 03:43 p. m. GMT-4» usa `nowrap`, una sola línea y columna ~251 px. El nombre largo completo sigue en el texto del enlace y ocupa dos líneas naturales en celda ~384 px; a 390 px se alcanza el resto con scroll horizontal **local**, no del documento. La tabla de comparación comparte el componente `DataTable`; sus seis encabezados tienen una línea y su scroll también está confinado. El gráfico fue excluido de este juicio y no se tocó. Biblioteca poblada no usa `DataTable`: renderiza filas `.saved-strategy-row`, una visible, sin overflow documental a esos cuatro anchos.

**Teclado:** la región «Experimentos» es nombrada y `tabIndex=0`. A 390 px, foco en región con `scrollLeft=0`; ArrowRight llevó a **40 px**; Tab enfocó botón «Nombre» con outline sólido; foco del botón «Acciones de Prueba base 80-20» llevó scroll a **743 px** y el botón quedó completamente dentro de la región. Enter abrió menú nombrado y enfocó «Usar como base»; Escape cerró y devolvió foco a «Acciones» (`keyboard-table.json`). A 1280 px, el contenido mide 1075 frente a 1012: **63 px de scroll local**. ArrowRight dos veces alcanzó 63/63 y dejó «Acciones» íntegramente visible (`table-action-reach.json`). Con foco directo sobre «Acciones» tras un solo ArrowRight, el scroll quedó en 40/63 y el botón permaneció **parcialmente recortado**, aunque operable con Enter y retorno de foco correcto (`experiments-1280-action-focused.png`).

**Biblioteca poblada:** `library-390.png`/`library-1280.png` muestran la plantilla API real de la copia. Editor «Nueva estrategia guardada» abierto sin guardar (`library-draft-390.png`, `library-draft-1280.png`), luego «Cancelar edición» lo cerró y permaneció una plantilla. «Eliminar Plantilla frío conservadora» abrió `alertdialog` con nombre y consecuencia; foco inicial «Cancelar»; Escape devolvió foco al disparador. Se volvió a abrir y «Cancelar» también devolvió foco; GET final conservó total 1 (`library-interactions.json`). No se ejecutó DELETE ni se guardó el draft. El botón Guardar aparece habilitado en draft vacío; no se probó envío/validación ni se afirma defecto funcional por eso.

## Hallazgos de esta muestra

- **P2 — nuevo recorte local a 1280 px, comprobado:** `experiments-1280.png` muestra encabezado y botones «Acciones» cortados en el borde derecho; la tabla min-content mide 1075 px dentro de una región de 1012 px. Es scroll local, no overflow documental; con dos ArrowRight o navegación de foco puede alcanzarse íntegramente. Impacto: descubribilidad/lectura de la acción a ancho de escritorio. Fuente probable: `DataTable.tsx` (`min-w-max`) + mínimos semánticos en `styles/index.css`/columnas en `pages/experiments/index.tsx`; no se adjudica cuál regla individual basta sin experimento causal. La corrección del encabezado móvil es real, pero el recheck visual global no se declara limpio.
- **P2 — biblioteca poblada a 1280 px, causalidad no establecida:** `library-1280.png` muestra valores «Fríos plano» y «Un sistema de selección» envueltos en una columna muy angosta a pesar del ancho disponible. Impacto: lectura más lenta. Biblioteca no usa `DataTable` y la captura anterior estaba vacía; no afirmar que lo introdujo esta corrección. No se arregló.
- No se atribuyen como nuevas las cadenas `circle`/`square` del gráfico ni el ID de error de mezcla preexistente. Sin claims de conformidad WCAG.

## Verificaciones y límites

- `npm run build` desde `webapp/frontend`: **OK**, 59 módulos; CSS 18,00 kB y JS 357,44 kB. El `dist/` ignorado no es fuente.
- Detector Impeccable **una vez en este seguimiento posterior a cambio de CSS**: `node "<impeccable-skill>/scripts/detect.mjs" --json webapp/frontend/src` → exit **0**, `[]` (`detector.json`). Los manifiestos de 57 archivos fuente antes y después (`source-before.json`, `source-after.json`) coinciden exactamente: 0 ediciones durante este recheck, incluida la ejecución del detector. Es una nueva ejecución respecto de la auditoría anterior, no un rerun repetitivo aquí.
- Writer/parent informaron **281/281**, typecheck/build; **no se reejecutaron tests ni suite** en esta tarea. Se inspeccionó el diff acotado de `DataTable.tsx`, `pages/experiments/index.tsx` y `styles/index.css`, sin editarlo.
- Zoom **real** 200 % sigue pendiente manual: ni viewport ni CSS transform ni page scale se consideran equivalentes. Aceptación humana de CI04 también pendiente. Sin prueba en dispositivo físico, lector de pantalla ni todos los estados de error.

## Key Learnings

1. El cambio min-content soluciona el quiebre de header/fecha a 390 px y preserva scroll local, pero puede empujar «Acciones» fuera de vista incluso a 1280 px.
2. Una región de tabla con nombre y Tab permite recuperar columnas por teclado; eso no elimina un problema de descubribilidad visual.
3. La biblioteca no comparte `DataTable`; su fila poblada debe evaluarse por separado y una captura vacía previa no demuestra causalidad.
4. Una copia del dato temporal y un único POST API permiten mostrar la biblioteca sin contaminar la base.
5. El detector limpio y 57 hashes idénticos no sustituyen la observación visual ni la aceptación del usuario.
