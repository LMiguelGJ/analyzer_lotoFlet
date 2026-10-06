# Feature: Reestructura y unificación de la web

Origen: Judgment Day sobre la estructura completa (target `fdab1f3`), ledger en
`odd/reviews/judgment-day-estructura-web.md` (10 hallazgos confirmados C1-C10,
5 sospechosos S1-S5, veredicto ESCALATED por contradicciones de severidad en C5/C6).
Decisión del usuario (2026-10-05): ejecutar las 4 fases completas.

Pregunta del usuario que guía todo: «¿por qué los simuladores son cosas distintas a
los históricos?». Respuesta de diseño: son el mismo trabajo (probar una estrategia
sobre el historial); la diferencia es un parámetro de alcance (una sesión desde un
sorteo frente a todo el historial con sesiones repetidas).

## Estructura objetivo

1. **Simulaciones**: un listado y un asistente únicos (Estrategia → Reglas del juego
   → Alcance → Capital y meta → Revisar), un resultado común y «Repetir con cambios»
   para todos los tipos.
2. **Estrategias**: una sola biblioteca.
3. **Datos**: historiales e importación en un solo formulario.
4. **Ajustes**: «Reglas del juego» como única fuente.

Término único: **Simulación** (palabra del usuario). Rutas `/simulaciones/...` con
redirecciones desde `/experimentos/...` para no romper enlaces guardados.

## Reglas de la reestructura

- Los 14 escenarios dorados (`webapp/backend/tests/test_backtest_golden.py`) deben
  seguir exactos en cada unidad: protegen el motor.
- No se pierde capacidad: todo flujo actual sigue existiendo, aunque entre por otra
  puerta.
- Cambios de datos persistidos (F3) llevan migración y prueba de migración.
- Una unidad de trabajo = un commit + verificaciones funcionales. La revisión
  nativa se ejecuta solo cuando RDD está activo; el usuario lo desactivó
  explícitamente para este clon. Con RDD apagado se aplica evaluación de riesgo
  y verificación independiente cuando corresponda.

## Tasks

### F1 — Bugs y nombres

- [x] T1. Título móvil (S1), enlace «Editar reglas» (C6), nombre único
  «Simulaciones» en menú, aria-label, títulos y rutas con redirecciones (C2), acción
  primaria declarada por ruta en vez de regex en el Shell (C4).

### F2 — Simulaciones unificadas

- [ ] T2. Listado único de simulaciones (clásicas, con perfil e históricas) con filtro
  por alcance; sin pestañas internas (C1, C3); «Repetir con cambios» en todos los
  tipos (C8).
- [ ] T3. Asistente único «Nueva simulación» con paso de Alcance; usa catálogo,
  `StrategyEditor` y biblioteca de estrategias también para historial completo
  (C7, C10). Los flujos con perfil quedan como una opción de datos dentro del mismo
  asistente.
- [ ] T4. Modelo de vista y componente de resultado comunes (C9).

### F3 — Una biblioteca y una fuente de reglas

- [ ] T5. Biblioteca única de estrategias (`/configurations` + `/strategies`, C5) con
  migración de datos.
- [ ] T6. Fuente única de reglas del juego (`settings/game` + perfiles de juego, C6)
  con migración de datos.

### F4 — Limpieza del backend

- [ ] T7. Versiones de perfil v1-v4 como adaptadores de lectura sobre v5 (S3).
- [ ] T8. API del agente sobre la misma API con autenticación propia, sin router
  espejo (S4).
- [ ] T9. Importación única (endpoint y formulario) con modo avanzado plegado (S5);
  borrado y orden en el listado de corridas (S2).

### Cierre

- [ ] T10. QA: suites completas, build, verificación visual móvil/escritorio,
  re-crítica Impeccable para medir contra el 22/40, push.

## Verification

