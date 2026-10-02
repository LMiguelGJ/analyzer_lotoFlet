# Plan ODD: producto local 80/20

> Plan solicitado mediante `plan-mode-trae`. Estado: listo para aprobación; implementación NO iniciada. Este archivo es el único artefacto de repositorio autorizado en esta etapa. Ejecución posterior por ODD, no SDD.

## Summary

Completar el recorrido local de una persona: cargar un historial, elegir o guardar una estrategia compuesta por bloques existentes, ejecutar una sesión y entender/comparar sus resultados. Exponer esas mismas operaciones mediante una API local documentada y protegida para agentes de IA; priorizar aceptación manual del usuario y comprobaciones automáticas mínimas en las fronteras críticas.

## Current State Analysis

- Base observada: rama `stage`, commit `6f1ef41`. Preservar la eliminación previa del gitlink `lottery-predictability-monte-carlo` y el cambio de `odd/tasks/claridad-interfaz-80-20.md`; no pertenecen a este plan.
- Stack existente: backend Python/FastAPI, almacenamiento SQLite/migraciones, cola y worker; frontend React/TypeScript/Vite. Reutilizarlo, sin instalaciones ni servicios adicionales.
- `chance_express_history.json`: 27.025.022 bytes, raíz `metadata` + `sorteos_por_fecha`. La metadata declara 105.426 sorteos; ese número debe contrastarse con la lectura efectiva, no tomarse como prueba de integridad.
- `webapp/backend/laboratorio/importing/records.py` y `api/imports.py`: importación genérica CSV/JSON plano con 2 MiB, 10.000 filas, transporte base64, vista previa y promoción revalidada. Esto no sirve directamente para el historial real. Conservar su compatibilidad, no aumentar indiscriminadamente sus límites.
- `importing/datasets.py`, `api/datasets.py` y `storage/repository.py`: identidad de fuente y dataset, perfil asociado, promoción y cuota. `pages/new-experiment/ProfileExperimentPage.tsx` ya consulta datasets y permite sesiones con perfiles; no confundir las advertencias obsoletas de `/datos` con ausencia global de ejecución.
- `settings.py` y `engine/adapter.py`: fuentes históricas/rankings congeladas por hash, filas `row_ids` y correspondencia cronológica. `domain/contracts.py` registra los sistemas archivados, incluidos `cold` y `transition`; no son algoritmos nuevos por inventar.
- `profile_capabilities.py`, `profile_request*.py`, `profile_result*.py`, `profile_session.py` y `profile_staking.py`: capacidades y protocolos versionados. La composición con selecciones archivadas no está habilitada en la ruta de perfiles actual; requiere integración explícita, no cambiar etiquetas para fingir soporte.
- `jobs/queue.py`, `jobs/worker.py`, `api/experiments.py`: admisión, cola serial, cancelación, resultados y replay existentes. Preservar semántica de resultados antiguos y errores compartidos frente a errores propios de una corrida.
- `components/RunTrajectory.tsx`, `FinancialMetrics.tsx`, `BalanceChart.tsx`, `ComparisonChart.tsx` y páginas de detalle/comparación ya cubren trayectoria acotada y métricas del backend. Conectar/reutilizar; no reconstruir cálculos financieros en el navegador.
- Los tres README leídos en `repo_ref/simuladores/` definen presets concretos y requieren insumos compatibles. Se inspeccionará su runner/tests al implementar la paridad; no se ejecutó todavía ninguna reproducción real en esta planificación.
- `webapp/reports/` permanece local e ignorado. No publicar capturas, logs, credenciales, bases de datos ni fuentes de usuario por defecto.

## Assumptions & Decisions

### Alcance aprobado como entrada al plan

