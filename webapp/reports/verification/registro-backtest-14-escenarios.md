# Registro de verificación — Backtest multi-sesión, 14 escenarios (T4)

Contrato: matriz de aceptación de `odd/tasks/backtest-multisesion.md` y
`docs/resumen_resultados_quiniela.md`.

## Método

- Prueba: `webapp/backend/tests/test_backtest_golden.py` (parametrizada, marcas `golden` y
  `real_data`, una prueba por fila).
- Camino ejercitado: `POST /api/v1/backtests` con `TestClient` sobre la aplicación real
  (`create_app` con las entradas reales y pinneadas: `chance_express_history.json` +
  `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`, hashes verificados). Es decir,
  `api/backtests.py::_selection_rows` → `domain/backtest.py::run_backtest`; no hay una
  implementación paralela en la prueba.
- Juego/condiciones por corrida: 100 números × 5 posiciones, premios 80/8/4/2/1, apuesta
  mínima 1, capital 2.000, meta 2.800.
- Comparación exacta: `reached_goal`, `completed`, `quiebres` (enteros), `goal_rate` y
  `neto_medio` redondeados a 1 decimal.
- No se ejecutaron los scripts de `repo_ref/simuladores/` (el MD bastó como verdad; no hubo
  divergencias que requirieran verdad adicional).

## Resultados: esperado (MD) vs obtenido

| # | Sistema | k | Apuesta | Esperado (llegaron/completas · meta · quiebres · neto) | Obtenido | Coincide |
|---|---|---|---|---|---|---|
| 1 | transition | 1 | bold | 681/963 · 70,7% · 282 · +10,3 | 681/963 · 70,7% · 282 · +10,3 | ✅ |
| 2 | cold | 1 | bold | 684/974 · 70,2% · 290 · −3,4 | 684/974 · 70,2% · 290 · −3,4 | ✅ |
| 3 | select_interpretable | 1 | bold | 663/946 · 70,1% · 283 · −8,2 | 663/946 · 70,1% · 283 · −8,2 | ✅ |
| 4 | mix | 1 | bold | 676/968 · 69,8% · 292 · −15,6 | 676/968 · 69,8% · 292 · −15,6 | ✅ |
| 5 | ensemble | 5 | bold | 3.226/4.720 · 68,3% · 1.494 · −51,2 | 3.226/4.720 · 68,3% · 1.494 · −51,2 | ✅ |
| 6 | ensemble | 10 | bold | 6.140/9.061 · 67,8% · 2.921 · −56,9 | 6.140/9.061 · 67,8% · 2.921 · −56,9 | ✅ |
| 7 | ensemble | 20 | bold | 10.785/16.086 · 67,0% · 5.301 · −59,2 | 10.785/16.086 · 67,0% · 5.301 · −59,2 | ✅ |
| 8 | cold | 25 | ladder | 677/1.105 · 61,3% · 428 · −162,2 | 677/1.105 · 61,3% · 428 · −162,2 | ✅ |
| 9 | mix | 50 | bold | 12.845/20.605 · 62,3% · 7.760 · −117,0 | 12.845/20.605 · 62,3% · 7.760 · −117,0 | ✅ |
| 10 | transition | 50 | bold | 12.890/20.682 · 62,3% · 7.792 · −116,0 | 12.890/20.682 · 62,3% · 7.792 · −116,0 | ✅ |
| 11 | parity | 50 | bold | 12.698/20.404 · 62,2% · 7.706 · −120,8 | 12.698/20.404 · 62,2% · 7.706 · −120,8 | ✅ |
| 12 | cold | 50 | ladder | 1.429/3.502 · 40,8% · 2.073 · −98,7 | 1.429/3.502 · 40,8% · 2.073 · −98,7 | ✅ |
| 13 | parity | 50 | ladder | 1.368/3.496 · 39,1% · 2.128 · −124,4 | 1.368/3.496 · 39,1% · 2.128 · −124,4 | ✅ |
| 14 | parity | 50 | flat | 13/91 · 14,3% · 78 · −1.572,8 | 13/91 · 14,3% · 78 · −1.572,8 | ✅ |

14/14 coinciden exactamente.

## Chequeos de consistencia de población (valores del reporte)

- `window.bets` = 65.235 en las 14 corridas: cada sorteo con ranking se consume exactamente
  una vez, igual que la población de referencia (65.235 con ranking).
- Cola inconclusa: `incomplete` = 1 en 12 filas y 0 en las filas 9 y 11, donde la sesión
  final cerró justo en meta/quiebre. Está excluida de tasas y promedios (`completed` =
  llegaron + quiebres) y sus apuestas permanecen en `window`.

## Divergencias encontradas

Ninguna. Los 14 escenarios reproducen el MD a la primera ejecución, sin cambios al código de
producto (dominio, motor o API). En particular, quedaron verificadas por resultado:

- consenso de paridad de 27 votos y orden de desempate (filas 11, 13, 14),
- escalera por cobertura (k=25 y k=50, filas 8, 12, 13),
- mapeo de familias de ranking (`select_interpretable`, `mix`, `ensemble`),
- restricción de población de paridad (consenso sobre todo el historial previo, apuestas
  solo en sorteos con ranking),
- liquidación contra las cinco posiciones con números repetidos.

| Divergencia | Causa raíz (archivo:línea) | Corrección |
|---|---|---|
| — | — | — |

## Cambios de esta tarea

- `webapp/backend/tests/test_backtest_golden.py`: nuevas pruebas doradas de las 14 filas.
- `webapp/backend/pyproject.toml`: marca `golden` registrada.
