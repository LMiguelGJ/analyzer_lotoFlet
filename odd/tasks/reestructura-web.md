# Feature: Reestructura y unificación de la web

Origen: Judgment Day sobre la estructura completa (target `fdab1f3`), ledger en
`odd/reviews/judgment-day-estructura-web.md` (10 hallazgos confirmados C1-C10,
5 sospechosos S1-S5, veredicto ESCALATED por contradicciones de severidad en C5/C6).
Decisión del usuario (2026-10-05): ejecutar las 4 fases completas.

Pregunta del usuario que guía todo: «¿por qué los simuladores son cosas distintas a
los históricos?». Respuesta de diseño: son el mismo trabajo (probar una estrategia
sobre el historial); la diferencia es un parámetro de alcance (una sesión desde un
sorteo frente a todo el historial con sesiones repetidas).

## Estado final del alcance

Implementación cerrada dentro del alcance acordado. Por decisión explícita del
usuario, T5b y T6b (migraciones físicas) quedan retiradas, no completadas como
migraciones. Se conservan los almacenes nativos y la interfaz/proyección común.
No quedan tareas activas de esta reestructura ni obligación de QA del usuario.
Las referencias históricas a migración pendiente, agentes activos o aceptación
manual quedan supersedidas por este cierre.

Los checks diferidos siguen sin ejecutarse; la última consulta LSP fue inconclusa.
Este cierre no certifica tests, types, build ni runtime, ni implica commit o push.
Se conserva el código, los datos y la evidencia histórica; la limpieza afecta
únicamente el seguimiento de tareas.

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
  seguir exactos: protegen el motor. Se ejecutan si una unidad afecta el motor,
  contratos financieros o backend relevante, y en el cierre; no se repiten por
  cambios frontend aislados que no afectan ese código.
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

- [x] T2. Listado único de simulaciones (clásicas, con perfil e históricas) con filtro
  por alcance; sin pestañas internas (C1, C3); «Repetir con cambios» en todos los
  tipos (C8).
- [x] T3. Implementación del asistente «Nueva simulación» con paso de Alcance,
  StrategyEditor e históricos/perfiles. Source implementation and known corrections
  delivered; runtime/manual acceptance is tracked separately in T10. This checkbox
  does not assert passing tests, completed delivery or runtime acceptance.
- [x] T4. Implementación del modelo de vista y componente de resultado comunes (C9).
  Adopted in native and historical reports; independent source review found no
  additional severe blocker. Runtime/manual acceptance remains in T10.

### F3 — Una biblioteca y una fuente de reglas

- [x] T5a. Implementación de biblioteca común de estrategias (C5): descubrimiento
  discriminado, búsqueda sobre páginas cargadas y consulta de revisiones nativas.
  Runtime/manual acceptance remains in T10.
- **Retirada del alcance — T5b.** Migración física de la biblioteca de estrategias
  (C5), no implementada ni ejecutada, por decisión explícita del usuario.
  Delivered implementation: discriminated library discovery in existing configurations
  page, backed by native APIs with IDs/revisions preserved. Allowed surfaces:
  pages/configurations/index.tsx and ConfigurationsPage.test.tsx;
  lib/strategy-library.ts and strategy-library.test.ts. No storage migration,
  destructive conversion or legacy API removal in this UI unit; migration remains
  withdrawn from scope by the user, not silently represented as completed.
- [x] T6a. Implementación de proyección y presentación compartida de reglas (C6).
  Writer muxq1bdw-n-ghh7 delivered typed projections and GameRulesSummary in
  Settings and all four native creators, plus explicit paged profile discovery.
  Source self-readback completed; tests/build/runtime unrun. Acceptance in T10.
- **Retirada del alcance — T6b.** Migración física de reglas del juego (C6),
  no implementada ni ejecutada, por decisión explícita del usuario.
  Delivered non-destructive UI unit: typed rules projection and reusable summary
  consumed by settings and the four native creators. Preserve classic first-match
  versus profile maximum-payout semantics, exact currencies/scales/provenance.
  Allowed surfaces: lib/game-rules.ts/test, components/GameRulesSummary.tsx/test,
  pages/settings/index.tsx/SettingsPage.test.tsx, four native creator pages and
  their existing page tests. No financial engine/API/storage changes or executed
  migration; literal data migration is withdrawn from scope, not claimed by UI unification.

### F4 — Limpieza del backend

- [x] T7. Implementación de lectura común sin pérdida para perfiles v1–v5 (S3).
  Writer muxr40x9-s-7z89 delivered a typed run-summary boundary consumed by
  experiment(), with native adapters preserving exact versioned result payloads.
  This resolves shared reading, not conversion of legacy requests into v5 batches.
  Storage/financial execution/replay unchanged; tests added but unrun.
  Source readback confirms strict version dispatch and a shared execution kernel;
  literal legacy-over-v5 adapters are not present or justified. Preserve native
  contracts; no synthetic conversion is authorized by this reuse finding.
  User-authorized resolution: common lossless read projection, not v5 request
  conversion. Scout muxr2872-r-rr5d found actual duplicate run-summary envelopes
  in api/__init__.py:39 and api/profile_views.py:22, consumed by experiment()
  at api/__init__.py:147–158. Share the envelope, retain native result branches,
  versions/metrics/identities/context and exact output. Allowed additional surfaces:
  api/__init__.py, api/profile_views.py, tests/test_profile_api.py and
  tests/test_profile_batch_views.py (all under webapp/backend).
  Current sole T9 writer receives this next bounded backend unit in the same
  handoff; finish T9 first, then implement T7. No second concurrent source writer.
- [x] T8. Implementación de API del agente sobre endpoints nativos con autenticación
  propia (S4). Writer muxqq94r-p-ny7b removed 18 forwarding wrappers, preserved
  all 23 allowlisted routes and five necessary contract adapters. Tests added but
  unrun; independent verification and runtime acceptance remain in T10.
  Existing agent router applies Bearer auth and delegates native handlers
  (api/agent.py:46–160). No duplicate service logic found. Literal router removal
  is not established by delegation; preserve the distinct authentication boundary.
  Active backend implementation: replace redundant forwarding handlers with explicit
  allowlisted native endpoint registrations where signatures/contracts match.
  Keep bounded adapters where query policy, revision lookup or agent response links
  differ. Allowed surfaces api/agent.py and tests/test_agent_api.py; native API
  modules may be read, not changed. Preserve auth, exact routes and allowlist;
  this removes mirrored implementation, not the required authenticated namespace.
  Final review muxru8vf-t-e44x found one blocker, independently spot-checked:
  pagination adapter omits name_contains, leaking FastAPI Query default into
  repository and causing409. Reopen only for explicit name_contains=None and
  a regression reaching the real native handler (current mock masks this).
  Correction surfaces remain api/agent.py and tests/test_agent_api.py.
  T7/T9 review found no additional severe source blocker; all runtime checks unrun.
  Corrector muxrzur2-u-9jme delivered explicit name_contains=None and an
  authenticated regression invoking the real native handler with a repository
  double. Parent independently read both changed blocks and confirmed the exact
  requested correction and regression wiring. No test execution is claimed.
  Automatic editor diagnostics reported five BaseRoute attribute typing issues
  in an existing test; APIRoute narrowing subsequently addressed the source issue.
  The LSP probe was inconclusive, so no clean typecheck is claimed.
  T10 technical source review and unrun-check record are complete. Functional
  verification remains unperformed, not a user-owned task or passing evidence.
