# Plan ODD: quiniela configurable y auditable

> Preparado con `plan-mode-trae`. Estado: listo para aprobación; implementación NO iniciada.
> Única escritura autorizada en esta etapa: este plan. Ejecución posterior con ODD y modo YOLO, no SDD.

## Summary

Convertir la web local existente en un laboratorio configurable de juegos de quiniela: asistente obligatorio, historiales compatibles, bloques de estrategia verificables, recreación y duplicación, comparación, exportación, trayectoria y detalle por apuesta, y respaldo/restauración manual. Conservar los contratos y resultados existentes; no incorporar cuentas, pagos, servicio remoto ni trabajo de empaquetado.

## Scope supplied by the user

Estos son los requisitos de entrada, no una especificación nueva ni una autorización para ejecutar:

- [A1] Web local en el navegador, como hoy. Distribución mediante ZIP; sin aplicaciones nativas ni servicio alojado.
- [P1] Una persona por instalación, sin cuentas ni inicio de sesión.
- [A2] Primera versión limitada a quiniela. Otras familias de lotería quedan fuera por ahora.
- [F1] Juegos de quiniela configurables: universo de números, posiciones, orden, repeticiones y pagos.
- [D1] Historial incluido y posibilidad de cargar otros historiales compatibles con el juego configurado.
- [F2] Constructor con bloques verificados de selección, apuesta y cierre. Sin código externo, plugins ni editor de programación.
- [F3] Los laboratorios existentes se pueden borrar manualmente y recrear fácilmente con sus configuraciones y reglas.
- [F4] Duplicación con cambios, comparación de pruebas compatibles y exportación de configuraciones y resultados.
- [F5] Análisis auditable: trayectoria del saldo y detalle por apuesta —selección, importe, resultado, premio y saldo—.
- [F6] Exploración automática de combinaciones de parámetros queda fuera de esta versión.
- [D2] Respaldo completo y restauración manuales. Eliminación permanente después de confirmar; sin papelera ni respaldos automáticos.
- [U1] Configuración mediante asistente obligatorio: juego → historial → estrategia → condiciones → revisión.

Correcciones posteriores que prevalecen:

- Acceso/distribución: «A no todo se lo mando en un zip nada de compras».
- Pregunta de entrega durante planificación: «ovidate de esto del zip dejalo tal cual esta no lo compliques yo me encargo luego».
- Por tanto, NO se implementan ZIP, instaladores, runtimes incluidos, preparación de dependencias ni nuevos mecanismos de arranque. El usuario se encarga de la distribución después.

## Current State Analysis

Base inspeccionada: `1c5e441`, rama `feat/reference-laboratories`. Exploración del padre y scout de solo lectura `mv6hergn-9-kgqd`; no se ejecutaron pruebas, builds ni modificaciones de datos en esta planificación.

