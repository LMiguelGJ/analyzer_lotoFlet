# Q1 own checks — provisional evidence

Baseline: `1c5e44142319e4608feb4c61ba51f27bc09c3312`.
Scope: `.tmp/quiniela-configurable/q1-scope/manifest.json` (21 source/test/doc paths).
Independent verifier: `mv7403j2-1-di2l`, running; Q1 is **not closed**.

## Observed checks

| Unit | RED | GREEN / latest own observation |
|---|---|---|
| Profile | missing-module collection error; later factory mapping1 FAIL/9 PASS |10 PASS; Ruff/check/format PASS |
| Trace values | missing-module collection error |54 PASS; three typed immutability-test errors corrected;54 PASS again |
| Profile HTTP API |53 FAIL/4 existing local guards PASS,6.56s,exit1 |57 PASS,7.53s,exit0;3 corruption probes subsequently PASS inside combined seam |
| Definitions/snapshots | missing-module collection error,exit2 |18 PASS,0.64s,exit0 |
| Existing laboratory migration expectations |2 FAIL/6 PASS because target18 !=17 |target expectations use SCHEMA_VERSION; other assertions retained; PASS inside seam |
| Combined11-file compatibility seam |not a synthetic RED |266 PASS/1 FAIL,38.74s,exit1; failure: old test_run_store schema17 expectation |
| Remaining current-version expectations |3 FAIL,1.73s,exit1 |3 PASS,0.86s,exit0; SCHEMA_VERSION only, stored rows/ownership assertions retained |
| Python lint/format |test formatting corrected during own work |16 changed Python files checked/formatted; all observed final required Ruff calls exit0 |

No all-green claim for the complete combined command: its failure stays recorded.
The bounded targeted correction passed; independent verification now tests the
final state. No whole backend suite, fourteen replays, UI/browser checks or final
feature acceptance are claimed at Q1.

## Evidence locations

- `.tmp/quiniela-configurable/q1-profile/`: worker RED/GREEN scratch; complete commands in handoff.
- `.tmp/quiniela-configurable/q1-run-values/`: original54 cases and one typed-assertion correction batch.
- `.tmp/quiniela-configurable/q1-profile-api/red-01/{stdout,stderr}.log`.
- `.tmp/quiniela-configurable/q1-profile-api/green-01/{stdout,stderr}.log`.
- `.tmp/quiniela-configurable/q1-snapshots/{red-01,green-01}/{stdout,stderr}.log`.
- `.tmp/quiniela-configurable/q1-compat/migration-red-01/{stdout,stderr}.log`.
- `.tmp/quiniela-configurable/q1-compat/{version-red-01,version-green-01}/{stdout,stderr}.log`.
- Combined seam job-1 output is the provider-owned job log; last pushed outcome above.

## Diagnostics and risk

Active probes did **not** confirm a clean workspace. Some files are silent/inconclusive;
new snapshot test retains a missing-import finding although its module imported and18
runtime cases passed. Existing host numeric-parse warning is guarded by the anchored
ASCII regex. Unchanged active_history/adapter retain object-History typing findings;
git diff against baseline is empty for those files. They were not opportunistically
edited. Three trace-test typing errors were specifically corrected, not ignored.

ASSESS was unassessable (undeclared untracked scope), so verification follows the
high-risk plan. No retry of native assessment, START, native receipt or authority
closure while RDD is off. Independent verification is not replaced by own tests.
Risk: items1/2/3/4 — additive schema, request guards, shared quota accounting and
serialized admission. All mutation checks use isolated test databases, never normal
data. Foreign index remains87,352 bytes/SHA-256
`26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`.

## Planned local work-unit slices (after proof)

1. Profiles: module + focused tests + profile guide.
2. Trace values: module + focused tests + value guide.
3. Structural definition/snapshot contracts: module + tests + guide.
4. Profile persistence/API and v1 compatibility: migration/store/API/shared wiring,
   HTTP and target-version tests, API guide, approved plan/tracking/evidence.

Each slice is a usable, separately revertible behavior/contract. Some exceed400
changed lines when tests/docs count; do not compress/delete evidence to hide churn.
No push/PR/merge/deploy or packaging/startup change is authorized by these slices.
