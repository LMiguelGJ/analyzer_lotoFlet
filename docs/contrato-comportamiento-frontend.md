# Contrato de comportamiento de la suite de pruebas del frontend

Documento de extracción: codifica el conocimiento que hoy viven en `webapp/frontend/src/**/*.test.{ts,tsx}` para poder reescribir la suite sin perderlo. Describe COMPORTAMIENTOS, no código de prueba.

## Supuestos
- [A1] Las reglas se derivan solo de lo que los tests afirman; no se verificó el código fuente ni se ejecutó la suite.
- [A2] Cuando varios tests cubren la misma regla con variantes (`it.each`), se registra una sola regla con sus variantes.
- [A3] «Riesgo si se pierde» = daño si la regla deja de verificarse: alto (pérdida de datos/dinero/seguridad/verdad al usuario o contrato con backend), medio (UX/accesibilidad), bajo (cosmético).
- [A4] Las cadenas en español exactas se marcan como copy frágil y se resumen al final.
- [A5] Completitud sobre brevedad.

## Áreas
F-API · F-UI · F-SHELL · F-CREATE · F-RESULT · F-LIST · F-UTIL

---

## 1. F-API — Cliente HTTP y contrato de tipos

### [F-API-001] Mapeo de errores HTTP a ApiError
- **Regla**: Cualquier respuesta no-2xx (400, 403, 404, 409, 422, 507) se convierte en `ApiError` con el `status` y el `detail` del cuerpo.
- **Fuente**: src/api/client.test.ts:maps HTTP %i to an ApiError with that status and detail
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-002] Fallback a statusText sin detail
- **Regla**: Si el cuerpo de error no es JSON o no trae `detail`, `ApiError.detail` usa el `statusText` de la respuesta.
- **Fuente**: src/api/client.test.ts:falls back to the status text when the error body has no detail
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-003] Fallo de red es NetworkError y nunca afirma que el servidor se detuvo
- **Regla**: Un rechazo de `fetch` produce `NetworkError`, cuyo mensaje no afirma que el servidor «se detuvo/stopped» (la causa es incierta).
- **Fuente**: src/api/client.test.ts:maps a fetch rejection to NetworkError, never claiming the server stopped
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-004] Desconexión marcada por el proxy es NetworkError
- **Regla**: Una respuesta 502 con la cabecera `X-Laboratorio-Backend-Unreachable: 1` se trata como `NetworkError`, no como `ApiError`.
- **Fuente**: src/api/client.test.ts:maps a proxy-marked disconnection response to NetworkError instead of ApiError
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-005] Éxito devuelve el JSON parseado; 204 devuelve undefined
- **Regla**: Una 2xx resuelve con el cuerpo JSON; una 204 No Content resuelve `undefined`.
- **Fuente**: src/api/client.test.ts:resolves with the parsed JSON body on success / resolves with undefined on a 204 No Content
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-006] 2xx con cuerpo no-JSON es ApiError tipado
- **Regla**: Una 2xx cuyo cuerpo no es JSON se mapea a `ApiError`, nunca a un `SyntaxError` crudo.
- **Fuente**: src/api/client.test.ts:maps a 2xx response with a non-JSON body to a typed ApiError
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-007] 422 de FastAPI: detail en array → fieldErrors y mensaje genérico en español
- **Regla**: Un 422 con `detail` como array expone `fieldErrors` (`type`, `loc`, `msg`) tal cual y un `detail` genérico en español que no filtra `loc/msg/type`. Con `detail` string, `fieldErrors` es `null` y `detail` se conserva.
- **Fuente**: src/api/client.test.ts:parses a FastAPI 422 array detail… / still supports a plain string detail
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-API-008] URLs same-origin relativas bajo /api/v1
- **Regla**: Todas las peticiones usan URLs relativas same-origin bajo `/api/v1` (p. ej. `/api/v1/catalog`).
- **Fuente**: src/api/client.test.ts:requests same-origin relative URLs under /api/v1
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-009] Codificación de ids reservados en la ruta
- **Regla**: Los ids con caracteres reservados (`a/b c`) se codifican con `encodeURIComponent` en la ruta (experimento, trayectoria, acciones de cola, lookup por client-request).
- **Fuente**: src/api/client.test.ts:encodes a path id that contains reserved URL characters / requests a bounded whole-run trajectory… / encodes queue action IDs…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-010] Trayectoria acotada con max_points
- **Regla**: `getTrajectory(id, run, max)` pide `/experiments/{id}/runs/{n}/trajectory?max_points=N`; la respuesta incluye `total`, `points` y `reduction_method`.
- **Fuente**: src/api/client.test.ts:requests a bounded whole-run trajectory with an encoded identifier
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-011] Lecturas paginadas de perfiles y datasets solo por GET
- **Regla**: `getProfiles`/`getDatasets` usan `offset=0&limit=20` por defecto, aceptan offset/limit, y son lecturas sin `method` (GET). El catálogo de perfiles incluye plantillas parciales con `known_fields`/`missing_fields`.
- **Fuente**: src/api/client.test.ts:reads bounded profiles and partial template metadata… / reads bounded inert datasets through GET only
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-012] Sorteos de inicio: sin fecha compatible, con fecha codificada
- **Regla**: `getStartingDraws` sin filtro de fecha no añade `date`; con fecha lo agrega al final; `getStartingDrawAvailability` consulta `/catalog/starting-draws/availability?date=`. Todo GET.
- **Fuente**: src/api/client.test.ts:keeps unfiltered starting draws compatible and encodes dated pagination…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-013] Filtros de listado de experimentos codificados en servidor
- **Regla**: `listExperiments` serializa offset, limit, `name_contains`, `status`, `sort`, `order` como query-string URL-encoded (espacios `+`, `&`→`%26`, `%`→`%25`, Unicode UTF-8) sin interpretar el texto.
- **Fuente**: src/api/client.test.ts:encodes server-side experiment filters, ordering and bounded offset…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-014] Borrado exige confirm_id igual al recurso
- **Regla**: `deleteExperiment(id, confirm)` envía cuerpo `{ confirm_id }` atado al recurso objetivo.
- **Fuente**: src/api/client.test.ts:sends confirm_id tied to the target resource on delete
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-015] Registro de perfil: POST único, confía en digest/readiness del servidor, errores 409/422
- **Regla**: `registerProfile` hace un `POST /catalog/profiles` con el perfil completo como cuerpo; el cliente confía en el `profile_sha256` y `profile_execution` del servidor; 409 (conflicto de versión, cuota insuficiente) y 422 se propagan como `ApiError` con su status.
- **Fuente**: src/api/client.test.ts:registers a complete profile once and trusts the server response digest/readiness
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-016] Ajustes: GET vista completa y PUT con cuota como string exacto
- **Regla**: `getSettings` lee `/settings`; `updateSettings` hace PUT con `Content-Type: application/json` y cuerpo `{"quota_bytes":"<string>"}`; los bytes enormes (9223372036854775807) se mantienen como string sin pérdida de precisión.
- **Fuente**: src/api/client.test.ts:GET and PUT settings use the full view, exact string payload…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-017] Acciones de cola: POST sin cuerpo y solo acuses
- **Regla**: `startHeld` y `cancelJob` son `POST` sin cuerpo a `/queue/{id}/start|cancel` y devuelven solo el acuse `{id,status}` (`queued`, `cancellation_requested`).
- **Fuente**: src/api/client.test.ts:encodes queue action IDs, sends POST without a body…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-018] Importación de historial canónico: bytes originales del Blob + cabeceras exactas
- **Regla**: Preview y promote de historial envían el Blob original (no `JSON.stringify` del Blob) con cabeceras `X-Profile-Id`, `X-Profile-Revision`, `X-Profile-Sha256`, `X-Confirm-Source`, `X-Confirm-Timezone`; promote añade `X-Expected-Dataset-Sha256`.
- **Fuente**: src/api/client.test.ts:uploads canonical history as original Blob bytes…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-019] Importación genérica: mismo envelope en preview y promote ligada a hash
- **Regla**: `previewImport` y `promoteImport` hacen POST a `/imports/preview|promote` con el mismo envelope explícito (raw_base64, format, mapping, source, clock, profile); promote suma `expected_dataset_sha256`.
- **Fuente**: src/api/client.test.ts:submits the same explicit import envelope to preview and hash-bound promotion
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-020] Creación de experimento de perfil: documento exacto sin envelope legado (schemas 1, 3, 4)
- **Regla**: `createProfileExperiment` hace POST a `/experiments/profiles` con el documento tal cual. Schema 1 usa `flat-per-number/v1` con `per_number_stake`; schema 3 (Audaz, `profile-audaz/v1`) no contiene `per_number_stake`; schema 4 (recuperación) lleva `target_margin`, `rounds`, `end_mode` explícitos.
- **Fuente**: src/api/client.test.ts:posts an exact profile request document… / posts schema-3 Audaz… / posts schema-4 recovery…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-021] Identidad verificada de dataset y sorteos paginados
- **Regla**: `getDataset(sha)` y `getDatasetDraws(sha, offset, limit, date)` usan `/datasets/{sha}` y `/datasets/{sha}/draws?offset&limit&date`.
- **Fuente**: src/api/client.test.ts:fetches verified dataset identity and paged draw labels with date encoding
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-022] Rutas cerradas de lotes v1 con identidad de cliente
- **Regla**: validar, crear y recuperar lotes usan `/profile-batches/validate`, `/profile-batches` y `/profile-batches/by-client-request/{client_request_id codificado}`; el cuerpo es el mismo objeto (schema_version 1, profile, dataset, strategies con `definition_sha256`, conditions, max_draws, client_request_id). Validar no crea reserva.
- **Fuente**: src/api/client.test.ts:uses the closed v1 batch routes and exact client identity…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-023] Lectura de estrategias, compatibilidad de perfil, revisiones y política
- **Regla**: `listProfileBatchStrategies` (offset/limit 0/20), `getProfileBatchStrategy` (con `profile_id/profile_revision/profile_sha256` en query), `getProfileBatchStrategyRevisions`, `getProfileBatchExecutionPolicy` (`/execution-policy`) y `createProfileBatchStrategy` (POST `/strategies`) usan esas rutas exactas.
- **Fuente**: src/api/client.test.ts:reads strategies, exact profile compatibility, revisions and policy…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-024] Credencial de agente por POST same-origin con cuerpo vacío y sin Authorization
- **Regla**: `getAgentCredential` hace POST a `/settings/agent-credential` con cuerpo `{}`, `Content-Type` JSON y sin cabecera `Authorization`.
- **Fuente**: src/api/client.test.ts:retrieves the actual agent credential by same-origin POST…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-025] Discriminadores de perfil vs legado (isProfile*)
- **Regla**: `isProfileExperiment/Run/Replay/Comparison` distinguen perfil de legado por marcadores (`request_kind`, `result_kind`); el legado los omite. Los resultados de perfil no llevan `kind`, y los replays de perfil usan `stakes` en vez de `per_number`.
- **Fuente**: src/api/types.contract.test.ts:discriminates profile detail, comparison, run and replay…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-026] Schema 2 (escalera cíclica) sin stake plano ni discriminador v1
- **Regla**: Para `schema_version 2`, `staking` es `{schema_version:1, capability:"q80-first-prize-cycling/v1"}` sin `per_number_stake`; el resultado lleva `schema_version 2` y no `kind`; el replay lleva `schema_version 2`.
- **Fuente**: src/api/types.contract.test.ts:narrows cycling requests without inventing a flat stake…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-027] Schemas 3 y 4 tipados en request, resultado, comparación y replay
- **Regla**: Audaz (schema 3) no tiene stake fijo; recuperación (schema 4) con `end_mode` `cycle` o `stop` expone `target_margin`/`rounds`; ambos propagan `schema_version` a resultado y replay.
- **Fuente**: src/api/types.contract.test.ts:types schema-3 Audaz… / types schema-4 recovery… (cycle, stop)
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-028] Compatibilidad con fixtures capturados (detalle y replay legados)
- **Regla**: Los fixtures reales (`experiment-detail.json`, `replay.json`) coinciden con los tipos; el detalle legado no tiene `profile`; el resultado usa `bets_count/wagered/paid/final_balance/delta` (no `bets_placed`, ni `bets`); la apuesta de replay usa `label/per_number/wagered/results/paid/balance` (no `drawn_at/amount_per_number/total_spent/drawn_numbers/payout`).
- **Fuente**: src/api/types.contract.test.ts:matches the parsed fixture… / matches the projected experiment detail run result… / matches the real replay bet shape…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-029] Ajustes: campos históricos más componentes exactos de admisión
- **Regla**: `SettingsView` conserva los campos históricos del fixture; los bytes exactos son strings (`*_exact`); `logical_used_bytes_exact + profile_artifact_bytes_exact == admission_logical_bytes_exact` (BigInt); no existe `adjustment_persistence`.
- **Fuente**: src/api/types.contract.test.ts:keeps historical settings fixture fields and adds exact admission components
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-API-030] Datasets descubiertos son metadata inerte
- **Regla**: `DatasetListing` expone `execution_supported:false` y `clock {mode, zone}`, y no incluye bytes crudos ni JSON canónico.
- **Fuente**: src/api/types.contract.test.ts:types metadata-only dataset discovery without implying execution support
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-API-031] Snapshot legado exacto de perfil y catálogo con plantillas no ejecutables
- **Regla**: El perfil legado tiene multiplicadores racionales `{numerator, denominator}`; el catálogo marca perfiles registrados `execution_supported:true` y todas las plantillas `false`, con `missing_fields` (p. ej. `maximum_stake`).
- **Fuente**: src/api/types.contract.test.ts:types the exact legacy snapshot and keeps older captured fixtures compatible
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

---

## 2. F-UI — Primitivas, tokens, contraste y formato

### [F-UI-001] Block es un bloque plano con regla fina; borde superior opcional
- **Regla**: `Block` renderiza una región con clase `ledger-block` (hairline); `border="top"` añade `ledger-block-top-rule`, que por defecto no existe.
- **Fuente**: src/components/ui/ui.test.tsx:renders a flat document block… / supports top-rule blocks…
- **Categoría**: contrato
- **Riesgo si se pierde**: bajo

### [F-UI-002] SectionHeader: título serif con número de secuencia decorativo y kicker
- **Regla**: `SectionHeader` renderiza un `h2` con el título; el número (`"02 "`) va en un `span aria-hidden`; el kicker lleva clase `ledger-kicker`.
- **Fuente**: src/components/ui/ui.test.tsx:supports top-rule blocks and serif section headers…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-UI-003] Money formatea pesos dominicanos y usa clases tabulares mono
- **Regla**: `Money amount={2800}` muestra `RD$2.800` con clases `ledger-figure`, alineación (`ledger-figure-right`) y variante semántica (`ledger-money-positive`).
- **Fuente**: src/components/ui/ui.test.tsx:formats Dominican pesos and uses mono tabular figure classes
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-UI-004] Figure y Stat: variantes semánticas y estructura etiqueta/valor/delta
- **Regla**: `Figure` admite variante `negative` (clase `ledger-money-negative`); `Stat` muestra etiqueta (`ledger-label`), valor (`ledger-figure`) y delta opcional.
- **Fuente**: src/components/ui/ui.test.tsx:renders generic figures, stat label/value/delta and semantic variants
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-UI-005] Chip: el color vive solo en texto/borde, nunca en relleno (5 variantes)
- **Regla**: Las variantes `success|neutral|warning|danger|info` generan `ledger-chip-<variante>` cuya regla CSS define `color:` pero ningún `background`; la base `.ledger-chip` tiene `background: transparent`.
- **Fuente**: src/components/ui/ui.test.tsx:renders %s chip with color-only text/border class / keeps chip fills transparent…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-UI-006] Las cifras son tabulares en CSS
- **Regla**: `.ledger-figure` declara `font-variant-numeric: tabular-nums` y `font-feature-settings: "tnum"`.
- **Fuente**: src/components/ui/ui.test.tsx:keeps chip fills transparent and figures tabular
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [F-UI-007] Button: variantes primary/secondary/ghost con disabled nativo
- **Regla**: Cada variante aplica su clase `ledger-button-*`; `disabled` usa el atributo nativo del `<button>`.
- **Fuente**: src/components/ui/ui.test.tsx:renders primary, secondary and ghost buttons with native disabled semantics
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-UI-008] Field conecta etiqueta, pista, error y detalle por aria
- **Regla**: `Field` asocia la etiqueta al textbox; con error pone `aria-invalid="true"` y `aria-describedby="<id>-hint <id>-error <id>-detail"` apuntando a elementos con esos ids.
- **Fuente**: src/components/ui/ui.test.tsx:wires field label, hint, error and optional detail descriptions accessibly
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-UI-009] Disclosure es un `<details>` nativo cerrado por defecto
- **Regla**: `Disclosure` usa `<details>` con `open=false` inicial; la información avanzada/técnica queda plegada hasta que el usuario lo abre.
- **Fuente**: src/components/ui/ui.test.tsx:provides a native details disclosure for advanced information
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-UI-010] EmptyState: una sola acción de siguiente paso
- **Regla**: `EmptyState` muestra título (heading), descripción, pista opcional y exactamente un botón que dispara `onAction` una vez.
- **Fuente**: src/components/ui/ui.test.tsx:renders an empty state with one next-step action and optional hint
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-UI-011] ErrorBanner nombra causa y recuperación; detalle técnico plegado
- **Regla**: `ErrorBanner` (role alert) muestra `cause` + `recovery` y un botón de acción; el `detail` técnico va dentro de `<details>` cerrado.
- **Fuente**: src/components/ui/ui.test.tsx:names the error cause and recovery…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-UI-012] ErrorBanner solo afirma «Tu información se conserva.» si `preserved`
- **Regla**: La frase de datos conservados aparece únicamente cuando se pasa `preserved`; por defecto no se promete.
- **Fuente**: src/components/ui/ui.test.tsx:names the error cause… / states that data is preserved only when explicitly flagged
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-UI-013] Loading: esqueleto estático y anuncio accesible
- **Regla**: `Loading` renderiza N filas `ledger-skeleton-row` (decorativas, `aria-hidden`) y un `role=status` con el texto de la etiqueta.
- **Fuente**: src/components/ui/ui.test.tsx:uses static skeleton rows and an accessible status announcement
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-UI-014] Verdict abre con veredicto, tres cifras, motivo de cierre y caveat
- **Regla**: `Verdict` es una región «Veredicto» con la frase como `h2` (nunca `h1`), exactamente tres cifras monetarias `RD$`, el motivo de cierre y el aviso «Esto simula escenarios…».
- **Fuente**: src/components/ui/ui.test.tsx:leads with a verdict, three monetary figures, close reason and simulation caveat
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-UI-015] Cifra de tipo `count` sin prefijo RD$
- **Regla**: Una cifra con `kind:"count"` (p. ej. sorteos jugados) se muestra sin `RD$`.
- **Fuente**: src/components/ui/ui.test.tsx:renders a count figure without the RD$ prefix
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-UI-016] OrderSummary permite sustituir el caveat por defecto
- **Regla**: Un `caveat` propio reemplaza al texto por defecto («Esto simula escenarios» no aparece).
- **Fuente**: src/components/ui/ui.test.tsx:accepts a custom order caveat replacing the default
- **Categoría**: copy
- **Riesgo si se pierde**: bajo