- `webapp/backend/laboratorio/app.py` sirve frontend compilado y API en loopback, conserva guardas Host/Origin y abre el navegador mediante el servidor local. `iniciar-laboratorio.bat` y el arranque actual quedan fuera de cambios.
- `webapp/frontend/src/App.tsx` abre Laboratorios por defecto y conserva `/corridas`, `/corridas/nueva`, `/corridas/:id` y `/ajustes`. `components/Shell.tsx` solo muestra Laboratorios/Ajustes.
- `domain/contracts.py` contiene `Game` y `GameProfile`, incluyendo límites de admisión de 1.000 números, 16 posiciones y moneda de escala hasta 6. El perfil es inerte: no prueba ejecución genérica. También distingue pagos racionales exactos y semántica histórica `first-match/v0` de perfiles nuevos.
- `domain/laboratories.py` mantiene definición inmutable v1, UUID, cinco premios, cobertura máxima 50, ventana archivada, paridad de 50 y límites financieros calculados para 105.426 sorteos. No se puede ampliar ese contrato eliminando validaciones.
- `engine/owned_laboratory_service.py` exige el historial congelado y usa el motor de referencia. `engine/reference_labs.py` contiene las fórmulas plana/audaz/escalera y el comportamiento de las catorce referencias.
- `domain/runs.py` y `domain/session.py` tienen otro contrato: universo 100, cinco resultados, apuesta fija y sesiones consecutivas; la siguiente sesión reinicia capital. `Draw`/`Bet` no son DTOs genéricos.
- `engine/run_data.py` prepara paridad y mezclas de los 13 rankings archivados. Los rankings se alinean por etiquetas en historiales extendidos; ello no demuestra identidad de resultados ni compatibilidad con cualquier perfil.
- `api/history.py`, `engine/active_history.py` y `engine/history_merge.py` gestionan JSON, fuentes inmutables y fusión/activación. No son una biblioteca de historiales de cualquier perfil.
- `storage/laboratory_store.py`, `storage/owned_laboratory_run_store.py` y `storage/database.py` ya tienen propiedad explícita, cuota, transacciones y borrado confirmado. El esquema observado es 17; ninguna migración aplicada se modifica.
- `storage/run_trace.py` guarda detalle heredado limitado a 50.000 sesiones, 250.000 apuestas y 32 MiB; puede quedar parcial/truncado. `api/laboratory_runs.py` declara `per_bet_trace: false` para laboratorios actuales.
- `pages/laboratories/{Workspace,LaboratoryForm,LaboratoryPanel}.tsx` son el recorrido actual; no hay asistente de cinco pasos. `pages/runs/RunBets.tsx` y sus tipos aportan patrones para detalle heredado, no una implementación de F5 para laboratorios.
- No se verificaron utilidades existentes de comparación de laboratorios, exportación, respaldo/restauración completa ni empaquetado.
- Los antiguos caminos `domain/profile*` y `components/FiveStepWizard.tsx` citados en planes históricos NO existen en el árbol actual. No se reutilizarán como si estuvieran implementados.
- Evidencia previa, no repetida aquí: backend 703 pruebas; frontend 152, tipos/build; catorce referencias recreadas con resultados equivalentes. No es aceptación automática del alcance nuevo.

### Estado ajeno que se conserva

El índice contiene cuatro cambios de otra unidad: eliminaciones de `docs/DESIGN.md`, `docs/PRODUCT.md`, `especificaciones-laboratorio-web.md` y alta de `odd/qa/reestructura-profile-repeat.cjs`. Su diff binario conocido mide 87.352 bytes, SHA-256 `26315d4a5004133f338b126535285ed13b4b2c117d3d55695f3e84798a4870d9`.

`odd/tasks/main-screen-clarity.md` también es ajeno. No limpiar, restablecer ni incorporar esos cambios a commits de esta iniciativa. Preservar `.env`, `repo_ref/`, `lagacy_loto/`, datos normales y procesos/previews del usuario.

## Assumptions & Decisions

Las siguientes son decisiones técnicas propuestas para aprobar con este plan. No se presentan como respuestas adicionales del usuario.

### 1. Contratos y compatibilidad

- Añadir protocolo configurable versionado y rutas `/api/v2`, sin reinterpretar definiciones/resultados v1 ni sustituir sus lectores. Nuevas tablas y migraciones aditivas, con número siguiente confirmado al implementar.
- Un perfil de quiniela describe universo finito de valores enteros no negativos, representación visual de números, posiciones, repetición permitida, posiciones jugadas, moneda/escala, unidad mínima, incremento, exposición y pagos. Aplicar los techos de admisión existentes de 1.000 valores/16 posiciones; no afirmar capacidad ilimitada.
- El orden se configura como posiciones diferenciadas o posiciones indiferentes. En el segundo caso, los pagos de las posiciones jugadas deben ser iguales: no se transforma el producto en una lotería por combinaciones.
- Los números elegidos por apuesta son distintos; la repetición configurable se refiere a resultados del sorteo. Más dinero sobre un mismo número se expresa mediante la apuesta, no duplicando números.
- Liquidación explícita: sumar premios de posiciones acertadas o tomar el mayor premio por número acertado. Mantener las reglas históricas que correspondan exclusivamente en sus contratos de referencia; jamás migrar un resultado antiguo a otra fórmula.
- Dinero calculado en unidades enteras de la escala del perfil y multiplicadores racionales. Rechazar pagos no representables en el incremento elegido; no redondear silenciosamente. Comprobar límites con cantidad real de filas, no con `MAX_FROZEN_DRAWS` para fuentes nuevas.
- Perfil, fuente, estrategia, condiciones y versión de motor quedan incorporados al snapshot inmutable. Una modificación crea una definición nueva, también al duplicar.

### 2. Historiales y bloques iniciales

