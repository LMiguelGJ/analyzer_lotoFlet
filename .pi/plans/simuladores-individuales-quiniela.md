# Plan: 14 simuladores individuales de Quiniela

## Summary

Crear una carpeta ejecutable por cada una de las 14 filas de `resumen_resultados_quiniela.md`. Cada `ejecutar.py` recalculará únicamente su escenario histórico con el motor probado, el mismo JSON y los mismos rankings congelados; no copiará resultados como sustituto de una simulación.

Estado: plan pendiente de aprobación. En esta fase solo se escribe este documento.

## Current State Analysis

Exploración de solo lectura delegada: `resumen_resultados_quiniela.md`, `quiniela_compare.py`, `quiniela_sim.py`, `test_quiniela_compare.py` e informe comparativo. Se consultó la plantilla de plan-mode-trae.

- `quiniela_compare.py` ofrece `ranking_context`, `ranking_family`, `selected_payments`, `replay`, `_record` y `_table`. `historical_rows` recorre toda la grilla y `run_experiment` agrega Monte Carlo: no deben invocarse para ejecutar una sola fila.
- `quiniela_sim.py` contiene `load_validated_history` y `consensus_parity`; se reutilizan sin modificaciones.
- Entradas comunes: `chance_express_history.json` y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`. La población común es de 65.235 filas en 14 folds, dentro del historial de 105.426 sorteos.
- SHA-256 del historial: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.
- SHA-256 de rankings: `b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d`.
- La implementación actual tiene 58 pruebas aprobadas y Ruff limpio según la última verificación. Esto es evidencia previa, no prueba de futuros cambios.
- El usuario quiere entrar a una carpeta y ejecutar su Python. Se conserva su nomenclatura española para carpetas y documentación; identificadores internos y tests en inglés.
- La revisión nativa del candidato acumulado quedó bloqueada por `lens_context_budget_exceeded`, sin autoridad creada. No debe describirse como revisión aprobada ni repetirse sin reducir el candidato.

## Proposed Changes

### 1. `quiniela_compare.py` — API pública para un escenario

Agregar `historical_scenario(history, path, system, k, style, mode="all", context=None, capital=CAPITAL, goal=GOAL)`.

- Componer las funciones existentes: contexto validado, carga de una sola familia, selección top-k, pago de ese mismo conjunto en las cinco posiciones, replay y métricas.
- Devolver el mismo registro estructurado que usa el comparador, incluidos completas/inconclusas, meta/quiebre exactos, tasas, intervalo, saldo/neto medios, duración y totales con cola.
- Validar entradas antes de cálculo. Permitir los sistemas archivados y el caso `parity` con k=50; no añadir nuevos selectores ni nuevas reglas.
- Para paridad, calcular el consenso sobre TODO el historial y después restringir a `row_ids`; nunca iniciar el predictor en el primer registro exportado.
- No duplicar fórmulas ni refactorizar innecesariamente el flujo completo existente. Probar equivalencia con sus filas.

### 2. `simuladores/runner.py` y `simuladores/__init__.py` — arranque compartido

Un runner pequeño centraliza validación, entradas, ejecución y presentación. `__init__.py` identifica explícitamente el paquete.

- Raíz derivada de `Path(__file__).resolve()`, nunca del directorio actual.
- Usar rutas absolutas calculadas para el JSON y NPZ comunes; no copiarlos a las carpetas.
- Verificar ambos SHA anteriores antes de reproducir la fila. Un cambio produce error explicativo y salida no cero: no presentar resultados diferentes como reproducción idéntica.
- Cargar contexto y ejecutar SOLO el escenario solicitado, sin grilla completa ni Monte Carlo.
- Parámetros fijos para reproducir la tabla: capital2000, meta2800, modo `all`, sistema/k/estilo de la carpeta. No añadir opciones para cambiar escenarios en esta versión. `--help` puede explicar el uso.
- Mostrar en español: configuración, rutas/hashes, población común, sesiones completas e inconclusas, meta y quiebre (n y porcentaje), neto y saldo final medios, mediana/p90 de apuestas e intervalo descriptivo.
- Mostrar aviso de contrafactual histórico, datos reutilizados y ausencia de garantía futura.
- Salida normal solo a consola. Sin reportes nuevos, cachés persistentes, modificación de entradas ni archivos temporales propios. Usar `py -B` para evitar bytecode; `py ejecutar.py` también debe funcionar aunque Python pueda crear su caché normal.
- No usar el Markdown como fuente de datos del cálculo. Los valores esperados se conservan en tests/documentación únicamente como evidencia de regresión.

### 3. Las 14 carpetas — `ejecutar.py` y `README.md` en cada una

Cada adaptador resuelve raíz con `Path(__file__).resolve().parents[2]`, habilita importación del paquete compartido y llama al runner con una configuración explícita. Todos tienen guardia `if __name__ == "__main__"`; importar no ejecuta el experimento.

| Carpeta bajo `simuladores/` | Sistema interno | k | Estilo | Meta / completas | Quiebres | Neto medio RD$ |
|---|---|---:|---|---:|---:|---:|
| `transicion_1_audaz/` | transition | 1 | bold | 681 / 963 | 282 | +10,3 |
| `frios_1_audaz/` | cold | 1 | bold | 684 / 974 | 290 | −3,4 |
| `selector_1_audaz/` | select_interpretable | 1 | bold | 663 / 946 | 283 | −8,2 |
| `mezclas_1_audaz/` | mix | 1 | bold | 676 / 968 | 292 | −15,6 |
| `ensemble_5_audaz/` | ensemble | 5 | bold | 3.226 / 4.720 | 1.494 | −51,2 |
| `ensemble_10_audaz/` | ensemble | 10 | bold | 6.140 / 9.061 | 2.921 | −56,9 |
| `ensemble_20_audaz/` | ensemble | 20 | bold | 10.785 / 16.086 | 5.301 | −59,2 |
| `frios_25_escalera/` | cold | 25 | ladder | 677 / 1.105 | 428 | −162,2 |
| `mezclas_50_audaz/` | mix | 50 | bold | 12.845 / 20.605 | 7.760 | −117,0 |
| `transicion_50_audaz/` | transition | 50 | bold | 12.890 / 20.682 | 7.792 | −116,0 |
| `paridad_50_audaz/` | parity | 50 | bold | 12.698 / 20.404 | 7.706 | −120,8 |
| `frios_50_escalera/` | cold | 50 | ladder | 1.429 / 3.502 | 2.073 | −98,7 |
| `paridad_50_escalera/` | parity | 50 | ladder | 1.368 / 3.496 | 2.128 | −124,4 |
| `paridad_50_plana/` | parity | 50 | flat | 13 / 91 | 78 | −1.572,8 |

Cada README incluye:

1. Qué combinación representa y su fila esperada.
2. Ejecución desde esa carpeta: `py -B ejecutar.py` (también compatible con `py ejecutar.py`).
3. Ejecución desde raíz: `py -B simuladores/<carpeta>/ejecutar.py`.
4. Explicación concreta del selector y forma de apostar, mínimo1 por número, costo total y meta.
5. Dependencia del repositorio completo: no es un script autónomo para copiar fuera del repo; necesita motor, JSON y NPZ compartidos.
6. Diferencia entre sesión/sorteo, quiebre/saldo cero y neto medio/ganancia garantizada; tratamiento de inconclusas.
7. Enlace relativo al resumen y al informe completo. No duplicar todo el informe en cada carpeta.

### 4. `simuladores/README.md` — índice

Listar las 14 carpetas con enlaces, comandos, parámetros y resultados esperados. Explicar arquitectura compartida, requisitos Python/NumPy existentes, resolución de rutas, errores por hash/entrada ausente y límites estadísticos. No ejecutar instalaciones automáticamente.

### 5. Pruebas

- `test_quiniela_compare.py`: pruebas pequeñas del nuevo helper, equivalencia con flujo existente, selección exclusiva de una familia, paridad calculada antes de recortar, gaps y cola censurada.
- `test_simuladores.py` nuevo en raíz: manifiesto esperado de14 rutas/configuraciones sin duplicados ni omisiones, importación sin efectos, errores de integridad, salida visible y lanzadores desde cwd independiente mediante fixtures/mocks.
- Integración opt-in en el mismo archivo, controlada por `QUINIELA_RUN_INTEGRATION=1`: ejecutar los14 scripts reales secuencialmente desde sus propias carpetas. Verificar códigos de salida, configuración y conteos exactos, neto redondeado a un decimal y tasas derivadas. Comparar salida legible con patrones estables; no agregar una API JSON innecesaria.
- Comparar números con referencias previamente fijadas arriba; nunca cambiar la referencia para que pase un resultado discrepante.
- Comprobar hashes de datos/rankings e informes protegidos antes y después de integración. No regenerar rankings ni informes.

## Assumptions & Decisions

- Alcance exacto: las14 filas del resumen, no todas las339 combinaciones ni solo las3 del ejemplo truncado.
- Se reproduce el escenario principal de pagos acumulados, sin nuevas selecciones, ajustes, semillas o búsquedas de mejores resultados.
- Misma lógica mediante importación, no14 copias del motor. Cada carpeta sí tiene un ejecutable independiente para el usuario.
- Las entradas binarias son necesarias además del JSON: contienen la selección histórica congelada. Reentrenar desde cero queda fuera de alcance.
- Sesiones continúan entre días/folds y filas sin apuesta; mismas65235 filas evaluables. Se preserva la información causal completa para paridad.
- No se promete la misma cifra con datos o código cambiados. La reproducción se valida por hashes, pruebas y conteos, no por imprimir constantes.
- Los reportes previos, `lagacy_loto/`, `repo_ref/`, JSON, eliminación ajena y demás cambios preexistentes no se alteran.
- Sin instalaciones, commits, push ni PR. El bloqueo RDD previo no se omite ni se resuelve cambiando política; cualquier reducción de candidato que requiera operaciones Git se propone al usuario por separado.

## Verification

Test-first: observar RED conductual para helper y adaptadores, luego GREEN con implementación. Documentación pasiva: revisión estructural/enlaces, sin inventar RED para prosa.

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest test_quiniela_sim.py test_quiniela_compare.py test_simuladores.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 py -B -m ruff check --no-cache quiniela_compare.py test_quiniela_compare.py test_simuladores.py simuladores
QUINIELA_RUN_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest test_simuladores.py -q -p no:cacheprovider
```

