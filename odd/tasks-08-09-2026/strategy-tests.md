# Pruebas de estrategias de apuesta en Chance Express

## Objective
Medir con datos reales y reglas oficiales (70/8/4/2/1 por peso) si alguna de las 8 ideas elegidas (6, 2, 1, 12, 21, 26, 27, 29) cambia la probabilidad de acierto o el retorno por peso de Chance Express.

## Problem and rationale
La auditoría RNG no encontró sesgo ni memoria en el generador, pero el usuario quiere probar estrategias concretas de apuesta: rachas, números fríos, arrastre entre posiciones, dobles, entrar tras N fallos, apuesta audaz, la regla de números repetidos y el cambio de fuente de datos. Hace falta que cada respuesta sea verificable, no una opinión.

## Scope
- Paquete `strategy_tests/` con reglas de premios, controles, 8 experimentos predeclarados (E1–E8) y un E9 adicional exploratorio aprobado después: condicionar el siguiente sorteo del mismo día por cada valor anterior 00–99.
- Correr todo sobre Loteka, un control sano y un control con 4 trampas sembradas.
- Elegir parámetros en el 60% inicial de los días y evaluarlos en el 40% final; corrección de Holm.
- Escribir `reports/strategy_tests.md` y `reports/strategy_tests.json`.

## Constraints / non-goals
- `chance_express_history.json`, `lagacy_loto/`, `loteka_numbers.json` y `rng_audit/` no se modifican.
- Sin instalar dependencias. Sin commit, push ni PR.
- Los resultados se reportan tal como salen, sin ajustar pruebas. E9 se declara exploratorio y no altera los p-valores, el corte, las semillas ni la aceptación original E1–E8.
- Fuera de alcance: ideas no elegidas, web, MCP y redes neuronales.

## Tasks
- [x] STR-1 — Escribir `strategy_tests/test_rules.py` con casos calculados a mano (test-first). Evidencia: RED antes de la implementación; 15 tests nuevos en verde, incluidos premios 78/70, escalera, rachas sin cruzar días, capital y ventanas solapadas.
- [x] STR-2 — Implementar `strategy_tests/rules.py` y `strategy_tests/controls.py`, y pasar los tests. Evidencia: pago 70/8/4/2/1, control SHA-256 y 4 patrones sembrados.
- [x] STR-3 — Implementar los experimentos E1–E8 en `strategy_tests/experiments.py`. Evidencia: E4 usa inferencia agrupada por día; E2 sin apuestas y 11 tablas 100×100 del segmento menor se excluyen de Holm como N/A.
- [x] STR-4 — Implementar `strategy_tests/run_experiments.py`, correr el análisis y generar el reporte. Evidencia: `py -B -m strategy_tests.run_experiments` produjo `reports/strategy_tests.md` y `.json`; 105.426 sorteos, 566 días, entrenamiento hasta 2026-02-09 y prueba ciega desde 2026-02-10.
- [x] STR-5 — Verificación técnica concluida: 33 tests, Ruff, LSP sin errores/advertencias, 0 rechazos Holm del sano, 4 defectos sembrados detectados y SHA-256 del historial sin cambios. **Resultado del criterio original: NO APROBADO**, porque el IC E5 [0,823736–0,848713] excluye 0,85. Se registra como bloqueo de aceptación STR-13, sin modificar semillas/umbrales a posteriori.
- [x] STR-6 — Resumir los hallazgos para el usuario. Se entregó la síntesis con el criterio E5 incumplido y se aclaró que las ocho estrategias originales se probaron; el usuario pidió ampliar la vista por N y por valor concreto.
- [x] STR-7 — E9 exploratorio para cada X=00–99: 104.860 transiciones válidas, 100 filas y matriz 100×100 descriptiva en JSON, sin p por X ni enlaces entre días. Evidencia test-first: RED por importación ausente, GREEN con 18 tests del módulo, 29 en suite completa; fixtures de X=00/99, días y suma de matriz.
- [x] STR-8 — El reporte regenerado muestra las 40 variantes E1 (N=1–10 × 4 vistas), las 12 E5 (N=3–8 × 2 vistas) y 100 filas E9; conserva el detalle completo y el incumplimiento E5. Evidencia: `py -B -m strategy_tests.run_experiments`, JSON/Markdown consistentes según el escritor.
- [x] STR-9 — Verificación independiente de E9 y reporte: 29 tests, Ruff limpio, SHA del historial igual, 40 filas E1 y 12 E5 en el resumen, 100 filas E9 sin p ni X elegido. Inspección del código confirmó que E9 no cruza días; comprobación aritmética independiente del JSON confirmó matriz 100×100, suma de cada fila, diagonal/repeticiones, tasas y 104.860 transiciones. LSP en tres archivos cambiados: 0 errores/advertencias (23 avisos informativos del corrector ortográfico sobre términos españoles).
- [x] STR-B — El usuario eligió una nueva validación prospectiva; el requisito original E5 sigue incumplido y no se declara aprobado. Protocolo congelado abajo antes de generar resultados nuevos.
- [x] STR-10 — Runner separado `strategy_tests/calibrate_e5.py`, test-first: RED por módulo ausente; GREEN con 4 tests de contrato deterministas (semillas, corte/selección sin fuga, IC inclusivo y umbral). Originales intactos.
- [x] STR-11 — Única ejecución de los 20 controles registrados: **19/20** IC contienen 0,85, por encima del umbral nuevo ≥18/20; solo la semilla `-017` no cubrió. `reports/e5_healthy_calibration.md` y `.json` contienen las 20 filas, política, retorno e IC. Duró 10,52 s; no se sustituyó ningún seed ni se reejecutó para buscar aceptación.
- [x] STR-12 — Verificador independiente: 33 tests, Ruff limpio, SHA del historial y reportes originales intactos; 20 semillas, corte, 12 políticas y bootstrap 2.000 conforme al protocolo; filas JSON/Markdown coherentes, cobertura inclusiva 19/20 con sola excepción `-017`. LSP en los 2 archivos nuevos: 0 errores/advertencias, 3 sugerencias ortográficas de texto español. Sin reejecutar controles, no se probó externamente que la corrida ocurriera una sola vez ni se reprodujeron individualmente las 20 réplicas.
- [ ] STR-13 — Bloqueo de aceptación: el **criterio original** del IC E5 sano sigue NO APROBADO. El piloto nuevo pasó su umbral separado, pero no corrige ni sustituye aquella falla. Solo datos/control nuevos bajo otro protocolo aprobado antes podrían aportar evidencia adicional; no declarar aceptación original completa.