- Importación inicial mediante JSON canónico versionado y adaptador para el JSON anidado incluido. Publicar esquema y ejemplo descargable. CSV, Excel, PDF, conectores y descarga automática no se agregan en este recorte.
- Elegir archivo → validar/previsualizar → confirmar guardado. Mostrar perfil, rango, cantidad, zona horaria, duplicados y errores. La fuente seleccionada se vincula al laboratorio; importar no sustituye silenciosamente otra fuente ni sus resultados.
- Fechas sin zona requieren confirmación explícita de la zona de la fuente; la referencia conserva su interpretación documentada. No ordenar ni reinterpretar las posiciones del sorteo al ordenar filas cronológicamente.
- Duplicados idénticos se detectan y reportan; mismo identificador/instante con resultados distintos provoca rechazo completo. No recortar filas para cumplir un límite.
- Catálogo de selección: números fijos/manuales, paridad causal y rankings archivados individuales/mezclas existentes. La selección manual es un bloque acotado de F2, no código del usuario.
- Paridad genérica usa el universo del perfil y únicamente contexto previo. Una mezcla archivada exige componentes admitidos y porcentajes que sumen 100. No entrenar ni generar rankings nuevos.
- Rankings archivados solo cuando universo, estructura y filas pueden vincularse a la fuente original con resultados idénticos. Bloquear otras combinaciones con motivo visible; igual etiqueta no prueba identidad. La política de filas elegibles de referencias antiguas se conserva y se informa, no se sustituye.
- Toda ejecución informa ventana solicitada/efectiva, filas evaluables, filas sin selección y política de contexto previo. No apostar con selecciones inventadas ni cambiar de algoritmo como fallback.
- Catálogo de apuesta: fija, plana, audaz y escalera. La fija admite importe; plana reproduce una unidad de apuesta; audaz y escalera conservan sus fórmulas/versiones de referencia en perfiles compatibles. Sus parámetros y restricciones se documentan y validan antes de admitir ejecución.
- Cierre: meta de saldo, siguiente apuesta no financiable y límite opcional de sorteos por sesión. Capital reiniciado explícitamente entre sesiones; fin del historial implica sesión incompleta. Restricciones de exposición/operación no se etiquetan como quiebra financiera.

### 3. Reproducción, comparación y trazabilidad

- Los catorce ejemplos siguen disponibles como plantillas de solo lectura, separadas de laboratorios guardados. Eliminar una instancia no elimina la plantilla ni provoca resiembra al reiniciar.
- «Crear desde ejemplo» y «Duplicar con cambios» abren el mismo asistente con valores completos. Guardan UUID nuevo, sin copiar corridas ni recuperar identidad eliminada. Permitir reutilizar el nombre cuando la instancia anterior ya no exista.
- Comparación inicial de dos corridas finalizadas con perfil, fuente, ventana/filas evaluables, capital y condiciones de cierre equivalentes. Pueden variar selección y apuesta. Si esas bases difieren, explicar incompatibilidades y no producir un ranking engañoso ni recortar resultados automáticamente.
- Presentar neto, apostado, pagado, retorno sobre lo apostado, sesiones por cierre y media de cerradas, con definiciones. Denominador cero es N/A; incompletas se identifican y conservan su tratamiento financiero.
- Cada apuesta nueva conserva ordinal, sesión, sorteo/fecha, selección, importe por número y total, resultados, pago, saldo antes/después y reglas utilizadas. Backend autoritativo para métricas; frontend no reconstruye las finanzas.
- Trayectoria consultada por páginas: saldo de sesión con reinicios señalados. Una reducción para dibujar no elimina el detalle almacenado; acceso exacto a cada punto/apuesta. No presentar los reinicios como ganancias ni como una sola cuenta continua.
- Una corrida nueva solo se declara completa/auditable si guarda toda su traza. Los límites existentes sirven como presupuestos iniciales de detalle; si se exceden, rechazo/admisión o fallo explícito sin publicar resumen completo con una traza parcial. No copiar la truncación silenciosa al contrato nuevo.
- Presupuestos independientes de lectura, trabajo, detalle y cuota visibles. Paginar consultas, calcular/guardar por bloques, no cargar todo en el navegador. Progreso y cancelación explícitos para la ejecución solicitada; sin lotes ni grillas automáticas.
- Mantener lectores de resultados antiguos sin trazas y con detalle parcial, marcándolos como tales. No inventar detalle retroactivo. Para obtener traza completa, ejecutar una instancia nueva compatible.
- POST ambiguo: reconciliar identidad de solicitud/estado; sin reenvíos automáticos. Las solicitudes nuevas usan identidad idempotente asociada al cuerpo canónico. Una ejecución cancelada/interrumpida no se muestra como completada.

