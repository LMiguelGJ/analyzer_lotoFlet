# L3b storage — initial frozen review

## Target and implementation

Target `5fdc1604d2888d7fa46f930a5bb9094c224f5776c14b78a339f3acda0319f45d`; `C:/Users/luism/AppData/Local/Temp/reference-labs-jd-l3b-store-4c3y5frv/manifest.json`, sibling snapshot. 140 files, 48,720,112 bytes, all 16 migrations plus four exact immutable baseline files from `a624bac` under `__baseline__`. Authored seven paths: database registry/head, repository accounting/delegates, new reference store and migration 0016, new storage tests, existing run-store schema-head expectations and history-store table inventory only. Production delta 478 lines.

Writer `mv3ssdc2-2t-ifyv`: initial RED five failures; focused 23 PASS (1.46s). Initial combined 50 PASS/1 FAIL (51.74s) stale strict v13-upgrade table inventory, not a production table loss. Parent confirmed the exact assertion and authorized only two new table names on seventh path, preserving equality and old profile count. Tuple-session serialization regression separately RED→GREEN. Final combined **52 PASS (49.97s)**, scoped whitespace clean. No public HTTP/UI implemented.

## Independent functional result

Exact five-module command: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3.14 -B -m pytest -q --no-header -p no:cacheprovider tests/test_reference_lab_store.py tests/test_run_store.py tests/test_history_store.py tests/test_reference_lab_service.py tests/test_reference_labs_api.py` in frozen backend.

Independent observed **52 PASS (43.78s)**. Exact guard before/after printed `MANIFEST_HASHES_AND_EXACT_FILE_SET_OK 140`, target identity/all file hashes/exact set intact. Temporary SQLite/ASGI only; no normal app/listeners/userdata. Native ASSESS unassessable due untracked files, RDD off, independent verification required.

Limits explicitly reported: successful exact cap boundaries, full invalid-number matrix, unknown lookup/deletion and actual engine-dataclass-to-storage integration were not additional executed probes; source readback only. Session paging internally validates the whole stored collection. Old SQL files were hashed in target, not independently compared to a separate SQL baseline. Controlled store error is ValueError subclass with no `.kind`. Tests passing do not resolve adversarial findings or establish application readiness.

## Merged initial findings — human decision required, not a terminal judgment

Initial blind Judge A `mv3thvuq-2v-tk2f` returned three HIGH and one WARNING:

| ID | Severity | Claim | State |
| --- | --- | --- | --- |
| JD-A-001 | HIGH | List pages materialize every session/full result for each selected run, potentially about 3.2 GiB serialized for 100 admitted runs, plus decoded overhead | Await Judge B corroboration |
| JD-A-002 | HIGH | Session digest checked as hex syntax only, not canonical agreement with sessions; false integrity evidence admitted/read | Await Judge B corroboration |
| JD-A-003 | HIGH | Session final balance and closed mean not reconciled with immutable capital/wager/payment accounting; coherent tampering accepted | Await Judge B corroboration |
| JD-A-004 | WARNING | Split header/session SELECTs without consistent read snapshot can report false corruption when deletion interleaves | Informational pending B |

Both blind results are complete. Exact actor fields/claims preserved in `L3b-storage-judge-a.json` and `L3b-storage-judge-b.json`; no parent-added inspection proof. Merged frozen ledger `L3b-storage-ledger.json`: **1 confirmed severe** (A001/B001 list memory), **2 single-judge suspects** (A003 financial HIGH, B002 bool/float MEDIUM), **1 severity contradiction** (A002 HIGH/B003 MEDIUM digest, factual defect agreed), **1 INFO** (A004/B004 concurrent-delete read race WARNING).

Do not relabel the digest MEDIUM to invent severe-fix authority. Ask human before round-one JD memory correction. Proposal: independently authorized ordinary test-first corrections for digest and reproducible financial/type suspects, separate from the severe-only JD fix actor; leave read-race warning as informational. No correction or re-judgment started, both round counters zero; maximum two each, no reset. Storage commit and terminal verdict remain blocked pending human decision and final verification.

## Prior unit

L3a committed `a624bac` after both judges `rows:[]`, independent 46 PASS and six live candidate hash matches. Four unrelated staged paths preserved. This storage unit remains unfinished; all public execution/persistence HTTP and fourteen Impeccable screens still pending.