- **A1–A3:** aplicación local de una persona, sin venta/cuentas/multiusuario; recorrido humano y API para IA; tres presets, otros once diferidos; sin MCP.
- **F1–F2:** guardar composiciones de bloques existentes compatibles: selección, cobertura, apuesta y cierre. Nada de Python de terceros, `eval`, nueva DSL matemática ni promesas de compatibilidad universal.
- **F3–F4:** un inicio elegido y una sesión por estrategia. Igual historial, perfil, capital inicial y condiciones de cierre para la comparación; las reglas de selección/apuesta pueden diferir. Sin sesiones consecutivas, grillas, Monte Carlo ni estabilidad.
- **F5:** saldo, apostado, cobrado, neto, ROI, drawdown, causa de cierre y trayectoria con consulta exacta por apuesta. Mantener definiciones/escala del backend; denominador cero es N/A. Mostrar completado, incompleto o no disponible sin confundirlos.
- **D1–D3:** JSON anidado como formato principal, validación/vista previa/biblioteca reutilizable, archivo real completo sin recorte silencioso, CSV avanzado; perfiles, procedencia y snapshots versionados. Universo, posiciones, pagos y moneda pertenecen al perfil, no al formato ni al nombre Chance Express.
- **P1/P2:** IA autónoma para guardar estrategias y ejecutar dentro de límites compartidos con la UI, API local protegida por credencial; sin endpoints de archivos arbitrarios, shell, eliminación de historiales o modificación de seguridad por la IA.
- **NF1:** límites conservadores editables, tamaño de lote visible y cancelación. Valores finales medidos/documentados antes de aceptación; no garantías inventadas de RAM/tiempo.
- **U1–U3:** asistente historial → juego/capital → estrategia → revisión → ejecución/resultados; avanzado desplegable sin pérdida; UI española, escritorio principal, adaptación móvil, teclado, botones reconocibles y errores claros.
- **T1–T3/E1:** `paridad_50_plana`, `transicion_1_audaz`, `frios_25_escalera`; rankings compatibles, sin sustitución ni entrenamiento; paridad de sesiones individuales, no reproducción de tasas históricas agregadas; archivo real, interfaz/API, comparación y Judgment Day final, sin rentabilidad garantizada/certificaciones.

### Decisiones técnicas acotadas

1. Mantener los motores y módulos financieros existentes. Añadir adaptación de selección/ranking al camino de perfiles, no un segundo simulador ni ejecutar los launchers de referencia como producto.
2. No cambiar aceptación ni lectura de requests/resultados v1–v4. Añadir protocolo v5, explícito y cerrado, para las composiciones/selecciones necesarias y lotes de una sesión por estrategia; persistencia y dispatch deben reconocerlo sin reinterpretar datos antiguos.
3. Historial completo almacenado ≠ todas sus filas apostadas. La sesión empieza donde se eligió y termina por su regla o presupuesto explícito. No truncar el dataset a 10.000 filas para eludir el límite actual del motor.
4. Rankings archivados: verificar hashes esperados, orden/resultados/etiquetas del historial canónico y `row_ids`; el hash del dataset o una cadena de procedencia por sí solos no prueban correspondencia. Revalidar al admitir y al ejecutar. La selección de una fila no consulta su resultado objetivo.
5. Los presets reproducen sus variantes originales: no confundir audaz histórica con otra regla genérica, ni escalera Q80 cíclica con recuperación configurable/E5. Su perfil de referencia es 100 números, cinco posiciones, repetición y pagos 80/8/4/2/1, liquidación `all`; es un preset, no un límite de la aplicación. Capital/meta de referencia 2.000/2.800 se muestran y pueden confirmarse o editarse; no se aplican ocultamente a todo juego.
6. Para los presets archivados, conservar su política de filas evaluables y contexto previo. Inicio sin ranking, fuentes distintas o perfil incompatible: explicar/bloquear, nunca cambiar el inicio o inventar selecciones. Historiales nuevos siguen admitidos para bloques cuya compatibilidad pueda demostrarse sin esos rankings.
7. Estrategia guardada: ID, revisión, nombre, versión de definición, composición validada y hash canónico. Una edición genera revisión inmutable. La ejecución incorpora snapshot exacto; no depende de una biblioteca mutable durante el cálculo. Reutilizar normalización de nombres existente.
8. JSON principal por cuerpo binario/raw JSON con lectura acotada, no duplicarlo dentro de base64. Mantener endpoints antiguos del importador genérico. Validar antes de promover; raw y normalizado con hashes distintos. Fuente, zona y cantidades tomadas de metadata se muestran para confirmación; pagos no se deducen de ella. Metadata ausente o contradictoria produce campos/errores explícitos.
9. Como los datasets existentes están ligados a un perfil, la promoción definitiva ocurre después de validar/confirmar el perfil en el paso juego. El paso historial permite seleccionar/inspeccionar primero. Cambiar perfil no altera datasets ni resultados previos: requiere validación y snapshot compatible nuevo.
10. Usar un servicio compartido de validación/compilación/admisión para UI y API IA. No copiar el motor en un router de agentes ni agregar un proveedor de IA: cualquier agente cliente entrega el JSON documentado.
11. Credencial aleatoria persistida fuera del repositorio, bajo el directorio local de datos, nunca en estrategias, URLs, logs ni resultados. La interfaz local puede mostrarla/copiarla mediante un acceso restringido al mismo origen. La fachada IA exige `Authorization: Bearer`, además de conservar guardas Host/Origin; sin CORS permisivo ni apertura a la red. No exigir aprobación por corrida.
12. Punto inicial de medición, NO valores ya certificados: JSON principal hasta 32 MiB y 200.000 registros; hasta tres estrategias por lote, un worker activo, diez corridas pendientes en total; cierre por defecto a 1.000 apuestas o 10.000 sorteos transcurridos y presupuesto operativo de 120 segundos por corrida. Todos se muestran/editan en ajustes avanzados dentro de techos de admisión documentados. Calibrar con el archivo real y las tres sesiones antes de aceptar; no reducir para esconder truncaciones ni modificar requests antiguos retroactivamente. Límites operativos se distinguen de meta/quiebre y se congelan en cada solicitud. No se promete un hard-limit de RAM del sistema operativo.
13. No nuevas dependencias, downloads, entrenamiento, interfaces de plugins, exportadores ni rediseño visual de todo el sitio. Refinar los componentes y estados del recorrido acordado sobre la identidad existente.