### 4. Exportación y respaldo/restauración

- Exportar configuración portátil en JSON, resultados/snapshots en JSON y tablas de sesiones/apuestas en CSV. La exportación de una corrida auditable incluye toda la traza; contar filas y señalar alcance, no solo la página visible.
- Exportar configuración no es un respaldo completo. Importarla crea otra identidad después de validación; no ejecuta automáticamente.
- Respaldo manual completo de datos gestionados: perfiles, fuentes importadas, definiciones, corridas, sesiones, trazas y ajustes persistidos. Manifest versionado con tamaños/hashes y referencias a insumos incluidos. No exportar secretos, `.env`, credenciales de agentes, cachés desechables ni archivos arbitrarios del equipo.
- Generar respaldo consistente con lecturas transaccionales/instantánea; no copiar a ciegas un SQLite abierto ignorando WAL. Ninguna copia se genera automáticamente.
- Restauración por reemplazo del espacio gestionado, NO fusión. Primero validar en estado aislado estructura, versión, hashes, relaciones, cuota e insumos requeridos; mostrar el conteo que reemplazará. Exigir confirmación explícita y ausencia de ejecución/escritura activa.
- Publicar el reemplazo únicamente después de validación completa; cualquier rechazo conserva los datos actuales. No ejecutar SQL suministrado por el archivo ni extraer rutas arbitrarias/symlinks. Controlar expansión de archivos comprimidos y tamaño efectivo.
- Datos de ejecución activa presentes en una copia no se reanudan automáticamente al restaurar: se marcan interrumpidos y conservan su procedencia. No regenerar resultados ni resiembra de ejemplos por restauración.
- Borrado permanente con conteo actualizado de dependencias. Sin papelera, deshacer ni copia automática previa; ofrecer respaldo manual, no fingir recuperación individual.

### 5. Interfaz y operación

- El asistente es obligatorio: juego → historial → estrategia → condiciones → revisión. Volver conserva campos válidos; cambios de perfil/fuente invalidan únicamente elecciones incompatibles y explican el motivo.
- La revisión muestra el contrato financiero, fuente, rango efectivo, límites y compatibilidad. Guardar crea el laboratorio; ejecutar sigue siendo una acción explícita posterior.
- Mantener la identidad visual actual de libreta/Archivo, controles accesibles y menú Laboratorios/Ajustes. No rediseño total, cuentas ni páginas comerciales.
- Resultados con enlace persistente a corrida/sesión, nombres legibles, unidades y zona horaria; huellas técnicas en detalles. Tabla vacía sin rangos `1–0`; motivos de cierre exhaustivos, no convertir estados desconocidos en «incompleta».
- La página nueva no promete que importar genere rankings ni que rentabilidad histórica prediga el futuro. Advertencia visible en creación, ejecución, resultado y exportaciones.
- Mantener acceso directo a `/corridas*` y resultados v1; no volver a poner Corridas en el menú principal ni borrar datos antiguos.
- Arranque, dependencia de Python, frontend compilado y distribución quedan tal como están. No tocar el servidor que el usuario está usando durante desarrollo/verificación.

## Proposed Changes

Los paths **NEW** son propuestas a crear; los demás existen y fueron inspeccionados o mapeados. Cada unidad lleva pruebas y documentación de su conducta; no un commit monolítico de todo el producto.

### Q1 — Perfiles ejecutables y contratos versionados [F1, A2]

**What/why:** definir la quiniela configurable real sin fingir que `GameProfile` inerte ya ejecuta ni debilitar v1.

**How/files:**
- Reutilizar validaciones de `domain/contracts.py`; mantener sus perfiles históricos y añadir adaptación explícita.
- **NEW:** `domain/quiniela_profiles.py`, `domain/configurable_laboratories.py`, `domain/configurable_runs.py` para perfiles, bloques referenciados, ventanas, snapshots y DTOs variables.
- **NEW:** `storage/game_profile_store.py` y `api/game_profiles.py`; migración aditiva siguiente en `storage/migrations/` y registro acotado en `app.py`.
- Pruebas **NEW** de perfil/DTO/API; regresión de lectores v1. Confirmar techos y aritmética antes de habilitar ejecución.

