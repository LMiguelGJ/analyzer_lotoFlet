# Quiniela — approved visual and logic improvements
Approved plan: `.pi/plans/mejoras-visuales-y-logicas-quiniela.md`; feature branch `feat/mejoras-quiniela`; delivery: auto-chain / feature-branch-chain (local reviewable slices only; no push/PR).
Runner: isolated `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3.14 -B -m pytest -p no:cacheprovider`; Vitest/tsc/Vite. Forecast >400 authored diff lines; preserve behavior/tests/docs together, no line-budget code golf.

## Specs

### S1 — Explicit implementation approval (verbatim)
> Plan completo guardado en:
>
>  C:/Users/luism/OneDrive/Escritorio/analyzer_lotoFlet/.pi/plans/mejoras-visuales-y-logicas-quiniela.md aplica el plan tal cual y estas mejorar usa odd en modo yolo vamos

### S2 — Approved U0 — Preparar una base recuperable, sin cambiar comportamiento


- Después de aprobar: releer este plan, comprobar Git y crear `feat/mejoras-quiniela` desde la base vigente. No descartar cambios, stashear, forzar ramas ni incluir archivos ajenos.
- Materializar la limpieza ya aceptada como baseline explícita: `webapp/frontend/index.html`, `src/components/Shell.tsx`, `Shell.test.tsx`, `src/pages/laboratories/LaboratoryPanel.tsx`, `Workspace.test.tsx` y el documento histórico `odd/tasks/laboratory-interface-copy.md`. No confundir ese baseline con el delta correctivo de Judgment Day.
- Crear recién entonces `odd/tasks/mejoras-visuales-y-logicas-quiniela.md`, espejo Engram y TODO de implementación. Incluir requisitos literales, IDs de este plan, rutas permitidas, estados y commits por unidad. El TODO de esta sesión es solo de planificación.
- Si el diff cambió desde la exploración, reconciliar su autoría y alcance antes de preparar commits. No agregar `.env`, datos, `.tmp`, insumos congelados ni directorios de usuario.


### S3 — Approved U1A — Admitir completos los resultados válidos de laboratorios propios


**Archivos:** `webapp/backend/laboratorio/storage/reference_lab_store.py`, `owned_laboratory_run_store.py`, `api/laboratory_runs.py`; tests owned y de referencia indicados en Verification.

- Parametrizar el validador compartido con un límite de sesiones explícito, keyword-only, cuyo valor predeterminado siga siendo 50.000. Mantener intacto el comportamiento de las rutas históricas/de referencia.
- En escritura Y lectura owned, derivar el límite de `eligible_draws` del resultado generado sobre la referencia verificada; validar tipo entero estricto, no booleano, rango no negativo e invariantes existentes. Exigir `sessions_total <= eligible_draws`; cero elegibles permite cero sesiones. No codificar 65.235 como tope ni usar un límite arbitrariamente enorme.
- Mantener MAX_PAYLOAD_BYTES, cuota transaccional, identidad del propietario, snapshot, sumas, digest y comparación de copias. No cambiar selección, premios, apuestas o cierres.
- Cuando el resultado cabe en cuota y bytes, guardar TODAS sus sesiones. Si excede bytes reales, distinguir capacidad de datos inválidos mediante una excepción owned específica y respuesta 409 con «El resultado completo supera el límite de almacenamiento de una corrida.». Mantener el mensaje de cuota vigente y los conflictos de definición/identidad.
- Extender `webapp/README.md` en la sección de laboratorios y límites; distinguir referencia/legacy de owned. No prometer que cualquier ejecución cabe en cualquier cuota.
- RED público principal: cobertura 50, plana, capital 50, meta 51, premios `[1,1,1,1,1]`, ventana completa. Antes falla al guardar; después debe responder 201 y conservar las 65.235 sesiones si los límites reales lo permiten. Recorrer todas las páginas públicas para comprobar conteo, ordinales, cierres y ausencia de truncamiento.
- Verificar también el segundo contraejemplo (cobertura 1, capital 1, meta 2, premios de 2), ventanas pequeñas/cero elegibles y rechazo por cuota/bytes sin filas parciales ni incremento de contadores/uso.


