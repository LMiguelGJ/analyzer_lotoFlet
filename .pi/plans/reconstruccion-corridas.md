# Reconstrucción: Laboratorio de corridas

Estado: **plan pendiente de aprobación** (solo lectura hasta que el usuario apruebe).
Origen: entrevista de especificación con 10 preguntas y el resumen de asunciones `[A1]…[T2]` aprobado sin correcciones.
Rama prevista: `feat/rebuild-corridas`, creada desde `feat/bossfarmer-design` (HEAD `09a15fd`, ya publicada en `origin`).
Ledger ODD previsto: `odd/tasks/reconstruccion-corridas.md` (espejo Engram `odd/reconstruccion-corridas/tasks`).

## 1. Resumen

Convertir la app en **una sola herramienta**: elegir una estrategia y las reglas del juego, correrla en **sesiones consecutivas** sobre el historial (cada sesión empieza con el capital inicial, termina por meta, quiebra o límite de sorteos, y la siguiente arranca en el sorteo siguiente) y ver la **rentabilidad** con el detalle de sesiones y apuestas.

Navegación final: **Corridas** y **Ajustes**. Se retiran simulación clásica, perfiles de juego, lotes, bibliotecas de estrategias, comparación, gráficos, reproducción, cola, asistente de cinco pasos y acceso para agentes.

El motor de sesiones consecutivas **ya existe** (`run_backtest`), así que la reconstrucción es mayormente: motor v2 (aditivo) → API y almacenamiento nuevos → frontend nuevo → retiro de todo lo demás.

## 2. Hallazgos que cambian lo acordado (leer primero)

Estos tres puntos surgieron al leer el código. Cada uno tiene un **default** en la sección 5; aprobar el plan aprueba los defaults.

1. **El historial trae 5 números por sorteo y tu ejemplo tiene 3 posiciones.** `adapter._validated_records` exige exactamente 5 números y `run_backtest` exige `len(results) == positions`. Tu regla 60/10/5 no se puede aplicar tal cual. → Decisión **D1**.
2. **Importar historial no alimenta hoy las corridas, y los rankings están congelados.** La importación actual crea *datasets* ligados a perfiles (`execution_supported: False`); las corridas leen solo `data.history` y `data.rankings`, fijados por SHA-256 (`settings.HISTORY_SHA256`, `RANKINGS_SHA256`). Los 13 rankings (transición, fríos…) existen únicamente para los sorteos que cubre `pos1.npz`; el laboratorio no tiene generador. Un sorteo importado nuevo **no tendría ranking**. → Decisión **D2**.
3. **Las corridas históricas guardadas se revalidan en cada lectura** con el modelo `CreateBacktest` (`repository.py:3096`). Cambiar ese modelo rompería la lectura de filas viejas. → Decisión **D5** (tabla nueva).

## 3. Estado actual relevante (verificado)

- `webapp/backend/laboratorio/domain/backtest.py`: `run_backtest` ya hace sesiones consecutivas con reinicio de capital, cola final `incomplete` y totales de ventana. Soporta apuesta plana/escalera/audaz, un solo ranking o paridad; **no** tiene mezcla, límite de sorteos ni ventana.
- `api/backtests.py`: POST síncrono, tope `MAX_BACKTEST_DRAWS = 200_000`, exige las huellas fijas.
- `storage/repository.py`: `create_backtest` (3044), `_validate_simulation_backtest` (3096), `get_backtest` (3208), `page_backtest_trace` (3216), `search_backtests` (3258). `storage/backtest_trace.py`: traza acotada (2 MiB, 10.000 apuestas, 1.000 sesiones).
- `domain/selection.py`: `blend_order` (mezcla ponderada, 100→1 puntos, desempate por número menor) y `parity_numbers`/`parity_votes` ya existen y están probados.
- Historial real: **105.426 sorteos, 570 fechas, 2025-03-05 → 2026-09-25**, 5 números por sorteo (leído directamente del JSON).
- `app.py`: `_SPA_PATH` lista las rutas del SPA; el ciclo de vida arranca `JobQueue`, `load_or_create_token` (agente) y `configure_game` global; el middleware valida Origin/Host y limita cuerpos de importación.
- Frontend: `App.tsx` (16 patrones de ruta), `Shell.tsx` (4 secciones + cola), `pages/backtests/index.tsx` (lista, asistente de 5 pasos y detalle de corridas históricas), `BacktestReport`, `BacktestSessions`, `QueueProvider/QueueDrawer`.
- Backend ≈ 15.000 líneas, frontend ≈ 8.900 líneas sin tests. Aproximadamente dos tercios corresponden a funciones que se retiran.

