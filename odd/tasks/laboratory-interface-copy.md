# Quiniela — laboratory interface copy cleanup
Scope: the four explicit UI feedback requests below, on the existing notebook interface.
Implementation is inline and small; no new commit/push was requested. Existing rules, data, actions and error handling remain unchanged.

## Specs

### S1 — Remove the redundant rules paragraph
User feedback, verbatim:
> siento que parrafos como este no deben de estar pues ya se nota que la interfaz no te deja editar lo unico que hace esto es traer ruido visual eliminalo

Exact target text:
> Las reglas no se editan: para cambiarlas, creá otro laboratorio. Es una reproducción histórica sobre una fuente congelada, no una predicción.

Target: `section.reference-contract > p.reference-note` in `LaboratoryPanel.tsx`.

### S2 — Remove the idle execution explanation
User feedback, verbatim:
> elimina esa vaina tambien pues nunca se usan las reglas ya guardadas

Exact target text:
> Se guardará una corrida nueva con estas reglas.

Target: `div.reference-run-action > span`. This is a copy-removal request, not authorization to change which stored rules the engine uses. Preserve the source-loading error branch and disabled execution state.

### S3 — Remove the saved-run selection explanation
User feedback, verbatim:
> elimina esta texto

Exact target text:
> Seleccioná una corrida para abrir su resultado.

Target: `.reference-runs > .reference-section-heading > div > p`.

### S4 — Name the app Quiniela without the old numeric suffix
User feedback, verbatim:
> quitale el numero de 80 solo deja Quiniela como nombre de la app ya no quiero volver a ver ese 80 en ninguna otra parte

Exact original brand:
> LABORATORIO / QUINIELA 80

Target: `span.shell-brand.legend`, plus the browser document title. The visible name is `Quiniela`; numeric payouts and historical data are not branding and are unchanged. A bounded source search found the old visible branding in `Shell.tsx` and `index.html`.

### S5 — Remove the incomplete-session explanation
User feedback, verbatim:
> elimina este párrafo

Exact target text:
> Las sesiones incompletas aportan a los totales de dinero, pero no al promedio neto de sesiones cerradas.

Target: `.reference-result > p.reference-note`. Remove the paragraph, not the incomplete count, totals or closed-session mean calculation.

### S6 — Remove the per-bet limitation paragraph
User feedback, verbatim:
> este tambien lo eliminas

Exact target text:
> Este contrato guarda resúmenes de sesión; no incluye el detalle de cada apuesta.

Target: `.reference-result > p.reference-note`. Remove this explanation without inventing per-bet detail or changing stored capabilities.

### S7 — Remove the session page explanation
User feedback, verbatim:
> y este texto lo eliminas

Exact target text:
> Se consulta solo esta página de resúmenes.

Target: `.reference-result > .reference-section-heading > div > p`. Preserve the range heading, session table and pagination.

## Tasks

- T1 — Remove the rules note; S1; route: inline; status: done (source and focused DOM regression); commit: not requested; evidence: actual removal RED then included in20 GREEN.
- T2 — Remove idle save guidance and retain loading-error behavior; S2; route: inline; status: done (source and focused DOM/error regression); commit: not requested; evidence: actual removal RED, existing error behavior PASS before/after, included in20 GREEN.
- T3 — Remove saved-run selection guidance; S3; route: inline; status: done (source and focused DOM regression); commit: not requested; evidence: actual removal RED then included in20 GREEN.
- T4 — Rename the app brand and document title to Quiniela; S4; route: inline; status: done (source and focused branding regressions); commit: not requested; evidence: actual brand/title RED then included in20 GREEN.
- T5 — Check the complete frontend, types and production build; reload the supplied Orca tab and verify the served UI; S1–S7; route: inline checks/background build and same-tab read-only browser verification; status: blocked; commit: none; evidence:161 PASS/typecheck0/build0/live DOM PASS; waiting for user visual confirmation because Orca viewport and full-document captures were defective. Do not claim completed visual acceptance.
- T6 — Remove the incomplete-session paragraph, preserve displayed financial values; S5; route: inline; status: done; commit: none; evidence: actual requested-text RED then focused1 GREEN/exit0; existing adjacent behavior asserted.
- T7 — Remove the per-bet limitation paragraph, preserve actual session detail; S6; route: inline; status: done; commit: none; evidence: actual requested-text RED then focused1 GREEN/exit0; existing adjacent behavior asserted.
- T8 — Remove the page-only session explanation, preserve headings/table/pagination; S7; route: inline; status: done; commit: none; evidence: actual requested-text RED then focused1 GREEN/exit0; existing adjacent behavior asserted.