### S4 — Approved U1B — Clasificar escrituras de resultado incierto sin romper el cliente común


**Archivos:** `webapp/frontend/src/api/client.ts`, `client.test.ts`, `src/pages/laboratories/LaboratoryPanel.tsx`, `Workspace.test.tsx`.

- Conservar `ApiError`, `status`, `detail`, `fieldErrors`, errores HTTP, GET ilegible, 204 y la identidad de AbortError. Agregar una marca booleana aditiva `uncertainWrite`, falsa por defecto; no reemplazar globalmente ApiError por NetworkError.
- Si falla la lectura/decodificación NO-abort del cuerpo exitoso de un método de escritura, adjuntar `uncertainWrite:true`. La respuesta 201 no prueba que la escritura falló. GET/HEAD ilegibles mantienen su clasificación anterior, sin esa marca.
- El panel debe tratar la marca como incertidumbre, conservar el mensaje existente «No hay confirmación de si el servidor guardó esta ejecución…» y bloquear otro POST. No reintentar automáticamente.
- Preservar el descarte de respuestas de componentes desmontados y el tratamiento de cancelaciones; no crear un mecanismo general de reintentos o nuevas promesas de idempotencia.
- Documentar la semántica en los comentarios del cliente; la documentación de operación se consolida después en U6 para no solapar superficies con U1A.
- RED a través de `request()` y del workspace, sin sustituir el problema por un mock de createLaboratoryRun: respuesta HTTP 201 con `json()` rechazado. Deben ocurrir un solo POST, aviso de incertidumbre y botón bloqueado, incluso ante otro clic.


### S5 — Approved Gate JD — cerrar primero los dos severos, sin ampliar la corrección


- La aprobación explícita de este plan habilita la primera ronda correctiva SOLO de JD-001/JD-002; no autoriza corregir INFO dentro del actor JD ni publicar cambios.
- U1A/U1B pueden ejecutarse en paralelo mediante dos `jd-fix-agent` con superficies disjuntas backend/frontend; cada uno recibe el documento ODD, IDs y pruebas. No comparten archivos de documentación.
- Congelar el delta correctivo respecto de U0 y usar ambos jueces ciegos con el ledger original y ese delta solamente. No sumar U2–U6 al delta JD ni hacer una nueva revisión general disfrazada.
- Como máximo dos rondas de corrección y dos rejuzgamientos acotados. Si quedan severos, contradicciones o prueba insuficiente, ESCALATED y decisión humana; sin reintentos ilimitados ni refuter.
- Una aprobación JD cubre ese delta, no futuras mejoras ni entrega. No ejecutar 4R ordinario sobre el mismo objetivo; RDD continúa bajo el interruptor humano, sin inventar recibos.


### S6 — Approved U2 — Reconciliar antes de volver a habilitar ejecución


**Archivos:** `LaboratoryPanel.tsx`, `Workspace.test.tsx`.

- Incorporar estado explícito `reconciling`. «Actualizar corridas guardadas» NO borra `uncertain` al hacer clic.
- Consultar una lista nueva desde offset 0; no considerar reconciliación los datos retenidos ni una respuesta anterior. Solo la respuesta exitosa de esa consulta vigente libera incertidumbre. Abortar/ignorar respuestas tardías de otro laboratorio o solicitud cancelada.
- Durante la consulta, bloquear Ejecutar y nuevos clics de reconciliación. Si falla, conservar incertidumbre, permitir reintentar la consulta y no emitir otro POST.
- Mantener la lectura de resultados anteriores y la confirmación de borrado con contador. No inferir éxito de escritura porque exista cualquier corrida anterior.
- Separar la consulta del detalle inmutable y la página de sesiones: cambiar de página debe solicitar solamente sesiones, conservar cabecera/detalle y mostrar carga/error en esa zona. Cambiar corrida sí carga ambos; Reintentar refresca solo lo que falló.
- RED: reconciliación diferida, rechazada, exitosa, respuesta obsoleta al cambiar laboratorio y abort; demostrar bloqueo hasta el éxito vigente y exactamente un nuevo envío solo tras una acción posterior del usuario.


### S7 — Approved U3 — Paginar SQL conservando detección de corrupción


