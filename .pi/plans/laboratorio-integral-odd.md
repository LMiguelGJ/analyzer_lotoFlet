# Plan: laboratorio integral mediante ODD

## Summary

Evolucionar la aplicación local existente hacia un laboratorio extensible de estrategias, simulación histórica, validación y auditoría. Este plan autoriza únicamente planificación: su ejecución necesita aprobación explícita; no adopta SDD ni autoriza instalaciones, conexiones externas, commits, publicación o ejecución de extensiones.

La entrega será incremental. No se promete un catálogo de todas las estrategias del mundo. Se entregará un catálogo aprobado y trazable, un constructor visual y una interfaz de extensiones.

## Current State Analysis

Exploración de planificación realizada por `gentle-ai-explore`, lectura completa de cinco archivos: `webapp/backend/laboratorio/domain/contracts.py`, `domain/session.py`, `api/queue.py`, `webapp/frontend/package.json` y `webapp/README.md`. Se mapearon además las superficies siguientes, sin ejecutar pruebas ni modificar fuentes:

- `webapp/backend/laboratorio/domain/contracts.py`: juego Quiniela 80 fijo, cinco posiciones, premios 80/8/4/2/1, 13 rankings, coberturas y contratos de configuración.
- `webapp/backend/laboratorio/domain/session.py`: cálculo financiero, liquidación y reglas de apuesta ligadas al juego fijo; rechazo de capital inicial insuficiente dentro de la ejecución.
- `webapp/backend/laboratorio/engine/adapter.py`: histórico y rankings congelados; filas de rankings como permutaciones de 100 números.
- `webapp/backend/laboratorio/jobs/queue.py`, `jobs/worker.py`: cola serial y procesos de cálculo. Un proceso separado no constituye un sandbox de seguridad.
- `webapp/backend/laboratorio/storage/repository.py`, `storage/database.py`: SQLite y snapshots de experimentos/resultados.
- `webapp/backend/laboratorio/api/{catalog,experiments,configurations,queue}.py`: catálogo, experimentos, configuraciones y control de trabajos.
- `webapp/frontend/src/components/StrategyEditor.tsx`, `pages/new-experiment/`, `pages/experiments/`: editor, asistente, detalle, comparación y replay.
- `repo_ref/{simuladores,chance_rank,strategy_tests,rng_audit}/`, `repo_ref/quiniela_compare.py`, `repo_ref/quiniela_sim.py` y los informes en `docs/`: fuentes de requisitos y resultados de referencia, no dependencias ejecutables de producción.

La revisión Judgment Day se realizó sobre `1441337`; registro Engram #5439. La equivalencia reportada se limita a las reglas inspeccionadas y al oráculo existente: 141 casos, no cobertura universal. No se ha vuelto a verificar HEAD o estado Git durante este plan. Antes de ejecutar se reconciliarán; preservar la eliminación ajena del gitlink `lottery-predictability-monte-carlo` y cualquier modificación previa de `odd/tasks/claridad-interfaz-80-20.md`.

## Assumptions & Decisions

### Decisiones acordadas

1. ODD, aplicación personal/local y evolución del stack actual; cálculos financieros exclusivamente en backend. No plataforma pública ni multiusuario.
2. Perfiles de juego versionados: universo, posiciones, repeticiones, premios por posición y apuesta mínima configurables. Cobertura y posiciones son conceptos diferentes.
3. Liquidación explícita: suma, mayor premio o extensión. No seleccionar silenciosamente una modalidad.
4. Catálogo + constructor visual declarativo + extensiones de código. No convertir automáticamente código arbitrario en bloques.
5. Extensiones instaladas explícitamente, sin ejecución durante importación, permisos restringidos y aislamiento real. Si no puede demostrarse, ejecución de terceros deshabilitada.
6. Sesiones individuales/consecutivas, comparaciones, barridos, validación temporal, estabilidad, Monte Carlo, rankings y auditoría.
7. Límites independientes de sorteos transcurridos, sorteos apostados, fecha/hora final y duración simulada; finalizar al primer límite activado. Tiempo de cómputo es otro límite operativo.
8. Importación CSV/JSON, conectores aprobados y programación opcional; conservación de las versiones usadas. Nunca inventar posiciones históricas faltantes.
9. Interfaz en español, accesible, adaptable, asistente y mesa avanzada sobre el mismo modelo; plantillas y bloques.
10. Cola, prioridades, recursos configurables, estimaciones orientativas, confirmación sobre umbrales y pausa/reanudación solo con soporte explícito.
11. Todos los hallazgos de Judgment Day se convierten en requisitos trazables, sin elevar observaciones a fallos demostrados ni afirmar revisión nativa aprobada.

