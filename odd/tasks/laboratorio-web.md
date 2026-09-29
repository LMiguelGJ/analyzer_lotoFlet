# Laboratorio web local — plan ODD

## Alcance y autorización

Objetivo: explorar Q80 histórico en navegador con motor Python, sin apuestas ni predicción. Fuente: `especificaciones-laboratorio-web.md`. **Ejecución del plan autorizada por el usuario (2026-09-28)**, empezando por LW01; ante dudas, preguntar. Siguen requiriendo autorización específica: instalaciones, cambios en zonas protegidas, commits y push. Un escritor; dividir unidades >400 líneas sin implicar commits.

Motor: `main/quiniela_sim.py`, `main/quiniela_compare.py`, `simuladores/runner.py` y 14 ejecutables de referencia; el scout no encontró scaffold web, manifiestos web ni lanzador. Reverificar al ejecutar. Proteger JSON/NPZ, `repo_ref/`, `lagacy_loto/`, `simuladores/` y resultados: no modificarlos. Rama `stage` verificada; los trackers anteriores fueron archivados por el usuario en `odd/tasks-08-09-2026/` (commit `e93a373`), y el submódulo `lottery-predictability-monte-carlo` borrado: preservar, no restaurar. Reverificar entorno/estado antes de instalar/ejecutar. Rutas siguientes: **propuestas**, no permisos.

MVP local sin cuentas: FastAPI + React/TypeScript/Vite/Tailwind + SQLite, loopback, frontend servido por backend, Node solo para compilar/desarrollar; `iniciar-laboratorio.bat` abre/detiene sin servicio/instalador. SQLite **propuesto** en `%LOCALAPPDATA%` fuera del repo/OneDrive: validar permisos; no asumir backups. Versiones, aislamiento y umbrales pendientes; sin prometer tiempos/capacidad.

Q80 fijo: 00–99, cinco posiciones repetibles, premios 80/8/4/2/1, pago acumulado o mejor. Trece rankings; azar/par-impar separados. Mezcla: puesto 1→100 puntos, 100→1, suma ponderada con porcentajes=100; **no probabilidades**. Empate **entre números**, no métodos: proponer 00–99 ascendente en LW01, sin futuro. Azar semilla+sorteo: permutación 100/prefijos anidados independiente del orden. Par/impar: voto causal 27, cobertura 50 sin subconjuntos inventados. Coberturas 1/5/10/20/25/30/40/50; plana/escalera/audaz según motor, DOP enteros ≥RD$1/número sin exceder saldo. Meta = saldo final; validar capital/meta. Warmup previo a inicio con ranking; huecos sin apuesta consumen reloj. Sorteo `>= inicio + minutos` excluido; liquidar apuesta previa; con dos límites, primero. Desenlaces: meta, quiebre (próxima apuesta no financiable), límite, historial agotado.

Sesión 1 o comparación hasta 5, condiciones comunes. Cola serial con UI utilizable y cancelación entre pasos: conservar terminadas; activa no completa; restantes no ejecutadas. Cerrar navegador no para servidor. Reinicio: activa interrumpida sin reanudar, pendientes guardados solo inicio manual. Snapshots inmutables consultables sin recálculo. Cuota inicial configurable 5 GB distinta de disco libre y SQLite/WAL/temporales: margen/error seguro, sin purga ni compactación automática. Históricos investigados ≠ validación independiente de rentabilidad; distinguir datos artificiales si se mencionan, sin Monte Carlo UI. Sin importación/exportación, retraining, juegos nuevos, cuentas ni remoto.

## Preparación, hitos y decisiones por resolver

Problema: los simuladores de consola no ofrecen sesiones web persistentes y cancelables. Este plan agrega una capa local sin duplicar la liquidación financiera ni presentar el historial investigado como evidencia de rentabilidad.

LW01 debe preparar también los manifiestos propuestos `webapp/backend/pyproject.toml`, `webapp/frontend/package.json`, lockfile, `tsconfig.json`, `vite.config.ts`, `index.html` y configuración de pytest/Vitest/Testing Library/Playwright antes de las pruebas que los requieren. Solo generar configuración bajo autorización de ejecución; instalar dependencias requiere autorización específica. Fijar versiones compatibles comprobadas, no asumir versiones por memoria. LW08 completa el arranque React y LW16 valida la distribución, no inicia el scaffold por primera vez.

