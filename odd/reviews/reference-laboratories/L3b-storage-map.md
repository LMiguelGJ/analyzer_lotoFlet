# L3b — bounded storage integration map

Read-only scout `mv3bw08t-2s-dkn2`; no source changes, verification commands or user-data operations. The preceding L3a unit still awaits both blind judgments; its independent functional check passed. This map does not authorize starting a parallel writer or assert storage behavior exists.

## Proposed split

1. Additive storage/quota unit: schema v16, separate reference-lab summary/session tables, immutable versioned stored metadata, repository CRUD and paging, bounded transactional admission and deletion. Test storage/migrations/old-run compatibility before a separate scoped Judgment Day and local commit.
2. Separate strict execution/list/detail/session/delete HTTP and body-limit integration unit, after storage is approved. No public execution/persistence currently exists.

## Derived minimal edit surfaces for the storage unit

- `webapp/backend/laboratorio/storage/database.py`: only schema head/ordered migration registration.
- `webapp/backend/laboratorio/storage/repository.py`: existing artifact accounting and thin new repository delegates; no rewrite.
- `webapp/backend/laboratorio/storage/migrations/0016_reference_labs.sql`: new additive summary/session tables and cascade/indexes only.
- `webapp/backend/laboratorio/storage/reference_lab_store.py`: new canonical, bounded, fail-closed reference storage operations.
- `webapp/backend/tests/test_reference_lab_store.py`: new deterministic storage/migration/quota/corruption tests.
- `webapp/backend/tests/test_run_store.py`: only two current-schema final-version expectations, currently literal 15 at lines 66/85, must become 16; other run tests preserved.

Do not edit prior migrations, `storage/run_store.py`, or `storage/quota.py` unless concrete evidence establishes a required shared seam unavailable above. Any expansion goes back to the parent first. No API/UI edits in this unit.

## Verified existing seams

- `storage/database.py:9,12–29,55–110`: schema head, ordered migrations and atomic guarded initialization; existing versioned databases upgrade in place.
- `storage/migrations/0015_runs.sql:1–25`: additive two-table pattern, no old-table rewrites. New sessions use foreign key cascade.
- `storage/repository.py:31–43,110–180,206 onward`: `BEGIN IMMEDIATE` transaction; `_run_artifact_bytes` and `_admission_logical_bytes` feed accounting/admission; Repository is a direct class, not a new mixin extension point. Existing CRUD has thin delegates near the end.
- `storage/run_store.py:1–17,261–320,477 onward`: controlled stored-JSON validation; compact sorted UTF-8 canonical serialization with `allow_nan=False`; transactional quota-checked create/delete.
- `storage/quota.py:20–67,70–105`: shared `QuotaStatus.require_capacity()` includes logical headroom and disk margin; positive int signed-SQLite-i64 quota validation.

## Required invariants and checks

- One accounting source: extend `_run_artifact_bytes` for new summaries/sessions. Both `Repository.set_quota_preference()`/`_admission_logical_bytes` and existing run-store `_quota()` must include new rows; no copied quota rules.
- Count all persisted UTF-8 JSON/text and fixed-width integer fields, including headers/immutable metadata/session rows. Project exactly the same bytes before insertion, inside the same `BEGIN IMMEDIATE` measurement/write transaction. Retain disk/sidecar margins; SQLite allocation is not logical bytes. Reject negative/overflowing persisted numbers rather than accepting SQLite coercion.
- Per execution cap: 50,000 session summaries and 32 MiB total persisted payload, including headers/metadata; actual known results about 20.7K maximum. Stable create/get/per-lab list/session paging/delete operations, paged limits bounded.
- Persist UUID, timestamp, explicit lab/history origin/SHA, ranking/source versions, immutable actual config and result summary. Read stored records from stored metadata/config, never active imports or current mutable catalog defaults. Session summaries only; no fabricated per-bet trace.
- Explicit stored JSON schema/version; malformed/unknown versions fail closed with a controlled storage error suitable for future HTTP 409.
- Observe RED/GREEN for new storage behavior. Fresh v16 plus v15→16 migration preserves old saved-run/history records; round trip, cascade, stable paging, exact byte accounting and quota preference visibility; atomic concurrent admission; over-limit attempts leave no rows; corruption/negative/overflow fail closed.
- `test_history_store.py:39` uses `database.SCHEMA_VERSION`, not literal 15. Its old “reaches_15” name is informational; no correctness-required edit identified. Scout found no other literal schema-head expectation in its targeted search, not an exhaustive full-suite proof.

Protected reference/legacy folders, existing 15 migrations/tables/data/cache settings, user ports/env/data and four unrelated staged changes remain untouched. HTTP/client/UI semantics and readiness remain outside this map.
