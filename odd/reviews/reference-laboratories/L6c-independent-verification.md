**PASS — independent technical verification of L6c only.**

Fresh human-authorized compatibility pass: **415 PASS across15 individual commands**, each executed once, all exit0. Together with previous focused **17 PASS**, scoped total **432**.

| Test file (`test_*.py`) | Pass | Wall seconds |
|---|---:|---:|
| history_api | 6 | 17.768 |
| laboratories_api | 30 | 4.706 |
| laboratory_definitions | 32 | 0.561 |
| laboratory_migrations | 8 | 1.111 |
| laboratory_run_snapshots | 32 | 0.571 |
| laboratory_store | 32 | 1.965 |
| owned_laboratory_run_insert | 28 | 1.795 |
| owned_laboratory_run_list | 17 | 2.200 |
| owned_laboratory_run_store | 29 | 2.903 |
| reference_lab_ownership_scope | 2 | 0.973 |
| reference_lab_result_validation | 25 | 0.520 |
| reference_lab_runs_api | 37 | 11.334 |
| reference_lab_store | 125 | 5.908 |
| reference_labs_api | 2 | 2.729 |
| runs_api | 10 | 24.801 |

Exact argv per command, root cwd, stdout/stderr, exits, timings and guards:
`.tmp/l6c-fresh-compat-47c98d02/report.json` and `result00.json`–`result14.json`.

- Before/after **153 SHA+mtime guards**, six pins, complete pathset, HEAD/branch and foreign87352-byte staged patch: **unchanged**.
- Previous source inspection and Ruff/format/whitespace PASS retained, not repeated. UUID/config forwarding: `domain/laboratories.py:224`, `engine/owned_laboratory_service.py:44`; bounded DTO and lock order: `api/laboratory_runs.py:69,94`; atomic current-definition check: `storage/owned_laboratory_run_store.py:136`.
- Historical missing-parent fixture failure preserved; fresh run used the prepared parent.
- **Limits:** two Pyright missing-import diagnostics remain, cause UNKNOWN. No new concurrency probes, full-backend703 run, UI/browser acceptance, native/JD approval or commit permission.
