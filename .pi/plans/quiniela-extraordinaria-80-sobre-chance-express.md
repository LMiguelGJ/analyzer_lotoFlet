# Plan: Quiniela 80/8/4/2/1 sobre el historial de Chance Express

> Created by `plan-mode-trae` · Idioma: español · Fecha: 2026-09-27

## Summary

Reevaluar las estrategias #1, #2, #6, #12, #21, #26, #27 y #29, más E9, usando **el mismo** `chance_express_history.json` y los premios de la imagen de Quiniela Extraordinaria: RD$80/8/4/2/1 por peso en las posiciones 1.ª–5.ª. Dar prioridad a la 1.ª posición, preservar íntegros los informes y datos anteriores, y rotular los nuevos resultados como **simulación contrafactual sobre sorteos de Chance Express**, no evidencia observada de Rapidita.

## Current State Analysis

- `strategy_tests/rules.py` fija `PRIZES=[70,8,4,2,1]`, calcula `payout`, `payout_matrix`, retorno esperado y la escalera original. El retorno anterior bajo pago de todas las coincidencias es 0,85.
- `strategy_tests/experiments.py` separa pruebas de probabilidad y apuestas. E2–E5 calculan pagos; E6 usa `PRIZES[0]`, Monte Carlo y una caché de sesiones que hoy no distingue tabla de premios; E7 compara `all` y `best`. E1 y E9 son de probabilidades/conteos y no cambian al cambiar premios. La escalera `LADDER` proviene de una captura con premio 70 y no debe renombrarse como escalera optimizada a 80.
- `strategy_tests/run_experiments.py` ejecuta E1–E8 en Loteka y controles sano/trampa, selecciona parámetros en el 60% inicial de días, prueba en el 40% final, añade E9 descriptivo y escribe **siempre** `reports/strategy_tests.md` y `.json`: invocarlo sin cambios sobrescribiría resultados anteriores.
- `strategy_tests/test_rules.py` congela premios y escalera de 70; `strategy_tests/controls.py` conserva cuatro defectos sembrados. `strategy_tests/calibrate_e5.py` y `reports/e5_healthy_calibration.*` congelan hashes y documentan el piloto anterior; el criterio original E5 sano sigue **NO APROBADO** en `odd/tasks/strategy-tests.md`.
- El repositorio tiene una eliminación preexistente ajena (`lottery-predictability-monte-carlo`); no tocarla. `chance_express_history.json` tiene 105.426 sorteos/566 días y SHA-256 `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.

## Proposed Changes

### 1. `strategy_tests/rules.py` y tests nuevos de reglas
- Definir una tabla de premios explícita e inmutable por escenario; mantener 70/8/4/2/1 como valor por defecto para compatibilidad y añadir 80/8/4/2/1 sin mutar el global. Pasar la tabla al cálculo de pago, matriz y retorno teórico.
- Test-first: primer puesto 80; aciertos repetidos `all` frente a `best`; retornos esperados **0,950000** (`all`) y **0,9474159401** (`best`) bajo cinco posiciones uniformes independientes. La modalidad `best` es sensibilidad porque la imagen no confirma qué pasa con números repetidos. No trasladar suponer `best` de “priorizar la primera”.
- La apuesta modelada es RD$1 **por número**; si se eligen cinco números, son cinco apuestas por separado. No inventar una apuesta combinada de cinco números ni palé/tripleta.

### 2. `strategy_tests/experiments.py` y pruebas de estrategias
- Propagar el escenario de pagos sin valores 70 hardcodeados a E2–E7. E6 debe calcular la apuesta audaz con premio 80 en 1.ª y simular el mismo modo de pago (`all` o `best`) que evalúa sobre datos; incluir tabla/modo en la clave de `_MC_CACHE` o evitar caché cruzada. Mantener los objetivos y capitales originales y revisar que “juego justo” no describa pagos con margen.
- Primera posición como **métrica principal**: aciertos al 1.º (referencia 1% por número, o cobertura real por cantidad de números apostados), retorno/cobros atribuibles **solo** al premio de 1.ª y ganancias netas de esa vista; también retorno total de quiniela con premios 2.ª–5.ª. Para E2–E5 seleccionar parámetros en entrenamiento por retorno de 1.ª posición y medir ambos retornos solo en prueba ciega. Mostrar como sensibilidad qué cambiaría al seleccionar por retorno total, sin confundirlo con una segunda prueba confirmatoria.
- E5: ejecutar **dos escaleras etiquetadas**: (a) la secuencia original de 70 aplicada sin cambios al premio 80, y (b) una secuencia nueva de hasta 10 rondas, calculada antes de ver resultados como mínimo entero que, con 50 números apostados, un acierto solo en 1.ª recupere lo invertido más RD$10: `s_r=max(1,ceil((invertido_previo+10)/(80-50)))`; inversión de la ronda `50*s_r`. La segunda no es una sugerencia de apuesta segura: reportar pérdida completa, capital mínimo y escenarios de cola no observados. Mantener la secuencia original y sus tests sin cambios.
- E7 reporta los dos supuestos de repetidos; E1/E8/E9 y pruebas de probabilidad E2–E5 deben conservar sus conteos/p-valores, pues los números sorteados no cambian. E9 conserva las 100 filas X=00–99 y su matriz descriptiva, sin crear 100 predicciones.

### 3. Nuevo `strategy_tests/run_quiniela80.py`; reportes nuevos
- Entrada exacta: `py -B -m strategy_tests.run_quiniela80`. Reutilizar funciones del runner existente que acepten escenario explícito; mantener sus valores predeterminados de 70. Separar el escenario de salida para impedir sobrescritura de `reports/strategy_tests.md|json` y `reports/e5_healthy_calibration.md|json`. Crear `reports/strategy_tests_quiniela80.md` y `.json` con metadatos: historial y SHA, pagos, supuesto `all` principal/`best` sensibilidad, calendario, corte, bootstrap, semilla, selector de 1.ª posición y naturaleza contrafactual.
- Resumen legible por las ocho ideas, tabla prioritaria de 1.ª posición, tabla de retorno total y pérdida/beneficio neto, intervalos, capital de escalera, controles sano/trampa y E9. Comparar contra **0,80** para el retorno de solo 1.ª y **0,95** para quiniela completa `all` (o 0,9474159401 en `best`); beneficio económico exige retorno **>1**, no solo superar la referencia aleatoria.
- Mantener el split 60/40, Holm para las familias preexistentes y las advertencias sobre E4 solapado, E8 celdas dispersas, períodos de fuentes distintos, selección post hoc y bootstrap diario. Para cada control sano, informar con honestidad cualquier IC que no cubra la nueva referencia; **no resembrar ni cambiar criterios** para hacerlo pasar. El piloto viejo 19/20 sobre 0,85 y STR-13 quedan históricos, sin reinterpretación como evidencia del escenario 80.

### 4. `odd/tasks/quiniela80-counterfactual.md` (solo tras aprobar este plan)
- Crear seguimiento ODD y espejo de memoria antes de tocar código. Dividir en unidades revisables: reglas/test-first; experimentos y primera posición; runner/reportes/controles; verificación independiente. Por el tamaño probable >400 líneas, revisar el volumen antes de implementar y dividir la revisión en porciones; **sin commits, push ni PR** por la restricción explícita anterior.

## Assumptions & Decisions

- “Número 1” significa **1.ª posición**, no el valor literal `01`. El premio nuevo es exactamente 80/8/4/2/1 y el análisis es **solo quiniela**, no palé/tripleta.
- El historial de Chance Express se usa por elección del usuario **como escenario hipotético**; no se ha establecido que sean sorteos de Rapidita. No atribuir resultados observados a Rapidita ni recomendar apuestas sobre ella basándose en este historial.
- En el modo principal se suman los premios si un número aparece en varias posiciones, igual que el informe original; `best` es sensibilidad obligatoria hasta confirmar reglas de repetidos. Los valores 0,95 y 0,9474159401 dependen del supuesto de posiciones uniformes e independientes.
- La probabilidad de acertar el 1.º **no cambia** por aumentar el premio. Mostrar siempre tamaño de muestra, unidades apostadas e intervalos; un retorno histórico >1, especialmente de escalera, no prueba ventaja predictiva ni elimina pérdidas raras.
- El plan original y sus informes no se editan ni se reemplazan; el bloqueo de aceptación STR-13 permanece pendiente. No modificar `chance_express_history.json`, `loteka_numbers.json`, `lagacy_loto/`, `rng_audit/`, ni la eliminación preexistente. Sin instalaciones ni operaciones de publicación.

## Verification

- [ ] Observar RED antes de implementación para premio 80, retornos `all`/`best`, pagos repetidos, objetivos E6/Monte Carlo y caché por perfil, retorno 1.º vs total, selector sin fuga y nueva escalera; luego GREEN y regresión íntegra de 70.
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest strategy_tests rng_audit -q -p no:cacheprovider` y `py -B -m ruff check strategy_tests`; LSP en archivos modificados.
- [ ] Ejecutar `py -B -m strategy_tests.run_quiniela80` (**solo el runner del escenario 80**) y verificar que termina, genera ambos archivos nuevos, reproduce conteos de pruebas de probabilidad y mantiene 100 filas E9. Confirmar controles trampa, p Holm y que los controles sanos no se retocan si fallan un criterio.
- [ ] Comprobar SHA-256 del historial sin cambios y hashes de los reportes originales (`strategy_tests.md`: `d59aeef80944e4c888ffc5c996f50a4906709103c1d717c8299ad3f2e7c10e89`; `.json`: `028eb3ea2050cbc8e0b0596c6951914f03e1aec1090ace56aef02730cbefc883`). El piloto E5 original también debe quedar intacto.
- [ ] Verificación independiente de consistencia MD/JSON, ganancia = cobros − apuestas, selección entrenamiento/prueba, cálculo de capital de ambas escaleras y referencias 0,80/0,95/0,9474159401. Reportar **cada** check fallido, N/A o pendiente sin declarar aprobación completa si no corresponde.

## Out of Scope

- Obtener o afirmar un historial real de Rapidita, confirmar sus reglas oficiales de duplicados, pronosticar números concretos o prometer ganancias.
- Analizar palé y tripleta, crear tablero web, modificar el historial, sobrescribir la evidencia original o resolver retroactivamente STR-13.
