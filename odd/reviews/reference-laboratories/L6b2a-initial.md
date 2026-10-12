# L6b2a — Legacy run ownership isolation

## Bound source and capture

- Base: `9fcc886707fbe9fe392b78941539abd6302946e3`, `feat/reference-laboratories`.
- Authored existing file: `webapp/backend/laboratorio/storage/reference_lab_store.py`, SHA256 `15a0f957fc5de02a6ae3cd64ee9a5d8efe81928d8daf45071e73569f4272f3f1`, 10 additions / 5 deletions.
- Authored new file: `webapp/backend/tests/test_reference_lab_ownership_scope.py`, SHA256 `dca74c7f351b40537611b35027ade56f77cab8accca041736b1d595bc440031c`, 193 lines. Source total: 203 additions / 5 deletions, 208 lines of churn.
- Private paired capture: `C:/Users/luism/AppData/Local/Temp/newreference-labs-jd-l6b2a-076595c7/`.
- `canonicalmanifest.json`: SHA256 `d19c693b146cef08008a4232e52ed3af7bc8aec1403d68e50daf6ad59485f094`.
- `unit_scoped.patch`: SHA256 `9acbfd638fe692fbb13d1b35d6a8d0ae3215c21d6939a6f4375132148cd28e14`.
- Actual inventory: 98 contexts, 97 real baseline and 98 current copies, 195 copies / 198 files. Only the new ownership test is baseline-absent; the two L6b1 codec files are now present in baseline9fcc. All 96 non-authored pairs are LF-normalized equal, with 18 explicit raw EOL differences.

## Behavior and functional evidence

All five legacy query sites require `owner_laboratory_id IS NULL`: get/read head, list count, materialized list page, session head and delete. Explicitly owned rows are invisible and cannot be removed by legacy methods, including malformed owned JSON that must be excluded before list projection. NULL-owner rows retain legacy CRUD, DTOs, filtering, pagination and deletion cascade, including laboratory/run UUID collisions. Ownership is never inferred from names, metadata, digest or laboratory ID.

Author `mv5jtwm2-h-26eb` observed two RED failures before implementation (owned get leaked into decoding; malformed owned JSON broke listing), then two focused GREEN tests and 271 compatibility tests passed in23.30s. Independent verifier `mv5k69ps-i-1i83` observed 271 focused passes in28.08s and **587 full-backend passes in733.61s**, exit0, no exclusions. Focused tests overlap the full suite. Its q6 inline probe ran once with **38 behavioral assertions passed** in a fresh owned Temp database; assertions are not extra pytest cases. The probe includes valid legacy-shaped owned metadata/result/session records and NULL-owner UUID collisions. Ruff lint/format and actual added-file whitespace checks passed.

The original full run timed out at180s and remains inconclusive. Exactly one fresh retry (`full-retry1`, already started) supplied the full result under a1800s budget; no second superseding retry ran. A scoped process check found no prior owned Python/py runner before the retry. Final112 source SHA/mtime entries, protected old110 entries, authored pins, HEAD and the four foreign staged entries/cached binary patch remained unchanged.

## Resolved tooling issues and checks not confirmed

A parent prompt joined the test pin and its193-line count, producing an unintended65-character expected pin. Corrected only the inline expected literal; actual source matched the original64-character pin. The protected cache digest is SHA256 of raw `git diff --cached --binary` output (87,352bytes), not SHA256 of `.git/index`. Parent bounded read-only fallback confirmed both pins, HEAD and exact foreign staging after a commandless incident scout could not execute checks; no restoration or source fix occurred.

Native ASSESS was unassessable because untracked files required an explicit declaration; RDD was off, runtime writer large, independent high-risk verification required. No native authority was created. Active LSP checked two paths: zero confirmed clean, one finding, one inconclusive. Auxiliary AST-grep `unchecked-throwing-call-python` at the existing `_loads` JSON parser is pre-existing: its body is identical to baseline9fcc. No unrelated parser fix, blanket-clean claim or guessed per-file timeout attribution.

The read-only verifier could not write a capture. Parent revoked that instruction and mechanically serialized passive source copies/manifest into the unique private Temp root, with repository sources untouched. Both blind reviewers independently verify the entire copy/tree/hash inventory before and after source inspection. This is forensic evidence, not native freezing, an ACL guarantee, receipt or delivery authority.

## Review and delivery boundaries

Initial blind pair complete: **JUDGMENT: APPROVED ✅**. Both reviewers returned no findings; A supplied10 evidence items and B12. Parent persisted exact raw results and validated both native JSON shapes before merging. Confirmed/suspect/INFO/contradictions are empty; corrections/re-judgments used are zero. No source changes followed review. Review identities: A `mv5l9k24-k-l3xt`, B `mv5l9khi-l-2imy`, human-approved generic read-only fallback, identical target/criteria and exact stdout-only metadata guard. Native output contract is `findings`/`evidence`; both outputs are required. No runtime claims by judges, source fixes, refuter or4R. Correction/re-judgment rounds used: zero. Skills: `C:/Users/luism/.agents/skills/judgment-day/SKILL.md`, its `references/prompts-and-formats.md`, and `C:/Users/luism/.agents/skills/work-unit-commits/SKILL.md`.

Owned readers, shared result-validation extraction, atomic owned insertion, producer/API and UI remain future units. Domain, engine, migrations, repository wrappers and existing result codecs are unchanged. Rollback boundary is these five predicates and their new isolation tests/proof only; do not alter definitions, ownership columns, user data or prior financial replay. Four unrelated staged entries retain cached SHA256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`. Separate contextual human authorization permits scoped local L5–L10 commits only; no push, PR, merge or service/user-database mutation.