### Puertas que deben resolverse antes de sus dependientes

Este es un plan integral con puertas de decisión, no una autorización para que el ejecutor invente decisiones técnicas pendientes. La primera etapa debe producir contratos completos; ninguna etapa bloqueada puede implementarse.

- **G1 — catálogo:** investigación externa con fuentes y aprobación humana del inventario ampliado. Separar selección, entrada/salida, apuesta, liquidación, preset y protocolo estadístico.
- **G2 — dinero y juego:** fijar unidad/precisión, redondeo, multiplicador bruto o premio neto, devolución de apuesta, granularidad y límites de configuración; reglas de compatibilidad y cronología de cierre. Preservar exactamente la semántica de los perfiles heredados. Personalizable no significa tamaño infinito ni ejecución sin validación.
- **G3 — extensiones:** evaluar aislamiento disponible en Windows, amenaza, permisos y dependencia adicional; aprobación antes de instalar infraestructura. Prohibido sustituir aislamiento por `spawn`, timeout o una lista de importaciones.
- **G4 — fuentes:** identificar conectores reales, reglas de origen, zona horaria, duplicados/correcciones y política aprobada para incorporaciones programadas. Sin scraping ni credenciales implícitos.
- **G5 — estadística:** contratos de splits, reinicios, censura, semillas, intervalos y correcciones múltiples; impedir fuga temporal. Un histórico ya investigado no se transforma retrospectivamente en validación independiente.
- **G6 — caso de aceptación:** elegir staking y liquidación del ejemplo antes de ejecutarlo. Mínimo RD$1 no implica apuesta fija RD$1.

## Proposed Changes

Los directorios y archivos citados arriba existen; los documentos y módulos nuevos mencionados a continuación son propuestas, no archivos encontrados. Mantener unidades revisables, cada una con pruebas y documentación. No convertir una etapa amplia en un único cambio de miles de líneas.

### ODD-00 — Contratos, catálogo e inventario de aceptación

**Nuevos documentos propuestos:** `docs/especificaciones-laboratorio-integral.md`, `docs/catalogo-estrategias.md`, `docs/matriz-cobertura-laboratorio.md`.

- Consolidar todos los requisitos A/P/F/D/U/NF/T/E de la elicitación y JD-01–05; asignar IDs estables y pruebas observables.
- Inventariar los 13 sistemas: `freq_hist`, `freq_recent`, `decay`, `cold`, `notebook`, `mix`, `transition`, `carry`, `doubles`, `category`, `time`, `ensemble`, `select_interpretable`; además blend, random y parity.
- Documentar E1–E5, tímida/audaz, escalera histórica/configurable y E9 sin confundir auditorías E7/E8 con selectores.
- Presets: transicion_1_audaz, frios_1_audaz, selector_1_audaz, mezclas_1_audaz, ensemble_5_audaz, ensemble_10_audaz, ensemble_20_audaz, frios_25_escalera, mezclas_50_audaz, transicion_50_audaz, paridad_50_audaz, frios_50_escalera, paridad_50_escalera, paridad_50_plana.
- Investigar familias externas; documentar fuente, fórmula, parámetros, supuestos y evidencia, no supuesta rentabilidad. No trasladar fórmulas de Quiniela 80 a juegos arbitrarios sin derivación.
- Resolver G1/G2/G5 y registrar G3/G4/G6; pedir solo decisiones humanas genuinas. Si no se resuelven, bloquear dependientes y explicar qué falta.
- Aceptación: inventario aprobado, matriz requisito→unidad→prueba, contratos precisos y ningún requisito eliminado silenciosamente.

### ODD-01 — Correcciones acotadas y línea base

**Superficies:** `api/experiments.py`, `domain/session.py`, `jobs/queue.py`, `storage/repository.py`, `frontend/src/pages/new-experiment/model.ts`, pruebas correspondientes.

