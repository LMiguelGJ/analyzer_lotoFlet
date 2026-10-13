# Configurable and auditable quiniela — ODD feature
Branch: `feat/reference-laboratories`; approved plan: `.pi/plans/quiniela-configurable.md`; baseline: `1c5e441`.
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

Approved technical assumptions, scope exclusions and acceptance examples are in the referenced plan's `Assumptions & Decisions`, `Verification` and `Out of Scope`. They are not additional silently inferred requirements. Validate each unit through public interfaces; rejected admission preserves data, counters and quota. Preserve all v1 readers and fourteen frozen reference outputs.

## Tasks

- T1 / Q1 — Profiles and versioned contracts; S3,S4,S9,S14; route: parallel bounded workers for independent profile rules and variable draw/bet DTOs, then parent persistence/API integration; status: in_progress (verified; integration commit pending); commit: ce16f92/16c7418/1304f61; evidence: independent259 PASS, parent3+8 PASS, Ruff17 PASS, frozen21 unchanged.
- T2 / Q2 — Compatible immutable history library; S4,S5,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T3 / Q3 — Verified strategy-block catalog and compilation; S6,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T4 / Q4 — Configurable replay and complete traces; S6,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T5 / Q5 — Owned laboratories, templates and integrated API; S7,S8,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T6 / Q6 — Homogeneous comparisons and complete exports; S8,S9,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T7 / Q7 — Manual backup and validated confirmed replacement restore; S11,S14; route: inline unless a named writer trigger fires; status: pending; commit: pending.
- T8 / Q8 — Mandatory wizard and analysis experience; S4,S5,S6,S7,S8,S9,S11,S12,S14; route: bounded wizard/results/comparison/settings work units with disjoint writers only when independent; status: pending; commit: pending.
- T9 / Q9 — Integration, documentation and final acceptance; S1,S2,S3,S10,S13,S14 and complete feature; route: parent integration plus independent high-risk verifier/browser evidence; status: pending; commit: pending.

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
