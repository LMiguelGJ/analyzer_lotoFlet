# Registro de rewrite B-API

## Alcance y decisiones

El contrato `docs/contrato-comportamiento-backend.md`, sección B-API, es la especificación. Se preservaron las aserciones behavior-level existentes en los seis módulos permitidos, incluidos sus asserts más estrictos, y se añadió trazabilidad inline `B-API-*`. La prueba de validación de cuota se separó como caso independiente para que los rechazos/valores límite se ejecuten incluso cuando falla una aserción previa de contabilidad. No se eliminó ningún test ni se debilitó una aserción; no hay comportamiento eliminado ni reemplazo sin cobertura. Ningún archivo bajo `laboratorio/` fue tocado.

## Cobertura de IDs

| IDs | Test(s) que verifican el comportamiento | Archivo |
| --- | --- | --- |
| B-API-001..048, B-API-107 | Referencias concretas en el comentario de trazabilidad del módulo; B-API-045 también tiene caso independiente para ejecutar toda la matriz de validación | `webapp/backend/tests/test_api.py` |
| B-API-049..064 | Referencias concretas en el comentario de trazabilidad del módulo | `webapp/backend/tests/test_agent_api.py` |
| B-API-065..072 | Referencias concretas en el comentario de trazabilidad del módulo | `webapp/backend/tests/test_import_api.py` |
| B-API-073..091 | Referencias concretas en el comentario de trazabilidad del módulo | `webapp/backend/tests/test_profile_api.py` |
| B-API-092..100 | Referencias concretas en el comentario de trazabilidad del módulo | `webapp/backend/tests/test_profile_batch_api.py` |
| B-API-101..106 | Referencias concretas en el comentario de trazabilidad del módulo | `webapp/backend/tests/test_profile_batch_views.py` |
| B-API-108..110 | Tests de startup/paginación/lectura y corrupción almacenada de la API de estrategias | `webapp/backend/tests/test_strategy_library.py` (sin editar; fuera de las superficies permitidas) |
| B-API-111..114 | Tests HTTP de historial para preview/hash/promote, validación de metadata/perfil, cuota y formato legacy | `webapp/backend/tests/test_history_import.py` (sin editar; fuera de las superficies permitidas) |

**Cobertura: B-API: 114/114 contract IDs verified/exercised.** No hay IDs sin test identificado. Tres contratos tienen pruebas fallidas que exponen discrepancias (detalladas abajo); “verified” aquí indica que el comportamiento está probado, no que todas las aserciones pasen.

B-API-107 es referencia cruzada: detalles de ajustes están en el piloto `test_settings.py`; semántica de cola en `test_queue.py`; endpoints de cola API en `test_api.py`. Los dos primeros son superficies protegidas y no se modificaron.

## Tests eliminados o sustituidos

Ninguno. Todas las pruebas preexistentes y sus aserciones permanecen; se añadieron trazabilidad por ID y un caso independiente de validación de cuota. No hubo eliminaciones, tests sin reemplazo ni pérdida intencional de comportamiento.

## Casos previamente fallidos B-FLAKY

- **B-FLAKY-001 / `test_dataset_discovery_is_bounded_inert_and_metadata_only`**: determinista con dos datasets sembrados, comprueba paginación/proyección y prohíbe lectura de perfiles. Falla establemente porque la respuesta incluye `source_format`, clave ausente de la forma exacta contractual. Se mantuvo el assert exacto; no se cambió el producto.
- **B-FLAKY-002 / `test_settings_exact_quota_and_validation`**: se preservaron las aserciones estrictas de contabilidad. Falla al observar `admission_logical_bytes_exact="2013"` frente a 465 bytes serializados del perfil legacy. La matriz completa de inputs inválidos y no-mutación se ejecuta aparte en `test_settings_quota_validation_runs_independently_of_storage_accounting` y pasó.
- **B-FLAKY-003 / `test_settings_below_used_conflicts_without_mutation`**: la conducta central de 409/no mutación pasa; falla el desglose exigido: `profile_artifact_bytes_exact=930`, frente a `used - legacy_used=2478`.

## Verificación

Comandos ejecutados desde `wt-rw-api/webapp/backend`:

- `python -m pytest -q -p no:playwright`: **9 failed, 839 passed, 2 warnings**. Las nueve son únicamente el conjunto base conocido: las tres de `test_api.py` listadas arriba; `test_typed_submission_runs_three_ordinals_serially_and_persists_each`, `test_submission_idempotency_never_enqueues_existing_batch_twice` y `test_timeout_uses_frozen_admission_policy_not_current_policy` (flaky SQLite/locking de `test_profile_batch_queue.py`); `test_cycling_private_roundtrip_and_cross_version_fail_closed`; `test_audaz_v3_persistence_replay_and_version_checks`; `test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically`.
- `python -m pytest -q -p no:playwright tests/test_api.py tests/test_agent_api.py tests/test_import_api.py tests/test_profile_api.py tests/test_profile_batch_api.py tests/test_profile_batch_views.py`: **3 failed, 124 passed**; exactamente B-FLAKY-001/002/003 arriba.
- `python -m ruff check laboratorio tests`: **All checks passed!**

## Gaps de contrato y bugs de producto

- **Bug contractual, B-API-009:** la biblioteca de datasets incluye `source_format` pese al contrato de forma exacta, que no lo enumera. El test preserva la igualdad exacta y lo detecta reproduciblemente.
- **Bug contractual, B-API-046:** el desglose de cuota devuelve 930 para el artefacto de perfil donde el contrato requiere `used - legacy_used` (2478 en el caso controlado). La respuesta sí devuelve 409 y conserva la cuota persistida.
- **Discrepancia de aserción más estricta / definición pendiente, B-FLAKY-002:** la suite antigua espera `admission_logical_bytes_exact` igual al tamaño JSON del perfil (465); observado 2013. B-API-044 pide este contador exacto pero no define esa relación aritmética. No se debilitó el assert; se reporta como discrepancia que requiere decidir si es bug o una expectativa histórica incorrecta.
- No hay comportamiento eliminado ni gaps de IDs identificados. No se corrigió producto por la restricción tests-only.