## Log

### L1 — Original UI feedback context and exact change requests
All four requests target `http://127.0.0.1:8765/laboratorios/e989ab55-cf28-48f9-9e1e-8167899efd0b`, supplied browser tab `661c5ab6-7f5f-4073-b5b6-d5e7e0eaf25f`, viewport1607x1097.

Original request1, verbatim user feedback:
> siento que parrafos como este no deben de estar pues ya se nota que la interfaz no te deja editar lo unico que hace esto es traer ruido visual eliminalo

The supplied target HTML was:
```html
<p class="reference-note">Las reglas no se editan: para cambiarlas, creá otro laboratorio. Es una reproducción histórica sobre una fuente congelada, no una predicción.</p>
```

Original request2, verbatim user feedback:
> elimina esa vaina tambien pues nunca se usan las reglas ya guardadas

The supplied target HTML was:
```html
<span>Se guardará una corrida nueva con estas reglas.</span>
```

Original request3, verbatim user feedback:
> elimina esta texto

The supplied target HTML was:
```html
<p>Seleccioná una corrida para abrir su resultado.</p>
```

Original request4, verbatim user feedback:
> quitale el numero de 80 solo deja Quiniela como nombre de la app ya no quiero volver a ver ese 80 en ninguna otra parte

The supplied target HTML was:
```html
<span class="shell-brand legend">LABORATORIO / QUINIELA 80</span>
```

### L2 — Explicit request for ODD tracking
User, verbatim:
> todo lo que te he pedido hasta ahora ponlo en odd haz la lista

This document and its TODO projection were requested after the small inline edits and focused tests had already occurred. Do not misrepresent tracking as preceding those edits. This list concerns the four current UI requests, not completion of the earlier configurable-quiniela roadmap.

### L3 — Observed implementation and checks before tracking
- Read the existing panel/workspace tests, Shell/tests, HTML, incumbent surface brief, and Impeccable distill/craft floor. Context had already run once earlier in the session; did not rerun it or repair unrelated stale briefs.
- Added separate DOM regressions for the three requested removals and an existing-behavior check for source-load failure. Observed3 FAIL/1 PASS/11 skipped, exit1,19.75s before source edits. The one passing case confirmed the existing source-loading error text, disabled execute action and no synthetic create call.
- Added brand/title regressions. Initial brand RED was valid; initial title case failed on the fixture's non-file `import.meta.url` under jsdom, not on the product title. Corrected only the test fixture to read package-root `index.html`, then observed the real title RED (`Laboratorio Quiniela 80` versus `Quiniela`),1 FAIL/4 skipped, exit1,1.51s. The setup failure remains acknowledged.
- Removed exactly the three target texts. Execution helper now renders only when there is a genuine `historyError`; execution, persistence, stored values, reference digest and controls unchanged. Existing shared `.reference-note` CSS remains for other uses.
- Changed Shell brand and HTML document title to `Quiniela`. Existing controls, navigation, keyboard focus, numeric payouts and data identifiers unchanged.
- Focused GREEN: Workspace.test.tsx and Shell.test.tsx,2 files/20 tests PASS, exit0,4.65s. Includes existing execution with exact saved digest, result opening, uncertain-response handling, delete confirmation/conflict, navigation, skip link and accessibility cases.
- Orca status and tab list confirmed the supplied tab exists on the requested route. No new tab, delete/run action, normal-data edit, Git commit or push performed. Served-build reload and browser assertions remain pending under T5.
- Automated ts-double-negation advisory is informational and refers to existing guard style; no unrelated guard/CSS/engine refactor requested or performed.

### L4 — Continue without unnecessary stops
User, verbatim:
> estas en modo yolo asi que dale sin parar

Continue the authorized four UI changes and their checks without unnecessary questions. Do not infer new engine/data changes, commits, pushes, unrelated text removal or completion of older roadmap tasks. Full frontend/type/build job12 is running; original app job10 remains serving the same authorized data. No normal-data mutation is required to verify the UI.

