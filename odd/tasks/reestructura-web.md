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

- Backup (not acceptance): `21faa78`, pushed to `origin/stage` by explicit request.
- T1: `776e345` — `fix(web): preserve simulation drafts across legacy navigation`.
  Accepted with the functional evidence above; native review skipped because the
  user disabled RDD for this clone, not because the old review was approved.
- T2 backend: `5fec388` — `feat(api): unify validated simulation listing`.
  Independent 37 focused / 896 complete backend tests, Ruff and whitespace pass;
  no push. This closes only the backend unit, not the T2 checkbox.
- T2 unified UI / repeat and T3-T10: pending.

## Next active unit

- T2 mapping `muw5aov3-6-fv3q` completed. Implement as three bounded work units:
  1. Add a backend-only `/api/v1/simulations` read endpoint with bounded,
     server-side global filtering/sorting/pagination across saved experiments
     (including validated profile versions/batches) and historical backtests.
     Query IDs/count/snapshots from one consistent SQLite read view. Keep old
     endpoints and stored financial contracts unchanged. Fail the request on
     unavailable/corrupt source data rather than returning a misleading complete
     count or pretending a partial first-page merge has global ordering.
  2. Move the current simulations list onto that contract, with scope filter,
     URL state, stale-response guards and explicit retry/error states; retain
     compatibility routes. No unbounded fetch-all or client first-page merge.
  3. Add repeat actions from saved requests/config/profile revisions/datasets and
     hashes; preserve stale historical-input 409 responses. Characterize older
     profile variants before enabling actions; never silently use current inputs.
- The first backend-only unit is active. Missing writer `muw5inqy-7-dz5q`
  left a partial implementation without an accepted final report. Recovery
  verifier `muwpcm29-1-hm0e` confirmed unchanged source hashes/status and ran:
  empty-database endpoint test 1 passed; compatibility/storage/golden subset
  135 passed after the initial 120-second attempt timed out; Ruff passed.
  These checks do not prove populated behavior or the missing writer's TDD.
- Four recovery findings must be closed with observed regressions: beyond-last
  offset crashes instead of returning the true total and an empty page; v5 batch
  query names differ from displayed strategy names; corruption/invalid eligible
  profile structures can be hidden by filtering/page-local validation; dataset
  validation opens another connection outside the promised SQLite read view.
  Add populated cross-source pagination/filter/tie/escape/profile/failure tests;
  do not claim source-wide semantic integrity from the empty-database test.
- The correction continuation recovered populated regressions: 5 passed / 1
  failed (global tie order), compatibility subset 135 passed, Ruff failed on
  import order in the new test. No completed GREEN or accepted writer report.
- Read-only integrity design confirmed that page-only hydration and SQL shape
  checks cannot prove full-source domain semantics. An index certificate cannot
  establish current integrity against unobserved external changes by itself.
- User subsequently approved complete-source semantic validation on each LIST
  request, with a paginated response, accepting cost proportional to eligible
  source rows and their dependencies. This supersedes the separate-design pause.
  Global source validation must run independently of requested filters/offset;
  do not silently hide malformed eligible rows. Use the same SQLite read view
  for all database reads, preserve existing financial validators and compatibility
  routes, and describe external-file consistency limits truthfully.
- Writer `muwrc4fn-3-jpy5` reported backend implementation complete within the
  existing surfaces, with RED: three filtered-out semantic-corruption cases
  returned 200 instead of 409, plus the initial tie-order failure. Final GREEN:
  12 focused API tests, 135 compatibility/storage/golden tests, Ruff passed.
  Four intermediate compatibility failures were corrected before the final run.
  These are writer-reported checks, not independent acceptance or T2 closure.
- Native risk assessment returned `unassessable` because intended new files were
  not declared to native assessment. RDD stays off; follow the high-risk fallback
  plan with independent verification rather than inventing a classification.
- Read-only verifier `muwsn2hu-4-c4kx` is auditing the actual diff and running the
  focused and complete backend suites plus Ruff. Review full-source validation,
  backtest report assumptions, legacy read compatibility, profile replay and
  dataset consistency. No other source writer is active; no commit yet.
