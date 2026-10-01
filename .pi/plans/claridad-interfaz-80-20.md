# Plan: claridad UX/UI 80/20 del laboratorio

> Plan Mode — planificación para implementación posterior con ODD, no SDD.
> Estado: listo para aprobación; NO autoriza todavía cambios de aplicación.
> Idioma: español. Único archivo creado durante esta planificación: este plan.

## Summary

Mejorar textos, ayudas breves y jerarquía visual de todas las interfaces existentes sin modificar recorridos, capacidades ni reglas del laboratorio. Conservar su identidad y comprobar claridad en navegador; el cierre depende de aprobación humana, no solo de pruebas automáticas.

## Current State Analysis

Exploración de solo lectura: scout leyó íntegramente `webapp/frontend/src/styles/tokens.css`, `src/lib/format.ts`, `package.json`, `src/pages/new-experiment/index.tsx` y `src/components/StrategyEditor.tsx`; el coordinador contrastó editor compartido, estilos y formato de ajustes.

- Frontend React/TypeScript/Vite, estilos Tailwind y tokens propios. Scripts existentes: `test` (vitest), `typecheck` (tsc --noEmit), `build` (vite build), `dev` (vite), `preview` (vite preview).
- Rutas en `webapp/frontend/src/App.tsx`: listado `/experimentos`, asistente `/experimentos/nuevo`, detalle `/experimentos/:id`, comparación `/experimentos/:id/comparacion`, biblioteca `/configuraciones`, ajustes `/ajustes` y estado de ruta inexistente.
- El asistente mantiene tres pasos: Condiciones, Estrategias, Revisar. `StrategyEditor.tsx` se comparte con la biblioteca. No contiene reglas financieras.
- `StatusLabel.tsx` distingue ejecución de desenlace. Esa separación se conserva y se aclara en etiquetas/contexto.
- Identidad: fondo #171e26, superficie #222830, campo #242f3b, acento #7eb3da; heading Georgia/serif, body system-ui y mono para datos técnicos. Controles actuales de 42px y radio de 4px. `styles/index.css` contiene foco visible y enlace para saltar al contenido.
- `lib/format.ts` define `formatDOP` con es-DO, importes enteros sin decimales y rechazo de fracciones; `formatTwoDigit` mantiene números 00–99. Se conservan ambos contratos.
- Ajustes usa string/BigInt para cuota int64 y formato es-AR. No convertir la cuota a Number. Los valores físicos son números de API y no se deben presentar como nuevos datos exactos.
- Hay pruebas existentes para rutas/componentes, formato y tokens. Los totales históricos no equivalen a una ejecución nueva.
- Git observado: rama `stage`, única modificación preexistente: eliminación de gitlink `lottery-predictability-monte-carlo`. No tocar, restaurar ni incluir esa eliminación.

## Assumptions & Decisions

### Alcance aprobado para planificar

- A1–A2: seis pantallas, navegación, cola y diálogos; mismos recorridos, pasos y acciones.
- F1–F6: lenguaje cotidiano consistente, valores traducidos, ayuda breve, ejecución distinta de desenlace, advertencia histórica próxima, estados y confirmaciones claros.
- U1–U3: conservar identidad/paleta, mejorar legibilidad/jerarquía, contenido largo y accesibilidad, formatos sin alterar valores ni tiempo.
- L1–L4: no cálculos, defaults, validaciones, habilitación, datos, métricas, gráficos, narrativas personalizadas ni funciones nuevas.
- V1–V3: pruebas pertinentes, navegador, foco/teclado/contraste/anchos/zoom real 200%, aceptación del usuario y límites explícitos de evidencia.
- T1: ODD, no SDD. Este plan es la referencia de alcance; no abrir otro ciclo de especificación para repetir decisiones resueltas.

### Decisiones de presentación

