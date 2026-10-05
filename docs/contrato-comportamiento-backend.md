# Contrato de comportamiento de la suite backend

Fuente: `webapp/backend/tests/*.py`. Documento de extracción para reescribir la suite sin perder conocimiento codificado ("cobertura igual o mejor", [A5]).

Supuestos: [A1] se excluyen `.git/gentle-ai/candidate-views/**` y `repo_ref/**`. [A2] Las reglas se infieren de las aserciones de los tests; no se ejecutó la suite. [A3] Un test puede aparecer en más de un área si cubre dos contratos (p. ej. `test_queue.py`, `test_settings.py`).

## Áreas
1. B-API · 2. B-DOM · 3. B-STO · 4. B-QUE · 5. B-SET

---

## 1. B-API — Contratos de API

### [B-API-001] Catálogo y lectura sin recálculo
- **Regla**: `GET /api/v1/catalog` devuelve `starting_draws` (rankeados) y `coverages == [1,5,10,20,25,30,40,50]`; crear (201) y leer experimentos nunca recalcula `run_session`.
- **Fuente**: test_api.py:test_catalog_and_create_read_without_recalculation
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-002] Paginación de experimentos con 422 en límites
- **Regla**: `GET /experiments` rechaza con 422 `offset<0` y `limit>100`; `total` refleja el conteo real.
- **Fuente**: test_api.py:test_catalog_and_create_read_without_recalculation
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-003] Catálogo conserva forma legacy de `game` y no incrusta perfiles
- **Regla**: `catalog["game"]` tiene exactamente las claves `name, numbers, positions, prizes, allows_repeats, minimum_stake`; no existe clave `profiles` y el catálogo no lee `list_game_profiles` (sin lectura no acotada).
- **Fuente**: test_api.py:test_profile_catalog_is_bounded_inert_and_keeps_legacy_catalog_shape
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-004] `/catalog/profiles` paginado (total/offset/limit/items) y ordenado
- **Regla**: lista perfiles paginados; orden: perfiles custom por revisión ascendente y el legacy `legacy_quiniela_80_profile` al final; offset más allá del total devuelve `items == []`; `offset<0`, `limit=0` y `limit>100` → 422; POST → 422 (validación de body antes que 405).
- **Fuente**: test_api.py:test_profile_catalog_is_bounded_inert_and_keeps_legacy_catalog_shape
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-005] Cada item de perfil expone `profile`, `profile_sha256`, `execution_supported`
- **Regla**: `profile` es el `model_dump(mode=json)`, `profile_sha256 == profile_sha256(profile)`; `execution_supported` es True solo para el perfil legacy y False para perfiles custom.
- **Fuente**: test_api.py:test_profile_catalog_is_bounded_inert_and_keeps_legacy_catalog_shape
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-006] Bloque `profile_execution` de capacidades por perfil
- **Regla**: incluye `ready`, `selector_capabilities` (`static-numbers/v1`, `seeded-random/hash-sha256-v1`), `staking_capabilities` (`flat-per-number/v1`, `q80-first-prize-cycling/v1`, `profile-audaz/v1`, `profile-recovery-ladder/v1`), `entry_policies [all_rows/v1]`, `settlements [all,best]`, `requires_compatible_dataset True`, `audaz_compatibility` y `recovery_compatibility` (con `maximum_compatible_coverage = max_coverage`, regla "selected coverage must be strictly less than multiplier[0]" y parámetros `target_margin, rounds, end_mode`).
- **Fuente**: test_api.py:test_profile_catalog_is_bounded_inert_and_keeps_legacy_catalog_shape
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-007] Plantillas de perfil conocidas e inertes
- **Regla**: `templates` (solo en la primera página) contiene `Original70` (`universe_size 100`, multiplicadores 70,8,4,2,1, provenance `repo_ref/strategy_tests/rules.py`, `missing_fields` incluye `maximum_stake`) y `User example 60/10/5` (positions 3, repeats, DOP, minimum_stake 1, `missing_fields` incluye `max_exposure`); ambas `execution_supported False`.
- **Fuente**: test_api.py:test_profile_catalog_is_bounded_inert_and_keeps_legacy_catalog_shape
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-008] `/datasets` vacío, acotado y solo metadatos
- **Regla**: sin datasets devuelve `{total:0, offset:0, limit:20, items:[]}`; el límite por defecto es 20; la lista no lee perfiles (`list_game_profiles`).
- **Fuente**: test_api.py:test_dataset_discovery_is_bounded_inert_and_metadata_only
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-009] Item de dataset: forma exacta sin filtrar procedencia privada ni bytes
- **Regla**: cada item contiene exactamente `dataset_sha256, source_sha256, created_at, source_id, source_kind, source_revision, profile_id, profile_revision, profile_sha256, positions, universe_size, records_total, first_draw, last_draw, clock{mode,zone}, execution_supported, profile_execution`; nunca contiene la procedencia privada, `raw_bytes` ni `canonical_json`; paginación offset/limit; `offset<0`, `limit 0/101` → 422; POST → 405.
- **Fuente**: test_api.py:test_dataset_discovery_is_bounded_inert_and_metadata_only
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-010] Dataset sin perfil ejecutable reporta `ready False` y compatibilidad 0
- **Regla**: para dataset de perfil de prueba, `profile_execution.ready False`, `staking_capabilities == [flat-per-number/v1]`, `audaz/recovery available False` y `maximum_compatible_coverage 0`.
- **Fuente**: test_api.py:test_dataset_discovery_is_bounded_inert_and_metadata_only
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-011] `starting-draws` paginado conserva paginación legacy y salta por fecha
- **Regla**: `GET /catalog/starting-draws` pagina los sorteos rankeados (`total, offset, limit, items`, default limit 100); con `date=YYYY-MM-DD` filtra al día y permite saltar a páginas tardías; offset sobre el total → `items []`.
- **Fuente**: test_api.py:test_starting_draw_date_jumps_to_late_ranked_page_without_changing_legacy_pagination
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-012] Búsqueda por fecha usa acceso indexado (no lineal)
- **Regla**: con 12 000 etiquetas, la búsqueda por fecha tardía lee <100 elementos de labels/row_ids (bisección).
- **Fuente**: test_api.py:test_starting_draw_late_date_uses_indexed_access_not_linear_page_scanning
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-API-013] Fecha excluye sorteos no rankeados y `/availability` reporta conteos
- **Regla**: `items` solo incluye sorteos rankeados del día; `/starting-draws/availability?date=` devuelve `{date, history_total, ranked_total}` (ceros en fechas fuera de rango o sin rankeados, `history_total` > 0 aun si `ranked_total` 0).
- **Fuente**: test_api.py:test_starting_draw_date_excludes_unranked_and_reports_bounded_history_availability
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-014] `date` solo ISO calendario válido
- **Regla**: `2025-02-30`, `2025-1-02`, `20250102`, `2025-01-02T00:00`, `oops` → 422 en `starting-draws` y `availability`.
- **Fuente**: test_api.py:test_starting_draw_date_rejects_non_iso_or_invalid_calendar_day
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-015] Snapshot de perfil aditivo en respuestas guardadas
- **Regla**: detalle y lista de experimentos incluyen `profile` (snapshot legacy: `best_rule first-match/v0`) además de `request` sin cambios y `sources.code_version`.
- **Fuente**: test_api.py:test_experiment_profile_snapshot_is_additive_on_saved_responses
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-016] Búsqueda de experimentos: filtro, orden, paginación y escape de comodines
- **Regla**: `name_contains` es insensible a mayúsculas y trata `%`/`_` literalmente; `sort` ∈ name/status/created_at (default más reciente primero), `order` asc/desc, `status` filtra; `created_at` serializado en UTC y `null` si falta (se ordena al final); offset grande devuelve `items []` con total correcto.
- **Fuente**: test_api.py:test_experiment_search_filters_orders_paginates_and_serializes_created_at
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-017] Parámetros de lista inválidos → 422
- **Regla**: `sort=request_json`, `order=sideways`, `status=goal`, `limit=101`, `offset=-1`, `name_contains` de 81 caracteres → 422.
- **Fuente**: test_api.py:test_experiment_search_filters_orders_paginates_and_serializes_created_at
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-018] Seed máximo seguro round-trip exacto
- **Regla**: `seed = 2**53-1` se persiste y se lee idéntico; `2**53` → 422.
- **Fuente**: test_api.py:test_max_safe_seed_round_trips_exactly_through_create_and_get
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-019] Seed string o float rechazado con `loc` del campo
- **Regla**: `"9007199254740991"` y `9007199254740991.0` → 422 con `loc [body, request, conditions, seed]`.
- **Fuente**: test_api.py:test_seed_rejects_string_and_float_with_field_loc
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-020] Estrategia duplicada (case-insensitive) con error localizado
- **Regla**: nombres "Una"/"una" → 422 con un único error en `loc [body, request, strategies, 1, name]` (no raíz).
- **Fuente**: test_api.py:test_duplicate_strategy_name_error_is_field_located_not_root
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-021] Payloads inválidos de experimento → 422/400
- **Regla**: 422 si `goal<=capital`, `start_draw` no parseable, `max_bets=0`, `max_minutes<0`, `coverage=3` (no catalogada), campo extra (también en el envelope), >5 estrategias, blend con pesos que no suman 100; start_draw no rankeado (`05:15`) → 400.
- **Fuente**: test_api.py:test_invalid_payload_and_start
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-022] Capital inicial insuficiente rechazado antes de encolar
- **Regla**: para flat/ladder/bold con coverage 50 y capital 49 → 400 con detalle exacto `strategy N (Nombre): initial capital cannot afford the prescribed bet`; no se llama `jobs.submit` y no se persiste nada (incluye lote donde solo la 2ª estrategia falla).
- **Fuente**: test_api.py:test_create_rejects_unaffordable_initial_stake_before_submit; test_create_rejects_later_unaffordable_strategy_without_persisting_batch
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-023] Límite exacto de costo inicial aceptado
- **Regla**: capital == costo inicial (50) → 201 para flat/ladder/bold.
- **Fuente**: test_api.py:test_create_accepts_exact_initial_cost_boundary
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-API-024] Guardia Host: solo `localhost:8765`
- **Regla**: GET con Host `evil.example`, `localhost.evil.example`, `127.0.0.1:9999`, `localhost:8765@evil`, `localhost:8765,evil`, `[::1]:8765`, `localhost:bad` → 403; Host `127.0.0.1:8765` → 200.
- **Fuente**: test_api.py:test_host_origin_guard
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-025] Guardia Origin en mutaciones
- **Regla**: POST exige `Origin` exacto `http://localhost:8765`; 403 para esquema https, host ajeno, `null`, con path, con userinfo, `127.0.0.1`, con `#`, para `Sec-Fetch-Site: cross-site` y para POST sin Origin.
- **Fuente**: test_api.py:test_host_origin_guard
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-026] Proyección de `delta`/`net` desde el capital del request
- **Regla**: en detalle, lista y `/compare`, `result.final_balance`, `delta = final - capital_request` (80→79, 0→−1, 1→0), `net = paid − 1`, `metric_scope == saved_individual_run`; runs pendientes tienen `result null`.
- **Fuente**: test_api.py:test_run_delta_projects_persisted_result_from_request_capital
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-027] Métricas guardadas sin `bets` y sin recálculo
- **Regla**: `result` expone `final_balance, net, return_per_wagered (80.0), roi (79.0), max_drawdown, metric_scope`, y nunca `bets`; no se recalcula `run_session`.
- **Fuente**: test_api.py:test_snapshot_replay_compare_and_confirmed_delete
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-028] Replay paginado
- **Regla**: `/runs/{i}/replay?limit=` devuelve `items[].numbers` y `total`; `limit=101` → 422; run inexistente → 404.
- **Fuente**: test_api.py:test_snapshot_replay_compare_and_confirmed_delete
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-029] Trayectoria con forma y límites
- **Regla**: `/runs/{i}/trajectory` devuelve `points[{source_index,label,balance,replay:"replay?offset=N&limit=1"}]`, `initial_capital`, `total`, `reduction_method "none"`; `max_points` fuera de [4?..2000] (3 y 2001) → 422; run inexistente → 404; run fallido → 409.
- **Fuente**: test_api.py:test_snapshot_replay_compare_and_confirmed_delete; test_mixed_failed_batch_keeps_api_shapes_and_comparison_incomplete
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-030] Borrado exige `confirm_id` exacto
- **Regla**: DELETE de configuración/experimento con `confirm_id` incorrecto → 400; correcto → 204; borrar configuración no altera resultados de experimentos existentes; experimento inexistente → 404.
- **Fuente**: test_api.py:test_snapshot_replay_compare_and_confirmed_delete
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-031] Configuraciones: validación y límites
- **Regla**: crear configuración con campo extra → 422; `GET /configurations?limit=0` → 422; `starting-draws?limit=101` → 422; GET por id existente → 200.
- **Fuente**: test_api.py:test_snapshot_replay_compare_and_confirmed_delete
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-032] Lote mixto fallido mantiene forma y comparación incompleta
- **Regla**: tras runs completed/failed/completed el status del experimento y de `/compare` es `failed`; `/compare` reporta `completed 2`, `requested 3`, `complete False`; el run fallido tiene `result null`; el replay del run completado sigue disponible.
- **Fuente**: test_api.py:test_mixed_failed_batch_keeps_api_shapes_and_comparison_incomplete
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-033] Borrado de experimento activo/running → 409; cancel de HELD
- **Regla**: experimento pendiente o corriendo: DELETE → 409, `start` → 409, `cancel` → 409 antes de recovery; tras `recover_jobs` queda `HELD` y aparece en `queue.held.items`; `cancel` lo pasa a CANCELLED (200) tras lo cual `start` → 409 y DELETE → 204.
- **Fuente**: test_api.py:test_active_delete_refused_and_cancel_held_start; test_running_delete_refused_and_unpersisted_failure_is_truthful
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-034] `/queue` pagina pending y held sin materializar el backlog
- **Regla**: `GET /queue?offset&limit` devuelve `pending` y `held` como `{total, offset, limit, count, items}`; no existe `pending_ids` en la respuesta ni se materializa la lista completa; offset > total → `count 0`; `limit=101` → 422.
- **Fuente**: test_api.py:test_queue_status_pages_pending_and_held_without_materializing_backlog
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-035] `last_failure` veraz y sanitizado
- **Regla**: `last_failure` expone `{experiment_id, persisted, reason (nombre de clase), persistence_error (nombre de clase o null)}`; si la persistencia del fallo falló, `persisted False` y `persistence_error "OSError"`; nunca revela mensajes privados/trazas (`secret`, `private path`).
- **Fuente**: test_api.py:test_running_delete_refused_and_unpersisted_failure_is_truthful; test_queue_failure_is_sanitized_with_persistence_truth
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-036] Capacidad (cuota) → 507 sin insertar; enqueue compensa
- **Regla**: crear con cuota insuficiente → 507 sin experimento persistido; si `enqueue` lanza `QuotaExceeded` → 507 y no queda experimento (compensación).
- **Fuente**: test_api.py:test_capacity_rejects_before_insert_and_enqueue_compensates
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-037] Fallo de arranque y sin reanudación automática
- **Regla**: catálogo ausente → `ValueError("file not found")` al arrancar; un experimento pendiente al reiniciar queda `HELD` (no se reanuda), `active_id None`, y se puede cancelar.
- **Fuente**: test_api.py:test_startup_failure_and_no_auto_resume
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-038] Un único dueño de la cola; arranque manual de HELD
- **Regla**: una segunda app sobre la misma base falla con `RuntimeError("already owns")`; `POST /queue/{id}/start` sobre HELD → 200 y completa; repetir start sobre COMPLETED → 409; el dueño se libera al cerrar la primera app.
- **Fuente**: test_api.py:test_single_queue_owner_and_manual_held_start
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-API-039] Timeout de shutdown retiene propiedad hasta que el coordinador se detiene
- **Regla**: si `shutdown` falla por timeout, el lock de dueño no se libera (otra app → `already owns`) hasta que el hilo termina.
- **Fuente**: test_api.py:test_shutdown_timeout_retains_database_owner_until_coordinator_stops
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-API-040] Fallo de `start` con coordinador vivo retiene propiedad
- **Regla**: si `start` falla tras iniciar el hilo, se invoca shutdown; si el hilo sigue vivo el error final es el de shutdown con `__context__` del fallo original y el dueño se retiene.
- **Fuente**: test_api.py:test_failed_start_with_live_coordinator_retains_owner
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-API-041] Fallo de `start` de la cola llama `shutdown` una vez
- **Regla**: `queue.start()` que lanza propaga el error y `shutdown` se invoca exactamente 1 vez.
- **Fuente**: test_api.py:test_queue_start_failure_reaps
- **Categoría**: concurrencia
- **Riesgo si se pierde**: medio

### [B-API-042] Integración ruta→cola→replay
- **Regla**: POST crea y la cola ejecuta hasta COMPLETED; el replay del run 0 devuelve `total 1`.
- **Fuente**: test_api.py:test_spawned_route_integration
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-043] Catálogo real usa inputs instalados (marcador real_data)
- **Regla**: con datos reales `starting_draws_total > 100`, `starting_draws` trae 100 y la página offset 1 limit 1 coincide con `starting_draws[1:2]`.
- **Fuente**: test_api.py:test_real_catalog_factory_uses_installed_inputs
- **Categoría**: contrato
- **Riesgo si se pierde**: bajo

### [B-API-044] `/settings` GET: cuota exacta como strings y desglose de almacenamiento
- **Regla**: `quota{effective_bytes, persisted_bytes, source (default|persisted|environment), writable}` con enteros como strings; `storage` incluye `limit_bytes`, `sqlite_bytes`, `logical_used_bytes_exact`, `profile_artifact_bytes_exact` (= bytes del perfil legacy), `admission_logical_bytes_exact`, `dataset_artifact_bytes_exact`.
- **Fuente**: test_api.py:test_settings_exact_quota_and_validation
- **Categoría**: contrato
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

### [B-API-045] `PUT /settings`: `quota_bytes` solo string decimal canónico en [1, 2^63−1]
- **Regla**: acepta `"9223372036854775807"`; rechaza (422, `loc [body, quota_bytes]`) 0, bool, float, `2**53` numérico, "", "0", "-1", "+1", "1.0", "1e3", dígitos fullwidth, 20 nueves, `2^63`, "0001", " 1", "1\n", "1_0"; campo extra, body `{}` y body lista → 422; un rechazo no muta el valor persistido.
- **Fuente**: test_api.py:test_settings_exact_quota_and_validation
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-046] Cuota por debajo de lo usado → 409 sin mutar
- **Regla**: `quota_bytes == admission_logical_bytes` → 200; uno menos → 409 y la vista conserva persistido, `logical_used_bytes_exact` (experimentos), `admission_logical_bytes_exact` y `profile_artifact_bytes_exact = used − legacy_used`; `limit_bytes == used`.
- **Fuente**: test_api.py:test_settings_below_used_conflicts_without_mutation
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido.

