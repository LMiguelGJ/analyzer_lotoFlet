# Feature: Backtest multi-sesión — reproducir los 14 escenarios del resumen

Contrato de aceptación: `docs/resumen_resultados_quiniela.md` (tabla de 14 filas).
El usuario pidió crear en la plataforma las mismas simulaciones de
`repo_ref/simuladores/` (configurables, sin hardcodear) y que consigan los
mismos resultados; las divergencias son bugs a corregir.

## Semántica de referencia (obligatoria)

- Sesión: capital RD$2.000, meta RD$2.800, SIN límite temporal; termina al
  alcanzar la meta o al no poder financiar la próxima apuesta prescrita (quiebre,
  aunque quede saldo). Reinicio en el siguiente sorteo con ranking disponible.
- Población: 65.235 sorteos con ranking (14 folds, huecos sin apuesta donde la
  sesión continúa). La sesión histórica inconclusa al final se EXCLUYE de tasas y
  promedios de completas.
- Juego: 100 números × 5 posiciones, premios acumulados 80/8/4/2/1 por peso,
  liquidado contra las cinco posiciones (configurable por corrida, nada hardcodeado).
- Selección: top-k del ranking de primera posición (orden de desempate exportado).
  Sistemas: transition, cold, select_interpretable, mix (familia de ranking),
  ensemble, parity (consenso causal de 27 votos sobre datos anteriores).
- Apuestas: plana RD$1/número · escalera de 10 rondas (k=50 arranca 1,2,6,16,42…;
  reinicia con primer premio; secundarios suman sin reiniciar; quiebre si no
  financia la próxima ronda completa) · audaz b = mín(ceil((meta−saldo)/(80−k)),
  piso(saldo/k)) por número, recalculada por sorteo.
- Reporte por escenario: llegaron / completas, meta %, quiebres, neto medio RD$
  (saldo final − 2.000 promediado en completas).

## Matriz de aceptación (las 14 filas del MD)

| # | Sistema | k | Apuesta | Llegaron/Completas | Meta | Quiebres | Neto medio |
|---|---|---|---|---|---|---|---|
| 1 | transition | 1 | bold | 681 / 963 | 70,7% | 282 | +10,3 |
| 2 | cold | 1 | bold | 684 / 974 | 70,2% | 290 | −3,4 |
| 3 | select_interpretable | 1 | bold | 663 / 946 | 70,1% | 283 | −8,2 |
| 4 | mix | 1 | bold | 676 / 968 | 69,8% | 292 | −15,6 |
| 5 | ensemble | 5 | bold | 3.226 / 4.720 | 68,3% | 1.494 | −51,2 |
| 6 | ensemble | 10 | bold | 6.140 / 9.061 | 67,8% | 2.921 | −56,9 |
| 7 | ensemble | 20 | bold | 10.785 / 16.086 | 67,0% | 5.301 | −59,2 |
| 8 | cold | 25 | ladder | 677 / 1.105 | 61,3% | 428 | −162,2 |
| 9 | mix | 50 | bold | 12.845 / 20.605 | 62,3% | 7.760 | −117,0 |
| 10 | transition | 50 | bold | 12.890 / 20.682 | 62,3% | 7.792 | −116,0 |
| 11 | parity | 50 | bold | 12.698 / 20.404 | 62,2% | 7.706 | −120,8 |
| 12 | cold | 50 | ladder | 1.429 / 3.502 | 40,8% | 2.073 | −98,7 |
| 13 | parity | 50 | ladder | 1.368 / 3.496 | 39,1% | 2.128 | −124,4 |
| 14 | parity | 50 | flat | 13 / 91 | 14,3% | 78 | −1.572,8 |

## Hallazgo del scout (capacidad actual)

- Los 14 SÓLO son configurables como UNA sesión (POST /api/v1/experiments).
- Falta el replay histórico multi-sesión con agregados y censura de la cola.
- Fórmulas de apuestas/pagos ya alineadas por inspección (domain/session.py:
  49-80, 145-147); equivalencia de paridad sin verificar (selection.py:45-57).
- Entradas idénticas y pinneadas: chance_express_history.json +
  repo_ref/reports/chance_rank_v1/predictions/pos1.npz (settings.py:21-22,180-188).

## Tasks

- [ ] T1. Dominio: replay multi-sesión con semántica de referencia (sesiones
  encadenadas, quiebre, reinicio en siguiente sorteo con ranking, huecos/folds
  sin reinicio, censura de la cola incompleta, agregados del reporte) + reglas de
  juego por corrida (100/5/80-8-4-2-1 configurables). Tests-first con valores
  dorados del MD (fixtures pequeñas + al menos 2 escenarios completos).
  Superficies: webapp/backend/laboratorio/domain/**, webapp/backend/tests/**.
- [ ] T2. API + persistencia: crear/correr/reportar backtests multi-sesión con
  estrategia configurable (6 sistemas × coberturas × 3 apuestas), pin de hashes,
  validación de payloads. Superficies: webapp/backend/laboratorio/api/**,
  storage/** si hace falta, tests.
- [ ] T3. Frontend: crear «corrida histórica» desde la configuración de
  estrategias (lenguaje claro) y ver la tabla de resultados estilo MD
  (llegaron/completas, meta %, quiebres, neto medio). Superficies:
  webapp/frontend/src/pages/**, components/**, styles/**, tests.
- [ ] T4. Correr los 14 escenarios REALES contra el MD, fila por fila; investigar
  cada divergencia (foco: parity/ties) y corregir hasta coincidir (enteros y 1
  decimal como el MD). Evidencia en webapp/reports/verification/.
- [ ] T5. QA: suite completa frontend+backend, build, revisión nativa, push.

## Verification

Backend: pytest focales + suite completa. Frontend: vitest + tsc + build.
Aceptación: los 14 escenarios reproducen exactamente la tabla del MD.

## Evidencia (commits)

- T1: pendiente
- T2: pendiente
- T3: pendiente
- T4: pendiente
- T5: pendiente