## Proposed Changes

Los paths marcados **nuevo** son archivos a crear en implementación, no archivos ya existentes. El ejecutor confirmará la última migración antes de asignar el número siguiente, preservando migraciones aplicadas.

### ODD80-01 — Importación real y biblioteca de historiales

**Qué/por qué:** resolver estructura, tamaño y filas del archivo real; cargar una vez y reutilizar, sin mapeo manual para el formato conocido.

**Cómo:** parser específico `metadata`/`sorteos_por_fecha`, lectura limitada del cuerpo, validación de fechas/horas/números/repetición contra el perfil, claves JSON duplicadas/constantes inválidas rechazadas, errores acotados y deduplicación declarada. No confiar en `cantidad_sorteos`. Mantener fuente original y representación normalizada; preview/promote revalidan identidad y cuota, con promoción idempotente existente. Listar paginado, mostrar rango/cantidad/perfil/procedencia y acción continuar a simular. CSV/plano quedan en avanzado sin romper el flujo anterior.

**Superficies:** `webapp/backend/laboratorio/importing/{records,datasets}.py`, `importing/history.py` (**nuevo**), `api/{imports,datasets}.py`, `storage/{repository,quota}.py`, `settings.py`; `webapp/frontend/src/api/{types,client}.ts`, `pages/data/{index,ProfileEditor}.tsx`. Extender migración sólo si la metadata nueva no cabe en el snapshot existente.

**Cierre:** el JSON real completo se valida/promueve sin recorte, queda listado y puede seleccionarse después de reiniciar. UI deja de afirmar que ningún importado se puede ejecutar; informa capacidades reales. Validación manual del usuario pendiente hasta observarla.

### ODD80-02 — Selecciones compatibles y tres presets exactos

**Qué/por qué:** ejecutar los tres presets sobre el historial importado, con reglas verificables y composición compatible con los perfiles.

**Cómo:** resolver selección a través del ranking archivado auténtico o bloque compatible existente; paridad usa contexto causal. Implementar binding de datos a filas archivadas sin debilitar verificaciones de inputs. Añadir capacidades versionadas al registro único y contratos v5 cerrados. Reutilizar liquidación/estado/apuesta existentes o la variante de referencia correcta; contrastar redondeo, costo por cobertura, aciertos repetidos/secundarios, reinicio de ronda y quiebre. No habilitar una capacidad sólo por existir su nombre en el catálogo.

**Superficies:** `webapp/backend/laboratorio/engine/adapter.py`, `domain/{contracts,selection,profile_capabilities,profile_session,profile_staking}.py`, `domain/profile_request_v5.py` y `domain/profile_result_v5.py` (**nuevos**). `repo_ref/simuladores/{paridad_50_plana,transicion_1_audaz,frios_25_escalera}/`, `repo_ref/quiniela_compare.py`, `repo_ref/quiniela_sim.py` y tests/oráculo sólo como referencias de lectura, sin editarlos.