Criterios de aceptación:

- [ ] Existen14 carpetas, cada una con su script y README; índice completo.
- [ ] Correr desde la propia carpeta funciona sin instalar nada ni editar rutas.
- [ ] Cada script ejecuta solo su escenario histórico, no MC ni grilla completa.
- [ ] Los14 reproducen los conteos y netos redondeados de la tabla con entradas verificadas.
- [ ] Las pruebas existentes siguen aprobadas; nuevas pruebas y Ruff aprobados.
- [ ] Datos/rankings/reportes originales intactos; ningún resultado impreso está hardcodeado como cálculo.
- [ ] Revisiones independientes reportan alcance real y límites; no afirmar revisión nativa aprobada si sigue bloqueada.

## Secuencia de implementación tras aprobación

1. Registrar ODD nuevo para este alcance y evidencia inicial; implementar helper con tests.
2. Implementar runner,14 adaptadores y documentación; tests de rutas y configuración.
3. Ejecutar integración real de14 escenarios secuencialmente y revisión independiente; reportar discrepancias sin ajustar resultados.

Es probable superar400 líneas por documentación y28 archivos repetitivos. Recomendar revisión en unidades acotadas (helper/tests, runner/adaptadores, documentación), o PRs encadenadas solo con autorización posterior; este plan no autoriza commits ni PRs.

## Out of Scope

App gráfica, nuevas estrategias, apuestas reales, nuevos datos, Monte Carlo por carpeta, entrenamiento de modelos, scripts autosuficientes con copias de todo el motor, actualización de las cifras históricas o mantenimiento destructivo de autoridad RDD.

## Estado de fases

- Fase1 exploración: completada mediante scout de solo lectura sobre5 archivos relevantes.
- Fase2 aclaración: sin preguntas pendientes; omitida la ronda de preguntas porque el resumen identifica las14 filas y el usuario pidió cubrirlas todas.
- Fase3 plan: completada en este archivo.
- Fase4 ejecución: no iniciada; espera aprobación explícita del usuario.
