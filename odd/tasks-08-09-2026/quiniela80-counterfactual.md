# Quiniela 80 contrafactual — ODD

## Objetivo y autorización
Ejecutar el plan aprobado `.pi/plans/quiniela-extraordinaria-80-sobre-chance-express.md`. Pagos 80/8/4/2/1 sobre el mismo historial de Chance Express; prioridad analítica a primera posición, no al número literal 01. No constituye evidencia real de Rapidita.

## Restricciones
Sin instalaciones, commits, push ni PR. Preservar datos, `rng_audit/`, `lagacy_loto/`, reportes anteriores, calibración anterior y bloqueo STR-13. No tocar eliminación preexistente `lottery-predictability-monte-carlo`. Un escritor por vez. Código/tests en inglés; informes en español. Test-first y revisión independiente.

## Tareas
- [x] Q80-1 — Reglas explícitas inmutables y pruebas de regresión 70/80. RED por perfil inexistente; GREEN: 6 tests nuevos + 18 originales; Ruff limpio. `PrizeProfile`, `ORIGINAL70`, `QUINIELA80`, helpers con perfil opcional y `first_prize_ladder`; predeterminado 70 preservado.
- [x] Q80-2 — Perfiles explícitos E5–E8, primera posición reutilizable E2–E5, simulación/caché E6 por perfil/modo, escaleras y conteo por acierto real al primero. RED: 6 tests fallaron; GREEN: 7 nuevos, 46 totales aprobados; Ruff limpio. La selección solo en entrenamiento se implementará en Q80-3.
- [x] Q80-3 — Runner separado y reportes generados (~143 s). RED por runner ausente, GREEN 4 tests nuevos/50 totales; Ruff limpio. Vistas primera/all/best, selección entrenamiento, grillas, ambas escaleras, controles y E9. Escritor comprobó 5 hashes preservados. Resultados pendientes de revisión independiente.
- [x] Q80-4 — Verificación independiente sin bloqueadores en alcance inspeccionado: 314 filas de probabilidad ×3 datasets iguales (excepto E6/Holm), E9 100×100/104.860 transiciones, 972 registros monetarios y 24 candidatos de escalera contrastados; 5 hashes preservados. Corrección menor de redondeo de IC con test RED/GREEN y render desde JSON sin simular: 51 tests finales, Ruff `strategy_tests` limpio, LSP sin errores/advertencias. No hay recibo nativo: evaluación no clasificable por archivos no rastreados; se siguió su exigencia de verificador independiente.
- [x] Q80-5 — Síntesis preparada desde resultados verificados: cuatro selecciones planas pierden en prueba; E3 total 0,9755 es la más cercana al equilibrio de esas cuatro; E6 audaz alcanza 1.000→2.000 en 48,20% de sesiones reales (simulación all), sin ventaja confirmada. Escalera nueva exige RD$453.500 de apuestas acumuladas por diez rondas frente a RD$4.517.300 original, no garantía contra ruina. Reportes separados disponibles y limitaciones explícitas.

## Evidencia de preservación inicial
- Historial: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`
- Reporte original MD: `d59aeef80944e4c888ffc5c996f50a4906709103c1d717c8299ad3f2e7c10e89`
- Reporte original JSON: `028eb3ea2050cbc8e0b0596c6951914f03e1aec1090ace56aef02730cbefc883`
- Calibración original MD: `d328d148b12b85ae052452647c7f7c93977315884c3d1033ce1d4869a59207e1`
- Calibración original JSON: `5d22cd7f9058ee811c169a32b198e3d035e48811f25a958b0d09fcdc28fa0dd0`

## Evidencia de ejecución

- Alcance de lint aprobado: `py -B -m ruff check strategy_tests`. Un sondeo adicional sobre `rng_audit` informó 11 hallazgos preexistentes en `rng_audit/run_audit.py`, fuera de alcance e intactos; no se afirma limpieza global del repositorio.
- Control sano E5 all del nuevo escenario: IC [0,920200–0,949524] no cubre 0,95; hallazgo conservado, sin ajuste de semillas. Esto no impide terminar la medición ni convierte el resultado en aprobación estadística. STR-13 anterior sigue histórico.
- JSON nuevo sin cambios tras ajuste solo visual: SHA `e5ba61577037b06674f22246788e1d474a3bf53d84bcdfb5958e45930e4a2b7b`.
Revisión de artefactos: explorador comprobó estructura y ejemplos puntuales, sin capacidad de ejecutar hashes/comparación completa; no se cuenta como verificación exhaustiva. El coordinador ejecutó `sha256sum` y confirmó los cinco hashes iniciales intactos, y `git status --short` preserva la eliminación ajena. Sondeo LSP en seis archivos modificados: 0 errores/advertencias. Verificador lógico independiente continúa; se le pidió comparación programática completa.

Q80-1 completado por escritor único; lectura de APIs confirmada por el coordinador. Q80-2 debe propagar explícitamente los perfiles: `PRIZES` sigue siendo el arreglo heredado de 70. No convertir resultados estadísticos desfavorables en fallas de software ni ajustar semillas para obtener aceptación.
