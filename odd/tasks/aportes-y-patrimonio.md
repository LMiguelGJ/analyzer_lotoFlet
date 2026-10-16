# Aportes de bolsillo y patrimonio simulado
Objective: execute the approved wallet plan without changing the engine or stored results. Branch: `feat/aportes-y-patrimonio`; base: `9275c0399db7ede98a98507b8ac552534329c942`.
Delivery: exception-ok, explicit verified integration into master, no PR requested; forecast 600–850 authored diff lines including tests/docs, coherent work-unit commits. Runners: Python pytest, Node Vitest/tsc/Vite, isolated browser.

## Specs

### S1 — Exact authorization and approved plan
User, verbatim (JSON-escaped to preserve the original trailing space and newline):
```json
{"request":"ejecuta el plan tal cual usa odd y modo yolo al final pasa todo a master y elimina las ramas creadas \n C:/Users/luism/OneDrive/Escritorio/analyzer_lotoFlet/.pi/plans/aportes-y-patrimonio.md"}
```
The complete approved specification is `.pi/plans/aportes-y-patrimonio.md`; read it in full in addition to this section. This request lifts its previous planning-only gate. It also authorizes final integration/publication to existing `origin/master` and cleanup of branches created for this delivery, only after their commits are retained in master. No PR, forced history rewrite, removal of existing detached review worktrees, or unrelated cleanup.

### S2 — Exact simulated accounting, complete chronology
User, verbatim: «asi como esta esta bien solo quiero un dato extra que me diga la verdad cuanto dinero salio de mi bolsillo».
Approved plan, verbatim:
```text
aporte = 0
billetera = 0
para cada sesión existente, en su orden original:
    adicional = max(0, capital_por_sesion - billetera)
    aporte += adicional
    billetera += adicional
    billetera = billetera - capital_por_sesion + saldo_final_de_la_sesion
```
Policy `retain-gains-top-up-v1`, one wallet per historical run, capital from that run's snapshot. Retain all gains/residuals; no withdrawals. Top up only before an actual next session, never after a final ruin. Include the last incomplete session. No sessions means 0 contributions / 0 wealth / 0 net. Use safe integers, reject booleans/invalid amounts; preserve the exact identity `final_wealth - out_of_pocket == existing total_net`. Do not replace engine totals or derive from aggregate profit or the visible page.

Approved examples, capital 2000:
| Session final balances in order | out_of_pocket | final_wealth | existing total_net |
| --- | ---: | ---: | ---: |
| `[]` | 0 | 0 | 0 |
| `[2800]` | 2000 | 2800 | 800 |
| `[2800, 2000]` | 2000 | 2800 | 800 |
| `[2800, 0]` | 2000 | 800 | -1200 |
| `[0, 2800]` | 4000 | 2800 | -1200 |
| `[2800, 0, 2000]` | 3200 | 2000 | -1200 |
| `[2800, 1500]` | 2000 | 2300 | 300 |
| `[0]` | 2000 | 0 | -2000 |

### S3 — Additive API and certified read integration
Approved response fragment, verbatim:
```json
{"summary":{"wallet":{"policy":"retain-gains-top-up-v1","out_of_pocket":2000,"final_wealth":2800}}}
```
Implement the plan's pure `domain/laboratory_wallet.py` derivation from fully validated ordered saved sessions. Same wallet in full POST projection and cold/warm detail GET. Store it only in transient compact certificate metadata, updating `_decode_certificate`'s strict summary allowlist/validation without weakening identity or integrity. Avoid computing wallet twice in the cold path; return the decoded certificate after certification. Preserve the same SQLite snapshot/epoch, warm bounded reads, cache identity and 64-entry/16-MiB limits including added bytes. Do not change list/session DTOs, existing capabilities, POST bodies, contract version or existing response fields/errors. No wallet fields in persisted result/snapshot/hash formats; old runs work without replay/backfill/migrations. GET stays read-only and quota/owner semantics remain unchanged.

### S4 — Approved three-column interface and fallback
User's exact example:
```text
 ┌─────────────────────────┬─────────────────────┬────────────────────┐
 │ Aportado de tu bolsillo │ Patrimonio al final │ Ganancia / pérdida │
 ├─────────────────────────┼─────────────────────┼────────────────────┤
 │ RD$2.000                │ RD$2.800            │ +RD$800            │
 └─────────────────────────┴─────────────────────┴────────────────────┘
```
Use «Tu dinero · Simulación» in the selected result; first two metrics use `summary.wallet`, third uses the existing net. Optional wallet DTO and strict local validation; missing, unknown-policy, unsafe/negative/inconsistent wallet means «No disponible» for the two new fields, not fabricated zero. Local absolute-amount formatter preserves unsigned example; shared money/ROI formatters unchanged. Do not calculate business funding in React or add API calls. Paginating more than 50 sessions must not change the figures or refetch detail.

