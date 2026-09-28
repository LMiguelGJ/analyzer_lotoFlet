# Plan: Simulador de estrategias para la Quiniela Extraordinaria 80/8/4/2/1

> Created by `plan-mode-trae` skill — Plan Mode of Trae IDE, adapted to Pi.
> Path: this file · Language: español · Created: 2026-09-28

## Summary

Crear en la raíz del repo un simulador (`quiniela_sim.py`) que es la versión mejorada y honesta de `lagacy_loto/`. Compara cuatro formas de jugar la Quiniela Extraordinaria 80/8/4/2/1 con capital RD$2.000 y meta RD$2.800: tu jugada real, un control al azar, tu escalera adaptada al pago 80 y la apuesta audaz. Lo hace sobre los 105.426 sorteos reales y sobre 20.000 sesiones aleatorias, midiendo probabilidad de meta, de quiebre, pérdida esperada, volumen apostado y duración. No predice números ni recomienda jugar.

## Current State Analysis

- **Proyecto**: Python 3.14, NumPy 2.4, pytest y Ruff disponibles; sin instalaciones nuevas. El repo tiene 128 renombres preparados hacia `repo_ref/` (reorganización ajena en curso, no se toca) y la eliminación ajena `lottery-predictability-monte-carlo`.
- **Legado** (`lagacy_loto/`, protegido, solo lectura):
  - `MarkovPY.py`: `MarkovPredictor(order)` con `update`, `predict_global`, `predict_with_context` (back-off k=order..1) y `predict_combined` (`weighted` 0,7 / `conservative` / `aggressive`). El bloque principal decide "Combinada" por mayoría de los 3 métodos, con desempate por probabilidad promedio.
  - `main_runner.py`: corre órdenes 1..9, junta 3 votos por orden (Global, Contexto, Combinada) y el "TOTAL FINAL" suma 27 votos Par vs Impar. Reescribe el fuente con regex y usa un subproceso por orden.
  - `simulador_loteria.py`: escalera de 10 rondas cubriendo 50 números, pago 70 solo al 1.º; tu jugada real era 50 fijos.
  - `scrapy.py`: solo guarda el 1.º número, sin fecha.
- **Código probado reutilizable** (`repo_ref/strategy_tests/rules.py`, solo importar):
  - `QUINIELA80 = PrizeProfile("quiniela80", (80, 8, 4, 2, 1))`.
  - `payout_matrix(nums, mode, profile)` → (N,100), modos `all`/`best`.
  - `expected_return` → 0,95 (all) / 0,9474 (best).
  - `first_prize_ladder(QUINIELA80)` → `(1, 2, 6, 16, 42, 112, 299, 797, 2126, 5669)` pesos por número.
- **Fórmula audaz ya validada** (`repo_ref/strategy_tests/experiments.py::_stake`): `min(banca, ceil((meta − banca)/(premio1 − 1)))`. No se importa `experiments.py` porque arrastra `rng_audit` y SciPy; se replica la fórmula y se testea.
- **Datos**: `repo_ref/chance_rank/data.py::load_history(path)` valida el SHA `d1c0e9ec…9711` y devuelve `History` con `nums` (105426, 5) int64 en orden cronológico; carga en ~1,3 s.
- **Convenciones**: código y tests en inglés, informes en español, tests con `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest … -p no:cacheprovider`, Ruff limpio, test-first con RED/GREEN observado.

## Proposed Changes

### Archivo 1 — `quiniela_sim.py` (nuevo, raíz)

