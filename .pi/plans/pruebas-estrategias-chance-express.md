# Plan: Pruebas de estrategias de apuesta en Chance Express

> Creado con `plan-mode-trae` · Idioma: español · Fecha: 2026-09-26
> Pendiente de aprobación del usuario.

## Summary

Probar con datos reales las 8 ideas elegidas (6, 2, 1, 12, 21, 26, 27 y 29) sobre
`chance_express_history.json`, con las reglas oficiales de premios (70/8/4/2/1 por peso). Cada
resultado debe ser verificable: tests con casos calculados a mano, un control sano que tiene que dar
~0,85 por peso, un control con trampas sembradas que tiene que ser detectado, parámetros elegidos en
el 60% inicial y evaluados en el 40% final, y corrección por pruebas múltiples.

## Current State Analysis

- **Datos**: `chance_express_history.json` → `sorteos_por_fecha[YYYY-MM-DD] = [{hora, numeros[5],
  source_url}]`. Son 105.426 sorteos en 566 días con datos, unos 187 por día, cada 5 minutos.
  - `premios.do`: 76.896 sorteos, del 2025-03-05 al 2026-04-24.
  - `loteka.com.do`: 28.530 sorteos, del 2026-04-25 al 2026-09-25.
- **Reglas del juego** (dadas por el usuario): el jugador elige un número 00–99. Por cada peso gana
  70 si sale 1º, 8 si sale 2º, 4 si sale 3º, 2 si sale 4º y 1 si sale 5º. Las reglas **no dicen**
  qué pasa si el número sale en más de una posición.
- **Código reutilizable** en `rng_audit/`:
  - `run_audit.load_draws(path)` carga y ordena por fecha y hora. Devuelve `Draws(nums (N,5), day
    ordinal, slot, weekday, month)` y trata los errores de lectura.
  - `lottery_tests._same_day_pairs(d, lag)` arma pares de sorteos del mismo día.
  - `generators.sha256_drbg(template)` produce un control sano sobre la misma línea de tiempo.
  - `run_audit.holm` y `run_audit.bh` hacen la corrección por pruebas múltiples.
  - `run_audit.write_report` sirve de patrón para el reporte en markdown en español más el JSON.
- **Hallazgos previos**: la auditoría RNG (`reports/rng_audit.md`) no encontró sesgo ni memoria. La
  martingala del screenshot (`lagacy_loto/Screenshot-2025-10-26.png`) sube la apuesta con la
  escalera 1, 3, 10, 35, 123, 430, 1505, 5268, 18438, 64533 pesos por número sobre 50 números.
- **Convenciones**: código y comentarios en inglés; reporte y ODD en español. pytest corre con
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. El lint exige `zip(strict=True)`, try/except en lecturas y
  prohíbe variables de loop sin usar. No se instalan dependencias ni se hacen commits.

## Proposed Changes

Paquete nuevo `strategy_tests/`. No se toca `rng_audit/` salvo para importarlo.

### 1 — `strategy_tests/rules.py`
- **Qué**: define la tabla de premios `PRIZES = (70, 8, 4, 2, 1)` y la función
  `payout(nums_row, bet, mode)`, que da lo que se cobra por peso apostado.
  - `mode="all"` paga cada posición donde sale el número. Es la **interpretación principal**.
  - `mode="best"` paga solo la mejor posición.
  - Incluye también `payout_matrix(nums, mode) -> (N,100)`, lo que paga cada número en cada sorteo,
    para simular rápido.
- **Por qué**: todas las pruebas de plata usan exactamente las reglas oficiales.

### 2 — `strategy_tests/test_rules.py` (se escribe primero)
- **Qué**: casos calculados a mano.
  - `payout([5,5,1,2,3], 5, "all") == 78` y con `"best"` da 70.
  - `payout([1,2,3,4,5], 9, "all") == 0`.
  - La esperanza teórica de `"all"` es exactamente 0,85.
  - La racha condicional en una serie fabricada `[0,0,0,1,…]` cuenta los casos correctos.
  - La apuesta audaz con una secuencia determinística llega a la meta en la jugada esperada.
  - La martingala del screenshot reproduce las columnas "Invertido total" y "Ganancia neta".
  - Un sorteo sin datos del día siguiente no forma pares entre días.

