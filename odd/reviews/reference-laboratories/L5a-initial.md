# L5a migration and shared-quota — initial Judgment Day

## Frozen target

- Identity: `5d5e5ff106bf203df523b5f4aeff98b7b0acf87a446b201c47f63ba1bda508d6`
- Artifact root: `C:/Users/luism/AppData/Local/Temp/reference-labs-jd-l5a-i3bokjh9`
- Candidate/base: `candidate/`, `base/`
- Canonical manifest: `manifest.json`
- Complete unit delta: `unit_scoped.patch`
- Pinned base: `b6945522f134be58de7c8df15d7ae4c151be746a`
- Freeze kind: standalone Judgment Day; no native authority or delivery receipt.

Candidate:144files/48,783,608bytes. Base:142files/48,765,166bytes.
Seventeen shared context files differ from Git HEAD only by line endings; the manifest records them. Both snapshots have identical context. Newly authored migration17 and migration test have no base entry.

## Authored scope

1. `webapp/backend/laboratorio/storage/database.py`
2. `webapp/backend/laboratorio/storage/migrations/0017_laboratories.sql`
3. `webapp/backend/laboratorio/storage/repository.py`
4. `webapp/backend/laboratorio/storage/reference_lab_store.py`
5. `webapp/backend/laboratorio/storage/run_store.py`
6. `webapp/backend/tests/test_laboratory_migrations.py`
7. `webapp/backend/tests/test_reference_lab_store.py`
8. `webapp/backend/tests/test_run_store.py`
9. `webapp/backend/tests/test_history_store.py`

## Review workload

EOL-normalized490additions/12deletions; literal byte-faithful735additions/257deletions due history-test CRLF versus base LF.
New migration tests account for377addedlines. Ninety additions exceed the usual400-line budget; the coherent migration/behavior proof was retained rather than trimmed or hidden.
Physical authored-file totals:3446candidate/2968base lines.

## Technical evidence before review

Independent verifier `mv4ptiic-g-6nl2` completed:
- Focused194PASS/53.49s.
- Authorized remaining backend481collected/481PASS/827.46s; no failures/skips/xfails/timeout.
- Included matrix7, reference engine25, provenance plus14HTTP golden cases.
- Only excluded file:`tests/test_reference_labs_api.py`; not an all-backend-suite claim.
- Ruff check/format8files pass.
- Atomic quota node three additional PASS:0.39/0.31/0.37s.
- Actual validated-domain UUID ownership, FK/CHECK rejection, NULL ownership, isolated cascade survivor sets and exact partial-seed rollback independently proved.
- Nine source hashes/all16oldSQL/domain/protected assets/cached patch before-after match.
- Prior LSP:0confirmedclean/2auxiliaryfindings/5inconclusive timeouts; inherited excerpts unchanged. No clean-LSP claim.
- Author-owned RED1FAIL0.31s→sameGREEN1PASS0.40s recorded separately; not independently recreated by restoring old SQL.

Counts194and481overlap and must not be summed as unique tests.

## Blind judges

Same task, target and criteria were sent concurrently:
- A:`jd-judge-a`, task`mv4quvaj-k-fakt`.
- B:`jd-judge-b`, task`mv4quuum-j-8m0j`.

Both must return exact current native judge JSON: `findings` and `evidence`.
No peer outputs/memory, ambient source, source edits, delegation, ordinary4R, refuter or native review transaction permitted.
Both results are pending. No verdict or approved authority is asserted.

## Bounds

Criteria: correctness, edge cases, rollback, concurrency, quotas/performance, security, ownership and conventions.
Scope is migration/bootstrap/shared-quota foundation, not future manual CRUD/HTTP/UI/configured replay.
Only corroborated candidate-caused severe findings may enter bounded correction; pre-existing findings are follow-ups.
At most two severe-fix/scoped-rejudgment rounds. No round consumed so far.
Only the parent persists/merges results and decides the next authorized work unit. Review never supplies delivery permission.