- **What**: motor + CLI + generador de informe, en un solo módulo.
- **Why**: el pedido es una herramienta única en la raíz que reemplace el flujo de `lagacy_loto/` (scraper sin fechas + Markov por subprocesos + simulador manual) por uno reproducible sobre el historial validado.
- **How**:
  1. **Imports**: agregar `repo_ref` a `sys.path` y usar `chance_rank.data.load_history` y `strategy_tests.rules` (`QUINIELA80`, `payout_matrix`, `first_prize_ladder`, `expected_return`).
  2. **Constantes**:
     - `CAPITAL=2000`, `GOAL=2800`, `NUMBERS=50`, `MC_SESSIONS=20_000`, `SEED=20260928`.
     - `LADDER80 = first_prize_ladder(QUINIELA80)`, `BOLD_DIVISOR = QUINIELA80.prizes[0] − 1` (79).
     - `EVENS`/`ODDS` como máscaras booleanas de 100.
  3. **Port fiel del Markov** (`LegacyMarkov`):
     - Misma lógica, nombres de estado `'Par'`/`'Impar'`, mismo orden de claves de diccionario para empates (`max` sobre `{'Par','Impar'}` elige `'Par'` en empate, igual que el original).
     - `predict_combined(method)` con los 3 métodos.
     - `combined_vote()` replica la "Combinada" del bloque principal: mayoría de weighted/conservative/aggressive; en empate, mayor probabilidad promedio de Par, y si esa no es mayor, Impar.
  4. **`consensus_parity(first_numbers) -> np.ndarray[int8]`** (0=par, 1=impar, uno por sorteo):
     - Nueve instancias `LegacyMarkov(order=1..9)`.
     - Para cada sorteo t: votar Global, Contexto y Combinada en cada orden (27 votos), elegir la mayoría y luego `update` con el 1.º número real de t.
     - Causal por construcción. Arranca sin historia: el primer sorteo vota "Par" por los empates del original.
  5. **Selecciones** (máscara (N,100) o índice de número):
     - `parity`: evens u odds según `consensus_parity` sobre `nums[:,0]`.
     - `random50`: 50 números distintos por sorteo con `default_rng(SEED+1)`.
     - `bold_number`: un número uniforme por sorteo con `default_rng(SEED+2)`.
  6. **Pagos por sorteo, en pesos por peso apostado a cada número**:
     - `cover_pay[t] = (payout_matrix(nums, mode, QUINIELA80)[t] * mask[t]).sum()`.
     - `single_pay[t] = pm[t, number_t]`.
     - Se calculan para `mode ∈ {all, best}`.
  7. **Estrategias** (`step(state, balance, t) -> (stake_total, paid, new_state)` o equivalente vectorizable):
     - `flat` (tu jugada real y el control):
       - Apuesta `NUMBERS×1 = 50`.
       - Quiebre si `balance < 50` antes de apostar.
       - `balance += cover_pay − 50`.
     - `ladder`:
       - Ronda `r` apuesta `NUMBERS×LADDER80[r]`; quiebre si `balance` no alcanza.
       - `balance += LADDER80[r]×cover_pay − 50×LADDER80[r]`.
       - Si el 1.º número real está cubierto, `r=0`; si no, `r+=1`; tras perder la ronda 10, `r=0`.
       - Con RD$2.000 solo se financian 4 rondas (50+100+300+800).
     - `bold`:
       - `stake = min(balance, ceil((goal−balance)/79))` a un solo número.
       - `balance += stake×single_pay − stake`.
       - Quiebre cuando `balance <= 0`.
     - Meta: `balance ≥ goal` después del sorteo.
  8. **Sesiones sobre datos reales** (`replay_back_to_back`):
     - Cada sesión empieza en el sorteo siguiente a donde terminó la anterior y cruza días.
     - Registra por sesión: `reached`, `ruined`, `steps`, `wagered`, `paid`, `final_balance`.
     - La sesión final sin terminar se cuenta como `inconclusive` y queda fuera de las tasas.
  9. **Montecarlo** (`simulate`), vectorizado sobre `MC_SESSIONS`:
     - En cada paso se generan 5 posiciones uniformes 0–99 independientes (repeticiones permitidas).
     - Cobertura fija `EVENS` para flat y ladder, número fijo 0 para bold. Con sorteos uniformes cualquier elección rinde igual, así que se testea la simetría.
     - Pagos `all`/`best` calculados como en `payout_matrix`.
     - Semillas fijas por (estrategia, modo).
     - Tope de seguridad de 2.000.000 pasos que lanza un error si se alcanza.
     - Filas MC: `flat` (vale para tu jugada y el control), `ladder`, `bold`.
  10. **Métricas** (`summarize`), por (estrategia, fuente real/MC, modo):
      - `sessions`;
      - `p_goal` con IC Wilson 95% (función local);
      - `p_ruin`;
      - `mean_net` (saldo final − capital);
      - `mean_wagered`;
      - `return_per_peso` (pagado/apostado);
      - `median_steps` y `p90_steps`;
      - `inconclusive` (solo datos reales).
  11. **CLI** (`main(argv=None)`, argparse):
      - Opciones: `--capital` (2000), `--meta` (2800), `--mc-sessions` (20000), `--report RUTA` (opcional), `--input` (default `chance_express_history.json`).
      - Validación: `capital > 0` y `meta > capital`, si no exit 2.
      - Imprime en consola la tabla en español, en modo `all`.
      - Con `--report` escribe el Markdown.
  12. **Informe en español** (`write_report`), generado solo desde las métricas calculadas:
      1. Qué se simuló y advertencias: retrospectivo, reglas de Rapidita no verificadas, no es recomendación.
      2. Tabla principal (modo all): estrategias × real/MC con las métricas.
      3. Tabla de sensibilidad (modo best).
      4. Glosario de cada columna.
      5. Lectura de resultados con los números calculados, sin frases fijas que afirmen resultados.
      6. Supuestos [A1]–[T2].

### Archivo 2 — `test_quiniela_sim.py` (nuevo, raíz; se escribe primero, RED antes de implementar)

