# Plan: cuatro sistemas nuevos para Leidsa (Transición, Ciclo vencido, Terminaciones y decenas, Ensamble)

> Created by `plan-mode-egm` · Language: es · Created: 2026-11-24
> Status: approved (revision de Goldfish interrumpida por pedido del humano: aprueba y ejecuta)

## Summary

Agregar a la lista `leidsa_quiniela` cuatro sistemas de ranking calculados al vuelo y de forma causal
(`transition`, `overdue`, `digits`, `ensemble`), ofrecerlos en laboratorios y corridas con etiquetas y ayudas
propias de Leidsa, sin tocar el comportamiento de Loteka Chance Express, y al final probarlos con los sorteos
de Leidsa de 2010-07-19 a hoy, año por año y con una prueba fuera de muestra.

## Current State Analysis

- **Affected area**: `webapp/backend/laboratorio/` (engine, domain, api) y `webapp/frontend/src/pages/`
  (laboratories, reference-labs). Datos: `datos/leidsa_quiniela_history.json` (5.836 sorteos, 2010-07-19 →
  2026-11-23).
- **Existing patterns and helpers to reuse**:
  - `engine/causal_rankings.py`: `FAMILIES` (l.~37) = `("cold","freq_hist","freq_recent","decay")`,
    `DEFAULT_PARAMS` (l.40), `TIE = _tie_priority()`, `N_VALUES = 100`, `_check_nums(nums)`,
    `_exclusive_counts(indicator)` (fila t cuenta filas `< t`), `_first_position_indicator(nums)`,
    `_windowed(cumulative, window)`, registro `_KEYS` (l.~158) de funciones
    `fn(nums: int64[n,k], params: dict) -> float[n,100]` (mayor = mejor, fila t causal),
    `score_matrix(system, nums, params=None)`, `rank_rows(scores, rows=None) -> uint8` (orden
    `np.lexsort((TIE, -scores))`), `class CausalRankings` con `.family(system)` cacheado por sistema.
  - `nums` es `History.nums`, n×3 para Leidsa, cronológico; la 1.ª posición es la columna 0.
  - `engine/list_catalog.py:101` `ListCatalog.lab_data` construye
    `LabData(history, rankings=CausalRankings(history.nums), settings)` y lo cachea por lista.
  - `domain/number_lists.py`: Leidsa `available_systems=(PARITY_SYSTEM, "cold", "freq_hist",
    "freq_recent", "decay")` (l.53); Chance `(PARITY_SYSTEM, *SYSTEMS)` (l.42); `system_label` (l.64) =
    `SYSTEMS.get(system, system)`; `unavailable_message` (l.68).
  - `domain/contracts.py:73` `SYSTEMS` (13 ids archivados de Chance, ya incluye `transition` →
    "Transición" y `ensemble` → "Ensemble"; no incluye `overdue` ni `digits`).
  - Chance usa `engine/adapter.py:52` `Rankings.family` sobre `pos1.npz` y `app.state.rankings_cache`;
    Leidsa usa `CausalRankings` por instancia: no comparten caché.
- **Constraints**:
  - Chance Express byte-idéntico: `tests/test_reference_parity.py`, `tests/test_reference_matrix.py`,
    `tests/test_runs_api.py:57` (`options["systems"]` = los 13 de `SYSTEMS`) y
    `tests/test_leidsa_labs.py:~190-193,215-220` (Chance: 13 sistemas en corridas, 14 en laboratorios)
    deben pasar sin cambiar sus aserciones.
  - `contracts.SYSTEMS` no se modifica: Chance ofrece `(PARITY_SYSTEM, *SYSTEMS)`, y agregar ahí ids nuevos
    los ofrecería en Chance.
  - `ranking_method = "causal-on-the-fly/v1"` (`domain/laboratory_run_snapshots.py:17`) no cambia: las
    corridas guardadas de Leidsa lo validan con igualdad exacta.
  - Causalidad: la fila t usa solo sorteos `< t`; la fila 0 debe dar puntuación constante (orden `TIE`).
  - `run_data.MAX_COMPONENTS = len(SYSTEMS)` (13) se mantiene.
  - Tests del backend: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (plugins globales chocan en `--browser`).

## Proposed Changes