## 4. Cambios propuestos (tareas ODD)

Regla general: **aditivo primero, retiro después**. El motor viejo y las pantallas viejas siguen funcionando hasta la tarea R6; así cada paso es verificable y reversible. Cada tarea cierra con commit local (Conventional Commit) y evidencia en el ledger. No hay push, PR ni merge sin pedido del usuario.

### R0 — Rama, ledger y medición base
- Crear rama `feat/rebuild-corridas`, ledger y mirror. Dejar intactos `D DESIGN.md`, `D PRODUCT.md`, `D especificaciones-laboratorio-web.md`, `D docs/*` y `odd/qa/`.
- Línea base: `pytest` del backend y `vitest` del frontend (conteos y duración) para detectar regresiones.
- **Medición** con el intérprete del backend (`webapp/backend/.venv`, tiene numpy): cuántos sorteos tienen ranking, tiempo de `run_backtest` sobre todo el historial con paridad y con mezcla 60/40, número de sesiones con el ejemplo del usuario (cobertura 10, capital 2.000, meta 2.800, límite 12) y tamaño de la traza resultante.
- Cierra las puertas **D4** (síncrono vs segundo plano) y **D11** (topes de traza).

### R1 — Motor de corrida v2 (dominio puro, test-first)
Archivo nuevo `domain/runs.py` (+ `tests/test_runs.py`). No modifica `backtest.py`.
- `RunConfig`: capital, meta, cobertura, números (100), posiciones N (1–5), premios (N enteros ≥ 1), apuesta mínima, `max_draws` opcional.
- `run_sessions(config, rows)`: apuesta **siempre la mínima por número** (costo = cobertura × mínima); pago por posición como hoy (`ALL`: cada posición cuyo número está cubierto paga `premio × apuesta`); usa solo los primeros N resultados de cada sorteo (D1).
- Cierre de sesión, en este orden tras liquidar cada apuesta: **meta** → **quiebra** (el saldo no alcanza para la siguiente apuesta) → **límite** (sorteos transcurridos de la sesión = `max_draws`). Una sesión que se queda sin sorteos antes de cerrar es **incompleta**.
- Sorteos sin ranking: avanzan el reloj de la sesión y cuentan para `max_draws`, no apuestan (D3). Los sorteos sin ranking al inicio de una sesión nueva se saltan antes de abrirla, como hoy.
- Resultado: sesiones (resultado, saldo final, apuestas) y totales: **neto total** = Σ(saldo final − capital) de todas las sesiones = pagado − apostado; metas, quiebras, límites, incompleta; neto medio por sesión cerrada.
- Pruebas (RED primero): meta/quiebra/límite, límite y meta en el mismo sorteo, reinicio en el sorteo siguiente, cola incompleta, N = 3 con premios 60/10/5, sorteos sin ranking, ventana vacía. **Prueba de caracterización**: con N = 5, apuesta plana, sin límite y sin ventana, `run_sessions` produce las mismas sesiones y totales que `run_backtest` sobre las mismas filas.