### [F-UI-017] OrderSummary: celdas etiqueta/valor separadas y selección en fila propia
- **Regla**: Capital, Meta de saldo y Duración son tres celdas `ledger-summary-cell` (etiqueta + valor separados, sin palabras pegadas); «Cobertura» va en `ledger-summary-selection`, fuera de las celdas.
- **Fuente**: src/components/ui/ui.test.tsx:renders each order label and value as a separate cell…
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-UI-018] OrderSummary muestra todas las cifras en vivo y mantiene el caveat visible
- **Regla**: Al re-renderizar con nuevos valores el resumen actualiza cifras (`RD$2.000`) y siempre conserva el caveat.
- **Fuente**: src/components/ui/ui.test.tsx:shows all live order figures and keeps the caveat visible
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-UI-019] Escala tipográfica consistente (ratio 1.125–1.2; H1 de escritorio 32–40px)
- **Regla**: Los tokens `--type-small … --type-h1` crecen con ratio entre 1.125 y 1.2 y el H1 queda entre 32 y 40px.
- **Fuente**: src/lib/tokens.test.ts:uses a consistent 1.125–1.2 ratio and keeps desktop H1 within 32–40px
- **Categoría**: formato
- **Riesgo si se pierde**: bajo

### [F-UI-020] Tokens de texto cumplen WCAG AA (≥4.5:1) sobre bg/surface/field
- **Regla**: `--color-text` y `--color-text-secondary` sobre `--color-bg`, `--color-surface` y `--color-field` cumplen ≥4.5:1.
- **Fuente**: src/lib/tokens.test.ts:%s meets WCAG AA text contrast (>=4.5:1)
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-UI-021] Acento y borde de control cumplen ≥3:1 como componente UI; acento como texto ≥4.5:1
- **Regla**: `--color-accent` y `--color-border-control` sobre las tres superficies cumplen ≥3:1; el acento usado como texto cumple ≥4.5:1.
- **Fuente**: src/lib/tokens.test.ts:%s meets WCAG AA UI-component contrast / accent as text…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-UI-022] Colores semánticos (positive/negative/warning/info) cumplen ≥4.5:1 como texto
- **Regla**: Cada token semántico es legible (≥4.5:1) sobre bg, surface y field.
- **Fuente**: src/lib/tokens.test.ts:%s meets WCAG AA text contrast on ledger surfaces
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-UI-023] contrastRatio implementa WCAG correctamente
- **Regla**: Colores idénticos dan 1; negro sobre blanco 21; el resultado es simétrico; `#d0d4d8` sobre `#171e26` ≈ 11.27.
- **Fuente**: src/lib/contrast.test.ts:(4 tests)
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [F-UI-024] formatDOP: separador de miles español, prefijo RD$, negativos y enteros solamente
- **Regla**: `formatDOP(2800)="RD$2.800"`, `0="RD$0"`, `-500="-RD$500"`; un no entero lanza `RangeError` (el backend nunca envía decimales).
- **Fuente**: src/lib/format.test.ts:formatDOP (4 tests)
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-UI-025] formatTwoDigit: rellena a dos dígitos y valida rango Q80 0–99 entero
- **Regla**: `7→"07"`, `42→"42"`, límites 0 y 99; fuera de rango (100, −1) o no entero lanza `RangeError`.
- **Fuente**: src/lib/format.test.ts:formatTwoDigit (5 tests)
- **Categoría**: validación
- **Riesgo si se pierde**: medio

---

## 3. F-SHELL — App, Shell y etiquetas de UI

> Nota [A6]: las reglas de glosario sobre jerga visible (semilla/hash/JSON/ids/números absurdos) no están en estos tres archivos salvo la ayuda de semilla; el resto está distribuido en los tests de páginas (F-CREATE, F-RESULT, F-LIST) y se registra allí.

### [F-SHELL-001] La raíz redirige a /experimentos
- **Regla**: Navegar a `/` termina mostrando la página «Simulaciones».
- **Fuente**: src/App.test.tsx:redirects the root path to /experimentos
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-SHELL-002] Título canónico por ruta
- **Regla**: `/experimentos`→Simulaciones; `/experimentos/nuevo`→Crear simulación; `/experimentos/nuevo/sesion`→Crear varias simulaciones; `/experimentos/nuevo/perfil`→Crear simulación con perfil de juego; `/experimentos/:id`→Resultado de la simulación; `/experimentos/:id/comparacion`→Comparar simulaciones; `/configuraciones`→Estrategias; `/datos`→Datos e historial; `/ajustes`→Ajustes. Cada título es un heading.
- **Fuente**: src/App.test.tsx:shows the canonical title for %s
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-SHELL-003] Rutas y destinos de navegación estables
- **Regla**: Los enlaces apuntan a `/experimentos`, `/configuraciones`, `/datos`, `/ajustes` con nombres Simulaciones, Estrategias, Datos, Ajustes.
- **Fuente**: src/App.test.tsx:keeps route paths and canonical destinations stable / src/components/Shell.test.tsx:exposes exactly four canonical destinations
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-SHELL-004] Exactamente cuatro destinos en la navegación principal
- **Regla**: `nav` «Navegación principal» contiene exactamente cuatro enlaces (más el skip link: cinco enlaces en total en el shell).
- **Fuente**: src/components/Shell.test.tsx:exposes exactly four canonical destinations / keeps navigation visible and compact…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-SHELL-005] 404 honesto con salida a Simulaciones
- **Regla**: Una ruta desconocida muestra «Página no encontrada», un texto que invita a elegir una sección de la navegación y un enlace «Ir a Simulaciones» a `/experimentos`.
- **Fuente**: src/App.test.tsx:renders an honest not-found state for unknown paths
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-SHELL-006] Destino actual marcado con aria-current y regla de acento de 2px
- **Regla**: El enlace activo lleva `aria-current="page"` y estilo `border-l-2 border-accent`.
- **Fuente**: src/App.test.tsx:marks the current nav destination as active / src/components/Shell.test.tsx:marks the current destination…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-SHELL-007] Skip link: primer foco y mueve el foco al contenido principal
- **Regla**: El primer Tab enfoca «Saltar al contenido principal»; Enter mueve el foco a `#main-content`.
- **Fuente**: src/App.test.tsx:is the first focusable element and moves focus to main content
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-SHELL-008] Orden de tabulación: skip link → cola → cuatro destinos
- **Regla**: Tras el skip link, el siguiente foco es el botón de cola, luego Simulaciones, Estrategias, Datos, Ajustes; el botón de cola está habilitado.
- **Fuente**: src/App.test.tsx:keeps all destinations and the queue control in the tab order
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-SHELL-009] Sin violaciones axe en la pantalla por defecto
- **Regla**: `/experimentos` no tiene violaciones axe (jest-axe).
- **Fuente**: src/App.test.tsx:has no axe violations on the default screen
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-SHELL-010] Control de cola: nombre accesible, popup diálogo, expandido y descripción de estado
- **Regla**: El botón se llama «Abrir cola de cálculo», tiene `aria-haspopup="dialog"`, `aria-expanded="false"` inicial y descripción accesible «Sin cálculos en curso»; al hacer clic abre el diálogo «Cola de cálculo» (QueueDrawer).
- **Fuente**: src/components/Shell.test.tsx:keeps the queue control accessible and connected to QueueDrawer
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-SHELL-011] Títulos de ruta no se parten a mitad de palabra
- **Regla**: El heading del shell usa `break-normal` y nunca `break-all`/`break-words`.
- **Fuente**: src/components/Shell.test.tsx:does not break route titles mid-word
- **Categoría**: copy
- **Riesgo si se pierde**: bajo

### [F-SHELL-012] Navegación visible y compacta bajo el breakpoint de riel de escritorio
- **Regla**: La nav ocupa ancho completo (`w-full`) por debajo de 900px, pasa a 210px desde `min-[900px]`, y nunca se oculta (`hidden`).
- **Fuente**: src/components/Shell.test.tsx:keeps navigation visible and compact below the desktop rail breakpoint
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-SHELL-013] Diccionarios de etiquetas exhaustivos y distintos de la clave cruda
- **Regla**: `SELECTOR_LABELS` cubre `system|blend|random|parity`, `STAKING_LABELS`/`STAKING_DESCRIPTIONS` cubren `flat|ladder|bold`, `SETTLEMENT_LABELS` cubre `all|best`; cada etiqueta es no vacía y distinta de su clave cruda (sin jerga de implementación visible).
- **Fuente**: src/lib/ui-labels.test.ts:is exhaustive… / gives %s a non-empty label distinct from its raw key
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-SHELL-014] Ayuda de semilla: automática, reproducible, sin rangos de implementación
- **Regla**: `FIELD_HELP_SEED` es exactamente «Se genera automáticamente; el mismo código repite la selección.»; no contiene el entero máximo seguro 9.007.199.254.740.991 ni rangos numéricos, ni las palabras experimento/sesión.
- **Fuente**: src/lib/ui-labels.test.ts:explains automatic reproducibility without exposing implementation ranges
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-SHELL-015] Constantes de etiquetas de campo existen y no están vacías
- **Regla**: `FIELD_LABEL_STAKING/SETTLEMENT/SEED/DELTA`, `FIELD_HELP_SEED/DELTA` y `HISTORICAL_CAVEAT` son constantes obligatorias no vacías.
- **Fuente**: src/lib/ui-labels.test.ts:exposes non-empty field-label constants fixed by the plan
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

---

## 4. F-CREATE — Creación de simulaciones (`src/pages/new-experiment/*`)

Fuentes: `NewExperimentPage.test.tsx` (formulario simple «NEP»), `ProfileExperimentPage.test.tsx` («PEP»), `ProfileBatchPage.test.tsx` («PBP»). Los tests de modelos (`model`, `batch-model`, `profile-model`) están en F-UTIL.

### [F-CREATE-001] Tres grupos numerados: Reglas del sorteo / Selección / Límites
- **Regla**: El formulario muestra tres `group` con números 01 «Reglas del sorteo», 02 «Selección», 03 «Límites». La página de perfil expone los mismos tres encabezados.
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups, truthful rules… / ProfileExperimentPage.test.tsx:shows the three plain rule groups…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-002] Reglas veraces del catálogo (números, posiciones, repeticiones, premios, apuesta mínima)
- **Regla**: El grupo de reglas muestra «Números posibles» (`00–99 (100 números)`), «Posiciones por sorteo», «Repeticiones», «Premios por posición» (`1: 80 · 2: 8 · 3: 4 · 4: 2 · 5: 1`) y «Apuesta mínima por número», todos derivados del catálogo; hay enlace «Editar reglas» a `/datos#perfiles`.
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups, truthful rules…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-003] Apuesta mínima viene del catálogo, no de un literal
- **Regla**: `minimum_stake` 5 se muestra `RD$5` y 2800 `RD$2.800`.
- **Fuente**: NewExperimentPage.test.tsx:renders the catalog minimum stake %i as %s instead of a hardcoded literal
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-004] Defaults prellenados
- **Regla**: Capital 2000, meta de saldo 2800, duración máxima 12 sorteos, selección «Transición 60% + Fríos 40%, cobertura 10 números» (estrategia blend con pesos 60/40), «Cómo contar los premios» = `all` (opciones «Sumar los premios»/`all` y «Contar solo el mayor premio por número»/`best`).
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups… / loads ranked starting draws and keeps conditions and settlement controls available
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-005] Resumen de la orden en vivo, sin palabras pegadas ni placeholders
- **Regla**: La región «Resumen de la orden» refleja capital, meta, «12 sorteos» y la selección; no contiene `Sin nombre:` ni `()`. Con varias estrategias lista `Nombre: composición` (p. ej. «Mix: Transición 60% + Fríos 40%», «Par: Selección por paridad»).
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups… / LW10 loads a saved request through detail…
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-CREATE-006] Un solo caveat visible
- **Regla**: Exactamente un texto «Esto simula…»: «Esto simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.»
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-CREATE-007] Semilla oculta en Avanzado; nunca expone el entero máximo seguro
- **Regla**: «Código de repetición» no está en el DOM hasta abrir «Avanzado» y pulsar «Cambiar»; `#advanced-settings` y «Estrategia avanzada» empiezan cerrados; el texto 9.007.199.254.740.991 nunca aparece. Avanzado explica «Este código permite repetir la misma selección». La semilla por defecto es un entero seguro.
- **Fuente**: NewExperimentPage.test.tsx:keeps the seed control inside the advanced disclosure / shows three numbered groups… / prefills only one strategy from a configuration…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-CREATE-008] Una sola acción primaria; Salir es ghost
- **Regla**: Hay exactamente un botón «Crear simulación» con clase `ledger-button-primary`; «Salir» es `ledger-button-ghost`.
- **Fuente**: NewExperimentPage.test.tsx:shows three numbered groups… / loads ranked starting draws…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-009] Descubrimiento del creador por perfil sin alterar el formulario clásico
- **Regla**: Enlace «Crear simulación con perfil» a `/experimentos/nuevo/perfil`; es solo navegación: no postea y los inputs clásicos siguen usables.
- **Fuente**: NewExperimentPage.test.tsx:links to the dedicated route without changing the legacy form
- **Categoría**: contrato
- **Riesgo si se pierde**: bajo

