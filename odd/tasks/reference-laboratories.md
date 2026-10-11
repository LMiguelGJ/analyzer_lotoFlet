# Reference laboratories — ODD implementation

## Authorized outcome

Implement the fourteen laboratories in `repo_ref/simuladores` faithfully inside `webapp`. Human selected `separate_reference_laboratories`: a catalog and separate named laboratory screens, each exposing its actual rules, parameters and results. Existing fixed-stake mixture/parity alone is not acceptance. Reference folders are read-only.

## Boundaries

- Preserve `repo_ref/`, `lagacy_loto/`, migrations, database records, `.env`, real user data and user-owned ports/processes (5173/8765). Never stop the previously observed 8765 listener automatically.
- Preserve unrelated staged deletions `docs/DESIGN.md`, `docs/PRODUCT.md`, `especificaciones-laboratorio-web.md` and staged addition `odd/qa/reestructura-profile-repeat.cjs`.
- Local scoped work-unit commits only; no push, PR, merge or deployment. One source writer at a time.
- Keep prior rebuilt-run functionality and saved data compatible unless a concrete conflict is reported. Do not perform opportunistic cleanup.
- Human explicitly requires Impeccable for every interface task: `C:/Users/luism/.pi/agent/skills/impeccable/SKILL.md`. Pass this exact path to UI writers, judges and UI fix actors. Load the owning playbook (`reference/new-work.md` for new surfaces; `reference/operate.md` for task UI), inspect incumbent design/tokens and representative components, and read `reference/craft-floor.md` immediately before UI edits. Follow context setup once per session, never repeatedly. Verify actual desktop/mobile layout, keyboard/focus/labels, loading/empty/error states and iterate with real screenshots; unit tests alone do not establish visual acceptance.
- Existing notebook identity remains; extend Operate-mode UI rather than redesigning it. English code/comments, existing Spanish interface/documentation convention. Missing approved comparisons remain disclosed, never fabricated.
- Python `py -3.14`; no `.venv` assumption, no `-I`. Verification uses isolated temporary data/owned process/port and actual browser, never the normal user profile.

## Reference contract from scout mv38z4i6-25-n2qi

Shared capital 2000, goal 2800, five positions with payouts 80/8/4/2/1, no duration cap. Ranked evaluation window has 65235 eligible draws among 105426 history draws, 2025-09-02 05:10 through 2026-09-25 18:20. Gaps receive no bet; sessions continue across gaps/folds. Incomplete tail contributes to totals, not completed-session rates/means. Exact formulas, eligibility, rounding and stake affordability must be read from the actual reference engine before implementation; README summaries do not replace code evidence.

| Lab | Archived selection | Coverage | Stake |
| --- | --- | --- | --- |
| transicion_1_audaz | transition | 1 | bold |
| frios_1_audaz | cold | 1 | bold |
| selector_1_audaz | interpretable selector | 1 | bold |
| mezclas_1_audaz | mix | 1 | bold |
| ensemble_5_audaz | ensemble | 5 | bold |
| ensemble_10_audaz | ensemble | 10 | bold |
| ensemble_20_audaz | ensemble | 20 | bold |
| frios_25_escalera | cold | 25 | ladder |
| mezclas_50_audaz | mix | 50 | bold |
| transicion_50_audaz | transition | 50 | bold |
| paridad_50_audaz | causal parity | 50 | bold |
| frios_50_escalera | cold | 50 | ladder |
| paridad_50_escalera | causal parity | 50 | ladder |
| paridad_50_plana | causal parity | 50 | flat |

Do not reconstruct archived mix/ensemble weights by guessing; consume archived selections and record frozen-input provenance. Parity eligibility and causal consensus must match the reference, not the existing all-draw run interpretation.

## Tasks and evidence