### R2 — Selección y datos de corrida (test-first)
Archivo nuevo `engine/run_data.py` (+ tests).
- Estrategia `mix`: lista de `(sistema, porcentaje)`, 1 a 13 sistemas de `SYSTEMS`, porcentajes enteros ≥ 1 que suman 100. Un solo sistema usa su ranking directo; dos o más usan `blend_order`. Estrategia `parity`: `parity_numbers(voto)` del sorteo (el voto se calcula con los sorteos anteriores, sin fuga).
- Cobertura: entero de 1 a 50 para ambas (D10).
- Construcción de filas `Draw` por **etiqueta de sorteo** (no por posición), para que funcione con historiales importados: el ranking de un sorteo se busca por etiqueta; si no existe, `order = None`.
- Ventana opcional `start_date`/`end_date` (fechas ISO, inclusivas, dentro del historial; ventana vacía → error de validación).
- Reutiliza `adapter.parse_history`, `Rankings.family` (con su verificación de permutaciones) y la caché de paridad existente.

### R3 — Historial activo e importación sin vista previa (test-first)
- Migración **aditiva** (mecanismo existente de `storage/database.py`): tabla `history_sources` (sha256, bytes verificados, primer/último sorteo, cantidad, creación) y puntero al historial activo. Los bytes cuentan en la cuota siguiendo el patrón de `dataset_artifact_bytes` en `quota_status`.
- `POST /api/v1/history`: cuerpo = JSON canónico `{metadata, sorteos_por_fecha}` (tope 32 MiB, mismo control de cuerpo que hoy en `app.py`). Un solo paso: valida con `parse_history`, **rechaza** duplicados en conflicto, formato inválido o sorteos que contradicen la base congelada (cada etiqueta de la base debe existir con números idénticos; el resto puede ser nuevo), guarda y activa. Mismo SHA → "ya estaba". Respuesta: sorteos totales, nuevos agregados, rango, sorteos con ranking.
- `GET /api/v1/history`: historial activo (huella, rango, sorteos, sorteos con ranking) y lista de los importados. Las corridas guardan la huella que usaron; los historiales importados no se borran (reproducibilidad).
- La huella base congelada se sigue comprobando al arrancar.

### R4 — Corridas: almacenamiento y API
- Migración aditiva: tabla `runs` (id, name, schema_version, config_json, result_json, created_at). Validación en cada lectura con su propio modelo (`schema_version: 1`), independiente de `backtests`.
- Traza: variante `storage/run_trace.py` basada en `backtest_trace.py` (mismos estados completo/truncado/no almacenado, huella de integridad, topes de D11), con resultado de sesión `limit`.
- `api/runs.py` bajo `/api/v1/runs`: `POST` crear y ejecutar, `GET` lista paginada, `GET /{id}`, `GET /{id}/sessions`, `GET /{id}/sessions/{ordinal}/bets` (20 por página, máx. 100), `DELETE /{id}` (D7). `GET /api/v1/runs/options`: sistemas con etiqueta, valores por defecto del formulario, límites.
- Nombre opcional; si falta se genera ("Transición 60% + Fríos 40% · 10 números").
- Ejecución según D4. Errores en español con mensaje útil; misma política de Origin/Host que el resto.
- Pruebas: contrato de API, validación estricta, persistencia, lectura corrupta rechazada, caracterización contra `run_backtest`, ejemplo del usuario.

### R5 — Frontend nuevo (aditivo, rutas bajo `/corridas`)
- Rutas: `/corridas` (lista), `/corridas/nueva` (formulario, acepta `?base=<id>`), `/corridas/:id` (resultado), `/ajustes`.
- **Lista**: nombre, estrategia, ventana, neto total, estado; acciones Abrir, Repetir con cambios y Borrar con confirmación; paginación; estado vacío con acción principal.
- **Formulario único** (no asistente), cinco bloques en una página: Reglas (posiciones 1–5, un premio por posición, apuesta mínima; 00–99 y repeticiones permitidas como datos fijos visibles), Estrategia (editor de mezcla con porcentajes que suman 100, o Paridad; cobertura), Condiciones (capital, meta, duración máxima opcional en sorteos), Alcance (todo el historial; inicio/fin opcionales; muestra sorteos disponibles y cuántos tienen ranking), Resumen y botón **Correr**. Valores precargados con tu ejemplo salvo la duración máxima, que queda vacía. Las reglas se definen siempre en este formulario; nunca se guardan globalmente.
- **Resultado**: resumen (neto total, retorno sobre lo apostado, total apostado y pagado, sesiones por motivo de cierre, sesión incompleta, neto medio por sesión cerrada), tabla de sesiones paginada con motivo de cierre y saldo final, detalle de apuestas por sesión (sorteo, números, resultado, premio, saldo), aviso de detalle parcial/no almacenado y la advertencia fija de que no es predicción ni garantía. Sin gráficos, sin reproducción, sin comparación.
- **Ajustes**: almacenamiento (uso y cuota editable), historial activo e importación (selector de archivo → resultado inmediato), fuentes y huellas.
- Estado de ejecución: "Calculando…" durante la solicitud; con cancelación solo si D4 resulta en segundo plano.
- Tests de componentes (Testing Library + jest-axe) por pantalla; accesibilidad por teclado y etiquetas.

