# L6b1 — Strict owned metadata snapshot: initial blind review

## Bound target

- Base: `4c1d637c82f9672013417c91041eceaa428d02dd`, `feat/reference-laboratories`.
- Capture: `C:/Users/luism/AppData/Local/Temp/newreference-labs-jd-l6b1-61e4da80/`.
- `canonicalmanifest.json`: SHA256 `2befcda13869eabc592b4ad28de594a8c014f65290ba7125868a27165157772e`.
- `unit_scoped.patch`: SHA256 `520d7c0fe7fdab63bb402e3666f7e4f7eaae029cf9fdd197c61b9d10b58b5f45`.
- Added files only: `webapp/backend/laboratorio/domain/laboratory_run_snapshots.py` (79 lines, SHA256 `a29880e05b8fc9d0cb0de400fb69e6e7e1e61dfb6730714c4202fabd93273e9e`) and `webapp/backend/tests/test_laboratory_run_snapshots.py` (178 lines, SHA256 `ec512e98ddb956a1b93299e7374455ad3a814dbfefbc092a2b894626d672dcff`). Total source churn: 257 additions, no deletions.
- Both authored files are absent from the actual baseline. The manifest records absence; no baseline copies were fabricated. The added-file patch includes untracked content rather than relying on empty ordinary Git diff output.
- Capture: 97 contexts, 95 baseline and 97 current copies, 195 total files. All copies, exact inventory and final live guards verified. All 95 existing contexts are byte-equal after LF normalization; 18 raw EOL differences are retained explicitly.

## Behavior and observed evidence

`OwnedLaboratoryRunSnapshot` is a pure immutable domain metadata codec. Its own version-1 namespace uses `kind=owned_laboratory_run`, the existing strict definition snapshot and exactly three frozen-provenance fields. Exact scalar and definition types precede equality/serialization; source pins are lowercase 64-character hexadecimal strings. Mappings are fresh and defensive. Legacy metadata, result/session codecs, owner assignment, storage, API and migrations are unchanged.

Author RED was a real collection `ModuleNotFoundError` for the absent module; GREEN was 32 focused tests and 261 combined tests. Independent checks observed 261 focused passes in 29.48s, 585 full-backend passes in 786.49s with no exclusions, and 137 supplementary assertions passed. Ruff lint/format and actual added-file whitespace checks passed. Focused counts overlap the full suite; assertions are not extra pytest cases. Fourteen seed DTO loops prove metadata roundtrips, not replay or GUI behavior. Mapping decoding does not prove duplicate-JSON-key rejection.

The parent mistyped the rank guard path as `rankrepo_ref/...`. Independent phase0 resolved the correct `repo_ref/reports/chance_rank_v1/predictions/pos1.npz` and verified SHA256 `b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d`; root history remained `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`. No missing-data inference or restoration occurred. A verifier assertion about no-index check exit status was corrected: difference exit 1 is expected, without whitespace diagnostics or source changes.

Final guards: 95 existing contexts, 14 unrelated frontend files and two new files retained raw hashes/mtimes; HEAD, complete status and foreign cached patch remained unchanged. Evidence: `C:/Users/luism/AppData/Local/Temp/newlab-l6b1-independent-evidence-61e4da80/`. LSP/memory tools were unavailable to that verifier; no clean-diagnostics or memory-save claim. Native assessment was unassessable, RDD off, and independent high-risk checks were therefore required.

## Blind review and non-goals

Judges A `mv5imktk-d-nlvp` and B `mv5iml7d-e-vg24` use the human-approved generic read-only verifier fallback, identical target/criteria/skills and the native Judgment Day findings/evidence JSON. Each must fully parse the actual manifest schema, verify all 192 copies/195-file inventory and hashes before/after, read both added bodies/full patch/supporting call chains, and confirm real baseline absence. Both results are required before a parent verdict. No refuter or 4R; correction/re-judgment rounds used: zero.

Skills: `C:/Users/luism/.agents/skills/judgment-day/SKILL.md`, its `references/prompts-and-formats.md`, and `C:/Users/luism/.agents/skills/work-unit-commits/SKILL.md`. Both reviews completed with no severe or functional defect: A returned two SUGGESTION findings and eleven evidence items; B returned two SUGGESTION findings and nine evidence items. The four suggestions merge into three nonblocking INFO topics: stronger permanent malformed-shape proof, digest edge cases, and a redundant alias assertion. No optional source fixes were made. Confirmed/suspect/contradiction counts are zero; correction/re-judgment rounds used are zero. Parent persisted the ledger/verdict. **JUDGMENT: APPROVED ✅** for this exact codec target only. A prompt-quoting failure occurred before any launch call; corrected prompting started each judge exactly once.

Owned-run persistence, explicit transactional owner verification, producer/API integration, UI and manual lifecycle acceptance remain future work. Capture is forensic evidence, not native freezing, a receipt or publishing authority. Separate contextual human authorization covers scoped local L5–L10 commits; no push/PR/merge. Four unrelated staged entries retain cached SHA256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`; frontend WIP, environment, user databases, references and services are preserved.

Rollback boundary: remove these two new domain/test files and their proof records only, before future consumers exist. Do not revert L6a financial replay, prior domain/schema/store/API work or user data.