**Archivos existentes:** `storage/database.py`, `repository.py`, `owned_laboratory_run_store.py`, `api/laboratory_runs.py` y tests de migración/store/list/API.
**Nuevos:** `storage/migrations/0020_owned_run_integrity_epoch.sql` y `storage/owned_laboratory_read_cache.py`.

- Migración ADITIVA 20: una fila operativa de época de integridad y triggers que incrementan esa época al insertar/modificar/eliminar metadatos/resultados de corridas o filas de sesiones. Cubrir cambios de ordinal, run_id, owner y borrados en cascada. Invalidar también por escrituras de referencia es aceptable y conservador.
- No reescribir result_json, sesiones, snapshots ni identidades; no backfill de resultados, escaneo al arranque, sustitución de formatos ni migraciones anteriores editadas. Mantener la siembra única de versión 17: no recrear laboratorios eliminados al pasar a 20.
- LRU por instancia de Repository: máximo 64 entradas Y 16 MiB de payload cacheado, lo que se alcance primero. Clave con identidad del repositorio/base, época, owner y run_id. Proteger estado concurrente; sin caché global entre bases ni conexiones permanentes.
- Guardar únicamente snapshot/resumen validados compactos y huellas SHA-256 de filas canónicas en un bloque `bytes` de 32 bytes por ordinal. Nunca retener listas de sesiones ni el result_json completo. Si una entrada excede el presupuesto, no cachearla; no rechazar la corrida por eso.
- Cada lectura usa una transacción consistente: leer época y datos desde la MISMA instantánea SQLite. Caché fría o época diferente: ejecutar la validación completa existente de todas las copias/sumas/digest antes de certificar el resumen y las huellas. Una mutación relevante invalida las entradas anteriores.
- En caliente: listar solo IDs/resúmenes de la página; detalle desde resumen compacto; sesiones por `ORDER BY ordinal LIMIT ? OFFSET ?`. Validar cada fila recuperada y comparar su huella canónica con la certificada. Conservar el método completo existente para sus consumidores; crear métodos compactos explícitos para los endpoints, sin cambiar DTO público.
- Un resumen persistido sin invalidación NO es suficiente: ocultaría corrupción fuera de página. Este diseño conserva el coste frío O(todas las sesiones), pero evita repetirlo en cada página; no prometer O(página) en frío.
- Preservar el alcance anterior: validar las corridas visibles del propietario consultado, no fallar un listado por una corrida ajena o fuera de página que antes no se leía.
- GET no escribe certificaciones en SQLite. La época es infraestructura, no un nuevo artefacto de usuario imputable como sesión. Mantener intacta la contabilidad de payload/cuota existente.
- No hay nueva garantía contra alguien que reemplace una base en caliente o falsifique/desactive los triggers mediante SQL adversarial; ya se exige detener la app para reemplazar/copiar SQLite. Las mutaciones SQL normales, incluso desde otra conexión, sí deben invalidar.


### S8 — Approved U4 — Resultado legible, ROI y procedencia bajo demanda


**Archivos:** `LaboratoryPanel.tsx`, `laboratories.css`, `Workspace.test.tsx`, `src/api/laboratories.ts` y sus fixtures/tests tipados.
- Completar el tipo TypeScript de `snapshot.provenance` con `rankings_sha256`, que el codec backend `domain/laboratory_run_snapshots.py:45–48` YA devuelve; actualizar los mocks tipados correspondientes. No es un campo nuevo del API ni se inventa una huella.
**Nuevos:** `src/pages/laboratories/result-model.ts` y `result-model.test.ts` para cálculo/presentación pura local.