## Acceptance criteria
- Los tests con valores calculados a mano pasan: premio 78/70, esperanza 0,85, escalera del screenshot, rachas sin cruzar días y apuesta audaz determinística.
- Control sano: 0 fallas Holm; el intervalo del retorno por peso contiene 0,85 en E2–E5.
- Control trampa: E1/E5, E2, E3 y E4 detectan su defecto sembrado (Holm < 0,01).
- El SHA-256 del JSON es igual antes y después.
- E9 informa 100 valores, incluyendo los sin casos; excluye enlaces entre días, reporta frecuencias y matriz descriptiva sin p individuales, sin vender un valor descubierto a posteriori como apuesta ganadora. El resumen permite leer todos los N predeclarados, no solo N=5.

## Protocolo prospectivo E5 (registrado antes de ejecutar)

- Objetivo: calibrar la **cobertura** del IC 95% de la apuesta plana E5 bajo un generador sano, no reexaminar si la apuesta gana ni reemplazar el control original fallido.
- Congelar el historial solo como calendario y longitud; 566 días, corte ya vigente en el día 60% (`2026-02-10`). Para cada réplica elegir entre las 12 políticas E5 (par/impar y bajo/alto × N≥3…8) por retorno de entrenamiento, con el mismo orden y desempate; evaluar solo en el 40% final.
- Exactamente 20 semillas distintas de la original `healthy`: `E5-healthy-cal-v1-001` hasta `E5-healthy-cal-v1-020`, incluidas ambas. Una sola corrida, sin sustituir ni agregar semillas tras ver el resultado. `sha256_drbg` usa cada semilla para generar un control con la misma plantilla temporal.
- Para cada corriente usar el bootstrap existente por días con 2.000 remuestreos y semilla de bootstrap fija del runner original; guardar política seleccionada, retorno, IC 95% e indicador `limite_inferior <= 0,85 <= limite_superior`.
- Criterio nuevo y separado: **≥18 de los 20 intervalos** deben incluir 0,85. Es un piloto de calibración con precisión limitada, no la aprobación retroactiva del criterio E5 original, ni una garantía de cobertura universal. Conservar los 20 resultados incluso si no alcanza el umbral. No generar p individuales por estrategia ni cambiar las pruebas E1–E8.
- Artefactos nuevos: `strategy_tests/calibrate_e5.py`, `strategy_tests/test_calibrate_e5.py`, `reports/e5_healthy_calibration.md` y `.json`; reportes originales intactos. No se modifican datos fuente, dependencias ni git.

## Progress
- Plan: `.pi/plans/pruebas-estrategias-chance-express.md` (aprobado por el usuario).
- SHA-256 del JSON antes y después: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.
- Verificación independiente final: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest strategy_tests rng_audit -q -p no:cacheprovider` → 33 aprobados; `py -B -m ruff check strategy_tests` → limpio; LSP en E9 y calibración: 0 errores/advertencias (26 sugerencias ortográficas informativas en texto español).
- Calibración prospectiva: 19/20 IC incluyen 0,85 (umbral nuevo ≥18/20). Original E5 sano sigue fuera de 0,85. `reports/strategy_tests.md` SHA `d59aeef80944e4c888ffc5c996f50a4906709103c1d717c8299ad3f2e7c10e89` y `.json` SHA `028eb3ea2050cbc8e0b0596c6951914f03e1aec1090ace56aef02730cbefc883` no cambiaron después de E9.
- Control trampa: E1/E5, E2, E3 y E4 tienen Holm < 0,01; control sano tiene 0 rechazos Holm, pero incumple el IC de E5 plana. Ese fallo muestral no se ocultó.
- E6 usa sesiones consecutivas sin solapamiento en vez de arrancar cada día; E4 usa errores agrupados por día; E8 excluye 11 p asintóticos inválidos por conteos bajos y 6 filas sin apuestas. Son correcciones de validez documentadas en el reporte.
- Límite de interpretación: la regla de premios repetidos no está confirmada por Loteka; el bootstrap diario supone independencia entre días y no modela pérdidas de escalera aún no observadas.
- Evaluación nativa de riesgo no pudo clasificar el árbol por archivos no rastreados; indicó verificador independiente, que se ejecutó. `gentle_review.inspect` quedó bloqueado por la selección de archivos no rastreados y proyecta además la eliminación ajena de `lottery-predictability-monte-carlo`; no se inició una revisión de un candidato mezclado ni se creó linaje.
- No se hicieron commits, push ni PR por la restricción explícita del plan; la eliminación preexistente de `lottery-predictability-monte-carlo` quedó intacta.
