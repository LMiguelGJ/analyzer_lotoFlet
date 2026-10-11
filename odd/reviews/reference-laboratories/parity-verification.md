# Independent historical parity-voter verification

## Scope

Followup to L2's explicit limitation: reference replay and production replay received the same votes in the historical matrix. Compare the distinct pure voter implementations directly, not a cache or the shared vector used by replay tests.

- Production: `laboratorio.domain.selection.parity_votes(first_numbers)`.
- Actual read-only reference: `repo_ref/quiniela_sim.py::consensus_parity(first_numbers)`.
- Input: the 105,426 first-position numbers from validated frozen history.
- No cache reads/writes, network, source edits, UI, server or user-data operations.

## Independently observed result

Verifier `mv3b7c0i-2n-4yyi`, exact parent-supplied Python comparison command, frozen artifact only:

- Manifest: `d39d8fc796fbfe8a23099d7eff197a74f5956f35d3e1b4a7865a19f322100d3f`.
- Snapshot: `C:/Users/luism/AppData/Local/Temp/reference-labs-jd-l2-w722r885/snapshot`.
- Validated history SHA: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.
- Both vectors have shape `(105426,)`, canonical `np.int8`, values only 0/1.
- **Mismatches: 0**; first mismatch list empty.
- SHA-256 of canonical int8 bytes, both vectors: `5100eb5d81f2fe8c894741261a66c9674ac63d2dbb397db476458ef8164040ec`.
- Production runtime: 4.643090400000801 seconds.
- Reference runtime: 20.74728499999037 seconds.
- `selection.py`, `quiniela_sim.py` and `adapter.py` hashes match frozen manifest before/after; final marker `PURE_VOTER_SOURCES_UNCHANGED`.

## Limits and next step

This establishes independently computed equality on this frozen historical input, not universal causality, cache correctness, UI correctness or integrated HTTP execution. Source inspection supports voting before the current draw updates model state; do not turn it into a universal proof.

A durable test-only regression is planned as `webapp/backend/tests/test_reference_parity.py` after the active L3a writer settles, before catalog/service final review. No parallel source writer is authorized. Existing implementation passes this direct comparison, so a coverage-only followup has no meaningful behavior RED; do not fabricate one. Keep L2's original verdict/limitation as historical record and reference this new evidence separately rather than retroactively inventing judge inspection evidence.
