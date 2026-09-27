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
- [ ] RNG-1 — Escribir fixtures con los ejemplos numéricos de NIST SP 800-22 (test-first).
- [ ] RNG-2 — Implementar las 15 pruebas NIST y pasar las fixtures.
- [ ] RNG-3 — Implementar las pruebas B1–B11 de 00–99 y los generadores de control.
- [ ] RNG-4 — Ejecutar la auditoría completa sobre Loteka y los controles; generar el reporte.
- [ ] RNG-5 — Verificar que los controles se comportan como se espera, que el JSON quedó intacto y que no hay errores de LSP.
- [ ] RNG-6 — Resumir los hallazgos para el usuario.

## Acceptance criteria
- Las fixtures NIST coinciden con los valores del documento (tolerancia 1e-6).
- El control `crypto` pasa; cada control defectuoso falla al menos en la prueba diseñada para detectarlo.
- El reporte indica, por prueba, si pasa o falla para Loteka, con valor p y explicación.
- El SHA-256 del JSON es igual antes y después.

## Progress
- Plan: `.pi/plans/auditoria-rng-chance-express.md`.