### L5 — Built and visually verified completion
- Background job12 observed exit0/51s wall. Full frontend suite:25 files/158 tests PASS,18.36s. `tsc --noEmit` exit0; production build exit0,72 modules,6.57s. Built bundle `assets/index-Cs9oiJ-r.js`; no server restart, dependency/configuration change or normal-data mutation required.
- Active LSP probe of five changed frontend paths: four confirmed clean, one Spanish spellchecker information (`inicial`) in existing UI wording; no errors. Do not claim a globally clean workspace. Existing ts-double-negation advisory was not a defect introduced by this edit.
- Before reload, actual same-tab DOM still showed all three old notes and old numeric brand/title, confirming the need to rebuild served assets rather than only edit source.
- Reloaded only the supplied Orca page, waited for `.reference-contract`, then took a new snapshot. Live title and brand exactly`Quiniela`; all three removed target strings absent; eight rule fields remain, Execute enabled, one stored-result button available, viewport1607x1097 with no horizontal overflow. URL stayed on the user's supplied laboratory. No create/run/delete action was clicked.
- Captured and visually inspected the same-tab screenshot. Notebook grid, flat/square controls, data and existing saved-run table remain; redundant notes are gone. Proof: `.tmp/laboratory-interface-copy/live-check.json` and `live.png` (ignored local evidence). No mobile or broader visual audit claim.
- User-visible changes S1–S4 complete and served at127.0.0.1:8765. T1–T5 done. ODD tracking/memory/TODO reflect actual completed checks. Source changes and this task file remain uncommitted because no new commit/push was requested for this scope. Older configurable-quiniela roadmap remains outside this task.
- Risk: none — copy-only UI changes; source error branch, actions, navigation, stored rules, numeric payouts, APIs and persistence unchanged and covered by existing plus focused regressions.

### L6 — Additional result-panel feedback
Same supplied route/tab and viewport. User feedback strings and target HTML, verbatim:

> elimina este párrafo
```html
<p class="reference-note">Las sesiones incompletas aportan a los totales de dinero, pero no al promedio neto de sesiones cerradas.</p>
```

> este tambien lo eliminas
```html
<p class="reference-note">Este contrato guarda resúmenes de sesión; no incluye el detalle de cada apuesta.</p>
```

> y este texto lo eliminas
```html
<p>Se consulta solo esta página de resúmenes.</p>
```

Added S5–S7/T6–T8 before these source edits; reopened only T5 verification. Preserve original numerical behavior, data, existing results, pagination and S1–S4. Source changes remain narrow UI copy, not an engine/capability change.

### L7 — New result-copy verification and explicit visual blocker
- S5 and S6 each produced the intended text-presence RED. Initial S7 test failed for an incorrect mock-call expectation: the public session API takes laboratory ID before run ID. Corrected only the test expectation to `[ID, "run-1", {offset:0,limit:50}]`, then observed the intended S7 text-presence RED before its source edit. Each of T6–T8 subsequently had one focused GREEN/exit0, with adjacent displayed summaries, session table and pagination asserted.
- Full frontend job13: exit0/40s wall;25 files/161 tests PASS in17.07s, `tsc --noEmit` exit0, Vite build exit0/4.51s/72 modules. New served bundle `assets/index--7jq78c9.js`. No dependencies, runtime configuration, engines, stored capabilities or data changed.
- Scoped active LSP probe: two frontend paths, one clean/one existing Spanish `inicial` spellchecker information, no code/type errors reported. `git diff --check` exit0; existing LF/CRLF advisories retained, not configuration changes.
- Reloaded only the supplied tab/route. Native Orca click reported success but did not select the saved result; the first DOM assertion correctly failed `Saved result not loaded`. A fresh snapshot showed neither selected result nor loading/error. Used the same existing-result button's DOM click instead; no create/run/delete action or normal-data mutation.
- Subsequent live DOM assertions PASS: all three requested result texts absent, same eight financial/count values as before reload (including incomplete1 and closed-session mean−RD$80,20), session heading1–50 of18.483,50 session rows, Previous disabled/Next enabled, titleQuiniela and no horizontal overflow. Actual live viewport was1607x1140, not a claim of the initial1607x1097 viewport. Proof: `.tmp/laboratory-interface-copy/result-live-check.json`.
- Visual acceptance is NOT complete. Orca viewport screenshot showed a large blank/misframed region; full-document capture repeated viewport tiles rather than producing a usable result-panel image. Both captures were inspected and retained as failed tool evidence, not passed visual proof: `result-live.png` and `result-full.png` in the same ignored evidence directory. Restored document scroll to0; no app CSS/logic change attempted to compensate for capture tooling.
- Plan reviewed against actual work: T1–T4/T6–T8 done with observed checks, T5 blocked solely awaiting user's manual visual confirmation. No further automatic capture retries or unrelated tool repair. Source and tracking remain uncommitted; previous roadmap remains out of scope.
- Risk: none for the copy-only source change. Missing proof: reliable rendered visual acceptance, explicitly blocked rather than silently marked done.
