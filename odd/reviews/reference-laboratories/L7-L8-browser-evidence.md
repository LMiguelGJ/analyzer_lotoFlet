# L7 unified workspace and L8 lifecycle — real-browser evidence

Base 6906184d811b5952a00d2fe897a85a6fe69c6262, branch feat/reference-laboratories.

## Scope

Single screen at `/laboratorios`, `/laboratorios/nuevo`, `/laboratorios/:labId`: persisted laboratories at the side, manual creation form, rules, execution, saved runs, paged session results and confirmed deletion with run and session counts. No per-run deletion exists in the API and none is offered.

## Automated checks

- Frontend 151/151 PASS (25 files), `tsc --noEmit` exit 0, `vite build` exit 0.
- API client 5, form model 4, mean formatter 2, workspace 10 (axe on the create form included), route test updated to the new contract.
- Client, form model and mean formatter have genuine RED (module absent, nothing collected) then GREEN.
- Page components were written before their tests: no RED exists for them. Tests assert real behavior, not test-first evidence.
- Two RED cycles came from browser findings (digest path, plural forms).

## Real browser (Orca embedded, isolated runtime)

Isolated backend 8791 with temporary data under `.tmp/l7-qa/data`, Vite 5191, one owned Orca tab. No normal-user data, no existing preview touched. Own processes stopped by exact PID and tab closed afterwards.

Lifecycle:

1. Create `transicion_1_audaz` manually through the form (POST 201, fresh UUID). Execute (4.3 s). Result equals the golden: eligible 65235, gaps 6543, completed 963, incomplete 1, goals 681, ruins 282, wagered 1182452, paid 1190701, net 8249, mean 10.28348909657321, session digest `e7e9d68a1ac0078b4e5a42366f6e989f8b4871f95cb6673717c17839ba69fbc4`.
2. Confirmed deletion through the dialog (names 1 run and 964 sessions). DELETE 200, empty state, run and sessions gone.
3. Delete seeded `paridad_50_plana` (13 remain), restart the backend on the same data: still 13, neither laboratory reappears.
4. Recreate `paridad_50_plana` manually through the form: new UUID. Result equals its golden: 92 sessions, 91 completed, 13 goals, 78 ruins, wagered 3261750, paid 3118481, net -143269, mean -1572.7692307692307, digest `23fb088c348900c7a56dacedaa97597c6ad6e76da22a4d767716e4022d9c83fb`.

## Defects found only in the browser (all fixed)

1. Saved-result source digest rendered empty: it lives at `snapshot.provenance.history_sha256`. The wrong TypeScript type and mock hid it. The corrected strict type now lets `tsc` catch it.
2. Narrow screens: the form or detail sat below the whole list. Fixed with a `data-selected` order rule; measured stage top 120 px versus list top 1274 px at the narrow viewport, no horizontal overflow.
3. Plurals ("1 corridas", "1 incompletas") and the clipped sidebar pagination.
4. Mean net per closed session showed 16 decimals; now two decimals.

## Limits (not claimed)

- Only 2 of 14 laboratories were recreated and compared; the other 12 are L9.
- Keyboard-only pass, loading, error and ambiguous-network states were verified by unit tests only, not in the browser.
- Embedded browser quirk: clicks are ignored until a screenshot is taken (document visible, `hasFocus` false). Treated as a tool quirk; the app responded correctly once focused. Not proven on a real focused browser.
- Seeded names are raw ids and seeds share a creation timestamp, so list order differs from the original order (cosmetic, unchanged).
- Project convention keeps every DOP amount signed, so capital shows as `+RD$2.000`. Left unchanged; open design question for the owner.
- Superseded prototype pages `CatalogPage`/`ReferenceLabPage` remain in the tree, unrouted, with passing tests.
- Backend not re-run for this unit (no backend change). No Judgment Day, native review or full-backend run claimed.
- Screenshots live in ignored `.tmp/l7-qa` and are not committed.