### R6 — Cambio de servicio y retiro del frontend viejo
- `App.tsx` solo con las rutas nuevas; `/` → `/corridas`; redirecciones: `/simulaciones*`, `/experimentos*`, `/configuraciones` → `/corridas`; `/datos` → `/ajustes`. Actualizar `_SPA_PATH` en `app.py`.
- `Shell`: dos entradas de navegación, sin cola ni `QueueProvider`.
- Eliminar páginas, modelos, componentes y tests de: simulación clásica, perfil, lote, comparación, detalle de simulación, configuraciones, datos de perfiles, gráficos (`BalanceChart`, `ComparisonChart`, `RunTrajectory`), `StrategyEditor`, `FiveStepWizard`, `QueueDrawer`, `DataTable` si queda sin uso, y los tipos y métodos de `api/client.ts` sin uso.
- Registrar en el ledger cada test retirado y la función que cubría. Ningún test de comportamiento que se conserva se debilita.

### R7 — Retiro del backend viejo (con puerta propia)
- Quitar routers y módulos de: experimentos y simulaciones, configuraciones, estrategias de perfil, lotes, cola, datasets/importación por perfiles, catálogo de perfiles, política de ejecución, `settings/game`, `settings/agent-credential` y acceso para agentes (`api/agent.py`, `agent_credentials.py`).
- Con D4 síncrono: retirar `jobs/*` y su arranque en `app.py`. Si D4 resulta en segundo plano: conservar solo lo necesario para corridas y retirar el resto.
- Quitar `configure_game` global y los `LABORATORIO_GAME_*` de `Settings`; el dominio viejo (`session.py`, `profile_*`, `batch_admission`, `contracts` de perfiles, `trajectory`, `strategy_library`, `importing/*` de perfiles) se elimina solo si el grafo de referencias (CodeGraph + `ruff` + `pytest`) muestra que no queda ningún uso.
- **No se toca** el esquema ni las migraciones de la base: los datos antiguos siguen en disco, fuera de la interfaz (T1). `repository.py` solo pierde métodos sin referencias; si un método es dudoso, se deja.
- Aprobar esta tarea es una puerta separada: el usuario confirma el inventario a borrar antes de ejecutarla.

### R8 — Dirección visual (puerta del usuario, T2)
- R1–R7 se construyen con la estructura y los tokens actuales como base neutra, sin invertir esfuerzo en estética.
- Antes de cualquier trabajo visual se pregunta qué no gustó del resultado actual y qué referencia o sensación se busca (preguntas estructuradas). Solo entonces se ejecuta un rediseño acotado a las dos secciones nuevas. `PRODUCT.md` y `DESIGN.md` se recrean al final con el estado real, solo si el usuario lo pide (hoy aparecen eliminados del árbol de trabajo).

### R9 — Documentación, verificación final y entrega
- Reescribir `webapp/README.md` y `iniciar-laboratorio.bat` si cambia algún requisito; documentar la importación y sus límites.
- Verificación independiente final (sección 6), cierre del ledger y del mirror, commits locales por unidad de trabajo. Push solo si el usuario lo pide.