Contratos HTTP a cerrar en LW01 e implementar/probar en LW07: `/api/health`, `/api/catalog` (métodos, sorteos iniciales disponibles, juego y fuentes), `/api/configurations` y `/{id}` (CRUD), `/api/experiments` y `/{id}` (crear/listar/consultar/eliminar), `/{id}/configurations/{configurationId}/bets` (paginación) y `/results`, `/{id}/cancel`, `/api/queue` y `/{id}/start` (pendientes tras reinicio), `/api/settings` y `/api/storage`. Son rutas propuestas: fijar verbos, respuestas, errores, filtros y actualización de estado antes de integrar la UI. Los borrados de experimentos activos deben rechazarse o exigir cancelación previa confirmada; no borrar mientras escribe el worker. Validar origen/Host, paths e IDs incluso en loopback.

Elegir en LW01 el aislamiento del worker de cálculo y el mecanismo de actualización de UI (polling o eventos), demostrando cancelación entre pasos y servidor responsivo. Fijar contrato de estados por experimento y configuración, semilla/rango/generador versionado, timestamps históricos, precisión de pesos y prioridad de desempate. Resolver cuota en bytes, margen de escritura, contabilización SQLite/WAL y registro seguro del error cuando el disco está lleno, sin prometer persistir un error donde ya no se puede escribir.

**Hallazgo del verificador:** `main/test_simuladores.py` y rutas por defecto del motor apuntan a ubicaciones inexistentes bajo `main/`. LW01 debe reproducir/documentar el problema y proponer una corrección acotada o adaptación de rutas; no dar por sanas las 14 referencias. Si requiere cambios fuera de las superficies propuestas, obtener autorización antes. LW17 exige ejecutar las 14 regresiones antes de declarar completo el MVP: una referencia rota queda como bloqueo explícito, no como prueba omitida aceptada.

**LW01 — evidencia inicial (2026-09-28):** rama `stage`; Git solo muestra la eliminación ajena del submódulo. Python 3.14.3 con FastAPI 0.135.1, Uvicorn 0.42.0, Pydantic 2.12.5, pytest 9.1.1, httpx 0.28.1, NumPy 2.4.4 y Ruff ya instalados; SQLite 3.50.4; Node 24.14.0 y npm 11.9.0. No existe `webapp/`. Reproducido el bloqueo: `simuladores/transicion_1_audaz/ejecutar.py` falla con `ModuleNotFoundError: No module named 'quiniela_compare'`. Causa: el motor se movió a `main/`, pero `main/quiniela_sim.py` (líneas 35 y 487/514) y `main/quiniela_compare.py` (246–249) resuelven `repo_ref`, JSON y NPZ respecto de `main/`; `simuladores/runner.py` no agrega `main/` al path y `main/test_simuladores.py` fija `ROOT` en `main/`. Corrección propuesta: ~6 líneas de rutas, sin cambiar cálculos, validada con las 14 referencias. **Pendiente de autorización del usuario** para editar `main/` y `simuladores/runner.py`. Instalar dependencias del frontend también requiere autorización específica.

## Arquitectura aprobada

El usuario aprobó la estructura documentada en `especificaciones-laboratorio-web.md`, sección «Arquitectura y estructura del proyecto» ([AR1]–[AR8]). Reemplaza las rutas planas propuestas originalmente. Resumen de capas:

```text
webapp/backend/laboratorio/  app.py · settings.py
  domain/   contracts.py · selection.py · session.py      (reglas puras)
  engine/   adapter.py                                     (único acceso a main/ y repo_ref/)
  storage/  database.py · repository.py · quota.py · migrations/0001_initial.sql
  jobs/     queue.py · worker.py                           (proceso de cálculo aislado)
  api/      catalog.py · experiments.py · configurations.py · queue.py · settings.py
webapp/backend/tests/        un archivo de pruebas por módulo
webapp/frontend/src/         main.tsx · App.tsx · api/ · styles/tokens.css
  components/  Shell · QueueDrawer · ConfirmDialog · DataTable · BalanceChart · StatusLabel
  pages/       experiments/ · new-experiment/ · configurations/ · settings/
%LOCALAPPDATA%\LaboratorioQuiniela\  laboratorio.db · logs/  (fuera del repo y de OneDrive)
```