- [x] T9. Implementación de entrada y formulario comunes de importación con modo
  avanzado plegado (S5); borrado y orden existentes en listado de corridas (S2).
  Writer muxr40x9-s-7z89 delivered strict explicit-mode dispatch, shared mode/form
  ownership and native payload adapters. Historical and agent aliases preserved;
  middleware retains 32MiB history / 3MiB envelope and native 2MiB decoded limits.
  Source self-readback completed; tests/types/build/browser/runtime unrun.
  Shared promotion exists (api/imports.py:168–230); advanced generic import is
  folded (pages/data/index.tsx:428), sorting and confirmed whole-experiment
  deletion exist (pages/experiments/index.tsx:234,251–252,292–293,337).
  Distinct import endpoints/forms remain intentional native contracts; readback
  does not prove the literal single-endpoint/form criterion. No destructive
  migration or silent contract normalization. Runtime acceptance remains pending.
  Active T9 implementation: shared preview/promote entry routes with explicit
  import mode and native parsing adapters, preserving historical route aliases;
  a single import UI entry with advanced mode folded. Allowed surfaces:
  api/imports.py, tests/test_import_api.py, tests/test_history_import.py;
  frontend api/client.ts and existing colocated client tests;
  pages/data/index.tsx, DataPage.test.tsx and DataPageHistory.test.tsx.
  Preserve historical raw-body versus generic envelope contracts, limits, hashes,
  profile/timezone/source checks and uncertain-promotion recovery. No storage
  migration or new wire normalization. If middleware limits are path-dependent,
  report exact blocker before changing middleware outside this scope.
  Confirmed app.py:172–192 selects 3MiB versus32MiB by path before handlers.
  Parent readback authorizes adding ONLY laboratorio/app.py to T9 surfaces for
  selecting existing limits from the same validated import mode. Reject unknown/
  duplicate explicit modes without increasing limits; keep streamed-byte counting,
  legacy paths and host/origin/Bearer policies unchanged. No edits were made by
  the stopped first attempt; continue same writer with this bounded addition.

### Cierre

- [ ] T10. Aceptación final integrada: QA manual a cargo del usuario, con pruebas,
  build y revisión independiente pendientes registrados explícitamente. Incluye
  T3, T4 y T5a implementados; sus casillas no certifican ejecución ni aceptación.
  Suites/build/QA automatizada diferidos por instrucción del usuario. Commits,
  push y entrega se registran separadamente; ninguno se afirma aquí.
  Final source reviewer muxqdosj-o-qo7k completed T5a/T6a and residual batch
  hydration readback: no severe source blocker found in that scope. No commands,
  tests/types/build/browser/manual QA were performed. Source review is complete;
  T10 acceptance remains pending the actual manual QA, not an active code review.

## Verification

T5b/T6b read-only exploration is complete. Mutable classic stores and immutable
revisioned profile stores retain distinct native contracts. The user withdrew
physical consolidation; no database was opened or changed and no migration ran.
The APIRoute narrowing fix is applied and source-read back, preserving the full
allowlist assertion. One LSP probe timed out (inconclusive; zero files confirmed
clean). Tests/typecheck/build/runtime remain unrun for the latest changes.

Latest user instruction: remove user-owned manual QA from tracked work. T10 now
tracks only agent technical closure and a truthful record of unrun checks; it does
not await a user QA report. Earlier manual-acceptance references are superseded.
No deferred test/build/browser check is thereby considered passed.

User-requested accelerated execution (2026-10-06): preserve functions, saved
contracts and existing tests; remove redundant orchestration/checks, not safety.
Writers run only focused RED→GREEN tests and typecheck for their affected files.
Full frontend suite and build run once on the integrated functional block, not
once per helper or agent. One combined mocked browser pass at390/1440 verifies
real user flow; never contact live APIs or cancel native core actions in QA.
Backend full suite/Ruff/14 goldens run when backend/financial changes warrant
it and at T10; migrations/auth/preservation still receive focused regressions.
Final commands: backend `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/ -q`
and `ruff`; frontend `npm test -- --run`, `npm run typecheck`, `npm run build`.
Native ASSESS decides any additional independent verification; RDD remains off.

## Execution status

### Accelerated active plan — supersedes earlier sequential scheduling

User explicitly requested fewer unnecessary tests, parallel subagents and YOLO.
Main HEAD `7d69af8` already includes validated v1 pure repeat mapper (614 tests,
prior types/build and exact backend-bound readback); do not remap that evidence.
T1 complete; T2 listing/historical/classic complete, profile repetition still open.
Two concurrent source writers operate only in separate same-clone worktrees:

- Sessions v1–v4: completed writer `mux1jhe1-v-tsy4`; acceptance pending,
  `odd/reestructura-profile-sessions`,
  `<TEMP>/reestructura-parallel-kr224zw6/profile-sessions`.
  Wire original-version saved requests into existing creator, using exact
  registry revision/hash and dataset digest, fail-closed loading/races, preserve
  untouched wire fields and fresh behavior. Reuse accepted v1 helpers.
- Batch v5: completed writer `mux1ji5e-w-efx5`; acceptance pending,
  `odd/reestructura-profile-batches`,
  `<TEMP>/reestructura-parallel-kr224zw6/profile-batches`.
  Add saved-request repeat hydration to batch creator; preserve requested
  constraints and immutable sources/strategy/policy, generate new request
  identity, do not mistake sessionStorage recovery for repetition.
- Shared list/detail profile entry actions can be implemented independently
  while isolated batch corrections finish: one sole source writer on main
  `stage`, four existing list/detail component/test files only. No creator/helper
  edits there and no main source integration while this writer is active.
  Acceptance still waits for both creators and combined integration. Full
  suite/build/browser run once for the functional flow; parent owns commits.

T3–T9 retain original acceptance criteria and remain pending, not deleted or
prematurely checked. T10 closes full verification and user-controlled delivery.
No dependency installs, real DB/API access, destructive migration, or push.

Both writers settled with no backend/API changes, four allowed files each:
- Sessions: RED missing new repeat module,52 existing tests pass; GREEN74 focused
  across3files/typecheck/whitespace. Source hashes match parent observations.
- Batch: RED1failed17pass; GREEN21focused/typecheck/whitespace/detector[]. Actual
  helper test is `profile-batch-repeat.test.ts`; writer command `.tsx` suffix
  discrepancy is checked by an exact-path spot-check, not assumed proof.
