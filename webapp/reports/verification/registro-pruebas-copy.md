# Registro de pruebas copiadas

## Reescritura backend — B-SET

Inventario de tests sustituidos durante el piloto. Cada conducta retirada conserva una aserción en la suite reescrita; los casos paramétricos se enumeran por su id de función y sus valores representativos.

| Test id anterior | Conducta verificada | Cobertura nueva |
|---|---|---|
| `test_app.py::test_production_static_spa_and_api_isolation` | SPA de producción, assets, HEAD, rutas API aisladas | `test_app.py::test_production_static_spa_and_api_isolation` (B-SET-011) |
| `test_app.py::test_profile_creation_direct_navigation_serves_only_the_spa_route` | Ruta SPA de perfil exacta y variantes 404 | misma conducta, reescrita (B-SET-012) |
| `test_app.py::test_batch_session_direct_navigation_serves_only_the_spa_route` | Ruta SPA de sesión con/sin query y variantes 404 | misma conducta, reescrita (B-SET-012) |
| `test_app.py::test_datos_direct_navigation_serves_only_the_spa_route` | Ruta SPA `/datos` exacta | misma conducta, reescrita (B-SET-012) |
| `test_app.py::test_static_never_leaks_outside_build` | traversal/symlink y guardias locales | misma conducta, reescrita (B-SET-013) |
| `test_app.py::test_missing_build_fails_production_startup_but_api_factory_remains_usable` | build requerido solo al servir frontend | misma conducta, reescrita (B-SET-014) |
| `test_app.py::test_settings_paths_are_absolute_and_cwd_independent` | rutas absolutas independientes del cwd | misma conducta, reescrita (B-SET-015) |
| `test_app.py::test_browser_only_after_own_server_started_and_once` | navegador solo al iniciar servidor propio, una vez | misma conducta, reescrita (B-SET-016) |
| `test_app.py::test_port_busy_never_creates_or_opens_server` | puerto ocupado no abre navegador | misma conducta, reescrita (B-SET-017) |
| `test_app.py::test_frozen_inputs_fail_before_browser_opens` | entrada congelada ausente detiene el arranque | misma conducta, reescrita (B-SET-018) |
| `test_app.py::test_corrupt_frozen_input_refuses_startup` | hash congelado alterado detiene el arranque | misma conducta, reescrita (B-SET-018) |
| `test_app.py::test_real_uvicorn_opens_once_after_owned_listener_is_ready` | listener propio listo antes de abrir browser | misma conducta, reescrita (B-SET-019) |
| `test_app.py::test_windows_launcher_has_foreground_and_failure_guards` | guardas del lanzador Windows | misma conducta, reescrita (B-SET-020) |
| `test_settings.py::test_explicit_default_environment_quota_is_still_read_only` | origen explícito aunque la cuota sea el default | `test_settings.py::test_explicit_default_environment_quota_is_still_read_only` (B-SET-001) |
| `test_settings.py::test_manual_settings_preserve_legacy_override_and_can_opt_into_default` | compatibilidad y validación de `quota_explicit` | `test_settings.py::test_manual_quota_provenance_is_legacy_compatible_and_validated` (B-SET-002) |
| `test_settings.py::test_defaults_produce_the_quiniela_80_game` | juego default global Q80 | `test_settings.py::test_defaults_produce_the_quiniela_80_game` (B-SET-003) |
| `test_settings.py::test_environment_configures_a_three_position_game` | entorno configura juego de 3 posiciones | `test_settings.py::test_environment_configures_three_position_game` (B-SET-004) |
| `test_settings.py::test_repeats_accepts_flag_spellings[value/expected]` | flags `1`, `TRUE`, `0` | `test_settings.py::test_environment_repeats_flag_spellings[value/expected]` (B-SET-005) |
| `test_settings.py::test_bad_game_environment_is_rejected[name/value/message]` | errores de entorno identifican variable/regla | `test_settings.py::test_invalid_game_environment_names_the_invalid_rule` (B-SET-006) |
| `test_settings.py::test_replace_keeps_the_configured_game` | replace conserva reglas | `test_settings.py::test_replace_preserves_configured_game` (B-SET-007) |
| `test_settings.py::clean_game` | restaura el singleton global entre tests | `test_settings.py::clean_game` (B-SET-008) |
| `test_adapter.py::test_parse_orders_days_and_hours_and_skips_empty_days` | orden cronológico, días vacíos y dtype | misma conducta, reescrita (B-SET-021) |
| `test_adapter.py::test_identical_duplicates_merge_and_conflicts_stop_the_load` | duplicado idéntico fusionado y conflicto rechazado | misma conducta, reescrita (B-SET-022) |
| `test_adapter.py::test_malformed_history_is_rejected[case]` | rechazo de cada historial malformado | misma conducta, reescrita (B-SET-023) |
| `test_adapter.py::test_missing_files_and_changed_hashes_fail_with_clear_errors` | faltantes/hash incorrecto y modo sin hash | misma conducta, reescrita (B-SET-024) |
| `test_adapter.py::test_rankings_align_with_history_rows` | alineación, forma/dtype y familia no disponible | misma conducta, reescrita (B-SET-025) |
| `test_adapter.py::test_rankings_use_the_verified_snapshot_after_path_replacement` | snapshot no releído tras reemplazo en disco | misma conducta, reescrita (B-SET-026) |
| `test_adapter.py::test_misaligned_or_invalid_rankings_are_rejected` | timestamps, orden y permutación validados | misma conducta, reescrita (B-SET-027) |
| `test_adapter.py::test_parity_cache_is_reused_by_a_fresh_instance` | instancia nueva reutiliza caché | misma conducta, reescrita (B-SET-028) |
| `test_adapter.py::test_parity_cache_recovers_from_shape_valid_changed_votes` | votos válidos pero alterados se recomputan | misma conducta, reescrita (B-SET-029) |
| `test_adapter.py::test_parity_cache_recomputes_when_provenance_is_wrong[field]` | provenance errónea se recomputa | misma conducta, reescrita (B-SET-030) |
| `test_adapter.py::test_frozen_history_matches_the_reference_loader` | fingerprint del historial congelado | misma conducta, reescrita (B-SET-031) |
| `test_adapter.py::test_frozen_rankings_and_parity_votes_match_the_reference` | fingerprint y caché de rankings/votos | misma conducta, reescrita (B-SET-032) |

