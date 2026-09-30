# LW15 controlled real-browser acceptance — harness-only

Date: 2026-09-30 (local runtime clock). No application source, tests, config, README, or tracker edited. This is a partial acceptance, **not an LW15 pass**.

## Isolation and ownership

- Baseline `git status --short`: pre-existing modified `.gitignore`, `especificaciones-laboratorio-web.md`, `odd/tasks/laboratorio-web.md`; deleted `lottery-predictability-monte-carlo`; untracked `.vitest/`, `node_modules/`, `pyrightconfig.json`, `webapp/`. Acceptance root was absent. Final status had the same top-level entries (the untracked `webapp/` entry also contains this harness); no pre-existing files cleaned.
- Seed command: `LABORATORIO_DATA_DIR="$(pwd)/webapp/.lw15-live-acceptance/data" PYTHONPATH="$(pwd)/webapp/backend" PYTHONDONTWRITEBYTECODE=1 python -B webapp/.lw15-live-acceptance/seed.py` — passed, catalog-confirmed `2025-09-02 05:10`, actual `Settings.database_path` under isolated data, 25 pending and one prepared running/two-run record. IDs in `seed-manifest.json`. This is **prepared recovery**, not an observed crash.
- `PYTHONDONTWRITEBYTECODE=1 python -B webapp/.lw15-live-acceptance/live_check.py start` — API PID 12272 and Vite PID 9884, ports 18765/15174 free before launch, loopback listeners started. Browser session `lw15accept` used Chrome in-memory profile, PID 17768.
- `PYTHONDONTWRITEBYTECODE=1 python -B webapp/.lw15-live-acceptance/live_check.py stop-api` — graceful stop of API PID 12272, verified lifespan exit and free port. `restart` — PID 8940, same DB. `stop-all` — graceful lifespan exit of PID 8940; Vite PID 9884 terminated **non-gracefully**, only after owned-PID/port metadata check. Browser session closed. Final ports 18765 and 15174 free. No runtime process intentionally retained.
- Logs: `../api-1.log`, `../api-2.log`, `../vite.log`; ownership metadata: `../processes.json`. Stop markers retained; no deletion.

## Observed live outcomes

- `live_check.py snapshot startup-queue '/queue?offset=0&limit=20'` and offset=20: HTTP 200; held total 25, pages 20+5; pending total 0, active null. Abandoned detail HTTP 200: `interrupted`, run 0 `interrupted`, run 1 `not_run`. No automatic execution observed. See JSON snapshots.
- Chrome UI at 800px: drawer reflected 25 held. Next/previous displayed 21–25 / 1–20, respectively. Nested Escape closed only the confirmation, leaving drawer and row; second Escape closed drawer and focused shell `Cola` button. **Focus defect:** after the first Escape, `document.activeElement` was `<body>` rather than the initiating Cancelar button (observed again on reopening); this violates confirmation focus return. No product change made.
- Held cancel via UI: POST `/queue/6f97bb0c442c4a0ba2645eb4733aa3a4/cancel` HTTP 200, row vanished after refresh; transient status paragraph became focus. Held start via UI: POST `/queue/210212be0e034b0098b59728b111d875/start` HTTP 200, briefly observed active row, subsequently completed; detail snapshot shows completed run, 50 bets. Neither duplicate-start race nor active/pending cancellation was observed; **inconclusive**, not passed. No synthetic delay or queue mutation.
- Single-poll observer over ~12 seconds with drawer closed and route change to `/ajustes`: exactly 2 `/api/v1/queue?offset=0&limit=20` requests at 5.015s separation; drawer reopened without extra poll. Detail GET and settings GET were separate. In-flight page action locks across route/drawer were not captured; **inconclusive**.
- After graceful API stop, manual queue retry showed truthful stale connection-loss message (calculation *could* continue); proxy 502. Restart same DB then manual retry removed disconnect warning and showed held 23. No automatic re-send observed, but uncertain-action explicit check/retry was not induced; **inconclusive**.
- Screenshots: `../../../.playwright-cli/page-2026-09-30T09-28-54-369Z.png` (800px) and `../../../.playwright-cli/page-2026-09-30T09-28-55-064Z.png` (1100px), tool-generated. Browser console: two favicon 404s, four queue 502s during intentional backend stop; no other errors observed. See `.playwright-cli/console-2026-09-30T09-28-55-376Z.log`.

## Limitations / next review

- Investigate confirmed nested-dialog Escape focus defect in `QueueDrawer` / `ConfirmDialog`; this harness did not edit them. Verify with real keyboard focus after cancellation Escape, not only jsdom.
- Pending cancellation, active cancellation, retained completed run, duplicate-start eligible race, in-flight route/drawer locks and explicit uncertain-action check/retry remain unproven because real work completed quickly; do not infer pass. No full suites rerun (parent supplied prior 156 backend / 246 frontend passing results, not reproduced here).
- One initial HTTP snapshot command failed due Git Bash conversion of `/experiments/...` argument into `C:/Program Files/Git/...`; retried with `MSYS_NO_PATHCONV=1`, then HTTP 200. No backend issue.
