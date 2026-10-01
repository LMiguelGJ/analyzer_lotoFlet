# CI04 — evidencia «después» y auditoría acotada

**Fecha:** 2026-09-30, ~21:01–21:11 UTC. **Alcance:** solo observación del frontend compilado en Chromium headless; sin cambios de fuente, fixtures base, contratos ni aceptación de producto. No es certificación WCAG. El navegador MCP nativo no estaba disponible en este runtime; se usó `playwright-cli` 1.59.0-alpha-1771104257000 (Chromium). Node v24.14.0, npm 11.9.0, Python 3.14.3, Vite 7.3.6. `context.mjs` no se volvió a ejecutar.

## Procedencia y comparabilidad

Servidor local propio `127.0.0.1:8791`, arrancado desde `webapp/backend` con `py -3 -B -m laboratorio.app`, `LABORATORIO_DATA_DIR=%LOCALAPPDATA%/Temp/ci-80-20-harness/data`; assets actuales tras `npm run build`. PID real Python **36732**, nombre `python.exe`, ejecutable `<python-install>/python.exe` (ruta absoluta verificada y redactada), comando `-B -m laboratorio.app`, listener 8791 comprobado; identidad reconfirmada antes de detener **solo ese PID**; 0 listeners al cierre (`runtime.json`). El launcher fue PID 6688. No se usaron datos personales ni se enviaron formularios.

La API real `GET /api/v1/experiments?offset=0&limit=20` devolvió dos experimentos completados: `96225a72d61e4b5da1288ecb1eeec451` = **«Prueba base 80-20»** (2 ejecuciones) y `258b22f841714c23b13eceb1c3b2003e` = nombre largo (1 ejecución). `GET /api/v1/configurations?offset=0&limit=20` devolvió **0 plantillas** (`fixture-observed.json`). **Discrepancia con before/README.md:** allí se describe «Captura línea base 80-20» y una plantilla «Plantilla frío conservadora»; estos valores *no* coinciden con la API actual. Por ello listado/detalle/comparación son comparables por tipo de estado, pero no pareja de datos idénticos; biblioteca actual vacía **no** es pareja equivalente a la captura anterior con plantilla. No se reescribió evidencia histórica ni se sembró/mutó la base. Otra errata descriptiva previa: before/README.md llama es-DO al formato de ajustes, pero la implementación anterior usaba **es-AR**; el formato actual es-DO. Esa afirmación previa no prueba una regresión de valores.

Los 20 nombres `<superficie>-<1280|390>.png` coinciden con `before/`: experiments, experiments-empty, wizard-conditions, wizard-strategies, detail, comparison, library, settings, queue-drawer y not-found. `experiments-empty` usa **solo un mock aislado de GET** `/api/v1/experiments?*` que devuelve página vacía; **no es el estado real de la base** ni antes/después con idéntica técnica (CI00 usó base recién creada). `not-found` es la **respuesta 404 JSON real del backend** al navegar directamente `/ruta-que-no-existe`, tal como la captura previa; no demuestra la vista interna del React Router. La cola se abrió con datos reales y sin trabajos activos. Adicionales, no pareados: `wizard-review-1280.png` (formulario válido, sin enviar), `experiments-filtered-1280.png` (filtro real sin coincidencias), `experiments-error-injected-1280.png` (GET 503 sintético), `experiments-loading-injected-1280.png` (GET demorado artificialmente). El GET se desregistró tras cada inyección. No se trata de incidentes reales. Los 24 PNG pesan **1.312.052 bytes** en total (<10 MB); lista/tamaño/SHA-256 en `evidence-inventory.json`.

## Matriz observada

| Superficie / rutas | 390 | 799 | 1100 | 1280 | Estado |
|---|---|---|---|---|---|
| `/experimentos` | sin overflow documental | idem | idem | idem | 2 filas reales; filtro sin coincidencias real; vacío/503/carga por GET aislado |
| `/experimentos/nuevo` | sin overflow documental | idem | idem | idem | Condiciones y Estrategias con formulario sin enviar; Revisar válido capturado a 1280 |
| `/experimentos/:id` | sin overflow documental | idem | idem | idem | detalle real completado, 2 ejecuciones |
| `/experimentos/:id/comparacion` | sin overflow documental | idem | idem | idem | comparación real 2/2, gráfica excluida del juicio de overflow |
| `/configuraciones` | sin overflow documental | idem | idem | idem | vacío real, **no pareado** con plantilla de CI00 |
| `/ajustes` | sin overflow documental | idem | idem | idem | éxito lectura, controles no guardados |

Método: Chromium viewport de altura 900 px y ancho indicado, `document.documentElement.scrollWidth > clientWidth + 2` para overflow de documento; los 24 valores `scrollWidth == clientWidth` están en `responsive.json`. Tablas con scroll propio, SVG y gráficos **excluidos** de esta conclusión; no se infiere que todo contenido local sea legible sin scroll. Las 20 capturas pareadas usan `fullPage`. Estados observables: cargando, error con «Reintentar», vacío mock, filtro vacío real, éxito con filas, botones «Anterior/Siguiente» deshabilitados y resumen de Revisar. No se probó error en otras rutas, permisos/read-only, red lenta real, nombres largos de *todos* los campos ni guardado/cancelación de trabajos en curso.