1. Mantener «Experimentos» como nombre del objeto y su navegación. Usar «simulación histórica» para explicar qué hace; no renombrar rutas.
2. Usar «Estrategias guardadas» para la biblioteca. Dentro de un experimento, «Estrategia 1», etc. Distinguir el nombre de la plantilla del nombre de la estrategia cuando ambos ya existan; no fusionar campos ni entidades.
3. Mapa exclusivamente visual: `system` → «Un sistema de selección»; `blend` → «Combinación de sistemas»; `random` → «Selección al azar reproducible»; `parity` → «Selección por paridad (par/impar)». Mantener los nombres de sistemas del catálogo, sin inventar descripciones científicas.
4. Conservar «Plana», «Escalera» y «Audaz» como nombres de modalidades y las explicaciones respaldadas por la implementación. No prometer seguridad, recuperación ni ventaja. Aclarar el campo como «Forma de ajustar la apuesta»; no inferir fórmulas nuevas.
5. Liquidación: «Cómo contar los premios», opciones «Sumar los premios» y «Contar solo el mayor premio por número». Conservar valores `all`/`best` y reglas.
6. «Semilla compartida» → «Código para repetir el azar (semilla)», con ayuda breve indicando que el mismo código permite repetir la selección aleatoria con las mismas condiciones. Sigue siendo el mismo campo requerido, sin generación ni defaults nuevos.
7. «Delta» → «Cambio respecto del inicio», ayuda «Diferencia entre el saldo final y el capital inicial». Mostrar exclusivamente `result.delta` recibido, sin restar en frontend.
8. Estado `completed`: etiqueta «Ejecución completada»; el motivo de cierre se presenta separado. No inferir meta alcanzada desde el estado general ni narrar dinámicamente resultados.
9. Advertencia estática junto al resumen/tabla: «Simulación con datos históricos: no predice resultados futuros ni garantiza rentabilidad». Conservar también la calificación existente sobre datos ya investigados y falta de validación independiente; no debilitarla al mover textos.
10. Reutilizar body system-ui para etiquetas, inputs, botones y ayuda; mantener serif de títulos, paleta, radios y alturas mínimas. Monoespaciada para IDs, hashes y códigos donde aporte. No cambiar tipografía global de gráficos por cascada.
11. Acción primaria mediante estilos compartidos, peso/borde/relleno y posición actual; secundarios delineados o enlaces según patrón existente. Destructivos inequívocos por texto y estilo, nunca solo color. No añadir ni reordenar acciones de flujo ni modificar disabled/handlers.
12. Locale de presentación numérica es-DO para ajustes, preservando BigInt y unidades exactas. Fallback de agrupación consistente; valores editables continúan como decimal ASCII sin separadores. Fechas: conservar comportamiento temporal actual y cadenas históricas sin introducir conversiones; no normalizar zonas horarias ni parsers. Mantener formato DOP y gráficos intactos.
13. Ayudas breves asociadas programáticamente al campo cuando se agreguen; conservar asociaciones de errores. Si se descubre un defecto funcional previo, registrarlo aparte en vez de arreglar lógica fuera de alcance.
14. No iniciar installs, migraciones ni servidores sobre datos reales durante validación. Los datos de muestra se aíslan y las inyecciones de error se rotulan.

## Proposed Changes

Todas las rutas siguientes son relativas a la raíz del repositorio. Tests nuevos se identifican explícitamente; los demás archivos existen.

### Unidad 1 — Vocabulario y base visual compartida

- **Nuevo `webapp/frontend/src/lib/ui-labels.ts` y nuevo `src/lib/ui-labels.test.ts`:** mapas tipados de etiquetas de selector, modalidad y liquidación para eliminar enums crudos y duplicaciones. Solo constantes/formato de presentación, sin cálculo ni lógica de dominio. Verificar correspondencia completa de valores conocidos.
- **`webapp/frontend/src/components/StatusLabel.tsx` y `StatusLabel.test.tsx`:** precisar etiquetas conservando vocabularios, iconos, roles y distinción de estado/desenlace. Preservar tratamiento actual de valores desconocidos.
- **`webapp/frontend/src/styles/index.css`:** clases compartidas y explícitas de control/etiqueta/ayuda/botón primario/secundario/destructivo; conservar foco, skip-link y reduced-motion. Sin selectores globales que alteren SVG o charts.
- **`webapp/frontend/src/lib/tokens.test.ts`:** conservar o ampliar aserciones aplicables; `styles/tokens.css` es referencia, sin cambio de valores de color/tamaño/tipografía base en esta entrega.
- Evidencia: mapas coherentes, estilos compartidos disponibles y pruebas afectadas verdes. La aplicación gradual de clases ocurre en unidades siguientes.