- Verification reconciled the current baseline independently: repository 3,164
  lines (`c9f5c1c242ca385cfc6f1541b538900c6221ca2438211474174bbaf91253f150`),
  API 79, tests 382, app 319. Earlier supplied counts were not current evidence.
  The verifier withdrew its unsupported formatter-notice attribution; no direct
  notice or concurrent writer was observed. Parent explicitly accepts these
  bytes as a fresh verification baseline only, not as a completed candidate.
  Focused run: 12 passed in 27.88s, subject to post-run hash confirmation.
  Recheck all four source hashes after checks; any subsequent drift blocks
  acceptance. Read-only incident diagnosis is isolated from implementation.
  Incident scout `muwsqgaq-5-yjeh` found no independently verified formatter
  configuration/logs or prior-byte comparison; the earlier count discrepancy
  remains unexplained and is not evidence of formatting-only changes.
- Independent complete backend run failed: 4 failed, 888 passed, 2 warnings
  in 241.20s (exit 1). Focused 12 tests and Ruff pass, but are insufficient for
  acceptance. The full log is `C:/Users/luism/AppData/Local/Temp/t2-independent-backend-pytest.log`.
  Failures in `tests/test_profile_storage.py`: prepared typed read, mixed-kind
  error precedence, corrupt-dataset/quota inspectability, and cycling quota.
  The new unconditional dataset verification in the shared loader changes
  existing `get_experiment` contracts. Isolate new listing integrity validation
  without weakening the new endpoint or legacy read/inspection behavior.
  Verifier final result: FAIL, no acceptance. All four pinned source hashes
  matched; parent task-document bookkeeping is not source drift or a blocker.
  Additional isolated temporary-DB cases returned 200 despite filtered-out
  damaged backtests: goal equals capital; prize count differs from positions;
  zero bets with nonzero wagered/paid. Existing API/domain producers forbid
  these states (`api/backtests.py:create_backtest`, `BacktestConfig.__post_init__`,
  `run_backtest`). Correct these proven invariants, not speculative restrictions.
  Correction writer `muwt0k1v-7-g8kt` completed within repository/API-test scope.
  Restored v1-v4 inspection/error precedence while retaining v5 checks; strict
  profile dataset validation now belongs to the unified listing read view.
  Backtest validation reuses producer `make_game`/`BacktestConfig` invariants
  and rejects zero-bet stake/payout totals. Added three corruption regressions
  and one legitimate zero-bet control; no legacy tests changed.
  Observed writer RED: 7 failed / 29 passed; final GREEN: 37 focused,
  896 complete backend tests with 2 deprecation warnings (195.23s), Ruff passed.
  Parent confirmed corrected hashes: repository 3,205 lines
  (`3fa8eb7b67f7baa625d141fb4edac9c2d8eeabbee26d0f116f1ff2730a63b962`),
  API tests 480 lines (`6112511d2ecd0be0cf9fd5537816e3f5fb89897ef601692b389aa4fcc811b01a`);
  API/app hashes unchanged. Native assessment remains unassessable; retain
  high-risk independent verification, without enabling RDD or inferring approval.
  Read-only verifier `muwterxc-8-94ob` completed PASS: 37 focused (4.50s),
  896 complete backend tests (174.05s), Ruff and whitespace checks passed;
  all four source hashes matched before/after. Prior seven blocking cases are
  closed; valid zero-bet reports return 200 and damaged off-page cases return 409.
  Parent accepts this backend unit only. Log:
  `C:/Users/luism/AppData/Local/Temp/t2-independent-corrected-20260720-pytest.log`.
  Two dependency deprecation warnings remain (`websockets.legacy`,
  `WebSocketServerProtocol`); RDD is off, not approved or acknowledged.
  Backend work-unit commit: `5fec388fe8bb668320aca82db23d8921569196fb`
  (`feat(api): unify validated simulation listing`), on `stage`, not pushed.
  Proceed to the five-surface frontend unit below with one writer and observed
  RED/GREEN; preserve compatibility routes, classic base/delete actions and
  historical workflows. T2 remains unchecked until unified UI and repeat pass.
