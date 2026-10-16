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

Amendment from explicit human choice L11, verbatim: «La revisión visual la hago yo; publicá lo probado». Retire only the automatic real-browser acceptance activity and transfer wallet visual cases B1–B7 to the user as OPEN / NOT VERIFIED. Preserve independent backend and frontend technical verification, all failed/unavailable browser evidence, and ordinary delivery checks. This is not visual approval and does not waive integrity, tests, or source preservation.

### S7 — Preserve data and delivery boundaries
No changes to engine, history, rankings, `.env`, frozen inputs, `repo_ref/`, `lagacy_loto/`, migrations, saved data/formats/hashes, reference/legacy consumers, quota policy, global cache/formatters/tokens or dependencies. Never access the user's normal database for this feature. Historic OPEN/manual/integrity acceptance stays OPEN. Parent alone owns staging/commits/merge/push; workers have no delivery permission. Only delete the newly created feature branch after verified master retention and publication; preserve detached review views and unrelated work.

## Tasks
- T0 — S1,S7; route: inline preparation; status: done; tracking document/mirror/projection and feature branch before source writes; commit: 7ac1432 (job2 exit0); initial whitespace failure job1 preserved.
- T1 — S2,S3,S6,S7; route: backend worker, parallel with T2; status: done (implementation/self-check scope only; independent acceptance remains T4); commit: 997429f (job5 exit0); RED: missing-wallet GET; GREEN: 82 backend cases/21.43s with authorized plugin isolation, parent API/query9PASS/4.59s.
- T2 — S4,S5,S6,S7; route: frontend worker, parallel with T1; status: done (implementation/self-check scope only; independent acceptance remains T4); commit: 3aa666a (job4 exit0); RED: absent Tu dinero heading; GREEN: 73 cases + tsc/build0; parent73PASS/19.08s.
- T3 — S1,S4,S5,S6,S7; route: inline docs/integration/browser; status: dropped from automatic visual execution, transferred to user by L11 (NOT approved); docs commits: 3aa666a/997429f; wallet visual B1–B7 USER/OPEN; failed browser evidence retained.
- T4 — S1–S7; route: independent read-only output judgment after authorized isolated host execution; status: done (bounded technical scope only); commit: 927d5786d323381ba4d0a642048a2a8844cadf21; prior UNAVAILABLE and user-owned visual gap preserved.
- T5 — S1,S7; route: inline verified master integration/publication/new-branch cleanup; status: in_progress; commit: delivery preparation pending; master/remote preflight clean at9275c03, feature retention verified by ancestry.

### User-owned wallet review registry — OPEN / NOT VERIFIED

| Scope | Owner / status | Evidence boundary |
| --- | --- | --- |
| Wallet visual cases B1–B7, real-browser layout, keyboard/touch, viewport/text enlargement | User / OPEN | Technical tests and static review are not visual approval; no valid browser run or screenshots. |

The historical user-owned acceptance registry in `odd/tasks/mejoras-visuales-y-logicas-quiniela.md` remains unchanged.

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

### L4 — Preparation complete; parallel production authorized
Initialization commit `7ac1432` completed with exit0; exact task mirror9190 read back before source writes. T1/T2 begin together with disjoint surfaces, no Git/delivery rights. Parent owns docs and evidence. No changed requirements.

### L5 — Parent documentation preparation
T3 documentation is prepared on its disjoint three-file surface while T1/T2 producers run. The visible production-wave entry includes this preparation; its later T3 entry tracks final integration/browser acceptance. No behavior test or manual acceptance is claimed by writing documentation. Parent's scoped documentation check exited0: three files, fixed policy, touched relative QA link and seven wallet QA cases; `git diff --check` passed for those paths. Source/build/browser/independent acceptance remains pending producer reports.