**División interna:** binding → selectores/presets → contratos/resultados. No exponer POST v5 hasta que almacenamiento/worker lo soporten en ODD80-04.

**Cierre:** fixtures/trazas pequeñas concuerdan con referencia; datos/filas/perfiles incompatibles rechazados con motivos explícitos. No afirmar tasas agregadas originales ni soporte para rankings de otro historial.

### ODD80-03 — Biblioteca de estrategias reutilizables

**Qué/por qué:** guardar estrategias propias desde la UI o la IA sin escribir código.

**Cómo:** definición estricta e inmutable, revisión/hash, matriz de compatibilidad del registro, list/get/create. Presets son definiciones iniciales sobre el mismo contrato, con nombre y explicación; variantes se guardan sin sobrescribir originals. Snapshot y versión ejecutable quedan incorporados en la corrida. Preservar `/configurations` heredado: no usarlo como biblioteca nueva mutable.

**Superficies:** `webapp/backend/laboratorio/domain/strategy_library.py`, `api/strategies.py` (**nuevos**), `domain/profile_capabilities.py`, `storage/{repository,quota,database}.py`, siguiente SQL en `storage/migrations/` (**nuevo**), `api/__init__.py`/`app.py` para registrar router. Frontend `src/api/{types,client}.ts` y constructor de ODD80-05.

**Cierre:** crear/listar/reabrir una estrategia; editar genera revisión; definición inválida o bloques incompatibles no se guardan como ejecutables. No modificar resultados al editar la biblioteca.

### ODD80-04 — Admisión, límites y comparación de sesiones individuales

**Qué/por qué:** una sesión por estrategia y comparación desde un mismo documento de condiciones; límites efectivos para humanos y agentes.

**Cómo:** dispatch explícito v5 en almacenamiento/cola/worker/API. Compilar lote acotado con mismo dataset/perfil/capital/inicio/cierre; un run ordinal por estrategia. Validar bindings, financiación y capacidad antes de persistir/encolar; tamaño de lote y estado legibles. Reutilizar cola serial, cancelación, listado, detalle, replay, trayectoria y comparación. No POSTs independientes sin agrupación que la pantalla no pueda comparar.

Eliminar el rechazo global por tamaño de dataset de la ruta nueva: conservarlo completo y acotar trabajo de sesión por presupuesto explícito; acceso paginado/iteración suficiente para esa ventana. Admitir capacidad de cola/cuota de forma atómica, no sólo un límite por petición que la IA pueda eludir con muchas peticiones. Configuración de límites local persistida por la UI; el agente consume esa política, no la cambia. Preservar recuperación/interrupción existente: no prometer pausa/reanudación nueva.

**Superficies:** `webapp/backend/laboratorio/api/{experiments,settings,__init__}.py`, `jobs/{queue,worker}.py`, `storage/{repository,database,quota}.py`, `settings.py`, contratos/resultados v5 y SQL siguiente (**nuevo**, puede agrupar tablas/constraints necesarias con ODD80-03 si aún no fue aplicado); `webapp/frontend/src/pages/settings/index.tsx`, `src/api/{types,client}.ts`.

**Cierre:** lote de hasta tres estrategias ejecutado serialmente, comparación de cada sesión, cancelación y errores sin falso completado; límites aplican a UI/API, exceso se rechaza antes de encolar. Clasificar por separado cierre financiero, cierre configurado e interrupción por presupuesto operativo.

### ODD80-05 — Asistente humano y presentación coherente

**Qué/por qué:** completar el recorrido acordado para alguien sin conocimientos de código; usar una sola definición entre editor, resumen y ejecución.

**Cómo:** historial → perfil/pagos/capital → presets o bloques compatibles → revisión del lote → progreso/resultados/comparación. Volver entre pasos o abrir avanzado no elimina campos; si cambian identidad/capacidades, invalidar sólo selecciones dependientes y avisar. Mostrar explícitamente incompatibilidades y filas iniciales evaluables, sin cambiar inicio automáticamente. Agrupar controles técnicos/procedencia en avanzado con resumen visible. Biblioteca de estrategias como selección/guardado dentro del recorrido, no un segundo producto.