### [B-API-047] Override por entorno: solo lectura y guardado
- **Regla**: con `LABORATORIO_QUOTA_BYTES` el origen es `environment`, `writable False`, `persisted_bytes` se conserva; PUT → 409 sin cambiar; Origin ajeno, sin Origin o Host ajeno → 403.
- **Fuente**: test_api.py:test_settings_env_override_read_only_and_guarded
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-048] Preferencia de cuota persiste entre apps; `sources`/`connection` son solo lectura
- **Regla**: tras PUT, una app nueva ve `source persisted`, `writable True`; el PUT no altera `sources` ni `connection`; enviar `sources` en el PUT → 422.
- **Fuente**: test_api.py:test_settings_preference_survives_new_app_and_sources_remain_read_only
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-049] Fachada de agente exige bearer; 401 opaco
- **Regla**: `/api/agent/v1/*` sin `Authorization`, con `Bearer malformed` o token incorrecto → 401 (GET y POST, incluso con body vacío y Origin válido); el cuerpo de la respuesta nunca contiene el token.
- **Fuente**: test_agent_api.py:test_agent_facade_auth_allowlist_delegation_and_local_credential
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-050] Allowlist de rutas del agente
- **Regla**: con bearer válido: `catalog` (con `game.name`), `strategies` (paginado) y `strategies/{id}/revisions/{rev}` (con `definition_sha256` igual al del listado) → 200; `execution-policy` → 404; `DELETE /experiments/{id}` sin Origin → 403 y con Origin → 405; POST a `/catalog` → 404/405; la API nativa `/api/v1/catalog` sigue accesible sin bearer.
- **Fuente**: test_agent_api.py:test_agent_facade_auth_allowlist_delegation_and_local_credential
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-051] Credencial local de agente: `POST /settings/agent-credential`
- **Regla**: con Origin válido devuelve `{token}` de ≥40 caracteres; es estable entre llamadas y reinicios de app; el token nunca aparece en `GET /settings`.
- **Fuente**: test_agent_api.py:test_agent_facade_auth_allowlist_delegation_and_local_credential; test_agent_origin_guards_and_credential_stable_across_restart
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-052] Guardias Origin/Host también en el agente
- **Regla**: en `/api/agent/v1`, Origin ajeno o `Sec-Fetch-Site: cross-site` → 403 aun con bearer válido; cabeceras `Host` u `Origin` duplicadas → 403.
- **Fuente**: test_agent_api.py:test_agent_origin_guards_and_credential_stable_across_restart
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-053] `schema_version` no coercible en lotes del agente
- **Regla**: en `/profile-batches` y `/profile-batches/validate`, `schema_version` (de la raíz o de `conditions`) igual a `True`, `1.0` o `"1"` → 422.
- **Fuente**: test_agent_api.py:test_agent_batch_schema_versions_reject_coercible_values
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-054] Lotes del agente reutilizan admisión nativa; validate sin efectos
- **Regla**: `validate` → 200 con `valid True` y `effective_constraints`; `POST /profile-batches` → 201 con `created True`, `batch_admission.effective_constraints` igual al de validate, y encola exactamente una vez.
- **Fuente**: test_agent_api.py:test_agent_batch_facade_reuses_native_admission_and_safe_links
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-055] Enlaces seguros del agente
- **Regla**: `links.self == /api/agent/v1/experiments/{id}` y ningún enlace contiene `/api/v1/` (no filtra rutas nativas).
- **Fuente**: test_agent_api.py:test_agent_batch_facade_reuses_native_admission_and_safe_links
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-056] Idempotencia por `request_id` (cliente) en lotes del agente
- **Regla**: reenviar el mismo cuerpo → 200 con el mismo `id` (sin reencolar), también si el lote ya está completed o cancelled (devuelve ese `status`); cuerpo cambiado con el mismo `request_id` → 409; `GET /profile-batches/by-client-request/{request_id}` (acepta `/` en el id) devuelve `id` y `status` actuales.
- **Fuente**: test_agent_api.py:test_agent_batch_facade_reuses_native_admission_and_safe_links
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-057] Fachada de agente delega idéntica a la nativa
- **Regla**: para `""`, `/compare`, `/runs/0/replay`, `/runs/0/trajectory` la respuesta del agente es JSON idéntico a la nativa (200); replay y trajectory exponen `result_kind == "profile"`; proyecciones de run tienen `metric_scope saved_individual_run` y `delta, net, return_per_wagered, roi, max_drawdown`; `compare.requested == 1`.
- **Fuente**: test_agent_api.py:test_agent_batch_facade_reuses_native_admission_and_safe_links
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-058] Cancelación por el agente de lote HELD
- **Regla**: `POST /api/agent/v1/experiments/{id}/cancel` sobre un lote HELD → 200 y no reencola.
- **Fuente**: test_agent_api.py:test_agent_batch_facade_reuses_native_admission_and_safe_links
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-API-059] Lote corrupto → 409 opaco idéntico en nativa y agente
- **Regla**: si el dataset guardado (bytes alterados) o la identidad de admisión (`row_count` alterado) se corrompen, `""`, `/compare`, `/runs/0/replay`, `/runs/0/trajectory` devuelven 409 con el mismo cuerpo en ambas fachadas, sin detalle interno.
- **Fuente**: test_agent_api.py:test_corrupt_saved_batch_is_opaque_conflict_on_native_and_agent_facades
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-060] Historial vía agente: cuerpo crudo, contexto registrado, límites
- **Regla**: `/api/agent/v1/history/preview` y `/promote` reciben bytes crudos con cabeceras de contexto del perfil (`history_headers`); cuerpo > `MAX_HISTORY_BYTES` → 413; JSON con `path` (entrada de filesystem) → 422; preview → 200 con `promotable True`; promote exige `X-Expected-Dataset-Sha256` igual al hash del preview y devuelve ese `dataset_sha256`; el token no aparece en respuestas.
- **Fuente**: test_agent_api.py:test_agent_history_preview_and_promote_use_raw_body_and_registered_context
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-061] Credencial de agente corrupta falla cerrado
- **Regla**: un archivo `agent-token` inválido hace fallar el arranque de la app (RuntimeError/ValueError/OSError); no se regenera silenciosamente.
- **Fuente**: test_agent_api.py:test_corrupt_agent_credential_fails_closed
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-062] Authorization duplicada → 401
- **Regla**: dos cabeceras `Authorization` (iguales o distintas) → 401 sin eco del token.
- **Fuente**: test_agent_api.py:test_agent_auth_rejects_duplicate_authorization_headers
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-063] Authorization no ASCII → 401 (nunca 500)
- **Regla**: byte `\xff` en `Authorization` produce 401 sin lanzar error de servidor ni reflejar `Bearer`.
- **Fuente**: test_agent_api.py:test_agent_auth_rejects_non_ascii_authorization_without_server_error
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-064] Creación concurrente de credencial publica solo un ganador completo
- **Regla**: `load_or_create_token` con dos creadores concurrentes publica un único token (el del segundo que terminó) en el archivo; ambos devuelven el mismo valor; no quedan archivos temporales al final; durante la carrera el archivo publicado nunca está vacío/parcial.
- **Fuente**: test_agent_api.py:test_concurrent_agent_credential_creation_publishes_only_complete_winner
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-API-065] `/imports/preview`: sin escrituras, muestra acotada, conteos veraces
- **Regla**: preview devuelve 200 con `promotable`, `execution_supported False`, `rows_seen == records_total`, `sample` máximo 20, `dataset_sha256` (64 hex), `source_sha256 == sha256(raw)` y no escribe en `datasets`; con 105 filas inválidas: `promotable False`, `dataset_sha256 null`, `records_total 0`, `error_count 105`, `errors_truncated True`, `errors` ≤ 100, `sample []`.
- **Fuente**: test_import_api.py:test_preview_no_writes_bounded_sample_truthful_counts_and_errors
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-066] `/imports/promote`: gate de hash, idempotencia y fuente distinta retenida
- **Regla**: `expected_dataset_sha256` obligatorio (ausente → 422); hash que no coincide → 409 sin escribir; correcto → 200 con `created True`, `retained_source_sha256 == submitted_source_sha256`, `execution_supported False` y sin `raw_bytes`/`canonical_json`; repetir → `created False`, `duplicate_source_differs False`; mismo dataset con bytes distintos → `created False`, `duplicate_source_differs True`, se conserva el `retained_source_sha256` original y `submitted_source_sha256` difiere; un solo registro en `datasets`.
- **Fuente**: test_import_api.py:test_promote_hash_gate_idempotence_and_distinct_raw_retained
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-067] Validación del envelope de import
- **Regla**: 422 para base64 inválido (`ab==!`, `%%%`, padding extra), `format` desconocido, `source_id` bool, posiciones no string/bool, `clock.mode` bool, `profile.positions` bool, campo desconocido; cuerpos JSON truncados, con clave duplicada o anidamiento excesivo (`[`*1100) → 422.
- **Fuente**: test_import_api.py:test_invalid_envelope_metadata_and_parser_errors
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-068] Errores de parser: preview 200 no promovible, promote 422
- **Regla**: raw inválido (`{`, anidamiento excesivo, hora `25:00`) → preview 200 con `promotable False`; promote con ese raw → 422; nunca se escribe dataset.
- **Fuente**: test_import_api.py:test_invalid_envelope_metadata_and_parser_errors
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-069] Promote: cuota excedida revierte; corrupción opaca
- **Regla**: cuota insuficiente → 409 sin fila persistida; con cuota restaurada → 200; si el dataset almacenado está corrupto, promote → 409 sin revelar `corrupt stored dataset` ni `canonical`, y no se agrega fila.
- **Fuente**: test_import_api.py:test_quota_failure_rolls_back_and_integrity_failure_is_opaque
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-070] Límite del envelope declarado y en streaming
- **Regla**: `Content-Length` declarado > `_IMPORT_ENVELOPE_BYTES` → 413; cuerpo en streaming que excede el límite → 413 (con Content-Length ausente o falso) en preview y promote; Host ajeno, Origin ajeno o ausente → 403; no se escribe nada.
- **Fuente**: test_import_api.py:test_cap_declared_and_streamed_with_missing_or_false_length_and_local_guard
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-071] Límite decodificado (2 MiB) y rutas ajenas sin afectar
- **Regla**: raw decodificado > 2 MiB → 413 en preview y promote; el límite del envelope solo aplica a `/imports`: otra ruta inexistente con body grande responde 404.
- **Fuente**: test_import_api.py:test_decoded_limit_and_other_route_unchanged
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-API-072] Origin debe coincidir con el Host loopback de la app
- **Regla**: con app servida en `127.0.0.1:8765`, Origin `http://127.0.0.1:8765` es aceptado; con app en `localhost:8765` el Origin `127.0.0.1` es rechazado (Origin == host de la solicitud).
- **Fuente**: test_import_api.py:client fixture/PATH; test_api.py:test_host_origin_guard
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-073] Proyección GET de perfil (v1) inerte y discriminada por `request_kind`
- **Regla**: para perfiles con 1, 3 y 5 posiciones, tanto estáticos como `seeded-random`, `GET /experiments/{id}` devuelve `request_kind "profile"`, `request` serializado, `profile`, `display{name,currency,scale,capital,goal,selector_label,staking_label}`, `sources` (`history_id/history_sha256 == dataset_sha256`, `rankings_* ""`, `code_version "profile-v1"`) y nunca reejecuta el motor (`run_profile_session`/`run_session` no se llaman en GET). El item de la lista es idéntico al detalle.
- **Fuente**: test_profile_api.py:test_profile_static_and_random_get_projection_is_inert_and_discriminated
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-074] Run de perfil: `result_kind`, métricas y sin `bets`
- **Regla**: el run completado incluye `ordinal, configuration_id None, status, result_kind "profile", bets_count` y `result{schema_version, profile_id, profile_revision, outcome, collisions, elapsed_draws, bet_draws, wagered, paid, final_balance, delta=final−capital, +financial_metrics}` sin `bets`; `/compare` repite `runs` con `request_kind`, `completed`, `requested`, `complete`.
- **Fuente**: test_profile_api.py:test_profile_static_and_random_get_projection_is_inert_and_discriminated
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-075] Replay de perfil: forma por apuesta, paginado, trayectoria enlazada
- **Regla**: replay devuelve `result_kind profile`, `total = bet_draws`, items `{label, stakes[[n,stake]], results (len = positions), wagered, paid, balance}` (sin `numbers`/`per_number`); `limit=101` → 422; run inexistente → 404; trayectoria con `result_kind profile`, `total`, y `replay == replay?offset=<source_index>&limit=1` por punto.
- **Fuente**: test_profile_api.py:test_profile_static_and_random_get_projection_is_inert_and_discriminated
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-076] `POST /experiments` legacy rechaza request de perfil
- **Regla**: enviar un request de perfil al endpoint legacy `/experiments` → 422 (la sumisión de perfiles tiene su ruta propia).
- **Fuente**: test_profile_api.py:test_profile_static_and_random_get_projection_is_inert_and_discriminated
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-077] Perfil HELD/FAILED: incompleto, sin replay
- **Regla**: un experimento de perfil HELD (tras `recover_jobs`) o FAILED expone run `{status pending|failed, result None, bets_count 0, result_kind profile}`; filtrable por `status`; `/compare` con `completed 0`, `complete False`; replay y trajectory → 409.
- **Fuente**: test_profile_api.py:test_profile_held_and_failed_are_incomplete_without_replay
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-078] Registro público de perfil (`POST /catalog/profiles`) + envío por import + lectura
- **Regla**: registro → 201 con `profile`, `profile_sha256`, `profile_execution.ready True`, `requires_compatible_dataset True` y `execution_supported False`; `POST /experiments/profiles` → 201 `{id, status "pending"}`; el job termina COMPLETED con resultado igual al replay esperado; `request`, `profile`, `request_kind == result_kind == profile`; el registro y el submit se ejecutan fuera del event loop (`asyncio.get_running_loop` lanza).
- **Fuente**: test_profile_api.py:test_public_registration_import_submission_and_completed_read
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-079] Detalle de dataset usa el perfil embebido verificado
- **Regla**: `GET /datasets/{sha}` = item de lista + `profile` canónico; `profile_sha256` es sha256 del JSON canónico (`sort_keys`, separadores compactos, `ensure_ascii False`, `allow_nan False`); `ready False` hasta registrar el perfil, `True` tras registrarlo, `False` de nuevo si el perfil registrado difiere del embebido; sin `records`, `raw_bytes`, `canonical_json` ni `provenance`.
- **Fuente**: test_profile_api.py:test_dataset_detail_and_draws_use_verified_embedded_profile
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-080] `/datasets/{sha}/draws` paginado con filtro `date`
- **Regla**: devuelve `{total, offset, limit (default 100), items[labels]}` en orden cronológico; `date` filtra el día; offset > total → `[]`; `limit` 0/101, `offset -1`, `date` inválida (`2025-02-30`, `2025-9-02`) → 422.
- **Fuente**: test_profile_api.py:test_dataset_detail_and_draws_use_verified_embedded_profile
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-081] Identificador de dataset: 64 hex minúsculas; 404/409
- **Regla**: `bad`, 64 mayúsculas, 63 hex, 64 no-hex → 422 en detalle y draws; sha válido inexistente → 404; error de integridad (`ValueError` privado) → 409 sin filtrar el mensaje.
- **Fuente**: test_profile_api.py:test_dataset_detail_and_draws_use_verified_embedded_profile
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-082] Registro de perfil estricto, idempotente y con conflicto
- **Regla**: POST sin Origin / Origin ajeno / Host ajeno → 403; campos extra, `minimum_stake 1.0` o multiplicadores float → 422; JSON con claves duplicadas o `NaN` → 422 y cuerpo > 65 536 bytes → 413; mismo perfil → 201 con respuesta idéntica y sin duplicar (`total` estable); mismo id/revisión con contenido distinto (`currency USD`) → 409; cuota insuficiente → 409 sin persistir.
- **Fuente**: test_profile_api.py:test_registration_strict_idempotent_conflict_quota_and_origin
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-083] Envío de job de perfil: validación y enlace estricto
- **Regla**: `POST /experiments/profiles`: 403 sin Origin/Host válido; 422 para campo extra, `capital 100.0`, `selector.capability` desconocida, `entry_policy conditional-entry/v1`, JSON duplicado/>65 536 (413); 409 si el perfil no está registrado (solo inline importado), si `profile_sha256` o `dataset_sha256` no coinciden, si la revisión difiere del sha, o si el capital inicial no cubre la apuesta.
- **Fuente**: test_profile_api.py:test_profile_submit_rejects_invalid_binding_affordability_and_queue_failure
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-084] Fallos de admisión/cola no dejan residuos
- **Regla**: rechazos 409 dejan `list_experiments()==[]` y `jobs.pending_ids()==()`; cuota insuficiente → 507; `enqueue` con `QuotaExceeded` → 507 compensado; `submit_profile` con `RuntimeError("queue stopped")` → 409 compensado.
- **Fuente**: test_profile_api.py:test_profile_submit_rejects_invalid_binding_affordability_and_queue_failure
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-085] Contrato HTTP legacy exacto sin cambios
- **Regla**: detalle, lista, `/compare` y replay de un experimento legacy conservan forma exacta: run con `result{outcome, bets_count, wagered, paid, final_balance, delta, net, return_per_wagered, roi, max_drawdown, metric_scope, ratio_rounding "decimal-half-up-6"}`; detalle `{id,status,created_at,request,profile,sources,runs}`; replay `{total,offset,limit 20,items[{label,numbers,per_number,wagered,results,paid,balance}]}` sin `result_kind`.
- **Fuente**: test_profile_api.py:test_legacy_exact_http_fixture_unchanged
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-086] Cycling v2 pendiente/HELD: snapshot veraz, cancelable
- **Regla**: un experimento cycling (schema 2) pendiente aparece en listas y detalle con `runs[0].result None`, replay → 409; tras `recover_jobs` queda `held` (cuenta en `queue.held.total`) y se cancela vía `/queue/{id}/cancel` → 200/CANCELLED.
- **Fuente**: test_profile_api.py:test_private_cycling_public_reads_and_queue_start_refuse_without_leaking
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-087] Envío público cycling v2: validaciones antes de leer filas
- **Regla**: `schema_version 3` con payload v2 → 422; `staking.per_number_stake` extra → 422; cobertura que excede capital/afford (409) o 80 números (409); `profile_sha256` mal → 409; perfil sin cycling (importado con 3 posiciones) no ofrece `q80-first-prize-cycling/v1` y el envío → 409; el catálogo del perfil legacy sí lista `q80-first-prize-cycling/v1`; `QuotaExceeded` en `_enqueue_profile_cycling` → 507 sin residuos; tras 201 el job completa con `result.schema_version 2`, replay y trajectory con `schema_version 2`.
- **Fuente**: test_profile_api.py:test_public_cycling_submit_spawn_replay_and_rejection_before_rows
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-088] Proyección pública de cycling completado y visibilidad en búsqueda
- **Regla**: detalle expone `request.staking {schema_version 1, capability q80-first-prize-cycling/v1}`, `display.staking_label` contiene "dinámica", run con resultado serializado (sin `bets`/`kind`) + `delta` + métricas; replay con `schema_version 2` paginado; `repo.search_experiments` oculta cycling completados salvo `include_completed_cycling=True` pero la API pública los lista (pendiente y completado) y filtra por `status` held/running/failed.
- **Fuente**: test_profile_api.py:test_completed_cycling_public_read_projection_and_visibility
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-089] Audaz v3: envío público, lectura veraz y rechazo de incompatibles
- **Regla**: POST schema 3 → 201; detalle con `request.schema_version 3`, `staking_label "Audaz · apuesta dinámica por sorteo"`, estado pending/running/completed; replay/trajectory con `schema_version 3` y `total == bets_count`; la lista coincide con el detalle; cobertura incompatible (2 números ≥ multiplicador₀ condición Audaz) → 409 sin persistir.
- **Fuente**: test_profile_api.py:test_public_audaz_post_has_truthful_detail_list_and_replay
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-090] Recovery v4: envío, worker y lecturas veraces
- **Regla**: POST schema 4 → 201; `request.staking {schema_version 1, target_margin, rounds, end_mode}`; `display.staking_label` empieza con "Escalera de recuperación"; resultado, replay y trajectory con `schema_version 4`.
- **Fuente**: test_profile_api.py:test_public_schema4_recovery_submission_worker_and_truthful_reads
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-091] Recovery v4 modo `stop` persiste `limit` + `recovery_round_limit`
- **Regla**: con `rounds=1` y `end_mode stop` sin aciertos, el run termina `completed` con `outcome "limit"` y `collisions == ["recovery_round_limit"]`; replay disponible con `schema_version 4`.
- **Fuente**: test_profile_api.py:test_public_schema4_stop_persists_round_limit_and_replays
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-092] `/profile-batches/validate` es dry-run total
- **Regla**: validate → 200 `valid True` + `effective_constraints`; `start_draw` no existente (`05:11`) → 422; no altera filas de `experiments/runs/profile_batch_admissions/settings_quota`, no cambia `admission_logical_bytes` ni registra `client_request_id`.
- **Fuente**: test_profile_batch_api.py:test_validate_is_dry_and_native_batch_routes_are_registered
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-093] Crear lote: `effective_constraints` iguales a validate y estrategia disponible
- **Regla**: `POST /profile-batches` → 201, `batch_admission.effective_constraints` == el de validate, encola 1 vez; `GET /strategies/{id}?profile_id&profile_revision&profile_sha256` devuelve `execution_available True`.
- **Fuente**: test_profile_batch_api.py:test_validate_is_dry_and_native_batch_routes_are_registered
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-094] Idempotencia nativa por `client_request_id`
- **Regla**: 1ª vez 201 con `created True`, `request_schema_version 5`, `runs[0].strategy.id`; repetir el mismo cuerpo → 200 con mismo `id` y `created False` sin reencolar (también si ya COMPLETED o CANCELLED, devolviendo ese `status`); cuerpo distinto con mismo id → 409.
- **Fuente**: test_profile_batch_api.py:test_native_batch_post_uses_queue_and_idempotent_lookup
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-095] Lookup `by-client-request/{id}`
- **Regla**: id desconocido → 404; conocido → 200 con `id`, `status` actual y `links{compare, runs[].replay}`; si la identidad apunta a un experimento ausente/corrupto → 409.
- **Fuente**: test_profile_batch_api.py:test_native_batch_post_uses_queue_and_idempotent_lookup; test_identity_lookup_maps_a_missing_verified_experiment_to_conflict
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-096] Política de ejecución: GET, PUT con CAS y acotada
- **Regla**: `GET /execution-policy` devuelve `policy` (`worker_count 1`), `revision`, `explanation`; `PUT` con `expected_revision` correcto actualiza (`max_bet_draws`); revisión obsoleta → 409; `worker_count 2` y `run_timeout_seconds 3601` → 422; el PUT exige Origin.
- **Fuente**: test_profile_batch_api.py:test_policy_route_is_bounded_cas_and_does_not_rewrite_frozen_batches
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-097] Cambiar la política no reescribe lotes congelados
- **Regla**: lotes ya admitidos conservan sus `effective_constraints`; lotes nuevos usan la política vigente (`max_bet_draws 7`).
- **Fuente**: test_profile_batch_api.py:test_policy_route_is_bounded_cas_and_does_not_rewrite_frozen_batches
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-098] Validate no reserva capacidad ni identidad; create rechaza con 409 a capacidad
- **Regla**: con `max_pending_runs 1` y un legacy pendiente, validate → 200 con `limits.reservation_created False` y no registra el `client_request_id`; el POST real → 409 y tampoco registra identidad.
- **Fuente**: test_profile_batch_api.py:test_validate_does_not_reserve_capacity_or_request_identity
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-API-099] `schema_version` no coercible en lotes nativos
- **Regla**: `True`, `1.0`, `"1"` en la raíz o en `conditions` → 422 en validate y create.
- **Fuente**: test_profile_batch_api.py:test_native_batch_schema_versions_reject_coercible_values
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-100] Body de lote cerrado y acotado
- **Regla**: 422 para campo extra (`selector`), `client_request_id` vacío, referencias de estrategia duplicadas, `python_code` en estrategia (no hay código custom), `max_draws 10001`; cuerpo > 64 KiB → 413.
- **Fuente**: test_profile_batch_api.py:test_native_batch_body_is_closed_and_limited
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-101] Proyección v5 de detalle/lista/replay/trajectory
- **Regla**: detalle con `request_schema_version 5`, `runs[0].result{schema_version 5, definition_name, metric_scope saved_individual_run, start_draw_index, prior_cutoff, stop_category}`, `batch_admission.source_identity.row_count`; la lista por `name_contains` (`client_request_id`) es idéntica al detalle; replay items con `source_index` y `bet_index`; trajectory `result_kind profile`, `schema_version 5`, `source_index >= 1` y `bet_index+1 == source_index`.
- **Fuente**: test_profile_batch_views.py:test_completed_v5_detail_list_and_replay_project_saved_session
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-102] Categorías de parada v5 (`_stop`)
- **Regla**: `LIMIT` por presupuesto → `(operational_budget, <límite>, False)`; `HISTORY_EXHAUSTED` sin límites → `(source_end, "full saved source ended", True)`; `GOAL` → `financial_goal`.
- **Fuente**: test_profile_batch_views.py:test_v5_stop_reasons_distinguish_budget_goal_and_source_end
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-API-103] Runs v5 sin resultado no hacen afirmaciones financieras
- **Regla**: run FAILED → `stop_category unknown`; CANCELLED → `interrupted`; ambos con `result None`, `complete False` y sin claves `roi`.
- **Fuente**: test_profile_batch_views.py:test_v5_resultless_runs_have_no_financial_claims
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-104] Corrupción de identidad de fuente → 409 (no 500)
- **Regla**: alterar `row_count`, `source_sha256` o `canonical_sha256` en `source_identity_json` hace que detalle, lista y `/compare` respondan 409.
- **Fuente**: test_profile_batch_views.py:test_v5_saved_source_identity_corruption_is_conflict
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-105] Dataset corrupto → 409 en replay/trajectory v5
- **Regla**: bytes de dataset alterados → `/runs/0/replay` y `/trajectory` → 409.
- **Fuente**: test_profile_batch_views.py:test_corrupt_v5_saved_dataset_is_conflict_for_replay_and_trajectory
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-106] Admisión corrupta → 409 no 500
- **Regla**: `ValueError("corrupt saved batch admission")` desde `get_experiment` se traduce en 409.
- **Fuente**: test_profile_batch_views.py:test_corrupt_v5_admission_is_conflict_not_server_error
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-107] (Referencia cruzada) Contratos de `test_settings.py` y `test_queue.py` en la capa API
- **Regla**: el detalle de parseo/defaults de `LABORATORIO_GAME_*` y de procedencia de cuota está en B-SET-001..B-SET-012; la semántica de cola (cancel, HELD, serial, quota en enqueue/start_held) está en B-QUE-001..B-QUE-026. Los endpoints `/queue`, `/queue/{id}/start|cancel` se contratan en B-API-033/034/038.
- **Fuente**: test_settings.py, test_queue.py
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-API-108] Arranque siembra presets y monta `/strategies`
- **Regla**: al iniciar la app se siembran 3 presets protegidos; `GET /api/v1/strategies?offset=0&limit=3` → 200 con `total 3` y `execution_available False` en todos.
- **Fuente**: test_strategy_library.py:test_startup_seeds_presets_and_mounts_strategy_api
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-109] Rutas de estrategias: cuerpo cerrado, paginación, contexto de perfil, CAS de revisiones
- **Regla**: POST con campo extra (`arbitrary_path`) o JSON truncado → 422; crear → 201 con `id`; `GET /strategies/{id}` devuelve la estrategia; con `profile_id/revision/sha256` añade `profile_compatible`; hash de perfil que no coincide → 409; `POST /strategies/{id}/revisions` con `expected_latest_revision` correcto → 201 (`revision 2`), obsoleto → 409; lista de revisiones con `total`; ids inexistentes → 404 (también `/revisions`); `limit=101` → 422; lista `total` coherente.
- **Fuente**: test_strategy_library.py:test_route_uses_closed_body_pagination_and_id_retrieval
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-110] Corrupción almacenada → 409 en lecturas de estrategias
- **Regla**: definición adulterada (`{}`) → 409 en lista, detalle y revisiones; perfil registrado adulterado → 409 en el detalle con contexto de perfil y la respuesta no incluye el contenido corrupto (`"{}"`).
- **Fuente**: test_strategy_library.py:test_strategy_read_endpoints_map_stored_corruption_to_409
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-111] `/imports/history/preview`: cuerpo crudo, hash fuente y compatibilidad de perfil
- **Regla**: preview recibe el JSON de historial anidado como bytes crudos con cabeceras `X-Profile-Id/Revision/Sha256`, `X-Confirm-Source`, `X-Confirm-Timezone`; devuelve `promotable`, `records_total`, `source_sha256 == sha256(raw)`, `profile_compatibility{registered True, execution_supported False}`.
- **Fuente**: test_history_import.py:test_history_api_raw_preview_hash_promote_and_paginated_library
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-112] `/imports/history/promote`: gate por `X-Expected-Dataset-Sha256` y biblioteca paginada
- **Regla**: hash esperado incorrecto → 409; correcto → 200 con `created True` y `retained_source_sha256 == sha256(raw)`; el dataset aparece en `/datasets?offset=0&limit=1` (`total 1`, `records_total 2`, `first_draw "2025-01-01 05:05"`) y los bytes crudos quedan retenidos.
- **Fuente**: test_history_import.py:test_history_api_raw_preview_hash_promote_and_paginated_library
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-API-113] Historial exige metadatos explícitos y perfil registrado
- **Regla**: sin cabeceras de perfil → 422; `X-Confirm-Source` que no coincide con la metadata del documento → 409; `X-Profile-Id` no registrado → 422; `X-Profile-Sha256` desactualizado → 409.
- **Fuente**: test_history_import.py:test_history_api_requires_explicit_metadata_and_registered_profile
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-API-114] Promote de historial revalida cuota; el import viejo permanece estricto
- **Regla**: con cuota 1 explícita, promote → 409; `POST /imports/preview` con `format history_json` y `{}` → 422 (el formato antiguo no acepta historial anidado).
- **Fuente**: test_history_import.py:test_history_promote_revalidates_quota_and_old_import_format_stays_strict
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

<!-- B-API:fin -->

## 2. B-DOM — Dominio y contratos

