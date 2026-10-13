# L6b2d — Owner-scoped historical run pagination

Base92a8b8fbfcf05bfe8cecdf5951a27ddeb0189b1a, branchfeat/reference-laboratories.
Production adds list_runs and a thin Repository wrapper; existing getters/creators, legacy NULL-owner queries, schema17 and shared validators remain unchanged.
A BEGIN read view covers owner-only count, descending timestamp/id page selection and strict existing owned decoder. Only selected-page summaries are returned.
IDs never infer ownership. Strict offset0..i64/limit1..100; corrupt other/NULL-owner/off-page payloads excluded, visible corruption fails closed; no live-definition dependency for historical reads.

## Observed TDD and checks

Parent authored new tests before production. One actual RED: missing list_runs import, exit2/zero collected/one error0.43s, no fixtures executed;150 backend/frontend hash+mtime/HEAD/staging guards passed.
Inline implementation then own focused17PASS15.90s. Ruff lint passed; format initially failed ONLY on new tests. Mechanical formatting preserved identical AST and149 non-test-file hashes/mtime; no assertion/fixture changes.
Postformat own compatibility11files360PASS18.20s, Ruff lint/format3/whitespace PASS;150 backend/frontend hash+mtime/HEAD92a8b8f/foreign87352-byte patch guards passed.
Independent mv60zlw2-1-gphy read the whole feature document and relevant source, then17PASS1.71s,360PASS14.25s, Ruff lint/format3/whitespace PASS; four frozen pins/150 hash+mtime/complete Git path set/HEAD/branch/staging passed.
Raw rule verdicts and limits are in L6b2d-independent-verification.md; exact expanded argv/cwd/exit/stdout/stderr/durations/guards in L6b2d-independent-commands.json.
Counts overlap. This is a scoped360 run, NOT a new full-backend686 run;669 full PASS belongs to the preceding INSERT commit.

## Risk and limits

Risk: item4 (concurrent read coherence).
Actual deterministic interleaving uses WAL ONLY in an isolated test DB: real public confirmed deletion commits on a second connection between ID selection and decoding, the list preserves its prior coherent view and later reads observe deletion. No timing threads/sleeps or changes to production journal mode.
Verification's background tool was unavailable; it used one bounded synchronous driver, no retries or source fixes. This is a reported tooling fallback, not native authority.
LSP remains inconclusive; no clean claim. RDD clone-local OFF/global ON; native assessment previously unavailable, no candidate/receipt/approval. Full-feature Judgment Day remains L9.
Scoped contextual local commit only; preserve foreign staged patch byte-identical, no push/PR/merge. Producer/API and L7-L10 remain pending.
Whole source/proof/tracking churn is disclosed at preflight; never remove tests or evidence merely to fit400.