### [F-CREATE-010] Plantilla de biblioteca prellena solo la estrategia; condiciones frescas, sin enviar
- **Regla**: `?configuration=id` carga una configuración, prellena una sola estrategia y deja nombre vacío y condiciones por defecto; no crea experimento; el enlace «Volver a simulaciones» sale sin diálogo si está limpio.
- **Fuente**: NewExperimentPage.test.tsx:LW13 prefills only one strategy from a configuration…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-011] Agregar desde biblioteca anexa sin tocar lo existente y rechaza duplicados normalizados; límite de cinco
- **Regla**: «Agregar desde biblioteca» añade una estrategia sin cambiar condiciones ni estrategias previas; un nombre duplicado (normalizado) muestra alerta «nombre único» sin POST; con cinco estrategias el botón queda deshabilitado.
- **Fuente**: NewExperimentPage.test.tsx:appends one selected template… / caps append at five…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-CREATE-012] Cambios semánticos de `configuration`/`base` con borrador sucio piden confirmación
- **Regla**: Cambiar o quitar `?configuration`/`?base` con borrador editado abre `alertdialog` con «Seguir editando» / «Salir sin guardar»; la URL y el formulario no cambian hasta confirmar; limpio no pregunta; cambios de query no relacionados (`?view=compact`) no se bloquean; un borrador en blanco pero sucio también se protege al añadir `base`.
- **Fuente**: NewExperimentPage.test.tsx:guards semantic configuration changes… / blocks a new base query… / guards base removal… / loads another base without a prompt while clean… / guards a dirty blank draft…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-013] Conflicto base+configuration se rechaza con alerta
- **Regla**: `?base=...&configuration=...` muestra alerta «dos orígenes» y no postea.
- **Fuente**: NewExperimentPage.test.tsx:guards semantic configuration changes…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-CREATE-014] Respuestas obsoletas (configuración/base) se ignoran
- **Regla**: Una respuesta tardía de una configuración o base previa no sobrescribe el borrador de la consulta nueva.
- **Fuente**: NewExperimentPage.test.tsx:ignores a stale configuration response… / ignores a delayed previous base response…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-015] Fallos al guardar en biblioteca preservan el borrador y mapean 422 a campos propios
- **Regla**: Un fallo de red al guardar en biblioteca muestra alerta (biblioteca … reintentar) y conserva nombre y borrador sin POST de experimento; un 422 marca `aria-invalid` en el nombre de biblioteca (`body.name`) y en el sistema (`body.strategy.system`).
- **Fuente**: NewExperimentPage.test.tsx:caps append at five… / maps library save 422…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-CREATE-016] Plantillas faltantes, sin red o inválidas se explican sin postear
- **Regla**: 404 → «ya no existe»; NetworkError → «contactar al servidor»; sistema desconocido → «Esta estrategia guardada ya no es válida». Igual para `base` (404 vs red).
- **Fuente**: NewExperimentPage.test.tsx:reports missing, network and catalog-invalid templates without posting / distinguishes a missing base from a network error without posting
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-CREATE-017] Usar como base: carga el request del experimento y localiza el sorteo más allá de la primera página
- **Regla**: `?base=id` muestra «Cargando experimento base…», precarga nombre, sorteo inicial, semilla, estrategias (método, pesos, cobertura 50 para paridad) y consulta el sorteo por fecha paginando (offset 0 y 100 con `date`); queda limpio hasta editar y sale sin diálogo; un borrador prellenado queda protegido solo después de un cambio.
- **Fuente**: NewExperimentPage.test.tsx:LW10 loads a saved request through detail… / keeps the prefilled draft guarded only after a change…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-018] Filtro de fecha de sorteos inicial: etiquetado, accesible y conserva selección del mismo día
- **Regla**: «Filtrar sorteos por fecha» es `type=date` con descripción «Vacío: todas las fechas…»; una selección del mismo día se conserva; otro día la limpia (sin elegir otro día) y volver con selección abre el diálogo; consulta `getStartingDraws(0,100,fecha)` y disponibilidad.
- **Fuente**: NewExperimentPage.test.tsx:ODD03b labels the date filter…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-CREATE-019] Distingue fecha sin historial de fecha con historial sin ranking
- **Regla**: Fecha sin historial muestra «No hay sorteos en esta fecha»; fecha con historial pero sin ranking tiene mensaje propio; en ambos «Crear simulación» queda deshabilitado y el combo de sorteo se bloquea cuando no hay opciones.
- **Fuente**: NewExperimentPage.test.tsx:distinguishes dates without history from dates with only unranked history
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-CREATE-020] Respuestas viejas de filtro/paginación se descartan tras elegir una fecha nueva
- **Regla**: Respuestas tardías de fecha o de «Cargar más sorteos» no agregan opciones tras una fecha más reciente; el botón de cargar más desaparece.
- **Fuente**: NewExperimentPage.test.tsx:ignores older filter and pagination responses…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-021] Un sorteo seleccionado que ya no tiene ranking no se acepta
- **Regla**: Si al recargar el día el sorteo seleccionado deja de existir, se muestra «Ese sorteo ya no está disponible», la opción queda deshabilitada y «Crear simulación» también; sin POST.
- **Fuente**: NewExperimentPage.test.tsx:does not accept a selected draw after its same-day reload reports no ranking
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-CREATE-022] Sorteo seleccionado fuera de página se revalida dentro de su día
- **Regla**: Un sorteo elegido en la segunda página del día se conserva válido al quitar y reponer el filtro (pide offset 100 del día) y mantiene habilitado el envío.
- **Fuente**: NewExperimentPage.test.tsx:rechecks a selected off-page draw within its day…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-023] Paginación por día y reintento de petición con fecha fallida
- **Regla**: Un fallo de red con fecha muestra alerta «Reintentá…», deshabilita crear y el botón «Reintentar» recupera; «Cargar más sorteos» pagina solo ese día.
- **Fuente**: NewExperimentPage.test.tsx:paginates only the selected day and retries a failed dated request
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-024] Estados vacío y desconectado del catálogo sin inventar sorteo
- **Regla**: Sin sorteos: «No hay sorteos iniciales», combo y crear deshabilitados; desconexión: «No se pudo contactar al servidor» con «Reintentar» que recarga; nunca hay un sorteo por defecto falso.
- **Fuente**: NewExperimentPage.test.tsx:shows empty and disconnected catalog states…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-025] Sorteos clasificados se cargan bajo demanda sin pedir todo el historial
- **Regla**: «Cargar más sorteos» pide la siguiente página (`offset 1, limit 100`); la primera carga es `(0,100)`.
- **Fuente**: NewExperimentPage.test.tsx:loads further ranked draws on demand…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-CREATE-026] Ayuda de semilla y error anunciados juntos (aria-describedby)
- **Regla**: El campo código tiene `aria-describedby="seed-help"`; con error pasa a `seed-help seed-error` y la descripción accesible es ayuda + «Ingresá un código de repetición válido.»; «Sorteo inicial» refiere ayuda y error («Elegí un sorteo con ranking disponible»).
- **Fuente**: NewExperimentPage.test.tsx:announces the seed help together with validation errors…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-CREATE-027] Validación de dinero, meta, límites y semilla sin redondear
- **Regla**: Capital `2.5`, meta menor, duración `10000001` y semilla `9007199254740992` se rechazan: alerta «errores», `aria-invalid` en campos, el valor tecleado se conserva, sin POST.
- **Fuente**: NewExperimentPage.test.tsx:rejects invalid money, goal, start, limits and seed without rounding
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-CREATE-028] Fallos de servidor nombrados en la alerta; detalle técnico plegado
- **Regla**: Un 500 muestra alerta con «servidor» y «revisá Simulaciones»; el detalle crudo está dentro de «Detalles técnicos» (oculto hasta abrir); se llama una sola vez.
- **Fuente**: NewExperimentPage.test.tsx:names server failures in the alert and keeps technical details disclosed
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-CREATE-029] Shape exacto del payload (mezcla 60/40, K10, duración 12) y envío único
- **Regla**: `createExperiment` se llama una vez con `{request:{name, conditions:{start_draw,capital,goal,settlement,max_bets:duración,max_minutes:null,seed}, strategies:[{name,selector:"blend",components:[{system,weight}],coverage,staking:"flat"}]}}`; durante el envío el botón muestra «Creando…» deshabilitado; al éxito navega a `/experimentos/{id}`.
- **Fuente**: NewExperimentPage.test.tsx:builds accepted 60/40 mix K10 max12 and posts exact body once…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-CREATE-030] Paridad fuerza cobertura 50; nombres de estrategia duplicados bloquean
- **Regla**: El método paridad fuerza cobertura «50 números»; dos estrategias con el mismo nombre (insensible a mayúsculas/espacios) muestran «El nombre debe ser único» y bloquean la creación.
- **Fuente**: NewExperimentPage.test.tsx:parity forces coverage 50 and duplicate strategy names block creation
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-CREATE-031] Mapeo de errores 422 a campos, bloques de estrategia y sección de condiciones
- **Regla**: Un 422 con `loc` de campo marca ese campo (`aria-invalid`, p. ej. `conditions.goal`, `strategies.N.name`) y mueve el foco al primer campo ofensor; sin campo en estrategia (`strategies.N`) expande ese bloque con «Estrategia rechazada» y el detalle del servidor sin marcar el nombre; sin campo en `conditions` se muestra en la sección sin marcar `goal`; un componente de mezcla suelto enfoca y borra su error al cambiar el subcampo conservando errores ajenos (staking).
- **Fuente**: NewExperimentPage.test.tsx:maps a field-located duplicate-name 422… / maps 422 field errors… / focuses and clears a bare mix component error… / maps a strategy-level 422… / maps a conditions-level 422… / moves focus to the first offending field…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-CREATE-032] Editar limpia solo el error del campo corregido y el aviso genérico se actualiza
- **Regla**: Tras 422 con `goal` y `max_bets`, corregir la meta limpia solo su error; el de duración persiste; la alerta pasa de «Revisá los campos señalados» a «Revisá los errores señalados junto a los campos antes de crear la simulación.»
- **Fuente**: NewExperimentPage.test.tsx:clears the server notice and the matching field error on edit…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-CREATE-033] 507 y fallos de red preservan valores; red incierta advierte posible creación
- **Regla**: 507 → «No hay espacio para crear el experimento»; NetworkError → «Sin respuesta del servidor. Puede que el experimento se haya creado»; los valores ingresados se conservan.
- **Fuente**: NewExperimentPage.test.tsx:maps 422 field errors; 507 and network failures preserve entered values
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-CREATE-034] Diálogo de confirmación al salir con cambios (enlaces, atrás del navegador)
- **Regla**: Con borrador sucio, navegar por un enlace o atrás del navegador abre `alertdialog` accesible; «Seguir editando» conserva el borrador y «Salir sin guardar» continúa; la ruta no cambia hasta confirmar; limpio no bloquea; salir nunca cancela trabajo del backend ni postea.
- **Fuente**: NewExperimentPage.test.tsx:blocks browser back while dirty… / does not block a clean wizard navigation / guards dirty navigation with accessible stay/leave…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-035] beforeunload solo mientras el borrador está sucio y se limpia al salir
- **Regla**: Se registra un listener `beforeunload` al ensuciar y se elimina al abandonar.
- **Fuente**: NewExperimentPage.test.tsx:requests native refresh confirmation only while dirty and cleans listener on leave
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-036] Perfil: valores técnicos tras disclosures cerradas; sin jerga de implementación
- **Regla**: Los bloques «Detalles técnicos» están cerrados; no aparece etiqueta «Semilla» ni `schema_version`; la identidad del historial (hash) solo se ve dentro de «Identidad del historial» tras abrirlo; las cantidades escaladas se explican («unidades escaladas», escala N).
- **Fuente**: ProfileExperimentPage.test.tsx:shows the three plain rule groups… / shows the chosen history identity and the scale context…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-CREATE-037] URL `dataset_sha256` es solo una pista de lectura; no autoselecciona
- **Regla**: Con `?dataset_sha256=` se muestra estado «Historial elegido desde la biblioteca.» con el hash, pero perfil e historial siguen sin seleccionar.
- **Fuente**: ProfileExperimentPage.test.tsx:keeps a library dataset URL as a read-only identity hint…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-038] Políticas de apuesta de perfil: Q80 cíclica (schema 2), Audaz (schema 3), recuperación (schema 4)
- **Regla**: Q80 («Política de apuesta» = cycling) oculta la apuesta fija y envía `schema_version 2` con `q80-first-prize-cycling/v1` sin `per_number_stake`. Audaz solo se ofrece si la cobertura es compatible con el servidor («hasta cobertura 1») y envía schema 3 con `profile-audaz/v1`. Recuperación envía schema 4 con `target_margin` en unidades menores (12.34→1234), `rounds`, `end_mode` cycle|stop y selector explícito; ninguna lleva `per_number_stake`.
- **Fuente**: ProfileExperimentPage.test.tsx:submits explicitly selected Q80 cycling… / offers generic Audaz only for server-compatible… / submits schema-4 recovery…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-CREATE-039] Revalidación previa al POST: capacidades retiradas o vínculos obsoletos bloquean
- **Regla**: Antes de postear se relee el servidor; si se retira compatibilidad de recuperación, `selector_capabilities`, `settlements`, `entry_policies`, la capacidad Q80, o cambia el perfil del historial, se muestra alerta «cambiaron», no se postea y se conserva el borrador.
- **Fuente**: ProfileExperimentPage.test.tsx:does not POST recovery if current server compatibility withdraws coverage / does not POST when the server withdraws %s at recheck / does not POST Q80… / blocks stale server bindings…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-040] Creación con perfil: request exacto una vez y abre detalle existente
- **Regla**: «Crear simulación y agregar a la cola» posta una vez `kind:"profile"` con `dataset_sha256`, `profile_sha256`, capital/meta en unidades menores (2000→200000), `settlement all`, selector `static-numbers/v1` con números `[0,1]` y `flat-per-number/v1` con `per_number_stake 125` (1.25); luego navega a `/experimentos/{id}`.
- **Fuente**: ProfileExperimentPage.test.tsx:creates the exact request once and opens existing detail
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-CREATE-041] Perfiles, historiales y sorteos paginados más allá de la primera página
- **Regla**: Navegación «Páginas de perfiles/datos/sorteos» pide offset 20/20 y filtra sorteos por fecha (`getDatasetDraws(sha,0,100,fecha)`).
- **Fuente**: ProfileExperimentPage.test.tsx:finds profiles, datasets and draws beyond the first page and date filter
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-CREATE-042] Preflight fallido no bloquea el reenvío; incertidumbre de red sí y nunca reenvía sola
- **Regla**: Si el preflight falla antes de cualquier POST: alerta «No se envió la simulación» y el botón sigue habilitado. Si el POST tiene resultado incierto (red, doble clic): alerta «Puede estar en la cola», botón deshabilitado, solo un POST, enlace «Revisá Simulaciones» a `/experimentos`; nunca reenvío automático.
- **Fuente**: ProfileExperimentPage.test.tsx:does not lock submission when preflight failed… / never automatically resubmits after an uncertain network outcome…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-043] Sin falsa compatibilidad entre historial y perfil; axe limpio
- **Regla**: Si ningún historial coincide con el `profile_sha256` del perfil, el selector queda con una sola opción y se muestra «No hay datos compatibles»; la página no tiene violaciones axe.
- **Fuente**: ProfileExperimentPage.test.tsx:shows no false compatibility and keeps keyboard-labeled controls accessible
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-CREATE-044] Lote guiado: título renombrado y detalles de estrategia cerrados
- **Regla**: La página se titula «Lote de simulaciones»; cada estrategia tiene sus detalles internos (p. ej. `static-numbers/v1`) dentro de un `<details>` cerrado.
- **Fuente**: ProfileBatchPage.test.tsx:presents the renamed artifact and keeps strategy internals closed by default
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-CREATE-045] Crear lote solo tras validación vigente del servidor; editar invalida
- **Regla**: Con perfil+historial exactos, estrategia y condiciones, «Crear simulaciones» está deshabilitado hasta pulsar «Validar simulación» y recibir «Validación aceptada»; el aviso dice «Validar comprueba la solicitud; no reserva capacidad.»; `validateProfileBatch` recibe el cuerpo exacto (schema 1, profile, dataset, strategies con `definition_sha256`, conditions); cualquier edición posterior (p. ej. máximo de sorteos) deshabilita crear de nuevo.
- **Fuente**: ProfileBatchPage.test.tsx:binds profile and exact dataset, preserves shared inputs…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-046] Creación incierta de lote: consulta la identidad congelada antes de reintentar
- **Regla**: Tras un NetworkError al crear: alerta «Sin confirmación: la simulación pudo haberse creado»; al reintentar primero consulta `getProfileBatchByClientRequestId`; si da 404 reintenta con el mismo cuerpo y mismo `client_request_id`; al confirmar se retira el pendiente de `sessionStorage`.
- **Fuente**: ProfileBatchPage.test.tsx:looks up the frozen client request identity before retrying an uncertain create
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-047] Recuperación de lote congelado sin depender del catálogo ni formulario actuales
- **Regla**: Con un pendiente en `sessionStorage` el botón «recuperar creación pendiente» funciona aunque catálogo, estrategias y política fallen por red; consulta por el id congelado, retira el almacenamiento y no crea otra vez.
- **Fuente**: ProfileBatchPage.test.tsx:recovers a frozen request without current form/catalog readiness…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-048] Tras 404 de lookup solo se reintenta el cuerpo congelado, no los inputs editados
- **Regla**: El reintento envía `frozenBody` aun con capital editado, y si vuelve a fallar el pendiente persiste intacto.
- **Fuente**: ProfileBatchPage.test.tsx:retries only the frozen body after a lookup 404…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-049] Montos de estrategia sin cambios hacen round-trip como decimal sin agrupar según escala
- **Regla**: `per_number_stake` en unidades menores se muestra decimal sin separador según escala (0:1000, 2:1000.00, 3:1000.000, 2:1234.56) y se reenvía exactamente igual al guardar nueva revisión.
- **Fuente**: ProfileBatchPage.test.tsx:round-trips unchanged minor units %i at scale %i as ungrouped decimal text
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-CREATE-050] Copiar una definición conserva defaults cerrados y metadatos protegidos
- **Regla**: «Crear copia editable» propone «Fijas copia» y al guardar conserva selector, staking, `selector_parameters` y `closing_defaults` (settlement, max_elapsed_draws, max_bet_draws).
- **Fuente**: ProfileBatchPage.test.tsx:copies supported definitions without dropping their closed defaults…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-051] Estrategia cerrada no soportada no se presenta como editable plana
- **Regla**: Una estrategia con selector/staking no soportado (`archived-cold/v1`, `profile-recovery-ladder/v1`) muestra sus detalles en el desplegable pero «Editar y guardar nueva revisión» da alerta «No se puede editar ni copiar esta estrategia sin cambiarla» y no ofrece «Guardar como estrategia nueva».
- **Fuente**: ProfileBatchPage.test.tsx:does not present an unsupported closed strategy as an editable flat/static replacement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-CREATE-052] Sorteo inicial canónico se conserva al navegar otra página de sorteos; respuesta actual tras edición no relacionada
- **Regla**: Un sorteo elegido sigue siendo el enviado a validar aunque se pagine a otra página; una respuesta de sorteos vigente se acepta tras editar otra condición.
- **Fuente**: ProfileBatchPage.test.tsx:keeps a selected canonical start draw… / accepts the current dataset draw page response…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-CREATE-053] Vínculo de perfil inválido no envía; referencias de fuente sin afirmaciones financieras
- **Regla**: Con solo el historial elegido se muestra el rango de fechas del historial, no se llama `createProfileBatch`.
- **Fuente**: ProfileBatchPage.test.tsx:does not submit an invalid or stale profile binding…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