**Contraste muestreado** (`contrast.json`): colores computados en Chromium y primer fondo ancestral opaco; sRGB linealizado y razón `(L_mayor + .05)/(L_menor + .05)`. En nuevo experimento: body `rgb(208,212,216)` sobre `rgb(23,30,38)` **11,27:1**; título 11,27:1; texto de botón primario `rgb(23,30,38)` sobre `rgb(126,179,218)` **7,48:1**; ayuda `rgb(173,181,191)` sobre fondo 8,11:1; etiqueta 11,27:1; texto del input enfocado sobre `rgb(36,47,59)` 9,12:1 y contorno enfocado `rgb(126,179,218)` sobre ese fondo **6,05:1**. Es muestreo de estados/elementos, no auditoría completa ni composición alfa de todos los fondos.

**Teclado/foco:** se abrió menú de acciones del experimento real, «Eliminar» mostró `alertdialog` con nombre y consecuencia; **no se confirmó**. Foco inicial en «Cancelar», Tab → «Eliminar experimento» con outline sólido, Shift+Tab → «Cancelar», Escape cerró y devolvió foco a «Acciones» (`dialog-keyboard.json`). Cola abierta por Enter desde botón «Cola» y Escape volvió foco a ese botón (`queue-help.json`); el cajón no apareció como `[role=dialog]` en esa inspección, por lo que no se afirma semántica modal ni trampa de foco. Seis controles con `aria-describedby` muestreados en Condiciones: los seis IDs referencian nodos existentes. No se recorrió íntegramente el árbol accesible ni se midió uso con lector de pantalla.

**Zoom real al 200 %:** **pendiente manual**; no había mecanismo de zoom de navegador verificable en esta automatización. No se usó viewport, CSS transform ni CDP page scale como sustituto.

## Hallazgos y límites de causalidad

1. **P2, regresión visual candidata introducida:** a 390 px, el encabezado «Estrategias» de la tabla de experimentos se parte en tres líneas (`experiments-390.png`), mientras el anterior «Configuraciones» cabía en una línea (`before/experiments-390.png`). Impacto: escaneo menos rápido de la columna; el scroll sigue localizado y no causa overflow del documento. Reproducción: abrir `/experimentos` a 390 px con dos filas y observar encabezado. Fuente probable: nuevo texto de encabezado + ancho/estilo de columna en `webapp/frontend/src/pages/experiments/index.tsx`, `components/DataTable.tsx` o `styles/index.css`; causalidad del cambio de ancho exacta **no verificada**. Propuesta para el padre, no arreglo en CI04.
2. **Preexistente / fuera del alcance:** leyenda del gráfico de comparación muestra `circle` y `square` crudos; ya se había identificado en CI01 y el archivo del gráfico está excluido del plan. No atribuirlo a CI04/CI02.
3. **Preexistente / fuera del alcance:** referencia `…blend.system.error` sin elemento ID en error específico del editor de mezcla, confirmada previamente en HEAD según tracker; no se reprodujo ese error de mezcla en este recorrido, así que no se presenta como hallazgo nuevo.
4. **Preexistente:** navegación directa a ruta inexistente devuelve JSON 404 del servidor (capturas antes/después iguales), sin probar la pantalla React de ruta desconocida. No atribuir al cambio de interfaz.

No se observaron otros defectos nuevos verificables en esta muestra. Ausencia de hallazgo no demuestra ausencia de defectos.

## Verificación técnica y límites de cierre

- `npm run build` desde `webapp/frontend`: **OK**, 59 módulos, assets CSS 17,66 kB y JS 357,28 kB. `dist/` ignorado; no se editaron fuentes.
- `node "<impeccable-skill>/scripts/detect.mjs" --json webapp/frontend/src` (ruta local redactada; ejecución exacta en el handoff): **una ejecución**, salida `[]`, exit **0**, **0 hallazgos / reglas / rutas** (`detector.json`). Detector limpio ≠ validación visual.
- `git diff --check` desde raíz: **exit 0**, advertencias de conversión futura LF→CRLF en archivos previamente modificados, sin error de whitespace.
- Manifiesto SHA-256 de **57 archivos** bajo `webapp/frontend/src` antes y después: diccionarios idénticos, **0 cambios** (`source-manifest-before.json`, `source-manifest-after.json`). No se tocó el gitlink eliminado preexistente.
- CI01–CI03: **279 pruebas independientes** y typecheck reportados por el tracker/padre; **no reejecutados** en esta tarea. No atribuir ese total a CI04.
- `wizard-review-1280.png` se capturó recién después de completar nombre de estrategia y sistema, sin «Agregar a la cola». Una primera tentativa inválida mostró errores en Estrategias; la captura final fue reemplazada con la vista Revisar real.
- Aceptación explícita del usuario sobre claridad/textos: **pendiente**. CI04 **no debe marcarse cerrada** por este informe.

## Key Learnings

1. El harness conservado tiene dos experimentos, pero su API actual no coincide íntegramente con la descripción de CI00; consultar IDs/nombres reales antes de capturar.
2. Biblioteca vacía en API invalida la comparación visual pareada de esa superficie, aunque el nombre del PNG coincida.
3. Vacío, carga y 503 pueden observarse sin mutar fixtures mediante GET aislado, siempre rotulados como inyección.
4. El overflow global fue nulo en 24 combinaciones, pero no equivale a legibilidad de tablas/gráficos locales.
5. El zoom real 200 % y la aprobación humana siguen siendo gates distintos de build, detector y capturas headless.
