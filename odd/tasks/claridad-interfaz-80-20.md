# Claridad de interfaz 80/20 — plan ODD

## Objetivo y autorización

Mejorar textos, ayudas breves y jerarquía visual de todas las interfaces existentes del laboratorio, sin cambiar recorridos, capacidades ni reglas. Plan fuente: [`.pi/plans/claridad-interfaz-80-20.md`](../../.pi/plans/claridad-interfaz-80-20.md). **Aplicación autorizada por el usuario el 2026-09-30: «aplica el plan ahora tal cual con odd».**

La autorización cubre cambios de frontend, pruebas y verificación descritos en el plan. **No autoriza commit, push ni PR**; esa entrega requiere autorización Git separada. Preservar la eliminación preexistente de `lottery-predictability-monte-carlo` sin stage ni restauración.

## Problema y porqué

La revisión Impeccable (25/40 heurístico, no prueba con usuarios) encontró que la interfaz exige traducir términos del motor: `system`, «Delta», «Semilla compartida», «Liquidación», «Completado» junto a «Límite de sesión», cuotas en bytes. El usuario eligió un 80/20: claridad transversal sin reorganizar recorridos.

## Alcance (resumen de A1–T1 aprobados)

- **A1–A2:** seis pantallas, navegación, cola y diálogos; mismos recorridos, pasos y acciones.
- **F1–F6:** lenguaje cotidiano consistente, valores internos traducidos, ayuda breve, ejecución ≠ desenlace, advertencia histórica próxima a resultados, estados y confirmaciones específicos.
- **U1–U3:** conservar paleta/identidad, legibilidad y jerarquía de acciones, contenido largo/accesibilidad, formatos sin alterar valores ni tiempo.
- **L1–L4:** sin cambios en cálculos, defaults, validaciones, habilitación, datos, métricas, gráficos, narrativas ni funciones nuevas.
- **V1–V3:** pruebas pertinentes, navegador, foco/teclado/contraste/anchos/zoom real 200 %, aprobación del usuario.
- **T1:** ODD, no SDD.

Glosario de presentación y decisiones 1–14: ver plan fuente, sección «Decisiones de presentación». Son vinculantes para los escritores.

## Uso obligatorio de Impeccable

**Solicitado por el usuario (2026-09-30):** usar la skill Impeccable (`<impeccable-skill>/SKILL.md`) cada vez que una tarea toque interfaz, para guiar la manera correcta de hacerlo.

- Todo escritor de CI01–CI03 carga `SKILL.md`, `reference/operate.md`, la referencia del comando que corresponde a su trabajo y `reference/craft-floor.md` inmediatamente antes de editar UI.
- Referencias por tipo de trabajo: textos, etiquetas y mensajes → `reference/clarify.md`; tipografía → `reference/typeset.md`; espaciado y jerarquía → `reference/layout.md`; estados vacíos/carga/error → `reference/harden.md`; anchos y contenido largo → `reference/adapt.md`; pasada final → `reference/polish.md`.
- CI04 usa `reference/audit.md` y el detector `scripts/detect.mjs`; una crítica final con `reference/critique.md` compara contra la línea base 25/40.
- `context.mjs` ya se ejecutó en esta sesión (sin PRODUCT.md/DESIGN.md): no volver a ejecutarlo; tratar la implementación actual como autoridad visual (refinamiento, no rediseño).
- Impeccable guía el cómo, **no amplía el alcance**: sus sugerencias fuera de A1–L4 se registran como propuestas y se consultan con el usuario.

## Dirección visual (usuario, 2026-09-30)

Interfaz **profesional de herramienta de análisis/investigación**, con menos ruido visual y que **no parezca generada por IA**. La claridad debe venir de la estructura, no de sumar texto.

- **Estructura antes que texto:** agrupar campos relacionados, usar grillas que aprovechen el ancho disponible, bloques de dato (etiqueta + valor) para métricas y parámetros, encabezados de sección claros. Una frase de ayuda solo si la estructura no alcanza.
- **Menos ruido:** menos bordes y separadores repetidos, menos cajas dentro de cajas, un solo énfasis por zona, texto secundario realmente secundario, monoespaciada solo para datos técnicos.
- **Componentes con propósito:** se permite cambiar la *presentación* de un control o bloque (p. ej. campos en dos columnas, resumen como lista de datos compacta, parámetros como pares etiqueta/valor, estado como distintivo) **si conserva los mismos datos, acciones, pasos, validaciones y comportamiento**. No agrega funciones, rutas ni pasos.
- **Sin señales de IA:** prohibidos gradientes decorativos, glassmorphism, emojis, iconos genéricos de relleno, tarjetas idénticas repetidas sin jerarquía, textos de marketing y sombras llamativas. Aplicar las prohibiciones absolutas de `reference/craft-floor.md`.
- **Referente de nicho:** herramientas profesionales de datos y análisis cuantitativo: densidad legible, alineación numérica, jerarquía sobria. Se conservan paleta, tipografía de títulos e identidad actuales (U1).
- Esta dirección precisa U1/U2; **no** anula L1–L4: sigue excluido el rediseño completo de identidad, cambios en gráficos, métricas nuevas y reorganización del asistente.

