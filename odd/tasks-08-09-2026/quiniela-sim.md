# Simulador Quiniela Extraordinaria (quiniela-sim) — ODD

## Objetivo y autorización

Ejecutar el plan aprobado `.pi/plans/simulador-quiniela-extraordinaria.md` (aprobación explícita del usuario: "ejecuta esto con odd"). Versión mejorada y honesta de `lagacy_loto/`: compara cuatro formas de jugar la Quiniela Extraordinaria 80/8/4/2/1 con RD$2.000 → RD$2.800 sobre el historial real y sobre Montecarlo. No predice números ni recomienda jugar.

## Restricciones

- Sin instalaciones, commit, push ni PR.
- No tocar `lagacy_loto/`, `chance_express_history.json`, `repo_ref/` ni la reorganización pendiente (128 renombres preparados + eliminación ajena `lottery-predictability-monte-carlo`).
- Código y tests en inglés; informe en español.
- Test-first con RED/GREEN observado; un escritor por vez.
- No cambiar supuestos ni semillas después de ver resultados.

## Tareas

- [x] QS-1 — Motor: port fiel del Markov legado, consenso de 27 votos, selecciones, pagos, estrategias flat/ladder/bold, sesiones back-to-back, Montecarlo y métricas (test-first).
- [x] QS-2 — CLI e informe en español (test-first).
- [x] QS-3 — Corrida real, informe generado y verificación independiente.
- [x] QC-1 — Ampliación autorizada: verificar 13 rankings y fijar coberturas 1,5,10,20,25,30,40,50.
- [x] QC-2 — Motor generalizado plana/escalera/audaz por cobertura, test-first y revisión independiente.
- [x] QC-3 — Integración de rankings, CLI protegida, conteos exactos y saldo final medio.
- [x] QC-4 — Corrida ampliada e inspección independiente del informe y NPZ.

## Evidencia de preservación inicial (2026-09-28)

- Historial: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.
- `git status`: la reorganización hacia `repo_ref/` ya está commiteada y sincronizada (`96457b1`). Solo quedan ` D lottery-predictability-monte-carlo` (ajena) y los archivos de este plan/ODD.

## Evidencia de ejecución

### QS-1 — completado y verificado independientemente

- Escritor: RED por módulo ausente y fallos conductuales de pago audaz/límite MC corregidos; GREEN 11 pruebas.
- Verificador independiente: 11 passed in 3.36s; Ruff --no-cache limpio. Comparación estática con legado y rules sin bloqueadores; estado Git sin cambios por la revisión.
- Cobertura a reforzar: empates/back-off explícitos, oráculo escalar MC ladder/bold, pagos best con varios números distintos, fronteras de replay sin saltar sorteos y métricas sin sesiones completas.
- La equivalencia par/impar uniforme es distribucional. Las cuatro rondas financiables describen pérdidas completas, no trayectorias con premios secundarios.

### QS-2 — completado con corrección verificada

- CLI y renderer: RED/GREEN, inicialmente 24 pruebas. Revisión encontró posible sobrescritura mediante --report.
- Corrección test-first: 13 casos RED; validación canónica antes de cargar datos, rechazo de destinos existentes/protegidos/enlaces y creación exclusiva con modo x. GREEN final: 40 pruebas; Ruff sin hallazgos, confirmados por verificador independiente.
- El informe existente no se sobrescribe; para nuevas corridas usar otro nombre.

### QS-3 — corrida completa y revisión del artefacto

- Ejecutado con éxito: `PYTHONDONTWRITEBYTECODE=1 py -B quiniela_sim.py --capital 2000 --meta 2800 --mc-sessions 20000 --report informe_quiniela_sim.md`.
- Historial: 105.426 sorteos; MC: 20.000 sesiones por estrategia/modo. Informe generado por el programa, no escrito a mano.
- MC all: plana meta 8,3%, quiebre 91,7%, neto medio -1737,2; escalera 38,3% / 61,7% / -138,7; audaz 68,5% / 31,5% / -53,4 DOP. Son estimaciones finitas, no garantías ni ventaja positiva.
- Verificación independiente: bloqueo cerrado, 40 pruebas y Ruff aprobados, lectura del informe coherente; NO regeneró independientemente las cifras de la corrida completa. Esa limitación queda explícita.
- SHA del historial idéntico al inicial; Git solo muestra los cinco archivos de esta tarea sin seguimiento y la eliminación ajena preexistente. No commits/push ni cambios a legado/repo_ref.
- Riesgo residual: sustitución concurrente adversarial del directorio padre fuera de cobertura. Quiebre de escalera/plana puede dejar saldo; las colas históricas inconclusas se excluyen de métricas completas y se reportan.

## Ampliación QC — completada

- Autorización posterior del usuario: comparar familias previas, diferentes coberturas y apuestas para 2000→2800, mínimo RD$1 por número. Originales conservados; nuevos archivos raíz `quiniela_compare.py`, `test_quiniela_compare.py`, `informe_quiniela_comparacion.md`.
- Grilla previa a corrida: 13 sistemas (12 familias interpretables + select_interpretable), 8 coberturas, 3 apuestas; azar en cada cobertura, paridad solo50; all/best. 339 combinaciones históricas y24 MC por modo.
- Audaz k: apuesta por número min(ceil((meta-saldo)/(80-k)),floor(saldo/k)); gasto total k veces apuesta. Escalera recalculada para cada k. Historial común65235 filas; huecos sin apuesta, sin reiniciar saldo; conjunto top-k pos1 liquidado en las cinco posiciones.
- Test-first y revisión independiente:52 pruebas motor,57 integración,58 finales con conteos exactos/saldo y validación temprana del capital. Ruff limpio.
- Comando exitoso: `PYTHONDONTWRITEBYTECODE=1 py -B quiniela_compare.py --capital 2000 --meta 2800 --mc-sessions 20000 --report informe_quiniela_comparacion.md`.
- Revisión final del artefacto:726 filas completas distintas (678 historial+48MC),10 líderes repetidos; conteos suman completas, tasas coherentes con redondeo, saldo medio=2000+neto, neto total=pagado-apostado. Todas las filas históricas65235 apuestas; MC20000 sesiones completas por fila.
- Verificador inspeccionó NPZ real: SHA coincide con informe,65235 IDs crecientes,14 folds,13 arrays uint8 de permutaciones completas; logistic/tree/select_all excluidos. No regeneró resultados ni verificó independientemente toda la generación causal o alineación contra etiquetas del historial; límites explícitos.
- Líder retrospectivo all: transición k1 audaz681/963=70,7%, neto medio+10,3. No evidencia confirmatoria de rentabilidad: datos reutilizados y selección entre muchas alternativas. Mejor tasa k50: mezcla audaz12845/20605=62,3%, neto-117. MC audaz50:12303/20000=61,5%, neto-142,1.
- SHA del historial sin cambios; sin installs/commits/push ni modificaciones a legado/repo_ref o informe anterior.
