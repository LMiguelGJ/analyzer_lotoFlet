# L3c — strict persisted laboratory HTTP

## Immutable target

- Identity: `8d4cc29f7beb3f3015e5a9bd5a6682cef71e29cceae2435ec0ec7132184b969e`.
- Artifact: `C:/Users/luism/AppData/Local/Temp/reference-labs-jd-l3c-http-70_n0l19/manifest.json`, sibling snapshot.
- Base `0d33004`; 140 files, 48,743,646 bytes; all sixteen migrations, conftest/test/fixture/source context, actual pinned history/rankings, two exact baseline source files under `__baseline__`.
- Four authored paths: `laboratorio/api/reference_labs.py`, `laboratorio/app.py`, `tests/test_reference_lab_runs_api.py`, `tests/test_reference_lab_runs_golden_api.py` under `webapp/backend`.
- All four live hashes stable before/after copying. App diff inspected: reference RLock plus 64-KiB POST-path predicate; old mutation guards unchanged. Storage/engine/reference data remain context, not authored changes.

## Writer observations

- RED: 41 failures, 2 passes, 9 errors in 9s (missing run routes).
- Rapid HTTP: **37 PASS in 16.6s**.
- All-fourteen golden HTTP: **15 PASS in 635s**.
- Combined seven-module suite: **218 PASS in 781s**. Ruff and format check clean; production diff whitespace clean. This is writer evidence, not independent approval.
- Each actual laboratory POST compared full immutable summary/provenance against source-pinned fixture; GET identity and thin listing verified. All session pages fetched through public HTTP with limit 100; independent test routines recomputed canonical seven-field digest, boundaries, wagering/payment/draw totals and completed mean. No production hash helper used as sole oracle.

| Laboratory | Stored sessions | POST plus full paging |
| --- | ---: | ---: |
| transicion_1_audaz | 964 | 1.1s |
| frios_1_audaz | 975 | 0.9s |
| selector_1_audaz | 947 | 0.8s |
| mezclas_1_audaz | 969 | 0.9s |
| ensemble_5_audaz | 4721 | 8.9s |
| ensemble_10_audaz | 9062 | 32s |
| ensemble_20_audaz | 16087 | 87s |
| frios_25_escalera | 1106 | 0.9s |
| mezclas_50_audaz | 20605 | 171s |
| transicion_50_audaz | 20683 | 155s |
| paridad_50_audaz | 20404 | 160s |
| frios_50_escalera | 3503 | 5.8s |
| paridad_50_escalera | 3497 | 5.1s |
| paridad_50_plana | 92 | 0.2s |

## Contracts and observed checks

Per-lab POST/list/detail/session/delete endpoints under `/api/v1/reference-labs/{lab_id}/runs`. POST body only `required_history_sha256`, strict lowercase 64 hex plus exact min/max length, extra fields forbidden. Invalid body 422; valid wrong/import SHA or loaded-source conflict 409 before votes/replay. Uses frozen `app.state.data`, not active-history selection. Config from actual lab contract; provenance is a frozen dataclass serialized with `asdict`, origin `frozen`.

POST 201/detail GET metadata includes stored config/provenance and summary, capabilities; no nested `sessions` key anywhere. List is thin. Sessions appear only in bounded pages; offset 0..signed-i64 max, limit 1..100, defaults 20/50. Unknown UUID/lab or cross-lab ID 404 without deletion; DELETE 204, then 404 with cascade. Corrupt stored records yield controlled 409; corrupt DELETE intentionally refuses because validated scope cannot be established. Internal create storage error 500 generic with type-only log, quota denial 409 and no rows.

App reference RLock coordinates all new record operations within one process; create also acquires existing simple rankings Lock in reference→rankings order. Deterministic paused GET/DELETE tests observe 200/204 or 404, not false corruption. Catalogue remains unlocked. Shared old Origin/Host/cross-site mutation safeguards retained. Header and actual-stream 64-KiB limits apply to new run POST paths; 65536 vs 65537, short/duplicate/invalid Content-Length and chunked overflow exercised without rows written.

## Completed review and independent verification

- Blind A `mv44s1px-35-n4vm`: `rows:[]`. B `mv44s2o2-36-olbb`: initial CRITICAL future-kind claim and WARNING possible future DELETE-body protocol change, both raw rows preserved. Original B clarification `mv45ihg2-39-f48q` explicitly withdraws unsupported CRITICAL/client-traceback assertions: every current service producer uses one of the three mapped Literal kinds; unsupported injection or future code change is not a current defect. Own reclassification **SUGGESTION**, informational future-proofing only. No source fix or refuter; one initial-claim clarification, zero correction/scoped re-judgment rounds.
- Independent full HTTP verifier `mv44s3jq-37-jy4v`: **218 PASS in 695.59s, exit 0**; all 140 hashes/exact set before/after intact, no extra files. Full all-fourteen paging retained. Verifier read new two test modules/conftest, API95–253/App55–130; independently recomputed public-page digest/boundaries/closed financial mean. No claim of reading old five test modules/store/SQL16, browser, production startup, coverage or warnings-as-errors. Scoped **APPROVED**, severe/suspect/contradiction 0, INFO2; `L3c-verdict.json`.
- Native ASSESS unassessable due untracked files, RDD off, treated high risk. No native receipt or candidate approval invented.
- Read-only frontend launch-preparation scout `mv44uin8-38-r48k` resolves exact transport export, surface-brief path and UI test seams while this review runs. No source writer active.

## Limits

Each session page still validates the entire stored run; traversing all pages is quadratic. This is a known unchanged storage cost, not a hung agent. Individual UI pages will request only the visible bounded page; do not claim the inefficiency is fixed. RLock is local-process coordination, not protection for direct Repo or multiple processes. Stored corrupt records cannot be deleted via this scoped API. Create holds locks during replay, so record readers wait. No idempotency or automatic POST retries. All ASGI tests use owned temporary databases/cache, no normal listener, user profile or production startup.

API implementation is not fourteen-screen, browser, full-suite or application-readiness acceptance. Both judges and independent verification completed; verify four live hashes against frozen scope immediately before the scoped local commit. Human selected fourteen interfaces first; defer pagination optimization. Preserve reference/legacy folders, prior migrations/data/env/ports and four unrelated staged paths.
