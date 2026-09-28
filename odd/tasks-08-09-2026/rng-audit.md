# Auditoría del generador aleatorio de Chance Express

## Objective
Determinar con evidencia si los resultados de `chance_express_history.json` muestran algún defecto del generador que deje un patrón explotable.

## Problem and rationale
Las estrategias probadas (Markov par/impar, frecuencias, gaps, horarios, modelo 45/45/10) rindieron al nivel del azar. Falta verificar el generador en sí, con la batería estándar NIST SP 800-22 y con pruebas específicas para 00–99 orientadas a errores reales de implementación: sesgo de módulo, semilla por hora, generadores lineales y memoria entre sorteos.

## Scope
- Implementar NIST SP 800-22 (15 pruebas) en numpy/scipy, validado con los ejemplos numéricos de NIST.
- Implementar las pruebas B1–B11 específicas de 00–99.
- Correr todo sobre Loteka y sobre 4 generadores de control (uno sano, tres defectuosos).
- Aplicar corrección por pruebas múltiples y escribir `reports/rng_audit.md` y `reports/rng_audit.json`.

## Constraints / non-goals
- `chance_express_history.json` y los archivos legacy son de solo lectura.
- Sin instalar dependencias. TestU01 y Dieharder quedan fuera y se documenta por qué.
- Sin commit, push ni PR.
- El resultado se reporta tal como sale, sin ajustar pruebas para que Loteka pase o falle.

## Tasks
- [x] RNG-1 — Escribir fixtures con los ejemplos numéricos de NIST SP 800-22 (test-first).
  - Evidencia: `rng_audit/test_nist_examples.py` con 11 casos. Falló en la recolección antes de que existiera la implementación.
- [x] RNG-2 — Implementar las 15 pruebas NIST y pasar las fixtures.
  - Evidencia: `rng_audit/nist_sp800_22.py`. 11/11 pasan: frequency 0,527089; block frequency 0,801252; runs 0,147232; cusum 0,4116588; ApEn 0,261961; serial 0,808792/0,670320; Berlekamp-Massey L=4; 148 plantillas aperiódicas m=9; bits justos aprobados y bits sesgados detectados.
- [x] RNG-3 — Implementar las pruebas B1–B11 de 00–99 y los generadores de control.
  - Evidencia: `rng_audit/lottery_tests.py` (52 pruebas) y `rng_audit/generators.py` (SHA-256 sano, LCG de bits bajos, sesgo de módulo de 8 bits, semilla por hora). Se corrigieron un desborde del hash de n-gramas (B9b), el overflow de `100**L` y lags sin pares del mismo día (B7).
- [x] RNG-4 — Ejecutar la auditoría completa sobre Loteka y los controles; generar el reporte.
  - Evidencia: `py -m rng_audit.run_audit` en 2 min 41 s. Genera `reports/rng_audit.md` y `reports/rng_audit.json`. 105.426 sorteos, 566 días con datos, 2.024.286 bits NIST.
- [x] RNG-5 — Verificar que los controles se comportan como se espera, que el JSON quedó intacto y que no hay errores de LSP.
  - Evidencia: Loteka 0/52 específicas, 0/15 NIST 6 bits y 0/15 NIST paridad fallan. SHA-256 sano: 0/0/0. LCG: 19/52, 7/15, 11/15. Sesgo de módulo 8 bits: 26/52, 7/15, 1/15. Semilla por hora: 50/52, 10/15, 11/15. SHA-256 del JSON igual antes y después (`d1c0e9ec…9711`). LSP sin errores; solo avisos heurísticos `unchecked-numeric-parse`.
- [x] RNG-6 — Resumir los hallazgos para el usuario.
  - Evidencia: resumen entregado en la conversación.

## Acceptance criteria
- Las fixtures NIST coinciden con los valores del documento (tolerancia 1e-6).
- El control `crypto` pasa; cada control defectuoso falla al menos en la prueba diseñada para detectarlo.
- El reporte indica, por prueba, si pasa o falla para Loteka, con valor p y explicación.
- El SHA-256 del JSON es igual antes y después.

## Progress
- Plan: `.pi/plans/auditoria-rng-chance-express.md`.
- Desvío del plan: el comando es `py -m rng_audit.run_audit` (módulo), no `py rng_audit/run_audit.py`, para que los imports del paquete funcionen.
- Pytest necesita `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` por un conflicto de plugins globales (`--browser`).
- Durante la ejecución aparecieron commits automáticos (d4ec7b6…4221244) que no hizo el agente.