### 3 — `strategy_tests/experiments.py`
Cada experimento devuelve dicts `{id, name, p, observed, expected, n, detail}` y, cuando hay plata,
`return_per_peso` con su intervalo de 95%. Ese intervalo se calcula con bootstrap por bloques de días
(2.000 remuestreos, semilla fija).

- **E1 — Mitades tras racha (#1)**. Se mide la probabilidad de que salga "la otra mitad" después de
  N = 1..10 resultados seguidos de la misma mitad en la posición 1.
  - Mitades: par/impar y bajo/alto (00–49 / 50–99). También se mide juntando las 5 posiciones.
  - Solo cuentan rachas dentro del mismo día.
  - Prueba binomial exacta contra 0,5.
- **E2 — Números fríos con umbral (#2)**. Se apuesta a cada número que lleva ≥ X sorteos sin salir 1º,
  con X ∈ {100, 150, 200, 300, 400, 500}.
  - Se miden la tasa de acierto en la posición 1 contra 1% y el retorno por peso con
    `payout_matrix`.
  - Variante: el atraso se cuenta en cualquier posición.
  - El atraso sí cruza días, porque "el número atrasado" no se reinicia a la mañana.
- **E3 — Arrastre entre posiciones (#6)**.
  - P(1º del sorteo t+1 = k-ésimo del sorteo t) para k = 1..5, contra 1%.
  - P(1º de t+1 ∈ los números del sorteo t), contra lo esperado según cuántos números distintos
    tuvo t.
  - Solo dentro del mismo día. Estrategia de plata: jugar el 2º (y aparte, los 5) del sorteo
    anterior.
- **E4 — Dobles (#12)**. Cuando un número sale ≥ 2 veces en un sorteo, se mide si sale 1º (y en
  cualquier posición) en los siguientes 1, 5 y 20 sorteos del mismo día, contra lo esperado.
  Estrategia de plata: jugarlo en los siguientes 5 sorteos.
- **E5 — Entrar tras N fallos virtuales (#21)**. Se mira sin apostar. Tras N = 3..8 resultados
  seguidos de la misma mitad (paridad o alto/bajo) en la posición 1, se cubren los 50 números de la
  mitad contraria. Se simula con:
  - (a) apuesta plana de 1 peso por número.
  - (b) la escalera del screenshot: máximo 10 rondas, reinicio al ganar o al agotar la escalera.
  - Se miden retorno por peso, ganancia total, peor caída de capital, cantidad de escaleras
    perdidas completas y el capital necesario para no quebrar.
- **E6 — Apuesta audaz contra apuesta tímida (#26)**. El objetivo es llegar a la meta.
  - Escenarios: capital 1.000 con meta 2.000, y capital 5.000 con meta 10.000.
  - Tímida: 10 pesos por sorteo a un número fijo (el 00).
  - Audaz: apostar al número la cantidad justa para llegar a la meta si sale 1º, o todo el capital
    si no alcanza.
  - Se simula recorriendo los sorteos reales desde muchos arranques distintos (uno por día, a las
    05:05) y además con Monte Carlo de 20.000 sesiones.
  - Se miden la probabilidad de llegar a la meta y su intervalo de 95%, junto al valor teórico de
    un juego justo (capital/meta = 50%).
- **E7 — Números repetidos en un sorteo (#27)**. Esperanza por peso en `"all"` contra `"best"`:
  teórica (0,85 y el valor exacto de `"best"`) y empírica, con la frecuencia real de números
  repetidos. Se informa cuánto cambia el margen de la casa según la regla.
- **E8 — Cambio de régimen (#29)**. Se parte en `premios.do` y `loteka.com.do`.
  - Chi² de 2 muestras por posición (fuente × número).
  - Tasa de repetidos por fuente.
  - Las 52 pruebas de `rng_audit.lottery_tests.run_all` corridas por separado en cada fuente.
  - E1–E4 recalculados por fuente, para ver si algún resultado depende de la fuente.

### 4 — `strategy_tests/controls.py`
- **Qué**: dos datasets de control con la misma línea de tiempo (plantilla `Draws`).
  - `sano`: `rng_audit.generators.sha256_drbg`.
  - `trampa`: igual, pero con 4 defectos sembrados para probar que los experimentos los detectan:
    1. Tras 5 impares seguidos en el 1º, sale par con 65%. Lo debe detectar E1/E5.
    2. El 1º del sorteo t+1 repite el 2º del sorteo t con 5%. Lo debe detectar E3.
    3. Un número doble sale 1º en el sorteo siguiente con 5%. Lo debe detectar E4.
    4. Un número que lleva ≥ 300 sorteos sin salir 1º sale con 3% en vez de 1%. Lo debe detectar E2.

### 5 — `strategy_tests/run_experiments.py`
- **Qué**: se corre con `py -m strategy_tests.run_experiments [path]`.
  - Carga los datos con `rng_audit.run_audit.load_draws`.
  - Divide por días: el 60% inicial es "entrenamiento" y el 40% final es la "prueba ciega".
  - En el 60% elige el mejor parámetro de E2 (X), E3 (k), E4 (ventana) y E5 (N y mitad) según el
    retorno por peso, y lo evalúa **solo** en el 40%. También reporta la grilla completa.
  - Corre todo sobre Loteka, `sano` y `trampa`.
  - Aplica Holm (α = 0,01) sobre todas las pruebas de cada dataset. FALLA = Holm < 0,01;
    SOSPECHOSA = solo el p crudo < 0,01.
  - Escribe `reports/strategy_tests.md` (en español, lenguaje simple) y
    `reports/strategy_tests.json`.
- **Estructura del reporte**:
  1. Veredicto por idea.
  2. Tabla de plata: retorno por peso con su intervalo contra 0,85.
  3. Detalle por experimento.
  4. Controles.
  5. Limitaciones.

### 6 — `odd/tasks/strategy-tests.md`
- **Qué**: tarea ODD con STR-1…STR-6 y evidencia:
  - STR-1: tests primero.
  - STR-2: `rules` y `controls`.
  - STR-3: experimentos.
  - STR-4: correr el análisis.
  - STR-5: verificar.
  - STR-6: resumen.

## Assumptions & Decisions

- **Regla de repetidos**: la simulación principal usa `"all"`, que paga cada posición y es la lectura
  literal de las 5 categorías. E7 cuantifica la alternativa. Solo Loteka puede confirmar cuál aplica.
- **Posición 1 como eje**: es 70 de los 85 pesos de retorno (82%). Las demás posiciones se miden
  como variante.
- **Rachas, arrastre y dobles** no cruzan días. **El atraso** (E2) sí cruza días.
- **Anti-trampa**: parámetros elegidos en el 60% inicial (≈ 2025-03-05 → 2026-01) y evaluados en el
  40% final. El corte de fuente (2026-04-25) cae dentro de la prueba ciega; E8 lo analiza aparte.
- **Esperado bajo azar justo**: 1% de acierto por posición, 0,5 para mitades, retorno de 0,85 por
  peso. El 0,85 viene de sumar 0,70 + 0,08 + 0,04 + 0,02 + 0,01.
- **Semillas fijas** en controles, bootstrap y Monte Carlo para que todo sea reproducible.
- **Tamaño**: unas 700–800 líneas nuevas, más de 400. Como no hay PR ni commit, se ejecuta en una
  sola pasada. Si más adelante se entrega como PR, conviene partirlo en dos: (1) `rules` + tests +
  controles, y (2) experimentos + reporte.

## Verification

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -m pytest strategy_tests rng_audit -q -p no:cacheprovider`
      pasa, con los valores calculados a mano incluidos.
- [ ] `py -m strategy_tests.run_experiments` termina y escribe `reports/strategy_tests.md` y `.json`.
- [ ] **Control sano**: 0 fallas Holm; retorno por peso con intervalo que contiene 0,85 en E2–E5;
      apuesta audaz y tímida sin ventaja respecto de sus valores teóricos.
- [ ] **Control trampa**: E1/E5, E3, E4 y E2 detectan cada uno su defecto sembrado (Holm < 0,01), y
      E5 muestra retorno > 0,85.
- [ ] El SHA-256 de `chance_express_history.json` es igual antes y después.
- [ ] Diagnósticos LSP sin errores en `strategy_tests/`.

## Out of Scope

- Ideas no elegidas: 3, 4, 5, 7–11, 13–20, 22–25, 28, 30 y 31.
- Web, MCP, redes neuronales y descarga de datos nuevos.
- Modificar `rng_audit/`, el JSON, `lagacy_loto/` o `loteka_numbers.json`.
- Commit, push y PR.