- Cambiar Cobertura a «25 números seleccionados» (singular para 1). En Paridad, «50 números seleccionados»; el sistema indica Paridad. Conservar en el formulario el límite 1–50. No presentar el límite como universo ni como probabilidad.
- Neto total primero y destacado; al lado, «Retorno sobre apostado». Después Apostado/Pagado/Media neta de cerradas; los cuatro contadores de cierre forman un grupo secundario. No cambiar las ocho magnitudes originales ni calcular otra media; el ROI es la novena métrica, derivada solo para presentación.
- ROI histórico = `100 * total_net / total_wagered`, incluyendo incompletas igual que el neto. Dos decimales, signo y coma decimal; dividir antes de multiplicar para evitar un intermedio entero innecesariamente grande. Normalizar cero negativo. Con cero apostado: valor nulo y «No disponible», nunca NaN/Infinity ni 0 % inventado.
- Ejemplos: −1.482.496 sobre 30.303.350 → «−4,89 %»; 50 sobre 100 → «+50,00 %»; cero sobre 100 → «+0,00 %»; cero apostado → «No disponible».
- No agregar return_pct al API ni cambiar `lib/format.ts:formatPercent`, que recibe puntos porcentuales y usa un decimal para otros consumidores.
- Datos compactos: «Sorteos evaluados» y «Sin ranking entre extremos», basados exactamente en eligible_draws/gaps. No afirmar que gaps cuenta todos los excluidos de la ventana.
- Desplegable nativo `<details>` «Datos de la reproducción»: tramo efectivo first/last, ventana configurada y las huellas completas de historial/rankings/sesiones. Cero elegibles: «Sin sorteos elegibles», extremos no disponibles y encabezado «Sesiones 0 de 0»; no rango 1–0.
- Estilos SOLO locales a `.lab-stage`/`.lab-result`: adaptación al contenedor, no cuatro columnas forzadas por viewport. Neto de 16–32 px según espacio, grupos que bajan a una columna cuando no caben; no partir cantidades. Importes y encabezados monetarios alineados a la derecha, cifras tabulares y signo/RD$ intactos; fecha, cierre y acciones a la izquierda.
- Mantener tablas desplazables horizontalmente, sin overflow de la página. No cambiar globalmente `th,td`, los tokens, la tipografía ni la presentación de rutas antiguas/de referencia.
- No restaurar ninguno de los seis párrafos eliminados, ni reemplazarlos por otra pared de texto.


### S9 — Approved U5 — Orden semántico responsive y corrección accesible


**Archivos:** `Workspace.tsx`, `LaboratoryForm.tsx`, `laboratories.css`, `Workspace.test.tsx`.

- Eliminar `order:-1`. Usar el mismo breakpoint existente de 860 px para decidir el orden REAL de dos elementos con keys estables: escritorio sidebar→panel; móvil con laboratorio/nuevo panel→sidebar; sin selección lista→estado vacío.
- Leer cambios de matchMedia y limpiar su listener. Mantener montadas las mismas instancias con keys estables: redimensionar no borra un formulario, selección o página ni dispara ejecuciones. Restaurar el foco al mismo elemento conectado si moverlo lo pierde; no enfocarlo de nuevo en cada render.
- Ofrecer destino de foco estable en el panel. Tras navegación iniciada por el usuario desde un enlace de laboratorio/Nuevo, enfocar ese destino; no robar foco en carga inicial, refresh de datos o paginación.
- Al enviar formulario inválido: resumen breve con `role="alert"`, enlaces a los campos y foco al primer inválido en orden visual, después de que el DOM tenga sus errores. Reutilizar IDs/etiquetas y las asociaciones aria-describedby existentes; no modificar el contrato compartido de Field para un caso local.
- Conservar valores y errores útiles; no POST si falla validación. No introducir onboarding, tooltips obligatorios o explicaciones estáticas nuevas.


### S10 — Approved U6 — Documentación, compatibilidad y aceptación final


- Actualizar `webapp/README.md`: nombre Quiniela, esquema 20, límite owned frente a referencia, incertidumbre/reconciliación, ROI/nulos, cobertura/gaps y coste frío/caliente. Las advertencias de reproducción histórica quedan en documentación, no reaparecen como los seis párrafos retirados.
- Actualizar solo secciones obsoletas relacionadas de `PRODUCT.md`, `DESIGN.md` y `.impeccable/surfaces/route-laboratorios.md`: marca, navegación, capacidades realmente entregadas y dirección visual preservada. No reescribir documentos por gusto ni prometer nuevas estrategias.
- Verificador independiente funcional sobre todos los criterios, por riesgo de persistencia, cliente compartido, concurrencia y migración. Datos aislados, interfaces públicas y fallos/ausencias reportados. No reemplaza ni reinicia el presupuesto de JD.
- Readback de cada requisito, evidencia por unidad y estado real en ODD/Engram/TODO. No declarar completada una prueba visual, móvil, de teclado o regresión no observada.