- ASSESS at both roots cannot classify undeclared untracked helpers; native plan
  treats unknown as high. One read-only verifier `mux2clya-x-f5bk` checks both
  candidates, only focused command spot-checks and concrete named risks:
  post-edit v2/v3 coverage compatibility and v5 catalog/old revision publication,
  fresh→base→fresh recovery isolation, valid saved time-field preservation.
  No extra full suites/build/browser or source changes during readback.
  Verifier finished: exact74session/21batch spot-checks pass and hashes stable.
  Findings require correction before acceptance:
  A edited v2coverage80 and v3coverage2/Audazmax1 actually accepted in helper
  probes; no backend write tested. Revalidate edited policy-specific caps.
  B same-mounted fresh→base→fresh loses fresh recovery by control-flow evidence
  (not mounted reproduction yet); pending/late catalog drops exact recovered
  profile revision, blocking validation; valid v5 end/duration bounds fail closed.
  No production unsupported-v1-capability finding; no equivalent local missing
  strategy rejection proven; no stale-validation submission demonstrated.
  Two isolated correction writers now active: A `mux2ky2r-y-wz1k` cap guard
  +two targeted regressions; B `mux2kyvx-z-880y` recovery transitions,
  independently pinned old profile and original time preservation.
  B may extend only batch-model.ts/test as needed; no backend/protocol changes.
  Corrections run affected tests/types only, not full suites or broader audits.
  A correction `mux2ky2r-y-wz1k` finished: realRED21pass/2fails, GREEN23helper,
  types/whitespace. Parent short body read confirms post-edit versioned guard;
  all4candidate hashes match and page bytes remain unchanged.
  Parent marks new helper paths intent-to-add for exact native risk assessment
  (no commit): fresh ASSESS medium/large/RDD-off,self-checks stand,no independent
  rerun required. Session integration/browser acceptance still pending.
  B correction `mux2kyvx-z-880y` finished: initialRED4fail25pass, GREEN30
  affectedtests/types/whitespace; mounted fresh→base→fresh and old-profile delay
  regressions added. Disabling the new generation guard gave1fail29pass as
  mutation sensitivity, not an unmodified-baseline RED. Parent readback found
  a remaining overrestriction: batch-model rejects every edited start for a
  time-bounded saved request, even when original end/duration remain valid.
  Narrow model correction `mux32bys-11-l7rv` settled:2actualREDfailures/9pass,
  GREEN11model/helper/typecheck/whitespace; valid edited starts preserve duration
  and absolute end, only invalid resulting end fails; saved null elapsed is
  supported by backend and preserved via repeat marker, fresh behavior unchanged.
  Parent short model read and6hashes match; prior page bytes unchanged.
  B new helper paths intent-to-add resolve assessment: medium/large/self-checks
  stand; reviewDue slice_budget_reached465lines informational under RDD-off.
  Final correction permits compatible explicit start changes,
  reject only invalid resulting bounds, and check nullable saved elapsed limits
  against actual backend contract. No UI redesign, new sources or broad suite.
  Shared-action writer `mux2v0st-10-zkl7` settled:15 actualREDfailures/93pass,
  GREEN108focused/typecheck/whitespace,4files68add12del. Parent diff/hash4match,
  ASSESSmedium/large/RDD-off,self-checks stand. Routes1–4/nueva/perfil,
  5/nueva/sesion,classic/nueva with encodedbase;unknown/loading/error fail safe.
  Main source writer released; all correction workers settled. Next is exact
  byte integration of A4/B6 files, preserving main4entry files and parent metadata,
  then one combined validation. Previous mechanical integration writer
  `mux3oswb-12-kna0` is no longer active in this resumed session.
  Recovery confirmed all ten integrated creator/helper/test files are byte-exact
  matches to the final isolated candidates; the four entry files are preserved.
  Current HEAD remains7d69af8 onstage,15pending paths,no source writer active.
  RDD clone-localoff independently confirmed. Integrated ASSESSmedium with
  fallback-small profile requires independent verification;903diff lines trigger
  informational slice_budget_reached, not permission to enable RDD.
  Verifier mux4v6nk-2-z608 settledPARTIAL:42files/663testsPASS,typecheckPASS,
  buildPASS579.91kBwarning,diff--checkPASSwithline-endingwarnings.
  Suite started16:31:52,duration77.67s; stdout preserved in verifier transcript,
  no disk log. Expected negative-status fixture emittedbogus-statusmessage.
  All14frontendSHA256hashes stable; canonical sorted compactJSONmanifest digest
  224651775fb436a318e0fac4af4104a653d4c379f99fe80374355e8a01e4e07a.
  Read-only contract review found no newly confirmed candidate defect.
  Browser QA not yet run; no screenshots. Parent confirmed installedCLI; blocker
  is mock-harness preparation, not browser runtime availability.
  QA writer mux50pjr-3-n454 settled with one352line harness:
  odd/qa/reestructura-profile-repeat.cjs; nodesyntax/fixturechecksPASS,
  no app/backend edits. Browser not run. Harness explicitly omits mounted
  recovery/race/retry cases; retain existing targeted test/contract evidence
  without claiming these gaps browser-verified.
  Parent full script read caught unconditionalfalse v2/v3 capplaceholder despite
  real negative assertions later. Correction mux5jzjl-4-s0qn settled: removed
  placeholder, retained real capnegatives, aligned summary/dataset/scope/queue
  and rationalcapfixture shapes. Nodesyntax/self-fixturesPASS; appunchanged.
  Verifier mux5t21e-5-oae9 settledPARTIAL:5173occupied; no browserchecks,
  syntheticrequests or screenshots. Unownedlistener untouched; ownedViterejected
  strictPort. PowerShellstdin continuedafterguardthrow; invocationfailure only.
  Source14hashmanifest unchanged; harness2c44abdb2459930b02717c167773e3c0559a6f26d32798bb0b173ec67a048f68.
  Logs:OS-temp/t2-profile-repeat-qa/vite-20261006-165836.stdout/stderr.log.
  Parent separatelyconfirmed5187free,changedonlyharnessBASEliteral,andcreated
  OS-temp/t2-profile-repeat-qa/run-owned-profile-qa.ps1 forsingle-Fileexecution,
  correctfrontendcwd,strictPort5187,unreachableproxy,ownedPID/namedCLIcleanup.
  Verifier mux5xf5c-6-7lh0 settled PARTIAL: owned Vite5187 ready430ms,
  Chrome openedaboutblank, but installedCLI rejected --filename before QA.
  Zero acceptancechecks/requests/screenshots;14sourcehashesstable.
  Harnesshash057ef67e13870c142eaccc9c4453ee58eb63b5a35ccd6fcba856ee0ce51f3d7d.
  CLIerror preserved in transcript; VitelogsOS-temp/t2-profile-repeat-qa/
  vite-20261006-170129.stdout/stderr.log. No confirmed application defect.
  ParentCLIhelp confirms positional-onlyrun-code. OS-tempwrapper nowcalls
  suppliedNode runner execute-supplied-harness.cjs usinginstalledPlaywright,
  exactunchangedharness,ownedChrome,JSON/console/requestledger/failurescreenshot.
  Verifier mux61zhz-7-i0sy settled PARTIAL after first functional browser run:
  390v1/list,v2/detail,v3/list,v4/detail reached4syntheticPOSTs;v5/list hydrated
  then harness241 waitedCapitalDOP whileconditionshiddenonstep0/fixtureEUR.
  1440/capnegatives not reached.106APIrequests102GET4POST,pageerrors0;
  5blockedresourceerrors+8mock-created-ID404s. Exceptionlostinternalchecks/body
  ledger; noassertionPASScountcertified. Inspectedv1/failurePNGsreadablebutfull
  pagefixedchromeoverlapdoesnotcertifyviewportlayout. No confirmedappdefect.
  Artifacts:OS-temp/t2-profile-repeat-qa/browser-2026-10-06T21-05-13-210Z.json,
  failurematchingPNG,2026-10-06T21-05-13-851Z/profile-repeat-390-1.png,
  runner/vitelogs20261006-170507. Source14/harness/runnerhashesstable.
  Harnesscorrection mux667co-8-ij4t settled: step-awarev5/EURcurrencyand
  scale-awareconditions,createdGETsfromsyntheticPOSTs,partialerror/checks/body
  ledgerreport,viewportwidthmetrics/PNGsandexplicitemptyfontCSSfallback.
  Syntax+5fixturechecksPASS; no browser/appchecksbywriter,noapplicationREDclaim.
  Verifier mux6hkgr-9-9u2p settled PARTIAL:46/47browserchecksPASS;390v1–v4
  createsandv5hydration/navigation/validationpass. Harness361–363reclicked
  Simulaciónaftervalidationalreadyadvanced,clearingvalidation/disablingCreate.
  1440/negativesunrun.107APIrequests4creates1validator,0batchcreates;
  0blocked/console/pageerrors;fivecreatorwidthsviewport/document/body390px.
  TwoavailableviewportPNGswereinspected;nodesktopimageyet.
  ArtifactOS-temp/t2-profile-repeat-qa/browser-2026-10-06T21-17-30-951Z.json
  plus2026-10-06T21-17-31-916Z/PNGsandmatchinglogs. Source14/runnerstable,
  harnessbaselinee8003071f2dc211bed9cf8f88e00ea3daf4ab70991c9eb4d5e16f9412bc44836.
  Parentmechanicallyremovedredundantstepclickandassertsautomaticconfirmation,
  preservingzeroPOSTbeforeexplicitCreate. No confirmedapplicationdefect.
  Verifier mux6lv04-a-9p52 settled PARTIAL:80/90checksPASS;390v1–v5create,
  1440v1–v4create;v5desktophydratedbutrestoredmobiledraftstep4blockedContinue.
  EightfalsefailuresaggregatedPOSTcountsacrosswidthswithreusedscenarioIDs.
  Cap/binding/driftnegativesunrun.213APIrequests10POSTs(8sessions,1validate,
  1batch);0blocked/console/pageerrors;all10widths390/1440withoutoverflow;
  mobile/desktop/failureviewportPNGswereinspected. No applicationdefectproven.
  Artifactbrowser-2026-10-06T21-20-52-745Z.json plus2026-10-06T21-20-53-237Z
  PNGs/logsunderOS-temp/t2-profile-repeat-qa/. Source14/runnerhashesstable,
  harness8f20ec059cff4d43bbecb5db49383300944c9922ff114ef392f726dc37222a6b.
  Harnesswriter mux6pop1-b-wefg settled PARTIAL: uniqueviewport/fixture/entry
  flowIDs/per-flowPOSTcounts andsyntheticv5repeat-keyisolationimplemented;
  syntax/5fixturesPASS,14sourcesunchanged. No functionalattempt:writerrole
  rejectsOS-tempoutputwritesdespiteauthorizedwrapper. StaticchecksnotbrowserQA.
  Verifier mux7a3u5-c-yp5h settled PARTIAL:62/63checksPASSthenruntime
  ERR_CONNECTION_REFUSED1440v2/list;Viteinitiallyready/stderrempty,causeunproven.
  390v1–v5and1440v1createpass;127APIrequests120GET7syntheticPOSTs;
  0blocked/console/pageerrors;sixwidths390/1440. DesktopfailurePNGshowsChrome
  networkerror,notappUI. Negativecasesunrun;storageisolationnotrecoveryevidence.
  ArtifactsOS-temp/t2-profile-repeat-qa/browser-2026-10-06T21-39-46-914Z.json,
  2026-10-06T21-39-47-780Z/PNGs,runner-20261006-173939.log/Vitelogs.
  Frontend14/runnerstable,harness5cfe8bbf2de5776e1c94929df49dd9a4635b6d339a5870a9f36de58e1422fc9a.
  Incidentdiagnosis mux7dvyd-d-i2da settled:actualtooltimeout240s,normal
  exit1,~18sfromVitelogcreationtofailure;timeoutnotprovenas cause.
  Ownedserverexit/lifecyclecauseUNKNOWN;readinessonlychecksinsufficient.
  ParentinstrumentedOS-tempwrapperPID/start/HTTPhealth/status/exitcodeand
  precleanup/cleanupUTCJSONL;runner180sdeadline,200scleanupgrace,toolbudget240s.
  Verifier mux7ix3w-e-8si0 settled PARTIAL:107/108checksPASS; all10v1–v5
  creationflows390/1440PASS,228APIrequests216GET12syntheticPOST(8sessions,
  2validations,2batches),0blocked/console/pageerrors,all10widths390/1440;
  mobile/desktop/failureviewportPNGswereinspected. ServerPID28548remainedalive,
  recordedHTTPhealth200throughrunnercompletion25.96s;exitcodesnullincomplete.
  PriorrefusalcauseUNKNOWN. Negativeharness434waitedcollapsedCobertura;
  caps/binding/dataset/driftcasesunrun. No confirmedapplicationdefect.
  Artifactbrowser-2026-10-06T21-46-38-497Z.json,lifecycle-20261006-174630.jsonl,
  2026-10-06T21-46-39-526Z/PNGsandlogsunderOS-temp/t2-profile-repeat-qa/.
  Parentopenedselectiondisclosureinharnessandaddedexplicitnegatives-only
  option/reportscope;existingcreationflowcodeunchangedandpriorproofretained.
  Verifier mux7opso-f-oeej settlednegative-onlyPARTIAL:4/5negativesPASS
  (5/6includingfixture),v2/v3capsandmissingexactprofile/datasetrejectbeforePOST.
  Source-metadata-onlymockkeptdatasetdigest/profilebindingssameandcreatedone
  syntheticrequest;alertwaitfailed.66requests65GET1POST,0blocked/pageerrors,
  onemock404;globalcontainment/immutabilitynotreached. Noappdefectproven.
  Readbackprofile-model/requestschemaandProfileExperimentPage175–205confirms
  supportedidentitypinsdatasetdigest/profileID/revision/digest/draw,notseparate
  source_sha256. ParentchangedONLYmockfieldtodataset_sha256foractualmismatch.
  T2 functional acceptance PASS: mux7wqlt-j-h6f6 reports 9/9 focused checks,
  including dataset digest mismatch, containment and fixture immutability.
  Requests: 58 GET, 0 POST, 0 blocked, 0 page errors; expected fixture 404 only.
  Prior 10 creation flows/viewport PNGs and 663 tests/types/build remain valid.
  Wrapper returned exit 1 because its captured runner exit code was null;
  browser JSON is PASS. This reporting defect is not an application blocker.
  Latest artifacts: browser-2026-10-06T21-57-08-670Z.json and lifecycle-20261006-
  175702.jsonl. Source, harness, runner and wrapper pre/post hashes match.
  T2 source freeze is lifted. Integration remains uncommitted: no new commit
  or push is authorized. Do not rerun verified checks for this reporting defect.
  Artifactpriorbrowser-2026-10-06T21-52-17-990Z.json/lifecycle-20261006-175121
  plusfailurePNGs/logsunderOS-temp/t2-profile-repeat-qa/arepreserved.
  Source-metadata-onlyrejection/backendfinancialintegrityisNOTclaimed.
  Userrenewedpaceconstraint:fewerintermediatechecks,functionalblocks,parallel
  agents. T3/T4read-onlymappingcompleted;no newsourcewriters/testdeletion.
  T3compatibilityfollowupmux7v3f3-i-1um1resolvedhistoricalsubset:configsStrategy
  system(transition/cold/select_interpretable/mix/ensemble,nocomponents)orparity
  coverage50/nosystem,exactflat/ladder/bold;disableunsupportedblend/random/other
  systemswithoutconversion. Versioned/strategiesdefinitionsremainseparate.
  Genuine5-stepcontrollerownsStrategy→Rules→Scope→Capital→Reviewandbranch
  fields;neverwrapexistingwholecreatorpages/nestwizards. Preservebuilders/APIs/
  repeatquery/hash. No backend/T5/T6migrationorfinancial-conversionneed.
  T4sharedresultframe/viewmodelkeepsdiscriminatedindividual/historical/profile
  metrics/formatting/routes;neverflattenincomparableKPIs. T4 mapping is ready.
  T3 historical integration writer muxku9ed-1-ej18 completed six scoped files:
  existing catalog/StrategyEditor/configuration library, strict supported-strategy
  adapters, parity coverage 50 and explicit missing/incompatible reference errors.
  Writer reports 27 focused tests across three files PASS and UI detector [].
  Reported RED was a missing-module import, not a behavioral assertion.
  Native assess attempted once: unassessable because untracked scope undeclared;
  RDD is off and the returned high-risk fallback requires independent verification.
  Verifier muxla4aq-4-1q42 settled FAIL on four confirmed structural defects:
  omitted unsupported catalog labels, ambiguous supported mix/unsupported blend
  labeling, blocked transient blank-name editing and late saved-config responses
  overwriting manual edits. All 21 inventoried source hashes stayed unchanged.
  No tests, typecheck, build, browser/server commands or artifacts ran; fix these
  known defects first, then execute the single planned final verification block.
  Correction writer muxlhr0h-6-ucr0 completed four source/test edits within the
  same six-file scope. Meaningful RED: three expected assertion failures covering
  four conditions; GREEN: 30 tests across three focused files PASS.
  Keep strict saved-strategy/submission checks distinct from transient input.
  Corrected-candidate assess attempted once: unassessable/untracked scope, RDD off;
  mandatory independent high-risk fallback still applies. Verifier muxlpc7x-9-lnv9
  confirmed all four corrections, then BLOCKED during temporary smoke script
  construction (unterminated Bash heredoc / Node Unexpected end of input).
  Zero typecheck/build/server/browser commands ran; only a temp wrapper exists.
  All 14 unrelated T2 hashes match; corrected candidate pre/post was not captured.
  No remaining deterministic app blocker was established. No scaffolding retries.
  Source freeze is lifted for unfinished T3 implementation; tests/readback remain
  evidence, not full acceptance. Group final functional checks at the completed
  wizard boundary rather than generating partial-unit browser harnesses.
  Classic writer muxm21g9-a-m8i7 returned PARTIAL: shared controller/frame added
  and classic recomposition started; combined tests 12 PASS / 48 FAIL, component
  3 PASS. NewExperimentPage.test.tsx was not migrated. No usable unit accepted.
  Resumed writer muxmi3bq-e-5rzg reports code-complete CLASSIC five-step UI and
  migrated workflow helpers within the same four-path unit. Final tests were not
  rerun: prior 12 PASS / 48 FAIL predates the latest edits, current status unknown.
  Shared API: useFiveStepWizard(5, validateCurrentStep) exposes step/next/back/goTo;
  FiveStepWizard renders shared progress/focus/navigation around active content.
  User owns manual UI QA; no automated execution or browser harness loops.
  Independent classic readback muxnk3ki-f-ngas settled with three source blockers:
  expand the selected invalid strategy before focus, map error step/strategy from
  the same chosen field (including settlement/bare conditions), and reject loading
  inside submit admission. Fixture migration also has step/setup contradictions
  and weakened F-CREATE-054 assertions; these are not newly executed failures.
  It confirms native builder/API/money/source/repeat guards remain present.
  SINGLE writer muxnr6t8-g-y073 fixes these known issues and integrates historical
  + v1–v4 + v5 native adapters into the shared controller/frame, using mapped APIs.
  Include shared Scope source selector in this same UI block, not another milestone:
  new components/WizardScopeSelector.tsx plus the already-authorized four creator
  pages. App route readback confirms classic /simulaciones/nueva, historical
  /simulaciones/nueva-historica, profile /simulaciones/nueva/perfil and v5 batch
  /simulaciones/nueva/sesion. Keep App/aliases unchanged. Explicitly confirm a
  fresh configuration on cross-contract scope change; do not silently transfer
  strategies, IDs, base/query/hash or financial values. Existing same-route repeat
  URLs remain untouched, and Back retains drafts within each native flow.
  No test/build/browser execution, financial/builder/API/storage normalization,
  hidden-all-fields workaround, test deletion/skips or fabricated acceptance.
  Preserve existing tests and legitimate edits; no deletion/skips/weakened
  assertions or invented GREEN. Prior 48 failures and unrun checks stay explicit;
  muxnr6t8-g-y073 returned PARTIAL after implementing all four native five-step
  flows plus shared Scope selector and classic loading/single-error focus fixes.
  Six changed files: four creators, NewExperimentPage.test.tsx and Scope selector.
  Historical/profile tests remain unmigrated; classic setup still edits some clean
  drafts. No tests/types/build/browser/manual QA were run; no GREEN is claimed.
  v5 stored step encoding remains native with UI-boundary restoration translation.
  Limited source review muxoljyy-h-bxt1 found seven remaining SOURCE gaps:
  classic Next still fails to select its invalid strategy; v5 UI steps are not
  persisted back/repeat restored ref is unset; Scope dataset change clears refs
  without returning to Strategy; recovery 404 can POST outside Review while
  pending navigation is locked; historical feedback is Review-only/parity50 is
  missed; profile Strategy/Capital admit invalid editable values; repeat helper
  internally validates v2–v4 via synthetic v1/default stake/flat capability.
  Last helper is outside this writer's edits and baseline causality is unproven;
  fix direct native-version validation without blaming all HEAD changes on T3.
  Native payload/client ID/ref order remain represented; NO runtime/test evidence.
  T3 stays OPEN with known code corrections, not only postponed fixture migration.
  Correction priority at next safe SOLE writer handoff; no parallel source edits.
  T4 writer was told return immediately if read-only, otherwise finish ONLY its
  current coherent source unit and return, preserving legitimate partial edits.
  T4 is now the sole active implementation block: shared discriminated result
  view-model and frame in lib/simulation-result-model.ts, components/
  SimulationResultFrame.tsx, DetailPage.tsx and BacktestReport.tsx, with narrowly
  relevant colocated tests only if authored/preserved without execution. No
  financial/KPI/denominator/currency recalculation, request/API/storage changes,
  loss of replay ordinals, recovery, provenance, exact repeat links or actions.
  T4 writer muxoqgev-i-wbx7 finished: discriminated result model and shared
  frame adopted by DetailPage and BacktestReport; eight source/test files changed.
  No tests/build/runtime/manual QA ran. Implementation delivered, final acceptance
  pending. No wizard edits. T3 correction now owns source writing: fix the seven
  documented gaps in four creator pages, profile-repeat-model.ts, profile-model.ts
  only if native validator extraction is necessary, and their existing colocated
  tests. Preserve original request versions and pending recovery identities.
  Correction writer muxp4h0h-k-mhz0 reports all seven T3 source fixes complete:
  classic focus owner; batch stage persistence/repeat restore/reselection/recovery;
  visible historical errors; native step validators and direct v1–v4 repeats.
  Six source files and six tests changed; assertions added but all execution
  deferred by user request, NOT because TDD requires activation. No GREEN or
  runtime acceptance claimed. T3/T4 await consolidated final verification and
  user manual QA. T5 is next source unit; T7/T8/T9 scout has completed.
  Consolidated source review muxpom8a-m-kyco found no additional severe T4
  blocker, but one T3 residual: dataset_sha256-only query changes can strand
  pending batch recovery at Strategy or clear unchanged repeat context.
  Minimal correction: restore UI step with every hydration (pending -> Review),
  preserve repeat context when base is unchanged. Current sole T5 writer receives
  additional narrow surfaces ProfileBatchPage.tsx and ProfileBatchPage.test.tsx
  for this correction in the same handoff; no new parallel writer/review loop.
  Writer muxpo2q9-l-1urz delivered T5 discovery and residual T3 fix: native
  independent pagination and immutable revision details; all batch hydration
  restores UI step, and unchanged repeat context survives hint-only changes.
  Six files changed; tests/build/types/runtime unrun. Source self-readback only.
  T5 data migration and final acceptance remain pending. T6 now owns source work.
  Same user-owned manual QA and no automatic execution loops apply. T3 is not
  silently checked off while its manual acceptance/test migration remains open.
  T7 call-site scout muxm3mj6-b-vuhu completed: repository codecs and API/detail
  consumers already discriminate stored kind/version and reject unknown schemas.
  No extra reader adapter is justified; response projection does not rewrite data.
  T7 stays pending for the intended v5 consolidation, not missing read dispatch.
  T7 execution challenge muxm91oh-c-gc8e completed: legacy and v5 both call
  run_profile_session; the financial kernel is already shared. Remaining source
  preparation/admission/orchestration contracts differ; v5 needs stored strategy
  revision/hash and batch policy not present in legacy requests. No source-format
  barrier was established. Do not add a redundant wrapper or retire legacy writes.
  T7 stays pending for scope reconciliation rather than speculative conversion.
  Profile-step scout muxmevt9-d-1j7x completed native field/action/guard mapping.
  Strategy capabilities/definition lookup/stake units require explicit profile;
  use a prerequisite/context picker inside the shared Strategy flow, not an
  implicit first-profile selection or a second wizard. Preserve v1–v4 builder,
  source rechecks/uncertainty and v5 ordered exact refs, validation invalidation,
  frozen pending-create recovery. Scope keeps compatible dataset/start draw;
  Rules keeps selected profile/settlement; native capital/limits parsing stays.
  Profile adapters remain pending; this prerequisite design is not implementation.
  Preserve native builders/routes/base/configuration/hash; no nested full creators.
  Profile as a source within the same wizard is already required by T3, not an
  open question permitting a link to a second independent profile wizard.
  T9 scout muxlhzmp-7-eu0m completed: distinct import contracts share promotion,
  advanced generic import is already folded; ordering/guarded experiment delete
  exist. Preserve profile/mapping/source/clock bindings and replay run ordinals;
  no dataset delete or per-run reorder contract is inferred. No live operations.
  Read-only wizard scout muxlnhyz-8-iaui prepares exact controlled-step extraction
  for the next genuine five-step functional unit; no duplicate source writer.
  T3 remains incomplete: genuine shared five-step controller still follows.
  T8 scout muxlajv5-5-e93c completed: agent API is mostly an authenticated facade
  over native handlers. Preserve native/browser versus agent auth policy, token
  source and intentional agent-prefixed links; avoid inventing a second service.
  The genuine shared five-step controller and profile step adapters remain next;
  T3 is not complete until all branches share step ownership.
  Previous T3 writer muxk3xli-1-8igi and T5 scout muxk3ykh-2-8gzv failed;
  user reported fetch failed after three retries. Exact network cause unknown.
  Historical edit surfaces remain clean; no partial writer changes to recover.
  Incident task muxkgxkj-4-hfre became unavailable in the runtime task registry.
  One bounded relaunch: T3 writer muxku9ed-1-ej18 remains the sole writer.
  T5 scout muxku9yx-2-ik8b completed: common discovery/load must discriminate
  mutable classic configurations from immutable revisioned profile definitions.
  Preserve UUIDs, revision/hash references and saved experiment snapshots;
  additive mapping/dual-read precedes backfill, never payload flattening.
  Non-lossless legacy conversion/labeling remains a proposal for T5, not a
  guessed migration. T5 implementation is still pending, with no live changes.
  T7 scout muxkyuyg-3-heih completed: v5 batch envelope and session engine are
  distinct; dispatch historical readers by original kind/schema, never rewrite
  request/result bytes or infer financial conversion from matching staking names.
  Existing v2–v4 repeat hydration through a v1 placeholder is not reader parity.
  Exact consuming UI/call site remains unmapped; T7 implementation is pending.
  T3 writer muxku9ed-1-ej18 confirmed running at this routing boundary, last edit;
  do not duplicate it or touch its historical surfaces.
  No retry loop or duplicate active writers.
  T6 scout muxk3zk4-3-qqor completed: preserve classic first-match best versus
  modern profile maximum-payout best and immutable profile/dataset/request
  identities. Shared projection must retain provenance and money semantics;
  additive mappings/dual-read precede cutover, never destructive conversion.
  No unresolved product choice unless explicitly redefining settlement results.
  No repeated T2 matrix or full suites/types/build. One focused check set for
  the new functional unit, followed by its required independent boundary check.
  Preserve current payloads/financial semantics and disable unsupported entries;
  no backend migrations, installs, live DB/API calls or test deletion in this unit.
  No automaticrestart/retryorapplicationchanges.
  No appedits,repeatedsuite/types/build,orclaimofrecoverycoveragefromisolation.
  No app/backendedits,newbroadercoverageorfull-checkreruns.
  T2 browser acceptance passed; never use/stop the unowned 5173 listener.
  No additional full suites/types/build. Source+harnesshashesmustremainstable.
  T2 stays open until functional acceptance; harnessselfchecks are not browserQA.
  Do not rerun passing suite/types/build without source changes. No live API/DB.
  No behavior changes or test deletion during assembly. Backend/goldens are
  deferred to relevant backend changes/T10, not repeated for frontend integration.