Reglas: el navegador no calcula; solo `engine/adapter.py` importa el motor; el cálculo corre en proceso aparte; `domain/` no depende de HTTP ni SQLite. Abreviaturas usadas abajo: `B/` = `webapp/backend/laboratorio/`, `T/` = `webapp/backend/tests/`, `F/` = `webapp/frontend/src/`.

Hitos: H1 contratos y harness (LW01); H2 primera sesión real persistida mediante API (LW02–07); H3 recorrido web completo crear→calcular→consultar (LW08–11,15); H4 seis pantallas y lanzador (LW12–16); H5 aceptación integral (LW17–18). Son hitos de evidencia, no fechas prometidas. Cada tarea registra comandos, RED/GREEN cuando aplique, limitaciones, revisión independiente y resultado; no basta que el código exista. Antes de retomar, reconciliar este archivo con Engram `odd/laboratorio-web/tasks`.

## Tareas (todas pendientes)

Rutas propuestas; tests vecinos. Conducta determinista: RED/GREEN y alternativos; texto pasivo sin RED. Aceptación pendiente.

- [ ] **LW01 Contratos/entorno** (dep. —). `B/domain/contracts.py`, `B/settings.py`, `B/engine/adapter.py`, `T/test_contracts.py`, `T/test_adapter.py`, `webapp/backend/pyproject.toml`, `webapp/README.md`. Inspeccionar motor/datos/14 refs, versiones, LOCALAPPDATA; fijar IDs, empate, fechas, límites y adaptación necesaria. RED/GREEN: 1–5, warmup, deadline, inválidos. Si exige editar `main/quiniela_sim.py`/`main/quiniela_compare.py`, ampliar permiso primero.
- [ ] **LW02 Selectores** (LW01). `B/domain/selection.py`, `T/test_selection.py`. Rankings 13 y pesos=100; azar semilla+sorteo/prefijos, par/impar causal 50. RED/GREEN: pesos inválidos, empates 00–99, sin fuga futura, orden invariante.
- [ ] **LW03 Sesión** (LW01–02). `B/domain/session.py`, `B/engine/adapter.py`, `T/test_session.py`; motor solo con permiso ampliado. Reusar finanzas Python. RED/GREEN: acumulado/mejor, entero/solvencia, meta/quiebre, huecos, warmup, ambos límites, igualdad temporal y liquidación.
- [ ] **LW04 Persistencia** (LW01, LW03). `B/storage/database.py`, `B/storage/repository.py`, `B/storage/migrations/0001_initial.sql`, `T/test_storage.py`. SQLite versionado: parámetros/fuente/hash/código/semilla/apuestas, estados/cierre transaccional. RED/GREEN: consulta sin recálculo, snapshots inmutables, borrado de plantilla conserva resultados, parcial no completo, migración.
- [ ] **LW05 Cola/reinicio** (LW03–04). `B/jobs/queue.py`, `B/jobs/worker.py`, `T/test_queue.py`. Un experimento/comparación por vez; validar aislamiento, respuesta y cancelación entre pasos. RED/GREEN: conservar finalizadas al cancelar, marcar restantes; navegador cerrado, reinicio interrumpe activa y deja pendientes manuales sin autorun.
- [ ] **LW06 Cuota/disco** (LW04–05). `B/storage/quota.py`, `T/test_quota.py`. 5 GB configurable, margen WAL/temporales y disco separado. RED/GREEN: umbrales/bloqueo, fallo de escritura con estado explícito/finalizados protegidos; no borrar/compactar.
- [ ] **LW07 API** (LW01, LW04–06). `B/app.py`, `B/api/catalog.py`, `B/api/experiments.py`, `B/api/configurations.py`, `B/api/queue.py`, `B/api/settings.py`, `T/test_api.py`. FastAPI loopback: catálogo/plantillas/experimentos/cola/cuota/estado; validar y confirmar borrado, definir defensa CSRF/origen. RED/GREEN HTTP: payloads maliciosos, concurrencia, borrado, bind no remoto.
- [ ] **LW08 Shell/tokens** (LW01). `F/main.tsx`, `F/App.tsx`, `F/api/`, `F/styles/tokens.css`, `F/components/Shell.tsx`, `F/components/StatusLabel.tsx`, `F/components/ConfirmDialog.tsx`, tests vecinos. Tema oscuro, tipos/grilla, sidebar/cabecera/foco sin marca pi.dev. Tests teclado, ~800/1100px, zoom 200%, medir contraste.
- [ ] **LW09 Asistente** (LW02, LW07–08). `F/pages/new-experiment/` (asistente y editor de estrategia reutilizable; tests incluidos). Tres pasos, resumen adaptable, condiciones comunes, 1–5 estrategias, pesos/plantillas, errores inline y salida avisada. RED/GREEN: par/impar 50, pesos/meta/fecha inválidos, mezcla 60/40 K10 límite 12, formulario sucio sin cancelar cola.
- [ ] **LW10 Listado** (LW07–08). `F/pages/experiments/` (listado), `F/components/DataTable.tsx`, tests vecinos. Vista inicial, búsqueda/orden/abrir/usar base/borrar confirmado; activo discreto. RED/GREEN: vacío, carga, sin coincidencia, desconexión, error y foco del diálogo.
- [ ] **LW11 Detalle/replay** (LW03–04, LW07–08). `F/pages/experiments/` (detalle y replay), `F/components/BalanceChart.tsx`, tests vecinos. Métricas, tabla paginada (cinco posiciones), gráfico/meta, parámetros, anterior/play/pausa/siguiente/velocidad visual. RED/GREEN: 00/DOP, estado ≠ desenlace, URL estable, pausa sin recálculo.
- [ ] **LW12 Comparación** (LW07–08, LW11). `F/pages/experiments/` (comparación), `F/components/BalanceChart.tsx`, tests vecinos. Tabla y líneas temporales hasta fin propio, etiquetas+patrones, toggle y enlace. RED/GREEN: cancelada N/M (M solicitado, no 5), 2/2 completa, faltantes con guion, sin ganador/probabilidad/exportación.
- [ ] **LW13 Plantillas** (LW04, LW07, LW09). `F/pages/configurations/` (reutiliza el editor de `F/pages/new-experiment/`; tests incluidos). Buscar/filtrar/crear/usar/editar/borrar confirmado con editor común. RED/GREEN: snapshots conservados, precarga, inválidas rechazadas.
- [ ] **LW14 Ajustes** (LW06–08). `F/pages/settings/` (tests incluidos). Cuota/uso/disco/SQLite separados, advertencias, fuente/hash/código solo lectura, conexión/cierre. RED/GREEN: cuota válida, sin prometer espacio recuperable ni importación/compactación.
- [ ] **LW15 Cola UI** (LW05, LW07–08). `F/components/QueueDrawer.tsx` (tests incluidos). Drawer serial, inspección/cancelación confirmada, inicio manual tras reinicio y reconexión autoritativa. RED/GREEN: desconexión sin afirmar parada, error inline, Escape/foco atrapado/retorno, no reanudar activa.
- [ ] **LW16 Windows/build** (LW07–08, LW15). `iniciar-laboratorio.bat`, `B/app.py`, `B/settings.py`, `webapp/frontend/vite.config.ts`, `T/test_app.py`. Doble clic, backend sirve build y lanzador detiene sin servicio. Tests: rutas con espacios, puerto ocupado, build ausente, loopback/reinicio; sin instalar ahora.
- [ ] **LW17 Regresión/mediciones** (LW02–07, LW09–16). `T/`, `F/**/*.test.tsx`, `webapp/README.md`. Contrastar 14 refs **si disponibles**, sin tocarlas; probar API, disco/cuota, cancelación, UI/recursos. RED/GREEN de defectos; registrar comandos/mediciones/faltantes, sin inventar rendimiento.
- [ ] **LW18 Aceptación/guía** (LW08–17). `webapp/README.md`, `F/styles/tokens.css`, componentes puntuales en `F/` solo ante hallazgo. Capturas reales; WCAG AA 4.5:1 texto/3:1 controles medidos, teclado/foco, zoom 200%, responsive, reduced motion, seis pantallas/estados. Guía en español; tests ante correcciones, sin RED para texto.