---

## 5. F-RESULT — Resultado, comparación, gráficos y métricas

Fuentes: `DetailPage.test.tsx` («DET»), `ComparisonPage.test.tsx` («CMP»), `BalanceChart`, `ComparisonChart`, `RunTrajectory`, `FinancialMetrics`, `StatusLabel`.

### [F-RESULT-001] Mapeo desenlace/estado → frase de veredicto
- **Regla**: `verdictPhrase(outcome,status)`: `goal`→«Meta alcanzada», `ruin`→«Se agotó el capital», `limit`→«Límite de sesión», `history_exhausted`→«Historial agotado», sin desenlace+`running`→«En curso», `cancelled`→«Simulación cancelada».
- **Fuente**: DetailPage.test.tsx:maps existing outcome %s and execution state %s to %s
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-002] El detalle abre con el veredicto (h2), tres cifras clave y caveat
- **Regla**: La región «Veredicto» tiene la frase como `h2`, exactamente tres `ledger-stat` (Saldo final, Mejor saldo, Sorteos jugados) y el caveat «Esto simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.»; el caveat aparece también en comparación.
- **Fuente**: DetailPage.test.tsx:leads with the verdict and keeps calculation jargon inside technical details / shows the delta help and exact standing caveat / does not claim historical provenance…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-003] Motivo de cierre visible y legible
- **Regla**: «Motivo de cierre: Límite de sesión (límite de sorteos transcurridos)» y, en lotes v5, categorías como «Límite configurado», «Fin de la fuente guardada» o «Ventana operativa; fuente incompleta»; los códigos crudos (`configured_limit`, `max_bet_draws`, `source_end`) solo viven en detalles técnicos.
- **Fuente**: DetailPage.test.tsx:shows server delta, elapsed/bet counts… / uses saved identity, frozen references… / labels history_exhausted as an incomplete operational window / keeps Historial agotado when v5 reports the actual full-source end
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-004] Historial agotado vs ventana operativa incompleta según categoría del backend
- **Regla**: `history_exhausted` solo se rotula «Fin de la fuente guardada» si el backend clasifica `source_end`; si clasifica `operational_window` se muestra «Ventana operativa; fuente incompleta» y no se afirma el fin de la fuente. Igual en la tabla de comparación.
- **Fuente**: DetailPage.test.tsx (2 tests v5) / ComparisonPage.test.tsx:labels history exhaustion only for a backend-classified full-source end
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-005] Delta del servidor mostrado tal cual; neto ausente es «No disponible»
- **Regla**: «Cambio respecto del inicio» muestra `delta` proyectado por la API (40→RD$40, -15→-RD$15, 0→RD$0) sin restar saldos en el navegador; `net` ausente se muestra «No disponible» (nunca cero ni confundido con delta); una ejecución sin resultado no inventa delta.
- **Fuente**: DetailPage.test.tsx:shows the API-projected delta… / shows an absent net as N/A… / does not invent a delta for an incomplete run…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-006] Métricas financieras: valores del servidor tal cual; sin recálculo ni ceros inventados
- **Regla**: `FinancialMetrics` muestra apostado, pagado, neto, ROI, retorno por peso apostado y caída máxima con los valores del backend (ratios con 6 decimales); ratios nulos → «N/D»; métricas ausentes → «No disponible» (nunca cero financiero); `omitNet` evita repetir Neto cuando el veredicto lo posee.
- **Fuente**: FinancialMetrics.test.tsx:shows server-derived… / does not invent unavailable values…; RunTrajectory.test.tsx:displays backend values verbatim… / does not replace missing metrics…; DetailPage.test.tsx:displays backend metrics with profile money…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-007] Color semántico solo en dinero, nunca en conteos ni ratios; cifras tabulares
- **Regla**: Neto positivo/negativo recibe `ledger-money-positive/negative`; el apostado no; los ratios usan `ledger-figure` sin color semántico. En el libro de sorteos el saldo es `text-right` y usa `font-mono tabular-nums`.
- **Fuente**: FinancialMetrics.test.tsx:applies semantic colors only to money… / shows server-derived…; DetailPage.test.tsx:shows server delta, elapsed/bet counts…
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [F-RESULT-008] Jerga de cálculo y detalle técnico plegados
- **Regla**: ROI/HALF_UP y similares solo aparecen dentro de un `<details>` cerrado «Detalles técnicos»; la página visible (con detalles cerrados) no contiene `ROI`, `drawdown` ni `N/A`; semilla, SHA-256, JSON y nombres de archivo (`history.json`) no aparecen hasta abrir los detalles de «Parámetros y datos» (donde existe «Semilla guardada»).
- **Fuente**: DetailPage.test.tsx:keeps technical identifiers folded… / leads with the verdict…; FinancialMetrics.test.tsx:keeps calculation terminology…; ComparisonPage.test.tsx:leads with a four-figure verdict…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-009] Selector y apuesta se muestran con etiquetas planas, nunca claves crudas
- **Regla**: En Parámetros aparecen «Un sistema de selección», «Plana», «Sumar los premios» y no `system`, `flat`, `all`.
- **Fuente**: DetailPage.test.tsx:maps saved selector and staking to plain labels…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-010] Ejecución sin resultado guardado: sin resultado, métricas ni replay fabricados
- **Regla**: Con estado `pending|held|running|failed|cancelled` y `result:null` (Q80, Audaz, v5, perfil) se muestra «no tiene un resultado guardado», el estado de ejecución (Pendiente, En curso, Con error), no se muestra región de Métricas financieras y no se pide replay.
- **Fuente**: DetailPage.test.tsx:shows Q80 %s without a fabricated result… / shows schema-3 Audaz %s… / shows v5 %s without claiming metrics or replay / shows one position… preserves held/failed null results
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-011] Fallos mixtos de lote son locales a su ordinal, sin ceros financieros
- **Regla**: Una estrategia fallida en un lote v5 muestra «no tiene un resultado guardado» y, en detalles técnicos, categoría de parada, motivo informado y error; las demás ejecuciones siguen intactas; solo se pide replay de la ejecución con resultado.
- **Fuente**: DetailPage.test.tsx:keeps mixed strategy failures ordinal-local without financial zeros
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-012] Apuesta dinámica (Q80 cíclica, Audaz, recuperación) no se presenta como monto fijo
- **Regla**: Las políticas dinámicas muestran su etiqueta («Escalera cíclica Q80 · apuesta dinámica por sorteo», «Audaz · apuesta dinámica por sorteo», «Escalera de recuperación · parámetros explícitos por perfil»), nunca «undefined por número» ni «por número»; los stakes por número se leen del replay (`7: USD 1.25, 8: USD 1.25`).
- **Fuente**: DetailPage.test.tsx:reads completed cycling stake as dynamic… / renders schema-3 Audaz as dynamic…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-013] Recuperación schema 4: parámetros y versión visibles solo en técnico
- **Regla**: Se muestran «Perfil v4» (2 veces), margen objetivo (USD 12.50 de 1250), «Rondas de recuperación» 3 y el cierre «Reiniciar la escalera» (cycle) o «Detener la sesión» (stop) dentro de detalles técnicos; «Versión del resultado» no se muestra en el cuerpo.
- **Fuente**: DetailPage.test.tsx:shows schema-4 recovery request… / ComparisonPage.test.tsx:compares schema-4 recovery…
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-RESULT-014] Moneda y escala del perfil gobiernan todo importe mostrado
- **Regla**: Con perfil USD/EUR escala 2 los importes se ven `USD 97.50`, `-USD 2.50`, `EUR 99.00` (unidades menores/100) en veredicto, tablas, gráficos y tabla de datos del gráfico; con el catálogo legado se ve `RD$` con separador de miles.
- **Fuente**: DetailPage.test.tsx:shows server delta, elapsed/bet counts, 3 positions… / ComparisonPage.test.tsx:shows server delta and elapsed versus bet draws…
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-RESULT-015] Posiciones del perfil: sin columnas fijas de cinco; resultados con relleno de dos dígitos en legado
- **Regla**: La tabla de apuestas tiene tantas columnas «Resultado» como posiciones del perfil (3 o 1), el detalle dice «Resultados (3 posiciones)» y no «posiciones 1 a 5»; en legado los números se muestran con relleno (`00, 07`, `00, 03, 07, 08, 09`) y monto `RD$10`.
- **Fuente**: DetailPage.test.tsx:shows server delta… / shows one position without fixed-five columns / shows persisted bet data with padded numbers and DOP
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [F-RESULT-016] Lote v5: identidad guardada, referencias congeladas y índices canónicos
- **Regla**: El detalle usa el nombre guardado («Lote guardado · Snapshot cold»), «Estrategia: Snapshot cold · revisión 2», enlace «Comparar simulaciones», y en detalles técnicos ID de estrategia, SHA-256 de definición, fuente canónica, filas de la fuente; el replay muestra `source_index` y `bet_index`; métricas vienen del backend.
- **Fuente**: DetailPage.test.tsx:uses saved identity, frozen references, backend metrics…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-RESULT-017] Estado de ejecución y desenlace son vocabularios distintos
- **Regla**: `StatusLabel` kind=execution (Ejecución completada, Pendiente, En curso, Cancelado, Con error…) y kind=outcome (Meta alcanzada…) nunca comparten texto; cada valor de cada vocabulario tiene etiqueta única; una ejecución sin resultado nunca recibe desenlace («Meta alcanzada» no aparece).
- **Fuente**: StatusLabel.test.tsx:(renders execution… / never uses the same label… / gives every distinct… / never shares a label…); DetailPage.test.tsx:keeps the stable URL, separates execution from outcome…; ComparisonPage.test.tsx:uses server N/M and delta…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-018] Estado nunca depende solo del color; chips con color semántico y glifo oculto
- **Regla**: Los estados son texto + glifo SVG `aria-hidden`; `outcome goal` usa `ledger-chip-success`, `execution failed` usa `ledger-chip-danger` y no clases de dinero; `cancelled` y `failed` pueden compartir `data-status-shape` (el texto es la señal autoritativa); atributos `data-status-kind/value`.
- **Fuente**: StatusLabel.test.tsx:uses semantic color on status chips… / includes a hidden SVG glyph… / shapes may repeat…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-RESULT-019] Valor de estado desconocido lanza error
- **Regla**: `StatusLabel` con un valor no reconocido lanza en lugar de renderizar vacío.
- **Fuente**: StatusLabel.test.tsx:throws for an unknown status value
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-RESULT-020] Gráfico de saldo: solo saldos persistidos, meta real y alternativa textual
- **Regla**: `BalanceChart` grafica solo puntos persistidos («2 de 4 sorteos»), con `img` «saldos registrados», filas de tabla por sorteo, «Meta de saldo: 200» y sin filas inventadas; sin puntos muestra «Todavía no hay sorteos jugados» sin desenlace ficticio.
- **Fuente**: BalanceChart.test.tsx (2 tests)
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-021] Gráfico comparado: eje temporal único y series distinguibles sin color
- **Regla**: Las series se posicionan por fecha en un eje común; cada serie termina en su último punto persistido; se distinguen por patrón de trazo (`none` vs `8 5`) y marcador (circle/square) con leyenda textual («A · circle, línea continua» / «B · square, línea a trazos»); `aria-label` menciona trazos y marcadores; el SVG tiene `min-w-[640px]` dentro de una región `overflow-x-auto`; hay nota «líneas conectan observaciones» y datos textuales «fecha … RD$90».
- **Fuente**: ComparisonChart.test.tsx:positions distinct dates on one time axis…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-RESULT-022] Series conmutables por teclado sin alterar métricas; los datos textuales persisten
- **Regla**: Cada serie tiene checkbox «Mostrar X» activable con espacio; ocultar quita la polilínea pero conserva su texto de datos.
- **Fuente**: ComparisonChart.test.tsx:offers keyboard-accessible toggles…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-RESULT-023] Trayectorias de corrida completa: acotadas, con reducción declarada y selección por índice original
- **Regla**: `RunTrajectory` pide `getTrajectory(id, ordinal, 500)` una sola vez; muestra «4 de 1001 sorteos»; la reducción (`minmax-even-v1`), extremos y línea base están en detalles técnicos cerrados; permite elegir un punto («Apuesta 1001»→índice 1000) o saltar a «Apuesta exacta» (601→600); sin avisos de «gráfico incompleto»; el SVG dibuja 5 círculos (4 puntos + marcador).
- **Fuente**: RunTrajectory.test.tsx:loads once, discloses reduction/extrema/baseline…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-024] Índice de sorteo canónico v5 separado del índice local de apuesta
- **Regla**: En v5 el botón dice «Apuesta 2 · sorteo n.º 905» y selecciona el índice local de apuesta (1), no el `source_index`.
- **Fuente**: RunTrajectory.test.tsx:keeps canonical v5 source indexes separate from local replay bet indexes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-RESULT-025] Trayectorias sin reducción >20 puntos enlazan búsqueda exacta sin descargar replay
- **Regla**: Con `chart={false}` el enlace «Apuesta 30» apunta a `/experimentos/exp?run=0&bet=29&from=comparison`.
- **Fuente**: RunTrajectory.test.tsx:uses all >20 unreduced points…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-RESULT-026] Trayectoria: vacío, fallo con reintento, tardías tras desmontar y índices mal formados
- **Regla**: Error → alerta «No se pudo cargar» con «Reintentar trayectoria»; vacío → «Todavía no hay sorteos jugados» sin spinbutton ni imagen; una respuesta tardía tras desmontar no llama `onLoad`; un `source_index` negativo muestra alerta y no publica gráfico.
- **Fuente**: RunTrajectory.test.tsx:handles empty data and retries… / ignores late responses after unmount / rejects malformed indexes…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-RESULT-027] Deep link a una apuesta exacta más allá de la página 20
- **Regla**: `?run=0&bet=600&from=comparison` selecciona la pestaña «Apuestas», pide el replay una sola vez con `(id,0,600,20)` y muestra «Sorteo seleccionado 601:».
- **Fuente**: DetailPage.test.tsx:jumps directly to an exact source bet beyond page 20…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-RESULT-028] Navegación estable por URL, polling solo en no terminales
- **Regla**: El detalle y la comparación se actualizan por polling (5 s) solo mientras el estado no es terminal, no cambian la URL, se detienen al completar y al desmontar.
- **Fuente**: DetailPage.test.tsx:polls a nonterminal snapshot…; ComparisonPage.test.tsx:polls nonterminal only, cleans up on unmount
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-RESULT-029] Respuestas obsoletas por id/ejecución se ignoran
- **Regla**: Una respuesta tardía de otro id (detalle o comparación), de otro replay tras cambiar de ejecución o de otra trayectoria tras salir no reemplaza la vista actual.
- **Fuente**: DetailPage.test.tsx:does not replace an existing snapshot with a stale response… / requests only the next bounded page and ignores an old replay response…; ComparisonPage.test.tsx:shows 404 and disconnection separately… / ignores a late trajectory response…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-030] Errores distinguidos: registro inexistente, desconexión y conflicto de replay
- **Regla**: 404 → alerta «no existe»; NetworkError → «El cálculo puede continuar en el servidor; comprobá el estado desde la cola antes de reintentar.» (nunca afirma que se detuvo); 409 de replay → «reproducción … disponible». Misma distinción en comparación («contactar»).
- **Fuente**: DetailPage.test.tsx:distinguishes missing record, disconnection and a replay conflict; ComparisonPage.test.tsx:shows 404 and disconnection separately…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-031] Replay paginado bajo demanda, navegación por teclado y reproducción
- **Regla**: El replay pide 20 apuestas por página («Página siguiente» → offset 20) sin pedir todas; «Sorteo mostrado: 21 de 21»; las pestañas (Resultado, Apuestas, Parámetros y datos) navegan con flechas/Home; «Reproducir»/«Pausar» con un solo temporizador (1 s/paso) que no cambia las métricas finales; «Siguiente sorteo» mueve el cursor sin tocar métricas ni fuentes ni mutar.
- **Fuente**: DetailPage.test.tsx:pages a long replay on demand… / supports keyboard tabs and play/pause… / keeps final metrics and sources unchanged…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-RESULT-032] Accesibilidad axe del detalle y la comparación completados
- **Regla**: El detalle completado (con imagen «saldos registrados») y la comparación completada no tienen violaciones axe.
- **Fuente**: DetailPage.test.tsx:has no automated accessibility violations…; ComparisonPage.test.tsx:has no automated accessibility violations…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-RESULT-033] Comparación: veredicto de cuatro cifras, una sola acción primaria, técnico cerrado
- **Regla**: El `h1` del veredicto dice «Entre las simulaciones con resultado, Primera terminó con más saldo y se alcanzó la meta»; exactamente cuatro cifras (Saldo final más alto, Cambio respecto del inicio, Sorteos jugados, ¿Alcanzó la meta?); aviso «El saldo no equivale a ganancia o pérdida…»; «Volver a simulaciones» es terciario; hay un solo `.btn-primary` («Ver detalle de Primera»); la tabla con ROI neto y Caída máxima del saldo vive en «Detalles técnicos · comparación» cerrado.
- **Fuente**: ComparisonPage.test.tsx:leads with a four-figure verdict while technical comparison stays closed
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-034] Comparación honesta: N/M del servidor, orden pedido, sin ranking ni afirmaciones
- **Regla**: «Comparación incompleta · 1/2 terminadas» / «completa · 2/2» usa N/M del servidor; las filas conservan el orden pedido; ausentes → «Sin dato»; ejecución distinta de desenlace; no aparece «mejor estrategia», «probabilidad de éxito» ni «exportar»; la tabla va en región `overflow-x-auto`; no se crean experimentos ni se pide replay de ejecuciones sin resultado.
- **Fuente**: ComparisonPage.test.tsx:uses server N/M and delta… / treats two completed runs as complete…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-RESULT-035] Columna de delta rotulada y caveat cerca de la tabla; lenguaje neutro de origen
- **Regla**: Columna «Cambio respecto del inicio»; caveat junto a la tabla; no aparece «Resultados históricos sobre datos ya investigados»; se rotulan «Historial»/«SHA-256 historial» en legado y, en perfil sin tipo de fuente, «Datos de origen»/«SHA-256 de datos de origen»/«Evolución comparada · fechas guardadas» (sin «Resultados históricos», «fechas históricas»).
- **Fuente**: ComparisonPage.test.tsx:labels the delta column… / uses neutral dataset language when profile source kind is unavailable
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-RESULT-036] Comparación de lotes v5: estrategias congeladas, métricas guardadas y continuidad local
- **Regla**: Orden congelado (Frozen A/B/C); fila A con saldo, neto, ROI, retorno por apostado y caída máxima en formato de perfil; B «Cancelado» y «Sin dato»; C «Con error» con su error local; «Definiciones congeladas» con `id · revisión N · SHA-256`; límites efectivos guardados; el gráfico usa índice local de apuesta; solo se pide una trayectoria (la ejecución con resultado) y ningún replay.
- **Fuente**: ComparisonPage.test.tsx:shows frozen ordered strategies, saved server metrics…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-RESULT-037] Filas no terminales (v5/held/failed) sin resultado y fuera del gráfico
- **Regla**: Con todas las filas pendientes: «Comparación incompleta · 0/3 terminadas», estado «En curso», «Sin dato» en las filas, mensaje `role=status` «Todavía no hay apuestas guardadas cargadas para graficar.» y ninguna llamada a trayectoria ni replay; `held/failed` en perfil muestran «Sin dato» y no EUR 99.00.
- **Fuente**: ComparisonPage.test.tsx:keeps all nonterminal v5 rows resultless… / shows %s with no fabricated result or replay
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-038] Comparación de perfiles Q80/Audaz/recuperación sin supuestos de apuesta plana
- **Regla**: La tabla muestra `EUR 99.00`, `-EUR 1.00`, «Límite de sesión», sorteos jugados y transcurridos; «Perfil EUR: 1 de 1 apuestas»; se pide trayectoria `(id,0,500)`; no se crea experimento.
- **Fuente**: ComparisonPage.test.tsx:compares completed cycling… / compares schema-3 Audaz…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-RESULT-039] Trayectorias acotadas cargadas automáticamente y reintento por serie
- **Regla**: Se cargan trayectorias completas acotadas sin botón «Cargar más»; una serie con reducción dice «Primera: 4 de 1001 apuestas… reducción»; una que falla muestra «No se pudo cargar la trayectoria de Segunda» con «Reintentar trayectoria de Segunda» sin borrar la otra; enlace «Apuesta 1001» a `?run=0&bet=1000&from=comparison`; la segunda ejecución completada también pide su trayectoria.
- **Fuente**: ComparisonPage.test.tsx:loads complete bounded trajectories automatically and retries… / treats two completed runs as complete…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-RESULT-040] Selección oculta y contexto se preservan al volver del detalle; ejecución inválida cae con honestidad
- **Regla**: Ocultar serie (checkbox) se conserva tras ir a «Detalle de Segunda» (`?run=1&from=comparison`) y «Volver a comparación»; `run=999` muestra «Esa ejecución no existe» y cae a la ejecución 1.
- **Fuente**: ComparisonPage.test.tsx:preserves hidden selection and loaded context on targeted detail return…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