**Close:** guardar/reabrir perfiles diferentes de 100/5; rechazar combinaciones inválidas sin escribir datos; contratos antiguos siguen leyendo igual.

### Q2 — Biblioteca de historiales compatibles [D1, F1]

**What/why:** separar fuente/perfil de historial activo heredado; la compatibilidad debe demostrarse, no suponerse por etiquetas.

**How/files:**
- Conservar `api/history.py`, `engine/active_history.py` y `engine/history_merge.py` para v1.
- **NEW:** `engine/quiniela_import.py`, `storage/quiniela_history_store.py`, `api/history_sources.py` y migración aditiva.
- JSON canónico, adaptador incluido, previsualización inmutable y promoción confirmada revalidada por hash; esquema/ejemplo en documentación.
- Validar cantidad de posiciones, universo, repeticiones, cronología, zona y conflictos. Guardar fuente inmutable asociada a perfil; no cambiar otra fuente global.

**Close:** importar un historial de otra quiniela, seleccionarlo y reabrirlo; rechazos dejan fuentes, cuota y contadores intactos. Archivo incluido completo admitido, sin cortes.

### Q3 — Catálogo/compilación de bloques [F2]

**What/why:** una misma validación decide lo disponible en asistente y motor; no habilitar etiquetas sin implementación.

**How/files:**
- **NEW:** `domain/strategy_blocks.py` y `engine/quiniela_selection.py` para catálogo, parámetros, compatibilidad y selección causal.
- Reutilizar matemáticas y restricciones de `engine/run_data.py`, `engine/reference_labs.py` y `domain/runs.py` por adaptadores; no reemplazar sus entradas v1.
- Selección manual/paridad genérica y rankings/mezclas archivados; apuesta fija/plana/audaz/escalera; reglas de cierre versionadas.
- **NEW:** `api/strategy_blocks.py` devuelve capacidades, explicaciones y motivos de incompatibilidad.
- Fixtures deterministas de pagos repetidos/ordenados/indiferentes, fondos insuficientes, límites y ausencia de información futura.

**Close:** una composición válida se compila; una inválida no se guarda como ejecutable. Misma entrada produce misma selección; incompatibilidad no provoca sustitución.

### Q4 — Motor configurable y trazas completas [F5, F2]

**What/why:** ejecutar perfiles nuevos y demostrar cada movimiento de saldo, manteniendo las referencias fieles.

**How/files:**
- **NEW:** `engine/quiniela_replay.py`, `storage/configurable_run_store.py` y migración de corridas/sesiones/trazas/estado de ejecución.
- DTO de sorteo y selección de longitud variable; aritmética exacta, exposición y cierre validados.
- Instrumentar/adaptar el núcleo de referencia con observación de apuestas sin alterar resultados v1. Si requiere extracción compartida, probar diferencialmente antes/después y mantener entradas públicas.
- Captura por bloques, cuota/admisión atómicas, una ejecución activa, progreso/cancelación y publicación transaccional de corrida finalizada.
- Rechazo/fallo de detalle insuficiente sin un falso resultado auditable. Recuperación de proceso marca interrumpido, sin ejecución automática.

**Close:** totales se reconcilian con la traza completa y cada sesión; los catorce ejemplos mantienen totales y fronteras originales, ahora con detalle verificable en ejecuciones nuevas.

### Q5 — Laboratorios, plantillas y API integradas [F3, F4, F5]

**What/why:** hacer que definición, ejecución y lectura compartan snapshots y propiedad explícita.

**How/files:**
- **NEW:** `storage/configurable_lab_store.py`, `engine/configurable_lab_service.py`, `api/configurable_laboratories.py`, `api/configurable_runs.py` y migración aditiva.
- `/api/v2` para CRUD, plantillas, admisión/estado, resumen, sesiones y apuestas paginadas; DTOs acotados y ámbito por owner.
- Adaptación de solo lectura para listar/abrir definiciones y resultados antiguos en el espacio actual sin modificar su serialización.
- Plantillas originales separadas de instancias; creación desde plantilla/duplicación genera UUID nuevo con todas las reglas. Borrado confirmado elimina sus dependencias, no la plantilla ni datos ajenos.
- Mantener guardas en `app.py` para rutas nuevas y límites de cuerpo específicos; no relajar globalmente v1.

**Close:** borrar → reiniciar → no reaparece → recrear desde ejemplo; identidad nueva, parámetros completos, cero corridas heredadas. Conteo obsoleto, cuota o incompatibilidad no producen guardado parcial.

