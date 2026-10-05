# B-STO contract rewrite verification

## Coverage

**B-STO: 103/103 contract IDs verified** by the rewritten/expanded persistence tests. The ID references are inline above the corresponding tests.

| File | IDs verified | Result |
|---|---:|---|
| `webapp/backend/tests/test_storage.py` | B-STO-001..040 (40/40) | v10 migration, strategy persistence, lifecycle, snapshots, and schema boundaries |
| `webapp/backend/tests/test_profile_storage.py` | B-STO-041..057 (17/17) | typed profile storage, replay, cycling, Audaz, and strict cross-version reads |
| `webapp/backend/tests/test_profile_archive.py` | B-STO-058..064 (7/7) | verified archive binding and historical selection |
| `webapp/backend/tests/test_datasets.py` | B-STO-065..072 (8/8) | promotion, canonical identity, immutability, paging, preflight, quota, concurrency |
| `webapp/backend/tests/test_history_import.py` | B-STO-073..075 (3/3) | nested-history parsing and validation |
| `webapp/backend/tests/test_import_records.py` | B-STO-076..089 (14/14) | JSON/CSV parsing, validation, limits, hashes, and safe previews |
| `webapp/backend/tests/test_quota.py` | B-STO-090..103 (14/14) | quota precedence, accounting, concurrency, and atomic writes |

No contract IDs are reported uncovered.

## Replaced/deleted tests and assumptions

- No old behavior test was deleted without replacement. B-STO-001..008 were added to the allowed storage test file because their prior coverage lived outside the allowed edit surfaces.
- Reworked `test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically` (B-STO-040/B-FLAKY-010): the current migration result asserts `SCHEMA_VERSION == 12`; v9-only request-schema restrictions are exercised at the v7→v9 migration boundary. This avoids treating the historical v9 target as the current database version.
- Reworked the cycling and Audaz known failures (B-STO-054/B-FLAKY-008 and B-STO-056/B-FLAKY-009) to test fail-closed reads under schema 12, where request schema 5 is valid for the separate v5 batch contract. Their intended persistence round-trip and cross-kind/version checks pass.
- Assumption: current schema-version capabilities take precedence over historical schema-version assertions, while migration-boundary behavior is checked against the corresponding historical migration DDL.

## Validation

Commands run from `wt-rw-sto/webapp/backend`:

- `python -m pytest -q -p no:playwright tests/test_storage.py tests/test_profile_storage.py tests/test_profile_archive.py tests/test_datasets.py tests/test_history_import.py tests/test_import_records.py tests/test_quota.py`: **151 passed**.
- `python -m ruff check laboratorio tests`: **All checks passed**.
- `python -m pytest -q -p no:playwright`: **850 passed, 5 failed** (855 collected; 2 warnings).

Full-suite failures observed:

1. `tests/test_api.py::test_dataset_discovery_is_bounded_inert_and_metadata_only` — response includes `source_format`, while the assertion expects the older exact item shape (B-FLAKY-001).
2. `tests/test_api.py::test_settings_exact_quota_and_validation` — expected profile-only admission bytes; actual admission total includes additional persisted artifacts (B-FLAKY-002).
3. `tests/test_api.py::test_settings_below_used_conflicts_without_mutation` — expected all non-experiment bytes to be profile bytes; actual profile-artifact total differs (B-FLAKY-003).
4. `tests/test_profile_batch_queue.py::test_corrupt_worker_result_stops_batch_but_keeps_prior_ordinal` — did not reach expected failed state (B-FLAKY-007).
5. `tests/test_profile_batch_queue.py::test_local_strategy_failure_continues_later_ordinals` — SQLite `database is locked` while polling the saved experiment; not one of the three known failures in the requested files.

The first four failures are outside the allowed edit surfaces and were not changed. The fifth is an unrelated, unclassified failure. No source/product files were changed; no product bug was observed in the focused B-STO suite.

## Deletions and replacements

- Removed: none.
- Replacements: the three known failing storage tests were made deterministic while preserving their stated intent; B-STO-040 now distinguishes the current schema version from the v9 migration-boundary constraint.