---

## 6. F-LIST — Listados, datos, estrategias, ajustes y cola

Fuentes: `ExperimentsPage.test.tsx` («EXP»), `DataTable.test.tsx`, `ConfirmDialog.test.tsx`, `DataPage.test.tsx` («DAT»), `DataPageHistory.test.tsx` («HIS»), `ProfileEditor.test.tsx` («PED»), `ConfigurationsPage.test.tsx` («CFG»), `SettingsPage.test.tsx` («SET»), `QueueDrawer.test.tsx` («QD»), `QueueProvider.test.tsx`, `StrategyEditor.test.tsx`.

### 6.1 Listado de simulaciones (ledger)

### [F-LIST-001] Estados de carga: texto de estado y esqueleto estático
- **Regla**: Antes de la primera respuesta se muestra `role=status` «Cargando simulaciones…» con filas de esqueleto y sin tabla.
- **Fuente**: ExperimentsPage.test.tsx:shows a loading state… / renders static skeleton rows…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-LIST-002] Vacío de primera ejecución enseña y posee la única acción primaria
- **Regla**: Con cero simulaciones se explica «Las simulaciones muestran cómo se comportan tus estrategias con datos históricos…»; hay un solo enlace «Nueva simulación» (`/experimentos/nuevo`, `ledger-button-primary`); el encabezado no lo repite y los filtros no se muestran.
- **Fuente**: ExperimentsPage.test.tsx:shows first-run guidance when there are zero experiments
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-003] Guía de recuperación offline: causa + paso concreto, nunca «se detuvo»
- **Regla**: NetworkError → alerta «No se pudo contactar al servidor» + «Iniciá el laboratorio desde el lanzador y después reintentá», sin «detuvo/detenido»; botón «Reintentar» recarga.
- **Fuente**: ExperimentsPage.test.tsx:shows a disconnected state with NetworkError wording…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-004] Error de servidor distinto de desconexión y conserva la información
- **Regla**: ApiError 500 → «No se pudo cargar el listado» + «Tu información se conserva» con «Reintentar».
- **Fuente**: ExperimentsPage.test.tsx:shows a generic server-error state distinct from disconnection…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-005] Sin coincidencias distinto de vacío; un solo paso siguiente: Limpiar filtros
- **Regla**: «Sin coincidencias» (nunca «Todavía no hay simulaciones») enseña y ofrece exactamente un botón («Limpiar filtros», que vacía la URL y recarga); la acción primaria sigue siendo la del encabezado (un solo enlace «Nueva simulación»).
- **Fuente**: ExperimentsPage.test.tsx:shows a no-matches state… / clears the filters from the no-matches state…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-006] Petición acotada por defecto y columnas veraces
- **Regla**: Primera carga `listExperiments({offset:0,limit:20,sort:"created_at",order:"desc"})`; la columna de corridas cuenta el array real (1 y 2); cabeceras numérica/fecha/estado/acciones con clases `table-numeric/date/status/actions`; «Creado» con `aria-sort`; fecha ausente se muestra «—» con título «Fecha no registrada».
- **Fuente**: ExperimentsPage.test.tsx:requests the bounded default page…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-LIST-007] Nombre largo intacto con ajuste de palabra y scroll horizontal local
- **Regla**: El nombre largo vive en `td.table-name` como enlace a `/experimentos/{id}`; la región «Simulaciones» es `overflow-x-auto`.
- **Fuente**: ExperimentsPage.test.tsx:keeps a long experiment name intact…
- **Categoría**: formato
- **Riesgo si se pierde**: bajo

### [F-LIST-008] Chips de estado: desenlace financiero solo si todas las corridas cerraron igual
- **Regla**: «Meta alcanzada» (`ledger-chip-success`, `data-status-kind=outcome`) solo cuando todas las corridas cerraron con ese desenlace; «En curso» es `ledger-chip-info` de ejecución; completada sin desenlace uniforme nunca afirma meta (no aparece «Ejecución completada» como falsa meta); `ruin`→«Se agotó el capital» `chip-danger`; `limit`→«Ejecución completada» `chip-neutral`.
- **Fuente**: ExperimentsPage.test.tsx:shows status chips… / maps a completed %s outcome to the %s chip
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-009] Resultado neto como cifra monetaria con signo; color solo en la cifra
- **Regla**: Una sola corrida muestra neto `+…837` con `ledger-figure ledger-money-positive` dentro de `td.table-numeric`; una comparación multi-corrida no tiene neto único («—»).
- **Fuente**: ExperimentsPage.test.tsx:shows the net result as a signed money figure…
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [F-LIST-010] Banda de resumen derivada de la página cargada
- **Regla**: El grupo «Resumen de simulaciones» muestra Simulaciones (total), «Con meta alcanzada» y «En curso» con la leyenda «de las 2 mostradas», calculados de la página.
- **Fuente**: ExperimentsPage.test.tsx:derives the stat band from the fetched page…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-011] Una acción de fila (abrir resultado); comparar/eliminar tras menú ghost
- **Regla**: Cada fila ofrece «Abrir resultado de X» (no primario) y un menú «Acciones de X» (ghost) con «Usar como base» (`/experimentos/nuevo?base=id`) y «Eliminar» (ghost); el menú abre por teclado enfocando el primer ítem y Escape restaura el foco al disparador.
- **Fuente**: ExperimentsPage.test.tsx:offers one open-result row action… / opens the row menu by keyboard…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-012] Filtros compactos visibles (≤4 controles) y orden dentro de «Filtros»
- **Regla**: Buscar, estado y limpiar quedan visibles (máximo 4 controles fuera del `details`); «Ordenar por» vive dentro del disclosure «Filtros» cerrado y actualiza la URL (`sort=name`).
- **Fuente**: ExperimentsPage.test.tsx:keeps compact filters visible…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-013] Una sola acción primaria en el ledger poblado
- **Regla**: El listado poblado tiene exactamente un `.ledger-button-primary` («Nueva simulación» a `/experimentos/nuevo`).
- **Fuente**: ExperimentsPage.test.tsx:has exactly one primary action on the populated ledger / links the primary action to the wizard…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-014] Paginación, filtros y orden respaldados por URL contra el servidor
- **Regla**: «Siguiente» pide offset 20 y pone `page=2`; `?name=&status=&sort=&order=&page=` se traducen a `name_contains/status/sort/order/offset`; cambiar un filtro quita `page`; `aria-sort` refleja el orden; valores malformados (`sort=count`, `order=evil`, `page=-1`, `status=bogus`) se sanean a los defaults.
- **Fuente**: ExperimentsPage.test.tsx:paginates forward and back… / uses URL-backed filters… / sanitizes malformed query values…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-LIST-015] La respuesta vieja no pisa a la nueva consulta
- **Regla**: Una respuesta tardía de una consulta anterior se ignora tras un cambio de URL.
- **Fuente**: ExperimentsPage.test.tsx:ignores an older response after a newer URL query succeeds
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-016] ID de cola activo como enlace real y cola consultada una vez
- **Regla**: El `active_id` de la cola enlaza al detalle de esa simulación; `getQueue` se llama una sola vez.
- **Fuente**: ExperimentsPage.test.tsx:sanitizes malformed query values…
- **Categoría**: contrato
- **Riesgo si se pierde**: bajo

### [F-LIST-017] Perfiles en el listado: formato de perfil, una corrida y sin base plana
- **Regla**: Las simulaciones por perfil muestran «Perfil test · 1 posiciones», «Capital USD 100.00 · Meta USD 200.00» y la etiqueta de apuesta («Escalera cíclica Q80…», «Escalera de recuperación»); la cabecera de columna es «Corridas» (no «Estrategias»); «Usar como base» no se ofrece y aparece «No disponible como base» (held/failed/completed); el único ítem es «Eliminar» con foco.
- **Fuente**: ExperimentsPage.test.tsx:lists completed cycling… / labels a recovery run… / shows %s profile with one run…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-018] Lote v5: nombre guardado en identidad, acciones, diálogo y aviso
- **Regla**: El nombre guardado (`display.name`) se usa en enlaces (tabla y cola), «Acciones de X», el diálogo «¿Eliminar la simulación «X»?» («Se elimina de forma permanente.») y el aviso `role=status` «Se eliminó "X".»; borra con `deleteExperiment(id,id)`.
- **Fuente**: ExperimentsPage.test.tsx:uses the saved display name for queue identity…
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [F-LIST-019] Eliminar: confirm_id, anuncio con foco, 409 activo, 404 ya eliminado, foco al cancelar, página previa
- **Regla**: Eliminar exige diálogo (alertdialog con nombre accesible «¿Eliminar la simulación «X»?») y envía `confirm_id` igual al id; al éxito quita la fila y enfoca el aviso de estado; 409 → «activa o en cola» sin quitar la fila; 404 → «ya no existe» y refresca; cancelar (Escape) devuelve el foco al origen; borrar la última fila de una página posterior retrocede a la página anterior.
- **Fuente**: ExperimentsPage.test.tsx:LW10 deletion (4 tests) / moves to the preceding URL page…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-020] Sin violaciones axe en el listado
- **Regla**: El estado listo no tiene violaciones axe.
- **Fuente**: ExperimentsPage.test.tsx:has no axe violations in the ready state
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### 6.2 Primitivas compartidas: DataTable, ConfirmDialog, StrategyEditor

### [F-LIST-021] DataTable: región etiquetada con semántica de tabla, caption y filas
- **Regla**: `region` con el nombre del caption contiene `table` con `caption`, cabeceras (`columnheader`) y filas (cabecera + N); las celdas se renderizan con `render` de cada columna; con cero filas queda solo la cabecera sin lanzar.
- **Fuente**: DataTable.test.tsx:renders a labeled region… / renders each row's cells… / renders an empty body…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-022] DataTable: scroll local etiquetado, ajuste por palabra y campos compactos
- **Regla**: La región es `data-table-region overflow-x-auto` con tabla `w-full` (no `min-w-max`); CSS: `th` con `white-space: nowrap`, `td` con `overflow-wrap: break-word` (nunca `anywhere`), `.table-date` y `.table-numeric` con `nowrap`; el contenido largo no se altera.
- **Fuente**: DataTable.test.tsx:keeps long content in a labeled local scroll region… / lets the table flex…
- **Categoría**: formato
- **Riesgo si se pierde**: bajo

### [F-LIST-023] DataTable: acciones operables por teclado; reglas hairline con transición de 150ms
- **Regla**: Tab llega primero a la región de scroll (tabIndex 0) y luego a las acciones, que Enter activa; la región usa `border-border` sin `rounded`/`shadow`; filas con `border-b border-border transition-colors duration-150 hover:bg-surface`; cabeceras `uppercase tracking-[0.08em]`; sin violaciones axe.
- **Fuente**: DataTable.test.tsx:keeps row actions reachable… / draws hairline rules… / has no axe violations
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: medio

### [F-LIST-024] ConfirmDialog: alertdialog modal etiquetado, foco inicial y trampa de foco
- **Regla**: Cerrado no renderiza; abierto es `alertdialog` con `aria-modal="true"` y nombre accesible = título; el foco entra en el diálogo (en «Cancelar»); Tab/Shift+Tab ciclan entre «Cancelar» y «Eliminar».
- **Fuente**: ConfirmDialog.test.tsx:renders nothing when closed / is labelled and marked as a modal… / moves focus inside… / traps Tab focus…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-025] ConfirmDialog: Escape cancela, devuelve el foco, no roba foco al re-render e inerta la raíz
- **Regla**: Escape llama `onCancel` una vez y devuelve el foco al disparador (incluso si `inert` lo desenfoca: se captura antes); un re-render del padre con un `onCancel` nuevo no vuelve a robar el foco; el contenedor `#root` recibe `inert` mientras está abierto y lo pierde al cerrar.
- **Fuente**: ConfirmDialog.test.tsx:closes on Escape… / returns focus… / keeps focus stable across a parent re-render… / captures the root trigger before native inert… / marks the app root inert…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-026] StrategyEditor: etiquetas mapeadas, valores enum conservados, ayuda de apuesta anunciada
- **Regla**: El selector muestra «Un sistema de selección»/«Selección al azar reproducible» pero conserva `system`/`random`; la apuesta tiene descripción accesible «Importe base constante por número.» (`strategies.0.staking.help`); con error la descripción une ayuda + error sin referencias colgantes y marca `aria-invalid`; usa `ledger-block` y no `.ledger-control`; un error `components.N` sin campo se asocia a «Sistema N+1» con `aria-invalid` y `aria-describedby`.
- **Fuente**: StrategyEditor.test.tsx (3 tests)
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### 6.3 Biblioteca de estrategias (Configuraciones)

