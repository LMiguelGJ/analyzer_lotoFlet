# Q2 history-source candidate — own checks

Scope: T2/Q2, S4/S5/S14 in `odd/tasks/quiniela-configurable.md`. Candidate baseline is `33aaf8ceb592180da3769de960d011df874d5989`; immutable candidate manifest is `.tmp/quiniela-configurable/q2-scope/manifest.json` (13 paths, 1,825 additions / 6 deletions). This report is not independent acceptance.

## Observed checks

| Check | Observed result | Evidence |
|---|---|---|
| Original focused parser/store/API | 22 passed, exit 0, 5.83s | `.tmp/quiniela-configurable/q2/batch-19/` |
| Migration compatibility | 8 passed | Worker batch-11 ledger |
| Existing Q1 profile API / local guards | 60 passed | Worker batch-12 ledger |
| Existing v1 history seam | 2 passed / 4 deselected | Worker batch-13 ledger |
| Original Ruff checks / formatting | 10 Python paths passed | Worker batch-20 / batch-22 |
| Parent full included source, original candidate | **1 failed**, exit 1, 0.92s | `.tmp/quiniela-configurable/q2/parent-included-01/` |
| Corrective synthetic included-source regression | **1 failed (RED)**, exit 1 | `.tmp/quiniela-configurable/q2/correction-01/red/` |
| Corrected parser regression set | 16 passed, exit 0 | `.tmp/quiniela-configurable/q2/correction-01/green/` |
| Corrective Ruff / format | 3 paths passed, exit 0 | Corrective worker command logs |
| Parent corrected full included source | 1 passed, exit 0, 19.51s; stderr empty | `.tmp/quiniela-configurable/q2/parent-included-02/` |

Counts above are separate, overlapping runs, not an aggregate number of distinct cases.

## Confirmed correction

Every one of the actual 105,426 included rows has `hora`, `numeros`, and `source_url`. The original adapter rejected the third field. The bounded correction permits optional string `source_url` metadata only, preserves legacy two-key rows and unknown/non-string-field rejection, never fetches URLs, and never claims rankings/provenance. Exact raw SHA-256 includes those bytes; canonical replay does not.

The corrected full-source case independently constructs expected IDs, UTC instants, ordered result tuples and repeated-result counts directly from every original row, then compares all 105,426 normalized draws. Raw frozen SHA, original counts, boundaries and absence of ranking claims remain asserted. The worker did not open the included dataset; the parent executed this selector after the actual source correction. The failed original candidate was not retried unchanged.

## Retained limitations

- Initial missing-parser RED exists; public API-route preimplementation RED was not captured. No historical RED is reconstructed.
- Worker initial assertion/SQL fixture/Ruff/format failures remain in its ledger. Batch-03 logs were deleted because redirects were placed inside pytest basetemp; exit 1 and capture incident remain declared.
- Parent active LSP store/API probe confirmed no files clean, one file inconclusive, and reported Spanish UI spellchecker information only. This is not a clean-workspace claim; inherited resolver/type limitations remain separate.
- Native ASSESS is unassessable because untracked files need explicit declaration. RDD is off; assessment supplies no review receipt and requires an independent verifier.
- Full backend suite, fourteen golden replays, browser/mobile acceptance and v2 execution/UI are deferred to later feature units.

## Preservation and next action

Parent freeze confirmed HEAD unchanged and foreign staged four-path binary diff exactly 87,352 bytes / SHA-256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`. No normal data, protected inputs, old active-history semantics, processes, startup, dependencies or deployment were changed.

Independent read-only verifier `mv7m6wla-5-ui1e` returned **BLOCKED / incomplete** for S4/S5/S14: developer restrictions forbid writes and execution without exact command authorization; its authorization query timed out. It executed no commands and wrote no report/ledger/probes. It read the spec/plan/manifest/source/tests and parent proof, but independently checked neither functional outcomes nor hashes/HEAD/index/Ruff/LSP. Parent-requested included metadata-read validation and exact quota-border probes remain unexecuted; the verifier identified both as static concerns only, not reproduced defects. Q2 is blocked pending a decision, not accepted or committed. No automatic replacement/retry or policy override. Proposed local slices remain parser/format, store/migration/quota, API/wiring/evidence; no push or PR.

Risk: items 1/2/3/4 — additive persistence migration, extended request guards, shared quota accounting and serialized admission. Independent verification is required before closure.