- JD-01: preflight autoritativo antes de persistir/encolar, con error por estrategia; reutilizar cálculo de apuesta para evitar divergencia de fórmulas.
- Validar apuestas dinámicas al ejecutarlas. Quiebre válido y error de configuración no son el mismo estado.
- Aislar errores particulares de configuraciones independientes; detener por errores compartidos de seguridad o integridad. Definir estado agregado sin representar ejecución parcial como completa.
- Ampliar pruebas de cobertura 20/30/40 y `best`; pruebas deterministas propias para azar y blend. No reemplazar/regenerar el oráculo congelado para que pase.
- Aceptación: entrada imposible no crea trabajo; un fallo particular no impide calcular estrategias independientes; regresiones originales conservadas.

### ODD-02 — Perfiles y snapshots versionados

**Superficies:** `domain/contracts.py`, `storage/{database,repository}.py`, `api/catalog.py`, `frontend/src/api/`, nuevas migraciones en estructura existente.

- Separar definición de juego de estrategia y condiciones; perfiles Quiniela 80, Original70 y ejemplo60/10/5 con procedencia.
- Snapshot inmutable de perfil, estrategia y versión ejecutable; migración que asigne semántica original a resultados existentes, sin recalcularlos.
- Validar cobertura/universo, premios, posiciones, repetición y compatibilidad con datos.
- Depende de G2. Aceptación: perfiles1/3/5 posiciones y otra cantidad válida; inválidos rechazados; históricos antiguos siguen legibles.

### ODD-03 — Datos, importación y procedencia

**Superficies:** `engine/adapter.py`, `settings.py`, `storage/`, `api/catalog.py`, frontend de selección de datos; nuevos módulos dentro del backend para importación.

- Separar adaptación heredada de fuentes genéricas; importar CSV/JSON con mapeo, preview, validación y promoción transaccional.
- Versionar fuentes y correcciones; guardar hashes, esquema, zona horaria y procedencia; distinguir artificial/histórico.
- JD-04: búsqueda directa por fecha/sorteo, paginación estable y validación de disponibilidad de rankings.
- Conectores/programación solo tras G4; no mutar snapshots en uso ni iniciar sincronizaciones no autorizadas.
- Aceptación: archivos malformados no contaminan datos; selección de fecha tardía sin cargas secuenciales; versión antigua reproducible tras actualización.

### ODD-04 — Motor configurable y registro de estrategias

**Superficies:** `domain/{contracts,selection,session}.py`, `engine/adapter.py`, `jobs/worker.py`, tests de dominio.

- Separar selección, decisión de entrada, cobertura, stake, liquidación y condiciones de cierre; registro con IDs/versiones y matriz de capacidades.
- Implementar estrategias heredadas conservando reglas; añadir familias aprobadas con parámetros documentados y estado causal.
- Límites independientes; ausencia de apuesta no consume límite de apuestas pero sí sorteo transcurrido. Definir desempates de cierres en G2.
- DSL declarativo validado, sin `eval`; presupuesto de complejidad. Rankings de100 números no sirven automáticamente para otro universo.
- Aceptación: paridad acotada del perfil heredado y casos manuales de juegos nuevos/repetidos/esperas; rechazar estrategias incompatibles en vez de adaptarlas silenciosamente.

### ODD-05 — Resultados completos y métricas

**Superficies:** `api/experiments.py`, `api/__init__.py`, `storage/repository.py`, `frontend/src/pages/experiments/{DetailPage,ComparisonPage}.tsx`, `components/{BalanceChart,ComparisonChart}.tsx`.

- JD-05: endpoint/consulta de trayectoria separado del replay tabular; vista completa con reducción declarada cuando haga falta, extremos preservados y acceso al detalle exacto.
- Mostrar wagered/paid y fórmulas backend de retorno, drawdown y métricas individuales. Definir unidades, cero denominador, nulos y resultados incompletos.
- Aceptación: curva no limitada a20apuestas, comparación no depende de cientos de clics; sin cálculos financieros duplicados en navegador.

### ODD-06 — Evaluación histórica masiva

**Superficies:** `domain/`, `jobs/{queue,worker}.py`, `storage/`, `api/experiments.py`, frontend experimentos.