### Tests nuevos y contratos agregados

- `test_settings.py::test_data_directory_and_real_data_skip_are_isolated` verifica el aislamiento de `data_dir` y el skip de `real_data` (B-SET-009).
- `test_settings.py::test_quota_default_and_environment_validation` amplía cobertura de cuota desde `test_quota.py` (B-SET-010); ese archivo no fue editado.
- `test_game_rules.py::test_game_rule_ceilings_preserve_supported_games` cubre techos y juegos válidos (B-NEW-001).
- `test_game_rules.py::test_game_rules_editor_persists_and_is_loaded_on_restart` y `test_game_rules_editor_guards_mutation_and_validates_rules` cubren persistencia, fila id=1, precedence en startup, Origin y validación (B-NEW-002).
- No se elimina ningún comportamiento sin reemplazo.

### Gaps del contrato preservados

`test_profile_creation_direct_navigation_serves_only_the_spa_route` rechazaba también `/experimentos/nuevo/other` y `/experimentos/other/perfil`; esas variantes adicionales siguen rechazadas en la prueba reescrita, aunque no están enumeradas en B-SET-012. Son un gap documental de alcance bajo.

### Convenciones del piloto

- Un test lleva el ID contractual en comentario contiguo; casos de una misma familia se parametrizan.
- `tests/_contract_ids.py` exporta listas explícitas y tuplas de IDs por área.
- Las pruebas de settings guardan/restauran el juego global y usan directorios aislados; los casos de datos congelados conservan `real_data`.
- Los contratos añadidos quedan identificados por separado en `B_NEW_GAME_RULES_IDS`.

### Cobertura y verificación

| Contratos | Resultado | Prueba principal |
|---|---:|---|
| B-SET-001..010 | 10/10 | `test_settings.py` |
| B-SET-011..020 | 10/10 | `test_app.py` |
| B-SET-021..032 | 12/12 | `test_adapter.py` |
| **B-SET total** | **32/32** | `tests/_contract_ids.py` |
| B-NEW-001..002 | cubiertos como pruebas; fallan contra esta base | `test_game_rules.py` |

- `python -m pytest -q -p no:playwright tests/test_app.py tests/test_settings.py tests/test_adapter.py tests/test_game_rules.py`: 47 passed, 3 failed (las tres pruebas B-NEW descritas abajo).
- `python -m pytest -q -p no:playwright`: 816 passed, 14 failed; 8 fallos coinciden con la lista conocida, 3 fallos adicionales de locking en `test_profile_batch_queue.py` y los 3 fallos nuevos de B-NEW. La primera ejecución terminó por timeout a 180s; la repetición completa terminó en 236.03s.
- `python -m ruff check laboratorio tests`: limpio.
- Bloqueo de aceptación: esta revisión de trabajo carece de implementación de los techos `make_game` y del endpoint `/api/v1/settings/game`; por eso B-NEW-001 no lanza `ValueError` en valores excesivos y las dos pruebas B-NEW-002 reciben 404. La restricción tests-only impide corregir la fuente. No se han suprimido ni debilitado estas pruebas.