### [B-DOM-001] Juego por defecto Quiniela 80
- **Regla**: `GAME` = 100 números, 5 posiciones, premios `(80,8,4,2,1)`, repeticiones, `minimum_stake 1`; `COVERAGES == (1,5,10,20,25,30,40,50)`; `SYSTEMS` tiene 13 entradas, incluye `transition` y excluye `logistic`.
- **Fuente**: test_contracts.py:test_default_game_is_quiniela_80
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-002] `make_game` valida reglas coherentes
- **Regla**: construye juegos de N posiciones (premios de lista → tupla; `minimum_stake` default 1); rechaza premios ≠ posiciones, universo < posiciones sin repeticiones (3 números/4 pos), universo 1, 0 posiciones, premio 0 y `minimum_stake 0`.
- **Fuente**: test_contracts.py:test_make_game_builds_a_three_position_game; test_make_game_rejects_inconsistent_rules
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-003] `configure_game` reemplaza el juego visible para todos los módulos
- **Regla**: tras `configure_game`, `contracts.GAME` cambia y `GAME` importado por nombre es el mismo objeto (mutación in-place).
- **Fuente**: test_contracts.py:test_configure_game_replaces_the_visible_game
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-004] `GameProfile` admite 1, 3 y 5 posiciones con round-trip JSON
- **Regla**: `GameProfile` con N posiciones tiene N multiplicadores y `model_validate_json(model_dump_json()) == perfil`.
- **Fuente**: test_contracts.py:test_new_profiles_admit_explicit_position_counts
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-005] Perfil admite otros universos y dinero escalado exacto
- **Regla**: universo 7, 6 posiciones sin repeticiones, `scale 2`, `stake_increment 2`, multiplicadores fraccionarios (3/2) son válidos; el dinero se serializa como entero en unidades mínimas.
- **Fuente**: test_contracts.py:test_new_profiles_allow_other_universes_and_exact_scaled_money
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-006] Perfil exige todos los campos y rechaza extras
- **Regla**: faltar cualquiera de los campos (`schema_version, profile_id, revision, universe_size, positions, allows_repeats, multipliers, currency, scale, stake_increment, minimum_stake, maximum_stake, max_coverage, max_exposure, best_rule`) → error; campo desconocido → error.
- **Fuente**: test_contracts.py:test_profile_requires_every_field_and_rejects_extra_fields
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-007] Perfil rechaza escalares mal formados (sin coerción)
- **Regla**: rechaza `schema_version` 2/True, `profile_id` con mayúsculas/espacios, `revision` 0 o >1 000 000, universo 0 o > `MAX_PROFILE_UNIVERSE`, posiciones > `MAX_PROFILE_POSITIONS`, `allows_repeats=1`, `currency "RD$"`, `scale > MAX_PROFILE_SCALE`, `stake_increment/minimum_stake/max_coverage` 0, `maximum_stake`/`max_exposure` > `MAX_MONEY`, `best_rule "custom"`, bool/float/str/inf en campos enteros.
- **Fuente**: test_contracts.py:test_profile_rejects_malformed_scalar_fields
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-008] Perfil rechaza términos inconsistentes o inexactos
- **Regla**: error si #multiplicadores ≠ posiciones; posiciones > universo sin repeticiones; `max_coverage > universe`; `minimum_stake > maximum_stake`; stakes no múltiplos de `stake_increment`; `max_exposure` menor que lo máximo pagable/apostable (9, o < maximum_stake, o desbordando `MAX_MONEY` con multiplicadores enormes); premios no enteros en unidades mínimas (3/2 con incremento 1); denominador 0, numerador float/bool o ausente; lista vacía.
- **Fuente**: test_contracts.py:test_profile_rejects_inconsistent_or_inexact_terms
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-009] Perfil y multiplicadores son inmutables y no comparten entrada mutable
- **Regla**: mutar el dict de entrada tras validar no altera el modelo; asignar `positions` o `numerator` → `ValidationError`.
- **Fuente**: test_contracts.py:test_profile_and_nested_multipliers_are_immutable_and_do_not_share_mutable_input
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-DOM-010] Descriptor legacy congelado, estable y distinto de `best_rule` nuevo
- **Regla**: `legacy_quiniela_80_profile()` refleja `GAME` (100/5/repeticiones, multiplicadores = premios, `DOP`, scale 0, incremento 1, mínimo 1), `best_rule "first-match/v0"`, `max_coverage == max(COVERAGES)`, `maximum_stake <= max_exposure`, es determinista y round-trip JSON; los perfiles nuevos no pueden usar `best_rule first-match/v0` ni `profile_id legacy-quiniela-80`.
- **Fuente**: test_contracts.py:test_legacy_descriptor_is_frozen_stable_and_distinct_from_new_best_rule
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-011] Estrategia individual válida e inválida
- **Regla**: `selector system` requiere `system` de `SYSTEMS` (sin `components`); inválidos: sistema `logistic`/None, cobertura 7, staking `martingale`, nombre en blanco, `components` junto a `system`.
- **Fuente**: test_contracts.py:test_individual_system_strategy_is_valid; test_invalid_individual_strategies_are_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-012] Blend: 2+ sistemas distintos, pesos enteros que suman 100
- **Regla**: válido 60/40; inválido con un solo componente, suma ≠100, sistemas repetidos, peso 0 o sistema `random` como componente.
- **Fuente**: test_contracts.py:test_blend_requires_two_distinct_systems_with_integer_weights_summing_100
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-013] `parity` solo cobertura 50; `random` sin `system`
- **Regla**: selector `parity` exige cobertura 50; `random` acepta coberturas estándar pero no `system`.
- **Fuente**: test_contracts.py:test_parity_only_allows_coverage_50_and_random_uses_standard_coverages
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-014] `goal` es balance final y debe exceder `capital`
- **Regla**: `goal > capital > 0`; `goal` máximo < 10^13.
- **Fuente**: test_contracts.py:test_goal_is_final_balance_and_must_exceed_capital
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-015] Límites `max_bets`/`max_minutes` opcionales pero positivos
- **Regla**: valores 12/90 válidos; 0 y negativos inválidos.
- **Fuente**: test_contracts.py:test_limits_are_optional_but_positive_when_present
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-016] `start_draw` usa el formato `YYYY-MM-DD HH:MM`
- **Regla**: `2025-09-02T05:10` y `2025-13-02 05:10` son inválidos.
- **Fuente**: test_contracts.py:test_start_draw_uses_the_historical_label_format
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [B-DOM-017] Seed acotada a `MAX_SEED = 2**53-1`
- **Regla**: `MAX_SEED` válido; `MAX_SEED+1` y `-1` inválidos.
- **Fuente**: test_contracts.py:test_seed_is_bounded_to_the_max_safe_javascript_integer
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-018] Experimento con 1–5 estrategias de nombre único
- **Regla**: 0 o 6 estrategias inválidas; nombres duplicados ignorando mayúsculas y espacios (`"Igual"` vs `" igual "`) inválidos.
- **Fuente**: test_contracts.py:test_experiment_has_one_to_five_uniquely_named_strategies
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-019] Error de duplicado localizado en `strategies[i].name`
- **Regla**: exactamente un error con `loc ("strategies", 1, "name")`.
- **Fuente**: test_contracts.py:test_duplicate_name_error_is_located_on_the_offending_strategys_name_field
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-020] Normalización de nombres según fixture compartido
- **Regla**: `normalize_strategy_name` y la validación de duplicados siguen `fixtures/strategy_name_cases.json` (misma lógica entre backend y cliente): igualdad normalizada ⇔ duplicado.
- **Fuente**: test_contracts.py:test_strategy_name_normalization_matches_the_shared_fixture
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-021] Nombres recortados y acotados a 80
- **Regla**: `"  Fríos  "` → `"Fríos"`; 81 caracteres inválido.
- **Fuente**: test_contracts.py:test_names_are_trimmed_and_bounded
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-022] Charset de recorte explícito y compartido
- **Regla**: U+FEFF y U+0085 NO se recortan (se conservan en el nombre almacenado), `\t` sí; la detección de duplicados usa el mismo charset.
- **Fuente**: test_contracts.py:test_stored_name_uses_the_same_explicit_trim_charset_as_duplicate_detection
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-023] Enteros estrictos en condiciones y estrategia
- **Regla**: `seed`, `capital`, `goal`, `max_bets`, `max_minutes`, `coverage` y `weight` rechazan str y float (`"7"`, `7.0`).
- **Fuente**: test_contracts.py:test_seed_capital_goal_limits_coverage_and_weight_are_strict_integers
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-024] `top_k` conserva el orden y valida `k`
- **Regla**: `top_k(order,3)` devuelve los 3 primeros en orden; `k=0` o `k=101` → `ValueError`.
- **Fuente**: test_selection.py:test_top_k_keeps_ranking_order_and_rejects_bad_k
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-025] Blend: puntos por rango 100→1 ponderados por porcentaje
- **Regla**: puntaje = Σ peso×(100−posición); 60/40 pone primero al número que lidera el método de mayor peso (9960 vs 9940).
- **Fuente**: test_selection.py:test_blend_uses_rank_points_100_to_1_weighted_by_percent
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-026] Empates del blend se rompen por número ascendente
- **Regla**: el desempate es el número menor, independiente del orden de los métodos en el dict.
- **Fuente**: test_selection.py:test_blend_ties_are_broken_by_ascending_number_not_by_method
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-027] Blend devuelve permutación completa y valida pesos
- **Regla**: el resultado es una permutación de 0..99; pesos que no suman 100 o con claves distintas a las del ranking → `ValueError`.
- **Fuente**: test_selection.py:test_blend_is_a_full_permutation; test_blend_rejects_weights_that_do_not_match_rankings
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-028] `random_order` reproducible, anidado y keyed por (seed, sorteo)
- **Regla**: mismo (seed, label) → mismo orden (permutación completa); cobertura 5 es prefijo de cobertura 10; cambiar seed o sorteo cambia el orden.
- **Fuente**: test_selection.py:test_random_order_is_reproducible_nested_and_keyed_by_seed_and_draw
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-029] `random_order` no depende del orden de llamada
- **Regla**: evaluar sorteos hacia adelante o hacia atrás produce las mismas listas por sorteo.
- **Fuente**: test_selection.py:test_random_order_does_not_depend_on_call_order
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-030] `random_order` estable entre versiones (huella congelada)
- **Regla**: `random_order(20260928, "2025-09-02 05:10")` empieza `[32,12,46,74,17]` y su sha256 es `4c40b250ead5...bd8bb5` (algoritmo BLAKE2b-64, orden ascendente); cambiarlo rompe reproducibilidad.
- **Fuente**: test_selection.py:test_random_order_is_stable_across_releases
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-031] `parity_numbers` y votos causales
- **Regla**: `parity_numbers(0)` = 50 pares, `(1)` = 50 impares, otro valor → `ValueError`; el primer voto sin historia es par (0); los votos son causales (el voto del sorteo i no depende de sorteos ≥ i); siguen la racha larga par/impar (60 pares → 0; 60 impares → 1).
- **Fuente**: test_selection.py:test_parity_numbers_are_the_50_even_or_odd_numbers; test_parity_first_vote_without_history_is_even; test_parity_votes_are_causal; test_parity_votes_follow_a_long_even_streak; test_parity_votes_follow_a_long_odd_streak
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-032] Métricas financieras por run, exactas, redondeo half-up a 6
- **Regla**: `net = paid − wagered`; `return_per_wagered = paid/wagered`; `roi = net/wagered`; redondeo decimal half-up a 6 decimales (`0.333333`, `−0.666667`); `max_drawdown` = mayor caída desde un pico (incluye capital inicial); `metric_scope "saved_individual_run"`, `ratio_rounding "decimal-half-up-6"`.
- **Fuente**: test_metrics.py:test_metrics_are_run_scoped_exact_and_round_half_up
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-033] Sin apuestas: ratios nulos y sin no-finitos
- **Regla**: `wagered 0` → `return_per_wagered None`, `roi None`, `max_drawdown 0`.
- **Fuente**: test_metrics.py:test_zero_wagers_have_null_ratios_and_no_nonfinite_values
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-034] Trayectoria vacía/corta no se fabrica
- **Regla**: `reduce_trajectory` sin apuestas devuelve `total 0`, `points []`, `reduction_method "none"`, extremos = capital con `source_index None`; trayectorias ≤ `max_points` se devuelven completas.
- **Fuente**: test_trajectory.py:test_empty_and_short_trajectories_are_not_fabricated
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-035] Reducción min/max conserva extremos, empates tempranos e índices de replay
- **Regla**: con 7 puntos y `max_points 4` se conservan extremos y primer/último (`{0,1,3,6}`), ordenados por `source_index`, mínimo/máximo con el índice más temprano en empate, `reduction_method "minmax-even-v1"`, `replay == replay?offset=<i>&limit=1`.
- **Fuente**: test_trajectory.py:test_reduction_keeps_endpoints_extrema_earliest_ties_and_replay_indices
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-036] Capital inicial participa en los extremos
- **Regla**: extremos consideran el capital inicial (`source_index None` si el extremo es el capital inicial, con desempate al más temprano).
- **Fuente**: test_trajectory.py:test_initial_capital_participates_in_extrema_with_earliest_tie
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-DOM-037] `max_points` acotado [4, 2000] y no-bool
- **Regla**: 3, 2001 y `True` → `ValueError`.
- **Fuente**: test_trajectory.py:test_point_limit_is_explicitly_bounded
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-038] Liquidación `all` vs `best` con números repetidos
- **Regla**: con resultados `(7,7,8,7,8)` y apuesta a 5 números: `all` paga cada posición (95) y `best` solo el mejor premio por número (84); balance final 100 vs 89; las `Bet` son inmutables (asignar → AttributeError/TypeError) y registran `numbers, results, per_number, wagered, paid, balance`.
- **Fuente**: test_session.py:test_repeated_numbers_pay_each_position_or_only_best_per_number
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-039] Contabilidad sintética por cobertura 20/30/40 × staking × modo
- **Regla**: para flat/ladder (stake 1) y bold (stake 2): `wagered = stake×cobertura`, `paid = stake×(95|84)`, `balance = capital − costo + pago`, outcome GOAL si `balance >= goal` sino LIMIT, 1 apuesta registrada con números seleccionados.
- **Fuente**: test_session.py:test_synthetic_coverage_accounting_with_repeated_numbers
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-040] Insolvencia inicial y posterior: sin sobregiro
- **Regla**: capital 4 con cobertura 5 → `ValueError("afford")` (también con bold); capital 5 exacto apuesta y termina `RUIN` con balance 0; orden de selección que no cubre la cobertura → `ValueError("ordering")`.
- **Fuente**: test_session.py:test_initial_and_post_settlement_insolvency_do_not_overdraft
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-041] `preflight_initial_stake` en el borde exacto
- **Regla**: flat/ladder/bold con cobertura 5 y 50: capital `cobertura−1` → `ValueError("initial capital cannot afford")` en preflight y en `run_session` (aun sin sorteos); capital == cobertura → preflight devuelve 1 y la primera apuesta es 1 por número con `wagered == cobertura`.
- **Fuente**: test_session.py:test_preflight_rejects_unfunded_first_bet_and_accepts_exact_boundary
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-042] Stake bold del preflight == primera apuesta ejecutada
- **Regla**: capital 2000, goal 2800, cobertura 50 → stake 27 tanto en preflight como en la primera apuesta.
- **Fuente**: test_session.py:test_preflight_bold_stake_matches_first_executed_wager
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-043] Ladder: rondas de recuperación por cobertura y reset al primer acierto
- **Regla**: cobertura 10 mantiene stake 1; cobertura 50 recupera con 1, 2, 6 y un acierto en primera posición (`7` en pos 1) reinicia a la ronda cero (secuencia `[1,2,6,1]`).
- **Fuente**: test_session.py:test_ladder_uses_coverage_recovery_rounds_and_resets_on_first_hit
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-044] La liquidación precede a goal/límite; goal es balance final
- **Regla**: tras pagar, si `final_balance >= goal` el resultado es GOAL aunque `max_bets` se alcance en la misma apuesta.
- **Fuente**: test_session.py:test_settlement_precedes_goal_and_limit_and_goal_is_final_balance
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-045] Huecos consumen tiempo; igualdad con el deadline excluye el sorteo
- **Regla**: un sorteo sin ranking (`order None`) consume tiempo; con `max_minutes=10` y sorteos a +0/+5/+10 solo se apuesta el primero (el de +10 igual al deadline queda fuera); outcome LIMIT.
- **Fuente**: test_session.py:test_gaps_consume_time_and_deadline_equality_excludes_draw
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-046] El primer límite gana; agotar historial es outcome aparte
- **Regla**: `max_bets=1` → LIMIT con 1 apuesta; `max_minutes=10` → LIMIT con 2; sin límites → `HISTORY_EXHAUSTED` tras todas las apuestas.
- **Fuente**: test_session.py:test_first_limit_wins_and_history_exhaustion_is_separate
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-047] Ruina precede al límite simultáneo de apuestas
- **Regla**: capital 1, `max_bets=1`, sin acierto → `RUIN` (no LIMIT).
- **Fuente**: test_session.py:test_ruin_precedes_simultaneous_bet_limit_after_settlement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-048] Stake bold: entero = brecha a la meta / neto del primer premio, con tope
- **Regla**: capital 2000, goal 2800, cobertura 50 → 27 por número, `wagered 1350`.
- **Fuente**: test_session.py:test_bold_integer_stake_is_goal_gap_over_first_prize_net_and_capped
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-049] Adaptador enruta selectores y preserva el reloj sin ranking
- **Regla**: `session_draws` entrega `order` ranking-primero para `system`, `blend` (50/50), `random` (= `random_order(seed,label)[:5]`) y `parity` (números `1,3,5,7,9` con voto impar); sorteos sin ranking tienen `order None` pero siguen avanzando el reloj; iniciar en un sorteo sin ranking → `DataError("no ranking")`.
- **Fuente**: test_session.py:test_adapter_routes_selectors_and_preserves_unranked_clock
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-050] Contabilidad blend/random a coberturas amplias
- **Regla**: con blend y random a cobertura 20/30/40 en modos all/best, `order == ranked[:coverage]`, `wagered = cobertura`, `paid = 95|84`, balance correcto, outcome LIMIT con `max_bets=1`.
- **Fuente**: test_session.py:test_adapter_blend_and_random_accounting_at_wider_coverages
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-051] Sesiones de referencia congeladas (real_data)
- **Regla**: el fixture `reference_sessions.json` contiene 141 casos únicos (sistema,k,staking,modo) y cada sesión reproduce exactamente `bets, final, wagered, paid, outcome` (`open` ≠ `history_exhausted` mapeado); es el oráculo inmutable del motor legacy.
- **Fuente**: test_session.py:test_all_frozen_reference_sessions
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-052] Política de ejecución por defecto conservadora; workers no editables
- **Regla**: `ExecutionPolicy.defaults()`: `max_strategies_per_batch 3`, `worker_count 1`, `max_pending_runs 10`, `max_bet_draws 1000`, `max_elapsed_draws 10000`, `run_timeout_seconds 120`; `worker_count 2` → `ValueError`.
- **Fuente**: test_batch_admission.py:test_default_policy_is_conservative_and_workers_are_not_editable
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-053] Campos de política acotados
- **Regla**: `max_pending_runs 101`, `max_bet_draws 10001`, `run_timeout_seconds 3601` → `ValueError`.
- **Fuente**: test_batch_admission.py:test_policy_fields_are_bounded_not_arbitrary
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-054] Admisión usa revisión exacta, persiste snapshot y es idempotente
- **Regla**: `admit_profile_batch` guarda un `ProfileBatchRequestV5` con las definiciones exactas de la revisión referenciada, `request_schema_version 5`, `batch_admission{strategy_refs, source_identity.row_count, policy_revision, policy}`; añadir una nueva revisión de la estrategia no cambia el resultado de reenviar la misma submission (devuelve el mismo id); cambiar condiciones con el mismo `client_request_id` → `IdempotencyConflict`; actualizar la política (CAS `expected_revision`) no reescribe la admisión congelada.
- **Fuente**: test_batch_admission.py:test_admission_uses_exact_revision_persists_snapshot_and_is_idempotent
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-055] Ordinales y límites de política congelados como condiciones explícitas
- **Regla**: las estrategias conservan orden (runs ordinales `[0,1]`); `max_draws` y `max_bet_draws` solicitados (5000) se recortan a los efectivos de la política (4 y 8) y ambos (`requested_constraints`, `effective_constraints`) quedan guardados.
- **Fuente**: test_batch_admission.py:test_batch_ordinals_and_policy_limits_are_frozen_as_explicit_conditions
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-056] Estrategia archivada exige contexto de binding confiable
- **Regla**: referenciar la estrategia de referencia archivada (`reference_cold_25`) sin `Settings` confiable → `ValueError("trusted Settings")` sin escribir experimentos.
- **Fuente**: test_batch_admission.py:test_archived_strategy_requires_trusted_binding_context
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-057] Admisión rechaza hash de revisión incorrecto y capital insuficiente
- **Regla**: `definition_sha256` incorrecto → `ValueError("SHA-256")`; estrategia de 2 números con capital 1 → `ValueError("fund")`; la revisión guardada no se altera.
- **Fuente**: test_batch_admission.py:test_admission_rejects_unfunded_and_untrusted_revision_inputs
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-058] `start_draw` no archivado debe coincidir con exactamente una etiqueta fuente
- **Regla**: con estrategia estática o seeded-random, `start_draw` inexistente (`05:11`) → `ValueError("exactly one canonical source draw")` antes de cualquier escritura (0 filas en experiments, runs, profile_batch_admissions, settings_quota; `logical_experiment_bytes 0`); con etiqueta válida la admisión procede.
- **Fuente**: test_batch_admission.py:test_non_archived_start_must_match_one_saved_source_label_before_writes
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-059] Fallo de cuota no reserva identidad de lote
- **Regla**: `QuotaExceeded` en admisión deja 0 filas en `profile_batch_admissions`; reintentar con cuota suficiente funciona.
- **Fuente**: test_batch_admission.py:test_quota_failure_does_not_reserve_a_batch_identity
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-060] Cuota de lote == delta SQLite medido, exacto en el borde
- **Regla**: el estimado de admisión coincide con el delta real de `admission_logical_bytes`; con `quota = usage + margen + 1` (margen = `min(LOGICAL_MARGIN_BYTES, max(1, bound//20))`) admite y con `quota−1` → `QuotaExceeded` sin escrituras; `admission_logical_bytes ≥ dataset_artifact_bytes + strategy_artifact_bytes`.
- **Fuente**: test_batch_admission.py:test_batch_quota_matches_measured_sqlite_delta_at_exact_boundary
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-061] Límite global de runs pendientes atómico (legacy)
- **Regla**: tras 10 experimentos legacy pendientes, el siguiente → `PendingRunsExceeded` y permanecen exactamente 10 runs `pending`.
- **Fuente**: test_batch_admission.py:test_global_pending_run_limit_is_atomic_for_old_submission_shapes
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-DOM-062] Límite de pendientes compartido entre perfil v5 y legacy
- **Regla**: con 9 pendientes legacy, un lote v5 de 2 estrategias → `PendingRunsExceeded` sin dejar admisión (9 runs, 0 admisiones); un lote de 1 se admite (10) y luego un legacy adicional → `PendingRunsExceeded`.
- **Fuente**: test_batch_admission.py:test_pending_limit_is_shared_between_profile_v5_and_legacy_admission
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-063] Admisión estática conserva el dataset completo > 10 000 filas
- **Regla**: un dataset de 10 002 sorteos se admite con `source_identity.row_count == 10002`, el preview conserva todos los registros y `max_draws 2`/`start_draw` se respetan (no hay truncado al límite legacy de 10 000).
- **Fuente**: test_batch_admission.py:test_static_admission_keeps_full_dataset_above_legacy_ten_thousand_rows
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-064] Lookup por `client_request_id` de solo lectura y verificado
- **Regla**: `get_profile_batch_request_id` devuelve el id o None sin alterar `admission_logical_bytes`; id de >128 caracteres → `ValueError("invalid client request identity")`; si el experimento verificado falta → `ValueError("missing experiment")`.
- **Fuente**: test_batch_admission.py:test_client_request_lookup_is_read_only_and_verifies_the_experiment
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-065] Request v1: `profile_sha256` es hash del perfil validado, canónico
- **Regla**: sha256 del JSON del perfil con claves ordenadas, separadores compactos, UTF-8 sin ASCII-escape; independiente del orden de claves de entrada; cambia con `revision`/`currency`; no es el digest del dataset; rechaza (ValidationError) perfiles forjados (`model_copy` con posiciones inconsistentes o numerador bool) y `TypeError` si no es `GameProfile`.
- **Fuente**: test_profile_request.py:test_profile_hash_is_full_validated_sorted_compact_utf8_json_not_dataset_digest
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-066] Request v1: round-trip canónico, inmutable, tipado, nulos explícitos
- **Regla**: `serialize == JSON canónico` y `load(serialize(x)) == x`; objetos anidados son `ProfileConditions/ProfileSelector/ProfileStaking` tipados y frozen (asignar → `FrozenInstanceError`); `settlement` es enum; `seed 0` válido; `per_number_stake` en unidades mínimas del perfil; `name` se recorta; slots no usados se serializan como `null` (`numbers`, `seed`, `max_bet_draws`).
- **Fuente**: test_profile_request.py:test_full_roundtrip_frozen_typed_nested_objects_and_explicit_null_slots
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-067] Request v1: sobre mal formado rechazado
- **Regla**: `kind` ≠ profile/bool, `schema_version` 2/True, `dataset_sha256` mayúsculas o 63 chars, `profile_sha256` no hex, `profile_id` con espacios, `profile_revision` bool o 0, `entry_policy` ≠ `all_rows/v1`, `name` en blanco → `ValueError/ValidationError`.
- **Fuente**: test_profile_request.py:test_malformed_envelope_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-068] Request v1: sin valores ocultos ni campos extra ni claves duplicadas
- **Regla**: faltar `kind, entry_policy, profile_sha256, conditions.settlement, selector.seed, selector.algorithm_version, staking.per_number_stake` → error (no hay defaults ocultos); campos extra en raíz/conditions/selector/staking → error; JSON con clave duplicada → `ValueError("duplicate")`.
- **Fuente**: test_profile_request.py:test_no_hidden_seed_stake_settlement_or_version_and_no_extra_fields
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-069] Request v1: tipos exactos, capacidades y dinero acotado
- **Regla**: rechaza float/bool en `capital/goal/coverage/seed/per_number_stake`, `> MAX_MONEY`, `settlement` numérico o desconocido, `schema_version` 2 anidado, `seed None` o `0.0`, capacidades desconocidas (`freq_hist`, `ladder`), `algorithm_version hash-sha256-v2`.
- **Fuente**: test_profile_request.py:test_nested_invalid_exact_types_capabilities_and_money
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-070] Request v1: números estáticos enteros exactos y JSON válido
- **Regla**: `numbers` rechaza bool, float, duplicados y string; `entry_policy conditional-entry/v1`, JSON inválido y claves de staking duplicadas → `ValueError`.
- **Fuente**: test_profile_request.py:test_static_numbers_are_exact_integers_and_unknown_entry_or_numbers_shape_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-071] Objetos forjados se revalidan antes de serializar
- **Regla**: mutar `selector.algorithm_version` vía `object.__setattr__` hace fallar `serialize_profile_request` (`ValueError("algorithm")`); `ProfileSelector(1,"parity",2)` → `ValueError`.
- **Fuente**: test_profile_request.py:test_forged_frozen_nested_objects_are_revalidated_before_serialization
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-DOM-072] El contrato legacy de experimento permanece separado
- **Regla**: `ExperimentRequest` legacy acepta `seed 0`, no emite `kind`, y rechaza `kind: "profile"` (campo extra).
- **Fuente**: test_profile_request.py:test_legacy_experiment_contract_is_unchanged_and_separate
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-073] Evolución v2 (cycling): bytes v1 intactos y parsers disjuntos
- **Regla**: v2 (`schema_version 2`, `Q80CyclingStaking`, capacidad `q80-first-prize-cycling/v1`, staking sin `per_number_stake`) serializa en JSON canónico con staking `{capability, schema_version 1}` y condiciones/selector con `schema_version 1`; el parser v1 rechaza bytes v2 y viceversa (`TypeError` al serializar con la función equivocada); v1 flat sigue cargando y serializando idéntico; la entrada `ProfileExperimentRequest` rechaza `TypeError` con argumentos de v2.
- **Fuente**: test_profile_request_v2.py:test_exact_private_roundtrip_and_v1_bytes_unchanged
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-074] v2: wire mal formado rechazado
- **Regla**: rechaza `kind legacy`, `schema_version 1/True`, nombre en blanco o con surrogate (`\ud800`), hash mayúsculas/no hex, `profile_id` inválido, `profile_revision 1.0`, `entry_policy conditional-entry/v1`, `schema_version 2` anidado, `capital True`, `settlement` desconocido, `numbers[0] True`, capability `flat-per-number/v1` y `per_number_stake` extra.
- **Fuente**: test_profile_request_v2.py:test_malformed_wire_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-075] v2: POST público despacha por versión y rechaza binding no registrado
- **Regla**: POST de v2 a `/experiments/profiles` con perfil no registrado → 409 con detalle exacto `"profile admission failed: incompatible binding or stake"`.
- **Fuente**: test_profile_request_v2.py:test_public_profile_post_dispatches_v2_then_rejects_unregistered_binding
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-076] v2: campos faltantes/extra, duplicados recursivos y no-JSON
- **Regla**: faltar `entry_policy`, `conditions.goal`, `selector.seed`, `staking.capability` → error; claves duplicadas (raíz, anidadas), `NaN` y campos extra → error; `schema_version=True` o capability forjada → `ValueError` al serializar.
- **Fuente**: test_profile_request_v2.py:test_no_missing_or_extra_fields_and_recursive_duplicate_and_non_json_numbers
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-077] Evolución v3 (Audaz): `schema_version 3` distinto, stake no inferido
- **Regla**: `ProfileAudazRequest` round-trip; el parser v2 rechaza bytes v3 y el parser v3 rechaza `schema_version 2`; `staking` (ProfileAudazStaking) no contiene `per_number_stake` (la apuesta es dinámica) y añadirlo → error; `schema_version` bool → error.
- **Fuente**: test_profile_request_v3.py:test_schema3_roundtrip_is_distinct_from_v1_and_v2; test_v3_does_not_infer_stake_and_rejects_unknown_fields_and_types
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-078] Evolución v4 (Recovery): staking anidado explícito
- **Regla**: `ProfileRecoveryRequest` (`schema_version 4`) serializa `staking {schema_version 1, target_margin, rounds, end_mode}` y round-trip; falta de `target_margin`, `rounds` o `end_mode` → `ValueError`; `end_mode` solo `cycle` o `stop`.
- **Fuente**: test_profile_request_v4.py:test_v4_recovery_request_roundtrip_explicit_nested_schema; test_v4_rejects_missing_recovery_parameters; test_v4_accepts_only_explicit_end_modes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-079] Result v1: wire estructural; solo el replay autenticado lo admite
- **Regla**: `serialize_profile_result` produce JSON canónico (`kind "profile"`, claves ordenadas, compacto) con round-trip exacto; `validate_profile_result(result, request, profile, rows)` reejecuta la sesión y devuelve el mismo resultado para selectores estáticos y seeded-random; `result` es frozen (`FrozenInstanceError`).
- **Fuente**: test_profile_result.py:test_roundtrip_and_known_valid_static_random_admission
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-080] Contabilidad exacta de enteros escalados, posiciones repetidas, universo ≠ 100
- **Regla**: con universo 11, 3 posiciones, escala 2 y stake 2: resultados `(1,1,2)` → `stakes ((1,2),(2,2))`, `wagered 4`, `paid 12`, `final_balance 28`; un perfil sin repeticiones rechaza el resultado con `ValueError("repeat")`.
- **Fuente**: test_profile_result.py:test_repeated_positions_non100_and_exact_scaled_integer_accounting
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-081] Falsificaciones estructuralmente válidas se rechazan por replay
- **Regla**: alterar `final_balance`, `paid`, `wagered`, `elapsed_draws`, balance/paid/wagered/stakes/results/label de una apuesta, `outcome` o `collisions` produce `ValueError("replay")` en `validate_profile_result`.
- **Fuente**: test_profile_result.py:test_structurally_valid_forgery_rejected_by_replay
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-082] Conteos internamente inconsistentes se rechazan en el parseo
- **Regla**: `bet_draws 0` o `elapsed_draws 0` con apuestas → `ValueError("counts")` al cargar.
- **Fuente**: test_profile_result.py:test_counts_that_are_internally_inconsistent_rejected_at_parse
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-083] Binding de perfil y filas fuente
- **Regla**: `profile_id` distinto, `profile_sha256`, `profile_revision` o perfil con otra moneda → `ValueError("binding")`; filas con otros resultados → `"replay"`; fila con `enter=False` → `"all_rows"`; generador (no acotado) → `"bounded"`.
- **Fuente**: test_profile_result.py:test_profile_binding_and_source_rows_mismatch
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-084] La configuración del request queda atada por replay
- **Regla**: cambiar selector (números), staking (stake) o `start_draw` del request hace fallar la validación con `"replay"`.
- **Fuente**: test_profile_result.py:test_request_configuration_is_bound_by_replay
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-085] Fuente completa con filas previas y entradas omitidas
- **Regla**: filas previas al inicio forman parte de la entrada; omitir una fila previa conserva el mismo replay (el binding del dataset es responsabilidad del llamador); `enter=False` en fila previa → `"all_rows"`; filas distintas → `"replay"`.
- **Fuente**: test_profile_result.py:test_full_source_including_prestart_and_skipped_entries_is_required
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-DOM-086] CANCELLED parsea pero no admite job completado
- **Regla**: un resultado `CANCELLED` hace round-trip, pero `validate_profile_result` → `ValueError("cancelled")` salvo `require_completed=False`; `require_completed` debe ser bool estricto (1 → error).
- **Fuente**: test_profile_result.py:test_cancelled_parses_but_cannot_admit_completed_job
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-087] Wire v1 con tipos/valores inválidos → `ValueError`
- **Regla**: rechaza `kind legacy/True`, `schema_version 2/True`, `profile_revision 1.0`, `elapsed_draws True`, `paid 1.0`, `outcome "won"`, `collisions ["other"]`, bool/float en stakes/results/balance y label con surrogate.
- **Fuente**: test_profile_result.py:test_bad_wire_fields_rejected_with_value_error
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-088] Campos faltantes/extra, claves duplicadas, unicode inválido y NaN controlados
- **Regla**: faltar `kind/bets/profile_id/paid` o campos de apuesta, campos extra (raíz y apuesta), claves duplicadas (`ValueError("duplicate")`), JSON truncado, surrogates y `NaN` → `ValueError`; serializar con `profile_id` surrogate → `ValueError`.
- **Fuente**: test_profile_result.py:test_missing_extra_duplicate_keys_and_invalid_unicode_are_controlled
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-089] Result v2 (cycling): envoltorio `schema_version 2` privado y parsers disjuntos
- **Regla**: `ProfileCyclingResult("profile", 2, session)` serializa JSON canónico con `schema_version 2` (la sesión interna sigue en 1); el parser/serializador v1 rechaza bytes v2 y viceversa (`ValueError`/`TypeError`).
- **Fuente**: test_profile_result_v2.py:test_roundtrip_and_crossversion_rejection_with_canonical_bytes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-090] Cycling: pago secundario, reset en primer acierto y replay anti-manipulación
- **Regla**: con filas `(1,7,2,3,4)`, `(50,50,50,7,9)`, y un tercer sorteo: stake por número `[1,2,1]` y paid `[0, 184 (all) | 160 (best), 0]`; manipular `paid`, `outcome`, paid/stakes de una apuesta o el orden de las apuestas → `"replay"`; filas distintas → `"replay"`.
- **Fuente**: test_profile_result_v2.py:test_secondary_payout_first_hit_reset_and_tamper_replay
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-091] Cycling: diez fallos recorren la escalera y vuelven al inicio
- **Regla**: 11 sorteos sin acierto con cobertura 50 apuestan `[50,100,300,800,2100,5600,14950,39850,106300,283450,50]` (la ronda 11 reinicia); binding de `profile_sha256`/perfil, selector distinto → `"replay"`, generador → `"bounded"`, `enter=False` → `"all_rows"`.
- **Fuente**: test_profile_result_v2.py:test_ten_misses_cycle_and_policy_profile_source_binding
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-092] Cycling solo en perfiles Q80 sin topes que rompan la escalera
- **Regla**: perfil con 3 posiciones → `ValueError("Q80 positions")`; `maximum_stake 5668` (tope menor que la escalera) → `"maximum stake"`; capital 49 → `"afford"` en admisión confiable.
- **Fuente**: test_profile_result_v2.py:test_non_q80_and_full_ladder_caps_rejected_on_trusted_admission
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-093] Cycling: cancelación requiere opt-in; sin inferir procedencia previa
- **Regla**: resultado cancelado → `"cancelled"` salvo `require_completed=False` (también sin la fila previa); `require_completed` no bool → error.
- **Fuente**: test_profile_result_v2.py:test_cancellation_requires_opt_in_and_no_prestart_provenance_inference
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-094] Cycling: wire mal formado y variantes extra/faltantes/duplicadas rechazadas
- **Regla**: `kind legacy`, `schema_version True/1`, revisión float, `paid True`, outcome desconocido, stake float, label surrogate, resultado bool; campos extra/faltantes (también en apuestas), claves duplicadas, `NaN` y surrogates en resultados → `ValueError`.
- **Fuente**: test_profile_result_v2.py:test_malformed_wire_rejected; test_extra_missing_nested_duplicate_and_non_json_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-095] Result v3 (Audaz): round-trip y replay con filas previas
- **Regla**: `ProfileAudazResult("profile",3,session)` serializa con `schema_version 3`, hace round-trip y valida por replay incluyendo filas previas al inicio; alterar `final_balance` → `ValueError("differs")`; el digest del dataset lo verifica el repositorio antes del validador puro.
- **Fuente**: test_profile_result_v3.py:test_v3_result_roundtrip_and_replay_include_prestart_rows
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-096] Audaz ejecuta universos alternos, racionales y con escala
- **Regla**: con universo 10, multiplicadores 7/2, 1/2, 1/4, escala 1, incremento 4: la sesión da `goal`, el stake es múltiplo de `stake_increment`, `wagered <= max_exposure` y el resultado valida por replay.
- **Fuente**: test_profile_result_v3.py:test_audaz_executes_alternate_universe_rational_scaled_profile
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-097] Result v4 (Recovery): colisión `recovery_round_limit` solo en v4
- **Regla**: `ProfileRecoveryResult("profile",4,session)` hace round-trip con `collisions ["recovery_round_limit"]`; los wires/serializadores v1, v2 (`"collisions"`) y v3 ("audaz result") rechazan esa colisión, y reetiquetar `schema_version` 4→ 1/2/3 falla.
- **Fuente**: test_profile_result_v4.py:test_v4_collision_roundtrips_but_older_wires_refuse_it
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-098] v4 rechaza versiones y colisiones desconocidas
- **Regla**: `schema_version 5` → `ValueError("version")`; colisión `"invented"` → `ValueError("collisions")`.
- **Fuente**: test_profile_result_v4.py:test_v4_rejects_unknown_versions_and_collision_values
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-099] Audaz de perfil generaliza el stake Q80 de referencia
- **Regla**: stake = ceil(brecha_a_meta / (m1 − k)) acotado por `balance // k` y por máximo/exposición; Q80 cobertura 1 → `(800+79−1)//79`, cobertura 50 → `min(ceil(800/30), 2000//50)`; si capital == meta → 0.
- **Fuente**: test_profile_staking.py:test_profile_audaz_generalizes_q80_reference_for_coverage_one_and_fifty
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-100] Audaz soporta universo, posiciones, pagos racionales y grilla propios
- **Regla**: para m1=12.5, k=3, brecha 100 y grilla de 2 unidades → stake 12; con 1/3/5 posiciones en universo 23, stake para cobertura 1 = `(brecha + m1 − 2)//(m1 − 1)`.
- **Fuente**: test_profile_staking.py:test_profile_audaz_supports_custom_universe_positions_rational_payouts_and_grid; test_profile_audaz_uses_configured_positions_on_non_100_universes
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-101] Audaz limita por balance, máximo y exposición
- **Regla**: `maximum_stake 10` → 10; exposición 20 con cobertura 3 → 6; balance 49 con cobertura 50 → 0 (no se puede apostar).
- **Fuente**: test_profile_staking.py:test_profile_audaz_caps_by_balance_maximum_and_exposure
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-102] Audaz rechaza margen de primer acierto no positivo
- **Regla**: `m1 ≤ k` (p. ej. multiplicador 2, cobertura 2) → `ValueError("greater than coverage")`.
- **Fuente**: test_profile_staking.py:test_profile_audaz_rejects_nonpositive_first_hit_margin
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-103] Escalera de recuperación generalizada
- **Regla**: `profile_recovery_ladder(p, cobertura, margen, rondas)` produce stakes mínimos en la grilla de `stake_increment` tales que `stake·(m1 − k) ≥ (costo_previo + margen)` y `stake − incremento` no lo cumple; válido para 1/3/5 posiciones, universo 37, multiplicadores racionales y escala 1.
- **Fuente**: test_profile_staking.py:test_recovery_ladder_generalizes_universe_positions_rationals_and_increment_grid
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-104] Escalera recovery coincide con Q80 de referencia y separa Original70
- **Regla**: Q80 cobertura 50, margen 10, 10 rondas → `(1,2,6,16,42,112,299,797,2126,5669)`; tabla Original70 (70,8,4,2,1) con 3 rondas → `(1,3,11)` (la LADDER fija histórica es otro preset).
- **Fuente**: test_profile_staking.py:test_recovery_ladder_matches_q80_reference_and_separates_original70
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-105] Recovery rechaza parámetros inválidos y topes que cortarían la escalera
- **Regla**: `target_margin 0`, `rounds 0`, `end_mode "terminal"` → ValueError con el nombre del campo; multiplicador de 1.ª posición ≤ cobertura → `"first-position multiplier"`; `maximum_stake 100` o `max_exposure` insuficiente para toda la escalera → `"maximum stake"`/`"exposure"` (se rechaza la escalera entera, no se recorta).
- **Fuente**: test_profile_staking.py:test_recovery_ladder_rejects_nonpositive_margin_bad_gain_and_full_ladder_caps
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-106] Identidad de política Audaz privada e inmutable
- **Regla**: `ProfileAudazStaking() == ProfileAudazStaking(1,"profile-audaz/v1")`; asignar `capability` → `FrozenInstanceError`.
- **Fuente**: test_profile_staking.py:test_profile_audaz_policy_identity_is_private_and_immutable
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-DOM-107] Escalera Q80 exacta de 10 rondas y cobertura menor
- **Regla**: `q80_first_prize_ladder(p,50)` = `(1,2,6,16,42,112,299,797,2126,5669)`; para cobertura k cada monto es `max(1,(invertido+10+(80−k)−1)//(80−k))` y cada ronda recupera ≥ 10; cobertura 20 y 1 comienzan `(1,1,1)`; el perfil de prueba distinto del legacy produce la misma escalera.
- **Fuente**: test_profile_staking.py:test_exact_ten_round_q80_recovery_and_distinct_lower_coverage; test_legacy_descriptor_has_same_q80_financial_ladder
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-108] Pago secundario no reinicia; solo la 1.ª posición reinicia
- **Regla**: `step_q80_first_prize_cycle` con premio secundario (8, no first-hit) → cost 50, paid 8, estado `Q80LadderState(1958,1)`; con first-hit (80) → cost 100, paid 160, estado `(2018, 0)`; el estado inicial no se muta (frozen).
- **Fuente**: test_profile_staking.py:test_secondary_only_pays_without_resetting_and_first_position_resets
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-109] Diez fallos ciclan (variante compare), no pérdida terminal E5
- **Regla**: costos `[50,100,300,800,2100,5600,14950,39850,106300,283450]`, balance `546500` y la ronda 11 vuelve a costar 50 (módulo 10).
- **Fuente**: test_profile_staking.py:test_ten_misses_cycle_in_compare_variant_not_e5_terminal_loss
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-110] Límites de fondos: borde exacto y rung actual/siguiente inasequible
- **Regla**: balance == costo exacto → apuesta y `outcome "ruin"` con balance 0; balance < costo → sin sorteo (cost 0, ruin); si el siguiente rung no es asequible → apuesta actual y `ruin`; alcanzar meta → `goal`; ya en meta → cost 0 y `goal`.
- **Fuente**: test_profile_staking.py:test_exact_funds_boundary_and_unaffordable_current_or_next_rung
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-111] Perfiles/coberturas incompatibles con Q80 rechazados por motivo
- **Regla**: errores `"Q80 payouts"` (70/8/4/2/1 y 160/2), `"Q80 positions"`, `"Q80 universe"` (101), `"Q80 repeats"`, `"DOP"`, `"scale"`, `"increment"`, `"minimum"`, `"coverage"` (max_coverage 20).
- **Fuente**: test_profile_staking.py:test_incompatible_profiles_or_coverage_are_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-112] Topes rechazan la escalera completa, no recortan un rung tardío
- **Regla**: `maximum_stake` < 5669 → `"maximum stake"` (también en `step`); `max_exposure` < 283450 → `"exposure"`; con 5669/283450 la escalera es válida y termina en 5669.
- **Fuente**: test_profile_staking.py:test_profile_caps_reject_whole_ladder_not_clip_a_later_rung
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-113] Cobertura de referencia inválida y entradas de `step`/estado inválidos
- **Regla**: cobertura bool, 0, 80, 100, 1.0 → `ValueError("coverage")`; `step` con unidades bool/negativas, first-hit no bool o goal 0 → `ValueError`; `Q80LadderState(balance<0 | round≥10 | bool)` → `ValueError`.
- **Fuente**: test_profile_staking.py:test_invalid_reference_coverage_is_rejected; test_invalid_step_inputs_fail_explicitly; test_invalid_state_fails_explicitly
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-114] Perfil forjado no evade la compuerta financiera
- **Regla**: `profile.model_copy(update={"scale":1})` se rechaza (`"scale"`) en `q80_first_prize_ladder`.
- **Fuente**: test_profile_staking.py:test_forged_profile_cannot_bypass_financial_gate
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-115] Audaz de referencia Q80 es identidad distinta de Audaz de perfil
- **Regla**: `Q80ReferenceAudazStaking().capability == "transition-1-audaz-reference/v1"` y difiere de `ProfileAudazStaking`.
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_identity_is_distinct_from_profile_audaz
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-116] Audaz de referencia: techo sobre 79 y tope por balance
- **Regla**: `q80_reference_audaz_stake(2000,2800) == 11`; `(1,2800) == 1`; `(100,101) == 1`.
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_uses_ceiling_over_79_and_balance_cap
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-117] Audaz de referencia: balance inicial 0 es quiebre, no meta
- **Regla**: stake 0 con balance 0; `step` con balance 0 → `outcome "quiebre"`, balance 0.
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_initial_zero_is_quiebre_not_goal
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-118] Audaz de referencia: dinero exacto, recomputa y no emite `goal`
- **Regla**: balance 2000, acierto 1.ª posición (80) → cost 11, paid 880, balance 2869, `next_stake 0`, `reset True`, `outcome None` (la meta no genera outcome en este modo).
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_steps_exact_money_and_recomputes_without_goal_outcome
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-119] Audaz de referencia verifica incremento y exposición; sin recorte genérico
- **Regla**: exposición insuficiente → `ValueError("exposure")`; `(10, 100000) == 10`; balance bool → `ValueError("exact integer")`.
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_checks_increment_and_exposure_not_generic_audaz_clipping
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-120] Audaz de referencia: pago secundario no reinicia y reporta tope
- **Regla**: premio 8 → cost 11, paid 88, balance 2077, `next_stake 10`, `reset False`; con balance 10 y meta enorme: cost 10, `next_stake 0`, `capped True`, `outcome "quiebre"`.
- **Fuente**: test_profile_reference_staking.py:test_reference_audaz_secondary_payment_does_not_reset_and_reports_cap
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-121] Registro de capacidades cerrado, único y con pendientes
- **Regla**: `PROFILE_CAPABILITIES` sin duplicados; soportadas por eje: selector (`static-numbers/v1`, `seeded-random/hash-sha256-v1`), staking (`flat-per-number/v1`, `q80-first-prize-cycling/v1`, `profile-audaz/v1`, `profile-recovery-ladder/v1`), entry (`all_rows/v1`), settlement (`all`,`best`) con `schema_version` 1/1/1/2/3/4/1/1/1 y versiones `v1`/`hash-sha256-v1`; pendientes con `schema_version None` (`freq_hist, blend, parity`; `fractional-flat, kelly-binary, fractional-kelly`); `_validate_registry` rechaza duplicados y pendientes mal marcados (`"invalid profile capability"`).
- **Fuente**: test_profile_capabilities.py:test_registry_unique_closed_versions_and_pending_status
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-122] Admisión exacta de capacidad: pendientes, desconocidas, tipo y esquema
- **Regla**: `require_supported(eje, id, schema)` acepta solo el par exacto; versiones 0, equivocada, bool o str → `ValueError("unsupported")`; ids pendientes/desconocidos/de otro eje/None → `unsupported`; `ProfileSelector` con `hash-sha256-v2` → unsupported, con algoritmo `v1` mismatch → `"algorithm"`; `ProfileStaking("kelly-binary")` y `ProfileConditions(schema_version=2)` → unsupported.
- **Fuente**: test_profile_capabilities.py:test_exact_admission_rejects_pending_unknown_wrong_kind_and_schema
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-123] Matriz API proyecta el registro en vivo
- **Regla**: `catalog.profile_execution(ready[, perfil])` devuelve `ready`, listas de capacidades, `requires_compatible_dataset True` y compat Audaz/Recovery; sin perfil solo `flat-per-number/v1` y `available False`; añadir una capacidad soportada al registro aparece de inmediato (proyección viva, no matriz fija); con perfil Q80 incluye cycling/audaz y `maximum_compatible_coverage 50`.
- **Fuente**: test_profile_capabilities.py:test_api_matrix_exact_projection_and_no_pending_families
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-124] Cobertura máxima compatible de Audaz depende del perfil
- **Regla**: con multiplicador[0]=3 → `maximum_compatible_coverage 2` (estrictamente menor que multiplicador[0]); Q80 → 50.
- **Fuente**: test_profile_capabilities.py:test_audaz_metadata_reports_profile_specific_coverage_bound
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-125] Motor de perfil: pagos en unidades enteras para 3 posiciones
- **Regla**: `settle_profile_bet` (`ProfilePayout(cost, paid, net)`): resultados `(7,8,9)` con `{7:1}` → `(1,60,59)`; `{9:1}` → `(1,5,4)`; `{8:2}` → `(2,20,18)`; `{10:1}` → `(1,0,-1)`; combinación `{7:2,8:3,9:1}` → `(6,155,149)`.
- **Fuente**: test_profile_engine.py:test_example_three_position_payouts_in_integer_units
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-126] Repeticiones: `ALL` suma cada posición; `BEST` una vez por número
- **Regla**: resultados `(7,7,8)` con `{7:2,8:3}`: ALL (5,155,150), BEST (5,135,130); `(7,7,7)` BEST → (1,60,59).
- **Fuente**: test_profile_engine.py:test_repeats_all_sum_each_position_best_only_once_per_number
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-127] `maximum-payout/v1` usa el máximo, no el primero
- **Regla**: con multiplicadores `(1,9,2)` y `(7,7,7)`: ALL → paid 24; BEST → paid 18 (máximo, aunque no sea monótono).
- **Fuente**: test_profile_engine.py:test_new_best_uses_maximum_not_first_even_with_nonmonotonic_payout
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-128] `first-match/v0` reservado conserva el primer match
- **Regla**: perfil legacy Q80 `(7,7,8,7,8)` con `{7:1,8:1}`: ALL (2,95,93); BEST (2,84,82); `best_rule == "first-match/v0"`.
- **Fuente**: test_profile_engine.py:test_reserved_legacy_best_preserves_first_match_not_maximum
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-129] Pago racional escalado exacto; premio 0 sin reembolso
- **Regla**: escala 2, incremento 2, multiplicadores 3/2, 0, 1/2: `{1:4,2:2,3:6}` → (12,9,−3); premio 0 → `(2,0,−2)` (no hay reembolso).
- **Fuente**: test_profile_engine.py:test_scaled_rational_payout_is_exact_and_zero_prize_has_no_refund
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-130] Perfiles de 1 y 5 posiciones; política sin repeticiones
- **Regla**: 1 posición (m=3) `{7:2}` → (2,6,4); 5 posiciones sin repeticiones BEST → (3,5,2); resultados con repetición en perfil sin repeticiones → `ValueError("repeat")`.
- **Fuente**: test_profile_engine.py:test_one_and_five_position_profiles_and_no_repeat_policy
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-131] Costo total limitado por presupuesto y capital
- **Regla**: costo 10 con `budget=10, capital=10` permitido; `budget=9` → `"total stake exceeds budget"`; `capital=9` → `"total stake exceeds capital"`; costo > `max_exposure` → `"exposure"`; `budget` bool/float/str/negativo/`> MAX_MONEY` → `ValueError("budget")`.
- **Fuente**: test_profile_engine.py:test_full_cost_must_fit_exposure_budget_and_available_capital
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-132] Sorteos/stakes mal formados o liquidación implícita rechazados
- **Regla**: resultados con longitud ≠ posiciones, bool, float, fuera de [0, universo); stakes vacíos, clave bool o fuera de rango, valor bool/float/0/>maximum; `mode` string o None (la liquidación debe ser `SettlementMode` explícita) → `ValueError`.
- **Fuente**: test_profile_engine.py:test_rejects_malformed_draw_stakes_or_implicit_settlement
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-133] Cobertura, incremento y tipo de mapping exigidos
- **Regla**: más números que `max_coverage` → `"coverage"`; stake fuera de la grilla → `"increment"`; stakes pasados como lista de pares → `TypeError("map")`.
- **Fuente**: test_profile_engine.py:test_coverage_increment_and_input_mapping_enforced
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-134] `model_copy` no evade la validación del perfil
- **Regla**: perfiles copiados con posiciones inconsistentes, `best_rule first-match/v0`, denominador 0, premio fraccionario no exacto o `max_exposure` insuficiente → `ValidationError` al liquidar.
- **Fuente**: test_profile_engine.py:test_model_copy_cannot_bypass_profile_validation
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-135] `ProfilePayout` es frozen
- **Regla**: asignar `paid` → `FrozenInstanceError`.
- **Fuente**: test_profile_engine.py:test_payout_result_is_frozen
- **Categoría**: contrato
- **Riesgo si se pierde**: bajo

