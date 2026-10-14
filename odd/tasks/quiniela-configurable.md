# Configurable and auditable quiniela — ODD feature
Branch: `master` after S15-authorized delivery (former `feat/reference-laboratories` removed); approved plan: `.pi/plans/quiniela-configurable.md`; baseline: `1c5e441`.
Local work-unit commits only; Python checks use `py -3.14 -B`, disabled pytest autoload/cache and fresh project-local basetemps; never normal user data.

## Specs

### S1 — Local browser application
```text
[A1] Web local en el navegador, como hoy. Distribución mediante ZIP; sin aplicaciones nativas ni
 servicio alojado.
```
Effective delivery constraint is overridden by S13: preserve existing startup; user handles packaging later.

### S2 — Single user
```text
[P1] Una persona por instalación, sin cuentas ni inicio de sesión.
```

### S3 — Quiniela only
```text
[A2] Primera versión limitada a quiniela. Otras familias de lotería quedan fuera por ahora.
```

### S4 — Configurable game
```text
[F1] Juegos de quiniela configurables: universo de números, posiciones, orden, repeticiones y pagos.
```

### S5 — Histories
```text
[D1] Historial incluido y posibilidad de cargar otros historiales compatibles con el juego
 configurado.
```

### S6 — Verified blocks
```text
[F2] Constructor con bloques verificados de selección, apuesta y cierre. Sin código externo, plugins
 ni editor de programación.
```

### S7 — Removable and recreatable examples
```text
[F3] Los laboratorios existentes se pueden borrar manualmente y recrear fácilmente con sus
 configuraciones y reglas.
```

### S8 — Iteration, comparison and exports
```text
[F4] Duplicación con cambios, comparación de pruebas compatibles y exportación de configuraciones y
 resultados.
```

### S9 — Auditable runs
```text
[F5] Análisis auditable: trayectoria del saldo y detalle por apuesta —selección, importe, resultado,
 premio y saldo—.
```

### S10 — No parameter grids
```text
[F6] Exploración automática de combinaciones de parámetros queda fuera de esta versión.
```

### S11 — Manual recovery only
```text
[D2] Respaldo completo y restauración manuales. Eliminación permanente después de confirmar; sin
 papelera ni respaldos automáticos.
```

### S12 — Mandatory wizard
```text
[U1] Configuración mediante asistente obligatorio: juego → historial → estrategia → condiciones →
 revisión.
```

### S13 — No purchase or packaging implementation
```text
A no todo se lo mando en un zip nada de compras
ovidate de esto del zip dejalo tal cual esta no lo compliques yo me encargo luego
```

### S14 — Implementation authorization
```text
C:\Users\luism\OneDrive\Escritorio\analyzer_lotoFlet\.pi\plans\quiniela-configurable.md
aplica el plan tal cual con odd atualiza mi list todo vamos modo yolo
```

### S15 — User-authorized delivery of current work
```text
no omite todo esto pues las pruebas la hare yo manual haz commit and push y pasa todo a la rama master y elimina las damas ramas
```
Explicit follow-up selections: `Todo lo pendiente`; `Todas las demás: locales y remotas`. Deliver the current implementation only; manual testing is the user's next action, not evidence of acceptance. Include the previously unrelated pending changes. Publish non-force to existing origin/master, then remove the confirmed local branches and remote stage/feat-bossfarmer branches; never remove user data or actual worktree directories.

Approved technical assumptions, scope exclusions and acceptance examples are in the referenced plan's `Assumptions & Decisions`, `Verification` and `Out of Scope`. They are not additional silently inferred requirements. Validate each unit through public interfaces; rejected admission preserves data, counters and quota. Preserve all v1 readers and fourteen frozen reference outputs.

## Tasks