- T2 integration is functionally accepted by independent combined evidence,
  not writer self-checks. Marked complete at the user's explicit request;
  commit/delivery is separate and remains pending explicit authorization.
  T3 is active; T4 is mapped; T5/T6 are parallel read-only preparation.
- User offered manual QA and asked to delete old tests; clarification of old vs
  obsolete/duplicate is pending. No test deletion or cleanup writer launched.

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
- T2 unified UI: `94c9f9d` — `feat(web): show unified simulation pages by scope`.
  588 frontend tests, typecheck/build and 23 mocked-browser checks at 390/1440
  passed; documented mixed-render RED gap, font, bundle and LSP limitations.
  Not pushed; whole T2 remains open for repeat.
- T2 historical repeat: `b4ddadc` — `feat(web): repeat historical runs from saved snapshots`.
  598 frontend tests, typecheck/build and 36 normal Chrome checks at390/1440;
  inherited premature-submit hazard corrected, no live writes or push.
- T2 classic expected-source backend guard: `b100f43` —
  `feat(api): guard classic creation with expected sources`; 57 API tests,
  906 full backend tests, Ruff and byte-stable independent verification.
- T2 classic frontend snapshot guard: `b871153` —
  `feat(web): pin classic repeat source snapshots`; 607 frontend tests, types,
  unchanged-production build and 62 normal Chrome checks; no live writes/push.