### S5 — Reorder without deleting existing information
Approved labels: «Movimiento de apuestas», «Volumen apostado», «Premios recibidos», «Retorno sobre apostado», «Detalle de sesiones», «Media neta de cerradas», «ⓘ Cómo se calcula».
Retain current wagered/paid/return values; keep the four counters and session table. Move the mean into its initially closed native detail; preserve provenance separately with dates, gaps and full hashes. Keep the list's «Neto total» column but avoid a duplicate net card in the selected result. New native details help is closed by default, keyboard/touch operable, explains retained funds, top-ups, no withdrawals and unchanged bets. Preserve option-help UI, existing validation, reconciliation/loading/focus, cold paper, Archivo, square controls, responsive container layout and readable amounts. No new ROI, graph or profitability promise. Update only the three docs enumerated in the plan.

### S6 — Verification and honest evidence
Use applicable test-first RED → GREEN and each writer's self-review before returning. Execute all eight S2 examples with exact results, safe numeric boundaries, API POST/cold/warm parity, 404/409/owner/corruption preservation, no GET persistence/quota side effects, cold-only derivation/warm SQL bounds, legacy wallet absence and >50-session paging. Run the plan's focused frontend regression, tsc/build and active LSP checks. Browser checks use an isolated static/test environment with no normal DB or real writes, desktop/600/390/320, keyboard/touch and enlarged text (do not call it actual browser zoom). Independent verification reads this whole file and approved plan, uses isolated state, and reports each S#. Missing/failed/unavailable evidence is not PASS. No automatic timeout retries, no full frozen 65k counterexamples, no global-suite or historical acceptance replay.

### S7 — Preserve data and delivery boundaries
No changes to engine, history, rankings, `.env`, frozen inputs, `repo_ref/`, `lagacy_loto/`, migrations, saved data/formats/hashes, reference/legacy consumers, quota policy, global cache/formatters/tokens or dependencies. Never access the user's normal database for this feature. Historic OPEN/manual/integrity acceptance stays OPEN. Parent alone owns staging/commits/merge/push; workers have no delivery permission. Only delete the newly created feature branch after verified master retention and publication; preserve detached review views and unrelated work.

## Tasks
- T0 — S1,S7; route: inline preparation; status: in_progress; tracking document/mirror/projection and feature branch before source writes; commit: pending.
- T1 — S2,S3,S6,S7; route: backend worker, parallel with T2 (independent substantial unit, disjoint exact files); status: pending; commit: pending; RED/GREEN: pending.
- T2 — S4,S5,S6,S7; route: frontend worker, parallel with T1 (fixed DTO, disjoint exact files); status: pending; commit: pending; RED/GREEN: pending.
- T3 — S1,S4,S5,S6,S7; route: inline docs/integration/browser; status: pending; commit: pending; checks: pending.
- T4 — S1–S7; route: independent read-only verify, after own checks/native assessment; status: pending; commit: evidence commit pending; verdict: pending.
- T5 — S1,S7; route: inline verified master integration/publication/new-branch cleanup; status: pending; commit: delivery evidence pending.

## Log

### L1 — Original execution request, verbatim (JSON-escaped)
```json
{"request":"ejecuta el plan tal cual usa odd y modo yolo al final pasa todo a master y elimina las ramas creadas \n C:/Users/luism/OneDrive/Escritorio/analyzer_lotoFlet/.pi/plans/aportes-y-patrimonio.md"}
```

### L2 — Preparation and routing
- Initial state: master/origin-master `9275c0399db7ede98a98507b8ac552534329c942`, only the approved plan untracked, no other branch. Existing detached review worktrees are preserved and outside cleanup scope.
- Created local `feat/aportes-y-patrimonio` at that base. No remote feature branch is needed; final push destination is existing origin/master.
- Approved plan re-read completely before work; source behavior explored during planning remains unchanged. RDD switch is off per current clone-owned status; native assessment after delegated returns still applies, without starting a review while off.
- Parallelism is the writer trigger: backend accounting/certified API and frontend DTO/UI/tests are substantive disjoint units based on the fixed contract. Writers do not edit docs, this tracker or Git state. Parent handles docs and integration, then independent verification.
- The visible TODO groups T1/T2 into one active production-wave entry so there is exactly one in-progress UI task; this file records each unit's real state/evidence separately. No requirement or work unit is dropped by that grouping.
- Delivery strategy `exception-ok`: user explicitly requested verified direct-to-master delivery, not PRs; keep coherent behavior/test/docs commits rather than invoke a PR-chain decision out of scope. Forecast is advisory; do not minify or omit tests to hit a line count. Parent notes actual counts per unit.
- No source writes, tests, database operations, installs, commits, publication or branch deletion performed yet. Session status publisher is unavailable; this does not grant or remove any task authority. Worker runtime is available.

### L3 — Initialization whitespace correction
Initialization job1 exited2 at `git diff --cached --check`: the two literal user quotations retained their original trailing space. No commit was created. Encode those quotes as JSON strings so decoding preserves the exact user request while the Markdown has no trailing whitespace; re-stage only plan/tracker. This is not a test failure or a skipped Git check.
