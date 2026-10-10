# Reconstrucción: Laboratorio de corridas

Plan: `.pi/plans/reconstruccion-corridas.md`. Rama `feat/rebuild-corridas` desde `feat/bossfarmer-design` (`09a15fd`).
Alcance autorizado hasta ahora: **limpieza previa** (borrar de `webapp/` y docs obsoletos lo que no sirve al plan).
`repo_ref/` y `lagacy_loto/` **no se tocan** por decisión del usuario. Sin push, PR ni merge.
Los datos de usuario en `%LOCALAPPDATA%\LaboratorioQuiniela` y las migraciones SQL 1–13 no se tocan.

## Tareas de limpieza

- [ ] C1 — Backend: borrar módulos y tests de perfiles, lotes, cola, agentes, importación por perfiles, simulaciones y configuraciones; recortar `repository.py`, `app.py`, `api/__init__.py`, `settings.py`, `contracts.py`, `session.py` y tests conservados.
- [ ] C2 — Frontend: borrar páginas, componentes, utilidades y fixtures de simulaciones; dejar un esqueleto mínimo que compile.
- [ ] C3 — Documentación y carpetas obsoletas: `webapp/reports/`, docs de funciones retiradas, `README` mínimo.
- [ ] C4 — Verificación independiente de la limpieza y cierre.

Se conserva hasta R1: `domain/backtest.py`, `api/backtests.py`, `storage/backtest_trace.py` y `test_backtest_golden` (patrón numérico de referencia).

## Evidencia

(se completa por tarea)