### 1 — `webapp/backend/laboratorio/engine/causal_rankings.py`
- **What**: dejar `FAMILIES` con los 4 actuales y agregar
  `EXTRA_FAMILIES = ("transition", "overdue", "digits", "ensemble")` y
  `LEIDSA_FAMILIES = FAMILIES + EXTRA_FAMILIES`. Agregar a `DEFAULT_PARAMS`:
  `"transition": {"fallback_window": 500}`, `"overdue": {}`, `"digits": {"window": 500}`,
  `"ensemble": {"components": ("cold","freq_hist","freq_recent","decay","transition","overdue","digits")}`.
  Registrar en `_KEYS` cuatro funciones nuevas con la firma existente:
  - `_transition_key(nums, params)`: `a = nums[:,0]`. Matriz `M` 100×100 de conteos de pares
    `(a[s-1], a[s])`. Fila t (t ≥ 2): `score[t] = M_t[a[t-1]] + f[t] / (1000 * (fallback_window + 1))`,
    donde `M_t` cuenta solo pares con `s ≤ t-1` y `f[t]` es el conteo de `_freq_recent_key` con ventana
    `fallback_window` (desempata y cubre estados sin historia). Filas 0 y 1: `score = f[t]/…` (fila 0 = 0).
    Implementación: bucle en t con actualización incremental de `M` (n ≈ 5.836).
  - `_overdue_key(nums, params)`: por número v, con apariciones en 1.ª posición estrictamente antes de t:
    `age = t - last_seen(v)` (nunca visto: `t + 1`); `mean_gap = (last_seen - first_seen) / (count - 1)`
    si `count ≥ 2`, si no `100`; `score = age / mean_gap`. Fila 0: todos `1/100` (constante).
  - `_digits_key(nums, params)`: sobre las últimas `window` filas `< t` de la columna 0,
    `U[d]` = proporción de sorteos con unidad `d`, `D[d]` = proporción con decena `d`;
    `score[t, v] = U[v % 10] + D[v // 10]`. Fila 0: 0.
  - `_ensemble_key(nums, params)`: para cada componente, `pos = argsort(rank_rows(score_matrix(c, nums)))`
    (posición 0 = mejor); `score = -mean(pos sobre componentes)` (Borda). No incluye paridad, que no es un
    ranking de 100 números.
- **Why**: reutilizar el registro, el orden `TIE` y la caché de `CausalRankings.family` sin tocar las 4
  familias que se comparan contra `pos1.npz`.
- **Verify**: tests nuevos de la sección 7 (permutación, causalidad, filas iniciales a mano) y
  `tests/test_causal_rankings.py` sin cambios en sus parametrizaciones (`SYSTEMS = cr.FAMILIES`).

### 2 — `webapp/backend/laboratorio/domain/number_lists.py`
- **What**:
  - Leidsa: `available_systems=(PARITY_SYSTEM, "cold", "freq_hist", "freq_recent", "decay",
    "transition", "overdue", "digits", "ensemble")`.
  - Nuevo campo de `NumberList`: `system_labels: Mapping[str, str]` (default vacío). Para Leidsa:
    `{"transition": "Transición", "overdue": "Ciclo vencido", "digits": "Terminaciones y decenas",
    "ensemble": "Ensamble"}`.
  - Nueva constante `LIST_ONLY_SYSTEMS = ("overdue", "digits")` (ids que no están en `contracts.SYSTEMS`).
  - `system_label(system, number_list=None)`: primero `number_list.system_labels`, luego `SYSTEMS`,
    luego el id. `unavailable_message` pasa la lista.
- **Why**: etiquetas por lista sin tocar `contracts.SYSTEMS` (Chance mantiene "Ensemble").
- **Verify**: `test_leidsa_labs` ampliado: `/laboratories/options` de Leidsa trae
  `{"id":"ensemble","label":"Ensamble"}` y Chance sigue con "Ensemble".

### 3 — `webapp/backend/laboratorio/engine/run_data.py` y `engine/run_service.py`
- **What**:
  - `run_data.py`: la validación de `RunStrategy.__post_init__` (l.~100) acepta
    `name in SYSTEMS or name in LIST_ONLY_SYSTEMS`. `SYSTEM_LABELS` y `MAX_COMPONENTS` sin cambios.
  - `run_service.py`: l.85 (`_fail_validation`) misma regla; `_default_name` (l.99, l.102) usa
    `system_label(system, number_list)` en vez de `SYSTEM_LABELS[...]`. La regla de disponibilidad por lista
    sigue en `_check_list_rules` (l.140, `available_systems`).
- **Why**: hoy rechazan con `ValueError`/`KeyError` todo id fuera de `SYSTEMS`.
- **Verify**: `POST /api/v1/runs` con Leidsa y `{"system":"overdue","percent":100}` → 201; con Chance →
  422 y el mensaje de `unavailable_message`.