### Q6 — Comparación homogénea y exportación [F4, F5]

**What/why:** comparar variantes con bases equivalentes y sacar el trabajo completo, no solo lo visible.

**How/files:**
- **NEW:** `engine/quiniela_comparison.py`, `engine/quiniela_exports.py`, `api/laboratory_comparisons.py`, `api/laboratory_exports.py`.
- Comparación de dos snapshots finalizados; diferencias de base devuelven razones explícitas. No recalcular ni volver a ejecutar al comparar.
- JSON de configuración/resultado y CSV de sesiones/apuestas mediante lectura consistente y salida por bloques. Neutralizar fórmulas de planilla en campos de texto, sin alterar valores financieros numéricos.
- Importación de configuración exportada por el mismo contrato validado y creación de identidad nueva.

**Close:** comparación reproducible; exportación incluye filas fuera de la primera página y coincide con los totales almacenados; importación no sobrescribe ni ejecuta automáticamente.

### Q7 — Respaldo completo y restauración manual [D2]

**What/why:** recuperación explícita del espacio local, sin papelera ni mecanismos automáticos no elegidos.

**How/files:**
- **NEW:** `engine/manual_backup.py`, `api/manual_backups.py` y pruebas con directorios/bases desechables.
- Archivo lógico versionado de datos gestionados con manifest/hashes; representación definida por tablas/contratos admitidos, no una orden SQL ni una ruta del cliente.
- Instantánea consistente; validación aislada y vista previa del reemplazo; exclusión mutua de restauración y ejecución/escritura.
- Publicación controlada solo tras confirmación y validación. Rechazos preservan el espacio anterior. Manejo explícito de versión no soportada, cuota, corrupción y paquetes maliciosos.

**Close:** una copia restaura perfiles, fuentes, laboratorios, sesiones y apuestas con mismos IDs/digests; restauración inválida no cambia archivos ni registros del destino.

### Q8 — Asistente obligatorio y experiencia de análisis [U1, F1–F5]

**What/why:** reemplazar formulario único por el recorrido acordado, conservando claridad y operación local.

**How/files:**
- `pages/laboratories/Workspace.tsx`/`LaboratoryForm.tsx`/`LaboratoryPanel.tsx`, `App.tsx` y `pages/settings/SettingsPage.tsx` se integran gradualmente.
- **NEW:** `pages/laboratories/Wizard.tsx`, `wizard-model.ts`, pasos `GameStep.tsx`, `HistoryStep.tsx`, `StrategyStep.tsx`, `ConditionsStep.tsx`, `ReviewStep.tsx`.
- **NEW:** cliente/tipos `src/api/configurableLaboratories.ts`, vistas `RunResult.tsx`, `RunTrace.tsx`, `BalanceTrajectory.tsx`, `Comparison.tsx`.
- Reutilizar `components/ui`, `ConfirmDialog`, `Shell`, tokens y CSS existentes. Selector de plantillas, duplicación prellenada, validación y foco de error; no guardado fuera de revisión.
- Consulta con enlaces persistentes, sesiones/apuestas paginadas, gráfico basado en backend, estados vacíos/carga/error/cancelación y reenvío incierto seguro.
- Ajustes incorpora respaldo/restauración manual, biblioteca de fuentes y límites comprensibles. No activación, cuentas, compra ni cambios de arranque.
- Impeccable: conservar contexto de sesión, leer playbook aplicable y craft-floor antes de escribir UI; verificar composición/teclado sin reemplazar la identidad.

**Close:** completar los cinco pasos, volver sin perder datos válidos, guardar, ejecutar, inspeccionar, duplicar, comparar, exportar y recuperar por copia manual. Rutas heredadas siguen accesibles.

### Q9 — Integración, documentación y aceptación [A1, P1, A2, F6 y conjunto]

**What/why:** demostrar el recorrido completo sin convertir checks parciales en aceptación global.

**How/files:**
- `webapp/README.md`, `PRODUCT.md`, `DESIGN.md` y `.impeccable/surfaces/route-laboratorios.md`: actualizar únicamente lo afectado y resolver su contexto obsoleto, preservando staging ajeno.
- **NEW:** guía de esquema de historial, bloques/reglas, exportaciones y respaldo/restauración bajo `docs/`; ejemplos pequeños sintéticos, sin fuentes privadas ni credenciales.
- Pruebas integradas en estado aislado, fidelidad de catorce plantillas, regresión de contratos existentes, suite final y navegador real.
- Documentar límites medidos y requisitos actuales de arranque, sin ZIP, instalador ni promesas de rendimiento universal.