### [B-DOM-136] Sesión de perfil: 1/3/5 posiciones y universo propio con contabilidad por número
- **Regla**: 1 posición (m=3, stake 3) → wagered 3, paid 9, balance 26 y `stakes ((7,3),)`; 3 posiciones `(7,7,8)` stake 2: ALL paid 140/balance 158, BEST paid 120/138, outcome GOAL; 5 posiciones sin repeticiones universo 11 con `static(2,4)` stake 3 → (6,12,26); el resultado trae `profile_id`, `profile_revision`, `schema_version 1`.
- **Fuente**: test_profile_session.py:test_one_three_five_and_custom_universe_with_exact_per_number_accounting
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-137] BEST legacy usa el primer match vía liquidación compartida
- **Regla**: perfil legacy Q80 `(7,7,8,7,8)` BEST con `static(7,8)` stake 1 → paid 84, balance 102.
- **Fuente**: test_profile_session.py:test_legacy_best_uses_first_match_via_shared_settlement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-138] Financiación y límites explícitos; sin stake implícito de 1
- **Regla**: capital insuficiente → `"afford"`; stake fuera de grilla → `"increment"`; costo > exposición → `"exposure"`; más números que `max_coverage` → `"coverage"`; número ≥ universo → `"universe"`; `ProfileStaking` exige monto explícito (no hay valor por defecto/posición alternativa).
- **Fuente**: test_profile_session.py:test_explicit_funding_stake_limits_and_no_implicit_one_unit
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-139] Selección estática y seeded-random: determinismo, prefijo y universo del perfil
- **Regla**: mismo seed → misma sesión; cada sorteo elige números distintos; cobertura 1 es prefijo de cobertura 3; otro seed cambia la elección; con universo 7 y cobertura 7 se eligen exactamente 0..6; `seeded-random` sin `algorithm_version` → `ValueError("algorithm")`.
- **Fuente**: test_profile_session.py:test_static_and_seeded_random_determinism_prefix_and_profile_universe
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-140] Resultados futuros no afectan la selección aleatoria
- **Regla**: dos sesiones con distintos resultados del mismo sorteo eligen los mismos números.
- **Fuente**: test_profile_session.py:test_future_results_do_not_affect_random_selection
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-141] Filas omitidas consumen tiempo transcurrido, no apuestas; el inicio se incluye
- **Regla**: `enter=False` incrementa `elapsed_draws` pero no `bet_draws`; con `max_elapsed_draws=3` y `max_bet_draws=3` termina `LIMIT` con `collisions ("max_elapsed_draws",)`, `elapsed 3`, `bet 2`, apuestas en `[START, 05:20]`; con solo `max_bet_draws=2` la colisión es `max_bet_draws`.
- **Fuente**: test_profile_session.py:test_skipped_rows_consume_elapsed_but_not_bet_limit_and_start_is_included
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-142] Prioridad goal/ruina/límites tras liquidar y lista de colisiones
- **Regla**: ganar con límites simultáneos → outcome GOAL, `collisions ("goal","max_bet_draws","max_elapsed_draws")`; perder todo → outcome RUIN con `("ruin","max_bet_draws","max_elapsed_draws")` y balance 0; sin goal/ruina → LIMIT con `("max_bet_draws","max_elapsed_draws")`.
- **Fuente**: test_profile_session.py:test_goal_ruin_and_bet_elapsed_collision_priority_after_settlement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-143] Límites de tiempo exclusivos: el sorteo en el borde se excluye
- **Regla**: `end_minute == minuto del 2º sorteo` y `duration 5` → LIMIT con `collisions ("end_minute","duration_minutes")`, 1 elapsed/1 bet; con `end_minute+1` y duración 6 → `HISTORY_EXHAUSTED`.
- **Fuente**: test_profile_session.py:test_exclusive_time_boundaries_and_collision_exclude_boundary_draw
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-144] Cancelación y agotamiento de historia son distintos
- **Regla**: `cancel_after_elapsed_draws=0` → CANCELLED sin apuestas; `=1` → CANCELLED con elapsed 1/bet 1; agotar filas → `HISTORY_EXHAUSTED` sin colisiones y `elapsed 2`; resultado frozen.
- **Fuente**: test_profile_session.py:test_cancellation_and_history_exhaustion_are_distinct
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-145] `ProfileConditions` rechaza valores implícitos o mal formados
- **Regla**: `start_draw` mal formato, `capital` bool/float/`> MAX_MONEY`, `goal ≤ capital`, `settlement` string, `max_elapsed_draws 0`, `max_bet_draws False`, `end_minute` bool/0, `duration_minutes 0`, `schema_version 2` → `ValueError`.
- **Fuente**: test_profile_session.py:test_conditions_reject_implicit_or_malformed_values
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-146] Entradas tipadas rechazan bool/float y capacidades no soportadas
- **Regla**: `ProfileSelector` rechaza `numbers` bool/float/duplicados, `numbers+seed`, `seed` bool, selector `system`; `ProfileStaking` rechaza stake bool/float y capacidad `ladder`; `ProfileDraw` rechaza minuto inconsistente con la etiqueta, `enter` no bool y resultados float.
- **Fuente**: test_profile_session.py:test_typed_inputs_reject_bool_float_and_unsupported_capabilities
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-147] Registro `CAPABILITIES` conserva familias pendientes y no hay eval
- **Regla**: `static-numbers/v1` y `seeded-random/hash-sha256-v1` `supported`; `kelly-binary`, `blend`, `freq_hist`, `select_interpretable`, `timid`, `conditional-entry` `pending`; `ProfileSelector` con `blend/parity/freq_hist/import-code` → `ValueError("unsupported")` (nunca código importado).
- **Fuente**: test_profile_session.py:test_capability_registry_retains_pending_families_and_has_no_eval
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-148] Filas inválidas se rechazan aun tras un evento terminal
- **Regla**: una fila posterior con posiciones incorrectas → `"positions"` aunque la sesión haya terminado; resultados fuera de rango, bool o float → error; repetición en perfil sin repeticiones → `"repeat"`; fila antes del inicio o duplicada → `"chronological"`; falta del sorteo inicial → `"start draw"`; objeto que no es `ProfileDraw` → `TypeError("ProfileDraw")`.
- **Fuente**: test_profile_session.py:test_invalid_rows_rejected_even_when_after_terminal_event
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-149] Filas acotadas, sin materializar generadores, presupuesto estricto
- **Regla**: un generador → `TypeError("bounded materialized")`; `> MAX_SESSION_ROWS` filas, `row_budget=0` o `row_budget < filas` → `ValueError("budget")`; `cancel_after_elapsed_draws=True` → `"cancel_after"`.
- **Fuente**: test_profile_session.py:test_bounded_rows_no_generator_materialization_and_strict_budget
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-150] Modelos frozen mutados se revalidan
- **Regla**: perfil copiado inconsistente → `ValidationError`; `ProfileConditions.capital=True` forjado → `ValueError("capital")`; `ProfileDraw.results` forjado → `"results"`; `replace(flat, per_number_stake=2.0)` → error.
- **Fuente**: test_profile_session.py:test_mutated_frozen_profile_and_session_models_revalidated
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-151] Variante Q80 cycling es privada: identidad validada sin admisión por registro
- **Regla**: `Q80CyclingStaking()` = `(1, "q80-first-prize-cycling/v1")`, versiones/capacidades distintas → `ValueError`, frozen; capability forjada → `"policy"`; `ProfileStaking("q80-first-prize-cycling/v1")` → `"unsupported"` (no entra por el v1); el request v1 flat sigue funcionando, el wire v1 con la capacidad cycling → unsupported, y `ProfileExperimentRequest` con `Q80CyclingStaking` → `TypeError("ProfileStaking")`.
- **Fuente**: test_profile_session.py:test_private_q80_variant_validates_identity_without_registry_admission
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-152] Audaz de perfil: cobertura 50 en all/best sobre Q80
- **Regla**: stake inicial 27 en ambos modos; paid `27×95` (all) y `27×83` (best); outcome GOAL; balances `2000−1350+27×95` / `…×83`.
- **Fuente**: test_profile_session.py:test_private_profile_audaz_settles_q80_coverage_fifty_in_all_and_best
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-153] Audaz de perfil Q80 k=1 coincide con el oráculo de referencia
- **Regla**: `stakes ((7,11),)`, wagered 11, paid 1012, balance 3001, GOAL.
- **Fuente**: test_profile_session.py:test_private_profile_audaz_q80_k1_matches_reference_oracle
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-154] Audaz es genérico por perfil y se recalcula tras liquidar
- **Regla**: perfil universo 37, 1 posición, m=25/2, escala 1, incremento 2 con cobertura 3: stake 12, wagered 36, paid 150, balance 214 y GOAL.
- **Fuente**: test_profile_session.py:test_private_profile_audaz_is_profile_generic_and_recomputed_after_settlement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-155] Audaz: topes y ruina con residual positivo; capital inicial inasequible se rechaza antes
- **Regla**: stake acotado a 27 con capital 2000; con capital 1399 el siguiente stake no es asequible → `RUIN` con balance residual 49 tras 1 apuesta; capital inicial que no cubre la primera apuesta → `ValueError("initial capital cannot afford")` (no es un RUIN de sesión).
- **Fuente**: test_profile_session.py:test_private_profile_audaz_caps_stakes_and_ruins_with_positive_residual
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-156] Audaz sin entrada no apuesta; margen no positivo rechazado
- **Regla**: filas con `enter=False` → `elapsed 2`, `bet_draws 0`, balance intacto; perfil con m1 ≤ cobertura → `"greater than coverage"`.
- **Fuente**: test_profile_session.py:test_private_profile_audaz_skips_without_staking_and_rejects_negative_margin
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-157] Recovery ladder con parámetros Q80 == secuencia cycling Q80
- **Regla**: `ProfileRecoveryLadderStaking(10,10,"cycle")` produce una sesión idéntica a `Q80CyclingStaking` (apuestas `[50,100,300,…,283450,50]`) sin cambiar el comportamiento Q80.
- **Fuente**: test_profile_session.py:test_private_recovery_ladder_q80_parameters_match_cycle_sequence_without_changing_q80
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-158] Recovery ladder respeta modos de liquidación
- **Regla**: `(7,7,7,8,9)` con cobertura 50: ALL paid 95/balance 2045; BEST paid 83/balance 2033.
- **Fuente**: test_profile_session.py:test_private_recovery_ladder_binds_settlement_modes_and_result_hit
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-159] Recovery: secundario avanza, 1.ª posición reinicia, omitidas solo consumen tiempo
- **Regla**: con multiplicadores 4/3/2, margen 10, 2 rondas: apuestas `[(10,30),(40,160),(10,30)]`, `elapsed 4`, `bet 3` (la fila con `enter=False` no avanza la ronda).
- **Fuente**: test_profile_session.py:test_private_recovery_ladder_secondary_advances_first_hit_resets_and_skip_consumes_only_time
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-160] Recovery `stop`: límite tras rondas y prioridad de goal
- **Regla**: tras fallar todas las rondas configuradas el outcome es `LIMIT` con `collisions ("recovery_round_limit",)` y 2 apuestas; si la meta se logra en el último rung, GOAL prevalece sobre el stop; capital que no cubre la primera apuesta → `"initial capital cannot afford"`.
- **Fuente**: test_profile_session.py:test_private_recovery_ladder_stop_after_configured_misses_and_terminal_priority
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-161] Recovery: ruina por siguiente stake inasequible; staking frozen
- **Regla**: capital 30 → RUIN con balance 0 tras 1 apuesta; `ProfileRecoveryLadderStaking` frozen.
- **Fuente**: test_profile_session.py:test_private_recovery_ladder_next_stake_ruin_and_cycle_then_repeat
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-DOM-162] Staking Audaz fuera del wire v1
- **Regla**: `ProfileStaking("profile-audaz/v1")` → `unsupported`; `ProfileAudazStaking(2, ...)` o capacidad `q80-cycling/v1` → `ValueError`.
- **Fuente**: test_profile_session.py:test_private_profile_audaz_staking_remains_outside_v1_request_wire
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-163] Q80: secundario avanza y primer premio reinicia desde el mismo sorteo
- **Regla**: tres sorteos: stakes `[1,2,1]`, `wagered [50,100,50]`, paid ALL `[8,184,0]` (balances 1958, 2042, 1992) y BEST `[8,160,0]` (1958, 2018, 1968); sesión determinista (reejecución idéntica).
- **Fuente**: test_profile_session.py:test_q80_secondary_only_advances_then_first_hit_resets_from_same_draw
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-164] Q80: diez fallos ciclan y las omitidas no avanzan la ronda
- **Regla**: 12 filas (una `enter=False`): `elapsed 12`, `bet 11`, apuestas `[50,100,300,800,2100,5600,14950,39850,106300,283450,50]`, balance final 546450, outcome `HISTORY_EXHAUSTED`.
- **Fuente**: test_profile_session.py:test_q80_ten_misses_cycle_and_skips_do_not_advance_round
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-165] Audaz de referencia (`transition-1-audaz-reference/v1`) liquida Q80 k=1
- **Regla**: capacidad distinta de Audaz de perfil; Q80 k=1 → stake 11, wagered 11, paid 1012, balance 3001, GOAL; con perfil de pagos incompatibles → `ValueError("payouts")`.
- **Fuente**: test_profile_session.py:test_private_reference_audaz_staking_is_distinct_and_settles_q80_k1
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-166] Admisión Q80 valida la escalera completa y el capital inicial
- **Regla**: perfil de 3 posiciones → `"Q80 positions"`; `maximum_stake 5668` → `"maximum stake"`; `max_exposure 283449` → `"exposure"`; capital 49 → `"afford"`.
- **Fuente**: test_profile_session.py:test_q80_admission_checks_whole_ladder_and_initial_affordability
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-167] Q80: ruina con residual positivo y prioridad goal/límite
- **Regla**: capital 99 con siguiente rung 100 → RUIN con balance 49 y colisiones `("ruin","max_bet_draws","max_elapsed_draws")`; goal en la última apuesta → `("goal",…)`, balance 80; primera fila `enter=False` con `max_elapsed_draws=1` → LIMIT con 0 apuestas y balance 99.
- **Fuente**: test_profile_session.py:test_q80_next_stake_ruin_with_positive_residual_and_goal_limit_priority
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-168] Q80: límites de tiempo, cancelación e historia censurada
- **Regla**: historia agotada con meta no alcanzada → `HISTORY_EXHAUSTED` sin colisiones (2 apuestas); cancelación tras 1 elapsed → CANCELLED (1 apuesta); `end_minute` en el segundo sorteo → LIMIT con `("end_minute","duration_minutes")` y 1 apuesta.
- **Fuente**: test_profile_session.py:test_q80_time_limits_cancellation_and_censored_history
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-169] Q80 con selección semilla: determinista y atada a la etiqueta de cada sorteo
- **Regla**: mismas filas → sesiones iguales; el número se elige por etiqueta (no por resultado previo); premio secundario repetido paga 15 (k=1: 8+4+2+1), el segundo sorteo paga 80 solo si coincide el número elegido, y el stake del 2º sorteo es 1 (un acierto secundario no reinicia pero las rondas k=1 igualan).
- **Fuente**: test_profile_session.py:test_q80_seeded_selection_and_draw_binding_are_deterministic
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-170] Techo de dinero total tras varios sorteos
- **Regla**: `goal > MAX_MONEY` → `ValueError("goal")`; capital `MAX_MONEY−2` con 2 sorteos stake 1 permanece válido (wagered = paid = 2); un perfil cuyo pago desborda `MAX_MONEY` → `ValueError("session totals")`.
- **Fuente**: test_profile_session.py:test_total_money_ceiling_after_multiple_draws
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-171] Evolución v5 (lote privado): definición cerrada y codec canónico
- **Regla**: `ProfileBatchRequestV5` (`schema_version 5`, `kind "profile_batch"`, lista de `StrategyDefinition`, `max_draws`) hace round-trip y re-serializa idéntico; `StrategyDefinition` es frozen; campo extra → `ValueError("exactly")`; claves duplicadas → `"duplicate"`; un wire v1 (`ProfileExperimentRequest`) sigue cargando con su parser y es rechazado por el parser v5 (`"version"`).
- **Fuente**: test_profile_v5.py:test_closed_definition_and_canonical_batch_codec_reject_legacy_versions
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-172] Sesión sobre archivo: inicio rankeado obligatorio; saltos de filas sin ranking
- **Regla**: `start_draw` sin ranking → `ValueError("ranked start")`; con inicio válido el run tiene `ordinal 0`, `elapsed_draws 4` (cuenta las filas sin ranking), apuestas solo en sorteos rankeados, `prior_cutoff None` para `reference_cold_25`; el resultado valida por replay, hace round-trip y alterar `final_balance` → `"replay"`.
- **Fuente**: test_profile_v5.py:test_archive_session_requires_ranked_start_and_skips_gap_rows
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-173] Referencia de paridad usa historia causal completa y liquidación
- **Regla**: `reference_parity_50` en `00:02` apuesta a `binding.select("parity", 2, 50)` con stake 1 por número, `wagered 50` y `prior_cutoff "2025-01-01 00:01"` (el voto usa solo sorteos anteriores).
- **Fuente**: test_profile_v5.py:test_reference_parity_uses_full_causal_history_and_settlement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-174] Presupuesto de operaciones v5 sin techo legacy de filas
- **Regla**: `operation_budget < max_draws` → `ValueError("operation budget")`; el límite de filas fuente legacy no se aplica a v5.
- **Fuente**: test_profile_v5.py:test_v5_operation_budget_does_not_apply_legacy_source_row_ceiling
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-175] Lote: nombres únicos, límites válidos, cierre por estrategia, recomendación de liquidación
- **Regla**: nombres duplicados ignorando mayúsculas/espacios → `"unique"`; `max_draws=True` → `"max_draws"`; `closing_defaults` con `max_bet_draws` distinto es aceptado; `closing_defaults settlement` que contradice la liquidación de condiciones → `"settlement recommendation"`.
- **Fuente**: test_profile_v5.py:test_batch_rejects_duplicate_names_invalid_limits_and_close_override
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-176] Codecs v5 rechazan campos anidados desconocidos y versión de resultado
- **Regla**: `selector_parameters` con clave extra (`eval`) → `ValueError("unknown selector")`; resultado con `schema_version 4` → `ValueError("version")`.
- **Fuente**: test_profile_v5.py:test_v5_codecs_reject_unknown_nested_fields_and_result_version
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-177] Definición de referencia Transition-Audaz exige cobertura uno
- **Regla**: `reference_transition_audaz` = selector `archived-transition/v1`, staking `q80-reference-audaz/v1`; cobertura ≠ 1 → `ValueError("coverage one")`.
- **Fuente**: test_profile_v5.py:test_transition_reference_definition_rejects_invalid_coverage
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-178] Cobertura de Audaz genérico usa el dominio del perfil, no el límite Q80
- **Regla**: `profile-audaz/v1` acepta coberturas 79, 80, 100, 101, 1000 y rechaza 1001 (`"coverage"`); `q80-first-prize-cycling/v1` acepta 1 y 79 y rechaza 80 (`"Q80 cycling"`); selector archivado acepta 100 y rechaza 101 (`"archived selector coverage"`).
- **Fuente**: test_profile_v5.py:test_generic_audaz_coverage_uses_profile_domain_not_q80_reference_limit
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-DOM-179] Perfil custom de universo 1000: flat y Audaz corren un sorteo
- **Regla**: con universo 1000, 1 posición, m=1001: estrategia flat de 1000 números (wagered 1000) y `profile-audaz` (wagered 2000, 1000 stakes) corren 1 `bet_draw`.
- **Fuente**: test_profile_v5.py:test_custom_1000_universe_flat_and_profile_audaz_run_one_draw
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-180] Recovery v5 con límite de rondas: round-trip, replay y manipulación
- **Regla**: con `end_mode stop`, `rounds 2`, `target_margin 10`: apuestas `[10,40]` por número y `collisions ("recovery_round_limit","max_bet_draws")`; el wire hace round-trip y valida; añadir colisión `unknown-limit` → `"invalid collisions"`; alterar `collisions`, los stakes de una ronda o `max_bet_draws` de las condiciones → `"replay"`/`ValueError`.
- **Fuente**: test_profile_v5.py:test_v5_recovery_round_limit_result_round_trips_and_replays
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-181] `closing_defaults` no sobrescriben condiciones compartidas en replay
- **Regla**: con `conditions.max_bet_draws=1` y `BEST`, dos estrategias con `closing_defaults` de 2 y 3 apuestas ejecutan ambas 1 apuesta con sesiones idénticas y `collisions ("max_bet_draws",)`, conservando sus `closing_defaults` en el resultado; el preset de referencia con recomendación de liquidación incompatible → `"settlement recommendation"`; el resultado valida por replay.
- **Fuente**: test_profile_v5.py:test_v5_closing_defaults_do_not_override_shared_conditions_on_replay
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-182] Biblioteca de estrategias: codec cerrado y hash canónico
- **Regla**: `definition_snapshot` produce JSON con el nombre (unicode intacto) y `definition_sha256 == sha256(json utf-8)`; `strategy_payload` con campo desconocido → `ValueError`.
- **Fuente**: test_strategy_library.py:test_closed_definition_codec_and_canonical_hash
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-DOM-183] Compatibilidad de estrategia con perfil es contextual
- **Regla**: `compatibility_projection(definition, profile)` devuelve `profile_compatible True` para una estática válida y no ofrece ejecución (`execution_available False`); un preset de referencia solo es compatible con su perfil exacto (paridad-50 con perfil de prueba → False).
- **Fuente**: test_strategy_library.py:test_profile_compatibility_is_contextual_and_presets_require_exact_reference
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-184] Audaz genérico: matemática del perfil, no Q80 ni admisión falsa de capital
- **Regla**: perfil genérico (universo 1000, USD, escala 2, m=10/2) → Audaz de 2 números compatible; si m1 no deja ganancia (4/2) → incompatible con motivo "first-position"; cobertura 1000 es un límite del perfil, no del Q80 (estrategia ancha compatible).
- **Fuente**: test_strategy_library.py:test_generic_profile_staking_math_is_not_q80_or_fake_capital_admission
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-185] Recovery genérico verifica exposición por rung y topes de stake
- **Regla**: `profile-recovery-ladder` es compatible en el perfil genérico; `maximum_stake 20` → incompatible con motivo "maximum stake"; sin ganancia en 1.ª posición → "first-position"; con mínimo = máximo = 20 y 1 ronda es compatible (`ladder == (20,)`); exposición que se supera en un rung tardío → "profile exposure".
- **Fuente**: test_strategy_library.py:test_generic_recovery_ladder_checks_full_rung_exposure_and_stake_caps
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-DOM-186] Identidad de preset de referencia estable ante renombrado
- **Regla**: `reference_preset_id` válido (`preset-paridad-50-plana`) se reconoce aunque cambie el nombre; id forjado o parámetros alterados → `ValueError("reference preset")`; copias/variantes usan la matemática genérica (compatibles en perfil de prueba); el preset es compatible con el perfil legacy Q80.
- **Fuente**: test_strategy_library.py:test_reference_identity_is_stable_when_definition_name_changes
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

