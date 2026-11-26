# Mejoras de métodos de laboratorio (hallazgos de Judgment Day)

Aplicar en la app las mejoras que el usuario eligió a partir de `odd/reports/judgment-day-metodos-leidsa.md`.
Los laboratorios de referencia de Loteka Chance Express y sus resultados dorados no cambian.

## Specs

- S1 — "Ventana y half-life configurables": "Elegir en cada laboratorio la ventana o el half-life en vez del 500 fijo; así podés crear y seguir \"Decaimiento 300\"."
- S2 — "Arreglar Escalera y progresiones": "Escalera ligada a la meta y sin \"quiebras\" falsas; Martingala/Fibonacci/etc. solo reinician cuando recuperan lo perdido."
- S3 — "Resultado por año en la app": "Mostrar en cada laboratorio cuánto ganó o perdió cada año, sin tener que pedírmelo."
- S4 — "Validación y Ensamble": "Rechazar configuraciones que solo pueden quebrar, desempates y calentamiento, y un Ensamble sin votos repetidos u opuestos."
- S5 — Sin regresión: laboratorios de referencia de Chance, dorados y laboratorios/corridas ya guardados siguen idénticos (los cambios de comportamiento son opt-in o solo para laboratorios nuevos).

## Tasks

- T1 — S1, S4, S5: parámetros de ranking por laboratorio (`ranking_params`), Ensamble que los respeta y sin votos repetidos/opuestos, desempate, calentamiento por defecto, validación prizes[0] > cobertura para progresiones nuevas. Route: worker. Commit: 9669701.
- T2 — S2, S5: reglas de apuesta v2 (Escalera ligada a la meta, sin reinicio silencioso, acotada al saldo y al tope; progresiones que reinician solo al recuperar el ciclo), opt-in para laboratorios nuevos. Route: worker. Commit: 3fea931.
- T3 — S3, S5: desglose por año en el resultado del laboratorio (backend aditivo + tabla en el panel). Route: worker. Commit: f055cca.
- T4 — S1–S5: verificación, reinicio de la app y laboratorio "Decaimiento 300" creado en la app. Route: inline. Commit: n/a.

## Log

- L1 — Pedido: "si haz variaziones cambia este valor y todos que entiendas que este afectante a que no consigamos los resultados deseados y analiza bien todo los demas metodos para punto de mejoras". Judgment Day APPROVED sin severos (commit eda668a), 19 hallazgos informativos.
- L2 — Respuesta del usuario a "¿Cuáles arreglo o agrego en la app?": "Ventana y half-life configurables, Arreglar Escalera y progresiones, Resultado por año en la app, Validación y Ensamble".