### [F-LIST-027] Biblioteca opcional y reutilizable: Usar secundario, Editar/Eliminar terciarios, una primaria
- **Regla**: «Estrategias» enmarca la biblioteca como opcional («Guardá un método para reutilizarlo.»); «Usar» enlaza a `/experimentos/nuevo?configuration=id` (`btn-secondary`); Editar y Eliminar son `btn-tertiary`; solo hay un `.btn-primary`; Eliminar abre alertdialog.
- **Fuente**: ConfigurationsPage.test.tsx:frames saved strategies as an optional reusable library / lists a bounded page, offers use and edit…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-028] Vacío que enseña un solo paso; buscar y paginar ocultos cuando está vacía
- **Regla**: Vacío → «La biblioteca es opcional; guardá un método para reutilizarlo.» con «Crear estrategia guardada»; sin cuadro de búsqueda ni navegación de páginas.
- **Fuente**: ConfigurationsPage.test.tsx:hides search and pagination while the library is empty / shows empty, disconnected and retry states honestly
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-029] Recuperación distinta para catálogo y para estrategias guardadas
- **Regla**: Desconexión → alerta «contactar al servidor» con «Volver a cargar las estrategias guardadas»; fallo de catálogo → «necesitan este catálogo» con «Volver a cargar el catálogo» (que desaparece al recargar).
- **Fuente**: ConfigurationsPage.test.tsx:shows empty, disconnected and retry states honestly / distinguishes recovery for the catalog and saved strategies
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-030] Búsqueda local de página distinta de biblioteca vacía
- **Regla**: Buscar sin coincidencias muestra `role=status` «No hay estrategias con ese nombre» (no «Todavía no hay…»), no recarga (`listConfigurations(0,20)` una vez) y «Mostrar todas las estrategias de esta página» limpia el campo.
- **Fuente**: ConfigurationsPage.test.tsx:keeps page-local search distinct from an empty library
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-031] Edición sucia no se descarta sin confirmación
- **Regla**: Cancelar edición con cambios conserva el borrador; navegar abre alertdialog («Seguir editando») y la ruta no cambia.
- **Fuente**: ConfigurationsPage.test.tsx:does not discard a dirty edit on cancel or navigation without confirmation
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-032] Fila guardada: orden DOM, fila de datos de ancho completo, acciones que envuelven
- **Regla**: `li.saved-strategy-row` tiene un enlace (Usar) y botones «Editar X», «Eliminar X» en ese orden; CSS: `grid-template-columns: minmax(0, 1fr)` y `.btn` con `max-width: 100%`.
- **Fuente**: ConfigurationsPage.test.tsx:keeps saved data and actions in DOM order…
- **Categoría**: formato
- **Riesgo si se pierde**: bajo

### [F-LIST-033] Etiquetas planas y nombres distintos (biblioteca vs estrategia)
- **Regla**: Se muestran «Un sistema de selección» y «Plana»; «Nombre guardado» (biblioteca) y «Nombre de la estrategia 1» son campos distintos; guardar edición llama `updateConfiguration(id, nombre, estrategia)`.
- **Fuente**: ConfigurationsPage.test.tsx:lists a bounded page, offers use and edit…
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-LIST-034] Borrador inválido se rechaza localmente; 422 se mapea a campo sin perder el borrador
- **Regla**: Guardar vacío no llama `createConfiguration`; un 422 con `body.strategy.name` muestra el detalle del servidor y marca `aria-invalid` en el nombre de la estrategia conservando lo escrito.
- **Fuente**: ConfigurationsPage.test.tsx:rejects invalid drafts locally and maps server 422 fields…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-035] No hay segundo guardado en vuelo
- **Regla**: Durante un guardado el botón y el nombre quedan deshabilitados, solo hay un `updateConfiguration`; al terminar `role=status` «actualizada».
- **Fuente**: ConfigurationsPage.test.tsx:prevents a second save and changes during an in-flight request
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-036] Eliminar estrategia guardada: confirmación con id exacto; errores honestos
- **Regla**: alertdialog «¿Eliminar la estrategia guardada «X»?» con «resultados de experimentos anteriores se conservan»; Escape no elimina y devuelve el foco al botón; NetworkError → «Sin respuesta del servidor» sin falso éxito; 404 se trata sin mostrar «eliminada»; `deleteConfiguration(id,id)`.
- **Fuente**: ConfigurationsPage.test.tsx:deletes only after confirmation with exact ID…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-037] El foco permanece en el estado de éxito tras borrar de forma asíncrona
- **Regla**: Tras borrar, «Estrategia eliminada. Los resultados se conservan.» (`role=status`) recibe el foco y lo conserva mientras la lista recarga, incluida la recuperación de última página («Página 1 · 20 en total»); `document.activeElement` nunca es `body`.
- **Fuente**: ConfigurationsPage.test.tsx:keeps focus on the success status… / keeps success focus through asynchronous last-page recovery…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### 6.4 Datos: perfiles, importación e historiales

### [F-LIST-038] Perfiles de juego primero; crear perfil visible sin disclosure avanzado
- **Regla**: La página ordena Perfiles de juego (`#perfiles`) → Biblioteca de historiales (`#historiales`) → Importar historial → «Más formas de importar»; «Crear perfil de juego» es visible; la importación de archivos queda en un disclosure técnico cerrado.
- **Fuente**: DataPage.test.tsx:shows profile creation before import…; DataPageHistory.test.tsx:shows Perfiles, Historiales, Importar and advanced options in task order
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-039] Vacío de historiales: acción directa de importar; crear perfil en contexto como primaria
- **Regla**: Biblioteca vacía → `role=status` «Todavía no hay historiales guardados» con enlace «Importar historial» a `#history-import-title` y pasos «Cómo importar el primer historial»; sin perfil guardado, importar ofrece «Crear perfil de juego» (`btn-primary`) y enlace «Ver Perfiles de juego» a `#perfiles`.
- **Fuente**: DataPage.test.tsx:gives the empty history library a direct import action / offers profile creation in context… / makes the empty-state create-profile actions primary; DataPageHistory.test.tsx:keeps Historiales before Importar and gives first-import guidance when empty
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-040] Reintento de perfiles en ambas secciones
- **Regla**: Si falla la carga de perfiles se ofrece «Reintentar perfiles» en las dos secciones y reintentar vuelve a pedir y los quita.
- **Fuente**: DataPage.test.tsx:offers a retry for failed profile loads in both sections…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-041] Importación por archivo (CSV/JSON): solo perfiles persistidos; bytes originales con contexto explícito
- **Regla**: Las plantillas parciales del catálogo no son opción (aviso «plantillas de catálogo son parciales»); la vista previa envía `raw_base64`, formato, mapeo de columnas, fuente (id/tipo/revisión/procedencia), reloj (`iana` con zona o `naive_legacy` con `zone:null`) y perfil; el mapeo de posiciones sigue la cantidad de posiciones del perfil.
- **Fuente**: DataPage.test.tsx:uses persisted profiles only and sends original bytes… / requires deliberate format and clock choices and supports JSON…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-LIST-042] Pasos y confirmación de importación: vista previa → confirmar con hash esperado
- **Regla**: Tras la vista previa válida («Filas leídas: 2 · Duplicados: 1», «Importar guarda datos, no ejecuta ni calcula pagos.») «Confirmar y guardar importación» llama `promoteImport({...preview, expected_dataset_sha256: hash})`; el resultado «Importación guardada» muestra la identidad canónica SHA-256 solo en detalles técnicos.
- **Fuente**: DataPage.test.tsx:uses persisted profiles only… / selects a newly registered profile…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-043] Vista previa inválida o con hash inconsistente bloquea la promoción
- **Regla**: Vista previa con errores muestra «Fila 2: …» (y «Fila 2 · date» en técnico) y deja «Confirmar y guardar importación» deshabilitado; una respuesta «promotable» sin hash de 64 hex válido también bloquea; nunca se llama `promoteImport`.
- **Fuente**: DataPage.test.tsx:shows invalid preview and blocks promotion… / rejects an inconsistent promotable response…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-044] Registrar un perfil nuevo lo selecciona e invalida la vista previa anterior
- **Regla**: Tras registrar un perfil, «Perfil guardado completo» pasa a `new-profile@1`, la vista previa previa desaparece, las columnas de posición se ajustan (solo pos1) y la siguiente vista previa usa el perfil nuevo.
- **Fuente**: DataPage.test.tsx:selects a newly registered profile for import and invalidates an earlier preview
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-045] Cambio de contexto: la vista previa nueva gana; el finalizador viejo no limpia el estado ocupado
- **Regla**: Con una vista previa colgada, cambiar un campo permite generar otra; la respuesta vieja no se publica ni libera el estado «Validando archivo…» de la nueva; cambiar el archivo oculta «Confirmar…».
- **Fuente**: DataPage.test.tsx:allows a fresh preview after a context change while the old request hangs…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-046] Promoción pendiente: bloqueada, sin doble envío y sin confirmación falsa
- **Regla**: Con una promoción en vuelo (doble clic) solo hay un `promoteImport`; controles y «Generar vista previa» quedan deshabilitados; se avisa «esperá la respuesta» y no se muestra «Importación guardada» hasta que resuelva.
- **Fuente**: DataPage.test.tsx:keeps a pending promotion locked and honestly unconfirmed…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-047] Promoción: 409 de cuota limpia la vista previa; duplicado explícito; red incierta sin reintento automático
- **Regla**: 409 → alerta «no hay espacio» enfocada y se retira la confirmación; un resultado duplicado muestra «Historial ya guardado» con «otro archivo de origen» y hashes retenido/enviado en técnico; NetworkError → «No se pudo contactar al servidor para guardar el archivo» + «Iniciá el laboratorio… y volvé a intentar», una sola llamada y sin botón de reconfirmar.
- **Fuente**: DataPage.test.tsx:reports 409 quota/conflict… / does not assume an uncertain network promotion failed…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-048] Validación de importación: límite de 2 MiB, disclosure se abre, foco al primer campo inválido
- **Regla**: Un archivo >2 MiB no se lee ni se envía: alerta «2 MiB», foco y `aria-invalid`/`aria-describedby` en el campo de archivo; si el disclosure colapsado oculta un campo inválido se abre manteniendo los valores escritos y el foco va al primer campo inválido real (p. ej. «Revisión o corrección», no el primero del formulario) y su `aria-invalid` se limpia al editarlo.
- **Fuente**: DataPage.test.tsx:rejects over-2-MiB file… / opens a collapsed advanced disclosure on validation failure… / points at the first field that fails a later check…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-049] Importación de historial canónico: metadatos para confirmar, Blob original y biblioteca reutilizable
- **Regla**: Al subir `history.json` se muestran los metadatos («Juego: Juego», zona horaria); hay que elegir «Reglas del juego» y marcar «Confirmo la fuente» y «Confirmo la zona horaria»; la vista previa recibe el Blob original, el listado de perfil, `origen` y `zona_horaria`; tras «Confirmar y guardar historial» aparece «Historial guardado.» y la biblioteca muestra «Historial · 1 sorteos», «Fuente: operador-local» y enlace «Usar este historial» a `/experimentos/nuevo/sesion?dataset_sha256=…`.
- **Fuente**: DataPageHistory.test.tsx:shows metadata for confirmation, uploads original Blob bytes…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-LIST-050] Confirmación explícita exacta; el botón explica por qué no está disponible
- **Regla**: Sin confirmar fuente y zona se alerta «Confirmá la fuente y la zona horaria» y no se pide vista previa; el botón «Importar historial» está deshabilitado con descripción accesible (primero «archivo», luego «perfil»); cada checkbox está en un `label.control-choice`.
- **Fuente**: DataPageHistory.test.tsx:requires exact explicit metadata confirmation… / wraps each confirmation in a control-choice label…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-051] Una sola acción primaria: Importar historial → Confirmar y guardar historial
- **Regla**: Inicialmente el único `.btn-primary` es «Importar historial»; tras la vista previa lo es «Confirmar y guardar historial» y «Importar historial» desaparece; crear perfil sigue disponible.
- **Fuente**: DataPageHistory.test.tsx:keeps profile creation available while confirmation replaces the history import action
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-052] Biblioteca: paginada, estados de carga/error sin confundir con vacío y orden estable
- **Regla**: «1–20 de 21» con «Siguiente» que pide offset 20 sin cambiar el perfil; mientras carga: `role=status` «Cargando historiales guardados…» sin «Todavía no hay…» y las secciones permanecen; el fallo muestra «No se pudo cargar la biblioteca» con «Reintentar biblioteca» (nunca como vacío); los controles de paginación siguen montados mientras carga la página; el orden Biblioteca → Importar se mantiene tras la primera importación.
- **Fuente**: DataPageHistory.test.tsx:pages through the saved dataset library… / retries a failed library request… / keeps task sections in place… / does not present loading as an empty library… / keeps cause and retry… / keeps the decided order after the first import… / keeps the pagination controls mounted…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-053] Respuestas obsoletas y desmontaje en importación de historial
- **Regla**: Una lectura de archivo reemplazada y una vista previa/promoción pendientes tras desmontar no publican estado ni refrescan la biblioteca ni promueven; solo cuenta la vista previa más nueva si cambia el contexto en vuelo; cambiar el vínculo de perfil invalida la vista previa antes de promover; la lectura de archivo pendiente conserva sus metadatos si cambia el perfil.
- **Fuente**: DataPageHistory.test.tsx:keeps file metadata when the profile changes… / ignores a superseded file read… / does not publish a promotion response… / keeps only the newest preview… / invalidates a preview when the profile binding changes…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-054] 409 de vínculo en vista previa y bloqueo tras respuesta incierta de promoción de historial
- **Regla**: Un 409 en la vista previa muestra «Los datos cambiaron o no hay espacio» y no promueve; una promoción con respuesta incierta (NetworkError) avisa «No se pudo contactar al servidor» + «Comprobá el estado desde la cola», bloquea «Importar historial» y no reintenta (una sola llamada).
- **Fuente**: DataPageHistory.test.tsx:surfaces backend binding mismatch… / locks promotion after an uncertain response instead of retrying
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-055] Sin enlace de continuación si el perfil guardado ya no permite ejecutar
- **Regla**: Con `profile_execution.ready=false` no se ofrece «Usar este historial» y se explica que las reglas «ya no están guardadas».
- **Fuente**: DataPageHistory.test.tsx:offers no continuation link and explains why…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-056] Editor de perfiles: Quiniela 80 editable por defecto, detalles técnicos cerrados, leyendas de escala
- **Regla**: Al abrir viene prellenado (`quiniela-80`, revisión 1, universo 100, 3 posiciones, repeticiones sí, premios 60/10/5, DOP, 0 decimales con ayuda «0 = sin decimales.», apuesta mínima 1 con nota «sin devolución adicional de la apuesta»); «Detalles técnicos» (ID/revisión) cerrado.
- **Fuente**: ProfileEditor.test.tsx:opens with an editable Quiniela 80 profile ready to register
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-057] Editor de perfiles: bloques de ≤4 decisiones y controles con estilo
- **Regla**: Cuatro bloques `ledger-block` (Juego, Moneda y apuestas, Apuestas, Límites por sorteo) con 2/3/2 controles en los bloques 2–4; todo input/select lleva `control` o `ledger-control`; hay un campo de premio por posición (3 por defecto).
- **Fuente**: ProfileEditor.test.tsx:groups decisions into bounded ledger blocks and styles every native control
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-LIST-058] Editor de perfiles: documentos de 1/3/5 posiciones en unidades menores; digest del servidor
- **Regla**: Guardar envía `schema_version 1`, `profile_id`, `revision`, `positions`, `currency`, `scale 2` y montos convertidos a unidades menores (0.25→25, 2.00→200, 10.00→1000), `best_rule: maximum-payout/v1`, multiplicadores de igual longitud; el digest `profile_sha256` lo aporta el servidor (no se calcula).
- **Fuente**: ProfileEditor.test.tsx:creates %i position documents with explicit money policy and server-derived digest
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-LIST-059] Plantilla parcial: solo campos documentados; faltantes obligatorios
- **Regla**: Una plantilla solo prellena sus campos conocidos (posiciones 3, premio `60/1`, aviso «1 unidad(es) sin escala»); apuesta mínima queda vacía; guardar sin completar da alerta («ID:…», luego «Incremento…») sin POST.
- **Fuente**: ProfileEditor.test.tsx:prefills only documented template fields and requires missing financial fields
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-060] Perfil: valores faltantes, fraccionarios o sobre el entero seguro se rechazan antes del POST
- **Regla**: Premio `1/3` → «pagos enteros»; `9007199254740992` → «límite»; sin POST.
- **Fuente**: ProfileEditor.test.tsx:rejects missing fractional and oversafe values before POST
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-061] Perfil: versión repetida local; 409 cuota/conflicto y 422 mapeados; nunca reintento automático
- **Regla**: Mismo ID+revisión existente → «Ese ID y revisión ya existen» sin POST; 409 cuota → «No hay espacio»; 409 conflicto → «revisión nueva»; 422 → «El servidor rechazó el perfil» con «Código HTTP: 422» en técnico; cada intento es manual.
- **Fuente**: ProfileEditor.test.tsx:rejects same version locally, reports quota/conflict/422 and never auto-retries
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-062] Perfil: abre disclosure del host colapsado y enfoca el primer campo inválido real
- **Regla**: Si el host `details` está cerrado al fallar la validación se abre, se conservan valores, el foco va al primer campo inválido con `aria-invalid` y `aria-describedby` = id de la alerta, y se limpia al editar.
- **Fuente**: ProfileEditor.test.tsx:opens a collapsed host disclosure… / focuses the field that actually fails…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-063] Perfil: bloqueo mientras el registro está pendiente
- **Regla**: Doble clic en «Guardar perfil» produce un solo `registerProfile`; controles deshabilitados, aviso «esperá la respuesta», `onBusyChange(false)` y un solo `onRegistered` al resolver.
- **Fuente**: ProfileEditor.test.tsx:holds the pending register lock until the single response completes
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### 6.5 Ajustes (capacidad primero)

