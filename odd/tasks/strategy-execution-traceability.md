# Strategy execution traceability recovery

## Authorization and scope

The user disputes the previous web restructuring closure: starting draws and the
step-by-step strategy execution are not discoverable. Recover the relevant product
requirements from `.pi/plans`, rather than treating UI unification as completion.
Physical storage migrations remain explicitly out of scope. No data deletion,
financial recomputation, fabricated rationale, or wholesale rollback is authorized.

## Evidence

Read-only scout `muxsvt2f-w-m2b5` found existing paginated replay, trajectory and
bet tables in `DetailPage.tsx`, with starting draws hidden in parameters. Historical
aggregate reports do not expose per-session details in the inspected public
contract. No verified Git evidence establishes that this functionality was deleted.

Plan anchors: `producto-local-80-20.md:29–35,50,93,166–167`,
`laboratorio-integral-odd.md:100,110,118`, `claridad-interfaz-80-20.md:69`, and
`claridad-visual-inspirada-en-pi.md:122` under `.pi/plans`.

## Tasks

- [x] R1 — Restore visible start provenance and readable bet-by-bet replay.
  Status: implementation and independent source review complete, not runtime
  acceptance. Reviewer `muxtjd6g-11-zbgp` found no concrete R1-caused blocker or
  weakened assertions. Tests remain unrun; polling-cache freshness and explicit
  zero-trajectory-call assertions remain coverage gaps, not proven defects.
  Writer `muxt2ak9-x-qdgk`: +215/-28 incremental lines, 10 unrun regression
  cases, source readback and passing scoped git diff --check. Parent recorded
  memory on its behalf. Native assessment unassessable, RDD off; independent
  reviewer `muxtjd6g-11-zbgp` finished. Two-file LSP probe inconclusive, not clean.
  Delegated writer; two non-trivial files triggered delegation.
  Surfaces: `webapp/frontend/src/pages/experiments/DetailPage.tsx` and its test.
  Show requested starting draw and native source index when available, an obvious
  entry to the existing bet ledger, current recorded choices/stakes/results/paid/
  balance and recorded stop reason. Preserve tabs, deep links, paging and native
  currencies. Do not equate first bet with execution start or bet ordinal with
  source draw index. Keep absent/loading/failed/pending states truthful.
- [x] R4 — Restore historical parity coverage and saved-run repetition.
  Status: implementation and independent source review complete. Reviewer
  `muxtzmih-13-gmdf` found no R4-caused blocker; native bounds, editable inputs,
  selector round trips, saved names/fields/hashes and exact coverage are preserved.
  Writer `muxtonkv-12-jpgd` restored exact coverage through models/adapters and
  scoped historical controls in six frontend files. Added accepted/invalid-range,
  universe-bound, saved-repeat and library-submission regressions; all unrun.
  Scoped git diff --check passed (CRLF warnings only). Parent read the adapter;
  native assessment unassessable, RDD off. One LSP batch: one confirmed clean,
  five inconclusive; not a clean typecheck. Reviewer `muxtzmih-13-gmdf` finished.
  Reviewer git diff --check also passed; untracked compatibility files were read
  directly, not checked by ordinary Git diff. Existing older page tests still
  expect the step-4 name field at mount or follow the old wizard sequence; this
  predates R4 and remains a test-staleness risk, not an observed test failure.
  Git auditor confirmed HEAD-to-worktree regression:
  `backtest-model.ts` changed the parity limit from >50 to !==50; hydration and
  `historical-strategy-compatibility.ts` reject/coerce valid 1–49 coverages.
  Backend `api/backtests.py` still accepts and executes coverage <=50, unchanged
  since `06f2764`. Restore historical native 1–50 coverage, bounded by game size,
  in validation, adapters, controls and repeat; preserve names/snapshots/hashes.
  No classic/profile engine behavior change or data rewrite. Single delegated
  writer, narrow historical frontend surfaces and matching regressions only.