- T1 / Q1 — Profiles and versioned contracts; S3,S4,S9,S14; route: parallel bounded workers for independent profile rules and variable draw/bet DTOs, then parent persistence/API integration; status: done; commit: ce16f92/16c7418/1304f61/33aaf8c; evidence: independent259 PASS, parent3+8 PASS, Ruff17 PASS, frozen21 unchanged.
- T2 / Q2 — Compatible immutable history library; S4,S5,S14; route: bounded Q2 worker (context backstop after long Q1/incident proof); parent owns final included-history/independent proof and commits; status: blocked; commit: 3340b88171f70365b0d9940dd0cf1eb018362078; awaits user manual acceptance per S15, not independent PASS. Two unproven static concerns remain declared.
- T3 / Q3 — Verified strategy-block catalog and compilation; S6,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T4 / Q4 — Configurable replay and complete traces; S6,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T5 / Q5 — Owned laboratories, templates and integrated API; S7,S8,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T6 / Q6 — Homogeneous comparisons and complete exports; S8,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T7 / Q7 — Manual backup and validated confirmed replacement restore; S11,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T8 / Q8 — Mandatory wizard and analysis experience; S4,S5,S6,S7,S8,S9,S11,S12,S14; route: bounded wizard/results/comparison/settings work units with disjoint writers only when independent; status: pending; commit: pending.
- T9 / Q9 — Integration, documentation and final acceptance; S1,S2,S3,S10,S13,S14 and complete feature; route: parent integration plus independent high-risk verifier/browser evidence; status: pending; commit: pending.

- T10 / D1 — Commit approved pending changes, publish to origin/master, then remove confirmed other branches; S15; route: parent Git operations with fresh remote ancestry checks and no force push; status: done; commit: 3340b88171f70365b0d9940dd0cf1eb018362078; evidence: observed non-force origin/master push and13local/2remote removal,10stale registrations only. Q2 functional acceptance and Q3–Q9 implementation are not part of this delivery proof.

## Log

### L1 — Original authorized implementation request
```text
C:\Users\luism\OneDrive\Escritorio\analyzer_lotoFlet\.pi\plans\quiniela-configurable.md
aplica el plan tal cual con odd atualiza mi list todo vamos modo yolo
```