### Unidad 2 — Asistente y resultados comprensibles

- **`webapp/frontend/src/components/StrategyEditor.tsx` + `StrategyEditor.test.tsx`:** consumir mapas, aplicar body/estilos compartidos, aclarar etiquetas y ayudas sin modificar onChange, catálogo, cobertura, componentes, pesos, validación ni límites.
- **`webapp/frontend/src/pages/new-experiment/index.tsx` + `NewExperimentPage.test.tsx`:** aplicar vocabulario y ayudas; diferenciar opcional/requerido según reglas ya existentes; conservar los tres pasos, selección de sorteo, semilla, resumen, salida, guardas y envío. Textos de carga/error/confirmación precisos. No generar resumen narrativo adicional.
- **`webapp/frontend/src/pages/experiments/DetailPage.tsx` + `DetailPage.test.tsx`:** etiqueta de cambio de saldo, distinción ejecución/desenlace, advertencia próxima, traducción de parámetros guardados; controles/tabs/replay intactos.
- **`webapp/frontend/src/pages/experiments/ComparisonPage.tsx` + `ComparisonPage.test.tsx`:** mismas etiquetas/advertencia fuera del gráfico, mantener N/M, valores ausentes «—», paginación y estados. No alterar props, series, algoritmo ni componentes de gráficos.
- Evidencia: mismos payloads y condiciones en tests; casos incompletos no se convierten en cero; captura comparable del asistente y resultados.

### Unidad 3 — Listado, biblioteca, ajustes y superficies compartidas

- **`webapp/frontend/src/pages/experiments/index.tsx` + `ExperimentsPage.test.tsx`:** distinguir vacío/sin coincidencias/error, jerarquía de acción existente y confirmación con nombre/consecuencia; filtros, debounce, orden, paginación y rutas idénticos.
- **`webapp/frontend/src/pages/configurations/index.tsx` + `ConfigurationsPage.test.tsx`:** biblioteca «Estrategias guardadas», mapas en resúmenes, nombres distinguibles, consecuencias de borrar plantilla y búsqueda explícitamente limitada a la página actual. No implementar búsqueda global ni fusionar campos.
- **`webapp/frontend/src/pages/settings/index.tsx` + `SettingsPage.test.tsx`:** claridad entre límite lógico/uso/tamaño físico/disco, etiquetas técnicas acompañadas de ayuda breve y formato es-DO exacto. Conservar input en bytes, MAX_QUOTA, BigInt, validaciones, precedencias, read-only y respuestas API. No nuevos controles ni conversiones con pérdida.
- **`webapp/frontend/src/components/Shell.tsx` + `Shell.test.tsx`:** etiqueta biblioteca coherente, acción de cola reconocible y texto adaptable, sin cambiar rutas/menú/breakpoints ni comportamiento.
- **`webapp/frontend/src/components/QueueDrawer.tsx` + `QueueDrawer.test.tsx`:** mensajes comprensibles para activo/pendiente/retenido/cancelación incierta, confirmaciones y estilos; mostrar únicamente información disponible, sin endpoints para obtener nombres ni estimaciones/progreso inventados.
- **`webapp/frontend/src/components/ConfirmDialog.tsx` + `ConfirmDialog.test.tsx`:** presentación compartida, textos específicos suministrados por consumidores; mantener inert, foco, Escape, roles y handlers.
- **`webapp/frontend/src/components/DataTable.tsx` + `DataTable.test.tsx`:** verificar y ajustar solo estilos para contenido largo y scroll localizado; conservar semántica, columnas y funciones.
- **`webapp/frontend/src/App.tsx` + `App.test.tsx`:** coherencia de títulos/texto del estado inexistente, sin agregar rutas ni acciones nuevas.
- Evidencia: seis rutas y superficies compartidas usan vocabulario/estilo consistente; regresiones de cola, borrado y settings siguen pasando.