### [F-LIST-064] Capacidad primero: cuota lógica, espacio libre y diagnóstico plegado; una acción primaria
- **Regla**: Mientras carga: `role=status` «Cargando capacidad y límites…»; luego el encabezado «Capacidad» (con «5 GiB», «1.5 KiB» y `progressbar` «Cuota lógica utilizada») precede a «Detalles técnicos» (cerrado) donde viven bytes exactos con separador de miles, artefactos de perfiles/datasets, SQLite, espacio en disco libre, `iniciar-laboratorio.bat`, Ctrl+C, fuentes y host:puerto; no aparece «LW16»; solo hay un `.btn-primary`; se aclara que el límite no es el espacio libre en disco.
- **Fuente**: SettingsPage.test.tsx:loads the actual view, distinguishing logical quota, physical files and free disk
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-065] Ajustes: desconexión distinta de error genérico; no promete conservar información
- **Regla**: NetworkError → «No se pudo contactar al servidor» + «Comprobá que el laboratorio siga abierto y reintentá» sin «Tu información se conserva»; 500 → «No se pudieron cargar los ajustes»; «Reintentar» recupera.
- **Fuente**: SettingsPage.test.tsx:distinguishes disconnected from generic errors and retries
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-066] Límite de almacenamiento: entero positivo ASCII en bytes, enfoque y sin PUT inválido
- **Regla**: Se rechazan `""`, `0`, `01`, ` 5`, `+5`, `-1`, `1.5`, `1e3`, dígito ancho `９` y `9223372036854775808` con foco, `aria-invalid`, mensaje «Ingresá un entero en bytes» y descripción accesible (ayuda + mínimo + error); nunca se llama `updateSettings`.
- **Fuente**: SettingsPage.test.tsx:rejects invalid byte input %j with focus and no PUT
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-067] Guardado: int64 máximo exacto como string, sin doble guardado, confía en la respuesta PUT
- **Regla**: `updateSettings("9223372036854775807")` una sola vez; botón «Guardando…» y campo deshabilitados; al resolver se usa la vista completa del servidor y aparece «Guardado» con el valor actualizado.
- **Fuente**: SettingsPage.test.tsx:sends max int64 exactly as a string…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-068] Fallos de guardado conservan el borrador (422, 409 bajo uso, red incierta, 403, 409 solo-lectura)
- **Regla**: 422 → «El servidor rechazó el límite» con foco; 409 → «El límite no puede ser menor que el uso actual»; red → «Puede que se haya guardado»; 403 → «El servidor rechazó el origen»; 409 de entorno → «El entorno fija el límite y no se puede cambiar desde la web»; el valor tecleado persiste.
- **Fuente**: SettingsPage.test.tsx:keeps the draft after 422, 409 below usage, and network failure… / does not block clean navigation and explains 403 and a raced read-only 409…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-069] Cuota de entorno es solo lectura; la preferencia persistida se distingue
- **Regla**: Con `source=environment`, `writable=false` se muestra «Variable de entorno», la preferencia persistida aparte, y no hay campo ni «Guardar límite».
- **Fuente**: SettingsPage.test.tsx:shows an environment quota as read-only, with persisted preference distinct
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-070] Formato de bytes exacto con agrupación es-DO; capacidad sin jerga; entrada cruda ASCII
- **Regla**: int64 máximo y uso agregado se muestran exactos en técnico (`9,223,372,036,854,775,807 bytes`); en la sección de capacidad se usan unidades legibles («8,388,608 TiB») y no aparecen `bytes`, `SHA-256` ni `JSON`; el campo de entrada conserva el entero crudo ASCII.
- **Fuente**: SettingsPage.test.tsx:presents max int64 and aggregate usage exactly with es-DO grouping…
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-LIST-071] La cuota no puede ser menor que el uso agregado de admisión; igualdad permitida
- **Regla**: 1500 (por debajo del uso agregado 1,536) se rechaza con «Mínimo 1.5 KiB (1,536 bytes)» y mensaje de uso actual; 1536 se acepta y limpia el error.
- **Fuente**: SettingsPage.test.tsx:rejects a quota above historical bytes but below aggregate admission usage, then allows equality
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-LIST-072] Capacidad restante y progreso acotados desde el uso agregado
- **Regla**: El restante exacto (p. ej. «1 KiB») y el progreso (60%) salen del agregado; si el uso supera el límite el restante es «0 bytes», el progreso 100 y se avisa «Uso superior al límite por 336 bytes».
- **Fuente**: SettingsPage.test.tsx:shows exact remaining capacity… / clamps remaining and progress…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-073] Respuestas solo-históricas se marcan como incompletas, sin afirmar un agregado
- **Regla**: Un servidor que no informa el total muestra «Uso incompleto: este servidor no informa el total», sin progressbar ni «Artefactos de perfiles», y bloquea el guardado de valores bajo el uso histórico.
- **Fuente**: SettingsPage.test.tsx:marks historical-only responses as incomplete…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-074] Advertencia del servidor sin confundirla con recuperación de disco
- **Regla**: `warning:true` muestra alerta «límite o falta de disco» con el agregado exacto.
- **Fuente**: SettingsPage.test.tsx:warns on the server's quota warning…
- **Categoría**: copy
- **Riesgo si se pierde**: medio

### [F-LIST-075] Borrador sucio protege navegación y unload; «Actualizar estado» conserva el borrador
- **Regla**: Editar registra `beforeunload`; navegar abre alertdialog («Seguir editando» / «Salir sin guardar») y la ruta no cambia hasta confirmar; «Actualizar estado» recarga sin pisar el borrador (incluso si pasa a solo lectura: aviso «Borrador no guardado:…»); navegación limpia no bloquea.
- **Fuente**: SettingsPage.test.tsx:guards dirty navigation and unload… / preserves an unsaved draft when a refresh changes quota to environment read-only / does not block clean navigation…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-076] Flujo de credenciales de agente: cerrado, sin secretos y solo bajo petición explícita
- **Regla**: «Acceso para agentes» es un `details` cerrado; no se consulta nada ni existe el campo «Credencial de agente» hasta pulsar «Consultar credencial de agente» (una vez); la advertencia «No compartas esta credencial de acceso a la API.» solo es visible al abrir.
- **Fuente**: SettingsPage.test.tsx:keeps agent access closed, secret-free, and retrieves a credential only after explicit request
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-077] Token enmascarado hasta mostrarlo; copiar solo por acción; nada en storage ni en el estado
- **Regla**: El token se muestra en `type=password`; «Mostrar/Ocultar credencial» alterna; «Copiar credencial» llama `clipboard.writeText(token)` solo al pulsar; el aviso «Credencial copiada al portapapeles» no contiene el token; no se guarda en `localStorage`/`sessionStorage`; «Ocultar y borrar credencial» la elimina.
- **Fuente**: SettingsPage.test.tsx:keeps a retrieved token masked until revealed and copies only on explicit action
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-078] Portapapeles denegado: copia manual con texto revelado y seleccionado; foco restaurado
- **Regla**: Si el portapapeles falla: alerta «seleccioná y copiá el texto mostrado manualmente», el campo pasa a `text`, recibe foco y selección completa (0..longitud); al borrarla el foco vuelve a «Consultar credencial de agente».
- **Fuente**: SettingsPage.test.tsx:explains clipboard denial… / restores focus to credential consultation after clearing…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-079] Credencial: respuestas descartadas o tras desmontar no se publican
- **Regla**: Con «Consultando credencial…» y «Cancelar» la respuesta tardía no se muestra (el foco vuelve al disparador); tras desmontar la pantalla tampoco; el token nunca aparece en el DOM.
- **Fuente**: SettingsPage.test.tsx:ignores credential responses dismissed while pending / ignores a credential response after the settings screen unmounts
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-080] Ajustes sin violaciones axe
- **Regla**: La pantalla cargada no tiene violaciones axe.
- **Fuente**: SettingsPage.test.tsx:has no axe violations in loaded settings
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### 6.6 Cola de cálculo (QueueProvider y QueueDrawer)

### [F-LIST-081] Un solo sondeo acotado compartido por Shell y cajón; páginas independientes
- **Regla**: Shell y cajón comparten un único `getQueue` por página; los totales de pendientes y detenidos se paginan de forma independiente con una sola petición («Siguiente cola» → `getQueue(20,20)`), y el carril vacío de la página dice «No hay elementos en esta página».
- **Fuente**: QueueProvider.test.tsx:requests one page for Shell and drawer…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-LIST-082] Se descarta la respuesta de página vieja y se reconcilia una página fuera de rango
- **Regla**: Una respuesta vieja no se muestra; si la cola se encoge, la página fuera de rango se reconcilia a la página 1 («Página 1», «Inspeccionar survivor»).
- **Fuente**: QueueProvider.test.tsx:discards an old page response and reconciles an out-of-range page after queue shrink
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-083] Nunca el carril de fallo junto al de pendiente durante un reintento
- **Regla**: Un fallo muestra «Sin conexión con el servidor» sin «Actualizando…»; durante el reintento se oculta el fallo; el éxito restaura la fila.
- **Fuente**: QueueProvider.test.tsx:never shows the failure lane together with the pending lane while a retry is in flight; QueueDrawer.test.tsx:retains last known state on disconnection…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-084] Desconexión retiene el último estado y no afirma que se detuvo
- **Regla**: Tras perder conexión se conserva la fila `run-1` y se dice «El cálculo puede continuar en el servidor; comprobá el estado desde la cola»; nunca «se detuvo» ni «Esto no detiene».
- **Fuente**: QueueDrawer.test.tsx:retains last known state on disconnection and does not claim a stopped calculation
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-085] Estados llanos de cola; detalles de protocolo plegados
- **Regla**: Los carriles se llaman «En curso», «Esperando», «Detenido»; el texto de protocolo (reintentos/páginas/reinicio) vive en «Detalles técnicos» cerrado; la frase «Pendientes y retenidos se consultan por páginas independientes» no se muestra.
- **Fuente**: QueueDrawer.test.tsx:uses plain queue states and keeps protocol details closed until requested
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-086] Cajón modal: abre bajo demanda, trampa de foco, Escape cierra y devuelve el foco
- **Regla**: Sin dialog hasta abrir; al abrir el foco va al `dialog` «Cola de cálculo»; Escape lo cierra, sin portal residual, y el foco vuelve a «Abrir cola de cálculo»; Escape descarta solo el cajón.
- **Fuente**: QueueDrawer.test.tsx:opens on demand, traps Tab, Escape closes and returns focus… / dismisses only the drawer on Escape…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-087] Confirmación anidada de cancelación absorbe Escape; la solicitud no afirma estado terminal
- **Regla**: «Cancelar run-1» abre alertdialog «¿Cancelar el experimento run-1?» con «resultados ya terminados»; Escape cierra solo la confirmación y devuelve el foco al botón; confirmar llama `cancelJob(id)` y muestra «Solicitud de cancelación enviada» sin afirmar «Cancelado». El foco se restaura en el botón de la fila aun bajo reglas nativas de `inert`.
- **Fuente**: QueueDrawer.test.tsx:nested cancel confirmation absorbs Escape… / restores the held-row Cancelar trigger after nested Escape under native inert focus rules
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-088] Tres carriles: confirmado / incierto / pendiente, una primaria por fila
- **Regla**: Fila `data-lane` = `pending` mientras la solicitud está en vuelo («Actualizando…», sin primaria, sin «Sin conexión» ni «puede haber llegado»); `uncertain` tras un fallo de red («La solicitud puede haber llegado; comprobá el estado desde la cola antes de reintentar») con «Comprobar estado X» como única primaria y «Cancelar X» deshabilitado; filas ociosas: held tiene «Iniciar» primario y «Cancelar» secundario, pending solo «Cancelar» secundario; el cajón tiene una sola `.btn-primary`; las consecuencias largas viven en el diálogo de confirmación, no en la fila.
- **Fuente**: QueueDrawer.test.tsx:names the uncertain lane and the concrete check… / shows the pending lane while a request is in flight…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-089] Cancelar: reenvío solo tras detalle fresco y confirmación explícita; nunca automático
- **Regla**: Tras ack o resultado incierto el botón queda bloqueado; «Reenviar cancelación X» solo existe tras «Comprobar estado X» con detalle fresco y exige «Confirmar reenvío» (cancelar el diálogo no envía); `cancelJob` no se repite sin confirmación.
- **Fuente**: QueueDrawer.test.tsx:requires fresh detail and an explicit confirmed resend for %s pending cancellation
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-090] No-reenvío automático: bloqueo por 409, comprobación fallida y estado terminal
- **Regla**: 409 → «ya no puede cancelarse», botón bloqueado y sin reenvío; una comprobación fallida → «No se pudo comprobar el estado» manteniendo el bloqueo sin habilitar el reenvío; un estado terminal («Estado final confirmado») se libera solo cuando la página de origen de la cola se pone al día; `cancelJob` se llama una vez.
- **Fuente**: QueueDrawer.test.tsx:keeps a 409 rejection locked… / keeps an action locked after a failed explicit recheck… / clears a terminal action only after the originating queue page catches up
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-091] Iniciar un held: sin reenvío si el detalle dice pendiente; reintento solo tras detalle fresco y confirmación
- **Regla**: Si tras un inicio incierto el detalle dice `pending` no se ofrece «Reintentar inicio» y «Iniciar» queda bloqueado; si dice `held`, «Comprobar estado» → «Reintentar inicio X» → «Confirmar reintento» para un segundo `startHeld`.
- **Fuente**: QueueDrawer.test.tsx:does not offer a start resend… / retries uncertain start only after fresh held detail and confirmation
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-092] Bloqueos persisten al paginar 0→20→0, cambiar de ruta y cerrar/reabrir el cajón
- **Regla**: Una acción de inicio o cancelación (ack o incierta) permanece bloqueada tras paginar de ida y vuelta, tras desmontar rutas (lista→detalle→ajustes→lista, con un solo sondeo y un solo envío), tras una solicitud en vuelo y tras cerrar/reabrir el cajón, hasta reconciliar con el detalle.
- **Fuente**: QueueDrawer.test.tsx:retains %s cancellation across actual list→detail→settings→list route unmounts… / retains an in-flight cancellation across route unmount… / does not unlock a held request on page 0→20→0… / does not unlock a pending cancellation… / retains an in-flight action across drawer close and reopen…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-093] Liberación del bloqueo de inicio con estado autoritativo; cancelación incierta bloqueada mientras el detalle no esté disponible
- **Regla**: Tras iniciar, un detalle `pending` o `running` libera el bloqueo de inicio y permite «Cancelar X» (sin «Iniciar»); una cancelación incierta se mantiene bloqueada mientras el detalle falla y se libera solo al ver estado terminal.
- **Fuente**: QueueDrawer.test.tsx:releases a start lock after authoritative %s… / keeps an uncertain cancellation locked while detail is unavailable…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-094] Detalle obsoleto no desbloquea; lecturas de detalle deduplicadas
- **Regla**: Un detalle viejo tras un desbloqueo de inicio y un nuevo bloqueo de cancelación se ignora; mientras una inspección está en vuelo los refrescos de cola no la duplican (`getExperiment` una vez).
- **Fuente**: QueueDrawer.test.tsx:ignores stale detail after a start unlock… / deduplicates detail reads across shared queue refreshes…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-095] Solo los held se inician; nunca «reanudar» el activo interrumpido
- **Regla**: «Iniciar held-1» existe solo en held (no en pending) y llama `startHeld(id)`; no aparece texto «reanudar».
- **Fuente**: QueueDrawer.test.tsx:offers explicit start only on held jobs, never resume…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-LIST-096] Errores de inicio/cancelación en línea, sin filtrar mensajes del backend
- **Regla**: Inicio 404/409/507 → «ya no existe» / «no puede iniciarse» / espacio-cuota; cancelación 404/409 → «ya no existe» / «ya no puede cancelarse», junto a su fila; el mensaje privado del backend nunca se muestra.
- **Fuente**: QueueDrawer.test.tsx:keeps start error %i inline… / keeps cancellation error %i beside its active row
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-LIST-097] Estado de éxito enfocado tras quitar el disparador; expira a los 4s sin robar foco
- **Regla**: Al confirmar una cancelación que elimina la fila, el `role=status` recibe el foco; a los 4 s un estado enfocado persiste (y se borra al mover el foco); uno no enfocado expira sin quitarle el foco al siguiente control; `document.activeElement` nunca es `body`.
- **Fuente**: QueueDrawer.test.tsx:keeps status focused when a confirmed held cancellation removes its trigger / retains focused success status after its four-second expiry… / expires an unfocused success status…
- **Categoría**: accesibilidad
- **Riesgo si se pierde**: alto

### [F-LIST-098] Último fallo no persistido no se describe como estado fallido duradero
- **Regla**: `last_failure.persisted=false` muestra «no se pudo confirmar en el almacenamiento» sin exponer el texto crudo del error.
- **Fuente**: QueueDrawer.test.tsx:does not describe an unpersisted last failure as a durable failed status
- **Categoría**: copy
- **Riesgo si se pierde**: medio

---

## 7. F-UTIL — Utilidades y modelos

### [F-UTIL-001] formatProfileMoney: unidades menores exactas, moneda y escala del perfil
- **Regla**: `formatProfileMoney(12345,"USD",2)="USD 123.45"`, `-5→"-EUR 0.05"`, escala 0 → `"DOP 0"`, escala 6 → `"XTS 0.000001"`, `MAX_SAFE_INTEGER` → `"USD 90,071,992,547,409.91"`; nunca asume RD$ ni redondea.
- **Fuente**: src/lib/profile-display.test.ts:formats exact integer minor units…
- **Categoría**: formato
- **Riesgo si se pierde**: alto