### L6 — Producer reports and single backend correction
- Backend worker mvb8mr9t-3-p3re returned partial: genuine missing-wallet public API RED, implemented five files, 77 backend cases PASS in18.21s with plugin autoload disabled. Original required pytest invocation failed before collection because unrelated SeleniumBase plugin adds conflicting --browser option; this is not a product RED or a passing original command. Authorize process-local `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for remaining bounded synthetic pytest runs, no dependency/config changes or blind rerun of that failing invocation.
- One correction mvb90h1r-5-f2ib requests the specifically missing POST/cold/warm parity, owner/corruption errors, GET no-write/quota/counter, >50-page completeness and cold-only derivation proofs before final backend self-review. No scope expansion.
- Frontend worker mvb8mrqe-4-fuf2 returned complete: 73 cases/4files PASS, tsc/build0; initial wrong-cwd Vitest invocation failed before collection and was corrected, not counted as UI RED. Genuine RED was absent Tu dinero heading. Parent seam spot-check job3 runs that same reported four-file suite once.
- Native assess after writer returns is unassessable due undeclared untracked files, rddLine off; conservatively high with separate independent verification required. No native review or authority repair started. Independent verification waits for final correction/self-review; no PASS inferred from implementation.

### L7 — Own checks complete; independent runtime proof unavailable
- Backend final correction reports82PASS/21.43s with empty stderr, plus9API/queryPASS/10.50s and1readonlycasePASS/7.24s. Parent re-read autoformatted APItest and ran the same API/query pair:9PASS/4.59s, exit0. Backend code/tests/README committed in997429f,350+/38−. Frontend code/tests/design/QA committed in3aa666a,138+/15−; parentseamjob3 confirmed73PASS. Producer tasks close only their implementation/self-check scope, not independent acceptance.
- Active frontend LSP probe returned0diagnostics but all6files inconclusive (4waitbudgettimeouts,2push-only); NOT a clean-type result. Actual tsc/build reported0 by writer. No automatic LSP retry.
- Frontend verifier mvb95geo-6-37di: INCOMPLETE/no independent approval; staticS4/S5favorable, runtime/tests/build/browserNOTexecuted. No background tool exposed; snapshot script failed before creation with SyntaxError from backslash string. No snapshot/manifest/junction/screenshots. Do not retry or replace verifier automatically.
- Backend verifier mvb98o8w-7-7x2k: UNAVAILABLEruntime; prepared58-file byte-copy snapshot/manifest under.tmp/aportes-y-patrimonio/verify-backend-1e7b693842/, manifestSHAac24022a36b8f1461278649837222478d13aba7c52103f7b2452acca6f632d7c; source-recheck all58unchanged. Valid relay.sh prepared, butpytest/stdout/stderr/exit files DO NOT exist and no runtimePASS. It reportsstaticcoverage gaps(cumulativeoverflow,validatedincompleteAPI,snapshotcapital/enrichedinterleavedread)as gaps,not reproduced defects. No new requirement or source correction authorized by those advisories alone.
- Required independent runtime/browser proof remains missing. Master is still9275c03, not integrated/pushed; feature is997429f plus this tracker update. Preserve all copies/data/branches. Ask ONE concrete Needs-your-decision question: authorize one bounded host execution/correct frontend preparation and independent result judgment, or stop retaining commits without delivery. No further verification or missing-proof acceptance is inferred from YOLO.

### L8 — Fresh explicit bounded host-relay authorization
Human selected «Sí, completar esa verificación aislada» with answer token `authorize_one_bounded_host_relay_and_frontend_snapshot_correction`. Authorize one first execution of the prepared backend relay, one corrected frontend snapshot preparation and its pending runtime/browser checks, then independent judgment of the actual frozen outputs. This is not approval of missing evidence, not an automatic retry, and not a new product requirement. If proof passes, finish the already-authorized master delivery and cleanup. Keep all old UNAVAILABLE reports and execution-vs-judgment provenance.

### L9 — Authorized host execution and bounded fixture/transport corrections
- Parent frontend snapshot prepared85files excluding secrets/dependencies/output, with junction to existing node_modules. Hostjob7exit0:73PASS/43.46s,tsc0/build0,85source/snapshotfilesunchanged; logs under.tmp/aportes-y-patrimonio/verify-frontend-host-gd15frti/logs.
- Original independent backend snapshot passed binding check:57immutablefilesmatched,trackerprogressalonechangedwithSpecsidentical. First actualhostrelayjob6exit1:26PASS/56setupErrors/17.75s,stderr_empty. Snapshot omitted20existingSQLmigrationfixtures; FileNotFoundError,notaproductdefect. Onefixture-onlycorrection copiedexactSQLbytesintoscratch (originalmanifest/logspreserved),thenjob8recheckedONLYfoursetup-failingfiles:56PASS/14.08s,exit0,emptystderr;20productionSQLhashesunchanged. Combined82distinctcasespassedacrosstwopasses,notonecleanoriginalrun.
- Backend verifier outputjudgmentmvb9ughl-8-ec5h independently returnedPASSforS2/S3/backendS6/S7andT1/backendT4,explicitlyseparatingparentexecutionfromindependentjudgment; no remainingdeterministicblocker. Staticdirect-testlimitationsremainadvisories,notnewrequirementsorfullQAapproval.
- BrowserCLIavailable1.59alpha; ownstaticfrontendserver5184(no backend) andnamedin-memoryquiniela-wallet-verify. Initialrun-code10236-characterinlineargumentexceededWindowscmd8191transportlimit andreturnedSessionclosedbeforeQAexecution(job11exit1); preservefailedoutput. Diagnostic snapshotauto-openedownedabout:blankbrowser. OneboundedtransportcorrectionservesreadableQAfunctionasownedstaticassetandusesa268-characterloader(job12),notanotherbrowserprovider/profileorproductionchange. BrowserPASSstillpending; no automatictimeoutretry.
- All source requirements remain unchanged. Normal data, realAPIwrites, existingviews/branchesandengineuntouched. Frontendjudgment/deliverywaitactualbrowseroutput.

### L10 — Browser correction exhausted; preserve missing proof
Job12short-loadercorrectionalsoexited1withSessionclosed,noQAresultorscreenshots. ThereforeWindowsargumentlengthwasanunconfirmedhypothesis,notestablishedrootcause;shorteningpayloadDIDNOTrestorethesession. Do not rerun/reopen/switchproviders automatically. T3browserproofremainsUNAVAILABLE;frontendverifierisaskedonlytojudgealready-successful73tests/types/build/sourcebinding,withvisualscopeexplicitlyunavailable. BackendindependentboundedPASSstands. Needoneconcreteuserdecisionforadifferentfreshisolatedbrowserroute,manualUIhandoffwithknownmissingproof,orstopbeforemasterdelivery.

### L11 — Explicit visual QA transfer and bounded technical judgments
- Human selected «La revisión visual la hago yo; publicá lo probado», token `transfer_wallet_visual_qa_to_user_and_deliver_verified_code`. Transfer only real-browser visual QA to the user, OPEN/NOT VERIFIED; integrate/publicize what was technically tested and remove only the already-integrated feature branch after master publication. This is fresh specific cleanup/delivery authorization, not inferred from YOLO.
- Frontend independent output judgment mvba2yxh-9-wyui returned bounded T2 PASS: S4/S5 static/unit, frontend S6 tests73/43.46s +tsc0/build0(75modules/8.60s),S7binding85unchanged. Explicitly NOT browser or full-feature approval. Backend output judgment mvb9ughl-8-ec5h PASS remains scoped to S2/S3/backend S6/S7,26initial+56corrected distinct cases. Parent execution and independent judgment are separate facts.
- Wallet visual registry and guide now explicitly retain B1–B7 as user-owned OPEN. No new browser/provider attempt. Own staticserverjob9 stopped; ownCLIclosejob13exit0 reports browser not open. No other servers/profiles or normal data touched.
- README/design/QA docs are already committed alongside behavior; this evidence/handoff commit closes bounded T4 technical acceptance only. Master refresh is job14; final integration/publication/branch cleanup still waits for ordinary Git checks.

### L12 — Bounded technical acceptance committed; delivery starts
Evidence/handoffcommit927d5786d323381ba4d0a642048a2a8844cadf21(job15exit0)containsindependentjudgmentsandexplicitmanualvisualregistry. T4closesonlyitsboundedtechnicalscope. Fetchjob14exit0;localmasterandorigin/masterboth9275c0399db7ede98a98507b8ac552534329c942,ahead/behind0/0;masterisancestoroffeature,workingtreecleanbeforethisreceiptupdate. Preparethisdeliveryunitonfeature,thenFFmasterandordinarypush;deleteonlycreatedlocalfeatureafterpublishedidentity/ancestrychecks. No PR/force/otherbranch/viewcleanup.