## Tareas

| ID | Unidad | Estado |
|---|---|---|
| CI00 | Captura «antes» y línea base técnica | completada |
| CI01 | Vocabulario y base visual compartida | completada |
| CI02 | Asistente y resultados comprensibles | completada |
| CI03 | Listado, biblioteca, ajustes y superficies compartidas | completada |
| CI04 | Verificación transversal y aceptación del usuario | completada con límites de evidencia documentados; sin aprobación nativa |

### CI00 — Captura «antes» y línea base

- [x] Registrar `git status` y ausencia de cambios de aplicación previos.
- [x] Ejecutar línea base frontend: `npm run test -- --run`, `npm run typecheck`, `npm run build` (desde `webapp/frontend`). Registrar resultados observados.
- [x] Capturas «antes» de las seis rutas con datos aislados, anchos 1280 y 390, si el navegador está disponible. Si no, registrar el límite.
- Evidencia: [before/README.md](../../webapp/reports/verification/claridad-80-20/before/README.md). 251/251 pruebas (24 archivos), typecheck 0 errores, build OK. 20 PNG (10 superficies × 1280/390), ~1,3 MB, datos sintéticos aislados en `%TEMP%/ci-80-20-harness` (puerto 8791), conservados para CI04. Servidor propio detenido con verificación de identidad. Capturas headless: no miden zoom real.

### CI01 — Vocabulario y base visual compartida

- [x] `src/lib/ui-labels.ts` + `src/lib/ui-labels.test.ts` (nuevos): mapas de selector, modalidad y liquidación.
- [x] `src/components/StatusLabel.tsx` + test: etiquetas precisas, vocabularios separados intactos.
- [x] `src/styles/index.css`: clases compartidas control/etiqueta/ayuda/botón primario/secundario/destructivo; sin afectar SVG/gráficos.
- [x] `src/lib/tokens.test.ts`: conservar/ampliar aserciones; `tokens.css` sin cambios de valores.
- Aceptación: pruebas afectadas verdes, sin cambios de lógica.
- Evidencia (writer `muoit852-i-du37`): 267/267 pruebas (25 archivos), typecheck 0, build OK. `completed` → «Ejecución completada»; literales actualizados en `ExperimentsPage.test.tsx` y `ComparisonPage.test.tsx`. Clases nuevas: `.field`, `.field-label`, `.field-help`, `.control`, `.btn`/`-primary`/`-secondary`/`-destructive`, `.section-header`, `.data-list`(+`-numeric`), `.status-badge`, todavía sin adoptar en páginas. Spot check del padre: `ui-labels.test.ts` + `StatusLabel.test.tsx` 25/25; diff 131+/8− en superficies permitidas.
- Pendiente de unificación en CI02/CI03: liquidación con tres redacciones distintas (asistente, detalle, plan) y dos calificativos históricos (detalle, comparación).
- **Propuesta para decisión del usuario (no implementada):** la leyenda de `ComparisonChart.tsx` expone `circle`/`square` crudos (choca con F1), pero el plan excluye ese archivo (L2). Se consulta en CI04.

### CI02 — Asistente y resultados

- [x] `StrategyEditor.tsx` + test.
- [x] `pages/new-experiment/index.tsx` + `NewExperimentPage.test.tsx`.
- [x] `pages/experiments/DetailPage.tsx` + test.
- [x] `pages/experiments/ComparisonPage.tsx` + test (sin tocar `ComparisonChart.tsx`).
- Aceptación: mismos payloads, pasos y validaciones; delta desde API; null sigue ausente; N/M conservado.

### CI03 — Listado, biblioteca, ajustes y compartidos

- [x] `pages/experiments/index.tsx` + `ExperimentsPage.test.tsx`.
- [x] `pages/configurations/index.tsx` + `ConfigurationsPage.test.tsx`.
- [x] `pages/settings/index.tsx` + `SettingsPage.test.tsx` (BigInt, entrada ASCII y contratos intactos; presentación es-DO).
- [x] `components/Shell.tsx`, `QueueDrawer.tsx`, `ConfirmDialog.tsx`, `DataTable.tsx`, `App.tsx` + sus tests.
- Aceptación: vocabulario/estilo coherente; regresiones de cola, borrado y ajustes verdes.