### 4 — `webapp/backend/laboratorio/api/laboratories.py` (l.77-96) y `api/runs.py` (l.102-117, l.160)
- **What**: al armar la lista de sistemas de `/options`, iterar `(PARITY_SYSTEM, *SYSTEMS)` y, solo si la
  lista activa no es Chance, agregar al final `LIST_ONLY_SYSTEMS`; la etiqueta sale de
  `system_label(system, number_list)`. `systems_available` sigue siendo `list(number_list.available_systems)`.
- **Why**: hoy solo se muestran ids de `SYSTEMS`; `overdue` y `digits` no aparecerían. Chance no cambia.
- **Verify**: `tests/test_runs_api.py:57` y los asserts de Chance en `test_leidsa_labs.py` pasan sin
  cambios; Leidsa ofrece 9 disponibles.

### 5 — Tests existentes a actualizar (`webapp/backend/tests/`)
- **What**:
  - `test_causal_rankings.py` l.68-77: `rankings.family("transition")` ya no lanza `DataError`; cambiar el id
    por `"notebook"` (sigue sin estar en `_KEYS`). l.16 (`set(cr.FAMILIES) == {...4}`) no cambia.
  - `test_leidsa_labs.py`: l.19-20 `AVAILABLE_SYSTEMS` y `RANKING_SYSTEMS` incluyen los 4 nuevos;
    l.165-186 renombrar `test_run_options_for_leidsa_offer_exactly_the_five_systems` a `..._nine_systems`
    con `len(...) == 9` y el total de ítems `13 + 2`; l.206-212 lab options; l.249-252 cambiar
    `lab_config("transition", 1)` por `lab_config("notebook", 1)`.
- **Why**: esas aserciones fijan la lista de 5 sistemas.
- **Verify**: los tests corren en verde tras el cambio y fallan antes (RED observado).

### 6 — Frontend `webapp/frontend/src/pages/`
- **What**:
  - `laboratories/option-help.ts`: `systemHelpOptions` (l.84-91) recibe el id de la lista; para listas que
    no son Chance busca primero en `listSystems`. Agregar a `listSystems` entradas de Leidsa para `cold`,
    `transition`, `overdue`, `digits` y `ensemble` con `label`, `what`, `effect` y `example` en español
    simple, diciendo que es una hipótesis de patrón y no una garantía.
  - `LaboratoryOptionHelp.tsx:25` y `LaboratoryForm.tsx:63`: pasar `options.list.id`.
  - `reference-labs/lab-model.ts:3` `SYSTEM_LABELS`: agregar `freq_hist` "Frecuencia histórica",
    `freq_recent` "Frecuencia reciente", `decay` "Decaimiento", `overdue` "Ciclo vencido", `digits`
    "Terminaciones y decenas" (usado por `LaboratoryPanel.tsx:173,181` y `Workspace.tsx:28`).
- **Why**: hoy Leidsa mostraría la ayuda de Chance para `transition`/`ensemble`/`cold` y el id crudo para
  los nuevos.
- **Verify**: `LaboratoryForm.list.test.tsx` ampliado (Leidsa ofrece los 9 con sus etiquetas y la ayuda de
  `transition` es la de Leidsa); `form-model.test.ts:67-88` (Chance) sin cambios.

### 7 — Tests nuevos `webapp/backend/tests/test_leidsa_new_systems.py`
- **What**: para cada familia de `EXTRA_FAMILIES`: cada fila es permutación de 0..99; causalidad (mutar
  sorteos `≥ t` no cambia filas `≤ t`); fila 0 = `argsort(TIE)`; ejemplos calculados a mano con un historial
  de 4–6 sorteos (transición cuenta el par correcto; ciclo vencido con `count ≥ 2`; dígitos con unidades y
  decenas; ensamble = promedio de posiciones). API: crear y correr un laboratorio de Leidsa con cada sistema
  nuevo (201) y que Chance los rechace (422). Tiempo: una corrida de rango completo por familia < 5 s.
- **Verify**: RED antes de implementar (importa `EXTRA_FAMILIES` inexistente), GREEN después.