<!-- B-DOM:fin -->

## 3. B-STO — Persistencia

### [B-STO-001] Migración 11 preserva filas v10 y claves foráneas
- **Regla**: migrar una BD poblada en v10 a v11 conserva el experimento/run existentes, añade `request_schema_version 1` y `result_schema_version 1`, `user_version == 11` y `PRAGMA foreign_key_check` vacío.
- **Fuente**: test_batch_admission.py:test_migration_11_preserves_populated_v10_rows_and_foreign_keys
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-002] Crear estrategia: snapshot exacto, hash y estado de ejecución tras reabrir
- **Regla**: `create_strategy` devuelve `revision 1`, `definition_sha256 == sha256(definition_json)`; `page_strategies` cuenta 1; reabrir `Repository` devuelve el mismo registro con `execution_available False` y `execution_unavailable_reason` que menciona `ProfileBatchRequestV5`.
- **Fuente**: test_strategy_library.py:test_create_page_reopen_preserves_exact_snapshot_hash_and_execution_state
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-003] Append de revisión es CAS y revisiones antiguas son inmutables
- **Regla**: `append_strategy_revision(id, esperada, ...)` crea la revisión 2; la 1 conserva su `definition_json`; esperada obsoleta → `ValueError("revision conflict")`; `latest_revision` queda en 2.
- **Fuente**: test_strategy_library.py:test_append_is_cas_and_old_revision_is_immutable
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-004] Siembra de presets idempotente; originales protegidos solo-copia
- **Regla**: `seed_presets` dos veces devuelve los mismos 3 ids; `UPDATE strategies` sobre presets → `IntegrityError("immutable")`; `append_strategy_revision` sobre un preset → `ValueError("protected")`; la copia propia recibe id distinto.
- **Fuente**: test_strategy_library.py:test_preset_seed_is_idempotent_and_protected_originals_are_copy_only
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-005] Filas manipuladas se detectan como corruptas
- **Regla**: definición con campo desconocido → `ValueError`; si se altera `definition_json` (quitando el trigger) la lectura → `ValueError("corrupt")`.
- **Fuente**: test_strategy_library.py:test_invalid_definitions_and_tampered_rows_are_rejected
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-006] Cuota de estrategias exacta en bytes UTF-8 y rollback
- **Regla**: `strategy_artifact_bytes` = suma de bytes UTF-8 de id, nombre, created_at, +9, id, +16, sha256, definition_json y revision_created_at; límite `candidate` con margen `min(LOGICAL_MARGIN_BYTES, max(1,c//20))` → `QuotaExceeded` y 0 bytes persistidos; un trigger que aborta el INSERT deja 0 bytes (transacción atómica).
- **Fuente**: test_strategy_library.py:test_exact_utf8_quota_and_failed_transaction_rollback
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-007] `INSERT OR REPLACE` no puede mutar ninguna cabecera de estrategia
- **Regla**: con foreign_keys ON, `INSERT OR REPLACE INTO strategies` sobre un preset o una estrategia propia → `IntegrityError("immutable")`; el preset sigue `protected` con su definición original.
- **Fuente**: test_strategy_library.py:test_replace_cannot_mutate_any_existing_strategy_head
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-008] Identidad protegida desconocida o preset forjado se rechaza
- **Regla**: estrategia no preset marcada `protected=1` → `ValueError("protected preset")` en `get_strategy`/`page_strategies`; un preset con definición forjada y hash recomputado → `"protected preset"` en `get_strategy`, `get_strategy_revision` y `page_strategies`.
- **Fuente**: test_strategy_library.py:test_unknown_protected_identity_is_rejected_on_get_and_list; test_known_preset_reads_reject_forged_definition_with_recomputed_hash
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-009] Reabrir un resultado completo sin motor ni fuentes
- **Regla**: tras `complete_experiment`, un nuevo `Repository` devuelve estado COMPLETED, `request_kind "legacy"`, `request == original`, IDs/sha de historia y rankings, `code_version`, `seed`, run con resultado igual y `configuration_id`; no se recalcula `run_session`.
- **Fuente**: test_storage.py:test_reopen_complete_result_without_engine_or_source_files
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-010] Resultado legacy rechaza sobre versionado sin reescribir el wire
- **Regla**: un `result_json` legacy al que se le agrega `kind/schema_version` → `ValueError("legacy result wire")` al leer.
- **Fuente**: test_storage.py:test_legacy_result_refuses_versioned_envelope_without_rewriting_wire
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-011] Mutar/borrar configuración conserva el historial
- **Regla**: actualizar una configuración no cambia el snapshot del experimento (`Cold` permanece); borrarla deja `configuration_id None` en el run y conserva el resultado; borrar experimento devuelve True y un segundo borrado False.
- **Fuente**: test_storage.py:test_configuration_mutation_and_deletion_keep_history
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-012] Runs completados inmutables; validación atómica
- **Regla**: `complete_run` con resultado inconsistente (`paid` ≠ suma de apuestas) → `ValueError("paid")` y el run sigue RUNNING; `complete_experiment` con runs incompletos → `ValueError("incomplete runs")`; tras completar, completar de nuevo o `mark_run` → `ValueError` y el resultado persiste.
- **Fuente**: test_storage.py:test_immutable_completed_runs_and_atomic_validation
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-013] Estados incompletos nunca reclaman finalización
- **Regla**: PENDING/INTERRUPTED/HELD no tienen resultado y `complete_experiment` falla; INTERRUPTED conserva `result None`.
- **Fuente**: test_storage.py:test_incomplete_states_never_claim_completion
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-014] Registros faltantes y enlaces inválidos
- **Regla**: `get_experiment/get_configuration("missing")` → None, `delete_configuration("missing")` → False; crear experimento con configuración inexistente → `ValueError("configuration")`; IDs de fuente vacíos → `ValueError("source IDs")`; nada queda persistido.
- **Fuente**: test_storage.py:test_missing_records_and_invalid_configuration_link
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-STO-015] Comparación conserva el run completado cuando otro se cancela
- **Regla**: solo un run RUNNING a la vez (`"already running"`); no se puede borrar un experimento running (`"running experiment"`); con run 0 completado y run 1 NOT_RUN + experimento CANCELLED: resultados conservados y `complete_experiment` → ValueError.
- **Fuente**: test_storage.py:test_comparison_retains_completed_run_when_another_is_cancelled
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-016] Fallo local: finalizar exige todos terminales y preserva resultados
- **Regla**: `fail_run` solo sobre RUNNING (`"not running"`); `fail_experiment_after_runs` con runs no terminales → `"nonterminal"`; `complete_experiment` con runs fallidos → `"incomplete runs"`; al estar todos terminales el experimento queda FAILED con `[COMPLETED, FAILED, COMPLETED]` y resultados intactos; repetir → ValueError.
- **Fuente**: test_storage.py:test_local_failure_finalize_requires_all_terminal_and_preserves_results
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-017] Fallo de insert revierte experimento y runs
- **Regla**: un trigger que aborta el insert del run 1 deja 0 filas en `experiments` y `runs`.
- **Fuente**: test_storage.py:test_insert_failure_rolls_back_experiment_and_runs
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-018] Migración v1→actual conserva datos y añade `created_at` NULL; idempotente
- **Regla**: base v1 se actualiza a `SCHEMA_VERSION`, `created_at` queda NULL para filas previas (`saved.created_at None`), repetir `initialize_database` es no-op.
- **Fuente**: test_storage.py:test_migration_from_v1_preserves_data_and_adds_created_at
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-019] Migración v2 conserva registros y preferencia de cuota vacía; concurrente
- **Regla**: v2→actual (con 8 inicializaciones en 4 hilos) conserva experimento y run (`created_at` intacto) y deja `settings_quota` vacía.
- **Fuente**: test_storage.py:test_migration_from_v2_preserves_records_and_empty_preference
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-020] Migración revierte todo el DDL si falla un paso
- **Regla**: si el paso 2 falla, `user_version` queda en 1 y `created_at` no existe; tras restaurar, reintentar funciona.
- **Fuente**: test_storage.py:test_migration_rolls_back_all_ddl_if_second_step_fails
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-021] Upgrade concurrente desde v1 es idempotente
- **Regla**: 8 inicializaciones en 4 hilos dejan `user_version == SCHEMA_VERSION` y exactamente una columna `created_at`.
- **Fuente**: test_storage.py:test_concurrent_upgrade_from_v1_is_idempotent
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-022] BD nueva aplica migraciones en orden y siembra el perfil legacy
- **Regla**: BD nueva: `created_at` existe, `game_profiles` contiene 1 fila, `experiment_profiles` 0 y `list_game_profiles() == [legacy_quiniela_80_profile()]`.
- **Fuente**: test_storage.py:test_fresh_database_applies_migrations_in_order
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-023] Upgrade desde v1/v2/v3 rellena filas históricas sin reescribir bytes
- **Regla**: `request_json`/`result_json` históricos se conservan byte a byte (incluyendo montos mayores a los topes nuevos del perfil, p. ej. `wagered 1000000001`); `experiment_profiles` queda con 2 filas (completado y pendiente) con el perfil legacy; el estado pendiente se mantiene.
- **Fuente**: test_storage.py:test_upgrade_backfills_all_historical_rows_without_rewriting_bytes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-024] Backfill fallido revierte DDL y versión
- **Regla**: si el backfill de la migración 4 falla (trigger), `user_version` queda en 3, `game_profiles` no existe, los bytes originales siguen; tras corregir, la migración completa y el experimento recibe el perfil legacy.
- **Fuente**: test_storage.py:test_failed_backfill_rolls_back_ddl_and_version
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-025] Upgrade v4→v5 conserva bytes legacy sin backfill de datasets
- **Regla**: inicialización concurrente de una BD v4 conserva `game_profiles`, `experiment_profiles`, `request_json` y deja `datasets` en 0.
- **Fuente**: test_storage.py:test_upgrade_v4_to_v5_preserves_legacy_bytes_without_backfill
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-026] Upgrade v5→v8 conserva request/result y etiqueta `legacy` v1
- **Regla**: filas v5 quedan con `request_kind "legacy"`, `request_schema_version 1`, `result_kind "legacy"`, `result_schema_version 1` y bytes intactos (incluyendo espacios en el JSON).
- **Fuente**: test_storage.py:test_upgrade_v5_to_v8_keeps_request_and_result_bytes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-027] Migración 7 conserva wire schema-6 y revierte
- **Regla**: el wire profile pendiente se conserva byte a byte con `request_schema_version 1` y `result_*` NULL; si la migración 7 falla, `user_version` queda en 6 sin la columna `request_schema_version` y los bytes intactos; reintentar completa (dos veces idempotente).
- **Fuente**: test_storage.py:test_seventh_migration_preserves_schema6_wire_and_rollback
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-028] Fallos de migración 6 y 5 revierten a la versión previa
- **Regla**: fallo de `0006_profile_requests` deja `user_version 5` sin `request_kind`; fallo de `0005_datasets` deja `user_version 4` sin tabla `datasets`; tras restaurar el reintento funciona.
- **Fuente**: test_storage.py:test_sixth_migration_failure_rolls_back_v5; test_fifth_migration_failure_rolls_back_v4
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-029] Perfiles: versiones inertes, inmutables y round-trip
- **Regla**: `create_game_profile` devuelve el perfil; reintento idéntico no-op (`profile_artifact_bytes` sin cambio); `profile_artifact_bytes` suma bytes UTF-8 del JSON; `list_game_profiles` ordena `[custom r1, custom r2, legacy]`; `get_game_profile` de revisión inexistente → None; mismo id/revisión con contenido distinto → `ValueError("different content")`; perfil forjado con `model_copy` → `ValueError("maximum stake exceeds")`; UPDATE sobre `game_profiles` → `IntegrityError("immutable")`, DELETE → `"append-only"`.
- **Fuente**: test_storage.py:test_profile_versions_are_inert_immutable_and_roundtrip
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-030] Snapshot de perfil por experimento inmutable y contabilizado
- **Regla**: crear experimento añade el snapshot legacy (`profile_artifact_bytes` +bytes del JSON); UPDATE/DELETE de `experiment_profiles` → `IntegrityError("immutable")`; borrar el experimento libera el snapshot sin tocar `game_profiles`.
- **Fuente**: test_storage.py:test_profile_versions_are_inert_immutable_and_roundtrip
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-031] `page_game_profiles`: orden estable, validación de identidad, sin lecturas totales
- **Regla**: paginación por clave `(custom r1, custom r2, legacy)` con `total 3` sin usar `get_game_profile`/`list_game_profiles`; offset/limit inválidos (neg, 0, 101, bool) → `ValueError("offset and limit")`; contenido cuyo id difiere de la clave → `ValueError("corrupt game profile identity")`.
- **Fuente**: test_storage.py:test_profile_page_uses_stable_key_order_and_validates_stored_identity
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-032] Snapshot faltante o corrupto → error de integridad sin fallback legacy
- **Regla**: si falta la fila `experiment_profiles`, o su JSON es inválido (`{}`) o su revisión difiere, `get_experiment` y `search_experiments` → `ValueError("missing or corrupt")` (nunca se cae silenciosamente al perfil legacy).
- **Fuente**: test_storage.py:test_missing_or_corrupt_snapshot_is_integrity_error; test_corrupt_profile_snapshot_never_silently_falls_back_to_legacy
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-033] `created_at` en UTC ISO-8601 con sufijo Z e inmutable
- **Regla**: `created_at` es UTC con offset 0; no cambia al iniciar/finalizar.
- **Fuente**: test_storage.py:test_create_experiment_sets_created_at_in_utc_iso8601
- **Categoría**: formato
- **Riesgo si se pierde**: medio

