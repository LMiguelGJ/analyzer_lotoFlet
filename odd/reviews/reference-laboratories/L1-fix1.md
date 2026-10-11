# L1 — scoped re-judgment 1 of 2

## Explicit correction authorization

Human selected `authorize_empty_window_bugfix`: separate ordinary TDD correction for the corroborated MEDIUM empty-window crash. Writer `mv39ur63-2c-8wrj`, only engine/test files. No severe finding promoted, no `jd-fix-agent` used, no correction/re-judgment budget reset.

## Observed writer checks

- RED: 22 new cases fail with the actual integer-index `IndexError`; previous 3 tests pass.
- GREEN: 25 focused tests pass in 6.21s; first Transición 1 historical golden unchanged.
- All eleven ranking laboratories tested with an out-of-window archived row and with no archived rows. Empty result asserts sessions/totals/draws/gaps/timestamps/digest.
- Minimal fix: `dtype=np.intp` for the positions array. No scope expansion/refactor.
- Scoped whitespace check passed. Writer evidence is not independent verification.

## Immutable corrected candidate

- Original target: `2ab66b03f4c21b6a62292baae89937fd2af39ad190d1179dd5c6458767b2438e`.
- Corrected target: `6bd2c6a97aca6f66919fdfcdd7021791d1fd0aa688cacbdd25749daa5a60f816`.
- Artifact: `C:/Users/luism/AppData/Local/Temp/reference-labs-jd-l1-fix1-zszz49_3/`; `manifest.json`, sibling `snapshot`.
- 104 manifested files, 48,444,748 bytes; unchanged frozen original context plus corrected engine/test and four review evidence artifacts.
- Frozen ledger: `snapshot/review/L1-initial.md`, SHA `e97f5034f220d2bcfb2577539ac872a912d3536ad1f6471a83c3e7a8f7df32d9`.
- Immutable fix delta: `snapshot/review/fix-delta.patch`, 57 diff lines, SHA `2d65d67d4891e6f738fe4d8dc8e1d97499fa10ff2b4e038ef05958ebd7d4c791`.
- Copy checks bound all three candidate files to stable pre/post source hashes; unchanged context loaded from original manifest, not mutable ambient source.

## Running checks

- Judge A `mv3a05gg-2d-7i7r` completed: `JD-L1-INFO-001` outcome `verified`; exact payload `L1-fix1-judge-a.json`.
- Judge B `mv3a06dl-2e-170b` completed independently: same item outcome `verified`; exact payload `L1-fix1-judge-b.json`.
- Actors render compact `resolutions` rather than requested neutral findings/evidence. Preserve exact returned payloads; no additional inspection or runtime-test evidence is inferred from these minimal responses. Neither actor reported a fix-caused defect.
- Identical scoped read-only prompts, frozen ledger plus fix delta only; no whole new review. Same skill paths. May report fix-caused defects with proof. Both complete results required.
- Independent functional verifier `mv3a0kds-2f-jwv5` completed: 25 tests pass in 5.97s; all 104 hashes, manifest identity and exact file set pass before and after, no extra snapshot files. First historical golden unchanged. Parent spot check confirms the three live candidate files match this reviewed snapshot. Native assessment still unassessable due undeclared untracked paths; high-risk verification path, RDD off.
- Scoped re-judgments used: 1/2. Severe correction rounds used: 0/2; ordinary human-authorized fix units: 1. Do not turn a failed review into a fresh unlimited loop.

## Terminal scoped verdict

APPROVED for this corrected L1 candidate only. Both scoped judges verify `JD-L1-INFO-001`; independent final checks pass, no reported fix-caused defect. Counts: 0 severe confirmed, 0 suspects, 0 contradictions, 1 original MEDIUM informational item now verified. Scope and skill resolution are recorded in `L1-verdict.json`; actor wrapper discrepancies remain disclosed. Other thirteen full scenarios and API/UI verification remain subsequent tasks. No delivery authority is conferred by this judgment; local commits follow the already-authorized ODD work-unit policy.
