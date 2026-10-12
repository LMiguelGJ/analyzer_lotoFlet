# L6b2b1 — Shared result and stored-session validation kernel

## Bound target

- Base: `f650a563ea518194de478e84aa8ade6810cebeb1`, branch `feat/reference-laboratories`.
- Existing source: `webapp/backend/laboratorio/storage/reference_lab_store.py`, SHA256 `fc89bf38d80ab50891a3749bf906d067746c79ad778b0bdc8e1f6001aae1bc79`, 507 lines / 19,137 bytes; 86 additions / 74 deletions.
- New test: `webapp/backend/tests/test_reference_lab_result_validation.py`, SHA256 `bcd4ec3318f841307c539769f6d8711db80e7cab1b4ff847143616a8b9e816c6`, 172 lines / 5,442 bytes. Total source: 258 additions / 74 deletions, 332 lines of churn.
- Private paired capture: `C:/Users/luism/AppData/Local/Temp/newreference-labs-jd-l6b2b1-4a78b114/`.
- `canonicalmanifest.json`: SHA256 `b3eda97cf762c901e2bd6b396273b0d141f6f200859a6ff0b949cc8eaeb26f43`.
- `unit_scoped.patch`: SHA256 `ea7b9e2f1abb29e155dec2445c3f71872c09f71e0856ae98f5079feac6ab529c`.
- Actual inventory: 99 contexts, 98 real baseline and 99 current copies, 197 copies / 200 files. Only the new kernel test is baseline-absent. All 97 non-authored support pairs match after LF normalization, with 18 explicit raw EOL differences. Existing codec and ownership-isolation tests are baseline-present.

## Behavior and parent-controlled test-first evidence

Extract `_validate_result(lab_id, capital, result)` and `_validate_session_rows(sessions, session_rows, capital)` from the existing legacy paths. The former returns canonical result-envelope/session JSON texts; the latter validates row cardinality, strict ordinal, duplicate-key-safe JSON, session bounds and canonical copy equality. Existing strict checks and digest/canonical serialization are reused, without a second finance or engine algorithm. Legacy `_validate_input` retains its five-argument / three-value contract; `_decode_run` retains headers, DTOs and corruption wrapping. All five owner-NULL predicates remain unchanged.

Tests-only author `mv5lqdz9-n-ztou` wrote the new tests without executing them or implementing helpers. RED verifier `mv5lu38a-o-tuc0` ran the exact focused command once: exit2, zero collected / one collection error in0.21s, missing `_validate_result` import at line8. `_validate_session_rows` import was not independently reached. This is a new private-contract RED, not a public production defect. Source/cached guards matched before and after.

Implementation author `mv5lxv1t-p-8nr8` then extracted the helpers without changing the tests; AST and diff checks passed, no fixture-producing commands were run. Its role-local “TDD not active” label is not the parent lifecycle record; the parent observed RED before extraction and delegated GREEN afterward.

Independent verifier `mv5m2w6k-q-kcvp` observed **25 new tests passed in0.06s**, **296 compatibility tests passed in25.67s**, and **612 full-backend tests passed in766.96s**, all exit0. Focused counts overlap the full suite, not additional unique cases. Cache-disabled Ruff lint/format and genuine added-file whitespace checks passed; no fixes or reruns. Protected old110 hashes/mtimes, three source pins, HEADf650 and the 87,352-byte foreign cached binary diff remained intact. Frontend hashes were guarded, not browser-tested.

## Evidence limits and source review criteria

The extraction now canonicalizes result/session JSON before metadata JSON, unlike baseline. Config/provenance checks still precede result validation; the verifier found no observable contract defect and compatibility tests passed. No separate baseline-output probe was executed. Reviewers must assess this ordering from the complete copied baseline/current source, without inventing a runtime claim or treating an internal order change alone as a regression.

Native ASSESS was unassessable due to untracked scope declaration, with RDD off and runtime writer large; the independent high-risk fallback ran. No native candidate/authority was created. Verifier LSP/CodeGraph/Engram tools were unavailable. Earlier auxiliary `_loads` unchecked-throw diagnostic was pre-existing; no unrelated parser change. Parent actively probed the two current changed paths with a1500ms budget: zero confirmed clean, zero findings, two inconclusive timeouts. This is not a clean-diagnostics result.

The read-only verifier did not create a capture. Parent mechanically serialized passive source copies/manifest into a unique private Temp root after functional PASS, with repository source and staging untouched. Both reviewers independently validate the full copy/tree/hash inventory before and after source inspection. This is forensic evidence, not native freezing, ACL immutability, a receipt or delivery authority.

## Review and delivery boundaries

Initial pair A `mv5mrazh-r-g21n` and B `mv5mrbbh-s-qc7h` returned `findings: []` / ten evidence items each, using the human-approved generic read-only fallback. B's complete raw result is persisted. A acknowledged four unresolved support-file inspections and parent-query timeouts; continuation `mv5n385a-t-nglk` is completing those exact captured paths under the same initial candidate and full before/after metadata guard. A completion `mv5n385a-t-nglk` resolved all four required support reads and returned complete replacement raw JSON: no findings /15 evidence items. Initial filename/timeout limitations remain recorded. B returned no findings /10 evidence items. Both complete results are persisted; parent ledger/verdict are APPROVED with confirmed/suspect/INFO/contradictions empty. This was an initial-review completion, not a correction/re-judgment round; zero corrections or re-judgments. The verdict creates no native authority or delivery permission. Identical target/criteria and exact stdout-only metadata guard; complete baseline/current store, added172-line test, patch and affected callers/contracts must be inspected. Both native `findings`/`evidence` outputs are required before a parent verdict. No runtime claims by judges, source fixes, refuter or4R; correction/re-judgment rounds used: zero. Skills: `C:/Users/luism/.agents/skills/judgment-day/SKILL.md`, its `references/prompts-and-formats.md`, and `C:/Users/luism/.agents/skills/work-unit-commits/SKILL.md`.

Explicit-owned reader/insertion, producer/API and UI remain future units. Domain, engine, migrations and repository wrappers are unchanged. Rollback boundary is this extraction and its test/proof only; preserve prior owner-NULL isolation and all user data. Separate contextual human authorization permits scoped local L5–L10 commits only, not push/PR/merge. Four unrelated staged entries retain cached binary SHA256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`.