### S11 — Approved constraints, verification and exclusions (verbatim)

#### Assumptions & Decisions

1. Alcance: dos severos + ocho INFO + ROI. Se preserva la libreta fría, Archivo/Archivo Narrow, tinta, rojo funcional, controles cuadrados y marca Quiniela. No es un rediseño.
2. Se favorece guardar íntegros resultados válidos dentro de cuota/bytes, no prohibir configuraciones útiles para ocultar el límite incoherente.
3. SQL paginado estricto e integridad requieren invalidación explícita; elegida época+LRU, no un backfill de resúmenes ni confianza ciega en un hash almacenado.
4. La migración 20 es nueva; no editar 1–19. Los contratos/snapshots v1 siguen en v1: versión de SQLite y versión de DTO no son lo mismo.
5. ROI es presentación derivada, no nuevo resultado persistido. Cierres/metas no se presentan como probabilidades futuras.
6. No hay preguntas de producto pendientes: las decisiones conservan comportamiento, estética y datos; la fase Clarify quedó resuelta con exploración y un contraste técnico de solo lectura.
7. El plan prevé más de 400 líneas totales: dividir en slices revisables, idealmente ≤400 líneas de diff cada una, con tests/docs junto a su comportamiento. Si luego se piden PR, usar PR encadenados; no crear un PR gigante ni publicar sin decisión de entrega.
8. Orden: U0 → U1A/U1B en paralelo → gate JD → U2 → U3 → U4 → U5 → U6. Cada unidad tiene commit propio; dividir U3 en migración, lector/cache y endpoints si supera el tamaño revisable, manteniendo dependencias compatibles.
9. Tras aprobar se crean los artefactos ODD de implementación; ahora solo existe este plan. Workers con superficies permitidas disjuntas; parent actualiza tracking y conserva autoridad de integración.
10. No ejecutar migraciones, bootstrap, fixtures ni nuevas corridas sobre `%LOCALAPPDATA%/LaboratorioQuiniela`. El permiso previo de arranque no equivale a autorizar una nueva migración de usuario. Probar con datos aislados; pedir autorización específica antes de aplicar 20 a la base normal o reiniciar contra ella.

#### Verification

### RED/GREEN y criterios públicos

- **U1A:** contraejemplos completos, límites 0/1/50.000/>50.000/elegibles, tipos inválidos, cuota/bytes; HTTP y mensajes exactos; rechazo deja definiciones/corridas/sesiones/uso sin cambios. Consultar todas las páginas para la corrida grande. Referencia conserva su límite anterior.
- **U1B:** POST 201 ilegible bloquea repetición; GET JSON ilegible sigue ApiError; HTTP 404/409/422 y fieldErrors intactos; 204 sin cuerpo; AbortError conserva identidad; fallo de red ya cubierto sigue funcionando. Un solo POST por clic válido, sin reintentos.
- **U2:** promesas diferidas, errores y respuestas obsoletas no desbloquean; solo una lista fresca exitosa lo hace. Cambiar página no vuelve a descargar detalle inmutable ni muestra totales de otra corrida.
- **U3:** schema19→20 y nueva base sin resembrar borrados ni cambiar JSON/huellas; rollback de migración fallida. Corrupción fuera de la página, resumen o snapshot aún da 409 tanto en frío como después de una lectura caliente seguida de INSERT/UPDATE/DELETE, otra conexión y cascadas. Owner ajeno y corrida inexistente conservan respuestas anteriores.
- **U3 rendimiento:** medir filas/consultas recuperadas, no solo JSON de salida. Primera lectura valida todo; siguientes recuperan únicamente página y metadatos. Cubrir más de64 entradas, presupuesto16MiB, cambio de época, repositorios distintos y ausencia de sesiones completas retenidas. No imponer latencias arbitrarias ni llamar O(página) a la lectura fría.
- **U4:** ROI positivo/negativo/cero/cero apostado/redondeo y cero negativo; media cerrada e incompletas iguales al baseline; labels de cobertura, tres SHA íntegros en disclosure, eligible/gaps y nulos exactos; todos los párrafos retirados siguen ausentes y la marca sigue Quiniela.
- **U5:** DOM/Tab coinciden a860 y861 px, input/selección/foco sobreviven redimensionado, no GET/POST extra por reordenado; formulario inválido no envía, anuncia errores y enfoca el primero; envío válido/conflicto y borrado con confirmación siguen funcionando.