Reutilizar `btn`, `control` y estilos existentes; botones de acción con estados de hover/foco/disabled/loading y nombres claros. Los enlaces de navegación pueden seguir siendo enlaces. Preservar rutas/direct links de resultados antiguos; el nuevo flujo sustituye/integra entradas existentes sin borrar acceso legacy. Adaptar sólo pantallas/componentes del recorrido. Resultados reutilizan métricas autoritativas y trayectoria completa reducida honestamente, con acceso exacto; no recalcular finanzas ni ocultar fallos/incompletos.

**Superficies:** `webapp/frontend/src/pages/new-experiment/{index,ProfileExperimentPage}.tsx`, `{model,profile-model}.ts`, `src/components/StrategyEditor.tsx`, componentes nuevos de pasos si hacen falta; `pages/data/index.tsx`, `src/{App.tsx,components/Shell.tsx}`, estilos existentes que usa `btn/control`, `pages/experiments/{index,DetailPage,ComparisonPage}.tsx`, `components/{FinancialMetrics,RunTrajectory,BalanceChart,ComparisonChart}.tsx`, `lib/profile-display.ts`. No reemplazar por completo lo ya verificado.

**Cierre:** recorrido humano listo para revisión manual: crear/guardar/elegir, regresar sin pérdida, revisar y ejecutar; escritorio/móvil/teclado, estados y errores. Evidencia visual y aceptación manual pertenecen al usuario.

### ODD80-06 — API local para agentes y guía breve

**Qué/por qué:** que un agente pueda realizar el mismo recorrido sin conocer implementación ni recibir acceso al sistema.

**Cómo:** fachada nueva `/api/agent/v1` que delega al servicio común; no cliente IA integrado. Exponer sólo capacidades/presets, historiales/perfiles, estrategias list/get/create, validación del lote, creación/estado/cancelación/resultados/comparación. La importación usa el cuerpo del archivo, nunca una ruta enviada por el agente. Versionar y documentar JSON, moneda/unidades, límites, credencial, errores y fuente/ranking compatible.

Exigir Bearer token en toda fachada; preservar Host/Origin y sin CORS abierto. Decisión humana A: confiar en clientes HTTP locales y conservar la API nativa sin autenticación adicional. La fachada y la UI usan idéntica admisión y política, pero el allowlist/Bearer de `/api/agent/v1` no impide llamadas directas a `/api/v1` desde un cliente local. Host/Origin es una protección de origen/CSRF del navegador, no autenticación de procesos locales. Consulta de credencial/ajustes restringida al origen local de la UI bajo este modelo de confianza; un cliente HTTP local puede falsificar Origin. No prometer aislamiento frente a clientes locales maliciosos ni procesos que puedan leer el directorio de datos. Un POST cuyo resultado es incierto no se reintenta automáticamente: se conserva/reconcilia identidad de solicitud para evitar duplicados; exponer identidad de cliente idempotente en la nueva creación de lotes sin alterar POSTs antiguos.

**Superficies:** `webapp/backend/laboratorio/api/agent.py` (**nuevo**), `app.py`, `api/{strategies,experiments,settings}.py`, `settings.py`, `storage/repository.py`; frontend ajustes avanzados para consultar/copiar la credencial; `webapp/README.md` y `docs/api-agentes-80-20.md` (**nuevo**). La documentación incluye un ejemplo JSON/curl para crear una estrategia, validar, ejecutar y consultar/cancelar; el usuario puede probarlo manualmente.

**Cierre:** cliente válido crea/ejecuta; sin credencial no obtiene acceso a `/api/agent/v1`. Dentro de esa fachada no puede saltar límites ni invocar rutas fuera del allowlist; los clientes nativos locales siguen siendo de confianza, sin garantía anti-elusión entre namespaces. Sin tokens en logs/URLs/snapshots. API y UI coinciden en condiciones y resultados.

### ODD80-07 — Comprobaciones mínimas, manual del usuario y Judgment Day

**Qué/por qué:** aceptación honesta del alcance, sin gastar tiempo en suites globales repetidas ni declarar aprobadas pruebas que hará el usuario.