## Trazabilidad integral

Rangos inclusivos; FUT01–03 diferidos, no autorizados.

| IDs | Tareas / significado |
| --- | --- |
| A1–A3 | LW01,03,17: histórico Q80/fuentes actuales intactas. |
| A4–A5 | FUT01: juegos/JSON propios, importación y rankings compatibles. |
| A6 | FUT02: evaluación masiva y validación separada. |
| A7 | FUT03: remoto/cuentas. |
| A8 | LW09,17: mezcla 60/40 K10 y 12 apuestas Q80; FUT01: tres posiciones, pagos 60/10/5, JSON propio. |
| P1 | LW07,16: local personal sin cuentas. |
| F1–F4 | LW01–02,09: selección, pesos/puntos/empates/coberturas. |
| F5–F6 | LW03,07,09: apuestas, capital y meta final. |
| F7–F11 | LW01,03,05,09: comparación, inicio, huecos, límites/tiempo, desenlaces. |
| F12 | LW11: replay visual. |
| F13–F15 | LW05,15: cancelación y retención sin reanudar. |
| F16–F18 | LW02,09: semilla y permutación por sorteo. |
| D1–D3 | LW04–05: snapshots, consulta, interrupción. |
| D4–D5 | LW04,07,10,13: borrado confirmado y retención. |
| D6–D8 | LW06,14,17: presupuesto, bloqueo, fallo seguro. |
| U1–U2 | LW10–12: listado, detalle y comparación. |
| U3–U4 | LW08,18: español/DOP, visual y accesibilidad. |
| U5–U6 | LW08,12,18: referencia sin servicios ajenos; sin exportación. |
| NF1–NF3 | LW02,05,17: cola, determinismo, mediciones. |
| NF4 | LW11–12,18: límites históricos/artificiales, no rentabilidad inferida. |
| NF5–NF8 | LW05,15–16: navegador, detener, interrumpir, pendientes manuales. |
| NF9 | LW17: respuesta/capacidad medidas. |
| T1–T2 | LW01,03–04,17: motor Python/14 refs, arquitectura. |
| T3–T5 | LW07–08,16: lanzador, stack y frontend servido. |
| T6 | LW06,14,17: margen/disco. |
| UX1–UX4 | LW08,18: referencia/tokens/contraste/tema. |
| UX5–UX11 | LW08,18: tipos, espaciado, bordes, controles, grilla. |
| UX12–UX19 | LW08–09,18: layout, tablas, responsive, movimiento. |
| UX20–UX24 | LW10: listado y estados. |
| UX25–UX30 | LW09: asistente completo. |
| UX31–UX37 | LW11: detalle, estados/replay/apuestas. |
| UX38–UX41 | LW12: comparación y N/M. |
| UX42–UX43 | LW13: biblioteca y retención. |
| UX44–UX46 | LW14: ajustes. |
| UX47–UX52 | LW15,18: drawer, reconexión, confirmaciones. |
| UX53–UX54 | LW08–09,18: resumen adaptable/jerarquía visual. |
| AR1–AR2 | LW01,03,17: cálculo solo en Python; adaptador único del motor. |
| AR3 | LW05,17: proceso de cálculo aislado, UI responsiva y cancelación. |
| AR4 | LW01–03: dominio puro probado sin HTTP ni SQLite. |
| AR5 | LW01,17: `webapp/` aislada; investigación existente sin reorganizar. |
| AR6 | LW01,04,06: SQLite en `%LOCALAPPDATA%`, fuera de OneDrive. |
| AR7 | LW09,13: editor de estrategia único reutilizado. |
| AR8 | Todas: subdivisión interna permitida sin cambiar capas; cambios documentados. |

## Evidencia y siguiente paso

Planificación completada: scout del código y lectura de la especificación; verificador independiente comprobó cobertura de los 110 IDs, 18 tareas pendientes y dependencias sin ciclos. Se incorporaron sus hallazgos sobre scaffold temprano, contratos API y rutas rotas de referencias. No se ejecutaron pruebas funcionales, build ni instalaciones: no hay implementación web en esta tarea. Las correcciones documentales posteriores requieren readback; todos los criterios funcionales/visuales siguen pendientes.

Arquitectura aprobada e incorporada a especificación y plan. LW01 iniciado: entorno inspeccionado y bloqueo de referencias reproducido; sin código web escrito.

**Estado:** implementación 0/18; LW01 en curso, bloqueado por autorización para corregir rutas del motor. Próximo paso: obtener autorización para corregir rutas del motor, validar las 14 referencias y continuar con contratos y adaptador. FUT01–03 son backlog diferido, no tareas autorizadas. Sin commits ni push; conservar cambios ajenos.