### CI04 — Verificación y aceptación

- [x] Suite frontend final 282/282, typecheck y diff-check independientes; build y detector OK del writer, no reejecutados por verificador.
- [x] Diff de backend, gráficos, modelo, API, tokens y formato vacío; cuatro hashes finales coinciden con evidencia.
- [x] Navegador: muestreo documentado de estados, teclado/foco, cuatro anchos y contraste; correcciones tabla/biblioteca comprobadas. No certificación exhaustiva. Zoom real 200 % no medido y retirado del requisito por el usuario.
- [x] Capturas «después» archivadas con límites de comparabilidad: biblioteca poblada en copia aislada, no pareja idéntica CI00; 404 directo no acredita vista React.
- [x] **Aprobación del usuario de textos y claridad visual:** «no hay zoom todo eso esta bien ya». Se retira el zoom real al 200 % como requisito de cierre por decisión del usuario; no se presenta como prueba realizada.

## Progreso y evidencia

- 2026-09-30: plan aprobado; tracker y espejo Engram creados antes del primer cambio de aplicación.
- 2026-09-30: CI00 delegado (`muoidmka-h-clzg`). El usuario agregó el uso obligatorio de Impeccable en cada tarea de interfaz y la dirección visual profesional.
- 2026-09-30: CI00 completada; el padre verificó estado Git, listado de evidencia y la captura de detalle.
- 2026-09-30: CI01 completada y verificada por el padre; CI02 delegada.

## Historial de verificación CI02

CI02 requirió corrección acotada antes de CI03. Recuperación writer `muojp9ot-k-excb`: 271/271, typecheck/build/diff-check OK; strict TDD no activo, no afirmar RED/GREEN. Padre repitió editor/detalle 18/18. Verificador `muojwnsj-l-um6v`: 271/271 y typecheck/diff-check OK, sin diff en gráficos/model/API/backend/tokens/formato, pero aceptación técnica de CI02 pendiente por:

1. Ayudas nuevas de semilla/apuesta no asociadas al control: agregar IDs estables y combinar ayuda+error en aria-describedby, conservando errores; comprobar descripción accesible en tests.
2. Ayuda de semilla perdió rango 0–9.007.199.254.740.991 y uso compartido por sorteo: restaurar información junto a explicación comprensible, sin modificar validación.
3. Resumen y bloques todavía usan Par/impar/Mezcla/Azar y Configuración/Configuraciones: aplicar mapas y Estrategia/Estrategias según plan, sin cambiar payload/IDs.
4. Agrupación cambió posición de semilla en orden Tab: restaurar secuencia original de campos en DOM, mantener grilla compatible, sin tabindex positivo ni reordenamiento CSS que contradiga DOM.

LSP previo: sin errores, hint returnValue obsoleto y avisos del corrector inglés sobre español. ASSESS nativo unassessable por untracked sin declarar; no aprobación nativa. Corrección writer `muok2hay-m-f35d`: reportó cuatro hallazgos corregidos con tests de descripción accesible ayuda+error, rango de semilla, vocabulario y orden DOM. 275/275 tests, typecheck/build/diff-check OK y diff prohibido vacío. Padre repitió StrategyEditor + ui-labels: 20/20. Reverificación independiente `muokgsv3-n-8l86`: PASS de las cuatro correcciones, 62/62 tests en cuatro archivos, typecheck/diff-check OK, diff prohibido vacío. CI02 completada técnicamente. Navegador/contraste/zoom y aceptación del usuario siguen pendientes CI04.

Residual preexistente comprobado también en HEAD: error exclusivo del sistema de mezcla referencia `…system.error` sin ID en su párrafo (StrategyEditor). Fuera del gate de nuevas ayudas; no corregido sin decisión del usuario. No se afirma ausencia global de referencias colgantes.

## Historial de verificación CI03–CI04

Las menciones pendientes siguientes corresponden al momento de cada intento; el cierre vigente figura al final.

CI03 writer `muoklrf6-o-axkn`: 279/279 tests, typecheck/build/diff-check OK. Padre SettingsPage + QueueDrawer56/56. Verificación independiente `muol46et-p-k4bl`: PASS acotado,279/279/typecheck/diff-check, sin regresión nueva bloqueante, límites prohibidos intactos. Conserva cuotaBigInt/ASCII, handlers/foco/guardas/cola ytestsconductuales. Observación menor no bloqueante: botón Guardar estrategia de objeto plantilla; revisar claridad enCI04sin ampliar funcionalidad.

