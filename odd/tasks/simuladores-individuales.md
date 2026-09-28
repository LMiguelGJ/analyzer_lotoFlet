# ODD — Simuladores individuales Quiniela

## Autorización y alcance

Usuario aprobó ejecutar `.pi/plans/simuladores-individuales-quiniela.md` tal cual usando ODD. Releído íntegramente. Crear los14 escenarios de la tabla, compartiendo motor e insumos, sin recalcular modelos ni alterar resultados esperados.

## Restricciones

Sin instalaciones, commits, push ni PR. Preservar JSON, rankings, legado, repo_ref e informes. Un escritor por vez, test-first para comportamiento. Revisión nativa anterior bloqueada por tamaño: no declarar aprobación nativa ni reparar autoridad automáticamente.

## Estado inicial

Git en rama stage: solo eliminación ajena ` D lottery-predictability-monte-carlo`; preservar. Los archivos previos del simulador ya no aparecen sin seguimiento. Nuevos cambios propios comienzan con este registro.

## Tareas

- [x] SI-1 — Helper histórico para una sola combinación, pruebas RED/GREEN y revisión.
- [x] SI-2 — Runner compartido,14 ejecutables y README, índice y pruebas de rutas/configuración.
- [x] SI-3 — Integración real secuencial de14 escenarios, preservación de hashes y revisión independiente.

## Evidencia

SI-1 implementado: RED15 fallos por helper ausente; GREEN16 pruebas enfocadas, Ruff limpio según escritor. Verificador independiente muliydta-j-5geb en curso.

Cambio de entorno confirmado: `test_quiniela_sim.py` no existe y el antiguo `test_quiniela_compare.py` tampoco estaba versionado/presente; el escritor creó este último con16 pruebas nuevas. El comando conjunto original terminó exit4 sin ejecutar pruebas. Se autorizó la suite enfocada disponible; no afirmar regresión de las58 pruebas previas ni restaurar archivos ajenos automáticamente.

SI-2 completado: runner,14 ejecutables con README e índice. RED4 fallos por paquete ausente; GREEN24 pruebas y1 integración opt-in omitida. Equivalencia sintética contra historical_rows real para familia y paridad cierra la brecha de SI-1. Documentos existentes ahora viven en docs/; enlaces comprobados allí.

SI-3 ejecutado por padre: `QUINIELA_RUN_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest test_simuladores.py -q -p no:cacheprovider` →9 passed en76,05s. Incluye14 subprocesos secuenciales desde sus carpetas, conteos/netos/tasas idénticos a referencias congeladas y hashes de JSON/NPZ/resumen/informe comparativo preservados.

Revisión independiente final sin bloqueos:24 passed,1 skipped y Ruff limpio; revisó runner/helper,14 configuraciones,READMEs/enlaces y equivalencia histórica. No repitió integración pesada; ese resultado fue observado directamente por padre. Las58 pruebas antiguas no se afirman. Importar adaptadores puede insertar raíz en sys.path, pero no ejecuta simulación.

Comprobación final del padre: git diff --exit-code sobre docs/informe_quiniela_sim.md, docs/informe_quiniela_comparacion.md, docs/resumen_resultados_quiniela.md, chance_express_history.json, repo_ref y lagacy_loto sin diferencias. El informe original no estaba incluido en el snapshot de hashes de integración, pero su diferencia Git final es nula. Estado final: solo helper modificado y nuevos archivos propios; eliminación ajena intacta. Sin instalaciones/commits/push. Revisión nativa no evaluable; no se declara aprobación nativa.