**Cómo:** checklist manual en la guía anterior/README, agrupado por las condiciones de cierre de cada unidad. Ejecutar sólo las comprobaciones críticas descritas abajo. Esperar resultado manual del usuario para cerrar aceptación. Dos jueces ciegos de solo lectura sobre el mismo commit/árbol y alcance inmutable; ambos reciben los mismos contratos, referencias y skills. No ejecutar además 4R sobre ese target. No es aprobación comercial universal ni autorización de publicación.

**Superficies:** documentación de ODD80-06, tests focalizados junto a archivos cambiados y registro de tareas creado al autorizar implementación. No crear ahora otro documento de especificación ni un nuevo plan global ODD-00…13.

**Cierre:** separar implementado, comprobado automáticamente, manual pendiente y aceptado. Judgment Day termina APPROVED o ESCALATED; ninguna aceptación global si falta evidencia manual o persiste un bloqueante.

## Ejecución ODD y dependencias

1. Aprobación explícita de este plan antes de cambios de código/config/DB. Releerlo al comenzar. No más elicitación: alcance fijado arriba; si aparece una contradicción real, detener sólo la unidad afectada y consultar, no ampliar silenciosamente.
2. Crear `odd/tasks/producto-local-80-20.md`, espejo Engram `odd/producto-local-80-20/tasks` y `todo` con las siete unidades antes de la primera escritura fuente. Son artefactos de continuidad de implementación, no autorizados en la planificación actual. Mantener el seguimiento integral previo: las tareas diferidas no pasan a cerradas por completar este recorte.
3. Orden: 01 → 02 → 03 → 04 → 05 → 06 → 07. Dividir internamente cambios extensos por fronteras comprobables; un solo escritor fuente activo. Usar delegación acotada con paths concretos según el harness, sin releer exhaustivamente ni repetir auditorías de toda la base.
4. Actualizar tarea/memoria/todo tras transiciones. No marcar aceptación manual del usuario como aprobada por haber pasado tipos o build. Documentar bloqueos, tests omitidos y mediciones pendientes.
5. Cambio esperado superior a 400 líneas: mantener unidades revisables y recomendar PRs encadenados sólo si el usuario luego pide publicar. Este plan NO autoriza commits, push, PRs, instalaciones ni limpieza del worktree; requerir autorización explícita correspondiente. No repetir la entrega monolítica anterior como método de revisión.
6. Al revisar con Judgment Day, esperar a ambos jueces; guardar ledger común. Sólo graves coincidentes pueden corregirse, preguntando antes de la primera ronda; máximo dos rondas de corrección/rejuicio acotado. No usar refutador ni fabricar aprobación. No iniciar esa revisión hasta tener un target completo e inmutable.

## Verification

### Política de velocidad y responsabilidad

- Usuario: mayoría de aceptación funcional/visual, archivo real, recorrido/UI/API y pruebas de uso. Entregar instrucciones concretas y esperar sus resultados.
- Agente: comprobaciones mínimas de compilación/tipos y fronteras financieras, integridad y seguridad modificadas. No ejecutar por defecto suites completas, benchmarks exhaustivos, las catorce referencias ni matrices de navegadores.
- Para un cambio de comportamiento con prueba determinista aplicable, una regresión mínima RED → GREEN; no crear suites redundantes. Documentación/UI no determinista: revisión estructural/tipos y manual del usuario, sin afirmar RED inexistente.
- Invocar tests desde su workspace. Los verificadores no instalan dependencias ni editan fuentes; pytest sólo escribe en TEMP autorizado, sin bytecode/caché de repositorio. Builds existentes son parte de implementación aprobada, no de esta etapa de planificación.

### Comprobaciones automáticas mínimas del agente

