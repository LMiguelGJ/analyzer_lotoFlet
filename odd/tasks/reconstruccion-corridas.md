# Reconstrucción: Laboratorio de corridas

Plan: `.pi/plans/reconstruccion-corridas.md`. Rama `feat/rebuild-corridas` desde `feat/bossfarmer-design` (`09a15fd`).
Alcance autorizado: limpieza previa (hecha) y **ejecución completa del plan** (orden del usuario: "ejecutar este plan tal cual usando ODD y la skill impeccable, en modo yolo"). Sin push, PR ni merge salvo pedido explícito.
`repo_ref/` y `lagacy_loto/` **no se tocan** por decisión del usuario. Sin push, PR ni merge.
Los datos de usuario en `%LOCALAPPDATA%\LaboratorioQuiniela` y las migraciones SQL 1–13 no se tocan.

## Tareas de limpieza

- [x] C1 — Backend: módulos y tests de perfiles, lotes, cola, agentes, importación, simulaciones y configuraciones borrados; `repository.py`, `app.py`, `api/__init__.py`, `settings.py`, `contracts.py`, `session.py`, `selection.py` y `adapter.py` recortados. Commit `a3d1fd6`.
- [x] C2 — Frontend: de 114 a 17 archivos, sin tests, con dos rutas de relleno (Corridas, Ajustes). Commit `d21ac3f`.
- [x] C3 — `webapp/reports/` (303 archivos, 12 MB, casi todos sin versionar), docs de funciones retiradas y `webapp/README.md` reescrito. Commit `1986951`.
- [x] C4 — Verificación independiente y corrección del hueco hallado. Commit `fix` posterior a `1986951`.

Se conserva hasta R1: `domain/backtest.py`, `api/backtests.py` y `storage/backtest_trace.py` (motor de referencia).

**Decisión del usuario (mensaje en curso de C1): borrar TODOS los tests**, backend y frontend ("son demasiados test, eliminalos todos, esto será algo desde 0"). Los tests nuevos se escriben junto con el código nuevo (R1 en adelante, test-first). Los 14 escenarios de referencia siguen documentados en `docs/resumen_resultados_quiniela.md` y en el historial de git (`test_backtest_golden.py` en `7634679`).

## Evidencia

Línea base antes de borrar (HEAD `7634679`, `py -3.14`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` porque un plugin externo choca con `--browser`): backend **957 pasan, 1 falla previa** (`test_backtest_trace::test_caps_capture_only_whole_session_prefixes[MAX_TRACE_BYTES-1100]`, umbral de 1100 bytes desactualizado). La verificación del backend recortado pasa a ser: `ruff`, importación de módulos y un smoke por API con datos temporales que reproduce la primera fila del escenario de referencia.

**C1** — backend de 14.969 a 2.579 líneas (92 archivos en el índice, −30.933 líneas; unos 555 tests por conteo de `def test_`). `ruff` limpio e importación correcta. La cuota calculada sobre una copia de la base real del usuario (API de respaldo de SQLite, solo lectura) es idéntica entre el código de `7634679` y el nuevo, salvo el espacio libre del disco, que es una medida en vivo. La migración desde cero (incluido el perfil legacy de la migración 4) llega a la versión 13.

**C2** — `src` de 20.596 a 879 líneas; `index.css` de 596 a 185. `typecheck` y `build` salen con código 0 (JS 238,96 kB, CSS 20,17 kB).

**C4** — arnés independiente (`rebuild-c4/runtime.cjs`: backend real con datos temporales en el puerto propio 5188, Chrome vía Playwright a 390 y 1440 px con movimiento reducido): la primera pasada dio 32/43. Causa única: tras el recorte, `_SPA_PATH` solo servía tres rutas y los enlaces viejos devolvían 404 JSON en carga directa; además Chrome pedía `/favicon.ico`. Arreglo: `app.py` sirve `index.html` para toda ruta de página (los archivos con extensión y `/api` siguen dando 404) e `index.html` declara un icono vacío. Segunda pasada: **43/43**, cero errores de consola, cero pedidos externos. Incluye la corrida de referencia por API: transition, cobertura 1, bold, capital 2.000, meta 2.800 → 681/963/70,7/282/10,3, igual que la fila 1 de la tabla de referencia; 404 en las rutas retiradas; Host ajeno y mutación sin Origin rechazados con 403. Fuera de lo tocado: `repo_ref/`, `lagacy_loto/`, migraciones, `database.py`, `pyproject.toml` y `chance_express_history.json` (diff vacío contra `09a15fd`).

**Datos medidos para R0:** la corrida de referencia tardó **4,2 s** (>3 s: por la regla D4 se iría a segundo plano, pero este caso es audaz con cobertura 1 y el caso nuevo es otro: se mide en R0) y dejó **964 sesiones / 65.235 apuestas**; la traza se truncó en **146 sesiones / 9.920 apuestas** por el tope de 10.000 apuestas.

**Limites:** no existen tests automatizados por decisión del usuario; la cobertura de navegador es solo la cascara con páginas de relleno; la app que el usuario dejó abierta en el puerto 8765 corre el código viejo en memoria hasta que la reinicie; `docs/catalogo-estrategias.md` enlaza a dos documentos borrados; `package.json` conserva el script y la dependencia `vitest` para los tests nuevos.

## Tareas de construcción

Skill `impeccable`: `context.mjs` ejecutado una vez (sin PRODUCT.md ni DESIGN.md previos). Modo yolo: sin entrevista nueva; `PRODUCT.md` escrito desde la especificación aprobada, con lo inferido marcado. La dirección visual se decide con `concept-seed.mjs` y se registra en `DESIGN.md` antes de la primera edición de UI. Todo código nuevo se escribe test-first.

- [x] R0 — Medición base. D4 = síncrono; D11 revisado (ver plan §4b). Commit con el plan.
- [ ] R1 — Motor de corrida v2 (`domain/runs.py`), test-first, con caracterización contra `run_backtest` y la fila `parity/50/flat` de la tabla de referencia.
- [ ] R2 — Selección y datos de corrida (mezcla vectorizada, paridad, ventana por fechas).
- [ ] R3 — Historial activo e importación sin vista previa (migración 0014).
- [ ] R4 — Corridas: tabla `runs` (migración 0015), traza revisada y API `/api/v1/runs`.
- [ ] R8a — Dirección visual con `impeccable` (new-work) y `DESIGN.md`.
- [ ] R5 — Frontend: lista, formulario, resultado y Ajustes.
- [ ] R6/R7 — Retirar `/backtests` y el código viejo restante.
- [ ] R9 — Verificación independiente final, documentación y cierre.

### Evidencia R0

Medido con `py -3.14` sobre el historial real (script fuera del repo): 105.426 sorteos, 65.235 con ranking (61,9 %, desde 2025-09-02). Carga 1,4 s; 2 familias de ranking 0,2 s; votos de paridad 4,2 s la primera vez (luego caché). Ejemplo del usuario sin límite de sorteos: 71 sesiones, todas cerradas por quiebra tras ~880 apuestas, 65.235 apuestas, retorno −21,5 %. Mezcla 60/40: 2,0 s en total (filas 1,6 + motor 0,4). Decisiones: ejecución **síncrona** (D4) y traza **revisada** (D11: resumen de todas las sesiones siempre; apuestas hasta 250.000 / 32 MiB, en columna aparte).