- T2 classic repeat entries: `b39f2d1` —
  `feat(web): expose classic repeat entry actions`; 610 frontend tests/types/build,
  34 normal GET-only Chrome checks (186requests,zero mutations), not pushed.
- T2 profile-v1 model prerequisite: `7d69af8` —
  `feat(web): preserve saved profile v1 repeat requests`; 614 frontend tests,
  types/build and backend-contract readback. No UI wiring yet; not pushed.
- T2 profile repeat UI/v2–v5 and T3-T10: pending.

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
- UI work-unit commit: `94c9f9d8ee965433283c96bfcd29e7afc0f2cbe4`
  (`feat(web): show unified simulation pages by scope`), on `stage`, not pushed.
  Repeat is unimplemented. Keep T2
  unchecked until all three units have checks and commit evidence. The original
  mixed-render RED gap and fallback-font-only QA remain explicit limitations,
  not backfilled evidence. T3 wizard and T4 common result remain separate.
- Repeat mapping found safe existing classic draft field mapping, but classic
  submission adopts current catalog provenance rather than binding saved hashes.
  Frontend display-only provenance does not satisfy snapshot-preserving repeat.
  Profile v1-v4 and v5 require version-specific saved-request hydration; historical
  exact prefill was resolved by follow-up scout `muwuq2ij-c-efz4`: historical
  detail GET returns the complete saved create config, and POST already rejects
  stale history/rankings hashes with 409. Current creator instead uses mutable
  game settings and catalog hashes; preserve saved game/config/hashes on repeat.