### [B-STO-034] `search_experiments`: filtro, orden, paginación y escape de comodines
- **Regla**: `name_contains` es literal (`%` y `_` no son comodines, `\` literal), case-insensitive incluso para no-ASCII (`Éclair`/`éCLAIR`); `status` filtra; `sort name asc` ordena; `total` refleja el filtrado; offset sobre el total → filas vacías con total correcto.
- **Fuente**: test_storage.py:test_search_experiments_filters_sorts_and_paginates; test_search_combined_filters_literal_escape_and_stable_page
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-035] Orden por defecto: `created_at` desc con desempate por id desc
- **Regla**: ante `created_at` empatado, el orden es `id` descendente determinista.
- **Fuente**: test_storage.py:test_search_experiments_default_order_is_created_at_desc_with_id_tiebreak
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-STO-036] Búsqueda rechaza sort/order/status/offset/limit inválidos
- **Regla**: `sort="not_a_column"`, `order="sideways"`, `status="not_a_status"`, offset negativo, limit 0 o 101 → `ValueError` (whitelist, nunca SQL dinámico).
- **Fuente**: test_storage.py:test_search_experiments_rejects_invalid_sort_or_status
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-037] Inicialización repetida y versión no soportada
- **Regla**: `initialize_database` crea directorios y es repetible; `user_version 99` → `UnsupportedSchema("99")` sin modificar la BD (también para `Repository(path)`); una BD no vacía con versión 0 → `UnsupportedSchema("version 0")` sin tocarla.
- **Fuente**: test_storage.py:test_initialization_repeat_and_unsupported_version
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-038] Inicialización concurrente repetible; `Repository` no inicializa implícitamente
- **Regla**: 8 inicializaciones en 4 hilos → una tabla `runs` y versión actual; `Repository(path)` inexistente → `FileNotFoundError` sin crear archivo.
- **Fuente**: test_storage.py:test_concurrent_initialization_is_repeatable; test_repository_does_not_initialize_implicitly
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-039] Ruta por defecto de datos fuera del repositorio
- **Regla**: sin `LABORATORIO_DATA_DIR`, `database_path` termina en `AppData/Local/LaboratorioQuiniela/laboratorio.db` (bajo `LOCALAPPDATA`).
- **Fuente**: test_storage.py:test_settings_default_not_under_repository
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-STO-040] Migración v7→v9 conserva bytes y revierte atómicamente
- **Regla**: tras v7→v9: `user_version 9`, `foreign_key_check` vacío, bytes de request/result/profile y configuraciones ajenas intactos; `request_schema_version` admite 3 y 4 y rechaza 5 (`IntegrityError`); si falla el paso 9 la BD queda en v7 con bytes intactos y sin tabla `experiments_v9`.
- **Fuente**: test_storage.py:test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically
- **Categoría**: contrato
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

### [B-STO-041] Request de perfil preparado carga tipado y `create_experiment` lo rechaza
- **Regla**: un experimento de perfil insertado (kind `profile`) carga con `request` tipado, `runs[0].result_kind "profile"`, PENDING; aparece en `search_experiments`; `create_experiment` legacy con un request de perfil → `ValueError("validated request")` (solo hay rutas dedicadas de admisión).
- **Fuente**: test_profile_storage.py:test_prepared_profile_request_loads_typed_without_exposing_enqueue
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-042] Discriminador y wire deben coincidir
- **Regla**: `request_kind legacy` sobre un wire de perfil, `request_json {}` o JSON inválido → `ValueError` al leer.
- **Fuente**: test_profile_storage.py:test_request_discriminator_and_wire_must_agree
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-043] Identidad del snapshot y hash completo deben coincidir
- **Regla**: `request_json` con `profile_sha256` distinto → `ValueError("differs from experiment profile snapshot")`.
- **Fuente**: test_profile_storage.py:test_snapshot_identity_and_full_hash_must_agree
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-044] Mezcla de tipos y resultados de perfil corruptos fallan cerrado
- **Regla**: request profile con run `result_kind legacy` → `"mixed request/result kind"`; run profile completado con `result_json {}` → `ValueError("result")`.
- **Fuente**: test_profile_storage.py:test_mixed_kind_and_completed_profile_results_fail_closed
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-045] `complete_run` legacy no puede escribir un run de perfil
- **Regla**: `complete_run` sobre un run de perfil → `ValueError("profile completed results are not supported")` antes de validar; el run queda `running` sin `result_json`.
- **Fuente**: test_profile_storage.py:test_legacy_completion_cannot_write_profile_run
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-046] Discriminadores de esquema rechazan valores desconocidos
- **Regla**: `request_kind = 'unknown'` y `result_kind = 'unknown'` → `IntegrityError` (CHECK).
- **Fuente**: test_profile_storage.py:test_schema_discriminators_reject_unknown_values
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-047] `create_profile_experiment` exige perfil y dataset exactos registrados
- **Regla**: perfil no registrado → `ValueError("registered")`; sha de perfil distinto → `"registered"`; dataset inexistente → `"dataset not found"`; `start_draw` ausente del dataset → `"start draw"`; no quedan runs ni experimentos; un trigger que rompe el insert del snapshot revierte todo; dataset con bytes alterados → `"corrupt stored dataset"`.
- **Fuente**: test_profile_storage.py:test_create_requires_registered_exact_profile_and_dataset
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-048] Creación atómica con procedencia y cuota exacta
- **Regla**: el experimento guarda `request`, `profile` y procedencia (`history_id = history_sha256 = dataset_sha256`, `rankings_* ""`, `code_version "profile-v1"`); `request_json` serializado y snapshot idénticos a los bytes canónicos; cuota exacta: con límite = uso+delta+margen → `QuotaExceeded` (sin cambios tras el rechazo).
- **Fuente**: test_profile_storage.py:test_create_atomic_snapshot_provenance_and_exact_quota
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-049] `complete_profile_run` reejecuta todas las filas y carga resultado tipado
- **Regla**: valida por replay con todas las filas del dataset (`2025-09-01..03`), guarda `result_json == serialize_profile_result`, estado COMPLETED y `complete_experiment` lo cierra; vale para estático y seeded-random.
- **Fuente**: test_profile_storage.py:test_complete_replays_all_rows_and_loads_typed_result
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-050] Completar rechaza falsificación, dueño equivocado, cancelación y replay obsoleto
- **Regla**: run sin iniciar o de otro experimento/ordinal inválido (`True`) → `ValueError("owned")`; resultado con `paid` alterado → `"replay"`; resultado cancelado → `"cancelled"`; si el experimento se cancela durante el replay → `"changed during replay"` sin guardar resultado.
- **Fuente**: test_profile_storage.py:test_complete_rejects_forgery_wrong_owner_cancel_and_stale_replay
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-051] Posiciones variables (1 y 5) se preservan al cargar resultados
- **Regla**: resultados de perfiles de 1 y 5 posiciones se guardan y leen con `bets[0].results == tuple(range(positions))`.
- **Fuente**: test_profile_storage.py:test_profile_result_loading_preserves_variable_positions
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-052] Carrera de replay rechequea binding de request y dataset
- **Regla**: si el `code_version` se cambia durante la validación, `complete_profile_run` → `"changed during replay"` y no queda resultado.
- **Fuente**: test_profile_storage.py:test_replay_race_rechecks_request_and_dataset_binding
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-053] Completar: cuota y dataset corrupto fallan sin resultado
- **Regla**: cuota insuficiente → `QuotaExceeded` con run en RUNNING; dataset con bytes alterados → `"corrupt stored dataset"` sin resultado.
- **Fuente**: test_profile_storage.py:test_complete_quota_and_corrupt_dataset_fail_without_result
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-054] Cycling v2 privado: round-trip y fallos cerrados entre versiones
- **Regla**: `create_profile_cycling_experiment` guarda `request_schema_version 2` y `result_schema_version None`; no aparece en `search_experiments`/`page_experiments` por defecto (v1-only) ni pendiente; `request_schema_version 5` o `request_kind legacy` → `IntegrityError`; `complete_profile_run` con una sesión v1 → `"owned"`; `complete_profile_cycling_run` guarda `result_json == serialize_profile_cycling_result`, `result_schema_version 2`; el resultado completado aparece solo con `include_completed_cycling=True`; `result_schema_version 1` en la fila → `"schema version"`; `result_json {}` → `"result"`; request v1 en la columna → `ValueError`.
- **Fuente**: test_profile_storage.py:test_cycling_private_roundtrip_and_cross_version_fail_closed
- **Categoría**: contrato
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

### [B-STO-055] Cycling: replay, propiedad, digest y cuota atómica
- **Regla**: dataset inexistente → `"dataset not found"`; cuota exacta con `quota_bytes = baseline+delta+1` → `QuotaExceeded` y `admission_logical_bytes` sin cambios; completar sin iniciar/otro experimento/ordinal inválido → `"owned"`; resultado alterado → `"replay"`; cuota al completar → `QuotaExceeded` sin cambios; binding cambiado durante replay → `"changed during replay"`; dataset corrupto → `"corrupt stored dataset"`; ningún fallo deja resultado.
- **Fuente**: test_profile_storage.py:test_cycling_replay_ownership_digest_and_atomic_quota
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-056] Audaz v3: persistencia, replay y versiones
- **Regla**: `create_profile_audaz_experiment` guarda `request_schema_version 3`; `complete_profile_audaz_run` guarda `result_schema_version 3` y `result_json == serialize_profile_audaz_result`; aparece con `include_completed_cycling=True`; `request_schema_version 5` → `IntegrityError`.
- **Fuente**: test_profile_storage.py:test_audaz_v3_persistence_replay_and_version_checks
- **Categoría**: contrato
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

### [B-STO-057] Audaz rechaza capital inicial inasequible antes de crear filas
- **Regla**: con incremento 2 y capital 1 → `ValueError("initial capital")`, 0 filas en `experiments` y `runs`.
- **Fuente**: test_profile_storage.py:test_audaz_initial_affordability_rejects_before_creating_rows
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-058] Binding de archivo autentica fuente y filas completas
- **Regla**: `bind_archived_dataset(dataset, settings)` verifica hash de fuente y rankings, `canonical_draw_count`, `rank_row_ids`, `canonical_draw_index`, `prior_cutoff(i)` (etiqueta del sorteo anterior) y `select(sistema, fila, k)` devuelve los k primeros del ranking (incluyendo `system="freq_hist"` para topk).
- **Fuente**: test_profile_archive.py:test_binding_authenticates_source_and_exact_full_history_rows
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-059] Binding rechaza perfil incompatible aun con filas y fuente coincidentes
- **Regla**: un dataset cuyo perfil embebido no repite números (`allows_repeats False`) → `DataError`.
- **Fuente**: test_profile_archive.py:test_binding_rejects_incompatible_profile_even_when_rows_and_source_match
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-060] Binding rechaza la misma etiqueta con resultado distinto
- **Regla**: si un registro del dataset difiere en números del histórico verificado → `DataError`.
- **Fuente**: test_profile_archive.py:test_binding_rejects_same_label_with_different_result
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-061] Binding rechaza hash fuente no verificado y fila sin ranking
- **Regla**: `source_sha256` incorrecto → `DataError`; `select` en una fila sin ranking (`row 1`) → `DataError("ranking")`.
- **Fuente**: test_profile_archive.py:test_binding_rejects_unverified_source_hash_and_missing_ranking_row
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-062] Binding rechaza timestamps desalineados; no acepta ruta de activos forjada
- **Regla**: `timestamps` del ranking que no coinciden con las etiquetas del historial → `DataError`; `bind_archived_dataset` solo acepta 2 parámetros (dataset, settings): la ruta de assets no es argumento.
- **Fuente**: test_profile_archive.py:test_binding_rejects_timestamp_mismatch_and_forged_asset_path_argument
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-063] Binding rechaza rankings que no son permutación
- **Regla**: ranking con número repetido → `DataError("permutation")`.
- **Fuente**: test_profile_archive.py:test_binding_rejects_nonpermutation_rankings
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-064] Selección de paridad usa historia previa y no exige ranking
- **Regla**: `select("parity", 0|2, 50)` devuelve los 50 pares (voto causal con historia previa mixta); `select("cold", fila sin ranking)` → `DataError`.
- **Fuente**: test_profile_archive.py:test_parity_selection_uses_prior_history_and_skips_no_rank_requirement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-065] Promoción inválida o preview forjado nunca inserta
- **Regla**: `promote_dataset(..., preview=...)` → `TypeError` (no se acepta un preview externo); fuente inválida → `ValueError("not promotable")`; `datasets` sigue en 0.
- **Fuente**: test_datasets.py:test_invalid_source_and_forged_preview_never_insert
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-066] Canonical UTF-8, retención del crudo, identidad por contexto, duplicados
- **Regla**: `dataset_sha256 == sha256(canonical_json)`, `source_sha256 == sha256(raw)`; `dataset_artifact_bytes = len(canonical)+len(raw)+128+len(created_at)`; mismo contenido con otro raw → `created False`, `duplicate_source_differs True` (sin cobrar cuota ni exigir disco); mismo raw → `duplicate_source_differs False`; cambiar el contexto (`source_id`) crea un dataset distinto reteniendo el raw; `get_dataset("missing")` → None.
- **Fuente**: test_datasets.py:test_canonical_utf8_raw_retention_context_identity_and_duplicate
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-067] Cuota exacta incluye datasets y bloquea otras escrituras
- **Regla**: `admission_logical_bytes` = baseline + delta de datasets; `quota_status.dataset_artifact_bytes == delta`; `set_quota_preference(baseline+delta−1)` → `QuotaBelowUsage`; con cuota = uso, promover otro dataset → `QuotaExceeded` sin cambios.
- **Fuente**: test_datasets.py:test_quota_exact_delta_and_other_writes_include_datasets
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-068] Borde de cuota, insert fallido y rollback de datasets
- **Regla**: límite con `limit − min(LOGICAL_MARGIN_BYTES, max(1, limit//20)) == proyectado` → `QuotaExceeded` y 0 bytes; el primer límite superior admite; trigger que aborta el insert deja `dataset_artifact_bytes` sin cambios.
- **Fuente**: test_datasets.py:test_quota_boundary_failed_insert_and_rollback
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-069] Datasets inmutables; bytes/contexto corruptos se rechazan
- **Regla**: UPDATE → `IntegrityError("immutable")`, DELETE → `"immutable"`; con raw alterado, `source_sha256` alterado o `canonical_json` alterado, `get_dataset` → `ValueError("corrupt stored dataset")`.
- **Fuente**: test_datasets.py:test_immutability_and_corrupt_bytes_context_rejected
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-070] `page_datasets` corta antes del trabajo de integridad y ordena empates
- **Regla**: orden `created_at, dataset_sha256`; solo se verifica la página pedida (`checked_dataset` solo para filas seleccionadas); offset sobre el total → `(total, [])` sin verificar nada; página con fila corrupta → `"corrupt stored dataset"`; offset/limit inválidos (neg, 0, 101, bool) → `ValueError("out of range")`.
- **Fuente**: test_datasets.py:test_page_datasets_slices_before_integrity_work_and_orders_ties
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-071] `preflight_profile_dataset`: perfil embebido registrado, configs estáticas
- **Regla**: perfil no persistido → `ValueError("must be persisted")`; tras registrar devuelve el dataset para selectores estático y seeded-random; perfil con otro `maximum_stake` → `"differs"`; `start_draw` ausente → `"start draw"`; número estático fuera del universo (100) → `"static number"`; capital que no cubre la apuesta (11×10) → `"cannot afford"`.
- **Fuente**: test_datasets.py:test_preflight_requires_exact_registered_embedded_profile_and_static_configs
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-072] Promociones concurrentes cobran una sola vez
- **Regla**: 8 promociones simultáneas del mismo dataset crean exactamente 1 (`created`), un solo `dataset_sha256` y `dataset_artifact_bytes` de una sola copia.
- **Fuente**: test_datasets.py:test_concurrent_promotions_charge_once
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-073] Parseo de historial anidado cuenta filas reales y hashea bytes crudos
- **Regla**: `parse_history(raw, profile)` → `promotable`, `rows_seen == len(records)`, `source_sha256 == sha256(raw)`, `dataset_sha256` de 64 caracteres, números parseados como enteros.
- **Fuente**: test_history_import.py:test_nested_history_counts_actual_rows_and_hashes_raw_bytes
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-074] Historial no hereda el límite legacy de filas y fusiona duplicados exactos
- **Regla**: 10 002 filas idénticas → `promotable`, `rows_seen 10002`, 1 registro, `duplicates_merged 10001`.
- **Fuente**: test_history_import.py:test_history_accepts_more_than_legacy_row_limit_and_merges_exact_duplicates
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-075] Historial rechaza filas mal formadas y claves duplicadas con códigos
- **Regla**: JSON con clave duplicada → error `json`; números repetidos en perfil sin repeticiones → `repeats`; hora `25:00` → `time`; `promotable False` y `dataset_sha256 None`.
- **Fuente**: test_history_import.py:test_history_rejects_malformed_nested_rows_and_duplicate_keys
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-076] Importador acepta 1/3/5 posiciones, JSON y CSV, con cero a la izquierda
- **Regla**: valores `"00"` se parsean a enteros; para `json` y `csv`: `promotable`, `error_count 0`, `records[0].numbers == range(positions)`, `source_sha256 == sha256(raw)`, `dataset_sha256` de 64 hex; `records` es tupla inmutable (frozen).
- **Fuente**: test_import_records.py:test_valid_position_counts_and_zero_padded_values
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-077] Forma, cabecera y codificación malformadas se rechazan por completo
- **Regla**: `{}`, `[[1,2]]`, objeto sin campos → `shape`; clave duplicada o `NaN` → `json`; CSV con cabecera duplicada → `header`; fila CSV con columnas de menos o de más → `shape`; bytes no UTF-8 → `encoding`; en todos `promotable False`, `records ()`, `dataset_sha256 None`.
- **Fuente**: test_import_records.py:test_malformed_shape_header_and_encoding
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-078] Campos de fila inválidos: un solo código, sin promoción parcial
- **Regla**: `date` (`2025-02-29`, `2025-2-09`, `2025-13-01`), `time` (`24:00`, `5:10`, `05:60`), `number` (bool, float, −1, 100, `"2.0"`, 5000 dígitos) producen exactamente ese código, `rows_seen 2`, `records ()` y no promovible.
- **Fuente**: test_import_records.py:test_invalid_row_fields
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-079] Campos faltantes y repeticiones: todo o nada
- **Regla**: en perfil sin repeticiones, filas con campo faltante (`missing_field`) o números repetidos (`repeats`) bloquean todo el lote (`records ()`, sin hash).
- **Fuente**: test_import_records.py:test_missing_fields_and_repeats_rejected_without_partial_promotion
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-080] Validación de mapeo, reloj, origen y formato
- **Regla**: `mapping_duplicate`, `positions` (mapeo con 1 posición en perfil de 3), `clock` (naive con zona), `clock_zone` (zona desconocida), `source` (id vacío), `format` (`xml`); un reloj IANA UTC es promovible o se declara `clock_zone` si la instalación no tiene tzdata (nunca se acepta una zona no verificada).
- **Fuente**: test_import_records.py:test_mapping_and_source_clock_validation
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-081] Conflictos bloquean; duplicados idénticos se fusionan y se ordenan
- **Regla**: filas con la misma fecha/hora y números distintos → `conflict` y no promovible; duplicados idénticos se fusionan (`duplicates_merged`) y los registros se ordenan cronológicamente.
- **Fuente**: test_import_records.py:test_conflicts_block_promotion_identical_duplicates_merge_and_sort
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-082] Hash normalizado: independiente del orden, ligado a procedencia, mapeo, perfil y reloj
- **Regla**: `dataset_sha256` igual para filas en cualquier orden y con duplicados exactos; `source_sha256` sí difiere; cambia con otro `source`, otra `revision` del perfil, otro orden de mapeo de columnas o reloj IANA.
- **Fuente**: test_import_records.py:test_normalized_hash_order_provenance_mapping_profile_and_clock
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-083] Límite de entrada antes de decodificar y tope de columnas
- **Regla**: entrada > `MAX_INPUT_BYTES` → solo `input_limit` (con `source_sha256` del crudo); mapeo sobredimensionado (31 posiciones) se rechaza antes que un payload UTF-8 inválido (`column_limit` + `positions`); cabecera CSV con `MAX_COLUMNS` excedidas → `column_limit`.
- **Fuente**: test_import_records.py:test_input_limit_precedes_decode_and_import_column_ceiling
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-084] Límite de filas y conteo de errores acotado y veraz
- **Regla**: errores reportados ≤ `MAX_ERRORS` con `error_count` real y `errors_truncated True`, numerados por fila; más de `MAX_ROWS` filas (CSV y JSON) → `row_limit` no promovible con `rows_seen = MAX_ROWS+1` y `records ()`.
- **Fuente**: test_import_records.py:test_row_limit_and_bounded_error_count_truthful
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-085] Vacío y celda numérica CSV sobredimensionada
- **Regla**: lista vacía → `empty`; celda CSV de 5000 dígitos → solo `number`.
- **Fuente**: test_import_records.py:test_empty_and_oversized_csv_numeric_cell
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-STO-086] Mapeo malformado y anchura de fila JSON son errores de validación
- **Regla**: posición de mapeo no string → `mapping`; fila JSON con `MAX_COLUMNS` extras → `column_limit`; valor anidado → `shape`.
- **Fuente**: test_import_records.py:test_malformed_mapping_and_json_row_width_are_validation_errors
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-087] JSON profundamente anidado válido es preview inválido acotado
- **Regla**: `[`×100 000 + `0` + `]`×100 000 → un solo error `json`, `error_count 1`, `errors_truncated False`, no promovible, con `source_sha256` calculado.
- **Fuente**: test_import_records.py:test_deeply_nested_valid_json_is_bounded_invalid_preview
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-088] Surrogates solitarios en metadatos/mapeo/reloj/perfil son preview inválido
- **Regla**: `\ud800` en `source_id`, `revision` o `provenance` → solo `source`; en mapeo → `mapping`; zona de reloj → `clock_zone`; perfil forjado con `profile_id` inválido (`model_construct`) → `profile`; nunca crashea ni envenena el hash; siempre con `source_sha256` correcto, sin registros y no promovible.
- **Fuente**: test_import_records.py:test_lone_surrogate_source_metadata_is_invalid_preview; test_lone_surrogate_mapping_and_clock_are_invalid_previews; test_bypassed_profile_text_validation_cannot_poison_hash
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-089] El parser puro no abre archivos de la aplicación
- **Regla**: con `builtins.open` bloqueado, `parse_records` sigue funcionando para reloj naive.
- **Fuente**: test_import_records.py:test_naive_preview_does_not_open_application_files
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-STO-090] Cuota por defecto 5 GiB; valores inválidos rechazados
- **Regla**: `DEFAULT_QUOTA_BYTES == 5·1024³`; `quota_bytes` 0, −1, bool, float, str o `2**63` → `ValueError("quota")`; `LABORATORIO_QUOTA_BYTES=2147483648` se lee; valor inválido → `ValueError("LABORATORIO_QUOTA_BYTES")`.
- **Fuente**: test_quota.py:test_default_and_invalid_configured_quota
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-091] Preferencia persistente y precedencia efectiva
- **Regla**: efectiva por defecto `(default, writable True, persisted None)`; `set_quota_preference` persiste y se lee tras reabrir (`source persisted`, `limit_bytes` = preferencia); con `quota_explicit=True` la fuente es `environment`, `writable False` y se conserva el persistido; `quota_explicit=False` respeta la preferencia; llamadores históricos que pasan `quota_bytes` sin procedencia conservan su override (`source override`); escribir con entorno explícito → `QuotaReadOnly` sin cambios.
- **Fuente**: test_quota.py:test_preference_persists_and_effective_precedence
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-092] Preferencia exige entero SQLite estricto
- **Regla**: `set_quota_preference` y `effective_quota` con 0, −1, bool, 1.5, `"100"` o `2**63` → `ValueError("quota")` sin persistir.
- **Fuente**: test_quota.py:test_preference_requires_strict_sqlite_int
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-STO-093] Preferencia bajo el uso hace rollback; igual al uso se permite
- **Regla**: `set_quota_preference(used)` permitido (igual), `used−1` → `QuotaBelowUsage` y el valor previo se conserva; `2**63−1` es válido; `admission_logical_bytes > logical_experiment_bytes`.
- **Fuente**: test_quota.py:test_preference_below_usage_rolls_back_and_equal_allowed
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-094] La frontera de escritura relee la preferencia tras un preflight obsoleto
- **Regla**: con preferencia reducida después del preflight, `create_experiment` y `complete_run` con `quota_explicit=False` → `QuotaExceeded` (run sigue RUNNING); el override explícito legado (sin `quota_explicit`) conserva su semántica previa y sí escribe.
- **Fuente**: test_quota.py:test_write_boundary_rereads_preference_after_stale_preflight
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-095] Una preferencia concurrente no puede socavar una escritura en vuelo
- **Regla**: mientras una escritura está en curso, `set_quota_preference(1)` espera y falla con `QuotaBelowUsage`; la escritura termina y la preferencia queda sin fijar.
- **Fuente**: test_quota.py:test_concurrent_preference_cannot_undercut_in_flight_write
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-STO-096] El uso lógico excluye entradas originales y overhead físico
- **Regla**: BD vacía: `logical_used 0`, `profile_artifact_bytes > 0` (perfil legacy sembrado), `admission_logical_bytes == profile_artifact_bytes`, `dataset_artifact_bytes 0`; archivos `source.json`/`rank.npz` de 4096 bytes no cuentan; tras crear un experimento `logical_used > 0` y `< 4096`, `admission = logical + profile`; `sqlite_bytes >= tamaño del archivo`, `free_disk_bytes`, `limit_bytes` reportados.
- **Fuente**: test_quota.py:test_logical_usage_excludes_original_inputs_and_physical_overhead
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-STO-097] Sidecars WAL/temp se reportan por separado
- **Regla**: `measure` suma `-wal`, `-shm`, `-journal` en `sqlite_bytes` y expone `wal_bytes`, `temp_bytes`, `disk_margin_bytes > 0`, `logical_margin_bytes > 0`.
- **Fuente**: test_quota.py:test_sqlite_wal_and_temporary_sidecars_reported_separately
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-STO-098] Umbral de cuota y disco libre son independientes
- **Regla**: uso < umbral (`limit − margen − perfil`) pasa; uso == umbral o +1 → `QuotaExceeded("quota")`; disco libre == margen → `QuotaExceeded("disk")`; margen+1 pasa.
- **Fuente**: test_quota.py:test_below_at_and_above_threshold_and_free_disk_independent
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-099] Bytes de discriminadores se cuentan y proyectan
- **Regla**: `request_kind` y `result_kind` ("legacy") son columnas de texto contadas; cambiarlas a `profile` suma exactamente 2 bytes; `admission_logical_bytes` ≥ la suma.
- **Fuente**: test_quota.py:test_discriminator_bytes_are_counted_and_projected
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-STO-100] Proyección del snapshot cuenta una copia, atómicamente, en igualdad
- **Regla**: crear un experimento cuesta `snapshot_cost > logical`; en límite `baseline+cost+margen` → `QuotaExceeded`; `limit+1` → admitido; borrar el experimento devuelve el baseline.
- **Fuente**: test_quota.py:test_snapshot_projection_counts_one_copy_atomically_at_equality
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-101] Versiones de perfil: cuota, idempotencia y conflicto
- **Regla**: registrar un perfil nuevo cuesta `len(json utf-8)`; en igualdad → `QuotaExceeded` (no se crea); con `limit+1` se crea; el reintento idéntico es no-op aun con cuota 1 y disco 0; contenido distinto bajo la misma versión → `ValueError("different content")`; `set_quota_preference(baseline+cost−1)` → `QuotaBelowUsage`.
- **Fuente**: test_quota.py:test_profile_version_quota_idempotence_and_conflict
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-102] Datos antiguos sobre cuota siguen legibles; borrar recupera holgura
- **Regla**: con una preferencia histórica = uso previo (menor que el agregado actual), el experimento sigue legible, `quota_status` reporta el agregado y crear otro → `QuotaExceeded`; cancelar+borrar deja `logical 0` y `admission == profile_artifact_bytes`, y ya se puede fijar la preferencia.
- **Fuente**: test_quota.py:test_old_over_quota_data_readable_and_deletion_recovers_headroom
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-STO-103] La escritura de resultados verifica bytes UTF-8 exactos antes del commit
- **Regla**: con cuota `used+100`, `complete_run` → `QuotaExceeded`, el experimento queda RUNNING y el run sin resultado.
- **Fuente**: test_quota.py:test_result_write_checks_exact_utf8_bytes_before_commit
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