**Close:** todos los requisitos enlazados a evidencia; toda ausencia/fallo/inconclusión declarada. Aceptación manual pendiente no se marca como aprobada por pruebas automáticas.

## ODD execution and ordering

1. **Aprobación primero:** este plan no autoriza source writes por sí solo. Releerlo tras aprobación; YOLO no anula esta etapa ni los permisos destructivos.
2. **Seguimiento grande antes del primer source write:** crear `odd/tasks/quiniela-configurable.md`, espejo Engram `odd/quiniela-configurable/tasks` y TODO desde esa fuente. Specs con los textos del usuario, tareas vinculadas, rutas/commits y Log con petición y corrección de ZIP verbatim. No extender artificialmente L1–L10 ya cerradas.
3. **Secuencia:** Q1 → Q2 → Q3 → Q4 → Q5 → Q6 → Q7 → Q8 → Q9. Dentro de Q8 separar pasos del asistente, resultados/trazas, comparación y Ajustes en unidades revisables; no una entrega frontend gigante.
4. **Rutas de trabajo:** una superficie compartida tiene un escritor. Delegar solo unidades pesadas independientes con Allowed edit surfaces disjuntas, o cuando se dispare el límite de contexto; no delegar lecturas que el padre repetirá para escribir inline. Workers sin commits ni despliegues.
5. **Test-first:** una regresión RED observada por regla aplicable, GREEN, refactor; pruebas del comportamiento existente que comparta código cambiado. No simular RED de componentes ya escritos.
6. **Verificación independiente:** perfiles/contratos, almacenamiento, motor, admisión concurrente, guardas y restauración activan riesgos de datos/seguridad/contrato/concurrencia. Verificador independiente después de checks propios, con el documento completo y estado aislado. Una indisponibilidad o proof agotada se informa y se pide decisión; sin reintentos ceremoniales.
7. **Commits locales:** un work-unit commit Conventional Commit por tarea terminada, pruebas/docs junto a conducta, commit registrado en tracking. Mantener la rama de feature y no incorporar staging ajeno; inspección del índice antes/después. No push, PR, merge ni deployment.
8. **Carga de revisión:** el conjunto superará 400 líneas. Dividir por contratos/motor/almacenamiento/UI/documentación, contabilizando todo el churn; no quitar evidencia para aparentar menor tamaño. Recomendar PRs encadenados solamente si el usuario luego decide publicarlos.
9. **RDD:** está apagado para este clon. No iniciar review nativo por una casilla TODO ni inventar recibos. Si el usuario lo activa, sus operaciones son adicionales a las comprobaciones funcionales.
10. **Estado protegido:** no ejecutar migraciones/restauración sobre la base normal desde herramientas del agente, detener previews del usuario ni modificar los insumos protegidos. Las pruebas usan estado desechable; el usuario decide cuándo usar funciones destructivas de la aplicación.

## Verification

### Ejemplos mínimos obligatorios por requisito

- **F1:** perfil 100/5 de referencia y perfil pequeño distinto; posiciones/universo/repetición/pagos inválidos rechazados; orden indiferente con premios desiguales rechazado; dinero fraccionario no representable rechazado. Ningún rechazo cambia datos/cuota/contadores.
- **D1:** JSON incluido completo y JSON canónico de otra quiniela; perfil incompatible, fecha inválida, duplicado conflictivo y hash cambiado entre preview/confirmación rechazados sin promoción parcial. Un historial distinto no obtiene rankings por coincidencia de etiqueta.
- **F2:** elección causal no cambia al modificar el resultado objetivo/futuro; mezcla suma 100; bloques incompatibles se bloquean. Fórmulas audaz/escalera contrastadas con referencia, no inferidas del nombre.
- **F3:** guardar/borrar/reiniciar/recrear desde plantilla; UUID nuevo y configuración completa; sin resiembra ni resultados ajenos. Duplicar conserva todos los parámetros y no muta el original.
- **F4:** dos corridas compatibles comparables; cambios de fuente/perfil/ventana/capital/cierre explicados y rechazados para comparación homogénea. Exportación completa más allá de páginas; configuración importada genera otra identidad.
- **F5:** saldo después = saldo antes − apostado + pagado en cada apuesta; sumar traza = totales de sesión/corrida; reinicios señalados; promedio excluye incompletas según contrato. Presupuesto insuficiente no produce falsa traza completa; cancelación/reinicio no generan completado ni reenvío duplicado.
- **D2:** respaldo consistente, restauración íntegra y conteos iguales; archivos corruptos, versión desconocida, referencias inválidas, cuota excedida, rutas peligrosas y expansión excesiva rechazados con destino intacto. Sin copias automáticas ni papelera.
- **U1:** validación en cada paso, volver/avanzar, dependencia invalidada explicada, foco/errores, revisión final y creación separada de ejecutar; duplicación y plantilla recorren los mismos cinco pasos.
- **A1/P1/A2/F6:** loopback y rutas heredadas conservados; sin cuentas, compras, apertura remota, paquetes/instaladores ni exploración automática de parámetros.

