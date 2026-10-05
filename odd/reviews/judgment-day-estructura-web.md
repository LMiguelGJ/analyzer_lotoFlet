# Judgment Day — whole-web structure (round 1)

- Target: commit `fdab1f3d972014ee55ee436a2d63b3525c2813ef` (clean worktree, frozen).
- Scope: `webapp/frontend/src` (App, components, pages, api client/types) and
  `webapp/backend/laboratorio/api/**` with the domain concepts they expose; product
  intent from `PRODUCT.md` and `DESIGN.md`.
- Judges: `jd-judge-a` (task muvqnzd3-m-1d6c), `jd-judge-b` (task muvqnzd4-n-28n3).
- Skills passed to both judges: impeccable `SKILL.md` and `reference/operate.md`.
- Primary lens: information-architecture integrity (fragmented concepts, parallel
  paths, inconsistent terminology, scattered entry points).

## Confirmed by both judges

| ID | Severity (A / B) | Finding | Evidence |
|---|---|---|---|
| C1 | WARNING / WARNING | "Simulaciones" and "Corridas históricas" answer the same user job (does this strategy survive?) through two routes, two lists, two wizards and two result models; the difference is one parameter (single session vs repeated sessions over the whole history). | `App.tsx:15-36`, `pages/backtests/index.tsx:25-31,128-189`, `api/backtests.py:123` |
| C2 | WARNING / WARNING | One concept, several names: nav label "Experimentos", aria-label "Simulaciones", route `/experimentos`, page title "Simulaciones", tab "Corridas históricas". | `components/Shell.tsx:8,101`, `App.tsx:20` |
| C3 | WARNING / WARNING | Historical runs have no navigation entry; reachable only through an inner tab repeated on list, create and detail screens. | `Shell.tsx:8-13`, `pages/backtests/index.tsx:23-31` |
| C4 | WARNING / WARNING | FAB visibility and destination derived from chained pathname regexes in the Shell; any new route can break it. Each route should declare its primary action. | `Shell.tsx:92-113` |
| C5 | WARNING / CRITICAL | Two unrelated "saved strategy" libraries: `/configurations` (screen "Estrategias") and `/strategies` (only inside the profile batch flow). Strategies saved in one are invisible in the other. | `pages/configurations/index.tsx:63,127-128`, `ProfileBatchPage.tsx:97,209-210`, `api/configurations.py`, `api/strategies.py` |
| C6 | WARNING / CRITICAL | Game rules live in three places with three sources (`/settings/game` in Ajustes, game profiles in Datos, copies in each wizard); the wizard's "Editar reglas" links to `/datos#perfiles` while displaying `catalog.game` edited in Ajustes. | `pages/new-experiment/index.tsx:553-564`, `pages/settings/index.tsx:120-135`, `pages/data/index.tsx:402-403`, `pages/backtests/index.tsx:128-135` |
| C7 | WARNING / WARNING | Three creation wizards for the same task (classic `/nuevo`, profile `/nuevo/perfil`, batch `/nuevo/sesion`) with separate models, validation and endpoints, cross-linked by technical labels. | `App.tsx:50-64`, `ProfileExperimentPage.tsx:168`, `ProfileBatchPage.tsx:371`, `pages/data/index.tsx:238` |
| C8 | WARNING / WARNING | "Usar como base" works only for classic simulations; profile runs show "No disponible como base" and historical runs have no repeat action. | `pages/experiments/index.tsx:100-121`, `pages/backtests/index.tsx:75-78` |
| C9 | SUGGESTION / SUGGESTION | No common result view model: list, detail, comparison and backtest report each re-derive verdict, money and names with per-type ternaries and separate components. | `DetailPage.tsx:233-238,407-410`, `ComparisonPage.tsx:43-48`, `components/BacktestReport.tsx` |
| C10 | WARNING / WARNING | Historical runs carry their own hardcoded systems/staking selects instead of reusing the catalog, `StrategyEditor` and the strategy library. | `pages/backtests/index.tsx:10-16,143-165`, `api/backtests.py:30-64` |

## Suspect (one judge only — not auto-fixed)

| ID | Judge | Severity | Finding | Parent verification |
|---|---|---|---|---|
| S1 | B | WARNING | Mobile app-bar title regex `^/experimentos/[^/]+$` also matches `/experimentos/historicas` and `/experimentos/nueva-historica`, titling them "Resultado". | Verified deterministic at `Shell.tsx:68`. |
| S2 | B | SUGGESTION | Backtest screens use a second hand-built style set; their list has no filter, sort or delete, and the API has no DELETE. | Not verified. |
| S3 | B | WARNING | Five parallel profile request/result versions (v1–v5) remain live write paths with cascading branches in API and UI. | Not verified. |
| S4 | B | WARNING | `api/agent.py` mirrors most `/api/v1` resources under `/api`, a second API surface that can diverge. | Not verified. |
| S5 | B | SUGGESTION | Two import endpoint pairs and two import forms for the same preview → promote flow. | Not verified. |

## Contradictions

- C5 and C6: both judges confirm the finding but disagree on severity (A: WARNING,
  B: CRITICAL). Per the Judgment Day decision gate, a contradiction escalates to an
  explicit human decision. No finding is confirmed as severe by both judges, so no
  correction round was launched.

## Verdict

```yaml
target_identity: fdab1f3d972014ee55ee436a2d63b3525c2813ef
round: 1
confirmed: [C1, C2, C3, C4, C5, C6, C7, C8, C9, C10]
suspect: [S1, S2, S3, S4, S5]
contradictions: [C5-severity, C6-severity]
info: [C9]
fix_work_units: []
scoped_rejudgment: not_run
terminal_state: escalated
skill_resolution: paths-injected
```

JUDGMENT: ESCALATED ⚠️ — awaiting the human decision on the C5/C6 severity
contradictions and on the proposed restructuring plan.