### L2 — Reconciled start state
- Read the complete approved plan. Prior commercial audit A/B and report are finished; stale audit TODO projection corrected.
- Current HEAD `1c5e441`; feature branch already selected. Four foreign staged paths must remain byte-identical (87,352 bytes, SHA-256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`). Exclude unrelated `odd/tasks/main-screen-clarity.md`.
- No native review while clone-local RDD is off. Assess returned writer mutations, follow risk-gated independent verification; unavailable assessment is not a receipt and is conservatively high.
- Job16 local preview reported exited with code1073807364. Do not assume it is running, restart it, or modify normal data for this feature.
- Source writes begin only after this document, complete Engram mirror `odd/quiniela-configurable/tasks` and nine-task TODO projection exist.
- T1 writer trigger: two independent heavy pure-contract units, disjoint files, neither imports the other's new module. Both launch in this turn; parent owns storage/API/combined definitions after they settle. Parallel writers do not touch app, migrations, original contracts, historical data, or each other's tests/docs. This is not delegation merely because T1 is large.

### L3 — Q1 implementation bindings (explicit technical decisions)
These instantiate the approved versioned-contract plan, not new product scope.

**Profile contract unit:** new `domain/quiniela_profiles.py`; strict frozen `QuinielaRules` and `QuinielaProfile`, public `to_mapping()/from_mapping()` and factory `create_profile(name, rules)`. Profile mapping is `{schema_version:2,id:<canonical lowercase UUID>,name:<trimmed UTF-8 <=120 bytes>,rules:<rules mapping>}`; factory creates a new UUID4. Rules mapping requires all fields: `schema_version:2`, `universe` (2..1000 distinct nonnegative JS-safe integers, canonical ascending order), `display_width` (1..16, sufficient to represent every number), `positions` (1..16), `played_positions` (nonempty sorted distinct zero-based indices within positions), `order_matters` and `allows_repeats` (strict bools), `multipliers` (one rational numerator/denominator per result position using existing `PayoutMultiplier`), `payout_mode` (`all` or `best`, best means maximum per matching number), `currency` (three uppercase ASCII letters), `scale` (0..6), `minimum_stake`, `stake_increment`, `maximum_stake`, `max_coverage`, `max_exposure` (strict positive integers bounded by existing MAX_MONEY). Unordered active positions require equal rational payouts. Reject duplicate/out-of-order canonical universe/positions, no-repeat positions greater than universe, invalid bounds/increments and fractional payout at minimum increment; conservative all-mode exposure/payment bounds must remain safe. New model does not enable execution or change v1. JSON lists are accepted only in documented array fields and converted without mutating caller input; no string/float/bool coercion to integers, extra keys forbidden at every level. Schema version2 only. Profile references are not the inert legacy slug contracts.

**Independent trace-value unit:** new `domain/configurable_runs.py`; strict immutable `QuinielaDraw`, `QuinielaBet`, `RunWindow`, mapping codecs. No import of new profile module, no engine/persistence or snapshot orchestration. Draw: schema_version2, draw_id (trimmed UTF-8 <=120 bytes), timestamp (canonical UTC `YYYY-MM-DDTHH:MM:SSZ`), results (1..16 nonnegative JS-safe integers, repeats allowed structurally until a profile compiler checks them). Window: schema_version2, start/end canonical UTC strings, start<=end. Bet: schema_version2, ordinal/session_ordinal/draw_ordinal (nonnegative JS-safe integers), draw_id/timestamp, numbers (1..1000 distinct nonnegative JS-safe integers), per_number (positive MAX_MONEY-bounded integer), wagered (must equal len(numbers)*per_number), results (1..16), paid (nonnegative), balance_before/after (nonnegative); money fields/MAX_MONEY aggregate bounds and balance_after=balance_before-wagered+paid, balance_before>=wagered. Include `rules_used` as a strict immutable mapping of required `profile_sha256`, `strategy_sha256`, `engine_version` strings (hashes lowercase64 hex, engine version nonempty trimmed <=80 UTF-8 bytes); no arbitrary executable content. Input bounds/extra-key behavior/immutability match profile contract; do not invent payouts or truncate numbers/results. Timestamp conversion from user zones belongs to Q2, not these values.

**Parent integration after both units:** compose validated profile references, laboratory definitions and immutable snapshots in `domain/configurable_laboratories.py`; then additive profile store/migration/API and constrained app registration. No execution endpoint claimed ready at T1. Shared public integration gets its own RED and compatibility tests, independent verification before T1 closes.

### L4 — Initial progress
Tracking and full mirror8398 created/read back; TODO now has nine tasks, only Q1 in_progress. Q1-profile worker `mv6t8qbw-1-a0x2` and Q1-trace worker `mv6t8qil-2-01wr` launched together on disjoint new paths. Their RED/GREEN evidence and commits are pending. Session work-publication reported unavailable; allocated tasks remain live and must not be relaunched. Parent next reads existing store/API wiring for integration; no normal server restart. Later task transitions append evidence here and update the task line and complete memory mirror.

### L5 — Q1 own-check progress (not completion)
- Profile worker returned10 GREEN, actual missing-module RED and factory-mapping RED (9 PASS/1 FAIL before fixing); Ruff pass, root-directory test-path mistake retained in report. Profile source/tests/docs553 added lines.
- Trace worker returned54 GREEN and missing-module RED; source/tests/docs559 added lines. Initial active LSP found3 intentional mutation-test typing errors; ONE correction task `mv6tjejk-3-epk5` changed only assertions and returned54 GREEN/Ruff pass. Later active probe confirmed1 file clean and2 inconclusive, not globally clean.
- ASSESS returned unassessable because undeclared untracked files prevent native assessment; RDD off, no retry/receipt. Independent high-risk verification required after own checks.
- Parent public API RED:53 FAIL/4 PASS, exit1,6.56s. Missing v2 routes produced404; four existing local guards already passed. Logs: `.tmp/quiniela-configurable/q1-profile-api/red-01/{stdout,stderr}.log`.
- Additive migration18/store/API and narrow profile POST guard written. Fresh bootstrap seeds when migration17 ran;17→18 never reseeds. Quota counts actual new profile JSON through existing profile counter; quota resolution and admission inside writer transaction. GREEN and snapshot-contract unit remain pending.
- Cascade diagnostics reported5 errors in unchanged `engine/active_history.py` (object History types). Git diff against baseline for active_history.py/adapter.py was empty. Do not fix unrelated legacy typing or call workspace clean; verification must distinguish inherited findings.
- TODO reviewed on explicit reminder: nine units unchanged, only Q1 in_progress; no completed task or commit claimed.

### L6 — Q1 integrated own evidence and verification handoff
- API57 GREEN/exit0/7.53s. Added3 public corruption/no-repair probes after an explicit local JSON parser exception-boundary clarification (already guarded by caller, no meaningful behavioral RED).
- Snapshot/definition codecs: missing-module RED/exit2 →18 GREEN/exit0/0.64s. Closed block kinds/roles with bounded exact immutable JSON are structural only; compiler/provenance/admission are Q3–Q5, not claimed here. Complete profile/source/strategy/conditions are embedded and hashed. New docs `docs/quiniela-snapshots-v2.md`.
- Existing migration suite observed2 FAIL/6 PASS: assertions expected17 after requested migration18. Replaced only target-version expectations with SCHEMA_VERSION; data/ownership/rollback assertions preserved.
- Combined seam job-1:266 PASS/1 FAIL/38.74s, exit1. Failure was another obsolete schema17 assertion in test_run_store. AST search safely simplified after quoted-pattern CLI safety rejection; found all five remaining target17 assertions in three files.
- Bounded version-expectation batch:3 RED failures→3 GREEN/0.86s, all retained stored data/ownership assertions. Changes limited to SCHEMA_VERSION import/assertions and current-schema test name; never change explicit historical setup/rollback versions16/14/15.
- Ruff checks/format13 initial files passed; three additional legacy test files receive final checks. Active LSP: source9 paths had1 clean/6 inconclusive, stale missing-import finding in new snapshot test and existing guarded-host int-parse warning. Python imported the new module and18 tests ran successfully, so missing-import diagnostic is not runtime evidence. Do not claim a clean workspace.
- Baseline/staging proof: HEAD1c5e441 unchanged; foreign index87352 bytes/SHA26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9; unit manifest `.tmp/quiniela-configurable/q1-scope/manifest.json` refreshed for final paths before independent check.
- Risk: items1/2/3/4 — additive migration, request guard extension, shared quota reader and serialized admission. Independent verifier required now after own checks/correction; no ordinary native review while RDD off. Q1 stays in_progress until proof and scoped local commit(s).
- Independent verifier `mv7403j2-1-di2l` launched on frozen21-file scope; original tree read-only, only scratch mutation allowed. `odd/reviews/quiniela-configurable/Q1-own-checks.md` records own checks, failed/skipped/inconclusive proof and planned four local slices. Await pushed completion, never poll/relaunch.

### L7 — Q1 independent PASS and local slices
- Verifier returned scoped PASS:142 new+106 v1+3 legacy regression+8 adversarial probes=259 PASS; Ruff16/check/format PASS. All captured stderr empty; no failed/timeout checks.21 source hashes/HEAD/foreign index unchanged before/after. Full proof `odd/reviews/quiniela-configurable/Q1-independent-verification.md`; frozen manifest made durable at `Q1-frozen-scope.json`.
- Parent reran exact reported3 regression selectors PASS. Eight adversarial probes promoted to `test_quiniela_admission_boundaries.py`:8 PASS/3.02s, Ruff/check/format PASS; added typed mutation cast/unchanged-state assertion and raw byte literal, no production correction. Original21 source hashes unchanged after promotion.
- Tooling incident isolated: two missing-import diagnostics persist despite canonical importlib.find_spec/direct import resolving exact in-project module/hash569a45a479675427efd2112224e691330aca6e603bb7542ba56bc854ebb8ea29 and runtime18+8 cases. Domain active LSP clean, CLI unavailable, restart notadvertised. lens_diagnostic_mark records false-positive dispositions only (no inline ignore/config/production mutation); do not claim a globally clean workspace.
- Local slices: profiles ce16f927736fd97d28f0056e8087932101b34b0e (553 additions); traces16c74180f17694cc1c309ca94f4300e753e80ad2 (569 additions); snapshots1304f6176f8cbf2af941da641f2d26dace50f175 (533 additions). Scope retains tests/docs rather than concealing review size. Last persistence/API slice and task closure follow. Foreign staged87352 bytes/SHA26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9 unchanged after all3 commits.
- Q1 acceptance is only contracts/persistence/API foundation; no current executable v2 lab, full replay audit UI, full-backend suite,14-golden replay or browser acceptance claim. Q2–Q9 remain pending. Native RDD stays off.

### L8 — Q1 closed; Q2 begins
- Final integration/persistence/API/evidence commit33aaf8ceb592180da3769de960d011df874d5989 observed exit0, eighteen paths1550 insertions/18 deletions including tracking/plan/evidence. Foreign index again87352 bytes/SHA26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9 unchanged. Four usable local slices now cover Q1.
- T1/Q1 marked done only after independent proof, parent spotcheck, retained diagnostics/failed evidence, promoted regressions and observed scoped commits. No push/PR/merge/deploy/startup/normal-data changes.
- T2/Q2 now in_progress, seven later tasks pending. Before any history-source write, map existing formats/timezone/metadata/quota seams and approved assumptions. Mandatory current blocker reminder addressed via canonical runtime proof and explicit resolver false-positive dispositions; no code or ignores changed to hide diagnostics.

### L9 — Q2 map and bounded technical implementation bindings
- User continuation verbatim: `continua ya termina modo yolo`. No outside-project inspection grant was provided; continue authorized feature work, do not read/change pi-lens installation. Static resolver limitation remains documented; no more ceremonial probes/retries or source relocation.
- Read-only scout mv74xss2-2-bvnr mapped Q2/S4,S5,S14. One spotcheck confirmed included metadata `zona_horaria: America/Santo_Domingo`; existing v1 ignores zone and has label-based active merge. ZoneInfo for documented zone/UTC is available, included-period offsetUTC−04:00. No dependency/startup change required. Existing immutable history persistence is Repository, not a nonexistent history_store module.
- Included schema remains metadata+sorteos_por_fecha/date keys+hora+ordered two-digit numeros; draw IDs are legacy `YYYY-MM-DD HH:MM` labels, never change result order. New adapter converts documented local instants to canonical UTC; v1 interpretation/routes/source activation are unchanged. No metadata/source_url fetch.
- New canonical uploaded JSON: strict `{schema_version:2,timezone:<IANA>,draws:[{schema_version:2,draw_id,timestamp,results}]}`. Timestamp is ISO seconds with Z/offset or naive ISO seconds. Naive imported times require explicit boolean timezone_confirmed; nested imported metadata zone is not consent. An explicit zone cannot silently override a conflicting declared zone. Included source uses its documented zone. Reject nonexistent/ambiguous naive DST times; caller must supply offset instants. Chronologically sort rows without sorting result positions. Exact repeated ID+instant+ordered results are counted/deduplicated; sameID different instant/results or sameinstant different results reject all. Distinct IDs with identical results at sameinstant remain distinct (no silent row loss); future causal context must use strictly earlier instants.
- Parser budgets: raw64MiB and400000 input rows, reject rather than truncate; declare these in preview/docs. Canonical UTC draw mappings/profile compatibility validate exact positions, universe and repeats, strict schema/integers, no extra keys/nonfinite/duplicate JSON keys. Raw SHA binds exact uploaded UTF8 bytes; canonical SHA binds normalized source JSON. Preview SHA additionally binds name, complete profile SHA, origin, zone/confirmation, raw/canonical hashes and duplicate/row metadata; no writes on preview.
- Immutable preview stores raw/canonical payload and tuple of QuinielaDraw values; to_mapping exposes bounded metadata/first3 sample, not all rows. Full raw/canonical data only enter confirmed v2 storage. SourceReference remains UUID/profileSHA/origin/rawSHA/canonicalSHA/optional rankingSHA. Imported source never claims rankings; included source must verify exact frozen rawSHA and compatible original universe/structure; archive availability/provenance/compiler validation still Q3.
- API surfaces `/api/v2/history-sources/preview` (POST), `/api/v2/history-sources` (POST confirm, GET page), `/api/v2/history-sources/{uuid}` (GET detail), and dedicated included preview/confirm routes. Imported body binds profile_id/name/raw_json/optional timezone/timezone_confirmed; confirmed POST additionally requires expected preview_sha256 and reparses/revalidates before atomic admission. Included routes read only server-configured frozen path, not client paths/origin. No preview token/client metadata trusted without recomputation. Repeated exact confirmed preview may return existing immutable source idempotently; differing hash/profile/payload rejects with no quota/counter mutation. Confirm cannot activate/merge any v1 source.
- Add migration19, new immutable source table with UUID/profile foreign key/canonical+raw payload hashes/bytes/metadata/name/confirmed-preview identity; update sequential registration and shared history-byte quota accounting only. Profile binding is complete profileSHA, not just rules. Resolve quota/countbytes/admit inside BEGIN IMMEDIATE; stored readers revalidate canonical text/hashes/bytes/metadata/profile binding rather than repair. Pagination bounded1..100, offsetJSsafe. Body ceilings and loopback guards only extended for new routes, no v1 relaxation.
- Context backstop routes the next bounded whole Q2 backend unit to a worker with explicit allowed files; parent no longer reads/writes its implementation in parallel. Worker owns test-first parser/store/API and small v1/Q1 guard seam, parent owns one full included-file check after its return (unknown-duration background), independent high-risk verification and scoped local commits. No Q3/UI/service/export/backup work started. Ordinary RDD remains off.

### L10 — Q2 writer allocation
- Initial dispatch rejected before allocation: Allowed edit surfaces included annotations instead of canonical narrow entries. Corrected ONLY that section into fourteen explicit path/glob entries and separate constraints; no duplicate/parallel equivalent task.
- Q2 worker allocated once as mv7jrgxv-1-grn7. It owns allowed backend/history tests/docs and scratch, never tracking/commits/UI/normal data. Parent waits for pushed completion, does not poll/sleep/relaunch or mutate/read the owned implementation in parallel. Session messaging/publication remains unavailable; allocation is live regardless of metadata publication failure.
- Visible TODO: Q1done; Q2in_progress; Q3–Q9pending. Q2 full included-file/independent proof and commits NOT yet observed; no Q2 closure claimed. LSP limit already declared/handled, no more outside inspection requests after user continuation.

### L11 — Delivered Q2 review and confirmed included-format correction
- User continuation verbatim: `Review the delivered subagent output and continue.` Worker mv7jrgxv-1-grn7 returned partial, not acceptance: focused22 PASS, migration8 PASS, Q1 profile API60 PASS, v1 history2 PASS/4 deselected, Ruff10 PASS. Parser missing-module RED was captured; public API-route RED was not captured and is not reconstructed. Preserve initial assertion/fixture/Ruff failures and batch03 capture incident (pytest deleted logs placed inside basetemp); no normal data or protected source mutation.
- Parent inspected public API, adapter, atomic store/revalidation, migration19, app guards/shared quota registration and foreign staging. Foreign staged four-path diff again exactly87352 bytes/SHA26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9; HEAD33aaf8c unchanged. Parent LSP store/API probe: zero confirmed-clean files, one inconclusive, Spanish UI spellchecker auxiliary findings only; not a clean-workspace claim.
- Parent full included selector FAILED exit1/0.92s at adapter line322: `included draw schema is invalid`. Actual bounded shape projection shows all105426 original rows have `hora,numeros,source_url`, whereas adapter required only two fields. Evidence `.tmp/quiniela-configurable/q2/parent-included-01/`; original failure remains retained, never rerun unchanged.
- Bounded corrective worker mv7lr32z-4-rx6w fixed only importer/tests/docs: source_url optional string metadata, never fetched/executed/provenance/rankings; two-key shape retained, unknown/non-string fields rejected. Actual synthetic1 RED ->16 GREEN; Ruff3/check/format PASS. Strengthened full test verifies every source ID, UTC instant, ordered result tuple and repeated-result count against original rows, not merely count/range. Evidence `.tmp/quiniela-configurable/q2/correction-01/`. Worker did not open included input or run full selector.
- Parent NEW corrected-candidate full included selector PASSED exit0 (background job-2,22s wall); all105426 draws, raw frozen hash, IDs, canonical UTC instants, ordered values and repetitions verified. Evidence `.tmp/quiniela-configurable/q2/parent-included-02/`. This is own functional proof, not independent verification or Q2 closure.
- Q2 remains in_progress: freeze corrected thirteen-path candidate, independent read-only high-risk verification and scoped local commits next. Q3–Q9 remain pending; no v2 execution/UI, source deletion, backup/restore or final acceptance claim.

### L12 — Independent functional verification unavailable; decision stop
- Parent froze13 paths/1825 additions/6 deletions; foreign staged bytes/hash and HEAD verified unchanged by the parent, not an independent verifier. Own full-source stdout confirms1 PASS/19.51s, stderr empty. Native ASSESS remains unassessable/untracked declaration with RDDoff; no receipt.
- Independent verifier mv7m6wla-5-ui1e returned BLOCKED/incomplete for S4/S5/S14: read spec including Log/approved plan/manifest/code/tests and inherited parent evidence, but developer restrictions prohibit writes and unapproved execution. Its authorization query timed out. It executed NO commands, wrote NO probes/report/ledger, did NOT check frozen hashes/HEAD/index or independently run pytest/Ruff/LSP. Do not claim independent PASS or fabricate nonexistent `.tmp/quiniela-configurable/q2-independent/report.md`.
- Static concerns, NOT reproduced: history store173–208 included read validation omits stored timezone/confirmation against recomputed preview; store312–314 capacity adds estimated384-byte overhead while repository159–168 counts actual columns (verifier estimates395 importedUTC bytes excluding ID/name/payload). Neither concern is a confirmed bugfix outcome; public-seam rejection/state-preservation probes remain unavailable.
- No automatic replacement/retry, additional verification ceremony, policy override, speculative source fixes, staging or commits. Q2 is blocked awaiting a decision on the unavailable independent verification and these two unresolved concerns. Q3–Q9 remain pending; no final feature completion. Recovery mirror and visible TODO updated for this valid Needs-your-decision stop.

### L13 — Manual-testing decision and exact Git-delivery authorization
- User request verbatim: `no omite todo esto pues las pruebas la hare yo manual haz commit and push y pasa todo a la rama master y elimina las damas ramas`.
- Explicit selections: `Todo lo pendiente` for commit scope, and `Todas las demás: locales y remotas` for branch removal. This supersedes earlier preservation/no-push restrictions for the known pending Git changes and this delivery only. It does not prove Q2 independently accepted or implement Q3–Q9. No new automated functional tests, speculative fixes, policy modification or verifier retry.
- Include approved Q2 source/tests/docs/evidence, this tracking document, historical main-screen task note, QA script, and the three previously staged document removals. Preserve secrets, normal data, protected datasets and ignored scratch. Origin is existing github.com/LMiguelGJ/analyzer_lotoFlet.git. No force push, reset, rebase, actual worktree-directory removal, package/startup change or deployment.
- Baseline read-only inventory: HEAD33aaf8c on feat/reference-laboratories, no local master; cached origin/master445abf8 is an ancestor (215 commits ahead,0 behind). Every other local head is already an ancestor of the current branch. Fresh origin fetch must confirm master and every deletion target before publishing/removal; new divergence requires a decision, not forcing.
- Authorized local removal set after creating/publishing master: feat/bossfarmer-design, feat/rebuild-corridas, feat/reference-laboratories, odd/reestructura-profile-batches, odd/reestructura-profile-sessions, stage, wt/editor, wt/rewrite-be, wt/rw-api, wt/rw-dom, wt/rw-fe, wt/rw-que, wt/rw-sto. Authorized remote removal set: stage and feat/bossfarmer-design only. User also approved pruning metadata records for nonexistent worktrees, not deleting actual worktree directories or detached native candidate views.
- T10 delivery in_progress. Preparation, observed local commit, non-force push and final branch list must be recorded separately. Q2 remains blocked on independent/manual acceptance; Q3–Q9 remain pending and are not represented as delivered features.

### L14 — Current work published and confirmed branch cleanup completed
- Fresh `git fetch origin` exit0 confirmed origin/master445abf835b6a52d03dd13bb15d99a6314e5ff32b is an ancestor and both confirmed remote deletion targets remain ancestors. Original thirteen Q2 source hashes matched the frozen manifest. Whitespace checks passed; no additional functional tests or verifier runs were performed after the user's manual-testing decision.
- Approved twenty-path commit3340b88171f70365b0d9940dd0cf1eb018362078 (`feat(quiniela): add immutable history sources and consolidate pending work`) observed exit0,2428 insertions/712 deletions. Includes all explicitly approved pending additions/modifications and three document removals; secrets, protected histories/reference inputs, normal data and ignored scratch excluded.
- Created localmaster at that commit without checkout of old source, reset or rebase. `git push --set-upstream origin master` observed exit0/6s:445abf8..3340b88, upstreamorigin/master configured. All earlier215 feature commits are retained in master ancestry.
- Live remote read reconfirmed master3340b88 and unchanged/ancestorstage andfeat/bossfarmer-design before `git push --atomic origin --delete stage feat/bossfarmer-design`; observed exit0/4s, both remote branches deleted. No force push/history rewrite.
- Exact prune dry-run identified ten nonexistent worktree registrations only: base-check, profile-batches, profile-sessions, wt-editor, wt-rw-api, wt-rw-be, wt-rw-dom, wt-rw-fe, wt-rw-que, wt-rw-sto. Pruned those Git metadata records, not actual directories or detached native candidate views. All thirteen confirmed local branches then removed with ordinary `git branch --delete`, not force deletion; every head already an ancestor of master. Observed exit0/2.8s; only master local and origin/master (plus symbolic origin HEAD) remained; working tree clean.
- Retained preparation incidents: initial Git128/Python1 pathspec failure on already staged deletions left the index unchanged; stage only existing approved paths and retain/assert staged deletions resolved it. Initial local cleanup guard Python1 captured onlystdout while Git prune dry-run emitsstderr; independent incident read established all tenexpectedrecords and unchanged14heads, then corrected collection before any mutation. Neither failed command was silently retried unchanged; no proof fabricated.
- T10 delivery done with actual work-unit commit and observed push/cleanup. This tracking acknowledgment is a follow-up documentation commit on master. Q2 manual acceptance remains the user's next action; two static concerns remain unproven. Q3–Q9 remain unimplemented/pending. No full-feature completion, clean LSP, automated acceptance, publication-ready UI, deployment or packaging claim.