- **What/Why**: probar fidelidad al legado, reglas de cada estrategia y reproducibilidad.
- **How**, tests:
  1. **Fidelidad Markov**: secuencia aleatoria de 400 números. Para órdenes 1..9 y varios prefijos, `LegacyMarkov` da los mismos `predict_global`, `predict_with_context` y `predict_combined` (3 métodos) que `MarkovPredictor` importado por ruta desde `lagacy_loto/MarkovPY.py`, en modo solo lectura.
  2. **Consenso**:
     - Replica el conteo de 27 votos de `main_runner` usando las instancias legado sobre prefijos.
     - Es causal: alterar números futuros no cambia elecciones previas.
     - El primer sorteo vota "Par".
  3. **Pagos** en filas hechas a mano: cobertura de pares, números repetidos en modo `all` vs `best`, pago de número único en posiciones 2–5.
  4. **Flat**: saldos exactos en una secuencia a mano; quiebre con saldo < 50.
  5. **Ladder**: progresión 1, 2, 6, 16; reinicio al cubrir el 1.º; quiebre al no poder pagar la ronda 5 con 2.000.
  6. **Bold**: `ceil((meta−banca)/79)`, apuesta todo si no alcanza, meta y quiebre.
  7. **Sesiones back-to-back**: sin solapamiento; la última inconclusa queda excluida.
  8. **Montecarlo**:
     - Determinista con semilla.
     - Con 2.000 sesiones, `return_per_peso` de flat ≈ 0,95 (all) y ≈ 0,947 (best) con tolerancia 0,01.
     - Simetría: cubrir impares da la misma distribución que cubrir pares con la misma semilla de sorteos.
  9. **CLI**: `main([...])` imprime la tabla; `--report` escribe un archivo con las 6 secciones; argumentos inválidos → exit 2.
  10. **Datos reales**: `load_history` carga 105.426 sorteos y el SHA del historial no cambia.

### Archivo 3 — `informe_quiniela_sim.md` (generado, raíz)

- **What**: salida de `py -B quiniela_sim.py --capital 2000 --meta 2800 --report informe_quiniela_sim.md`. No se escribe a mano.

## Assumptions & Decisions

Asunciones del usuario:

- [A1]–[T2] tal como se confirmaron: Quiniela 80/8/4/2/1; tu jugada = 50 fijos; escalera 80; audaz; control al azar; sesión termina en meta o quiebre; modo `all` principal y `best` como sensibilidad; RD$2.000 → RD$2.800; historial real back-to-back; 20.000 sesiones MC; informe + CLI; archivos en la raíz; no tocar legado, historial, `repo_ref/` ni la reorganización pendiente.

Decisiones de implementación (no-default):

- **Escalera**: "ganar" una ronda = el 1.º número está cubierto, igual que el legado; las posiciones 2–5 suman al saldo pero no reinician. Tras perder la ronda 10 vuelve a la 1 (con 2.000 no se alcanza).
- **Markov**: arranca sin historia previa en el primer sorteo del historial (2025-03-05). `loteka_numbers.json` del legado no se usa porque no tiene fechas y no se puede alinear. Diferencia declarada en el informe.
- **Control al azar**: 50 números nuevos por sorteo, semilla fija.
- **Montecarlo**: cobertura fija (pares, número 0), justificado por simetría y verificado por test.
- **Unidades**: pesos enteros; sin comisiones ni impuestos.
- **Imports**: solo de `repo_ref/strategy_tests/rules.py` y `repo_ref/chance_rank/data.py` vía `sys.path`; no se importa `experiments.py`.
- **Ejecución**: una sola unidad de trabajo con lista TODO; test-first con RED/GREEN observado; sin commit ni push.
- **Presupuesto**: port de Markov sobre 105k sorteos estimado en segundos a pocos minutos (sin medir todavía); MC de flat es la parte más larga. Si una corrida supera 10 minutos, se informa antes de optimizar.

## Verification

- [ ] RED observado: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest test_quiniela_sim.py -q -p no:cacheprovider` falla por módulo ausente antes de implementar.
- [ ] GREEN: el mismo comando pasa completo.
- [ ] Lint: `py -B -m ruff check quiniela_sim.py test_quiniela_sim.py` sin hallazgos.
- [ ] Corrida real: `py -B quiniela_sim.py --capital 2000 --meta 2800 --report informe_quiniela_sim.md` termina e imprime la tabla con 4 estrategias reales + 3 MC.
- [ ] Sanidad: `return_per_peso` MC flat ≈ 0,95 (all) y ≈ 0,947 (best).
- [ ] Preservación: `sha256sum chance_express_history.json` = `d1c0e9ec…9711`; `git status --short` muestra solo los 3 archivos nuevos además de los renombres y la eliminación ajena ya existentes; `lagacy_loto/` y `repo_ref/` sin cambios.
- [ ] Criterio de aceptación: el informe responde, para cada estrategia, probabilidad de meta, de quiebre, ganancia/pérdida promedio, total apostado y duración, con advertencias visibles.

## Out of Scope

- App Flet o interfaz gráfica (se puede sumar después sobre el mismo motor).
- Predecir números, recomendar estrategias o montos.
- Otras tablas de pago (70/8/4/2/1) y otras familias de selección de chance-rank.
- Verificar reglas oficiales de Rapidita o descargar sus sorteos.
- Modificar `lagacy_loto/`, `repo_ref/`, el historial o la reorganización pendiente; commit, push o PR.
