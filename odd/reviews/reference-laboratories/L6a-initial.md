# L6a — Validated financial replay: initial blind review

## Target and boundaries

- Base: `dd6b26bc5ed6fb7cb43bd3aa92d54901a9a0ed10`, branch `feat/reference-laboratories`.
- Snapshot: `C:/Users/luism/AppData/Local/Temp/newreference-labs-jd-l6a-typefix-8dc591a2/`.
- Canonical manifest: `canonicalmanifest.json`, SHA256 `cb5e95e77146226eaf9586bcb374072218ef5874b21d1d90a46e2d70cb417cf3`.
- Patch: `unit_scoped.patch`, SHA256 `400bd4895a6427b21ebe7d5cb29c338912ee73c971d8802bbcc0448167b03b0d`.
- Authored scope: `webapp/backend/laboratorio/engine/reference_labs.py` and `webapp/backend/tests/test_reference_labs.py`, 170 additions / 14 deletions (184 diff lines).
- Current raw LF hashes: engine `cf65ef467012d2caa0d1c0afe05772bfd538054fa90a2c8182bc06ce25be2adf`; test `2de51caabb57ede17bc4e990f7d6b3f39e5def389304216689ef117bfbb04a17`.
- Base hashes: engine `17c818ce497e2e6ea9b6135272b461fa8395c34af950d2c69c65ab18224b7171`; test `a9157d315ace50d839edfda5e748e179039aacaab0b04d0d05d8f268a84a884e`.

The complete capture has 95 unique contexts, 95 base and 95 current copies, and 193 files including its three metadata files. The independent verifier checked every copy and exact file set. Eighteen supporting EOL differences are recorded; every non-authored pair is byte-equal after CRLF-to-LF normalization. This is a digest-addressed forensic capture, not native review authority or an ACL-frozen tree.

## Behavior under review

Validated capital, goal and prize values drive the faithful replay engine. Bold and ladder calculations use the configured first prize while preserving integer arithmetic, ten-unit ladder recovery and ten rounds. Fourteen historical defaults, window/ranking intersection, causal parity, UUID-neutral session digest and result shape remain covered.

A pre-review independent check found that parity-to-cold validation substitution erased the original system type. Direct `ReferenceLab` inputs using a string subclass or equality-spoof object could execute custom finance despite the domain's exact-string rule. Default-money acceptance was pre-existing; ordinary JSON strings and the validated definition adapter were unaffected. No API exposure was demonstrated.

The bounded correction now checks the original exact-string type before equality or data access. One regression node exercises both malformed values. Its observed RED failed on history access; GREEN and subsequent independent probes prove rejection before equality/data (`eq_calls=0`). This functional correction occurred before Judgment Day and consumes no Judgment Day correction round.

## Observed functional evidence

- Corrective author: one regression node passed; complete target file 33 passed; six-file suite 141 passed.
- Corrected independent focused suite: 141 passed in 27.06s.
- Corrected independent full backend: 553 passed in 660.63s, no exclusions, exit 0.
- Corrected independent supplementary probes: 56/56 passed. Valid exact-string custom parity still reaches goal balance 140, wagered 50, paid 90.
- Ruff lint, format check and scoped diff check: exit 0.
- Final integrity: 95 backend/support paths and 14 unrelated frontend files retained raw bytes and mtimes; HEAD, status, exact candidate patch and foreign cached patch remained unchanged.

The focused suite is a subset of the full suite; counts are not additive. Earlier 552-test success and two failed probes belong to the uncorrected candidate, not this target. Logs and final capture records are under `C:/Users/luism/AppData/Local/Temp/newlab-l6a-typefix-independent-evidence-8dc591a2/`.

Native assessment remained unassessable because of the untracked-declaration error; RDD was off, runtime writer large, and independent high-risk verification was required. Prior parent LSP evidence was incomplete and predates the correction; no blanket clean claim is made.

## Blind reviewers and criteria

- Judge A: `mv5gs5d2-8-cwge`.
- Judge B: `mv5gs5o8-9-zjnh`.
- Both use the previously human-approved generic read-only `gentle-ai-verify` fallback. Global legacy judge profiles remain unchanged.
- Both received identical target, scope and correctness/edge-case/error-handling/performance/security/convention criteria, differing only in judge label.
- Both must verify the manifest, patch, all copies and exact tree before and after review; read both complete current/base authored bodies, full patch and supporting call chains.
- Both return only the native Judgment Day `findings`/`evidence` JSON. The parent waits for both before merging findings or issuing a verdict.
- Round: initial. Correction/re-judgment rounds used: zero. No refuter or ordinary 4R.
- Skills: `C:/Users/luism/.agents/skills/judgment-day/SKILL.md`, its `references/prompts-and-formats.md`, and `C:/Users/luism/.agents/skills/work-unit-commits/SKILL.md`.

## Non-goals and delivery

Owned metadata, persistence, producer/API wiring, GUI and manual lifecycle acceptance remain later work. No user database, environment, reference corpus, unrelated frontend WIP or services were changed. Four foreign staged entries retain cached patch SHA256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`.

Both blind reviewers completed: A and B each returned zero findings and eight genuine source-inspection evidence items. All confirmed, suspect, contradiction and INFO counts are zero; correction/re-judgment rounds used are zero. Parent validated both native JSON shapes and persisted the ledger/verdict. **JUDGMENT: APPROVED ✅** for this exact target only. Neither functional checks nor this standalone judgment grant native authority or permission to publish. Separate contextual human authorization permits scoped local L5–L10 work-unit commits only after applicable checks. No push, PR or merge is authorized.

Rollback boundary: the two authored engine/test files and this unit's proof records only. Reverting to the base restores fixed-finance rejection; it does not roll back laboratory domain/schema/store/API changes or user data. A forward correction is preferable to restoring the type-substitution flaw.