### [F-UTIL-002] formatProfileMoney rechaza lo inseguro
- **Regla**: `RangeError` para enteros por encima de `MAX_SAFE_INTEGER`, no enteros (1.5) y escala no soportada (7).
- **Fuente**: src/lib/profile-display.test.ts:rejects unsafe or non-integral units…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-003] profileOutcome: desenlace y colisiones en español sin inventar resultado
- **Regla**: `limit` + colisiones se rotula «Límite de sesión (límite de sorteos apostados, límite de sorteos transcurridos)»; la colisión de recuperación schema 4 es «Límite de sesión (límite de rondas de recuperación)»; `cancelled` → «Cancelado durante la sesión».
- **Fuente**: src/lib/profile-display.test.ts:labels the schema-4 recovery ladder… / separates saved outcome and collision reasons…
- **Categoría**: copy
- **Riesgo si se pierde**: alto

### [F-UTIL-004] exactMultiplier: racionales exactos sin coma flotante
- **Regla**: `"1.25"→5/4`, `"0.000000000001"→1/10^12`, `"60"→60/1`, `"10/20"→1/2` (reducido).
- **Fuente**: src/lib/profile-input.test.ts:reduces decimal and fractional multipliers…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-005] exactMultiplier rechaza entradas vacías, inválidas, negativas o sobre el límite seguro
- **Regla**: Lanza con `""`, `"1/"`, `"1/0"`, `"1.2/3"`, `"-1"`, `"1e2"`, 13 decimales y `9007199254740992`.
- **Fuente**: src/lib/profile-input.test.ts:rejects missing, invalid, negative and oversafe rational parts
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-006] moneyUnits: dinero humano a unidades enteras a la escala declarada
- **Regla**: `"12.34"@2→1234`, `"0.01"@2→1`, `"1"@6→1_000_000`; rechaza `""`, `"0"`, `"1.001"@2`, notación científica, negativos, `9007199254740992`, `"0.001"@2` y montos que desbordan al escalar (`"1000000000000"@2`).
- **Fuente**: src/lib/profile-input.test.ts:converts human money to exact integer units at declared scale
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-007] wholeNumber: enteros acotados antes de convertir a Number
- **Regla**: `wholeNumber("16","Posiciones",1n,16n)=16`; rechaza `""`, `"0"`, `"17"`, `"1.0"` y `9007199254740992`.
- **Fuente**: src/lib/profile-input.test.ts:enforces bounded integers before conversion to JS Number
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-008] Cursor de replay acotado: clamps y página del índice
- **Regla**: `replayIndex(actual, delta, total)` se satura en `[0, total-1]` (0− →0; 41+1 de 42 →41; 19+1→20); `pageOffset(índice, tamaño)` da el inicio de página (20→20, 39→20); sin resultados el cursor y la página son 0.
- **Fuente**: src/pages/experiments/replay.test.ts (2 tests)
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [F-UTIL-009] Borrador de lote: solo identidades versionadas y entradas editables
- **Regla**: El borrador serializado lleva `version` (BATCH_DRAFT_VERSION), `datasetSha256` y referencias de estrategia `{id,revision,definition_sha256}`; nunca registros/historial/token/archivo; el parseo recupera dataset y referencias.
- **Fuente**: src/pages/new-experiment/batch-model.test.ts:persists only versioned identities and editable inputs…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-010] Borradores mal formados, de versión desconocida o con campos extra se rechazan
- **Regla**: `parseBatchDraft` devuelve `null` para versión 99, hash de dataset inválido y campos desconocidos (p. ej. `accessToken`); no actualiza referencias congeladas.
- **Fuente**: src/pages/new-experiment/batch-model.test.ts:rejects malformed or unknown-version drafts…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-011] Sorteo inicial seleccionado se persiste ligado al dataset; metadatos desajustados se rechazan
- **Regla**: `selectedDraw {datasetSha256,index,draw}` se restaura igual; si el hash no coincide con el del borrador → `null`; si falta → `selectedDraw` nulo.
- **Fuente**: src/pages/new-experiment/batch-model.test.ts:persists a bounded selected draw identity…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-UTIL-012] buildBatchBody: cuerpo cerrado con referencias ordenadas inmutables y condiciones compartidas
- **Regla**: Construye `{schema_version:1, profile:{id,revision,sha256}, dataset_sha256, strategies:[{id,revision,definition_sha256}], conditions:{… capital:100, goal:200 … max_bet_draws:null, end_minute:null, duration_minutes:null}, max_draws, client_request_id}` convirtiendo los campos de texto del borrador a números/`null`.
- **Fuente**: src/pages/new-experiment/batch-model.test.ts:builds the exact closed batch body…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-013] Condiciones iniciales y validación del catálogo legado
- **Regla**: `initialConditions` = capital "2000", meta "2800", `max_bets` "12"; `initialStrategy(1)` = blend 60/40 (transition/cold), cobertura "10"; con nombre, sorteo y semilla válidos no hay errores.
- **Fuente**: src/pages/new-experiment/model.test.ts:starts with the brief's valid financial limits and blended selection
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-UTIL-014] Round-trip de estrategias sin sustituir el nombre de biblioteca; prellenado completo sin mutar la fuente
- **Regla**: `draftFromStrategy`↔`buildStrategy` preserva la estrategia exacta; `draftFromRequest(buildRequest(…))` restaura todos los campos (incluida `max_minutes` y semilla 9007199254740991) y todos los componentes de la mezcla sin redondear, y mutar el borrador no altera el request original.
- **Fuente**: src/pages/new-experiment/model.test.ts:round-trips one library strategy… / prefills every saved request field…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-015] Validación de condiciones: sin decimales, exponentes, negativos, desbordes; meta final > capital
- **Regla**: `integer("1.1"|"1e2"|"-1")` = `null`; `validateConditions` marca `start_draw` fuera de ranking, `capital` "2.5", `max_minutes` "0", `max_bets` "10000001" y `seed` "9007199254740992"; meta ≤ capital da un error que menciona «superar».
- **Fuente**: src/pages/new-experiment/model.test.ts:rejects decimals, exponents, negatives, overflow…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-016] Semilla: máximo entero seguro válido y enviado como número JSON; uno más se rechaza
- **Regla**: `9007199254740991` valida y `buildRequest` lo envía como `number`; `9007199254740992` da error; la semilla ida/vuelta por JSON no pierde precisión.
- **Fuente**: src/pages/new-experiment/model.test.ts:accepts the max safe integer seed… / round-trips the entered seed…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-017] Nombre duplicado: mismo veredicto que el backend para el fixture compartido
- **Regla**: `normalizeStrategyName(a)===normalizeStrategyName(b)` coincide con `duplicate` de cada caso de `backend/tests/fixtures/strategy_name_cases.json` y `validateStrategies` marca `strategies.1.name` exactamente en esos casos.
- **Fuente**: src/pages/new-experiment/model.test.ts:agrees with the backend's duplicate-name verdict…
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [F-UTIL-018] trimName usa el mismo charset explícito que la detección de duplicados
- **Regla**: `trimName` no recorta U+FEFF (BOM) ni U+0085 (NEL) pero sí tabulaciones; `buildRequest` conserva el BOM en el nombre de estrategia y el nombre de la simulación.
- **Fuente**: src/pages/new-experiment/model.test.ts:trims a stored name with the same explicit charset…
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [F-UTIL-019] Estrategias: nombres únicos, 1–5 estrategias, mezcla suma 100 y sistemas distintos
- **Regla**: Nombres duplicados (« Una » vs «una») → único; 6 estrategias → error «1 y 5»; una mezcla cuyos pesos no suman 100 → error en `components` (menciona 100); sistemas repetidos → error en `components.1.system` («distinto»).
- **Fuente**: src/pages/new-experiment/model.test.ts:rejects duplicate names, six strategies, invalid mix sums and repeated systems
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-020] buildProfileRequest: Q80 cíclica explícita sin apuesta fija y exige la capacidad
- **Regla**: Con `"cycling"` y perfil que declara `q80-first-prize-cycling/v1` produce schema 2 con `staking {schema_version:1,capability}` sin `per_number_stake`; sin la capacidad lanza («capacidad»); cobertura 80 lanza.
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:builds explicit Q80 cycling without a fixed stake…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-021] buildProfileRequest base: vínculo del servidor, selector fijo explícito, unidades enteras sin envelope legado
- **Regla**: Produce exactamente `{kind:"profile", schema_version:1, name (recortado), dataset_sha256, profile_id/revision/sha256, entry_policy:"all_rows/v1", conditions (capital 2000.00→200000, meta 2800→280000, settlement, max_elapsed_draws 12, max_bet_draws 6, end_minute/duration_minutes null), selector static-numbers/v1 con números [0,1] y seed/algorithm null, staking flat-per-number/v1 con 1.25→125}`.
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:uses server binding, explicit fixed selector and integer money units…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-022] Audaz genérica (schema 3): sin apuesta fija; cobertura y disponibilidad del servidor
- **Regla**: Con `profile-audaz/v1` produce schema 3 sin `per_number_stake`; cobertura superior a `maximum_compatible_coverage` lanza («hasta 1») y `audaz_compatibility.available=false` lanza («no está disponible»).
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:builds generic Audaz schema 3…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-023] Recuperación schema 4: margen en unidades, rondas y end_mode; cobertura compatible
- **Regla**: Para `cycle` y `stop` produce schema 4 con `target_margin` 12.34→1234, `rounds`, `end_mode` y sin `per_number_stake`; cobertura fuera de la compatibilidad racional («hasta 2»), rondas 10001 («Rondas»), `end_mode` vacío («completar la escalera») o capacidad ausente («capacidad») lanzan.
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:builds schema-4 recovery… / rejects recovery coverage outside server-derived rational compatibility…
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-024] Aleatorio determinista solo con semilla segura y algoritmo explícitos
- **Regla**: `selector:"random"` produce `seeded-random/hash-sha256-v1` con `numbers:null`, `seed` numérico (MAX_SAFE_INTEGER) y `algorithm_version:"hash-sha256-v1"`; la semilla `9007199254740992` lanza («Semilla»).
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:builds deterministic random only with explicit safe seed and algorithm
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-025] Vínculos obsoletos o desajustados, sorteo, capacidades y liquidación no soportados se rechazan
- **Regla**: `matchingDataset` es falso si `profile_sha256` difiere; revisión distinta, sorteo vacío («Sorteo»), sin capacidad de selección fija («selección fija») o liquidación vacía («capacidad») lanzan.
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:rejects stale/mismatched binding, draw, unsupported capability and settlement
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-026] Entradas de admisión inválidas se rechazan (números, incremento, máximo, capital, transcurridos, meta)
- **Regla**: Lanzan: números repetidos o fuera de rango (`0,0`, `0,100`), apuesta por número no múltiplo del incremento (1.26) o sobre el máximo (100.01), capital sobre el entero seguro, sorteos transcurridos vacío, meta ≤ capital.
- **Fuente**: src/pages/new-experiment/profile-model.test.ts:rejects invalid admission inputs
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [F-UTIL-027] Servidor de desarrollo y vista previa enlazados explícitamente a 127.0.0.1
- **Regla**: `server.host` y `preview.host` de Vite son `127.0.0.1`.
- **Fuente**: src/test/vite-dev-server.test.ts:binds the dev server explicitly… / binds the preview server explicitly…
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [F-UTIL-028] Proxy `/api`: Origin normalizado y 502 marcado cuando el backend está caído
- **Regla**: El proxy de `/api` existe; en `proxyReq` fija `origin` = `new URL(target).origin` (no la cadena cruda); en `error` responde 502 con cabecera `X-Laboratorio-Backend-Unreachable: 1` y termina la respuesta (consumido por F-API-004).
- **Fuente**: src/test/vite-dev-server.test.ts:vite dev proxy (3 tests)
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

---

## Comportamientos de copy frágil

Se rompen primero ante una reescritura de copy; deben regirse por el glosario (sin jerga visible: semilla, hash, JSON, ids, números absurdos como 9.007.199.254.740.991).

- **Frases fijas de caveat y veredicto**: «Esto simula con datos históricos: no predice resultados futuros ni garantiza rentabilidad.» (F-CREATE-006, F-RESULT-002); frases de veredicto «Meta alcanzada / Se agotó el capital / Límite de sesión / Historial agotado / En curso / Simulación cancelada» (F-RESULT-001); «Entre las simulaciones con resultado, Primera terminó con más saldo…» (F-RESULT-033).
- **Títulos de ruta y navegación**: Simulaciones, Estrategias, Datos, Ajustes, «Datos e historial», «Crear simulación», «Crear varias simulaciones», «Crear simulación con perfil de juego», «Resultado de la simulación», «Comparar simulaciones», «Página no encontrada», «Saltar al contenido principal» (F-SHELL-002/005/007).
- **Nombres accesibles usados como selectores**: «Abrir cola de cálculo», «Cola de cálculo», «Navegación principal», «Capital (RD$)», «Meta de saldo (RD$)», «Duración máxima (sorteos)», «Código de repetición», «Sorteo inicial», «Crear simulación», «Reintentar», «Detalles técnicos», «Avanzado» (toda F-CREATE, F-LIST).
- **Mensajes de error con causa + recuperación**: «No se pudo contactar al servidor… Iniciá el laboratorio…», «El cálculo puede continuar en el servidor; comprobá el estado desde la cola antes de reintentar.», «Tu información se conserva.», «Sin respuesta del servidor. Puede que el experimento se haya creado», «Puede estar en la cola», «Puede que se haya guardado» (F-UI-012, F-CREATE-033/042, F-LIST-003/004, F-RESULT-030).
- **Prohibiciones de copy**: «se detuvo/detenido/stopped», «Esto no detiene la ejecución», «mejor estrategia», «probabilidad de éxito», «exportar», «Resultados históricos sobre datos ya investigados», claves crudas (`system`, `flat`, `all`), «Semilla», `schema_version` (F-API-003, F-LIST-084, F-RESULT-008/009/034/035, F-CREATE-036).
- **Etiquetas de vocabularios separados**: estado de ejecución (Ejecución completada, Pendiente, En curso, Cancelado, Con error) vs desenlace (F-RESULT-017).
- **Leyendas de formularios y editores**: «Reglas del sorteo / Selección / Límites», «Resumen de la orden» (Capital, Meta de saldo, Duración, Cobertura), «Apuesta mínima por número», «Sumar los premios», «Un sistema de selección», «Plana» (F-CREATE-001/002/004, F-UI-017, F-RESULT-009).
- **Textos de cola**: «En curso / Esperando / Detenido», «La solicitud puede haber llegado…», «Comprobar estado X», «Reenviar cancelación X», «Confirmar reenvío», «Solicitud de cancelación enviada» (F-LIST-085/087/088/089).
- **Copy de ajustes y datos**: «Importar guarda datos, no ejecuta ni calcula pagos.», «Validar comprueba la solicitud; no reserva capacidad.», «No compartas esta credencial de acceso a la API.», «Uso incompleto…», «El entorno fija el límite…» (F-LIST-042/064/068/073/076).
- **Ayuda de semilla exacta**: «Se genera automáticamente; el mismo código repite la selección.» (F-SHELL-014).
- **Conjuntos de caracteres/valores de formato**: `RD$2.800` (separador de miles español), `USD 97.50`, `-USD 2.50`, ratios con 6 decimales y «N/D» / «No disponible» (F-UI-024, F-RESULT-006/014, F-UTIL-001). A diferencia del resto, estos son contratos de formato y no deben cambiarse con el glosario.

---

## Índice de cobertura

| Área | Alcance (archivos de test) | Ítems de contrato | De ellos riesgo alto |
| --- | --- | --- | --- |
| F-API | client.test.ts, types.contract.test.ts | 31 | 18 |
| F-UI | ui.test.tsx, tokens, contrast, format | 25 | 10 |
| F-SHELL | App.test.tsx, Shell.test.tsx, ui-labels.test.ts | 15 | 9 |
| F-CREATE | NewExperimentPage, ProfileExperimentPage, ProfileBatchPage | 53 | 32 |
| F-RESULT | DetailPage, ComparisonPage, BalanceChart, ComparisonChart, RunTrajectory, FinancialMetrics, StatusLabel | 40 | 28 |
| F-LIST | ExperimentsPage, DataTable, ConfirmDialog, StrategyEditor, Configurations, Data(+History), ProfileEditor, Settings, QueueDrawer, QueueProvider | 98 | 79 |
| F-UTIL | profile-display, profile-input, replay, batch-model, model, profile-model, vite-dev-server | 28 | 25 |
| **Total** | 37 archivos | **290** | 201 |

## Supuestos de decisión registrados

- [A6] Los tests de glosario de jerga visible (semilla/hash/JSON/ids) están repartidos en las páginas; se codificaron donde ocurren (F-CREATE-007/036, F-RESULT-008/009, F-LIST-070).
- [A7] Un ítem agrupa varios tests cuando afirman la misma regla con variantes (`it.each`, par de tests complementarios); la columna Fuente los enumera.
- [A8] Los dos tests de `ConfirmDialog` y `DataTable`, que no estaban en la lista de F-LIST del encargo, se incluyeron en F-LIST (6.2) por pertenecer a `src/components/` y ser primitivas de las páginas de listado.
- [A9] Los tests de modelo de `new-experiment/*` se asignaron a F-UTIL según el encargo, aunque se encuentran físicamente en el directorio de F-CREATE; `profile-model.test.ts` exporta fixtures reutilizados por `ProfileExperimentPage.test.tsx` (acoplamiento a conservar al reescribir).
- [A10] El conteo de «riesgo alto» se calculó sobre las etiquetas escritas en cada ítem.
- [A11] No se ejecutó la suite ni se leyeron fuentes de producción; nombres de tests y reglas provienen únicamente de las aserciones leídas.

