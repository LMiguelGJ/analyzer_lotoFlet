# L6c — Execute stored user configuration by explicit owner UUID

Base b838ea7f73d7428d46c65c14b77371f78f3a0768; feature branch feat/reference-laboratories.
New owned service strictly roundtrips the stored LaboratoryDefinition, checks exact required history input and pinned source, and calls the existing UUID/config adapter and faithful kernel without catalog lookup.
Snapshot binds definition/history/rankings. The loader retains verified immutable NPZ bytes; source paths are not reopened after validation.
Four owner-scoped routes create, list, detail and paginate sessions. POST/detail contain compact snapshot/summary/capabilities, not complete sessions.
POST takes reference_lab_lock then rankings_lock; persistence rechecks canonical current definition under its existing BEGIN IMMEDIATE transaction. Missing/changed/corrupt definition, quota or invalid source do not save partial rows.
Owned POST joins the existing 64KiB body guard; local Host/Origin protection and existing routes are preserved. No new per-run DELETE or migration.

## Actual lifecycle

One real HTTP RED:17 failed3.20s (exit1/3.957wall), absent routes404/API import absent/body cap absent, no fixture setup errors.151 source/frontend hash+mtime/HEAD/foreign staging guards passed.
Parent implemented service/router/narrow app integration inline. Own17PASS3.61s (4.4wall) with real ranked one-draw source, manual UUID/config, snapshot/readback/paging/isolation and quota/source/replay/delete rejection.
Ruff initially flagged API formatting; mechanical formatting preserved identical AST, frozen test unchanged SHA9cad92a5d045156b543df68dd9d6809f04448b3f9a52a9e706d7d1bd076b5cfc. Own16file432PASS43.97s (44.82wall), Ruff lint/format4/whitespace PASS;153 guards passed.
Independent first pass:17HTTPPASS3.62s, source inspection/quality/153guards PASS; first compatibility file had6 setup errors because the verifier appended a leaf beneath an uncreated scratch parent. Other15 files unexecuted, no retry, no production defect shown.
After explicit Needs your decision, the user's contextual continuation authorized ONE fresh compatibility execution. Parent prepared the project-only scratch parent first;15 files executed once each with direct-child basetemps, all415PASS. Previous17/quality checks were not repeated.
Final scoped independent total432=17previous+415fresh, not a single command/timing. Preserve partial report and fresh completion separately. Before/after six pins,153 SHA+mtime, pathset/HEAD/branch and foreign87352-byte staged patch passed.
Exact command/stdout/stderr evidence exported to L6c-independent-commands.json, without irrelevant full foreign-staging byte dumps; original full scratch report retained by SHA. No evidence is removed to fit400.

## Evidence limits and risk

Risk: item2 (shared HTTP guards) and item4 (cache/replay/delete concurrency).
No additional concurrency scheduling probe, new full-backend703 run, UI/browser acceptance, native/JD approval or delivery authority.
Active LSP found two new-module missing-import diagnostics, one clean path and one inconclusive path. Read-only scout found correct paths/packages and root extraPaths, no justified source correction; cause UNKNOWN. Preserve findings, do not suppress or call them clean. The existing numeric-parse advisory is pre-existing and not changed.
RDD clone-local OFF/global ON; prior native assessment unavailable. Independent technical verification is complete for this unit, not a native receipt.
README documents routes/source/snapshots/deletion counts/schema17; single-screen UI remains L7, isolated lifecycle L8, fourteen manual recreations/JD L9, final regression/visual documentation L10.
Contextual local commit only, preserve foreign staging and unrelated frontend WIP; no push/PR/merge. Whole source/proof/tracking churn disclosed at preflight.