### Checks de desarrollo (solo después de aprobación)

- Preparar padres nuevos de basetemp bajo `.tmp/quiniela-configurable/<unidad>/` antes de cada corrida; nunca DB normal ni caché/bytecode de proyecto.
- Backend focalizado: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3.14 -B -m pytest <tests de la unidad> -q --tb=short -p no:cacheprovider --basetemp=<directorio nuevo preparado>`.
- Ruff sobre archivos cambiados: `py -3.14 -B -m ruff check --no-cache <paths>` y comprobación de formato.
- Frontend focalizado: `npm test -- --run <tests de la unidad>`; `npm run typecheck`; build al integrar UI.
- Cierre integrado Q9: una suite backend completa aislada, `npm test -- --run`, `npm run typecheck`, `npm run build`, fidelidad de los catorce y checks públicos de exportación/restauración. No repetir suites globales por cada subunidad.
- LSP activo sobre paths cambiados; diagnóstico ausente/inconcluso no se convierte en «limpio».
- Para checks cortos deterministas, timeout explícito hasta 30 s; duración larga/desconocida en background con salida/exit preservados. No pipelines que oculten el exit code detrás de `tail`.
- Navegador real en runtime aislado propiedad de la tarea: escritorio y ancho CSS real comprobado, teclado/foco/zoom, cinco pasos, estados vacíos/errores, resultado, selección de sesión/apuesta, comparación, exportación y respaldo/restauración de fixtures. Cerrar solo pestañas/procesos propios. Un fallo del navegador no demuestra fallo de aplicación ni aceptación visual.
- Fronteras de trabajo/detalle y tiempos observados con fuente incluida y perfil alternativo; no publicar cifras de rendimiento sin medición. Si no se puede conservar F5 íntegro dentro del presupuesto, informar el caso, no ocultarlo recortando datos.

## Out of Scope

- SaaS, acceso remoto, cuentas, roles multiusuario, pagos, activación/licencias técnicas, suscripciones.
- Trabajo de ZIP, runtime portable, instalación automática, aplicaciones nativas, nuevos launchers o soporte multiplataforma añadido.
- Juegos por combinaciones, acumulados, raspaditas, reparto de fondos u otras familias no quiniela.
- Código externo, plugins, editor de programación, entrenamiento/generación de rankings nuevos, promesas de predicción o rentabilidad.
- Importación CSV/Excel/PDF, conectores y actualización automática de fuentes en esta primera implementación.
- Grillas, optimización automática, lotes de variantes, Monte Carlo, automatización de apuestas.
- Papelera, recuperación individual, respaldos automáticos, fusión de respaldos o reanudación automática tras restaurar.
- Reescribir datos/resultados antiguos, modificar `repo_ref/`/`lagacy_loto/`, borrar rutas heredadas o limpiar cambios ajenos.
- Push, PR, merge, deployment o aceptación manual inventada.

## Planning phase status

- **Phase 1 — Explore:** cumplida con fuentes actuales y scout de solo lectura; rutas históricas inexistentes excluidas explícitamente.
- **Phase 2 — Clarify:** cumplida con una pregunta de entrega; el usuario excluyó ZIP/runtime del trabajo. El resto de decisiones propuestas está declarado arriba para aprobar o corregir, no oculto.
- **Phase 3 — Generate Plan:** este archivo. No se creó spec ni tracking de implementación.
- **Phase 4 — Notify & Execute:** notificar que el plan está listo y esperar aprobación explícita. Ejecución pendiente; ninguna fase de planificación omitida.
