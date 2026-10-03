# Plan: Rediseño comercial completo del laboratorio de simulaciones

> Created by `plan-mode-trae` skill — Plan Mode of Trae IDE, adapted to Pi.
> Path: this file · Language: español · Created: 2026-10-03

## Summary

Rediseño estructural y visual completo del frontend para que el laboratorio se entienda como un producto serio y comercial: un solo camino de creación en tres grupos humanos (Reglas / Selección / Límites), perfiles de juego visibles, vocabulario único "simulación", resultados que responden primero "¿qué ocurrió?", y complejidad técnica entera plegada en Avanzado. Aplica todo lo encontrado en la crítica Impeccable (18/40; 2 P0, 7 P1, 3 P2, 1 P3) sin dejar hallazgos fuera, conservando backend, contratos, datos históricos y la verdad financiera/auditada.

## Current State Analysis

- **Project**: `analyzer_lotoFlet`, frontend React 18 + TypeScript + Vite + Tailwind en `webapp/frontend`; SPA con rutas en `src/App.tsx` (`/experimentos`, `/experimentos/nuevo`, `/nuevo/sesion`, `/nuevo/perfil`, `/experimentos/:id`, `/comparacion`, `/configuraciones`, `/datos`, `/ajustes`). Backend FastAPI aparte; contratos API sin tocar.
- **Affected area**: `webapp/frontend/src/{App.tsx, components/, pages/, lib/, styles/}` más sus suites `.test.tsx`.
- **Existing patterns**: vocabulario de presentación centralizado en `src/lib/ui-labels.ts` (`FIELD_LABEL_SEED`, `HISTORICAL_CAVEAT`, etc.); estados de carga/error/reintento robustos en todas las páginas; tokens de color/tipografía en `src/styles/tokens.css` (paleta Pi #171e26/#222830/#242f3b/#d0d4d8/#adb5bf/#7eb3da, radio 0, tipografía sans cuerpo + serif títulos); componentes `.btn-*`, `.control`, `.link`, `.data-list`, `.field`; tests Vitest por página con fixtures de API.
- **Constraints (no negociables)**: sin cambios backend/API/payloads/esquemas ni claves internas (`SelectorKind`, `SettlementMode`, semilla requerida por contrato se mantiene); datos históricos/DB solo lectura; identidad visual fijada por el usuario (oscuro, paleta Pi, fuentes actuales, radio 0); verdad financiera y caveats intactos (`HISTORICAL_CAVEAT`, neto ≠ delta, null ≠ 0, versiones/códigos crudos en «Detalles técnicos»); preservar `rng_audit/` y el gitlink eliminado sin tocar.
- **Evidencia de la crítica** (fuente de alcance): 18/40 Nielsen; carga cognitiva 8/8 fallas; `/experimentos/nuevo` = 9 campos, `/nuevo/perfil` = 11 campos (verificado en navegador); perfiles invisibles en render (`data/index.tsx:404–412`, dentro de «Opciones avanzadas» → «Importar CSV o JSON plano»); semilla visible (`lib/ui-labels.ts:47`); `/nuevo/sesion` monta `ProfileBatchPage` con título «Nuevo lote de sesiones» y `/nuevo/perfil` monta `ProfileExperimentPage` con título «Nueva sesión con perfil» (`App.tsx:34–48`) — nombres y funciones cruzados.

## Proposed Changes

### Slice 1 — Vocabulario y navegación por tareas
- **`webapp/frontend/src/lib/ui-labels.ts`**
  - **What**: Unificar lenguaje a «simulación»; quitar del flujo visible «semilla», «liquidación», «escala», «revisión» como etiquetas de campo principales (pasan a rótulos de Avanzado/Detalles técnicos). Mantener `HISTORICAL_CAVEAT` y semánticas.
  - **Why**: P1 vocabulario; heurística 2 y 4 en 2/4.
  - **How**: Renombrar solo strings de presentación (el archivo ya garantiza que no toca enums ni payloads; `Record<Kind,string>` sigue fallando typecheck si falta una entrada). `FIELD_LABEL_SEED` → «Código de repetición (avanzado)»; `FIELD_HELP_SEED` conserva la verdad (0 a 9.007.199.254.740.991) pero solo se muestra dentro de Avanzado, nunca como valor sugerido.
- **`webapp/frontend/src/components/Shell.tsx`**
  - **What**: Navegación por tareas: **Simulaciones · Perfiles de juego · Historiales · Estrategias · Administración**; marca/promise visible bajo «Laboratorio» (una línea: «Simulaciones honestas con datos históricos.»).
  - **Why**: P1 navegación; credibilidad comercial (jerarquía de producto).
  - **How**: Mapear rutas existentes sin romper URLs: Simulaciones→`/experimentos`, Perfiles→`/datos#perfiles` (sección nueva), Historiales→`/datos#historiales`, Estrategias→`/configuraciones`, Administración→`/ajustes`. Conservar skip link, colapso 800px, Escape/foco.
- **`webapp/frontend/src/App.tsx`**
  - **What**: Corregir títulos/cruzamiento de rutas: `/experimentos/nuevo` «Crear simulación»; `/nuevo/sesion` pasa a mostrar el flujo con perfil simple; `/nuevo/perfil` pasa a «Lote de simulaciones»; `/experimentos/:id` «Resultado de la simulación». Ruta desconocida con enlace primario «Ir a Simulaciones».
  - **Why**: P1/P3 de la crítica; los títulos actuales prometen otra cosa.
  - **How**: Cambiar `title` de `Shell` y reasignar componentes o `<Navigate>` de compatibilidad para no romper enlaces guardados; P3 fix del fallback.
- **Tests**: actualizar `App.test.tsx`/`Shell.test.tsx` por títulos/destinos; conservar assertions de accesibilidad y breakpoints.

### Slice 2 — «Crear simulación» en tres grupos (el formulario simple)
- **`webapp/frontend/src/pages/new-experiment/index.tsx`**
  - **What**: Reemplazar el constructor de pasos por un solo formulario visible en tres grupos: **1. Reglas del sorteo** (universo 00–99, posiciones por sorteo, repeticiones permitidas, premios por posición 60/10/5, apuesta mínima RD$1 — prellenados desde el perfil seleccionado y editables), **2. Selección** (método: transición 60% + fríos 40%, cobertura 10 números, con controles comprensibles), **3. Límites** (capital RD$2.000, meta de saldo RD$2.800, máximo 12 sorteos). Un solo primario «Crear simulación». Debajo, **«Ajustes avanzados»** (cerrado) con semilla autogenerada + «Cambiar», liquidación (`SETTLEMENT_LABELS`), minutos históricos y edición de estrategias.
  - **Why**: P0 — hoy es un constructor de experto (9 campos + semilla) y no existe tu formulario de tres grupos.
  - **How**: Conservar orden de teclado y todos los `id`/payloads actuales (semilla sigue en el request: autogenerada con `crypto.getRandomValues` y visible en Avanzado para reproducibilidad); errores por campo con foco y `aria-invalid`; drafts persistidos como hoy. Test-first: RED de «muestra 3 grupos y oculta semilla», GREEN con la reestructura.
- **Tests**: `NewExperimentPage.test.tsx` — conservar payloads/duplicados/no-POST/sin ranking; reemplazar asserts de copy obsoleto; nuevo test de progressive disclosure (Avanzado cerrado, abre sin perder valores).

### Slice 3 — Perfiles de juego visibles
- **`webapp/frontend/src/pages/data/index.tsx`**
  - **What**: Reordenar secciones **Perfiles de juego → Historiales → Importar → Opciones avanzadas**; sacar `ProfileEditor` del desplegable «Importar CSV o JSON plano» (`:404–412`) hacia sección propia con CTA primario «Crear perfil de juego» visible sin abrir nada; si falta perfil para importar, ofrecer crearlo en contexto.
  - **Why**: P0 — causa directa de «no veo dónde se crean los perfiles» (verificado en render).
  - **How**: Mantener preview/promote, hashes SHA-256 plegados y copy «Importar guarda datos, no ejecuta ni calcula pagos»; `fail()` abre el detalle y enfoca el campo.
- **`webapp/frontend/src/pages/data/ProfileEditor.tsx`**
  - **What**: Plantilla completa de Quiniela 80 precargada (00–99, 3 posiciones, premios 60/10/5, apuesta mínima RD$1, escala «sin escala»); ID interno y «revisión» pasan a «Detalles técnicos»; conservar la verdad financiera de multiplicadores (pago total sin devolución adicional de apuesta).
  - **Why**: P0 + minimalismo (12 campos base a la vista).
  - **How**: Defaults del formulario, sin tocar contratos; validaciones por campo y foco existentes intactos.
- **Tests**: `DataPage.test.tsx`, `DataPageHistory.test.tsx`, `ProfileEditor.test.tsx` — RED de «CTA crear perfil visible en estado vacío»; conservar payloads/bytes/hashes/preview/promote.

### Slice 4 — Flujos con perfil y lote, con revelado progresivo
- **`webapp/frontend/src/pages/new-experiment/ProfileExperimentPage.tsx`**
  - **What**: «Simulación con perfil»: resumen de reglas del perfil primero (Reglas / Selección / Límites), perfil y datos como requisitos con acción en contexto; semilla, versiones de esquema y detalles crudos a Avanzado/Detalles técnicos.
  - **Why**: P1 (11 decisiones a la vez) y naming inconsistente.
  - **How**: Mismo patrón de grupos del Slice 2; conservar identidad canónica, hashes, esquemas y guardas de duplicados.
- **`webapp/frontend/src/pages/new-experiment/ProfileBatchPage.tsx`**
  - **What**: «Lote de simulaciones» explícito; definición/selectores internos, semilla y revisiones plegados; mantener el caveat «la validación no reserva capacidad» y la identidad de la estrategia no soportada.
  - **Why**: P0 de coherencia nombre/función + P1 de densidad.
  - **How**: Progressive disclosure sobre el estado actual; sin cambios de API.
- **Tests**: `ProfileExperimentPage.test.tsx`, `ProfileBatchPage.test.tsx` — conservar frozen-request/admission/duplicados; copy assertions retiradas sólo si son puramente de presentación.

### Slice 5 — Resultados que responden primero «¿qué ocurrió?»
- **`webapp/frontend/src/pages/experiments/DetailPage.tsx`**
  - **What**: Abrir con **Desenlace**: saldo final, cambio, neto, motivo y clasificación; luego evolución y apuestas; el resto (ROI, drawdown, parámetros) en «Detalles técnicos» junto a versiones de esquema, hash canónico y categoría de parada cruda.
  - **Why**: P1 — hoy los indicadores compiten antes del resultado.
  - **How**: Reordenar `dt/dd` existentes sin tocar cálculos; `omitNet` y caveats intactos.
- **`webapp/frontend/src/pages/experiments/ComparisonPage.tsx`**
  - **What**: Liderar con saldo final / neto / motivo por corrida; tabla comparativa completa desplegable; mantener definiciones congeladas e identidad por referencia.
  - **Why**: P2 de densidad analítica.
  - **How**: Plegado por sección; sin cambios de métricas ni fórmulas.
- **Tests**: `DetailPage.test.tsx`, `ComparisonPage.test.tsx`, `RunTrajectory.test.tsx` — conservar verdad financiera (neto ≠ delta, null ≠ 0), versiones/códigos/hashes.

### Slice 6 — Cola, Estrategias y Administración
- **`webapp/frontend/src/components/QueueDrawer.tsx`**
  - **What**: Estados en lenguaje humano: «En curso / Esperando / Detenido»; protocolo de reintentos y páginas en «Detalles técnicos».
  - **Why**: P2 — texto de protocolo para usuarios comunes.
- **`webapp/frontend/src/pages/configurations/index.tsx`**
  - **What**: Enmarcar como **biblioteca opcional de estrategias** («Guardá un método para reutilizarlo»), sin «plantilla»; conservar búsqueda/paginado/acciones.
  - **Why**: P2 — herramienta especializada al nivel del flujo principal.
- **`webapp/frontend/src/pages/settings/index.tsx`**
  - **What**: **«Administración del laboratorio»**: Capacidad → Límite → Diagnóstico técnico (plegado) → Acceso para agentes (plegado, secreto oculto).
  - **Why**: P1 — mezcla administración y preferencias.
- **Tests**: `QueueDrawer.test.tsx`, `ConfigurationsPage.test.tsx`, `SettingsPage.test.tsx` — conservar cuota/parsing/foco `#quota-error`, borradores, no-PUT y secreto oculto.

### Slice 7 — Jerarquía visual comercial
- **`webapp/frontend/src/styles/tokens.css` + `index.css`**
  - **What**: Escala tipográfica editorial sobria (H1 32–40px, razón 1.125–1.2), ritmo de espaciado (page-margin/section-gap), una acción primaria visualmente dominante por pantalla, superficies planas, foco 2px, radio 0, reduced-motion conservando cambios de estado; `.link` único ya existente.
  - **Why**: P1 credibilidad comercial + heuristic 8; «serio y comercial» = herramienta financiera sobria (identidad pi.dev ya fijada).
  - **How**: Solo tokens y clases compartidas; sin sombras/gradientes/animaciones nuevas; sin cambio de paleta ni fuentes (decisiones del usuario).
- **Tests**: `src/lib/tokens.test.ts` ampliado si cambian valores medidos; resto de la suite sin cambios funcionales.

### Slice 8 — Adapt, harden, audit y cierre
- **What**: Barrido final: errores en lenguaje plano con recuperación, empty states que enseñan la siguiente acción en todas las páginas (P1 vacíos), tablet/coarse-pointer 44px, zoom 200%, foco/teclado, orden de encabezados h1→h2→h3 sin saltos; luego `detect.mjs`, auditoría de contraste y corrida Playwright de solo lectura con fixtures.
  - **Why**: Cierra P1 de vacíos, banderas de personas (Jordan/Sam/Casey) y la verificación pendiente.
  - **How**: Sin servidor real ni POSTs; fixtures `/api/v1/**` GET.

## Assumptions & Decisions

1. **Un solo camino principal de creación** («Crear simulación»): el ejemplo del usuario (Reglas/Selección/Límites) es la especificación de la forma. Las capacidades existentes (lote de sesiones, estrategias guardadas, edición experta) **no se eliminan**: quedan como entradas secundarias o dentro de Avanzado.
2. **Semilla**: sigue existiendo porque el contrato la requiere; se autogenera, se explica en Avanzado y **nunca** se muestra el máximo legal como valor sugerido.
3. **Identidad visual fijada**: oscuro, paleta Pi actual, cuerpo sans + títulos serif (cursiva coherente), radio 0, `sm: 640px` + `nav: 800px` + `wide: 1100px`. «Comercial» = sobriedad de herramienta financiera, no marketing, no mono en mayúsculas, no tema claro.
4. **URLs existentes se conservan** (con redirecciones/títulos corregidos) para no romper enlaces guardados ni bookmarks del usuario.
5. **Vocabulario único**: «simulación» para el artefacto; «perfil de juego» para las reglas del sorteo; «historial» para datos importados; «estrategia» solo para métodos guardados. Se retiran «sesión» y «lote» del copy visible.
6. **Pruebas**: test-first donde hay conducta determinista (CTA de perfil visible, grupos del formulario, Avanzado cerrado, orden de desenlace). Se conservan todas las salvaguardas funcionales (finanzas, payloads, admisión, duplicados, foco, borradores, secretos); se retiran solo aserciones puramente de copy obsoleto, dejando constancia.
7. **Entrega por unidades** (el plan supera 400 líneas cambiadas): 8 slices = 8 unidades de trabajo con tests y docs junto al comportamiento, commits convencionales en `stage`, revisión nativa por unidad según RDD. Si un slice supera ~400 líneas autorizadas se encadena en sub-unidades, no se comprime código.
8. **No se cambian** backend, esquemas, claves internas, `rng_audit/`, datos históricos, ni el gitlink eliminado.

## Entrega por fases (mapeo Impeccable)

| Slice | Comandos Impeccable | Criterio de cierre |
| --- | --- | --- |
| 1 Vocabulario/nav | `clarify`, `layout` | Una sola voz; rutas y títulos coherentes |
| 2 Formulario simple | `shape`, `distill`, `clarify` | 3 grupos visibles, semilla en Avanzado, 1 primario |
| 3 Perfiles visibles | `onboard`, `layout` | CTA visible sin desplegables; plantilla Quiniela |
| 4 Perfil/lote | `distill`, `clarify`, `harden` | ≤4 decisiones visibles por pantalla |
| 5 Resultados | `distill`, `typeset` | «¿qué ocurrió?» primero; métricas plegadas |
| 6 Cola/Estrategias/Admin | `clarify`, `layout` | Administración separada; protocolo plegado |
| 7 Jerarquía visual | `polish`, `typeset` | Look sobrio comercial; sin deuda visual |
| 8 Cierre | `adapt`, `harden`, `audit`, `critique` | Tablet/zoom/foco OK; detector y auditoría limpios |

## Verification

- [ ] Por slice: `cd webapp/frontend && npm run test -- --run <suites afectadas> --maxWorkers=1` y `npm run typecheck` (exit 0 observado, con counts).
- [ ] Final: `npm run test -- --run --maxWorkers=1` (suite completa; hoy base 485/485 — el conteo puede crecer con tests nuevos; nunca disminuir salvaguardas), `npm run typecheck`, `npm run build`.
- [ ] `git diff --check -- webapp/frontend` (exit 0; solo advertencias EOL conocidas).
- [ ] Detector: `node "C:/Users/luism/.pi/agent/skills/impeccable/scripts/detect.mjs" --json webapp/frontend/src` → 0 hallazgos.
- [ ] Playwright de solo lectura con fixtures `/api/v1/**` (sin backend real, sin POST): `/experimentos`, `/datos`, `/experimentos/nuevo`, `/experimentos/nuevo/perfil`, `/configuraciones`, `/ajustes` — evidencia: ≤4 decisiones visibles por grupo, semilla fuera del flujo principal, CTA «Crear perfil de juego» visible, sin overflow horizontal en 768×1024 / 1024×768 / 1280×800, controles ≥44px con `any-pointer: coarse`, foco visible, zoom 200% sin corte.
- [ ] Aceptación manual del usuario (quien hace las pruebas manuales en modo rápido): recorrido completo «crear perfil → importar historial → crear simulación → ver resultado» en menos de 5 minutos sin ayuda.
- [ ] Contratos: diffs de código sin cambios en `webapp/backend`, `api/types`, ni payloads enviados (verificación por diff review por slice).

## Out of Scope

- Backend, esquemas API, claves internas, motores, bases de datos e históricos (`rng_audit/`, sesiones, perfiles guardados).
- Tema claro, cambio de paleta/fuentes, mono en mayúsculas, animaciones decorativas, sitio de marketing.
- Cambios de semántica financiera (fórmulas, redondeos, neto/delta) y caveats de riesgo.
- El gitlink eliminado `lottery-predictability-monte-carlo` y cualquier cambio ajeno del worktree.
- Capacidades nuevas de predicción/rentabilidad: la promesa sigue siendo **simulación honesta, no predicción**.