### Archivos de pruebas

- Backend existentes: `test_owned_laboratory_run_insert.py`, `test_owned_laboratory_run_store.py`, `test_owned_laboratory_run_list.py`, `test_owned_laboratory_runs_api.py`, `test_reference_lab_store.py`, `test_reference_lab_runs_api.py`, `test_laboratory_migrations.py`.
- Frontend existentes: `src/api/client.test.ts`, `src/api/laboratories.test.ts`, `src/pages/laboratories/Workspace.test.tsx`, `form-model.test.ts`, `src/components/Shell.test.tsx`; nuevo `result-model.test.ts`.
- Fixtures y corrupción deliberada solo en SQLite temporal. Afirmar efectos a través de API/UI, no conformarse con inspección de arrays privados o estructura de caché; complementar el caso de memoria con instrumentación acotada.

### Comandos previstos — NO ejecutados al redactar

Desde `webapp/backend`, con `<run-id>` nuevo y logs FUERA del basetemp:
```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3.14 -B -m pytest -p no:cacheprovider --basetemp=../../.tmp/mejoras-quiniela/<run-id>/pytest-focused tests/test_owned_laboratory_run_insert.py tests/test_owned_laboratory_run_store.py tests/test_owned_laboratory_run_list.py tests/test_owned_laboratory_runs_api.py tests/test_reference_lab_store.py tests/test_reference_lab_runs_api.py tests/test_laboratory_migrations.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 py -3.14 -B -m pytest -p no:cacheprovider --basetemp=../../.tmp/mejoras-quiniela/<run-id>/pytest-full
```
Desde `webapp/frontend`:
```bash
npm test -- --run src/api/client.test.ts src/api/laboratories.test.ts src/pages/laboratories/Workspace.test.tsx src/pages/laboratories/form-model.test.ts src/pages/laboratories/result-model.test.ts src/components/Shell.test.tsx
npm test -- --run
npm run typecheck
npm run build
```
- Ruff check/format-check sobre archivos Python modificados; LSP activo de paths cambiados y `git diff --check`. No convertir un cache vacío o un spellchecker informativo en prueba de workspace global limpio.
- Suites/builds de duración larga o incierta en background desde el inicio, sin polling ni reinicio automático después de timeout. Conservar RED, GREEN, stdout, stderr y códigos; no «arreglar» pruebas debilitándolas.

### Navegador y datos normales

- Para navegador aislado, usar las variables EXISTENTES `LABORATORIO_DATA_DIR` con ruta absoluta bajo `.tmp/mejoras-quiniela/<run-id>/data` y `LABORATORIO_PORT=8766`, comprobando que el puerto esté libre; si está ocupado no matar procesos ajenos. Registrar cómo detener solo ese servidor.
- Usar la misma pestaña Orca `661c5ab6-7f5f-4073-b5b6-d5e7e0eaf25f`; navegar temporalmente al servidor aislado con fixtures. No abrir otra pestaña/instancia ni ejecutar o borrar resultados normales para QA. Al finalizar, detener el servidor aislado y restaurar la URL original.
- Probar360,768,860,861,900,1024 y1607 px, zoom200 %, teclado y contraste/foco. La tabla puede desplazarse, la página no; dinero sin cortes y controles de48px. Capturar/inspeccionar imágenes fiables y registrar dimensiones reales.
- Si la automatización visual continúa defectuosa, reportarla una vez como no disponible y pedir validación manual; no dar PASS, repetir capturas indefinidamente ni cambiar CSS para compensar un fallo de herramienta.
- Aplicación final a datos normales y eventual commit/push/PR de entrega quedan sujetos a sus permisos: no se deducen de una revisión ni de que se haya escrito este plan.

#### Out of Scope

