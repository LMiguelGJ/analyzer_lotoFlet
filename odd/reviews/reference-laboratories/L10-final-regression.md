# L10 — final regression, visual quality and documentation

Base 4aa139007d007e2ae731f148bce421fe2e7d515a, branch feat/reference-laboratories.

## Automated regression (exact results)

- Full backend: `py -3.14 -B -m pytest -q --tb=short -p no:cacheprovider tests` with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and a fresh project-local basetemp: **703 passed in 649.41 s**. This is the first full run that includes the owned-run API (L6c) and the final workspace work.
- Full frontend: **151 passed (25 files)**, `tsc --noEmit` exit 0, `vite build` exit 0.
- Fourteen manual recreations compared with the protected goldens: 14/14 PASS (`L9-recreation-verification.md`).

## Real browser (Orca embedded, isolated runtime, own tab, own processes stopped by exact PID)

- Desktop and 390 px layouts of list, creation form, rule panel, saved runs, result, confirmed-deletion dialog: inspected from screenshots; no horizontal page overflow; tables scroll inside their own region.
- Full lifecycle: create, execute, confirmed deletion, restart without reseeding, recreate with a fresh UUID: exact golden match for two laboratories (L7/L8 evidence).
- Server unreachable: the sidebar shows the problem, a recovery sentence and a retry button (inspected).
- Keyboard: tab order is logical and every interactive control is at least 48 px high. Focus rings are defined in CSS (`:focus-visible` global rule plus component rules) but could NOT be seen rendered, because synthetic key presses did not move focus and the embedded window had no focus. Verified in the stylesheet only.

## Defects the browser found that unit tests and typing had missed (all fixed)

Empty source digest (wrong snapshot path), narrow-screen content order, singular/plural forms, 16-decimal mean, clipped sidebar pagination.

## Documentation

`webapp/README.md` now describes three screens and the laboratory screen's behavior, including that DOP amounts are always signed, deletion semantics, no per-run deletion and no per-bet detail.

## Judgment Day

Blind dual review of the workspace and the recreations: zero findings from both judges, APPROVED (`L7-L9-verdict.json`). The review quality notes recorded there stand: one judge cited tests that do not exist, so this approval is a review state, not proof of correctness.

## Not done / open

- Owner's joint human review of all fourteen laboratories: pending, by design.
- Focus ring rendering not observed in a focused browser.
- Page components were written before their tests (no RED for them).
- Two editor-reported missing-import diagnostics on the L6c modules remain unresolved with unknown cause; runtime imports and all tests pass. No native review receipt exists (native tooling was unavailable).
- Open design question for the owner: capital, goal and prizes show a leading "+" because the project formats every DOP amount as signed.
- Seeded laboratories keep their raw ids as names and share one creation timestamp, so their list order differs from the original order.
- Superseded prototype pages `CatalogPage` and `ReferenceLabPage` remain in the tree, unrouted.
- Nothing was pushed, no PR created, normal user data and the user's preview ports untouched.