- Protocolos explícitos de sesiones consecutivas, barridos de parámetros/fechas/semillas y comparaciones; cardinalidad calculada antes de ejecutar.
- Reinicios, colas censuradas, tasas, Wilson, neto medio, mediana/p90 y totales con denominadores documentados.
- Reproducir14presets y grillas bajo condiciones originales; verificar cardinalidad desde código de referencia, no fijar339 sin indicar modo/filtros.
- Aceptación: casos pequeños completamente verificables y ejecución de referencia registrada; ninguna extrapolación de éxito desde una sesión.

### ODD-07 — Validación temporal y estabilidad

**Superficies:** nuevos protocolos en backend, `repo_ref/chance_rank/walkforward.py` y `repo_ref/strategy_tests/` solo como referencia; UI de evaluación.

- Separar selección de parámetros de evaluación final; folds/versiones, warmup y procedencia por fila; ninguna observación futura llega a decisiones pasadas.
- Estabilidad por fechas/semillas, bootstrap con unidad correcta y correcciones múltiples según G5.
- Aceptación: tests de fuga temporal y reproducibilidad; datos reutilizados se etiquetan como tales, no como prueba ciega nueva.

### ODD-08 — Monte Carlo y controles

**Superficies:** nuevos generadores/protocolos dentro de backend, API y resultados; `repo_ref/quiniela_compare.py` como referencia.

- Generación compatible con universo, posiciones y repeticiones; semillas reproducibles independientes de orden/concurrencia.
- Baselines uniformes y controles sesgados conocidos, con comparación separada de históricos.
- Aceptación: configuraciones imposibles rechazadas; reproducibilidad serial/paralela y propiedades estadísticas evaluadas con tolerancias predefinidas, sin tests probabilísticos frágiles.

### ODD-09 — Rankings y auditorías

**Superficies:** módulos nuevos en backend, catálogo/API/UI; referencias `repo_ref/{chance_rank,rng_audit}/`.

- Recálculo versionado, parámetros de ventanas, posiciones soportadas y diagnósticos top-k/esperas/supervivencia.
- Auditorías aplicables al tipo/tamaño de datos; restricciones y correcciones múltiples visibles. No ejecutar una batería binaria sobre datos incompatibles sin transformación justificada.
- Aceptación: controles conocidos, causalidad y cachés ligados a versiones; ausencia de significancia no presentada como demostración de aleatoriedad.

### ODD-10 — Extensiones seguras

**Superficies:** subsistema nuevo de extensiones en backend, `jobs/worker.py` como integración, API y UI especializada.

- Antes de implementar: cerrar G3 mediante evidencia en Windows y consentimiento de dependencias. Sin solución demostrada, mantener función bloqueada, no marcarla terminada.
- Manifiesto declarativo, protocolo serializado, hash/versionado, límites, permisos y resultados validados; sin acceso directo a SQLite del host.
- Importación inerte: no ejecutar instaladores, imports o metadatos dinámicos de paquetes durante inspección.
- Aceptación adversarial: denegar lectura/escritura ajena, red, procesos no autorizados, agotamiento de recursos y escapes; invalidar salida malformada. Subproceso por sí solo no pasa esta etapa.

### ODD-11 — Recursos y operación recuperable

**Superficies:** `jobs/{queue,worker}.py`, `storage/`, `api/queue.py`, `frontend/src/components/QueueDrawer.tsx`, settings.

- Concurrencia acotada, cuotas, prioridades, estimaciones/confirmación y admisión global por lote; aplicar presupuestos desde que exista trabajo masivo, sin esperar esta etapa para proteger el equipo.
- Checkpoints solo para protocolos compatibles, validados contra versiones; pausa/reanudación no cambia resultados ni duplica apuestas. Extensiones sin soporte solo cancelan/reinician explícitamente.
- Aceptación: cancelación/crash/reinicio, recursos excedidos, cuota insuficiente y concurrencia reproducible; evitar promesas de RAM exacta sin enforcement disponible.

### ODD-12 — Constructor, asistente y mesa avanzada

**Superficies:** `StrategyEditor.tsx`, `pages/new-experiment/`, `pages/configurations/`, `pages/experiments/`, `App.tsx`, componentes y estilos existentes.