- Q3–Q9 del roadmap configurable, ampliar Q1/Q2, nuevos motores/rankings, cambiar reglas financieras, Monte Carlo, pronósticos o promesas de ganancia.
- Gráficos, exportación, comparación de corridas, cuentas, nube, plugins, empaquetado, instaladores o dependencias nuevas.
- Eliminar o corregir datos existentes, tocar `.env`, editar los insumos congelados o sobrescribir `repo_ref/`/`lagacy_loto/`.
- Reintroducir el nombre viejo, textos redundantes retirados, falsas trazas por apuesta o nuevos claims de verificación.
- Reparar Orca/las herramientas de revisión como parte del producto.


## Tasks

- T0 — U0 recoverable baseline and ODD; S1–S2,S11; route: inline (existing narrow copy changes, no new behavior); status: done; commits: e9fd0513a895ad01bf1f04cc9dd0e4827ce43da7 (preserved UI baseline), a60cb3dded529cdeb5f5bd98295229b9bab6a4ab (approved plan/tracking); focused23PASS/job14exit0.
- T1 — U1A/U1B confirmed severe corrections in parallel; S3–S4,S11; route: two jd-fix-agent workers, disjoint backend/frontend; status: blocked; commits: none; RED/GREEN: not run; waiting for JD dispatch compatibility resolution or an explicit authorized route change: frozen ERROR rows cannot pass the host BLOCKER/CRITICAL-only guard.
- T2 — Functional independent verification and scoped JD gate; S3–S5,S11; route: gentle-ai-verify then two blind judges; status: pending; commit: pending.
- T3 — U2 reconcile and separate immutable detail/session loading; S6,S11; route: inline (dependent frontend unit); status: pending; commit: pending.
- T4 — U3 additive migration20 integrity epoch; S7,S11; route: inline (ordered schema dependency); status: pending; commit: pending.
- T5 — U3 bounded read certificate/cache and SQL endpoints; S7,S11; route: inline (dependent reader); status: pending; commit: pending.
- T6 — U4 financial hierarchy/ROI/coverage/provenance; S8,S11; route: inline (dependent panel); status: pending; commit: pending.
- T7 — U5 semantic responsive order and accessible validation; S9,S11; route: inline (dependent workspace); status: pending; commit: pending.
- T8 — U6 docs, full regression, independent acceptance and isolated same-tab browser QA; S1–S11; route: inline docs + gentle-ai-verify, browser via Orca; status: pending; commit: pending.

## Log

### L1 — Original implementation request (verbatim)

> Plan completo guardado en:
>
>  C:/Users/luism/OneDrive/Escritorio/analyzer_lotoFlet/.pi/plans/mejoras-visuales-y-logicas-quiniela.md aplica el plan tal cual y estas mejorar usa odd en modo yolo vamos

### L2 — Authorization and reconciled starting state
- Explicit plan approval activates implementation and round1 of2 corrections for JD-001/JD-002 only. It does not authorize normal-data migration, restarting against that database, push, PR, or scope expansion.
- Starting branch master, HEAD19a08edce6b4aa1e6ee70aba5247334fd9100e84. Exactly the five expected frontend edits, the earlier copy task file and approved plan are present; no staged/foreign edits.
- Preserve all existing files/data and frozen inputs. No .env reads, no user-database writes. Existing visual capture failures remain honest limitations, not visual PASS.
- RDD off. JD frozen ledger SHA2560226bcdb567ebb1874b33ae605473c4262ef897a7a928adf2a1cffd81a4cf69f; correction round1 of2,0 new rejudgments used.
- Delivery planning: bounded local work-unit commits on feature branch; forecast exceeds400 lines; chain strategy feature-branch-chain only if publication is later requested. No publication now.
- Session metadata publication unavailable (`session messaging is not ready`); no peer work/delegation authority inferred from it.