## 4b. Resultados de R0 (medido, `py -3.14`, todo el historial)

- Historial: 105.426 sorteos (2025-03-05 → 2026-09-25). **Solo 65.235 (61,9 %) tienen ranking, desde 2025-09-02.** Las estrategias de ranking solo apuestan desde esa fecha; la paridad apuesta en los 105.426.
- Carga de historial y rankings: 1,4 s; verificar y leer 2 familias de ranking: 0,2 s; votos de paridad: 4,2 s la primera vez.
- Ejemplo del usuario sin límite de sorteos (capital 2.000, meta 2.800, cobertura 10, apuesta mínima 1, premios 60/10/5/2/1 aplicados a los cinco resultados): la meta **no se alcanza nunca**, todas las sesiones cierran por quiebra tras ~880 apuestas; 71 sesiones, 65.235 apuestas, retorno −21,5 %. Es un resultado del historial, no un error. Con un límite de 12 sorteos se esperan ~5.400 sesiones.
- Las tres estrategias medidas rinden entre −21,5 % y −23,0 % sobre lo apostado.

## 5. Supuestos y decisiones (defaults que se aprueban con el plan)

| Id | Decisión | Default |
|---|---|---|
| D1 | Posiciones y premios con historial de 5 números | La corrida usa los **primeros N resultados** de cada sorteo (N de 1 a 5) y N premios. El rango de números queda fijo en 00–99, lo determina el historial. |
| D2 | Historial importado sin rankings | Importar **extiende el historial**. Las estrategias con ranking solo apuestan en sorteos que tienen ranking; los demás avanzan el reloj y no apuestan. La paridad apuesta en todos. La interfaz muestra "sorteos con ranking: X de Y". Generar rankings nuevos es un proyecto aparte y queda **fuera de alcance**. |
| D3 | Qué cuenta como "sorteo" en la duración máxima | Cada sorteo transcurrido desde el inicio de la sesión, incluso sin ranking. |
| D4 | Ejecución | **Resuelto en R0: síncrono, sin cancelación.** Mezcla 60/40 con cobertura 10 sobre todo el historial: 2,0 s (filas 1,6 s + motor 0,4 s; con mezcla vectorizada en R2 baja a menos de 1 s). La paridad calcula sus votos una sola vez (4,2 s) y los deja en caché. Indicador "Calculando…" en pantalla. |
| D5 | Datos antiguos | Tabla `runs` nueva. `backtests` y todo lo demás quedan en disco **sin mostrarse**. Consecuencia: las corridas históricas ya guardadas dejan de verse. |
| D6 | Visual | Puerta R8: no se rediseña sin tu dirección. |
| D7 | Borrar corridas | Incluido (con confirmación). No estaba en el resumen; sin esto la lista solo crece. |
| D8 | Ajustes | Almacenamiento y cuota, historial e importación, huellas. Se retiran reglas globales y acceso para agentes. |
| D9 | Base de datos | Solo migraciones aditivas; ninguna destructiva. |
| D10 | Cobertura | Entero de 1 a 50 para rankings y paridad. |
| D11 | Topes de la traza | **Revisado en R0.** Con límite de 12 sorteos habrá ~5.400 sesiones y hasta 65.235 apuestas (solo 65.235 de los 105.426 sorteos tienen ranking). Los topes viejos (1.000 sesiones / 10.000 apuestas / 2 MiB) truncarían casi todo. Nuevo diseño de `runs`: el **resumen de todas las sesiones se guarda siempre** (hasta 50.000) y las apuestas se guardan completas hasta 250.000 apuestas / 32 MiB, en columna aparte para que la lista no cargue la traza. Si se superan, se trunca por sesiones enteras y la interfaz lo dice. |
| D12 | Valores precargados | Tu ejemplo (3 posiciones, 60/10/5, apuesta mínima RD$1, mezcla transición 60 % + fríos 40 %, cobertura 10, capital RD$2.000, meta RD$2.800); la duración máxima queda vacía. |
| D13 | Rentabilidad | **Neto total** = pagado − apostado en toda la ventana (incluye la cola incompleta); **retorno** = neto total ÷ total apostado. Son métricas descriptivas del historial, no probabilidades. |