<!-- B-STO:fin -->

## 4. B-QUE — Cola y trabajos

### [B-QUE-001] Fallo local de estrategia no afecta a vecinas
- **Regla**: `StrategyLocalError` en la estrategia 2 deja runs `[COMPLETED, FAILED, COMPLETED]`, experimento `FAILED`, resultados de vecinas intactos; cada cálculo corre en un proceso hijo distinto al padre; `last_failure.persisted True`; la cola sigue viva.
- **Fuente**: test_queue.py:test_spawned_local_failure_preserves_neighbours_and_continues
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-002] `ValueError` desconocido del worker falla el experimento actual, no el siguiente
- **Regla**: error inesperado en la estrategia 2 → runs `[COMPLETED, FAILED, NOT_RUN]` para ese experimento; un job posterior se completa normalmente; no se lanza cálculo de la estrategia 3.
- **Fuente**: test_queue.py:test_unknown_worker_value_error_fails_current_experiment_not_later_job
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-003] Fallo compartido/infraestructura detiene la cola
- **Regla**: `DataError` (integridad de sorteos) u `OSError` (storage) en un worker → el run queda FAILED, restantes NOT_RUN, la cola se detiene (`is_stopped`), `last_failure.persisted True`, y el job siguiente permanece PENDING (no se pierde ni se ejecuta).
- **Fuente**: test_queue.py:test_shared_worker_failure_stops_queue_and_preserves_unstarted_job
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-004] Mensaje de spawn mal formado/silencioso es fatal para la cola
- **Regla**: mensaje `("failed", ("strategy_local", 123))` o hijo que cierra el pipe sin resultado → run FAILED, cola detenida, siguiente job PENDING.
- **Fuente**: test_queue.py:test_malformed_spawn_message_is_queue_fatal
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-005] EOF por salida limpia es fatal aunque el pipe parezca legible
- **Regla**: si `recv()` da EOF tras `poll()==True`, el run falla, la cola se detiene y `last_error` contiene "without a final result"; el siguiente job queda PENDING.
- **Fuente**: test_queue.py:test_clean_exit_eof_is_fatal_even_when_pipe_reports_readable
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-006] La frontera de producción solo localiza el stake inicial
- **Regla**: en `calculate_run`, capital insuficiente para la apuesta prescrita → `StrategyLocalError("initial capital")`; `DataError` al abrir datos se propaga como `DataError`; `ValueError` de `run_session` → `SharedCalculationError`.
- **Fuente**: test_queue.py:test_production_boundary_only_localizes_initial_stake
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-007] Admisión por cuota en `enqueue` y en `start_held`
- **Regla**: con cuota 1 byte, `enqueue` y `start_held` lanzan excepción "quota", no encolan (`pending_ids()==()`) ni lanzan proceso; el HELD permanece HELD.
- **Fuente**: test_queue.py:test_admission_at_enqueue_and_held_start
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-008] El backlog revalida capacidad antes de una corrida cara
- **Regla**: tras completar el primer experimento, si el disco queda sin espacio (free=0), el siguiente pasa a HELD, `last_failure.experiment_id` es ese experimento y no se lanza proceso para él.
- **Fuente**: test_queue.py:test_backlog_rechecks_capacity_before_expensive_run
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-009] Fallo de escritura de resultado detiene la cola, preserva previo y reapea hijo
- **Regla**: si `complete_run` falla (OSError) en el 2º run, el experimento queda FAILED con `[COMPLETED, FAILED]`, el resultado previo se conserva, el siguiente PENDING, `last_failure.persisted True`, `_process is None`; al reiniciar, el pendiente pasa a HELD y el fallido sigue FAILED.
- **Fuente**: test_queue.py:test_write_failure_stops_queue_preserves_prior_result_and_reaps_child
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-010] Estado no persistible se reporta solo en memoria y se recupera al reiniciar
- **Regla**: si `complete_run` y `finish_incomplete` fallan, `last_failure.persisted False` con `persistence_error` ("store unavailable"), el hijo ya no vive y el experimento sigue RUNNING en BD; al reiniciar queda INTERRUPTED sin resultado.
- **Fuente**: test_queue.py:test_failed_status_write_is_reported_only_in_memory_then_recovered
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-011] Experimentos en serie en proceso hijo
- **Regla**: solo un experimento activo; el segundo permanece PENDING mientras el primero corre; el cálculo ocurre en un pid distinto al del proceso padre.
- **Fuente**: test_queue.py:test_serial_experiments_and_child_process
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-012] Cancelar el activo preserva completados y descarta el parcial
- **Regla**: `cancel` de un experimento corriendo deja runs `[COMPLETED, CANCELLED, NOT_RUN]`, experimento CANCELLED, el resultado completado se conserva y el parcial/no ejecutado queda sin resultado.
- **Fuente**: test_queue.py:test_cancel_active_preserves_completed_and_discards_partial
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-013] Cancelar no espera a una sesión atascada y reapea al hijo
- **Regla**: aunque el worker ignore la señal de cancelación, `cancel` lleva el experimento a CANCELLED en <4 s, termina el proceso hijo y no guarda resultado.
- **Fuente**: test_queue.py:test_cancel_does_not_wait_for_a_stuck_session_and_reaps_child
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-014] Shutdown interrumpe el activo; reinicio retiene pendientes (no auto-reanuda)
- **Regla**: `shutdown` deja el activo INTERRUPTED (`[COMPLETED, INTERRUPTED, NOT_RUN]`) y el pendiente PENDING; al reiniciar el pendiente pasa a HELD, `pending_ids()==()`, y solo `start_held` lo ejecuta.
- **Fuente**: test_queue.py:test_shutdown_and_restart_holds_pending_and_does_not_resume
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-015] Muerte abrupta del hijo falla el job y el siguiente avanza
- **Regla**: `os._exit(17)` → experimento FAILED con `[FAILED, NOT_RUN]` sin resultados, `last_error` contiene "17", y el job siguiente se completa.
- **Fuente**: test_queue.py:test_abrupt_child_death_fails_and_next_job_proceeds
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-016] Fallo de inicialización del hijo es explícito y la cola se recupera
- **Regla**: error al cargar datos en el hijo → run FAILED y el siguiente experimento completa.
- **Fuente**: test_queue.py:test_child_initialization_failure_is_explicit_and_queue_recovers
- **Categoría**: concurrencia
- **Riesgo si se pierde**: medio

### [B-QUE-017] Resultado inválido del hijo es fatal sin perder el previo
- **Regla**: resultado `None`, de tipo equivocado o `SessionResult` sin apuestas → mensaje "malformed worker completed result", run FAILED, resto NOT_RUN, resultado previo conservado, cola detenida, siguiente job PENDING, `_process None`.
- **Fuente**: test_queue.py:test_invalid_child_result_is_queue_fatal_without_losing_prior_result
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-018] `start_held` rechaza un experimento ya activo sin cambiar estado
- **Regla**: tras `start_held`, mientras la admisión está en curso (`active_id == held`, estado aún HELD), un segundo `start_held` lanza `ValueError("already enqueued")` y `pending_ids()==()`.
- **Fuente**: test_queue.py:test_start_held_rejects_active_before_status_changes
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-019] Arranques HELD concurrentes encolan una sola vez
- **Regla**: dos hilos llamando `start_held` simultáneamente → un `queued` y un `rejected` (`ValueError`); el id aparece como máximo una vez entre pendientes+activo.
- **Fuente**: test_queue.py:test_concurrent_held_starts_enqueue_once
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-020] Cancelar encolado y HELD sin lanzar proceso
- **Regla**: `cancel` de un pendiente o de un HELD → CANCELLED con run `NOT_RUN`, sin lanzar cálculo.
- **Fuente**: test_queue.py:test_cancel_queued_and_held_without_spawning
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-021] Cuota persistida alcanza a la cola existente
- **Regla**: tras `set_quota_preference(admission_logical_bytes)`, `submit`, `enqueue` y `start_held` fallan con "quota"; `submit` no deja experimento nuevo; `pending_ids()==()`.
- **Fuente**: test_queue.py:test_persisted_quota_reaches_existing_queue_submit_enqueue_and_held_start
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-022] Límite explícito de entorno gana a la preferencia persistida
- **Regla**: con `quota_explicit=True` el job se completa aunque el límite persistido sea muy bajo, y la preferencia persistida no se modifica.
- **Fuente**: test_queue.py:test_explicit_environment_default_wins_over_persisted_limit_at_runtime
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-023] Reducir la cuota durante un cálculo activo bloquea el resultado sin escritura parcial
- **Regla**: bajar la cuota mientras el run está RUNNING hace fallar el experimento (`FAILED`, `result None`) y `last_failure.experiment_id` apunta a él.
- **Fuente**: test_queue.py:test_persisted_update_during_active_calculation_blocks_result_without_partial_write
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-024] La siguiente configuración revalida el límite persistido
- **Regla**: tras completar la 1ª estrategia, si la cuota baja, la 2ª no se calcula (`result None`), `last_failure.error` menciona "quota" y no se lanza un segundo proceso.
- **Fuente**: test_queue.py:test_next_configuration_rechecks_persisted_limit_after_completed_result
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-025] Reconciliación al arrancar: RUNNING → INTERRUPTED, PENDING → HELD
- **Regla**: al `start()`, un experimento con run RUNNING abandonado pasa a INTERRUPTED (`[INTERRUPTED, NOT_RUN]`) y uno PENDING a HELD.
- **Fuente**: test_queue.py:test_startup_reconciles_abandoned_running_and_pending
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-026] Motor real en proceso spawn (real_data)
- **Regla**: con datos reales, un experimento creado antes de arrancar queda HELD hasta `start_held`; luego se completa con `bets_count 1`; un snapshot con capital 1 y cobertura 50 falla localmente solo esa estrategia (`[FAILED, COMPLETED]`) tras el spawn.
- **Fuente**: test_queue.py:test_default_worker_runs_real_engine_in_spawned_process; test_real_engine_unaffordable_snapshot_is_local_after_spawn
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-QUE-027] `submit_profile` ejecuta en proceso spawn: estático y aleatorio (3 posiciones)
- **Regla**: tras `queue.start()`, `submit_profile` de requests estático y seeded-random completan con resultado igual a `replay(...)`, con 3 resultados por apuesta y `last_failure None`.
- **Fuente**: test_profile_queue.py:test_submit_profile_spawn_static_and_random_three_positions
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-028] `submit_profile` rechaza hash/dataset incoherentes sin dejar huérfanos
- **Regla**: `profile_sha256` distinto → `ValueError("registered")`, dataset inexistente → `"dataset not found"`, `list_experiments()==[]`, `pending_ids()==()`.
- **Fuente**: test_profile_queue.py:test_submit_rejects_metadata_hash_mismatch_without_orphan
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-029] Perfil completado inválido es fatal para la cola y preserva el previo
- **Regla**: worker que envía resultado mal formado/`kind legacy` ("malformed"), forjado con balance +1 ("differs"), muere con código 17 ("worker exited with code 17") o cierra sin resultado ("without a final result") → run FAILED, `last_failure.persisted`, cola detenida, el experimento anterior conserva su resultado, el siguiente queda PENDING y `_process None`.
- **Fuente**: test_profile_queue.py:test_bad_completed_profile_is_queue_fatal_and_preserves_prior_result
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-030] Cancelar un worker de perfil sin respuesta lo descarta; shutdown interrumpe
- **Regla**: `cancel` de un perfil activo que ignora la cancelación → CANCELLED en <5 s, hijo muerto, sin resultado; `shutdown` con un perfil activo → INTERRUPTED sin resultado.
- **Fuente**: test_profile_queue.py:test_cancel_unresponsive_profile_discard_and_shutdown_interrupt
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-031] Preparación privada de cycling no puede encolarse/iniciarse/recuperarse por rutas v1
- **Regla**: al arrancar, un experimento cycling queda HELD (`page_held_ids`); `cancel` lo cancela; `queue.enqueue` → `ValueError("new pending")` si está cancelado y `"not executable"` si se reintroduce `pending` a mano; `pending_ids()==()`, `active_id None`, run `NOT_RUN`.
- **Fuente**: test_profile_queue.py:test_cycling_preparation_cannot_enqueue_or_start_or_recover
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-032] Cycling privado: spawn autentica dataset completo y preserva v1
- **Regla**: `_enqueue_profile_cycling` completa con resultado igual a `cycling_result(...)`, `result_schema_version 2` y `elapsed_draws > 0`; tras reiniciar, un cycling creado antes queda HELD (nunca se agenda solo), `enqueue` → "new pending" y solo `start_held` lo ejecuta.
- **Fuente**: test_profile_queue.py:test_private_cycling_spawn_authenticates_full_dataset_and_preserves_v1
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-033] IPC malo de cycling detiene la cola preservando previo y posterior
- **Regla**: mensaje mal formado ("malformed"), muerte con código 17 o resultado forjado ("differs") → run FAILED, `last_failure.persisted`, cola detenida, el previo conserva resultado y el posterior PENDING.
- **Fuente**: test_profile_queue.py:test_private_cycling_bad_ipc_stops_queue_preserving_prior_and_later
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-034] `_enqueue_profile_cycling` rechaza tipo/versión/estado equivocados y duplicados
- **Regla**: id inexistente, request v1 de perfil o legacy → `ValueError("profile cycling")`; `enqueue` v1 sobre cycling → `"not executable"`; segundo enqueue → `"already enqueued"`; ya completado → `"profile cycling"`.
- **Fuente**: test_profile_queue.py:test_private_cycling_enqueue_refuses_wrong_kind_version_status_and_duplicate
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-035] Shutdown interrumpe un cycling activo sin resultado
- **Regla**: `shutdown` con cycling activo mata al hijo y deja experimento y run `INTERRUPTED` con `result None`.
- **Fuente**: test_profile_queue.py:test_private_cycling_shutdown_interrupts_spawn_without_result
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-036] Error de integridad del artefacto detiene antes de lanzar el hijo
- **Regla**: `get_dataset` que lanza `ValueError("corrupt dataset bytes")` → `last_failure.persisted False` con `persistence_error` (no puede fallar antes de `start_run`), cola detenida, experimento PENDING sin resultado; tras reiniciar queda HELD.
- **Fuente**: test_profile_queue.py:test_private_cycling_artifact_integrity_error_stops_before_spawn
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-037] Reanudación manual de perfil HELD
- **Regla**: un perfil creado antes del arranque queda HELD; `start_held` lo completa.
- **Fuente**: test_profile_queue.py:test_manual_resume_held_profile
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-QUE-038] Audaz v3: HELD, cancelación, reanudación manual y replay en spawn
- **Regla**: experimentos Audaz creados antes del arranque quedan HELD; `cancel` → CANCELLED; `start_held` completa con `request_schema_version 3`, `result_schema_version 3`, `final_balance >= 0` y `last_failure None`.
- **Fuente**: test_profile_queue.py:test_audaz_schema3_held_cancel_manual_resume_and_spawned_replay
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-039] Hijo de lote autentica el archivo congelado por un lote mixto
- **Regla**: con `source_identity.archive_bound` y rank_row_ids/hash de archivo congelados, `profile_batch_process_entry` llama `bind_archived_dataset(dataset, settings)` con el dataset del lote y envía un frame `status "completed"` (el proceso hijo recibe un request de una estrategia pero hereda la identidad del lote completo).
- **Fuente**: test_profile_batch_queue.py:test_manual_child_authenticates_archive_frozen_by_mixed_batch
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-QUE-040] `ValueError` de fuente con mensaje desconocido es fallo compartido
- **Regla**: `ValueError("signature digest disagrees")` al enlazar el archivo → frame `{status failed, kind shared}` (no se asume que sea local por el mensaje).
- **Fuente**: test_profile_batch_queue.py:test_profile_batch_source_value_error_with_unfamiliar_message_is_shared
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-041] `ValueError` financiero del lote es fallo local tipado
- **Regla**: estrategia no asequible (stake 2, capital 1) → frame `{status failed, kind strategy_local}`.
- **Fuente**: test_profile_batch_queue.py:test_profile_batch_financial_value_error_is_typed_local_failure
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-042] Lote tipado ejecuta 3 ordinales en serie y persiste cada uno
- **Regla**: `submit_profile_batch` con 3 estrategias → 3 runs (`ordinal [0,1,2]`) COMPLETED, cada resultado `ProfileBatchResultV5` con un solo `result.ordinal 0` y nombres `[Static low risk, Second, Third]`, `last_failure None`.
- **Fuente**: test_profile_batch_queue.py:test_typed_submission_runs_three_ordinals_serially_and_persists_each
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-043] Idempotencia: nunca encola dos veces un lote existente
- **Regla**: reenviar la misma submission devuelve el mismo id (1 experimento, ≤1 vez en pendientes), también completado; mismo `client_request_id` con condiciones cambiadas → `ValueError("client_request_id")`.
- **Fuente**: test_profile_batch_queue.py:test_submission_idempotency_never_enqueues_existing_batch_twice
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-044] Fallo local de estrategia continua con los siguientes ordinales
- **Regla**: el ordinal 0 FAILED (`strategy_local`) y los ordinales 1 y 2 COMPLETED con resultado; experimento FAILED.
- **Fuente**: test_profile_batch_queue.py:test_local_strategy_failure_continues_later_ordinals
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-045] Resultado corrupto del worker detiene el lote conservando el ordinal previo
- **Regla**: frame `not-json` en el ordinal 1 → runs `[COMPLETED, FAILED, NOT_RUN]`, el primero conserva su resultado y `last_failure.error` contiene "malformed or oversized".
- **Fuente**: test_profile_batch_queue.py:test_corrupt_worker_result_stops_batch_but_keeps_prior_ordinal
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-046] Frame sobredimensionado (>16 MiB) es fallo compartido
- **Regla**: un frame de 16 MiB+1 → runs `[FAILED, NOT_RUN, NOT_RUN]`, cola detenida, `last_failure.error` con "oversized" y `_process None`.
- **Fuente**: test_profile_batch_queue.py:test_oversized_worker_frame_fails_shared_and_does_not_run_later_ordinals
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-047] Cancelar durante un hijo conserva el ordinal completado y cancela el resto
- **Regla**: `cancel` con el ordinal 1 en curso → runs `[COMPLETED, CANCELLED, NOT_RUN]`, experimento CANCELLED, primer resultado conservado y `_process None`.
- **Fuente**: test_profile_batch_queue.py:test_cancel_during_child_keeps_completed_ordinal_and_cancels_remainder
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-048] Timeout usa la política congelada en la admisión, no la actual
- **Regla**: con `run_timeout_seconds=1` al admitir y luego cambiado a 3600, el ordinal 0 que se cuelga falla con "frozen wall limit" (`last_error`), los siguientes completan y `batch_admission.policy.run_timeout_seconds == 1`.
- **Fuente**: test_profile_batch_queue.py:test_timeout_uses_frozen_admission_policy_not_current_policy
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