1. Importación: ejemplo anidado válido y mayor que antiguo límite de filas; estructura/rangos inválidos; mismatch del hash preview/promote y duplicados explicados. No convertir en verde una pérdida de filas.
2. Financiero/binding: casos pequeños de los tres presets (costo, premio, saldo, redondeo y reinicio de ronda), ranking incompatible/reordenado rechazado y snapshot guardado inmutable. Oráculo/referencias no se regeneran ni se editan para ajustar expectativas.
3. API/admisión: credencial ausente/incorrecta, lote o cola excedidos y combinación no soportada rechazados; identidad de creación reintentada sin duplicación. No probar payloads que accedan a archivos reales del usuario.
4. Ejecutar sólo tests afectados/seleccionados. Comando base desde `webapp/backend`: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -3 -B -m pytest <tests-o-nodos-afectados> -q -p no:cacheprovider`. Usar los tests existentes `test_import_records.py`, `test_import_api.py`, `test_datasets.py`, `test_profile_staking.py`, `test_profile_session.py`, `test_profile_api.py`, `test_queue.py`; añadir archivos/nodos v5, biblioteca y credencial estrictamente necesarios al implementar. No ejecutar toda esta lista en cada transición.
5. Ruff sobre paths Python cambiados: `py -3 -B -m ruff check --no-cache <paths>`. Frontend desde `webapp/frontend`: `npm run typecheck`; `npm run build` al integrar/cerrar. Vitest sólo si existe una regresión lógica específica necesaria, nunca suite completa por rutina. LSP sobre archivos cambiados puede ayudar, pero caché vacía no demuestra ausencia de errores.
6. Guardar comandos/resultados observados; no extrapolar estos checks a una suite completa verde. Si fallan cálculos/integridad/seguridad o compilación, bloquear la unidad, no delegar su resultado a una afirmación manual inventada.

### Checklist manual del usuario

- [ ] Cargar el `chance_express_history.json` original completo; comprobar cantidad leída frente a metadata, rango, zona, duplicados y errores; promover y volver a seleccionarlo tras reiniciar. No descarga ni modificación del original.
- [ ] Revisar pagos/moneda/perfil; seleccionar o crear estrategia sin código, guardar, reabrir, volver entre pasos y desplegar avanzado sin pérdida.
- [ ] Correr paridad plana, transición audaz y fríos escalera desde un inicio evaluable común, con condiciones comparables. Revisar apuesta/cobro/saldo en una muestra y causa de cierre; contrastar la sesión de referencia sin exigir estadísticas de sesiones consecutivas.
- [ ] Comparar métricas/trayectorias y abrir una apuesta exacta fuera de la primera página de replay; verificar reducción declarada y estados incompletos/no disponibles.
- [ ] Probar inicio sin ranking, historial distinto para selector archivado, importación inválida, stake inicial no financiable, presupuesto/lote excedido y cancelación. Esperar motivos claros, no sustituciones ni falso completado.
- [ ] Cambiar límites dentro de los rangos admitidos; revisar el lote antes de ejecutar. Medir importación y sesiones reales, registrar tamaño/tiempo observado y confirmar/calibrar defaults; no asumir garantías de hardware.
- [ ] Seguir ejemplo API: credencial → consultar capacidades/historial → guardar definición → validar → ejecutar → progreso → resultados/comparación → cancelar si corresponde. Sin aprobación por corrida; límites iguales a UI.
- [ ] Revisar escritorio, móvil y teclado; botones accionables, foco/labels, mensajes de carga/error, volver/reintentar sin duplicar ejecución ni perder configuración.
- [ ] Confirmar alcance aceptado o informar fallos. Este checklist queda PENDIENTE hasta recibir evidencia del usuario.

## Out of Scope

MCP; once presets restantes; cuentas/multiusuario/ventas; conectores/descargas/programación de actualizaciones; nuevos algoritmos/entrenamiento; Python de terceros, plugins o nueva DSL; sesiones consecutivas, múltiples inicios/grillas, Monte Carlo y estabilidad; nuevas estadísticas de rentabilidad; exportadores nuevos; reanudación/pausa universal; rediseño de todo el sitio; suites completas repetidas/certificación automática; ejecutar todas las tareas del laboratorio integral; commits/push/PR sin autorización específica.

## Estado de fases del plan

- Phase 1 — Explore: cumplida con lectura de fuentes actuales, referencias y scout de solo lectura. La observación del scout sobre inexistencia de `cold` se descartó: `domain/contracts.py` lo registra explícitamente.
- Phase 2 — Clarify: sin preguntas adicionales; el usuario entregó el alcance consolidado tras ocho decisiones y pidió convertirlo en plan. Los defaults numéricos son propuesta inicial de calibración explícita, no evidencia ya medida.
- Phase 3 — Generate Plan: este archivo, sin modificar producto/config/migraciones.
- Phase 4 — Notify & Execute: notificar plan listo y esperar aprobación. Ejecución NO iniciada; no se omitió exploración ni se trasladó a SDD.