CI04 auditoría `muol9glr-q-9ex7`: 24 PNG + JSON/README en after/, build/detector0/diff-check OK;57fuentes idénticas antes/después, proceso propio detenido. Muestra24combinaciones de6rutas×4anchos sinoverflowdocumental(no prueba legibilidad local), contrastebody11,27/primario7,48/ayuda8,11/foco6,05; diálogoEliminar ycolaEscape retornanfoco. No nueva suiteenestaauditoría.

Pendientes CI04:
- Corrección tabla por `muolthu9-r-g3et`: min-width según contenido y wrapping por semántica, sin reordenar columnas ni cambiar datos/handlers. Writer281/281/typecheck/build/diff-check; primer intento testfallópor rutaCSS luego corregido. Padre DataTable+Experiments27/27. Verificación técnica independiente `muom23do-t-jhjk`: PASS45/45/typecheck/diff-check, sin cambios semánticos ni gráficos. Recheck navegador `muom22rc-s-eoid` falló con assistant reported an error, sin conclusión visual; usuario pidió continuar. Recuperación de la misma tarea `muomq6os-u-4xai` en curso, conservando evidencia parcial, primero comprobando procesos propios y sin cambios de fuente. Todavía no cierre visual.
- BibliotecaAPIactualvacía: after no es par válido con before que tenía plantilla. Obtener evidencia con fixtureaislado rotulado sin alterarbaseharness ni reescribirbefore. READMEbefore contiene discrepancias nombreexperimento/esDO; after lasdocumenta sin atribuirautoría causal.
- Captura not-found corresponde404JSONbackend, no rutaReact; no arreglarbackend, documentar cobertura.
- Zoomreal200% y aceptaciónhumana pendientes. ASSESSunassessableuntracked, noaprobaciónnativa.
Seguimiento visual recuperado `muomq6os-u-4xai`: PASS encabezado/fecha390, FAIL parcialAcciones1280recortadas63px (tabla1075/región1012); biblioteca con fixtureAPIencopiaTEMP muestra valoresmuyestrechos, causalidadnoestablecida.10PNG/JSON after/followup,57fuentesintactas, propioPID34916detenido. No sobrescribir evidencia.

Corrección de distribución `muomz8y8-v-uofz`: completada con una iteración+navegador; retirado min-w-max, biblioteca una columna conaccionesdebajo. Writer282/282/typecheck/build/detector[]/diff-check. Experimentos1280región/tabla1012/1012Accionesvisible,390scrolllocaldocumentosinoverflow; comparaciónybiblioteca comprobadas4anchos. Evidencia after/layout-final/12PNG+matrix+hashes. Proceso propio cerrado; único404faviconpreexistente. PadretestsDataTable+Library17/17.

Crítica finalA `muonkzyj-w-r5it`: sin nuevo defectoobjetivograveenalcance; heurístico28/40vs25/40noexperimentocontrolado. Su párrafo deparidadbiblioteca es contradictorio(poblada/vacía); no usarlo como evidenciadedatos, fuentesmatrix/PNGpriman. Intentoparalelofinal devolviósinsalida ylistconfirmósóloAcreado; Verificador B `muoojs70-1-0vk5` falló con `assistant reported an error`, sin informe final: no atribuirle PASS. Recuperación `muooqdl6-2-f04h`: PASS técnico final. Primera ejecución 281/282 por timeout de NewExperimentPage.test.tsx; única repetición282/282 y25/25archivos exit0. Conservar ambos resultados, causa del timeout no determinada. Typecheck/diff-check OK, diff prohibido vacío,4SHA256 iguales al README layout-final. No build/detector/browser nuevos del verificador.

NativeINSPECTfinal: detenido en intended_untracked_selection_required; no START/lineage/aprobación. Proyección también incluye gitlink ajeno; no alterarlo. Sin commit/push autorizado.

### Decisión vigente del usuario

«no hay zoom todo eso esta bien ya»: aceptación visual recibida y comprobación de zoom real al 200 % retirada del requisito de cierre. No afirmar que se midió. Sustituye las menciones históricas de aceptación/zoom pendientes; no concede aprobación nativa ni autorización de commit/push.

## Estado vigente y próximo paso

CI00–CI04 completadas funcionalmente, con aprobación visual del usuario y PASS técnico independiente final. Se conservan límites de muestreo, el timeout transitorio y defectos preexistentes fuera del alcance. La revisión nativa NO se completó: sigue detenida por selección untracked, sin lineage ni aprobación. No presentar el cierre ODD como aprobación nativa.

No hay implementación pendiente dentro del alcance. Entrega Git autorizada por el usuario: commit `1441337` publicado en `origin/stage` (141 archivos). Rutas personales redactadas antes del commit. Gitlink `lottery-predictability-monte-carlo` eliminado ajeno, sin stage.