- Incorporar UI incrementalmente junto a cada etapa; esta unidad integra navegación, catálogo/plantillas, bloques y mesa avanzada sobre un único documento de configuración.
- Cargar Impeccable para trabajo UI. Mantener español, teclado/foco, errores por campo, confirmaciones, responsive y números exactos.
- Importar código no implica representación en bloques. Capacidades no soportadas visibles, no botones que aparenten funcionar.
- Aceptación: alternancia guiado/avanzado sin pérdida, casos largos/errores/vacíos, recorrido real en navegador y aceptación del usuario.

### ODD-13 — Aceptación integral y documentación honesta

**Superficies:** `webapp/README.md`, nuevos documentos de `docs/`, pruebas backend/frontend y evidencia de verificación.

- Matriz completa de requisitos/hallazgos, estado por familia y limitaciones; pruebas de migración y reapertura de experimentos anteriores.
- Caso usuario:00–99,3posiciones,repeticiones,60/10/5,mínimo1,blend transición60/fríos40,k10,capital2000,meta2800,12sorteos transcurridos. Elegir explícitamente staking/liquidación antes de ejecutarlo (G6).
- Separar reconstrucción histórica, validación nueva y simulación artificial; no prometer rentabilidad.
- Aceptación final exige todo requisito aprobado implementado/verificado o una exclusión posterior explícitamente aceptada. Una etapa terminada no cierra automáticamente el producto.

## Ejecución ODD y dependencias

- Antes de la primera escritura de implementación: reconciliar Git y memoria; crear `odd/tasks/laboratorio-integral.md` y espejo `odd/laboratorio-integral/tasks`, proyectar TODO. No crearlos durante este modo plan.
- Orden base:00→01→02→03→04→05→06→07→08→09;10 depende de03/04/G3;11 se integra desde06 y se cierra tras10;12 acompaña cada capacidad y se cierra después;13 cierra todo.
- Delegar exploración de4+archivos, escritores para cambios sustanciales y verificadores independientes. Escrituras secuenciales; subagentes con superficies permitidas acotadas.
- Verificar y actualizar evidencias por unidad. Revisión nativa según switch/consentimiento vigente; una inspección bloqueada no equivale a aprobación. No heredar aprobación del commit1441337.
- Unidades mayores de400líneas deben dividirse en cortes revisables. Recomendar PRs encadenados si luego se solicita publicación; no abrirlos automáticamente.
- No commits, push ni cambios destructivos sin autorización explícita. Mantener fuera todo cambio ajeno, usar staging selectivo si se autoriza entrega.

## Verification

Comandos existentes, NO ejecutados para este plan:

Desde `webapp/backend`:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -3 -B -m pytest tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 py -3 -B -m ruff check --no-cache .
```

Desde `webapp/frontend`:

```bash
npm test -- --run
npm run typecheck
npm run build
```

- Tests específicos antes de suite completa; seguir modo TDD configurado, no inventar evidencia RED/GREEN.
- Migraciones con datos anteriores, snapshots, dinero exacto, límites y repetidos.
- Oráculos originales inmutables más fixtures nuevos con origen/método registrados; invariantes para variantes sin equivalente.
- Integración API/cola/cancelación/checkpoints/cuotas; cada fallo y reintento registrado.
- Evidencia de aislamiento real y pruebas negativas de extensiones.
- Verificación de causalidad, reproducibilidad y denominadores estadísticos.
- Navegador real para fechas tardías, curva completa, UI guiada/avanzada y caso de usuario. No confundir resize con zoom ni tests unitarios con aceptación visual.
- Cierre por matriz de cobertura, no por conteo de tareas.

## Out of Scope

- Apuestas reales, pagos, conexión automática con casas de apuestas o promesas predictivas.
- Plataforma pública/multiusuario, infraestructura cloud y publicación automática.
- Catálogo universal exhaustivo; ejecución arbitraria sin aislamiento; compatibilidad automática de toda estrategia con todo juego.
- Alterar fuentes congeladas, referencias, oráculo original o cambios ajenos.

## Estado y aprobación

Fase1 explorada mediante scout; fase2 sin nuevas preguntas ahora: decisiones pendientes convertidas en puertas explícitas de ODD-00, no asumidas. Fase3 completada con este plan. Fase4 pendiente: esperar aprobación para comenzar ODD-00. No se implementó ni ejecutó prueba alguna. La especificación en docs todavía no existe por efecto de este plan.