Backend: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/ -q` (incluye los
14 dorados) y `ruff`. Frontend: `npm test -- --run`, `npm run typecheck`,
`npm run build`. Visual: capturas a 390 px y 1440 px.

## Execution status

### Current resumed checkpoint (supersedes historical blockers below)

- User explicitly disabled RDD for this clone; global RDD remains enabled.
  Pending native review `review-2a7f14113ecdbd71` is neither approved nor deleted.
  Its capture failure no longer pauses ordinary implementation under RDD-off policy.
- User-requested backup `21faa78` was pushed to `origin/stage`; it preserves
  partial T1, not a completed task. Resumed work starts from a clean worktree.
- Observed checkpoint checks: frontend 581 passed / 2 failed (stale navigation
  expectations in BacktestsPage and ExperimentsPage); typecheck and build passed
  with a 550.65 kB chunk warning; backend 880 passed and Ruff passed; all 14
  golden scenarios passed. Visual checks at 390 px / 1440 px remain pending.
- T1 correction writer `muw4dqwn-4-yo6e` completed: dirty raw-path changes
  now trigger the leave guard; the regression re-queries the live textbox and
  proves stay preserves the draft while explicit leave clears it. Two stale
  navigation assertions now use canonical labels/routes. Source/test delta:
  19 insertions and 12 deletions across four frontend files.
- Observed RED: creator tests 47 passed / 1 failed before the fix. GREEN:
  focused five-file suite 117 passed; full frontend suite 583 passed in 40 files;
  typecheck/build passed (550.56 kB chunk warning); 14 golden scenarios passed.
  Full-suite JSDOM logs include the bogus-status negative case; their origin
  remains under focused verification, not assumed harmless.
- Native read-only ASSESS: medium risk, large runtime writer, RDD off; writer
  self-verification stands and no separate verifier is required by the plan.
  Verifier `muw4xvoe-5-ji07` completed an independent focused spot check:
  78 tests passed across creator/App/Shell. Actual browser QA at 390 px and
  1440 px passed with GET-only mock API data: eight screenshots inspected,
  no horizontal overflow, readable titles, correct primary destinations,
  rules deep link, legacy query/hash preservation and dirty draft stay/leave.
  Zero page errors; owned server/browser processes stopped; Git status unchanged.
  Artifacts: OS temp `t1qa-results.json`, `t1qa-browser.log`, and
  `t1qa-{390,1440}-{simulaciones,historicas,nueva,nueva-historica}.png`.
  The bogus-status throw is an intentional fixture at StatusLabel.test.tsx:102-104;
  the full console log was unavailable, so not every console entry is certified.
  Real-data submissions/settings saves, populated result/comparison screenshots
  and native unload-dialog checks were not exercised; full-feature QA remains T10.
- T1 functional acceptance is complete under RDD-off policy; its work-unit commit
  is recorded below. The historical native review remains unapproved.
- T2 is next: consolidate the simulations list and preserve exact repeat inputs.
  T3-T10 remain pending; the backup commit alone accepted no implementation task.

### Historical execution evidence

- T1 was in progress with partial source changes; it was not accepted or committed.
- Initial writer and explorer attempts ended without final reports. The parent
  confirmed a clean worktree at `0dc29d6`; neither attempt is accepted as completed.
- Resumed writer `muvr6h6e-q-9a1z` returned partial after the parent requested a
  pause for native review. Observed checks: focused tests 29 passed / 1 failed;
  full frontend suite 550 passed / 31 failed; typecheck and build passed, with a
  build warning for a chunk above 500 kB. RED was observed, GREEN not achieved.
- Remaining T1 work: internal links and test route expectations, correct mobile
  viewport setup, and verification that the settings deep link opens rules.
- Intermediate review `review-6da25275f8862c9a` approved and acknowledged target
  `sha256:5ff3dc74a55fbdce7c03fe9cb0572100dc377fa0995bb9f9d99e3972065f6e20`;
  native acknowledgement burned authority. Advisory `R3-legacy-route-case` at
  `App.tsx:21-22` is informational, not a correction route. This review does not
  replace functional checks or approve subsequent changed content.
- Continuation writer `muvrto99-s-dhz8` stopped at the requested checkpoint and
  returned partial: focused tests 30/30 passed; typecheck and build passed; full
  suite 543 passed / 39 failed across 10 files, with 4 unhandled errors. Build
  warned about a 550.56 kB chunk. Remaining failures include stale route
  expectations, profile-wizard routing and the settings test textbox query.
- Review `review-dad78fb049dccaff` approved and acknowledged frozen target
  `sha256:17083849ac58c2846e0f43e8b40440bce9656aa11d4504f95c2576ece8f77df0`;
  acknowledgement returned authority burned. Its route-case advisory is
  informational. This does not close T1 or replace failing functional checks.
- After interruption, verifier `muvsdvcz-t-hasm` was absent from the task registry;
  its result is unavailable and is not accepted as verification evidence.
- Replacement read-only verifier `muvw94ym-1-f5be` completed: reproduced
  543 passed / 39 failed and 4 unhandled rejections; typecheck passed. Root
  classes: stale UI route assertions; stale rules-link expectation; async settings
  textbox query; isolated profile router missing canonical destination; leaked fake
  timers; genuine raw-path alias mismatch in the dirty-navigation guard.
- Sole writer `muvwl94y-2-rnxg` stopped partial at the requested safe boundary.
  Its last four-file test run reported 3 failed / 173 passed; required focused
  App/Shell, typecheck, full suite and build were not rerun after these edits.
- Native review `review-2a7f14113ecdbd71` requires bounded correction of
  `R3-alias-draft-loss` (CRITICAL) for frozen target
  `sha256:4e7df8619ee99c80c3b110960da9b78979eac0aa1ed9ad7b8e411d7212bacf0d`.
  Equivalent-path exemption bypasses the dirty guard but the legacy redirect
  unmounts the creator; the test falsely checks a detached input. Preserve the
  guard or the mounted creator and assert the live field, never the old DOM node.
- Current native STATUS offers `correction_plan_required`. Exact offered capture
  with a 60-diff-line plan was rejected locally with `capture-binding-rejected`:
  matching provider lineage/target token unavailable. No mutation occurred.
  Fresh bound STATUS still offers the correction slot; authority remains
  `correction_required`, with a changed live target. No opaque binding was changed,
  no bypass or recovery performed. Further source writes are paused pending an
  accepted native correction route; T1 has no functional GREEN or task commit.
- On user-requested resume, fresh bound STATUS reoffered the same correction slot.
  The exact fresh binding and 60-line plan were again rejected without mutation.
  Read-only tooling explorer `muvydqmx-3-hvnq` completed its diagnosis:
  installed `gentle-pi` 4.0.0 checks correction-plan target against live STATUS,
  with no frozen-authority-target exception (extensions/gentle-ai.ts:7343-7358;
  lib/review-integration-v2.ts:1718-1740). Native intent is not independently proven;
  no documented non-destructive alternative was found.
- Read-only researcher `muvyj7m7-4-tynp` could not query published metadata
  because its toolset lacked shell/web access. Parent completed the bounded
  read-only command `npm view gentle-pi version dist-tags repository --json`:
  installed and published `latest` are both 4.0.0; repository is
  `Gentleman-Programming/gentle-shell`. No newer latest-channel release or
  verified compatible fix is available in this evidence.
- T1 remains blocked awaiting a compatible published fix or documented maintainer
  continuation. No package installation/update, app source writes, authority
  recovery, opaque-binding edits or raw CLI bypass were performed.
- Review `review-d1560b35741d9a5a` approved and acknowledged exact intermediate
  target `sha256:6b2567de426b4f42fca9dcb427eae3584c86aa2b797c1ff789c87f78afeea752`;
  native returned authority burned. This does not cover later edits or close T1.
- Latest review reminder for `sha256:b464b85d1fa83dcbc6cc40586f66e186a10fb63d5a8c449fcf2213147553ce02`
  failed before lineage creation: candidate-view Git `rev-parse` failure.
  Native reported no mutation; no reset/recovery or approval was performed.
- Resumed read-only explorer: `muvr6i9d-r-f5bo` completed its F3/F4 design
  handoff. It did not inspect the user's database or execute checks; none of
  T5-T9 is implemented or verified by this report.
- User requested autonomous overnight progress, ordinary questions deferred, ODD
  and parallel subagents. This does not authorize review/maintenance bypass or
  destructive migration. Source writers remain paused under the open correction.
- Independent read-only preparation is running in parallel:
  - `muvyqe30-5-wh0m`: T2-T4 implementation map completed, read-only.
    Experiments support filter/sort/pages but backtests only offset/limit; never
    globally sort a merge of just their first pages. Scout proposed collecting all
    pages before merging; this remains an unaccepted scalability tradeoff, not an
    implementation decision. Preserve explicit partial-source error/retry states,
    stale-response protection and truthful totals.
    Repeat must use saved contract/version/profile/dataset/revision/hash snapshots;
    endpoint-level availability for every older variant remains unproven. Stale
    backtest hashes must surface 409 rather than silently use current inputs.
    Use a shared wizard/frame with contract-specific inputs and financial panels;
    never equate cohort averages with a single session's balance. Proposed T2
    subdivisions (model, presentation, repeat) are planning units, not checkoffs.
    App route changes remain deferred until T1 correction is resolved.
  - `muvyqevu-6-0gdt`: T5-T7 compatibility matrix completed, read-only.
    Legacy `best` uses first-match/v0, newly registered profiles use
    maximum-payout/v1; identical prizes do not prove payout equivalence.
    Classic settings omit currency/scale/grid/max-stake/exposure, and classic
    blend/random/ladder/bold cannot be assumed equivalent to v5 policies.
    Proposed sequence: characterization inventory, additive provenance-preserving
    strategy projection, rules projection with fallback, then legacy read parity.
    Keep legacy writes until every selection/staking/closing capability has parity.
  - `muvyqfm3-7-bghm`: T8-T9 auth/import/list map completed, read-only.
    Share resource operations behind explicit agent allowlist/bearer adapters while
    retaining browser host/origin/CSRF checks and compatibility paths. External
    client usage remains unknown. Discriminated mapped/canonical ingestion must
    retain both wire validators, profile/source/timezone confirmation, preview hash,
    quotas and uncertainty handling. Backtest sort requires allowlist/tie-break;
    deletion requires matching confirmation ID and proof of no unintended cascade.
    Proposed bounded sequence: ingestion service/contracts, unified import UI,
    backtest sort/delete, agent shared operations with auth regression tests.
  All three reports are planning evidence only, not implementations or passing
  checks. No real database was inspected or migrated and no API was changed.
- T2-T10 remain pending. No task may close until its checks and commit are observed.

## F3/F4 compatibility findings and implementation gates

- T5: classic configurations (`0001_initial.sql`, `repository.py:1508-1545`)
  and revisioned strategies (`0010_strategy_library.sql`, `repository.py:1377-1467`)
  have different contracts. Proposed survivor: the revisioned library, with explicit
  compatibility projections. Lossless conversion is unproven. Preserve original
  rows, provenance and readable incompatible records; test idempotent migration
  before switching consumers. Do not silently emulate mutable deletion against
  immutable revisions.
- T6: legacy `settings_game` drives `GAME` at startup (`app.py:103-108`), while
  profiles have richer versioned semantics. Proposed canonical source: an active
  immutable profile revision, only after payout, repeats, currency/scale and stake
  equivalence are proven. Preserve legacy fallback and stored run snapshots.
- T7: versions 1-4 still accept writes through `/experiments/profiles`; v5 writes
  use `/profile-batches`. Preserve legacy readers and replay behavior. Unifying new
  writes requires proving the existing creation capabilities remain available;
  rejecting legacy writes alone does not satisfy the no-capability-loss requirement.
- T8: corrected agent prefix is `/api/agent/v1`, with dedicated bearer auth and
  in-repository tests, not an unauthenticated mirror. Consolidation must preserve
  browser auth, agent scopes/allowlist, response links and temporary compatibility.
- T9: the two import pairs have distinct wire formats (JSON envelopes versus raw
  canonical history plus profile/confirmation headers). A shared discriminated
  contract must preserve both validators and confirmation requirements.
- Suggested later implementation order: isolated T9 work, then write-side T7,
  strategy migration T5, rules migration T6, and external-client/auth-sensitive T8.
  This is an advisory dependency order, not authorization to skip T2-T4 or overlap
  writers. Confirm consumer dependencies before changing the visible execution plan.
- The user's live database contents and conversion compatibility remain unknown.
  No destructive migration or rewrite of saved requests/results is authorized.

## Evidencia (commits)

- T1-T10: pendiente
