# Registro de reescritura B-DOM

## Alcance y método

Se preservó el conjunto de aserciones existente y se hizo explícita su trazabilidad con citas `B-DOM-*` en los docstrings de los tests. No se borraron tests: al cotejar sus fuentes/nombres con el contrato, no hubo una eliminación que requiriera reemplazo. Se conservan las aserciones más estrictas que ya existían. `B-NEW-001` sigue cubierto en `tests/test_contracts.py` y `tests/test_game_rules.py`; no se modificó `test_game_rules.py`.

## Cobertura por archivo

| Archivo | IDs B-DOM cubiertos |
|---|---|
| `tests/test_contracts.py` | B-DOM-001–023 |
| `tests/test_selection.py` | B-DOM-024–031 |
| `tests/test_metrics.py` | B-DOM-032–033 |
| `tests/test_trajectory.py` | B-DOM-034–037 |
| `tests/test_session.py` | B-DOM-038–051 |
| `tests/test_batch_admission.py` | B-DOM-052–064 |
| `tests/test_profile_request.py` | B-DOM-065–072 |
| `tests/test_profile_request_v2.py` | B-DOM-073–076 |
| `tests/test_profile_request_v3.py` | B-DOM-077 |
| `tests/test_profile_request_v4.py` | B-DOM-078 |
| `tests/test_profile_result.py` | B-DOM-079–088 |
| `tests/test_profile_result_v2.py` | B-DOM-089–094 |
| `tests/test_profile_result_v3.py` | B-DOM-095–096 |
| `tests/test_profile_result_v4.py` | B-DOM-097–098 |
| `tests/test_profile_staking.py` | B-DOM-099–114 |
| `tests/test_profile_reference_staking.py` | B-DOM-115–120 |
| `tests/test_profile_capabilities.py` | B-DOM-121–124 |
| `tests/test_profile_engine.py` | B-DOM-125–135 |
| `tests/test_profile_session.py` | B-DOM-136–170 |
| `tests/test_profile_v5.py` | B-DOM-171–181 |
| `tests/test_strategy_library.py` | B-DOM-182–186 |

**B-DOM: 186/186 contract IDs verificados/citados.** Sin IDs descubiertos sin cobertura y sin contract gaps identificados durante este cotejo. `tests/test_profile_strategy.py` no existe en el worktree; los contratos B-DOM de estrategia (182–186) están implementados en `tests/test_strategy_library.py`, que es la fuente indicada por el contrato. No se cambió esa organización.

## Eliminaciones y reemplazos

- Tests eliminados: ninguno.
- Tests reemplazados por comportamiento equivalente: ninguno; se mantuvieron las aserciones existentes y se añadió trazabilidad inline a cada grupo de comportamiento.
- Cambios de producto: ninguno (tests-only).

## Verificación observada

- Suite enfocada de los archivos existentes del lane: **451 passed**.
- Suite backend completa: **840 passed, 7 failed**, total **847**. Los siete fallos observados pertenecen al conjunto conocido: `test_dataset_discovery_is_bounded_inert_and_metadata_only`, `test_settings_exact_quota_and_validation`, `test_settings_below_used_conflicts_without_mutation`, `test_timeout_uses_frozen_admission_policy_not_current_policy`, `test_cycling_private_roundtrip_and_cross_version_fail_closed`, `test_audaz_v3_persistence_replay_and_version_checks`, `test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically`.
- Ruff: limpio.