### L3 — Baseline check timeout; no retry or implementation
- Ran once from the project root: `cd webapp/frontend && npm test -- --run src/pages/laboratories/Workspace.test.tsx src/components/Shell.test.tsx`, synchronous timeout30 seconds.
- Observed stdout: npm script `vitest --run src/pages/laboratories/Workspace.test.tsx src/components/Shell.test.tsx`; `RUN v5.0.2 C:/Users/luism/OneDrive/Escritorio/analyzer_lotoFlet/webapp/frontend`. No test results were returned.
- Tool outcome: `Command timed out after 30 seconds`. No numeric exit code or separate stderr was supplied. This is failed verification due to timeout, not proof of failing assertions or an application regression.
- No automatic retry, restart or migration of that command to background. No actors launched, baseline commit made, new product source edited, dependency/configuration changed, normal database accessed/migrated, or push/PR performed.
- Only new implementation artifacts so far: feature branch and this tracking document/mirror. The approved plan and prior frontend modifications remain preserved.
- Needs your decision at that point: authorize a fresh baseline verification with an explicitly larger execution budget before U0 can close and U1 correction actors can start. All dependent tasks remained pending, not completed.

### L4 — Explicit continuation and fresh verification approval
User, verbatim:
> hazlo si nunca pares me ire a dormir tienes todas las autorizaciones modo yolo
- Reopened T0. This explicitly authorizes a fresh baseline run without the30s synchronous cutoff and continuation of the approved plan. Use background execution from the start and wait for its exit event; no polling, automatic retries or duplicate actors.
- Ordinary in-scope local decisions and work-unit commits need no further routine confirmation. Preserve the approved plan's data protections, bounded JD budget and separate delivery boundary; do not infer permission to erase data or bypass provider consent.

### L5 — U0 observed completion and bounded correction launch
- Fresh authorized background job14 exit0 after9s: two files/23testsPASS, Vitest6.81s. Prior30s timeout retained as a separate failed verification attempt, not erased.
- Baseline commit e9fd0513a895ad01bf1f04cc9dd0e4827ce43da7 preserves the five UI changes and historical copy tracking;6files,+258/−8. Source/test behaviors already requested, runtime test boundary is workspace/Shell DOM. No claim of new screenshot/mobile proof.
- First staged diff check caught an extra blank line at EOF in the historical task file (exit2); removed only redundant trailing whitespace, then staged check and commit succeeded. No historical factual text rewritten.
- U0 rollback boundary: six baseline paths only; reverting does not affect new corrections/data. Risk:none for the preserved copy changes. Full frontend161PASS/types/build proof remains historical; fresh check is23PASS only.
- Approved plan plus current feature tracking are a separate passive docs commit. Their naturally >400line documentation scope is disclosed; preserve full approved requirements rather than deleting evidence to fit a heuristic.
- T1 route reason: two independently substantial confirmed corrections have disjoint backend/frontend surfaces and were submitted together. Only causal JD-001/JD-002, round1of2; original ledger remains immutable. Subsequent INFO work waits for gate.

### L6 — Pre-allocation JD guard incompatibility; not a permission prompt
- U0 tracking/plan commit succeeded as a60cb3dded529cdeb5f5bd98295229b9bab6a4ab; this is the intended corrective-delta baseline. Its staged guard first caught empty-quote trailing spaces/EOF in the new Markdown; formatting-only correction succeeded, with the verbatim text and requirements intact.
- Both scoped jd-fix-agent submissions were rejected before allocation. First Promise.allSettled rendering hid Error.message as an empty object. One task-inventory read confirmed no new tasks; a single diagnostic resubmission of the exact unchanged envelopes captured the guard error. No actor ran, no corrective source write happened, no correction/rejudgment budget was consumed.
- Guard states that frozen open rows must be BLOCKER/CRITICAL and the supplied SHA256 must match the canonical exact-row section. Original judge rows JD-A-001/JD-B-001/JD-A-002/JD-B-002 have severity ERROR. Original complete ledger file hash remains0226bcdb567ebb1874b33ae605473c4262ef897a7a928adf2a1cffd81a4cf69f, not a per-subset row-section hash. Neither severity promotion nor invented canonical replacement is authorized.
- No further submissions, new general review, generic fix-writer substitution, review-tool repair, source changes or normal-data operation. Preserve the two original reports/ledger unchanged. The approved plan requires this gate before U2–U6, so do not skip it under unattended YOLO.
- Evidence: .tmp/mejoras-quiniela/jd-dispatch/{u1a-prompt.md,u1b-prompt.md,errors.json}. T1 blocked on external guard/protocol compatibility or explicit human route decision; T2–T8 remain pending. This is not a request for another routine implementation approval.
