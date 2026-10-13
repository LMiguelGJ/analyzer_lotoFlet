# L6b2c — Atomic owned laboratory run insertion

## Target and behavior

Base `00850a37e1a4349e941ce2f41da6da0f2f560d65`, feature branch `feat/reference-laboratories`.
Production surfaces: `owned_laboratory_run_store.py` and the thin `Repository.create_owned_laboratory_run` wrapper.
Frozen new test: `test_owned_laboratory_run_insert.py`, SHA256 `640de0418c07ff5a6e4a588ad1104cb4f22e73759b47a682e822a5726f66dac2`, 430 lines /14 functions /28 parametrized cases.
Owned store SHA256 `6e484fa034d6733127bce130bbba5d86fa005691ec95b4dde6a3e99569282f69`; Repository `62aa32a403742a67f6490d3fb9a0c9fad8d538fe8c703236be6d07b677424941`.

Create requires canonical UUIDs and an exact owned snapshot, round-trips the strict codec, and reuses shared result validation/canonical UTF-8 serialization.
Within one BEGIN IMMEDIATE transaction, reload/decode the current definition and compare its canonical form with the replay snapshot BEFORE quota admission and run/session writes.
Absent, changed or corrupt definitions fail closed. Explicit owner equals lab ID; never NULL fallback, inference, reseeding, catalog conversion or schema migration.
Input errors use OwnedLaboratoryRunStoreError; quota denial and SQLite duplicate/session-trigger failures retain their established exception types.
Payload charging matches the existing logical run/session metric, not physical SQLite bytes; the owner column is not independently added to that metric.

## Observed lifecycle and verification

Tests-only author `mv5sfndb-d-89fn` wrote tests and tracking before production changes.
First RED verifier `mv5sq6lj-e-hciz` ran guards only; pytest never ran, and its formatter-mutation claim was retracted.
Recovery `mv5stzhi-f-ewo6` had an accepted dispatch but lost its task registry entry; diagnosis/process filtering could not establish termination or an execution result.
The user explicitly authorized ONE replacement acknowledging possible prior duplicate execution, isolated inside project .tmp.
Parent actual RED: exit2, zero collected/one import error in0.74s, missing create_run at test line14; before/after six pins,68 frontend hash/mtime entries and foreign staged bytes passed.

Latest harness routes a single atomic unit inline, not by file count. Parent implemented only the owned store and Repository wrapper, leaving tests unchanged.
First GREEN attempt:28 setup errors because the .tmp parent did not exist; this is runner failure, not behavioral GREEN.
Created the ignored in-project parent; own28 passed2.96s. Ruff import sorting and signature-format failures were corrected mechanically without changing tests.
Final own checks:241 compatibility tests passed19.67s; three-file Ruff lint/format and whitespace passed.
Independent verifier `mv5wj89y-2-6z0l`:28 focused passed2.54s and669 full-backend passed1106.76s; Ruff lint/format3 and whitespace passed.
Counts overlap;28/241 are not additional to669. Exact raw verifier report is retained in `L6b2c-independent-verification.md`.
Before/after independent guards: six pins,149 backend/frontend hash/mtime entries, HEAD/base and feature branch, and four foreign staged paths with87,352-byte cached diff all passed.

## Limits, risk and delivery

Risk: item 4 (concurrency). Transaction structure, stale-definition rejection and deterministic SQLite session-trigger rollback were verified; no adversarial runtime race scheduling probe was run.
Active LSP on three changed paths timed out:0 confirmed clean/3 inconclusive. No clean-LSP or CodeGraph diagnostics claim.
Fresh CLI review mode is clone-local OFF/global ON. Native ASSESS was unassessable (`package-local-binary-missing`), so conservative own checks plus independent verification were used.
No native approval/receipt or per-candidate dual review was created; the separate full-feature Judgment Day remains L9.
Current source churn is549 additions/2 deletions=551, before evidence/tracking; disclose whole delivery churn at commit, never trim proof or tests to fit400.
Rollback boundary: this insert helper, its wrapper and new tests/proof; preserve the previously committed owned reader, legacy owner-NULL predicates, strict codecs, engine and schema17.
Contextual user authorization permits scoped local work-unit commits, not push/PR/merge. Preserve foreign staged content exactly.
Owned run listing, producer/API and L7-L10 remain pending; storage PASS does not close all ofL6 or establish browser/lifecycle acceptance.