### Unidad 4 — Verificación transversal y aceptación

- Sin nuevas funciones ni refactorización general. Correcciones limitadas a textos/estilos/asociaciones de ayuda en los archivos anteriores, con sus tests.
- Ejecutar verificación completa de frontend y detector; inspección activa LSP cuando disponible.
- Recorrido de navegador con datos aislados, capturas antes/después, matriz de estados/anchos y zoom real 200%.
- Presentar evidencia y límites al usuario; no marcar aceptación final hasta su aprobación explícita.
- Actualizar `webapp/README.md` únicamente si las etiquetas/ayudas documentadas quedaron obsoletas; preservar evidencia histórica y no reemplazarla por nuevos números sin ejecución.

## Ejecución ODD posterior a aprobación

1. Releer este plan y git diff/status, preservar cambios ajenos. No replanificar ni pedir de nuevo decisiones cerradas.
2. Antes del primer cambio de aplicación crear `odd/tasks/claridad-interfaz-80-20.md`, espejo Engram `odd/claridad-interfaz-80-20/tasks` y todo reconciliado con las cuatro unidades anteriores. Estos artefactos NO se crean durante plan mode.
3. Un solo writer delegado por unidad; delegaciones con superficies permitidas exactas y checks explícitos. Leer Impeccable `reference/clarify.md` y `reference/craft-floor.md` antes de cambios UI, reutilizar contexto ya cargado y no rerun context.mjs en esta sesión.
4. Capturar antes inicial ANTES del primer source edit; si navegador no está disponible, registrar límite y mantener aceptación pendiente. Datos/runtime de prueba fuera del árbol fuente y nunca sobre experimentos personales.
5. Conservar configuración TDD vigente; comprobar su modo al ejecutar, no inferirlo por existencia de pruebas. Actualizar pruebas con cada cambio; no borrar aserciones de comportamiento para acomodar etiquetas nuevas.
6. Estimar diff por unidad. La extensión transversal puede superar400líneas; dividir en unidades revisables, no crear una PR gigante. No abrir PRs encadenadas automáticamente.
7. Commits/push/PR no autorizados por este pedido de plan. La autorización anterior correspondía a otra entrega; solicitar autorización Git separada cuando corresponda. No incorporar gitlink eliminado preexistente.
8. Ejecutar revisión nativa al completar candidato si el switch RDD sigue habilitado, mediante inspect y continuaciones exactas. Respetar consentimiento y reportar bloqueos; no afirmar aprobación solo por tests.
9. Registrar evidencia real tras cada unidad. Unidad4 permanece pendiente de aprobación humana aunque checks técnicos pasen.

## Verification

### Comandos a ejecutar después de implementar (no ejecutados para este plan)

Desde `webapp/frontend`:

```sh
npm run test -- --run
npm run typecheck
npm run build
```

Por unidad, filtrar Vitest a los archivos de prueba enumerados con `npm run test -- --run <rutas-de-tests>` y comprobar consumidores de componentes compartidos. Suite completa al final.

Desde raíz:

```sh
node "<impeccable-skill>/scripts/detect.mjs" --json webapp/frontend/src
git diff --check
```

Detector exit0=sin hallazgos; exit2=hallazgos a evaluar, no prueba de fallo funcional ni certificación UX. No instalar dependencias ni ejecutar fixes automáticos. No hay script lint frontend inventado. Backend sin cambios: comprobar diff excluido; si aparece necesidad de modificar backend, detener esa expansión y consultar.

