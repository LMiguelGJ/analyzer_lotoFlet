# Predicción cronológica Chance Express (chance-rank-v1) — ODD

## Objetivo y autorización
Ejecutar tal cual el plan aprobado `.pi/plans/prediccion-cronologica-chance-express.md` (aprobación explícita del usuario: "ejecuta el plan tal cual usa odd siempre"). Estudio sin dinero: rankings 00–99 causales, Top-25 del primer puesto al siguiente sorteo consecutivo como métrica principal; secundarios, controles y fase supervisada incluidos.

## Restricciones
Sin instalaciones, commits, push ni PR. Preservar historial, `rng_audit/`, `strategy_tests/`, `lagacy_loto/`, notebook, reportes previos y eliminación ajena `lottery-predictability-monte-carlo`. Un escritor por vez; revisores de solo lectura. Código/tests en inglés; ODD e informes en español. Test-first (RED/GREEN observado). No cambiar criterios, grillas ni semillas al ver resultados. STR-13 sigue histórico y bloqueado.

## Tareas
- [x] CR-1 — Protocolo congelado, carga validada, cronología canónica, elegibilidad y fixtures de calidad.
- [x] CR-2 — Features y modelos interpretables causales (grilla cerrada, desempates, ablaciones).
- [x] CR-3 — Replay y validación anidada (folds externos/internos, horizontes actualizado/congelado, barreras antifuga).
- [x] CR-4 — Métricas, inferencia (bootstrap por bloques de días, Holm) y controles (sanos, señales, nulo de orden).
- [ ] CR-5 — Artefactos, CLI (`validate`, `smoke`, `run`, `report`, `inspect`) y reporte.
- [ ] CR-6 — Ejecución fase interpretable y verificación independiente.
- [CANCELADO] CR-7 — Modelos supervisados: decisión explícita del usuario de no ejecutarlos (ver D15). No es un bloqueo técnico.
- [x] CR-8 — Síntesis final de la fase interpretable. `reports/chance_rank_v1/sintesis_cr8.md`. Conclusión: 14/16 sin mejora, 1 (Ensemble) señal exploratoria sin pasar el criterio práctico (p_adj=0,438), 3 N/A por CR-7 cancelada. Controles de señal plantada 6/6 detectados con +7 a +7,7pp, ~20x más grande que la señal del Ensemble en datos reales.