- [x] R2 — Recover historical per-session traceability where stored data allows.
  Status: implementation, both source reviews and targeted correction readback
  complete. Verifier `muxvwj9a-18-k1oh` confirmed both findings resolved:
  persistent user-action focus without async focus stealing, and exactly three
  real-validator test calls with original assertions intact. Parent readback
  agrees. Tests/runtime remain unrun; no functional acceptance is asserted.
  Backend reviewer `muxvgno1-15-nl5f` found no production blocker, but three new
  test_storage.py calls omit mandatory validate_experiment and hit an existing
  guard before the intended trace checks. Corrector `muxvn7o3-17-h31i` supplied
  the API's real _validate_public_experiment callback; production admission and
  assertions remain unchanged. Its three-file correction is delivered.
  Frontend reviewer `muxvgo8p-16-fp44` confirmed pagination/retry unmounts the
  focused control during loading without preserving/restoring keyboard focus.
  Correct only `BacktestSessions.tsx` and its test with stable focus behavior and
  assertions. Monetary-format concern withdrawn: native trace values are
  nonnegative integers with unsafe integers represented as strings. No other
  frontend source blocker found; no runtime acceptance is claimed.
  Writer `muxua3na-14-iqfm` completed both units in 14 authorized files. Trace v1
  stores whole-session prefixes capped at 2 MiB / 10,000 bets / 1,000 sessions;
  readers page at 20 by default, maximum 100. Responses expose metadata only.
  Added legacy/strict-validation/digest/caps/paging/UI regressions and updated
  stale wizard-test navigation. All execution checks remain unrun. Writer scoped
  diff --check passed; reported +1,369/-56 HEAD lines include pre-existing edits.
  Parent read the session browser. Assessment unassessable (untracked), RDD off;
  14-file LSP probe inconclusive, no clean files confirmed. Writer reported
  automatic edit-hook diagnostics/autofix; no separate post-delivery changes
  have been established. Reviewers inspect current source.
  User authorized finishing the sole remaining scope with
  “ya termiana con todo esto”. One writer completed two sequential units:
  versioned bounded trace storage/API with regressions, then paginated session/
  bet UI with regressions and stale historical-wizard test updates.
  Legacy aggregate-only reports remain byte-unchanged and show “Detalle no
  almacenado”. New runs save native session outcomes, bets and provenance without
  recomputing financial results. Paginate reads, cap stored bytes/rows explicitly,
  disclose truncation and never treat missing detail as an empty execution.
  Preserve exact native aggregates, request hashes, labels, identities and units;
  validate legacy and new snapshots strictly. No schema migration, engine change,
  automatic historic reconstruction, database operation or tests execution.
- [x] R3 — Independent source review and final evidence reconciliation.
  Status: bounded Git/plan audit and both recovery source reviews complete.
  Auditor `muxtgk2y-10-6ix3` confirmed the historical parity regression and no
  additional important committed capability removal within the inspected scope.
  Classic advanced controls, limits/start draws, profile policies, redirects,
  editable rules and advanced imports remain, sometimes folded or relocated.
  Advanced profile-definition editing was absent in original `f5149aa`; historical
  blend/random were absent in original `06f2764`/`0e7390e`, not removed later.
  Plans explicitly defer grids/Monte Carlo/stability and extra presets; old plans
  are not cumulative authorization. R4 correction was independently reviewed with
  no concrete blocker. Source/Git evidence is not runtime acceptance.

## Verification and delivery

Earlier user direction defers automated tests, typechecks, builds and browser/live
checks. Add/preserve meaningful regressions but label them unrun; no invented RED,
GREEN, runtime acceptance, or user-QA obligation. Source readback is not functional
verification. Native review is off. Assess delegated diffs and obtain an independent
source review as needed. Preserve all pre-existing changes. No commit or push is
claimed; delivery stays separate from implementation evidence.

## Current evidence

R1/R4 source implementations and reviews are closed with unrun checks retained.
All four recovery tasks are complete as implementation/audit/source-review
records. R2's two findings have independent targeted confirmation in
`muxvwj9a-18-k1oh`. No active task, writer or reviewer remains. Older wizard test
navigation was updated with assertions preserved. No concrete source finding
remains open in the reviewed scope.

Execution checks remain deferred: tests, typecheck, build, browser and live API/DB
were not run. Last correction LSP probe confirmed no files clean (three
inconclusive). Native assessment remained unassessable due to untracked scope;
RDD is off. No runtime, clean-build, commit or push claim follows from closure.
Legacy reports retain aggregate data and explicitly lack stored trace; new trace
capture is capped at 2 MiB, 10,000 bets and 1,000 sessions, with visible truncation.
The bounded Git history audit is complete.
No runtime acceptance, clean build, commit or push is claimed.

Parent Git evidence: root PRODUCT.md and DESIGN.md blobs match their current
copies under docs/ using Git path filters. Initial historical backend commit
`06f2764` already persisted aggregates only, not session ledgers. These findings
do not establish absence of all regressions. The broader bounded Git audit has
finished: historical parity coverage was the sole confirmed capability reduction
in its inspected boundaries; R4 correction and review are complete. Parent verified
`.pi/plans/producto-local-80-20.md:29–35` exists in the authoritative workspace:
its approved scope is one selected-start session per strategy and explicitly
excludes consecutive sessions. Therefore the plan corpus must not be treated as
one cumulative authorization for every historical feature. The scout's inability
to locate plans does not establish missing/deleted files.

The earlier complete feature ledger remains historical; this document reopens
concrete product gaps rather than restoring withdrawn physical migrations.