### Regresiones obligatorias

- [ ] Mapas de etiquetas completos, mismas claves internas, sin enums sin traducir en vistas ordinarias.
- [ ] Misma secuencia del asistente, defaults, campos, validación y payload; no cálculo financiero en frontend.
- [ ] Estado de ejecución y motivo separados; delta mostrado desde API; null continúa ausente y comparación incompleta conserva denominador.
- [ ] Settings conserva valores int64 exactos, formato BigInt y entrada ASCII; contrato 409/read-only/cuota intacto. `lib/format.test.ts` y `lib/tokens.test.ts` incluidos en regresión.
- [ ] Borrado, cancelación, solicitud incierta, guardas de navegación y foco mantienen comportamiento.
- [ ] Sin cambios en `BalanceChart.tsx`, `ComparisonChart.tsx`, backend, migraciones, API contracts, model de validación, fixtures históricos o datos congelados.

### Matriz de navegador

Para las seis rutas y sus superficies aplicables:

| Caso | Comprobación |
|---|---|
| Normal | Misma tarea/acción, etiqueta comprensible, principal distinguible sin depender solo de color |
| Vacío y filtro vacío | No confundir falta de contenido con consulta fallida; sin nuevas acciones |
| Carga/error/éxito/deshabilitado | Texto específico, no falsas garantías; datos previos/solicitudes inciertas preservados |
| Destructivo | Objeto y consecuencia explícitos; Escape/cancelar/confirmar y retorno de foco |
| Contenido largo | Nombres permitidos, IDs y hashes completos accesibles, mensajes largos, sin solapamientos |
| Teclado | Tab/ShiftTab, Enter/Espacio, Escape y navegación existente de tabs; foco visible/no atrapado accidentalmente |
| Responsive | 390px,799px,1100px,1280px; preservar breakpoints y scroll de tablas; documentar diferencias |
| Zoom | Zoom de navegador real200% en escritorio, no emulación porviewport/transform; si no se puede automatizar pedir validación manual y dejar pendiente |
| Contraste | Medir estilos nuevos/modificados en render real; mínimo4.5:1texto normal,3:1texto grande e indicadores funcionales pertinentes; sin claimWCAGtotal |

- Capturas antes/después con mismo viewport, estado y datos representativos. Etiquetar fixtures/errores inyectados; no presentarlos como incidentes reales.
- Solo procesos de prueba propios, identificados y detenidos al finalizar; no cerrar servidor/browser del usuario ni matar árboles ajenos.
- Verifier read-only no puede crear fixtures/levantar servidores: si hace falta preparación, delegar únicamente infraestructura temporal de validación con autoridad acotada después de aprobar; revisión independiente posterior.
- Guardar evidencia útil sin perfiles, bases, caches ni dependencias en Git. Definir destino durable con tracker de ejecución; no crear durante planificación.

### Aceptación de producto

- [ ] El usuario revisa presentación/textos de las seis pantallas y superficies compartidas.
- [ ] Confirma que se entiende qué configura, qué significa el cambio de saldo y que completado no implica meta alcanzada.
- [ ] Se explicitan checks fallidos, omitidos y pendientes; no cerrar por evidencia histórica.

## Out of Scope

Motor, cálculos, reglas de estrategia, defaults, validaciones, condiciones de habilitación, persistencia y datos. Nuevas métricas/narrativas/gráficos, ejes, búsqueda global, borradores, backup/restore, exportación, instalación, importación, controles de unidades, generación de semillas, paneles desplegables nuevos, rediseño de identidad, nuevas rutas y reorganización del asistente. No SDD, nuevas dependencias ni publicación automática.

## Approval Gate

Fase1 completada mediante exploración real; fase2 resuelta con las decisiones ya tomadas, sin preguntas nuevas; fase3 este plan. Fase4 pendiente: solicitar aprobación explícita antes de crear tracker ODD o cambiar código. Ninguna fase omitida; implementación y pruebas todavía no ejecutadas.