## Evidencia de preservación inicial (2026-09-27)
- Historial: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`
- `reports/strategy_tests.md`: `d59aeef80944e4c888ffc5c996f50a4906709103c1d717c8299ad3f2e7c10e89`
- `reports/strategy_tests.json`: `028eb3ea2050cbc8e0b0596c6951914f03e1aec1090ace56aef02730cbefc883`
- `reports/e5_healthy_calibration.md`: `d328d148b12b85ae052452647c7f7c93977315884c3d1033ce1d4869a59207e1`
- `reports/e5_healthy_calibration.json`: `5d22cd7f9058ee811c169a32b198e3d035e48811f25a958b0d09fcdc28fa0dd0`
- `reports/strategy_tests_quiniela80.md`: `17692de7dfdba2fce6a54a7991a116b35729360f8499dadf3a59c9b5c915e0bf`
- `reports/strategy_tests_quiniela80.json`: `e5ba61577037b06674f22246788e1d474a3bf53d84bcdfb5958e45930e4a2b7b`
- `reports/rng_audit.md`: `f881efd855d0c6df414e99c07b5b2456f97593f5d69ad13a1e775fd0ff921ce1`
- `reports/rng_audit.json`: `9cefb9911017134da76ad08fb4ae3375f18638bd11cb9a4bf389419840114535`

## Entorno
Python 3.14.3, NumPy 2.4.4, SciPy 1.17.1, scikit-learn 1.9.0 (ya instalado; no se instaló nada), Ruff 0.16.7, 16 CPU, ~10 GB RAM libre, 92 GB disco libre.

## Hallazgos de calidad (solo estructura, sin métricas predictivas)
- 105.426 filas, todas con `hora`, cinco `numeros` de dos dígitos y `source_url`; 0 timestamps repetidos, 0 conflictos, 0 valores inválidos, 0 días con dos fuentes.
- Fuentes: `premios.do` hasta 2026-04-24 (76.896), `loteka.com.do` desde 2026-04-25 (28.530); cuatro fechas vacías (2025-04-18, 2025-12-25, 2026-01-01, 2026-04-03).
- Pasos entre filas del mismo día: 95.818 de 5 min, **9.019 de 10 min** (~16 por día), y 25 mayores. Día típico 187 filas 05:05–21:55. Según el plan (predecesor exactamente 5 min antes), esos ~9.000 targets tras saltos de 10 min quedan fuera del principal y entran al análisis secundario "siguiente registro disponible". No se aplica el plan de otro modo aunque el salto de 10 min parezca programado; se reporta como limitación.

## Decisiones de ejecución no fijadas literalmente por el plan
Registradas el 2026-09-27 antes de calcular cualquier métrica predictiva real.
- D1 Día observado = fecha con ≥1 fila (566). Folds externos usan índices de estos días, como dice el plan.
- D2 Segmento = cadena de filas del mismo día con pasos de 5 min. Target elegible principal = fila con predecesor en su segmento. Warmup 2.000 filas: filas con índice < 2000 no se evalúan (irrelevante para folds, que empiezan después).
- D3 Desempate de ranking: `tie = permutación de 0..99` derivada de SHA-256(`chance-rank-v1/tie`); orden por (-score, tie[v]). Rango del ganador = #{score mayor} + #{score igual con tie menor}.
- D4 Semillas: entero = primeros 8 bytes big-endian de SHA-256(etiqueta), usado en `numpy.random.Generator(PCG64)`.
- D5 Categorías usan λ ∈ {100, 1000} (el plan no fijó λ en esa fila; se aplica la misma grilla que las demás familias condicionales).
- D6 Supervisados: se entrena con los min(ventana, disponibles) targets elegibles previos; fallback marginal solo si hay < 2.000 disponibles.
- D7 Criterio práctico "positivo en ≥70% de folds": se exige contra ambos baselines por separado (uniforme y reciente500), contando folds externos con ≥500 targets.
- D9 Bootstrap: generador nuevo por contraste con la misma etiqueta (`chance-rank-v1/inference` para bloques de 7 días; `.../L1` y `.../L14` para sensibilidad), de modo que todos los contrastes usan los mismos remuestreos de días (pareados).
- D10 Clasificación por sistema (Top-25 H1 primer puesto): **consistente histórico** = criterio práctico completo (Δ≥0,01 y Holm<0,01 contra uniforme y contra reciente500, y ≥70% de folds con ≥500 targets positivos contra cada uno); **señal exploratoria** = Δ>0 contra ambos con p cruda unilateral <0,05 en ambos, sin criterio completo; **inconcluso** = no señal y límite superior IC99% contra uniforme ≥0,01; **sin mejora detectada** = límite superior IC99% contra uniforme <0,01. Bandera **inestable** si con bloques de 1 o 14 días cambia el signo de Δ o la decisión Holm. Confirmación prospectiva: imposible con este JSON.
- D11 Control de cambio de distribución: familia relevante = sistema seleccionado internamente entre configuraciones `decay` ∪ `freq_recent` ("EWMA/reciente" del plan). Mapeo del resto: repeat→transition, carry→carry, hour→time, streak→category.
- D12 Ablaciones: 17 (12 notebook + 5 ensemble); CR-2 informó 20 por error de conteo. Las variantes notebook-no_recent son idénticas entre ventanas; se conservan por id.
- D13 (pre-resultados, CR-5b) Bootstrap degenerado con n>0: p=1, IC=(Δ,Δ), bandera `degenerate`; no N/A. Jaccard de listas Top-25 entre sistemas se omite ("skipped: memory budget", pico medido ~6,5 GB > 4 GB del plan); el acuerdo entre sistemas se reporta con correlación φ de aciertos. Deduplicación de inventario solo informativa (no elimina candidatos).
- D15 (2026-09-28) El usuario decidió explícitamente cancelar CR-7 (fase supervisada) tras conocer el resultado preliminar de CR-6 (14/16 sistemas sin mejora, 1 señal exploratoria no confirmada) y el hallazgo cerrado de Quiniela80 (retorno real <1 en las 4 selecciones, sin ventaja posible bajo el pago 80/8/4/2/1). Razón declarada: el coste (~40 h estimadas para la grilla completa) no se justifica dado que la pregunta práctica del usuario ya quedó respondida. `logistic`, `tree` y `select_all` quedan N/A permanente en la síntesis, etiquetados "fuera de alcance por decisión del usuario", nunca "bloqueado" ni "sin mejora detectada".
- D16 (2026-09-28) Incidente operativo: dos relanzamientos completos de CR-6 por invalidación del checkpoint. (1) El fix de exportación por memoria tocó código y cambió `code_hash`. (2) El fix de checkpoint por fit de CR-7 tocó `pipeline.py`/`supervised.py` y volvió a cambiar `code_hash`, invalidando CR-6 aunque ese cambio no afectaba su lógica. Se identificó que el candado de identidad hashea el paquete completo sin distinguir qué pasos dependen de qué archivos (hallazgo F3 señalado por el usuario); no se corrigió bajo presión de tiempo para no debilitar la protección real que ya evitó dos reusos indebidos. Decisión operativa: no tocar ningún archivo de `chance_rank` mientras CR-6 corre, dado que CR-7 queda cancelado. Además, los lanzamientos previos por `nohup`/`disown` desde bash muríeron ambos en simultáneo tras ~41 minutos sin causa identificada (probable reciclado de la sesión de shell); se relanzó con un proceso nativo de Windows totalmente independiente (`DETACHED_PROCESS`).
- D17 (2026-09-28) El usuario decidió reducir los controles de 70 a 20 por presión de tiempo, tras ver el resultado preliminar (Ensemble = señal exploratoria). Reparto elegido: 10 sanos (001-010, ya calculados), 6 de señal fuerte q=.10 × 2 semillas en los 3 tipos con mapeo directo a familias ya evaluadas (repeat→transition, carry→carry, hour→time), 4 de orden mezclado (001-004). Se excluyen por completo `shift` y `streak`, y la intensidad débil q=.02. Consecuencia explícita: la etiqueta final del Ensemble (y de cualquier sistema) se reporta con "calibración parcial (10/20 sanos, cobertura reducida de tipos de señal, sin q=.02)", nunca como el cierre completo de 70 controles que prometía el plan original. No se cambió ningún criterio estadístico (Holm, umbrales, semillas); solo se redujo la cantidad de evidencia de calibración disponible.
- D8 Refit supervisado en trozos de 7 días observados alineados a la grilla de bloques internos (día 96 + 7k); predicciones causales por trozo se reutilizan entre folds porque dependen solo del prefijo.

## Evidencia de ejecución

### CR-1 (escritor: subagente gentle-ai-worker)
- RED: 2 errores de colección (`chance_rank.protocol`/`chance_rank.data` inexistentes). GREEN: 30 tests. Ruff limpio. Coordinador reejecutó: 30 passed, Ruff limpio, SHA historial intacto.
- Grilla congelada: 93 configuraciones interpretables + 14 supervisadas = 107; mix 45.
- Desviación detectada por coordinador: `load_history` defaulteaba `expected_sha=None`; corregido en CR-2 con RED ("DID NOT RAISE") y GREEN.
- Verificación independiente CR-1 lanzada en segundo plano (gentle-ai-verify, tarea `mujgx422-m-nb5i`).

### CR-2 (escritor: subagente gentle-ai-worker)
- Archivos: `ranking.py`, `features.py`, `models.py`, tests `test_ranking.py`, `test_models.py`; fix `data.py`.
- RED observado para `ranking.py` (módulo ausente) y el fix de SHA. **Desviación ODD: `features.py`/`models.py` se escribieron junto con sus tests, sin RED previo observado.** Mitigación obligatoria: oráculo independiente de fuerza bruta (bucles lentos desde las fórmulas del plan) para todas las familias antes de cerrar CR-2.
- GREEN: 68 tests; Ruff limpio. Barrido de causalidad: 93 configs + 20 ablaciones, posiciones 0 y 3, futuro alterado sin cambiar filas ≤ t0.
- Tiempo (sintético uniforme, calendario real, sin métricas): 93 configs pos1 = 47,7 s; pico ~3,9 GB por posición. Regla operativa: una caché de posición a la vez.

### CR-3 (escritor: subagente gentle-ai-worker)
- RED observado: 3 errores de colección (módulos ausentes). GREEN: 106 tests; Ruff limpio.
- Bug real hallado en GREEN: `np.savez_compressed` añadía `.npz` al temporal y rompía el reemplazo atómico; corregido con file object.
- Target "any" se calcula con clave entera exacta = suma de 2×rango medio de las 5 posiciones (transformación monótona de la media de percentiles del plan, sin ruido de coma flotante).
- Test de fuga: alterar días ≥ inicio de fold no cambia la selección de ese fold (historia sintética 260 días × 12 filas).
- Tiempo pos1 con 93 configs + 17 ablaciones, sintético con calendario real: 109,9 s, pico ~4,05 GB, 41 MB en disco.

### Verificación independiente CR-1 (gentle-ai-verify `mujgx422-m-nb5i`)
- Re-derivación desde JSON crudo: 0 discrepancias fila a fila (nums, day, slot, hour, weekday, day_pos, source, eligible, segment); 95.818 elegibles, 9.608 segmentos. Causalidad de elegibilidad/segmento: PASS. Grilla 93+14=107, mix 45, semillas y permutaciones: PASS.
- Hallazgos corregidos después (ver ronda de fix): `protocol_hash` no cubría etiquetas de semilla, presupuesto, ablaciones, ajustes supervisados ni decisiones; regex con `.match` aceptaba `\n` final; registros no-dict daban `AttributeError`; claves de fecha no ISO aceptadas; docstring de segmento incorrecto.

### CR-4 (escritor: subagente gentle-ai-worker, sesión interrumpida y reanudada)
- RED: 3 errores de colección. GREEN: 158 tests; Ruff limpio.
- **Bug hallado por el coordinador en revisión:** `waits()` registraba la primera fila objetivo de cada segmento como espera censurada de 1 ignorando su acierto (un test estaba mal escrito y el worker ajustó el código a ese test). Habría sesgado Kaplan-Meier.

### Ronda de fix (gentle-ai-worker)
- `waits`: RED 3 fallas → GREEN; semántica: el hueco de máscara o cambio de segmento cierra el spell abierto como censurado y la fila actual cuenta normalmente.
- Protocolo: RED 14 → GREEN; nuevo `protocol_hash` = `ed329fe9a50e2fa1b4e5879b1d6b39b41febf5aaba23e548068be689a43572b4` (antes de cualquier ejecución real).
- `data.py`: RED 6 → GREEN (fullmatch, DataError para registros inválidos, fecha ISO estricta).
- Coordinador: `chance_rank strategy_tests rng_audit` 231 passed; Ruff limpio; SHA historial intacto.
- Riesgo residual: `models.py` mantiene su propia lista de miembros del ensemble; equivalente a `protocol.ENSEMBLE_MEMBERS` (test de igualdad pendiente en CR-5).

### CR-5a (pipeline núcleo)
- RED (colección + 4 fallas reales) → GREEN 191. 16 sistemas × 2 baselines = 32 contrastes fijos; supervisados/select_all N/A con p=1 en Holm; `recent_decay` auxiliar (D11). Entrega parcial declarada por el worker.
- Tiempo por stream de control (sintético, calendario real, 10.000 réplicas): 77,5 s, pico 3,87 GB.

### CR-5b (pipeline completo)
- `inference.contrast` degenerado: RED 5 → GREEN. Secundarios completos, orquestación `run_interpretable` con 15 pasos, checkpoints, `status.json`, log JSONL, chequeo de disco y hash.
- **Desviación ODD:** tests de `analyze_secondary`/`run_interpretable` escritos junto con la implementación (sin RED previo). Mitigación: verificación independiente en CR-6 recalcula métricas desde artefactos sin llamar al motor.
- GREEN 204 (255 con suites previas); Ruff limpio. La estimación inicial de ~16 min para store+primario+secundario resultó demasiado optimista y no debe usarse como presupuesto.

### CR-6 — preflight y bloqueo de presupuesto
- Auditoría independiente encontró fuga de resultado en predicciones (ranking100 + winner_rank permitían reconstruir el valor real), Holm de controles reducido y reanudación sin identidad completa. Fix test-first: resultado y rangos derivados se separaron en results_*.npz; familia primaria fija de 32, señales de 5 aparte; checkpoint vinculado a código/config/folds/réplicas. 298 tests tras el fix.
- Días con dos fuentes corregidos en inferencia, ranking exacto en reinicio por fuente, límite de 7200 s y checkpoints por posición. 311 tests pasaron, 1 benchmark optativo omitido.
- Benchmark sintético completo con calendario real y números aleatorios, 110 entradas × cinco puestos + any: **se detuvo a 902,5 s al superar 4 GiB (pico 4,023 GiB)**; no completó ni produjo métricas reales. 4,397 GiB temporales eliminados. Esto bloquea la corrida real bajo el presupuesto vigente. No ejecutar más trabajos largos sin consultar al usuario.

### CR-6 — desbloqueo de memoria
- Causa: acumulador `any` en `np.memmap` (~2,3 GB) cuyas páginas tocadas cuentan como RSS en Windows. Reemplazado por archivo binario con lectura/escritura por configuración (`_AccumulatorFile`); Brier por identidad algebraica sin matriz one-hot.
- Equivalencia: 5.000 filas, 110 entradas, cinco puestos + any, bit-idéntico a copia congelada de la implementación previa (Brier ≤1e-6). RED observado rompiendo el offset.
- Medido (sintético): 20.000 filas store completo 391 s y 0,562 GiB; 105.426 filas una posición 416,7 s y **1,884 GiB** (antes 3,669). Extrapolación store completo ~2,96 GiB (estimación, no observada).
- Coordinador: 316 passed, 1 skipped; Ruff limpio; SHA historial intacto.

### Oráculo CR-2 y corrección
- Referencia independiente con bucles: 93 configs + 17 ablaciones × 5 puestos, diferencias numéricas ≤1e-12; ranking y causalidad PASS. Encontró 6 configs estructuralmente equivalentes (93→87 rankings distintos), y empates matemáticos de mezclas separados por 1 ulp que podían cambiar Top25.
- Writer corrigió con claves enteras exactas para mix/notebook/ensemble/ablaciones, usadas también en store, frozen, any y export; invalidó stores heredados. RED observado; coordinador verificó 282 tests (incluye suites previas), Ruff limpio. Probabilidades condicionales conservan float: empate exacto no demostrado, riesgo residual declarado.
