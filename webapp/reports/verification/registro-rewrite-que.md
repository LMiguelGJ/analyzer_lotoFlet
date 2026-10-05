# Registro de reescritura B-QUE

## Resultado

**B-QUE: 50/50 contract IDs verified.** La especificación aplicada es `docs/contrato-comportamiento-backend.md`, sección 4; se preservaron también las intenciones B-FLAKY-004..007. Los IDs están citados junto a sus tests.

| Archivo | IDs verificados | Total |
|---|---|---:|
| `webapp/backend/tests/test_queue.py` | B-QUE-001..026 | 26/26 |
| `webapp/backend/tests/test_profile_queue.py` | B-QUE-027..038 | 12/12 |
| `webapp/backend/tests/test_profile_batch_queue.py` | B-QUE-039..050 | 12/12 |

**Tests eliminados:** ninguno. Los tests existentes ya cubrían el comportamiento contractual; se conservaron y etiquetaron en lugar de eliminar contratos. No quedan IDs B-QUE sin cubrir.

## Determinismo / fallos previos

- B-FLAKY-004 / B-QUE-048: se difirió explícitamente el enqueue hasta cambiar la política persistida, de modo que el cambio sucede después de la admisión pero antes de procesar el lote. Así se evita competir con escrituras de la cola y se prueba la política congelada.
- B-FLAKY-005, B-FLAKY-006 y B-FLAKY-007: el polling del archivo batch consulta únicamente el estado de la fila del experimento (sin cargar/autenticar el dataset mediante una segunda conexión), tolera bloqueos SQLite transitorios y usa una pausa de 100 ms. Esto evita que las lecturas de observación compitan continuamente con las escrituras del worker. Los casos de compensación/reintento, idempotencia y resultado corrupto siguen verificando sus estados/resultados contractuales.
- No se observaron bugs de producto B-QUE que requirieran cambios en `laboratorio/` (fuera de alcance).

## Validación

- `python -m pytest -q -p no:playwright tests/test_queue.py tests/test_profile_queue.py tests/test_profile_batch_queue.py`: **62 passed**.
- `python -m pytest -q -p no:playwright`: **841 passed, 6 failed**. Los seis fallos coinciden exactamente con el conjunto previo conocido: `test_dataset_discovery_is_bounded_inert_and_metadata_only`, `test_settings_exact_quota_and_validation`, `test_settings_below_used_conflicts_without_mutation`, `test_cycling_private_roundtrip_and_cross_version_fail_closed`, `test_audaz_v3_persistence_replay_and_version_checks`, `test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically`. Ninguno está en los archivos B-QUE modificados.
- `python -m ruff check laboratorio tests`: **All checks passed!**

## Supuestos y alcance

El documento de contrato es la fuente normativa (A2/A5). Se considera cubierta una regla cuando su test mantiene las aserciones conductuales enumeradas para el ID; no se usa el número de tests como medida de cobertura. Sin cambios de producto ni de archivos fuera de las superficies autorizadas.