- Next authorized repeat work unit is historical-only: detail action to existing
  creator, saved-config draft mapping and exact submission/stale-409 regressions.
  Candidate surfaces: `pages/backtests/index.tsx`, `backtest-model.ts`,
  `BacktestsPage.test.tsx`, and targeted model tests if applicable. No backend,
  route-table, strategy/profile wizard, database or financial-engine changes.
  No automatic rebind to current hashes; explicit rebind UI is outside this unit.
  Writer `muwuwfdo-d-k71o` completed within four historical frontend surfaces:
  detail/list repeat links, saved-config draft mapping with explicitly pinned
  inputs, stale-load protection, actionable load/source-409 errors.
  Observed RED: 5 of 7 page tests failed on required behavior before implementation.
  GREEN: 12 historical/model tests, 57 App/client, full 595 tests / 40 files,
  typecheck/build passed. Chunk warning: 554.81 kB; expected bogus-state fixture
  remains recorded. A first npm command from repo root failed; correct-cwd retry
  and all final commands passed. Increment +182/-29, tests +119/-4.
  Parent assessment: medium risk / large writer / RDD off, self-checks sufficient.
  Read-only functional verifier `muwvaok4-e-cbuh` is checking 390/1440 actual App
  repeat/edit flows with all API calls intercepted; only synthetic backtest POST
  responses are permitted, no live backend/database writes. Four source hashes
  pinned; parent progress-document writes do not count as source drift.
  LSP probe: one auxiliary ESM import warning, three files inconclusive, none
  confirmed clean. Historical unit is not accepted/committed before browser QA.
  Browser QA found an Enter hazard: pressing Enter on step-3 Siguiente can
  advance and trigger a synthetic create POST before explicit confirmation.
  Source hashes still match. Space also reproduced unintended submission;
  the earlier Space workaround is withdrawn. Explicit harness cancellation of
  Siguiente default action may isolate remaining data checks, but is not an
  application fix or normal Enter/Space/click workflow PASS. Preserve both
  incidents and compare baseline `94c9f9d` before claiming causality; finish the
  remaining payload/error checks and end hashes before a minimal correction.
  Verifier final FAIL: Enter, Space and pointer click each sent one premature
  POST from step-3 Siguiente; baseline `94c9f9d` has the same button hazard.
  This is inherited, but still blocks the current repeat flow's functional
  acceptance. Four source end hashes match. Instrumented 390/1440 checks
  confirm saved config/pinned c/d hashes, explicit edited-field preservation,
  immutable original, 409/no-rebind, invalid-base blocking and fresh defaults;
  those checks do not establish a safe ordinary creation workflow.
  Failure artifacts: `C:/Users/luism/AppData/Local/Temp/t2-historical-repeat-qa/`.
  Next bounded correction: only historical `index.tsx` and `BacktestsPage.test.tsx`
  to prevent next-button native submission, add a regression sensitive to the
  actual DOM/default-action hazard, then rerun ordinary click/Enter/Space browser
  progression and explicit create without harness cancellation. No commit yet.
  Correction worker `muwvq2i8-g-y4fq` completed +24/-1: distinct next/create
  keys prevent DOM type morph, with focus restored to the new step action.
  RED: all three DOM-identity cases failed; JSDOM did not reproduce native POST.
  GREEN: 15 historical/model, 57 App/client, full 598 tests / 40 files, types
  and build passed; chunk warning 554.84 kB. Parent confirmed corrected hashes:
  index `226bd630ffa8084118e5e37e02ef3a61dce6e0df967c0ee7be765257adf6ff8d`,
  page test `8a9213d95e810e1b09d0ff60d9362978e47a40c53725ea8e6a0f5545d4d5f8f5`;
  both model hashes unchanged. Medium-risk assessment again admits self-checks;
  read-only verifier `muwvzmeo-h-9n30` must prove normal Chrome click/Enter/Space
  have zero premature POST and one after separate Create, with NO cancellation
  instrumentation. All prior failure artifacts remain preserved.
  Verifier `muwvzmeo-h-9n30` finished PASS: 36 normal-browser checks at390/1440;
  pointer/Enter/Space each produced zero premature POST and exactly one after
  separate Create, distinct DOM nodes and correct focus. Saved c/d config,
  edited fields, 409/no-rebind, invalid bases, stale loads and fresh e/f all pass.
  255 intercepted API requests (237 GET / 18 synthetic backtest POST), zero
  unmapped requests, live writes, page errors or unexpected console errors.
  Planned console messages correspond to injected failures. Four hashes stable.
  Parent accepts the historical repeat unit; commit
  `b4ddadc74f063449bde94ae8c6b4cc976d7a3c23`
  (`feat(web): repeat historical runs from saved snapshots`), stage, not pushed.
  Corrected normal artifacts: `C:/Users/luism/AppData/Local/Temp/t2-historical-repeat-qa/normal-corrected/`.
  Mocked API/fallback fonts do not prove financial reproduction or live integration.
  Read-only scout `muwvbovp-f-e43q` is deriving the next classic source-guard
  envelope/test scope; it does not authorize a broad mixed creator rewrite.
  Classic repeat requires a separate additive expected-source guard; v1-v5
  hydration remains separate. Do not bundle three editors or expand into T3/T7.