## 6. Trazabilidad de las asunciones

| Código | Cubierto por |
|---|---|
| A1, A2 | R5, R6, R7 (una sola herramienta; retiro de modos) |
| A3 | R5 (advertencia fija en resultado y formulario) |
| F1 | R5 formulario, R4 (reglas guardadas dentro de cada corrida), R7 (sin reglas globales), D1 |
| F2, F3 | R1, R2 (mezcla, paridad aparte, apuesta mínima, sin azar ni políticas) |
| F4, F5 | R1 (meta, quiebra, límite opcional, saldo final cuenta), D3 |
| F6 | R1 (capital inicial en cada sesión, encadenado, cola incompleta) |
| F7 | R2, R5 (ventana opcional) |
| F8 | R4, R5 (repetir con cambios crea corrida nueva) |
| D1, D2 | R3, R4 (reglas y huella dentro de la corrida, importación en un paso) |
| U1–U4 | R5 |
| NF1 | R7 (sin agentes), sin cuentas |
| NF2 | R4/D4 |
| T1 | D5, D9, R7 |
| T2 | R8 |

## 7. Verificación

Entorno: intérprete `webapp\backend\.venv\Scripts\python.exe`; frontend en `webapp/frontend`.
- Backend: `python -m pytest -q` y `python -m ruff check .` (conteos comparados con R0; los tests retirados se listan en el ledger).
- Frontend: `npm.cmd run test -- --run` (presupuesto ≥ 300 s), `npm.cmd run typecheck`, `npm.cmd run build`.
- **Aceptación con datos reales y aislados**: arrancar el backend con `LABORATORIO_DATA_DIR` temporal y puerto propio (nunca 5173 ni los datos del usuario), crear por API la corrida del ejemplo y comprobar contra el motor viejo (`run_backtest`) en el caso equivalente; importar un historial sintético con sorteos nuevos y comprobar rechazo de conflictos, activación y aviso de "sin ranking".
- Navegador (Playwright instalado, puerto propio, API real sobre datos temporales): lista vacía → crear → resultado → repetir con cambios → borrar; Ajustes e importación; 390 px y 1440 px; teclado; movimiento reducido emulado; cero peticiones externas.
- Revisión independiente de integridad de tests: sin `.skip`/`.todo`, sin aserciones debilitadas, cada test retirado mapeado a una función retirada.
- Diferencia de `git diff` revisada: sin cambios en el esquema ni en las migraciones existentes.

## 8. Riesgos

- Rendimiento de la mezcla (`blend_order` por sorteo) sobre ~105 mil sorteos: se mide en R0 antes de decidir D4.
- Detalle parcial frecuente (D11): puede decepcionar si se espera ver todas las apuestas.
- Los sorteos nuevos sin ranking limitan lo que la importación aporta (D2): es la mayor diferencia entre lo pedido y lo posible sin un generador de rankings.
- Volumen de borrado en R6/R7 (≈ dos tercios del código): se hace por unidades pequeñas con el grafo de referencias; cada commit debe mantener las pruebas verdes. Si el cambio acumulado supera ~400 líneas por revisión, se divide en PRs encadenados.
- Pérdida de visibilidad de datos antiguos (D5).

## 9. Fuera de alcance

Generar rankings nuevos, Monte Carlo, apuestas reales, predicción, exportación, comparación entre corridas, bibliotecas de estrategias, cuentas de usuario, despliegue y cualquier push, PR o merge sin pedido explícito.

## 10. Orden y dependencias

R0 → R1 → R2 → R3 → R4 → R5 → R6 → R7 → R8 → R9. R6 y R7 son destructivos y exigen que R1–R5 estén verificados. R8 espera tu dirección visual y puede ejecutarse en paralelo conceptual, nunca antes de R5.