- While independent backend acceptance is pending, read-only scout
  `muwsu192-6-h0ns` is refining the next frontend unit against the actual new
  contract: discriminated mixed-source items, server-backed scope/URL state,
  complete-error retry and compatibility links. No frontend writer is active;
  repeats, wizard, result and destructive historical actions stay out of scope.
  Scout handoff completed: later edit surfaces are frontend `api/types.ts`,
  `api/client.ts`, `api/client.test.ts`, `pages/experiments/index.tsx`, and
  `pages/experiments/ExperimentsPage.test.tsx`. Use tagged `source_kind + id`
  keys, server-backed scope/URL filters and explicit whole-list 409/503 retry.
  Keep `/simulaciones/historicas` independently reachable for compatibility;
  no `App.tsx`, historical-page, shared fixture or detail/create edits planned.
- Response pagination is bounded, validation/replay cost is not. SQLite guarantees
  a database read view, not a filesystem-wide snapshot. Classic/backtest saved
  provenance is checked without rereading current external histories/rankings;
  archived v5 binding checks external sources without promising a file snapshot.
  No migrations, index/certificate redesign, real-database writes or engine edits.
- Frontend writer `muwtp3yq-9-7m0i` returned partial with the five-surface
  mixed list implemented (+183/-57): tagged types/client, scope URL state,
  source-qualified row/menu IDs, historical detail links, whole-error retry.
  Writer checks: 76 focused + 24 compatibility tests; full 588 tests / 40 files,
  typecheck/build and whitespace pass. Build chunk warning: 552.24 kB.
  TDD: client RED observed (`listSimulations` missing); mixed-render RED was
  invalid due to an undefined fixture. Record this deviation; do not backfill or
  claim that behavior had observed test-first RED. Parent confirmed five hashes.
- Native frontend assessment: medium risk, large writer, RDD off; writer checks
  satisfy the selected verification plan. Functional browser verification is
  still required. Read-only verifier `muwu881g-a-l9xz` is checking actual UI
  at 390/1440 using GET-only API mocks, source-hash freeze and inspected images.
  Verifier finished PASS: 23 browser checks, 111 API requests all GET,
  zero unmapped API/mutation attempts/page errors, four console messages exactly
  matched injected 409/503 failures. Actual 390/1440 document widths stayed
  390/1440, including long v5 names; all five source hashes remained unchanged.
  Parent accepts the frontend-list unit, not whole T2. Inspected screenshot
  evidence and logs are under `C:/Users/luism/AppData/Local/Temp/t2qa/`.
  No live-backend integration or real-data mutation is part of this browser QA.
  Active LSP check: two auxiliary client warnings; four files inconclusive,
  none confirmed clean. Typecheck passed; do not infer clean from silent LSP.
- The initial browser overflow measurement was invalid: the temporary harness
  started Vite from the repository root, so frontend-relative Tailwind content
  globs omitted actual component rules (including title wrapping). Verifier
  preserved that run under OS-temp `t2qa/incorrect-cwd-run` and restarted only
  its owned Vite process with `webapp/frontend` cwd and an OS-temp cache.
  No source/CSS change follows from this invalid measurement. Corrected browser
  QA is rerunning with contract-correct replay/trajectory GET mocks; offline
  empty Google Fonts CSS is an explicit font-fidelity limitation.
- Read-only scout `muwuk3vx-b-fc4x` is mapping saved-snapshot repeat availability
  across classic/historical/profile v1-v5, specifically the previously unproven
  safe-prefill/new-submission capability. No repeat implementation, source edits
  or expansion into the T3 wizard/T7 adapters is authorized by this mapping.
- UI is accepted pending work-unit commit; repeat is unimplemented. Keep T2
  unchecked until all three units have checks and commit evidence. The original
  mixed-render RED gap and fallback-font-only QA remain explicit limitations,
  not backfilled evidence. T3 wizard and T4 common result remain separate.
- Repeat mapping found safe existing classic draft field mapping, but classic
  submission adopts current catalog provenance rather than binding saved hashes.
  Frontend display-only provenance does not satisfy snapshot-preserving repeat.
  Profile v1-v4 and v5 require version-specific saved-request hydration; historical
  exact prefill still needs evidence. Follow-up read-only scout `muwuq2ij-c-efz4`
  is resolving classic additive source guards and historical saved-config fields
  before a smallest bounded repeat writer is authorized. No large three-editor
  rewrite or implicit expansion into T3/T7 is accepted by this mapping.