- Classic guard preparation is complete: backend-only next unit derives optional
  `expected_sources` with four saved fields (history/rankings IDs and SHA-256s).
  Compare before queue/write, return 409 on mismatch; absent guard preserves old
  clients. Planned edit surfaces are `laboratorio/api/experiments.py` and
  `tests/test_api.py`; frontend body/seed integration follows separately.
  Parent confirmed actual create uses `data.history.sha256`, `RANKINGS_SHA256`
  and `settings.*_path.name`. Capture these once for both check and submit;
  do not substitute a blindly assumed history constant. Existing tmp-DB/API
  fixture and classic create/draw/stake/auth/quota test grouping are confirmed.
  Historical unit is now accepted/committed, enabling the next classic guard
  work unit within those two backend surfaces only. Test-first: each mismatching
  ID/hash returns 409 before submit/insert, matching snapshots persist exact
  sources once, malformed/partial snapshots reject, old omitted guards preserve
  create/draw/stake/auth/quota behavior. Frontend source seeding follows in a
  separate unit; no profile/wizard/engine or database migration expansion.
  Worker `muww89i5-i-u6g6` completed the two-file guard: strict complete
  `expected_sources`, explicit-null 422, sanitized stale 409 before preflight,
  admission identities captured once and reused for submission. Observed RED:
  five guard cases returned 422 instead of expected 409/201 before implementation.
  Reported GREEN: 57 API tests, 906 full backend tests, Ruff; two existing
  dependency deprecations. Parent ASSESS: medium/large/RDD-off, self-checks stand.
  Incident resolved by read-only verifier `muwwxgmo-j-wv75`: in-memory restoration
  of the six-line catalog set to its original one-line spelling exactly produces
  worker SHA256 `959afbbd7e176ea2d2a78e58609932bffe412e6ec6b0fb61630e085d4aa0ee84`.
  Sole byte delta proven formatting-only; actor/tool origin remains unknown.
  Independent current-byte GREEN: 57 API tests, 906 full backend tests, Ruff,
  whitespace check. Two existing websocket dependency deprecations remain.
  Before/after hashes stable: production326
  `a7aaf8ea24cdd8401ffebd2ace321200f7590015967593dd3dd4b40d21e6988e`;
  test1517 `1a0cacb412b1656e99d17a2f6d50fa5eb2c80b4b358a052b78282bc266034ec8`.
  Parent accepts this backend-only unit; committed as
  `b100f431125ca3c8921fa264b37424f55009c34d`
  (`feat(api): guard classic creation with expected sources`), stage, not pushed.
  Frontend classic binding and profile repeat parity remain pending. Next: map
  existing classic creator hydration/source typing/tests read-only, then derive
  a separate bounded frontend guard-integration unit; no live DB or push.
  Scout `muwx6spx-k-ssbl` mapped `client.ts`, classic creator and existing tests:
  base submissions must validate/pin four saved source fields, fresh must omit
  the guard, and exact stale-source 409 needs distinct copy from queue 409.
  Scoped challenge `muwxazdc-l-7y9n` clarified the parity premise:
  drafts retain saved coverage but serialization uses current catalog for parity.
  The hypothetical17→29 substitution is source reasoning, NOT an executed valid
  classic request: backend contracts require parity coverage50. Other supported
  saved conditions/strategy fields round-trip; unavailable current catalog/draws
  may reject safely. Classic request contains no game-rules snapshot, so neither
  the four-source guard nor this unit promises historical global-rules replay.
  Next unit is three frontend surfaces only: `api/client.ts`,
  `pages/new-experiment/index.tsx`, and `NewExperimentPage.test.tsx`.
  Test-first: exact saved guard on base POST, omitted fresh guard, fail-closed
  invalid/missing source fields, stale-source409 distinct from queue409, explicit
  retry retains guard and edits, base async/reset protections retained.
  Worker `muwxfziw-m-tyy4` completed the three-file guard (90 additions/5 deletions):
  runtime fail-closed saved fields, active-base pinning, base-only snapshot POST,
  fresh body unchanged, and exact stale-source409 versus generic queue409.
  Observed RED: intended base-payload assertion lacked `expected_sources`.
  Writer GREEN: 57 creator tests, 66 App/client/model tests, 607 full tests/40files,
  types/build; existing555.69KB bundle warning and intentional JSDOM bogus-status
  logs. Detector `[]`, whitespace pass; financial goldens NOT rerun (untouched).
  Parent ASSESS medium/large/RDD-off: self-checks stand; functional QA still due.
  Parent corrected one error-copy literal: mismatch may predate opening, so say
  current sources differ from saved sources without inventing when they changed.
  No meaningful new RED for this literal-only clarification; current-byte reruns
  and normal Chrome QA assigned to verifier `muwy60gq-n-166s` before acceptance.
  Freeze: client377 `e99c43a4b8681ae5c38271bd4d88dbd1485136bf7e3206b2a498fe92a9dafc76`;
  creator664 `ee80aa505839623ae8cc8f18d0b368457e8cbbebc54573d9bf831a3fdd2b1b56`;
  tests1159 `e7ff81a27382495a043487c2f9dba4a771a74aff76e086fa8b4dab04a4855f08`.
  Current-byte verifier observed creator FAIL: 56 passed/1 failed at test897;
  parent copy edit left the old `/fuentes.*cambiaron|nueva simulación/i` assertion
  unmatched by the clarified current-versus-saved message. Parent-caused assertion
  mismatch, not original writer GREEN or newly invented feature RED.
  Preserve the three-source freeze while verifier completes remaining commands
  and functional QA; retain failure logs. After completion, correct that one
  test to assert actual stale-source semantics and rerun affected checks.
  Initial browser harness failed after deliberate synthetic POST: its blend
  fixture included unsupported `system:null` (serializer correctly omits it),
  and detail replay/trajectory GET mocks were missing and safely blocked.
  No backend traffic or source changes. Preserve initial artifacts separately;
  verifier corrects only temp fixtures/mocks in a distinct subfolder. Neither
  this harness-only failure nor future browser PASS erases the test897 failure.
  Verifier `muwy60gq-n-166s` completed PARTIAL: full606 passed/1 failed of607,
  creator56/57 (same test897 only); typecheck/build/whitespace PASS,555.69KB warning.
  Normal Chrome PASS: 48 main +14 viewport/focus/touch checks at390/1440,
  native pointer/Enter/Space and explicit Create safe, immutable original,
  pinned four-field guards, supported unchanged/edited requests, manual409retry,
  invalid bases, delayedA→B→fresh, queue409/422/507/network, no tested overflow.
  Main289GET/19syntheticPOST, supplement100GET/8syntheticPOST; zero unmapped
  APIs/other mutations/page errors/unexpected console errors. Planned failures
  counted separately. Four fullPage and six viewport PNGs inspected by verifier;
  ordinary viewport evidence resolves fixed-header/nav composite ambiguity.
  Three baseline hashes stable, owned PID2892 stopped; no live API/DB.
  Artifacts: `C:/Users/luism/AppData/Local/Temp/t2-classic-repeat-qa-N08zOr/`
  (`final-contracts`, `viewport-final`); all initial/intermediate fixture/control/
  syntax/desktop-threshold incidents preserved separately, not application defects.
  Limits: list entry not exercised; bounded async case, fallback fonts, not
  financial reproduction or wholeT2. Final step focus falls to body but Create
  is Tab-reachable and touch-safe; no new focus fix mixed into this unit.
  Parent now changed ONLY test897 to assert the exact current-versus-saved
  stale-source sentence (not a weakened OR). Production remains browser-verified.
  Fresh ASSESS medium/large/RDD-off self-check plan unchanged. Read-only continuation
  `muwypfp9-o-wofg` completed PASS: 57/57 creator, 607/607 full (40/40files),
  types and whitespace. In-memory assertion replacement reconstructs prior test
  hash, proving exactly one semantic assertion correction, no skips/suppression.
  Production hashes match final normal-browser baseline; test final hash
  `1d1db70034cd865847758e6c1587f99ecd93e0ee74ee94584ad791aeb55b7265`.
  Prior production build555.69KB and browser48+14checks retained, NOT rerun;
  production unchanged. All earlier test/harness failures remain preserved.
  Parent accepts this scoped frontend guard unit; committed as
  `b871153a235244d26623498fe8a0d4b798300014`
  (`feat(web): pin classic repeat source snapshots`), stage, not pushed.
  Next separate unit: classic list/detail 'Repetir con cambios' entry actions.
  Parent bounded mapping confirmed `ExperimentsPage.test.tsx` and
  `DetailPage.test.tsx` exist. List `index.tsx` existing classic action keeps
  the same encoded base URL/menu focus but replaces 'Usar como base' label.
  `DetailPage.tsx` existing nav gets a legacy-only secondary repeat Link with
  encoded id; profiles/loading/no valid detail do not expose this action.
  Allowed surfaces: those two components and their two existing test files.
  RED/GREEN: detail action absent first, list new label absent first, encoded
  href/route, GET-only inert activation, classic-only/profile-negative coverage;
  preserve comparison/back/delete/menus. Focused/full frontend, types/build,
  detector and normal mobile/desktop entry QA before acceptance. No creator/
  mapper/backend/profile or financial changes in this unit; T2 remains open.
  Worker `muwz1cl1-p-38wy` completed four files (two production lines plus tests).
  Observed RED4 intended missing label/detail-link failures,92 passed; GREEN96
  focused/610 full frontend tests40files/types/build555.83KB; detector `[]`,
  whitespace pass. Expected bogus-status logs; financial goldens NOT rerun.
  Parent ASSESS medium/large/RDD-off: writer self-checks stand. Parent diff
  confirms encoded href, legacy-only condition, preserved menu refs/navigation.
  Worker40hex hashes are Git blob identities: all four match `git hash-object`,
  not raw-file SHA1/SHA256; no drift inferred from algorithm differences.
  Raw SHA256 freeze (list331/detail419/list-test659/detail-test682):
  `75ec83f8440d5c4be73f7854babeb8e2f735a861c8bca5941c764a661186f928`;
  `db1fd2669b5941f6c9337f5b1cc7f8cfc5c7f4018e452621eb4d5d1935cf640e`;
  `4951d64634554033d677f8b0f99e946de5d080f65d433318b21291c3597f63c9`;
  `313cb0af903dc9d0333f4175583f4075b0d5fa186254ba906db39eec73513f3a`.
  Normal browser verifier `muwzh724-q-qe27` now checks390/1440 list/menu/detail
  entries into the REAL guarded creator using GET-only intercepted APIs, encoded
  query-sensitive IDs, keyboard/Escape/focus/touch bounds, profile exclusions.
  No synthetic or live mutation allowed. Verifier `muwzh724-q-qe27` finished
  PASS34 checks390/1440,186 API GETs, zero mutations/unmapped/prohibited/page
  or unexpected console errors; six planned404 console messages. Encoded IDs
  survive real list/detail creator hydration, no injected scope. Menu/native
  pointer/Enter/Tab/Escape/focus/touch pass; profilev1/v5/load/404 exclusions
  positively verified. Mobile detail target48px above nav; no tested overflow.
  Four raw SHA256 hashes stable; six viewport PNGs read/inspected. Owned server
  PID1260 stopped and ECONNREFUSED confirmed. Writer610tests/types/build retained,
  NOT rerun. Parent accepts this scoped actions unit; committed as
  `b39f2d1c121fecde8d119e3ae222272ee648ba68`
  (`feat(web): expose classic repeat entry actions`), stage, not pushed.
  Artifacts: `C:/Users/luism/AppData/Local/Temp/t2-classic-actions-qa-UhBv63/`.
  Temp harness generation/quoting incidents happened before browser execution;
  candidate browser passed its first execution. Fallback fonts/mocked GET only;
  no full creator/financial/global-rules replay or wholeT2 claim.
  Next: read-only version-specific profile repeat mapping before any writer.
  Map v1–v5 saved-request completeness, immutable dataset/revision/reference/
  policy/provenance fields, existing creators and backend admission validation.
  Recommend the smallest first version-specific unit and exact edit candidates;
  no all-version parity assumption, upgrades, T3/T7 adapters, router mirror,
  migrations, engine writes or snapshot schema changes during exploration.
  Scout `muwzqimd-r-i5do` confirms saved original requests forv1–v5:
  v1–v4 bind profileID/revision/SHA and datasetSHA with version-specific staking;
  profile rules are a stored response snapshot, not embedded request fields.
  v5 is a distinct batch with immutable strategy/admission/policy/source metadata;
  private sessionStorage restoration is not saved-record repeat.
  Conditional proposal: smallest v1-only frontend slice, not all-version wizard.
  But exact historical profile/dataset retrieval and admission-time identity
  validation are not yet proven; worker-time checks alone do not establish
  rejection before enqueue/insert. One scoped read-only challenge
  `muwzvofl-s-dmwn` completed: profile registry pages ALL stored ID/revision
  rows via `getProfiles(offset,limit)` (no single revision GET); exact dataset
  GET by savedSHA verifies artifact with missing404/corrupt409. Registered
  profile revision/SHA and dataset binding are validated before insertion/queue,
  with transaction rechecks. No backend guard prerequisite is needed forv1.
  Missing exact registry profile/dataset blocks repeat; embedded display snapshot
  is never registered or used as a substitute. No schema upgrades/current fallback.
  Parent single mapper spot-check confirmed fresh `buildProfileRequest` hardcodes
  entry policy/time nulls and requires fresh elapsed bounds. Avoid naive rebuild:
  preserve a valid original v1 wire request and overlay ONLY explicit user edits.
  Split first implementation to TWO model surfaces: `profile-model.ts` and
  existing `profile-model.test.ts`. Pure helpers hydrate saved fields and build
  exact v1 repeats against verified matching artifacts; tests use backend-valid
  wire fixtures including supported time bounds/static/seeded selectors.
  RED/GREEN: full unedited roundtrip, edited-field-only overlay, frozen schema/
  bindings/time constraints, malformed/mismatched artifacts fail-closed, immutable
  originals; fresh v1–v4 builder behavior unchanged. No UI/API/backend writes.
  Then separate creator/retrieval hydration unit, then list/detail entry actions
  with their tests. No oversized combined six-file vertical slice or fullT2 claim.
  Mapper writer `mux04gkg-t-bbd9` finished: 129 added lines, two files only.
  RED: missing helper assertion failed,15 existing tests passed. GREEN17 model,
  52 page/model,614 full40files/types/build555.83KB/whitespace. One prior unrelated
  ConfigurationsPage 'Usar' transient failed then passed full rerun; retained.
  Parent hashes match; ASSESS medium/large/RDD-off self-checks stand.
  Narrow read-only `mux138oo-u-4fdw` PASS: actual backend MAX_SESSION_ROWS10000,
  MAX_MONEY1e12, MAX_SEED2^53−1, end/duration1e9 and exact key shapes match.
  Both source hashes stable; no valid-request bound mismatch found. No suites
  repeated. Parent accepts model-only checkpoint; committed as
  `7d69af8af945a397bf1b89153015a3ee49ea3738`
  (`feat(web): preserve saved profile v1 repeat requests`), stage, not pushed.
  Unchanged-draw verification is a future UI loading requirement, not proven by
  pure helpers. No UI/retrieval/financial validation yet. Per user's pace concern,
  close and report this checkpoint before starting another implementation front.
  For eventualv5 repeat preserve original requested constraints, not silently
  policy-clamped effective values; new run identity, not prior idempotent retry.
  Acceptance/commit blocked pending that correction plus mocked normal390/1440
  payload/error/async/reset/pointer/Enter/Space/fresh checks; no live API/DB. Auxiliary ast-grep silent
  diagnostic is incomplete, not a clean claim. No T2-wide acceptance.
  Defensive parity mapper work and classic list/detail repeat actions remain
  separate follow-ups; no T3/profile/financial-engine or snapshot-schema expansion.