### 8 — Prueba final ODD con todos los años
- **What**: documento `odd/tasks/leidsa-4-sistemas.md` (Specs con el pedido literal, Tasks, Log) y espejo
  Engram `odd/leidsa-4-sistemas/tasks`. Al terminar, script en el directorio temporal del SO (no en el repo)
  que, con `fastapi.testclient.TestClient` y `create_app` sobre un `data_dir` temporal (lista activa
  `leidsa_quiniela`), corre los 9 sistemas × cobertura {1,2,3,5,10} × apuesta {flat, ladder, bold} ×
  capital {1000, 2000, 5000, 20000} × meta +{20, 100, 1000}, desde `2010-07-19 00:00` hasta
  `2026-11-24 23:59`, y reporta:
  1. Neto por año (sesiones contadas en el año de cierre, como ya se hizo) para el mejor de cada sistema.
  2. Fuera de muestra: elegir con 2019-01-01 → 2022-12-31 y confirmar sin tocar con
     2023-01-01 → 2026-11-24 (2010–2018 se informa aparte: no se comporta como azar, ver
     `odd/reports/investigacion-estrategias.md` §3).
  3. Cuántas superan 10 % anual en ambos tramos.
  Resultado en `odd/reports/leidsa-4-sistemas.md`. Crear en la app real (servidor :8765, tras reiniciarlo)
  solo el mejor laboratorio por sistema nuevo, con todo el rango.
- **Why**: es la prueba pedida ("con todos los años de leisa con ellos desde el 2010 hasta ahora").
- **Verify**: el informe muestra para cada sistema su tabla anual y el resultado fuera de muestra; los
  netos de los laboratorios creados en la app coinciden con los del script.

## Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Agregar `overdue` y `digits` a `contracts.SYSTEMS` | Chance ofrece `(PARITY_SYSTEM, *SYSTEMS)`: aparecerían en Loteka y romperían sus payloads y tests. |
| Ids nuevos `leidsa_transition`, `leidsa_ensemble` | Evita colisión, pero duplica conceptos; la colisión ya está aislada por lista (caché distinta, validación por `available_systems`). |
| Ensamble como caso especial en `CausalRankings.family` | Rompe la firma uniforme de `_KEYS`; como score Borda entra en el registro sin código nuevo de caché. |
| Modelos de machine learning (LSTM) | Sin evidencia pública de ventaja (ver informe de investigación) y caros de validar. |
| Recalcular `pos1.npz` para Leidsa | El pipeline de `repo_ref/chance_rank` está atado a 5 posiciones y a Loteka. |

## Assumptions & Decisions

- Transición y los demás usan la 1.ª posición (columna 0), igual que las familias actuales.
- Ensamble combina 7 rankings (sin paridad); "los 8 sistemas" del pedido = los 7 rankings + paridad, que no
  es combinable como ranking.
- Etiqueta de `ensemble` en Leidsa: "Ensamble"; en Chance sigue "Ensemble".
- Ventanas fijas (500) como las familias actuales; no se ajustan parámetros con los datos.
- Entrega en dos commits: backend (cambios 1–5 y 7) y frontend (6); la prueba final y su informe en un
  tercer commit de docs. Sin push.

## Verification

- [ ] `cd webapp/backend && PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3 -B -m pytest tests/test_leidsa_new_systems.py tests/test_causal_rankings.py tests/test_leidsa_labs.py tests/test_runs_api.py tests/test_run_data.py tests/test_laboratories_api.py tests/test_reference_parity.py tests/test_reference_matrix.py -q -p no:cacheprovider` — todo pasa.
- [ ] `py -3 -B -m ruff check laboratorio tests` y `ruff format --check` sobre los archivos tocados — limpio.
- [ ] `cd webapp/frontend && npx vitest run && npm run typecheck && npm run build` — todo pasa.
- [ ] Acceptance: en `/laboratorios/nuevo` con Leidsa activa aparecen Paridad, Fríos, Frecuencia histórica,
  Frecuencia reciente, Decaimiento, Transición, Ciclo vencido, Terminaciones y decenas y Ensamble; con
  Loteka la lista no cambia.
- [ ] Acceptance: `odd/reports/leidsa-4-sistemas.md` con tabla anual 2010–2026 por sistema y prueba fuera
  de muestra.

## Out of Scope

- Modalidades Palé y Tripleta, detector de sesgo, machine learning.
- Cambios en Loteka Chance Express o en `pos1.npz`.
- Ajustar parámetros (ventanas) con los datos.

## Goldfish Review

Status: skipped: no fresh context (el humano aprobo y pidio ejecutar; la revision quedo a medias)

| # | Severity | Where | Finding | Disposition |
|---|---|---|---|---|

## Drift Check

> Filled after implementation.