### [B-QUE-049] Recepción de frame bloqueada observa cancelación y deadline congelado
- **Regla**: con `recv_bytes` bloqueado: `cancel` interrumpe `_calculate` en <1.2 s devolviendo None; el deadline (1 s) lo interrumpe en <1.5 s con `StrategyLocalFailure` ("frozen wall limit"); en ambos se termina el hijo, se cierran writer y reader y no queda hilo `laboratorio-profile-batch-reader` vivo.
- **Fuente**: test_profile_batch_queue.py:test_stalled_frame_receive_observes_cancel_and_frozen_deadline
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto

### [B-QUE-050] Fallo de enqueue compensa el lote y permite reintentar la misma identidad
- **Regla**: `_enqueue_profile_batch` que lanza `RuntimeError("enqueue failed")` → el lote admitido se compensa (`list_experiments()==[]`, `pending_ids()==()`); reintentar la misma submission funciona y completa.
- **Fuente**: test_profile_batch_queue.py:test_enqueue_failure_compensates_batch_and_allows_same_identity_retry
- **Categoría**: concurrencia
- **Riesgo si se pierde**: alto
- **Nota**: test fallido previo conocido (ver sección final).

<!-- B-QUE:fin -->

## 5. B-SET — App / settings

### [B-SET-001] Cuota explícita por entorno es solo lectura (aun igual al default)
- **Regla**: `LABORATORIO_QUOTA_BYTES=DEFAULT_QUOTA_BYTES` hace `is_quota_explicit True` y se preserva tras `replace(settings, data_dir=...)`.
- **Fuente**: test_settings.py:test_explicit_default_environment_quota_is_still_read_only
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-002] Settings manuales: `quota_explicit` heredado/optable
- **Regla**: `Settings(...)` manual → `is_quota_explicit False`; `replace(quota_bytes=123)` → True (override legado); `replace(quota_explicit=False, quota_bytes=123)` → False; `quota_explicit` no booleano (`1`) → `ValueError("quota_explicit")`.
- **Fuente**: test_settings.py:test_manual_settings_preserve_legacy_override_and_can_opt_into_default
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-003] Defaults producen el juego Quiniela 80
- **Regla**: sin variables `LABORATORIO_GAME_*`: `game.name "Quiniela 80"`, `contracts.GAME` = 100 números, 5 posiciones, premios `(80,8,4,2,1)`, repeticiones permitidas, `minimum_stake 1`.
- **Fuente**: test_settings.py:test_defaults_produce_the_quiniela_80_game
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-004] El entorno configura un juego de tres posiciones
- **Regla**: `LABORATORIO_GAME_NAME/NUMBERS/POSITIONS/PRIZES ("60, 10,5" tolera espacios)/REPEATS/MINIMUM_STAKE` configuran `contracts.GAME` al construir `Settings.from_environment()`.
- **Fuente**: test_settings.py:test_environment_configures_a_three_position_game
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-005] `LABORATORIO_GAME_REPEATS` acepta grafías de flag
- **Regla**: `"1"` y `"TRUE"` (case-insensitive) → True; `"0"` → False.
- **Fuente**: test_settings.py:test_repeats_accepts_flag_spellings
- **Categoría**: validación
- **Riesgo si se pierde**: medio

### [B-SET-006] Entorno de juego inválido se rechaza nombrando la variable
- **Regla**: `NUMBERS=abc`, `POSITIONS=1.5`, `PRIZES=60,x`, `REPEATS=maybe` → `ValueError` que menciona la variable; `MINIMUM_STAKE=0` → error `minimum_stake`; `PRIZES=60,10` con 5 posiciones por defecto → error "one prize" (un premio por posición).
- **Fuente**: test_settings.py:test_bad_game_environment_is_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-007] `replace` conserva el juego configurado
- **Regla**: `Settings(..., game_positions=3, game_prizes=(60,10,5))` y `replace(port=9000)` mantiene `game.prizes`.
- **Fuente**: test_settings.py:test_replace_keeps_the_configured_game
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-SET-008] Aislamiento: construir `Settings` aplica el juego global y se restaura
- **Regla**: construir Settings muta `contracts.GAME`; los tests restauran el default (fixture `clean_game`) — la reescritura debe conservar ese aislamiento o evitar estado global.
- **Fuente**: test_settings.py:clean_game fixture
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-SET-009] Fixtures globales: `data_dir` aislado y skip de `real_data`
- **Regla**: `data_dir` apunta a un directorio temporal vía `LABORATORIO_DATA_DIR` (nunca la BD real); los tests `real_data` se omiten si `LABORATORIO_SKIP_REAL_DATA=1` o faltan history/rankings congelados.
- **Fuente**: conftest.py:data_dir, pytest_collection_modifyitems
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-SET-010] Cuota por defecto y variable `LABORATORIO_QUOTA_BYTES`
- **Regla**: `Settings.quota_bytes == DEFAULT_QUOTA_BYTES (5 GiB)`; valores 0, −1, bool, float, str, `2**63` → `ValueError("quota")`; entorno válido (`2147483648`) se lee y `invalid` → `ValueError("LABORATORIO_QUOTA_BYTES")` (ver B-STO-090).
- **Fuente**: test_quota.py:test_default_and_invalid_configured_quota
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-011] Producción sirve SPA y aísla `/api` y `/assets`
- **Regla**: con `serve_frontend=True`, las rutas `/`, `/experimentos`, `/experimentos/nuevo`, `/experimentos/{id}`, `/experimentos/{id}/comparacion`, `/configuraciones`, `/ajustes` devuelven el `index.html` (`text/html`); `/assets/main.js` → `text/javascript` (GET y HEAD 200); asset ausente o `/unknown.js` → 404; `/api/v1/does-not-exist` → 404 JSON; `/api/v1/queue` y `/catalog` siguen → 200.
- **Fuente**: test_app.py:test_production_static_spa_and_api_isolation
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-012] Navegación directa a rutas SPA solo para las rutas exactas
- **Regla**: `/experimentos/nuevo/perfil`, `/experimentos/nuevo/sesion` (con o sin `?draft=`) y `/datos` devuelven el `index.html` (GET/HEAD); variantes (`/perfiles`, `/perfil/child`, `/sesiones`, `/sesion/child`, `/sesion-extra`, `/experimentos/other/sesion`, `/datos/child`, `/datos-extra`, assets y API inexistentes) → 404.
- **Fuente**: test_app.py:test_profile_creation_direct_navigation_serves_only_the_spa_route; test_batch_session_direct_navigation_serves_only_the_spa_route; test_datos_direct_navigation_serves_only_the_spa_route
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-013] El servidor estático nunca sale del build
- **Regla**: symlink fuera del build, `..`, `%2e%2e`, `%5c`, doble codificación, `/data/laboratorio.db` y `/private.txt` → 400/404 sin filtrar contenido; Host/Origin ajenos y `Sec-Fetch-Site: cross-site` en `/` → 403.
- **Fuente**: test_app.py:test_static_never_leaks_outside_build
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-014] Falta de build falla el arranque de producción; la API factory sigue usable
- **Regla**: sin `index.html` y `serve_frontend=True` → `RuntimeError("npm run build")`; sin `serve_frontend`, la API (`/api/v1/queue`) funciona.
- **Fuente**: test_app.py:test_missing_build_fails_production_startup_but_api_factory_remains_usable
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-015] Rutas de settings son absolutas e independientes del cwd
- **Regla**: `frontend_dist`, `history_path`, `rankings_path` son absolutas y `frontend_dist == <backend>/../frontend/dist` aunque cambie el cwd.
- **Fuente**: test_app.py:test_settings_paths_are_absolute_and_cwd_independent
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-016] El navegador se abre solo tras iniciar su propio servidor y una vez
- **Regla**: `BrowserServer.startup` no abre el navegador si `started` es False; con `started` True abre exactamente una vez `http://127.0.0.1:8765/` aunque se llame varias veces.
- **Fuente**: test_app.py:test_browser_only_after_own_server_started_and_once
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-017] Puerto ocupado nunca crea ni abre el servidor
- **Regla**: `run_production` con puerto ocupado → `RuntimeError("occupied")` y el navegador no se abre (no confunde otra instancia con la propia).
- **Fuente**: test_app.py:test_port_busy_never_creates_or_opens_server
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-018] Entradas congeladas faltantes o corruptas impiden el arranque
- **Regla**: historial inexistente → `ValueError("file not found")`; historial alterado (`tampered`) → `ValueError("SHA-256 mismatch")`; en ambos antes de abrir el navegador.
- **Fuente**: test_app.py:test_frozen_inputs_fail_before_browser_opens; test_corrupt_frozen_input_refuses_startup
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-019] Uvicorn real abre el navegador una vez con el listener propio listo
- **Regla**: con un socket propio, `BrowserServer.run` abre `http://127.0.0.1:{port}/` una sola vez y esa URL responde 200 `{"ready":true}`; `should_exit` detiene el hilo.
- **Fuente**: test_app.py:test_real_uvicorn_opens_once_after_owned_listener_is_ready
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-SET-020] Lanzador Windows con guardas de primer plano y fallo
- **Regla**: `iniciar-laboratorio.bat` usa `pushd "%~dp0"`/`popd`, verifica `frontend\dist\index.html`, sugiere `npm run build`, usa `py -3` con `-b -m laboratorio.app`, conserva `exit_code`, hace `pause` y no usa `start ` ni `pip install`.
- **Fuente**: test_app.py:test_windows_launcher_has_foreground_and_failure_guards
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-SET-021] Parseo de historial: orden, días vacíos, dtype uint8
- **Regla**: `parse_history` ordena días y horas, omite días vacíos; `labels` `YYYY-MM-DD HH:MM`; `nums` es `uint8` de forma (N,5).
- **Fuente**: test_adapter.py:test_parse_orders_days_and_hours_and_skips_empty_days
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-022] Duplicados idénticos se fusionan; conflictos detienen la carga
- **Regla**: mismo sorteo con distintas `source_url` pero mismos números se fusiona; números distintos → `DataError("Conflicting")`.
- **Fuente**: test_adapter.py:test_identical_duplicates_merge_and_conflicts_stop_the_load
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-023] Historial malformado se rechaza
- **Regla**: `DataError` para hora `5:05`, 4 números, número sin cero a la izquierda (`"1"`), fecha inválida (`2025-02-30`) y día que no es lista.
- **Fuente**: test_adapter.py:test_malformed_history_is_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-024] Archivos faltantes y hashes cambiados fallan con errores claros
- **Regla**: historial ausente → `DataError("not found")`; hash distinto del congelado → `DataError("SHA-256")` (con `None` no se verifica); rankings ausentes → `"not found"`.
- **Fuente**: test_adapter.py:test_missing_files_and_changed_hashes_fail_with_clear_errors
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-025] Rankings se alinean con las filas del historial
- **Regla**: `row_ids` conservados; `family("transition")` tiene forma `(filas,100)` y dtype uint8; familia inexistente (`logistic`) → `DataError("unavailable")`.
- **Fuente**: test_adapter.py:test_rankings_align_with_history_rows
- **Categoría**: contrato
- **Riesgo si se pierde**: alto

### [B-SET-026] Rankings usan el snapshot verificado tras reemplazar la ruta
- **Regla**: tras reemplazar el archivo en disco, las familias ya cargadas siguen siendo las verificadas (no se relee el archivo).
- **Fuente**: test_adapter.py:test_rankings_use_the_verified_snapshot_after_path_replacement
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-027] Rankings desalineados o inválidos se rechazan
- **Regla**: `timestamps` que no coinciden → `DataError("timestamps")`; `row_ids` decrecientes → `"increasing"`; ranking que no es permutación → `"permutation"` al pedir la familia.
- **Fuente**: test_adapter.py:test_misaligned_or_invalid_rankings_are_rejected
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-SET-028] Caché de votos de paridad se reutiliza por una instancia nueva
- **Regla**: `LabData.parity_votes()` calcula una vez (`compute_parity_votes` llamado 1 vez); una instancia nueva lee la caché en disco sin recalcular.
- **Fuente**: test_adapter.py:test_parity_cache_is_reused_by_a_fresh_instance
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: medio

### [B-SET-029] Caché de paridad con votos alterados de forma válida se recupera
- **Regla**: si los votos cacheados cambian manteniendo forma válida, la instancia nueva los recalcula (1 llamada) y devuelve los votos correctos.
- **Fuente**: test_adapter.py:test_parity_cache_recovers_from_shape_valid_changed_votes
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-030] Caché de paridad con procedencia incorrecta se recomputa
- **Regla**: `history_sha256` o `algorithm` incorrectos en la caché → se recalcula 1 vez y el resultado es el esperado.
- **Fuente**: test_adapter.py:test_parity_cache_recomputes_when_provenance_is_wrong
- **Categoría**: regla de negocio
- **Riesgo si se pierde**: alto

### [B-SET-031] Historial congelado coincide con el loader de referencia (real_data)
- **Regla**: 105 426 sorteos, primero `2025-03-05 05:05`, último `2026-09-25 18:20`, huella sha256 del arreglo (N,5) int64 `af0c827c…973664`.
- **Fuente**: test_adapter.py:test_frozen_history_matches_the_reference_loader
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

### [B-SET-032] Rankings y votos de paridad congelados coinciden con la referencia (real_data)
- **Regla**: 65 235 filas rankeadas (primera 33 648 = `2025-09-02 05:10`, última 105 425); huella de votos `5100eb5d…ec` y suma 76 369; la caché en disco se reutiliza (`cache/parity-*.npz`).
- **Fuente**: test_adapter.py:test_frozen_rankings_and_parity_votes_match_the_reference
- **Categoría**: contrato
- **Riesgo si se pierde**: medio

<!-- B-SET:fin -->


## 6. Flaky / fallidos previos — intención preservada

Estos tests fallaban ANTES de esta sesión (medidos contra una base limpia en HEAD:
11 failed / 793 passed). Ninguno es regresión de este trabajo. Se documenta la
**intención** de cada uno para que sobreviva aunque el test sea inestable: la
reescritura debe reimplementar el comportamiento verificado, no el test exacto.

### [B-FLAKY-001] `test_dataset_discovery_is_bounded_inert_and_metadata_only` (test_api.py)
- **Regla**: el descubrimiento de datasets es acotado (límite de lectura), inerte
  (no muta estado) y devuelve solo metadatos — nunca filas de datos.
- **Fuente**: `tests/test_api.py::test_dataset_discovery_is_bounded_inert_and_metadata_only`
- **Categoría**: contrato | regla de negocio
- **Riesgo si se pierde**: alto

### [B-FLAKY-002] `test_settings_exact_quota_and_validation` (test_api.py)
- **Regla**: los ajustes de cuota se leen y escriben con valores exactos (bytes
  sin redondeo) y toda entrada inválida se rechaza sin mutar.
- **Fuente**: `tests/test_api.py::test_settings_exact_quota_and_validation`
- **Categoría**: validación | formato
- **Riesgo si se pierde**: medio

### [B-FLAKY-003] `test_settings_below_used_conflicts_without_mutation` (test_api.py)
- **Regla**: fijar la cuota por debajo del uso actual devuelve conflicto (409) y
  **no** modifica el valor almacenado.
- **Fuente**: `tests/test_api.py::test_settings_below_used_conflicts_without_mutation`
- **Categoría**: validación | regla de negocio
- **Riesgo si se pierde**: alto

### [B-FLAKY-004] `test_timeout_uses_frozen_admission_policy_not_current_policy` (test_profile_batch_queue.py)
- **Regla**: el timeout de un run aplica la política de admisión **congelada** en
  el momento de la admisión, no la política vigente al correr.
- **Fuente**: `tests/test_profile_batch_queue.py::test_timeout_uses_frozen_admission_policy_not_current_policy`
- **Categoría**: regla de negocio | concurrencia
- **Riesgo si se pierde**: alto

### [B-FLAKY-005] `test_enqueue_failure_compensates_batch_and_allows_same_identity_retry` (test_profile_batch_queue.py)
- **Regla**: si falla el encolado, la admisión se compensa (rollback) y se permite
  reintentar con la misma identidad de solicitud.
- **Fuente**: `tests/test_profile_batch_queue.py::test_enqueue_failure_compensates_batch_and_allows_same_identity_retry`
- **Categoría**: concurrencia | regla de negocio
- **Riesgo si se pierde**: alto

### [B-FLAKY-006] `test_submission_idempotency_never_enqueues_existing_batch_twice` (test_profile_batch_queue.py)
- **Regla**: reenviar una solicitud idéntica nunca encola el mismo batch dos veces.
- **Fuente**: `tests/test_profile_batch_queue.py::test_submission_idempotency_never_enqueues_existing_batch_twice`
- **Categoría**: concurrencia | contrato
- **Riesgo si se pierde**: alto

### [B-FLAKY-007] `test_corrupt_worker_result_stops_batch_but_keeps_prior_ordinal` (test_profile_batch_queue.py)
- **Regla**: un resultado corrupto del worker detiene el batch pero **conserva**
  los ordinales ya completados.
- **Fuente**: `tests/test_profile_batch_queue.py::test_corrupt_worker_result_stops_batch_but_keeps_prior_ordinal`
- **Categoría**: concurrencia | regla de negocio
- **Riesgo si se pierde**: alto

### [B-FLAKY-008] `test_cycling_private_roundtrip_and_cross_version_fail_closed` (test_profile_storage.py)
- **Regla**: los perfiles cycling privados hacen roundtrip completo y fallan
  cerrado ante cruces de versión (nunca degradan silenciosamente).
- **Fuente**: `tests/test_profile_storage.py::test_cycling_private_roundtrip_and_cross_version_fail_closed`
- **Categoría**: contrato | validación
- **Riesgo si se pierde**: alto

### [B-FLAKY-009] `test_audaz_v3_persistence_replay_and_version_checks` (test_profile_storage.py)
- **Regla**: los perfiles audaz v3 persisten, se reproducen idénticamente y
  verifican versión de forma estricta.
- **Fuente**: `tests/test_profile_storage.py::test_audaz_v3_persistence_replay_and_version_checks`
- **Categoría**: contrato | validación
- **Riesgo si se pierde**: alto

### [B-FLAKY-010] `test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically` (test_storage.py)
- **Regla**: la migración v7→v9 preserva los bytes y revierte atómicamente si
  falla (nunca deja el storage a medio migrar).
- **Fuente**: `tests/test_storage.py::test_migration_v7_to_v9_preserves_bytes_and_rolls_back_atomically`
- **Categoría**: contrato | concurrencia
- **Riesgo si se pierde**: alto

## 7. Comportamientos agregados en esta sesión (preservar en la reescritura)

### [B-NEW-001] Techos del juego activo
- **Regla**: `make_game` rechaza `numbers > 1000` y `positions > 16`
  (`MAX_GAME_NUMBERS` / `MAX_GAME_POSITIONS`, coherentes con los techos de
  perfil). El default Q80 (100/5) y el caso del brief (3 posiciones, 60/10/5)
  siguen válidos.
- **Fuente**: `tests/test_contracts.py::test_make_game_rejects_game_sizes_above_the_ceilings`,
  `tests/test_contracts.py::test_game_ceilings_keep_the_supported_games_valid`,
  `tests/test_settings.py::test_game_put_rejects_invalid_rules_with_the_reason`
- **Categoría**: validación
- **Riesgo si se pierde**: alto

### [B-NEW-002] Editor de reglas del juego persistente
- **Regla**: `GET/PUT /api/v1/settings/game` persiste las reglas en la tabla
  `settings_game` (fila id=1), valida con `make_game`, adopta el juego en el
  arranque vía `app.py` (orden stored > env > default) y solo afecta simulaciones
  futuras ([A7]). PUT sin Origin da 403; validación inválida da 422 con motivo.
- **Fuente**: `tests/test_settings.py::test_game_*`
- **Categoría**: contrato | regla de negocio
- **Riesgo si se pierde**: alto

## 8. Índice de cobertura

| Área | Ítems extraídos |
|---|---|
| B-API — Contratos de API | 114 |
| B-DOM — Dominio y contratos | 186 |
| B-STO — Persistencia | 103 |
| B-QUE — Cola y trabajos | 50 |
| B-SET — App / settings | 32 |
| **Subtotal comportamientos** | **485** |
| B-FLAKY — intención de fallidos previos | 10 |
| B-NEW — agregados en esta sesión | 2 |
| **Total** | **497** |

**Cobertura de archivos**: 40/40 archivos de test de `webapp/backend/tests/`
citados. Excluidos por no ser fuente de verdad: `.git/gentle-ai/candidate-views/**`
y `repo_ref/**`.