- [x] L1 — Immutable fourteen-lab contracts and isolated replay engine; first `transicion_1_audaz` exact golden validated. Commit **`375f1e1`** (3 backend files plus exact review evidence). Initial independent 3 tests pass in 8.33s; actual empty-window RED 22 failures/3 passes → writer GREEN 25 in 6.21s. Final independent **25 pass in 5.97s**, all 104 frozen hashes and exact file set intact before/after. Both scoped judges verify the original MEDIUM item; severe confirmed/suspect/contradiction counts 0; 1 informational item resolved. Re-judgment 1/2, no severe fix actor. **APPROVED** only for corrected target `6bd2c6a97aca6f66919fdfcdd7021791d1fd0aa688cacbdd25749daa5a60f816`; evidence `odd/reviews/reference-laboratories/L1-verdict.json`. Minimal returned actor wrappers preserved; no extra inspection proof invented. Parent confirms three live source hashes match reviewed snapshot. Not all-fourteen, API/UI or full-suite approval.
- [ ] L2 — **In progress**: full independent fourteen-scenario matrix, provenance and per-session digests, explicit stake/reset/gap/tail boundary cases. Freeze source-backed oracle expectations, never match an incorrect implementation by changing the oracle. Commit pending.
- [ ] L3 — Wire strict lab catalog/execution/results persistence API, compatible with existing storage/data and frozen history. Reject incompatible imported history transparently rather than silently substituting the reference. Commit pending.
- [ ] L4 — Implement catalog and first dedicated lab page/results with notebook identity, actual rules visible, accessible controls and execution/error/loading states. Commit pending.
- [ ] L5 — Implement remaining thirteen dedicated laboratory entries/screens with explicit scenario rules, no unsupported placeholders. Verify every lab independently. Commit pending.
- [ ] L6 — Independent regression tests and real-browser acceptance for all fourteen entries, mobile/desktop, arithmetic and result details; operational documentation and scoped closure. Commit pending.

## Judgment Day — explicitly activated by the human

Apply `C:/Users/luism/.agents/skills/judgment-day/SKILL.md` to each implemented laboratory and its affected shared engine/API/UI behavior, against the corresponding read-only `repo_ref/simuladores` contract. The current in-flight writer is not yet an immutable review candidate. After each bounded implementation is complete, freeze one complete target and exact matching reference evidence, then launch `jd-judge-a` and `jd-judge-b` blind and read-only in parallel with identical scope, criteria and skill paths. Both roles and `jd-fix-agent` are available. Wait for both results; parent merges and persists the findings ledger. Do not use ordinary 4R or `review-refuter` for this adversarial target.

Fix only severe findings confirmed by both judges through `jd-fix-agent`; ask the human before round one. Single-judge findings remain suspects; warnings/suggestions are informational. Contradictions require a human decision. Maximum two fix rounds and two scoped re-judgments, limited to frozen ledger plus immutable fix delta. Remaining issues after the budget escalate; never reset the budget. Terminal verdict is only APPROVED or ESCALATED, not a delivery authorization or substitute for functional checks. Do not issue a verdict before complete judged evidence exists.

## Checks

Writer self-verification runs the exact authorized commands and reports observed RED/GREEN/remaining failures. Parent assesses the resulting candidate and routes independent verification accordingly. Frontend tests/types/build and real browser checks are required when their surfaces change. Existing previous 220 backend /116 frontend /13 browser checks are historical evidence, not proof of this mission.

## Current status

L1 completed and locally committed as `375f1e1`; final scoped Judgment Day APPROVED and independent 25 tests pass (5.97s). L2 full fourteen-laboratory matrix is in progress; API/UI still unimplemented for this mission. No full-suite or all-fourteen approval yet. Human UI choice remains fourteen separate lab pages with a catalog; mandatory Impeccable for all UI and Judgment Day per laboratory.

First frozen reference: `transicion_1_audaz`, 65,235 eligible draws, 6,543 gaps, 963 completed (681 goals, 282 ruins), 1 incomplete; wagered 1,182,452, paid 1,190,701, net 8,249. Per-session SHA `e7e9d68a1ac0078b4e5a42366f6e989f8b4871f95cb6673717c17839ba69fbc4`. Exact source provenance and corrected empty-window evidence retained in `odd/reviews/reference-laboratories/`. Runner path constants were not used because they add an incorrect reference prefix; actual bundled history/rankings were hash-verified. Reference source remains untouched.

No cause for the reported live runtime failure has been proven. Real user app/processes/data remain untouched. No approved visual benchmark or complete Impeccable comparison will be fabricated; scoped local commits confer no publishing decision.
