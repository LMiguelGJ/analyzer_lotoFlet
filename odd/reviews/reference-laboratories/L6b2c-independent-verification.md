## PASS — independent verification

Executed the supplied `py -3.14 -B - <<'PY' … PY` guard/check command **exactly once**, with bash timeout **2000 seconds**. No retries, fixes, formatting writes, installations, or Git mutations.

### Observed commands and results

All argv below used the project cwd. `S` denotes these literal arguments, in order:
- `webapp/backend/tests/test_owned_laboratory_run_insert.py`
- `webapp/backend/laboratorio/storage/owned_laboratory_run_store.py`
- `webapp/backend/laboratorio/storage/repository.py`

| Command/argv | Exit | Observed result | Process duration |
|---|---:|---|---:|
| `py -3.14 -B -m pytest -q --tb=short -p no:cacheprovider --basetemp=C:\Users\luism\OneDrive\Escritorio\analyzer_lotoFlet\.tmp\l6b2c-independent-focused-c90172e4 webapp/backend/tests/test_owned_laboratory_run_insert.py` | 0 | **28 passed in 2.54s** | 3.989s |
| `py -3.14 -B -m pytest -q --tb=short -p no:cacheprovider --basetemp=C:\Users\luism\OneDrive\Escritorio\analyzer_lotoFlet\.tmp\l6b2c-independent-full-c90172e4 webapp/backend/tests` | 0 | **669 passed in 1106.76s** | 1108.906s |
| `py -3.14 -B -m ruff check --no-cache S` | 0 | All checks passed | 0.317s |
| `py -3.14 -B -m ruff format --check --no-cache S` | 0 | 3 files already formatted | 0.318s |
| `git diff --check -- S odd/tasks/reference-laboratories.md` | 0 | No whitespace errors; LF→CRLF notices | 0.050s |

Counts overlap: the focused 28 are included in the full **669**, not additional tests.

### Actual mutation guards

**Before and after: PASS**
- Six pinned SHA-256 values matched.
- **149** protected backend/frontend files retained hashes and modification timestamps.
- HEAD remained `00850a37e1a4349e941ce2f41da6da0f2f560d65`.
- Branch remained `feat/reference-laboratories`.
- Cached diff retained **87,352 bytes**, its expected SHA-256, and the exact four-path set.

The line-ending notices alone are **not mutation evidence**; the actual guards passed. Guard coverage does not inventory every ignored file or newly created path.

### Source proof

Read the complete 193-line implementation and 430-line new test file before execution.

- `storage/owned_laboratory_run_store.py:create_run`: exact snapshot type check and strict `from_mapping(snapshot.to_mapping())` round-trip; canonical owner-definition comparison.
- `storage/repository.py:36–44`: `_transaction` executes **BEGIN IMMEDIATE**, commits on success, rolls back and rethrows on failure.
- Within that single transaction, owned creation performs definition lookup, strict decoding, canonical comparison, quota measurement/admission, run insertion, and session insertion.
- `storage/laboratory_store.py:64–91`: decoding validates definition identity/name, canonical JSON, UTF-8 byte count, and timestamp.
- Repository wrapper delegates directly to owned `create_run`.
- Validation failures become `OwnedLaboratoryRunStoreError`; quota denial and SQLite integrity/session-trigger faults remain their original exception types.
- UTF-8 payload charging matches `repository.py:_run_artifact_bytes` and reference-run charging. It intentionally excludes the extra owner column; this is the existing **logical metric**, not physical SQLite allocation.

Focused tests observed successful persistence/readback, invalid-input rejection, stale/missing/corrupt-definition rejection, quota denial, duplicate preservation, and session-fault rollback.

### Limits / blockers

**No blocker observed within this verification scope.** No runtime concurrent-race test was added or independently executed; concurrency protection is established by transaction structure, not adversarial scheduling evidence. No return-DTO typo claim is established.

Parent LSP timeouts remain unverified, not clean results. Native ASSESS/RDD authority is not established. This PASS grants neither commit authority nor native approval.
