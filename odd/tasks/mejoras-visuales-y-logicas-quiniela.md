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


### S5 — Explicitly amended correction and verification route

User selected, verbatim:
> Cambiar la ruta de corrección — recomendada

Selected option, verbatim:
> Mantener intactos los informes originales.
> Corregir los dos errores con workers normales, pruebas RED/GREEN y verificación independiente.
> Continuar después con las demás mejoras.
> Registrar que **el gate JD no se completó**, sin inventar una aprobación.

- This explicit amendment supersedes the original plan's jd-fix-agent and scoped re-judgment requirement. Use two normal gentle-ai-worker instances for U1A/U1B with disjoint allowed surfaces. Preserve all functional requirements in S3/S4 and all data/compatibility protections.
- After self-checks, assess each work-unit diff and preserve required independent functional verification; the parent checks the seam. S13 explicitly supersedes the original ordering gate: U2→U4→U5 may proceed before U1 acceptance; U1/U3 and absent verification remain pending, never approved.
- Preserve the original frozen judge reports, ledger, ERROR severities and zero corrective/rejudgment counters unchanged. Original JD remains ESCALATED / not completed, never APPROVED.
- No JD actor, new blind re-review, ordinary4R substitute, harness repair or schema/severity conversion is requested by this amendment. RDD remains off. Delivery and normal-data protections remain unchanged.

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


### S11 — Approved constraints, verification and exclusions (original text except route amended by S5)

#### Assumptions & Decisions

1. Alcance: dos severos + ocho INFO + ROI. Se preserva la libreta fría, Archivo/Archivo Narrow, tinta, rojo funcional, controles cuadrados y marca Quiniela. No es un rediseño.
2. Se favorece guardar íntegros resultados válidos dentro de cuota/bytes, no prohibir configuraciones útiles para ocultar el límite incoherente.
3. SQL paginado estricto e integridad requieren invalidación explícita; elegida época+LRU, no un backfill de resúmenes ni confianza ciega en un hash almacenado.
4. La migración 20 es nueva; no editar 1–19. Los contratos/snapshots v1 siguen en v1: versión de SQLite y versión de DTO no son lo mismo.
5. ROI es presentación derivada, no nuevo resultado persistido. Cierres/metas no se presentan como probabilidades futuras.
6. No hay preguntas de producto pendientes: las decisiones conservan comportamiento, estética y datos; la fase Clarify quedó resuelta con exploración y un contraste técnico de solo lectura.
7. El plan prevé más de 400 líneas totales: dividir en slices revisables, idealmente ≤400 líneas de diff cada una, con tests/docs junto a su comportamiento. Si luego se piden PR, usar PR encadenados; no crear un PR gigante ni publicar sin decisión de entrega.
8. Orden actualizado por S13: avanzar U2 → U4 → U5 sin declarar aceptado U1; U3 y la evidencia independiente faltante permanecen pendientes. Cada unidad conserva su commit local; no migrar datos normales ni publicar. S13 delega mayormente QA manual al usuario, sin convertir comprobaciones omitidas en PASS.
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


### S12 — Explicit request to reactivate the app and explain manual checks
> vamos levanta todo otra vez dime que tipo de pruebas pues la mayoria la puedo hacer yo manual

### S13 — Explicit approval of reordered UI implementation and mostly manual QA
Accepted proposal, verbatim:
> ¿Autorizás cambiar el orden y seguir con **U2 → U4 → U5**, manteniendo explícitos los pendientes de verificación?
User, verbatim:
> hazlo asi pues esta bien ojo las prouebas las hare yo manuel en su mayoria asi que omitelas ya

- Proceed in that order; defer U3 and retain unresolved U1 acceptance. User owns manual browser/visual QA. Do not rerun blocked/full suites or claim manual/skipped checks passed; retain only minimal required focused safety/type checks. No storage/backend changes or normal-data operations.

### S14 — Explicit continuation and human next steps
> hazlo y dime que debo hacer yo continua con el odd y modo yolo

- Continue the already-approved documentation portion of S10 for delivered U2/U4/U5 and give a concrete manual QA checklist. S13 still defers U3; no claim of schema20/cache, no normal-data changes, no blocked/full test or verifier retry. Preserve pending U1A source/README changes separately from this documentation commit.

### S15 — Explicit visual acceptance and reopening of technical closure
User, verbatim:
> siii lo veo super bien perfecto continua termina con el odd

Clarification selected by the user, verbatim:
> Completar el plan técnico
> Autorizar retomar U3 y recuperar la verificación de U1 con pruebas focalizadas en datos aislados, sin tocar tu base normal ni relanzar suites amplias.

- General visual acceptance only, not claimed execution of M1–M7 or independent functional PASS. Reopen S7/U3 implementation and focused U1 recovery, superseding only S13/S14's deferral/backend exclusion. Keep normal-data, broad-suite, frozen-input, delivery and JD protections unchanged.
- Before any fresh U1 execution, establish no old matching check process remains; no duplicate, process termination or inference from missing registry. Preserve old evidence and source changes. New focused isolated checks/independent verification are explicitly authorized, not automatic retries. ODD cannot close until actual evidence or a clearly reported unavailable blocker.

## Tasks

- T0 — U0 recoverable baseline and ODD; S1–S2,S11; route: inline (existing narrow copy changes, no new behavior); status: done; commits: e9fd0513a895ad01bf1f04cc9dd0e4827ce43da7 (preserved UI baseline), a60cb3dded529cdeb5f5bd98295229b9bab6a4ab (approved plan/tracking); focused23PASS/job14exit0.
- T1 — U1A/U1B logic corrections with normal workers; S3–S5,S11; route: disjoint normal workers; status: blocked; U1B commit fbe48a7450f5fdd68d82b8646f0d2feec7c7cb93 with writer25focused/163fullPASS/types0 and parent readback, independent proof unavailable; U1A task mv8np9vu-5-aney is now absent from runtime inventory, backend partial edits preserved; waiting for restored worker control/usable independent verification; no blind replacement.
- T1R — Recover U1A's own checks on an isolated immutable copy; S3,S11,S15; route: bounded read-only map then focused isolated recovery; status: pending; current old-process exclusivity established0matches/exit0; full owned API counterexamples deferred until T5 read optimization avoids repeated full decoding per page. No old PASS inferred. User explicitly reopened focused recovery; acceptance still depends on T2B.
- T2 — Original scoped JD gate; S5; route: retired by explicit user amendment; status: dropped; not completed/approved; original artifacts preserved; no correction/rejudgment budget consumed.
- T2B — Independent functional verification of U1A/U1B; S3–S5,S11,S15; route: assess and newly authorized focused independent verification after own checks/exclusivity; status: pending; old verifier mv8uc1jf-1-b8ls failed without usable proof, job15 unconfirmed; old evidence retained, not passed.
- T3 — U2 reconcile and separate immutable detail/session loading; S6,S11,S13; route: inline; status: blocked (implementation delivered, independent/manual acceptance pending); own RED6fail/exit1 then focused GREEN10PASS/exit0; local implementation commit: 84edcb7c5507df750aced727ba609a079dba10f3.
- T4 — U3 infrastructure: additive migration20 epoch and independent bounded-cache primitive; S7,S11,S15; route: disjoint bounded writers; status: in_progress; isolated epoch/migration tests and new cache-only module/tests, no owned-store/API/U1A changes; both writer own checks passed (epoch11/cache9), parent focused seam20PASS/exit0; separate commits/native assess/independent verification pending, not accepted.
- T5 — U3 bounded read certificate/cache and SQL endpoints; S7,S11,S15; route: dependent bounded implementation + independent technical verification; status: pending (reopened by S15, isolated data only); commit: pending.
- T6 — U4 financial hierarchy/ROI/coverage/provenance; S8,S11,S13; route: inline; status: blocked (implementation delivered, manual/independent acceptance pending); RED7fail/exit1 then focused GREEN/job4exit0; implementation commit: c45e0bfe015330727956e4b0f2e9a9485b9c5eb5.
- T7 — U5 semantic responsive order and accessible validation; S9,S11,S13; route: inline; status: blocked (implementation delivered, manual/independent acceptance pending); RED5fail→first GREEN9PASS/1FAIL→semantic fix→10focusedPASS, typecheck0/build0; implementation commit: 351ed5821cc47ebe6d305c2b39c90409011d6a31.
- T8 — U6 docs, full regression, independent acceptance and isolated same-tab browser QA; S1–S11; route: inline docs + gentle-ai-verify, browser via Orca; status: pending; commit: pending.
- T8D — U6 documentation slice and manual QA guide for current UI; S10–S14; route: inline passive documentation; status: done; readback/7links/README-preservation/staged-scope and final Git checks passed; no functional test applicable to prose; commit: 0480e0c021497b319ed9a3a61313d8276e10cadc. Full T8 acceptance remains pending.
- T9 — Reactivate current app for manual QA and identify checks; S12; route: parent operational startup; status: done; backend/frontend/proxy HTTP200 observed, checklist M1–M8 delivered (human execution pending); tracking-only work-unit commit: d91629d87bb2db56aa6afc5562191c3e41fe2448; no product code edits, test/verifier retries or push/PR.

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

### L7 — Explicit correction-route amendment
User, verbatim:
> Cambiar la ruta de corrección — recomendada
- User chose offered option1: normal workers, RED/GREEN and independent functional verification, then the remaining improvements. Only S5 and its ordering dependencies change; S3/S4 behaviors and the rest of the approved plan remain intact. Original plan stays an unchanged historical record.
- T1 returns to in_progress, ordinary disjoint workers. Original T2 JD gate is dropped, not done; new T2B functional gate is pending. Do not label JD approved or modify its frozen artifacts/counters.
- Baseline remains23PASS/job14exit0; commits e9fd051,a60cb3d,60a65d0 on feat/mejoras-quiniela; working tree clean before this amendment. No new source edits or tests have occurred yet.
- TODO reviewed against observed work as requested: only U0 done; corrections in progress, replacement verification and later units pending; retired gate dropped.

### L8 — Normal workers allocated in parallel
- Both launches succeeded: U1A mv8np9vu-5-aney (backend/README), U1B mv8np9zq-6-78ql (client/panel/tests); normal gentle-ai-worker, disjoint surfaces and isolated scratch subtrees. Both received T1, relevant S3/S4/S5/S11, strict TDD, exact focused/regression commands and self-review. No actor has returned evidence yet.
- One local codemode preparation exceeded its1MiB state store before any tool call; cleared redundant copied recovery/source values, then resubmitted identical prepared handoffs. No duplicate workers, failed source edit or test retry.
- Route amendment committed5af0a37. T1 stays in_progress; wait for pushed settled results, do not poll or duplicate work. Assess actual per-unit diffs only after return; T2B independent functional gate stays pending. JD remains unchanged/uncompleted.

### L9 — U1B delivered, inspected and committed; not yet accepted
- U1B worker reports completed S4/S5/applicableS11. Genuine pre-fix RED:7failures/25cases, including2behavior failures plus5incomplete-mock failures corrected in the harness; preserve this distinction. GREEN25PASS/2files; full163PASS/25files; typecheck0. No U2 refresh/reconciliation change.
- Parent inspected actual request() body and four-file diff. Workspace test uses real createLaboratoryRun/request and checks onePOST plus disabledexecute after unreadable201. No source changes outside assigned frontend surfaces. The advertised scratch directory does not exist; worker results are command-report evidence, not invented saved log artifacts.
- Source commit fbe48a7450f5fdd68d82b8646f0d2feec7c7cb93 contains only4frontendfiles,+76/−9. Backend worker edits and tracking were not staged. Rollback boundary is these4files only.
- Native read-only assess of that committed unit: native medium, raised high for shared request/ApiError consumer compatibility (item3); large runtime writer; independentVerifier:true, RDDoff/reviewDuefalse. No ordinary review started. Required independent check and parent spot check remain pending.
- U1A remains active; do not poll it. T1 is NOT done. T2B functional seam gate and U2–U6 remain pending; retired JD gate stays dropped. Visible TODO reviewed against this exact evidence after the user's reminder.

### L10 — Repeated route choice already applied; new runtime proof blocker
- User repeated `Cambiar la ruta de corrección — recomendada`; preserve L7, do not relaunch correction workers or treat this as a different plan. The method change is already committed and JD remains uncompleted.
- Prepared isolated U1B copy from commit fbe48a7450f5fdd68d82b8646f0d2feec7c7cb93 at .tmp/mejoras-quiniela/u1b-verify/candidate-zzhfzsta. Existing dependencies linked in-project; exact parent runner preserves raw command outputs and source hashes. No install or normal-data change.
- Independent gentle-ai-verify mv8uc1jf-1-b8ls failed: `assistant reported an error`. One result retrieval confirmed no usable details; verification-logs directory is empty. Do not invent test execution or infer candidate failure from this runtime failure. No retry/replacement verifier launched.
- Parent spot-check job15 had been launched, but current job_list reports no jobs and no completion proof was received. Its outcome is unconfirmed, not PASS; no new test run.
- At this real incident boundary, U1A status lookup reports no task mv8np9vu-5-aney. The previous active-worker assertion is no longer supportable. Backend source/tests/README are partially modified; preserve them untouched. Do not assume its process stopped, duplicate its work or kill unidentified processes.
- T1 and T2B now blocked on external runtime/control and independent-proof recovery. U0 remains the only completed unit; original JD gate dropped; U2–U6 pending. TODO reconciled to observed outcomes, not the stale injected projection. No new feature is declared complete.

### L11 — User requests continued ODD; recover U1A without duplicating actors
User, verbatim:
> continua conel todo odd
- Authoritative file/mirror and live Git reconciled: HEADfbe48a7, eight pending backend/README paths preserved, original worker still absent from runtime registry; verifier record confirms4turns/0toolcalls, no usable independent execution proof.
- Incident-only process lookup initially failed due shell variable expansion, then a regex escaping error emitted nonterminating PowerShell errors (exit0 was NOT accepted as clean). Final literal-filter query with ErrorActionPreference=Stop succeeded:0matching known-check/task-marker processes. No process was killed. This does not invent a recovered worker completion.
- The only retained U1A scratch evidence is a RED pytest temporary directory and command-setup note; no raw RED/GREEN exit/output report. Do not fabricate original TDD chronology. Existing implementation/tests were inspected, but not accepted.
- Add T1R before any new recovery artifact: freeze current backend plus its verified inputs in a fresh project-local copy, then run U1A's first parent-observed own regression check there. Hash the source before/after; never run against normal data or relaunch the lost writer. A test on an isolated snapshot cannot race its live edits.
- This recovers missing U1A own-check evidence, not a substitute for the failed independent verifier. T1/T2B remain blocked on final acceptance; U2–U6 are not started. Only T1R is in_progress. No verifier retry, alternative reviewer or new source changes.
- Recovery candidate prepared successfully (exit0): `.tmp/mejoras-quiniela/u1a-recovery/candidate-ktp89qa8`, HEAD`fbe48a7450f5fdd68d82b8646f0d2feec7c7cb93` plus precisely8pending U1A backend/README files. Git archive excludes credentials; both frozen inputs copied only after exactSHA validation. All snapshot source/input hashes recorded in `u1a-recovery/context.json`; live overlay stability checked while freezing.
- Started job-1: `py -3.14 -B .tmp/mejoras-quiniela/u1a-recovery/run.py`. One own-check command covers6owned/reference store/API testfiles, including both realcounterexamples and everypublicsessionpage. Candidate-local data/basetemp/input overrides, no normaldatabase access; pluginautoload/cache/bytecode disabled. One-hour bounded childprocess; timeout is failure, no automatic rerun. Rawargv/stdout/stderr/result and before/aftersourcehashcheck live under candidate `check-logs/`. At launch, result is PENDING, not PASS. Do not poll; await pushed completion.

### L12 — Continued ODD: reconcile interrupted recovery proof
User, verbatim:
> continua conel todo odd
- Current session job inventory reports no background jobs. This does not prove that the original test process stopped. No re-launch, cleanup or process termination was performed.
- Recovered candidate `candidate-ktp89qa8/check-logs/` contains command.json, stdout.log and empty stderr.log, but no result.json. Stdout confirms pytest collected263tests and several early tests PASSED. Its last available line names `test_full_frozen_owned_result_is_saved_and_publicly_paginated[full-coverage-flat]`, without its result. There is no final suite outcome/exit or after-run immutable-source proof. Do not count the263collected cases as passed.
- Git HEAD remainsfbe48a7 and the same8pendingbackend/READMEpaths plus this trackingfile. No new source edits, test retries, independent reviewer or commits.
- T1R transitions to blocked on external job/runtime/result recovery. T1/T2B remain blocked; U2–U6 remain pending, not started. Valid stop: Needs your decision, missing final own-check and independent-verification proof. Do not compensate with additional checks or declare U1 accepted.

### L13 — Reactivate the app for human validation
User, verbatim:
> vamos levanta todo otra vez dime que tipo de pruebas pues la mayoria la puedo hacer yo manual
- Scope: reactivate app, explain actionable manual cases, preserve existing incomplete evidence. No authorization inferred to mark a missing test/verifier as PASS or start another copy of pytest.
- Initial one-shot socket probe: both127.0.0.1:8765and:5173closed (exit0). Existing appfactory and Viteproxy inspected; startup can run without opening a new browser. No dependency installation or production database migration.
- Operational choice: fresh project-local QA data directory, current working-tree backend and Vitefrontend, verified frozen read-only input paths. No copying or touching normal user database; application startup may initialize only the fresh QA database. Explain clearly that this is an empty test environment, not the user's saved data.
- Manual checks are supplemental: ordinary UI/create/results/paging/validation and responsive/keyboard checks can be human-owned; malformed successful write responses, transactional quota/byte atomicity, corruption, and exhaustive parity/digests still need controlled automated evidence. U2–U6 not implemented and must not be presented as available.
- Startup succeeded: backend job-1 on8765, frontend job-2 on5173 (new host IDs; do not confuse with earlier lost pytest job-1). QA data/logs/context: `.tmp/mejoras-quiniela/manual-qa-a063bbnr/`. No browser opened, no dependencies installed, no test/verifier retried, no normal database opened.
- One-shot readiness command exit0; `readiness.json`: backend `/api/v1/laboratories` HTTP200JSON4599bytes; Vite `/` HTTP200HTML706bytes; proxied `/api/v1/laboratories` HTTP200JSON4599bytes. This establishes HTTP readiness and the proxy, not visual/functional acceptance. User entry: `http://127.0.0.1:5173/`.
- Human checklist (NOT executed, no PASS claimed): M1create a distinct QA laboratory and verify creation alone does not execute it; M2execute a short valid historical window once, inspect results and disabled in-flight Execute, check paid-minus-wagered equals net and closed-plus-incomplete equals total; M3reload/reopen and verify saved result persists; M4next/previous sessions pages, check consistent ordinals and no visible duplicate/omitted boundaries; M5empty name/coverage0or51/reversed dates show validation and create no new laboratory; M6full-window Transición/flat/coverage50/capital50/goal51/prizes[1,1,1,1,1]; M7full-window Transición/flat/coverage1/capital1/goal2/prizes[2,2,2,2,2]. M6/M7expect65235sessions if real capacity permits, otherwise exact specific storage-capacity409, not truncation or generic execution failure. A human spot check of paging is not exhaustive integrity proof. M8keyboard/mobile readability: record observed issues, not pretend planned U5accessibility improvements already exist.
- Automated controlled evidence still missing: successful write persisted but successful response body unreadable (U1B fault injection, not merely turning off the network); full sessions/digest consistency and shared reference/legacy50000contract; quota/byte rejection atomicity and corruption detection. No human screen tour substitutes for these. Ask user to report checklist IDs with observed values/error text/screenshot.
- Scope reminder for human QA: U2reconciliation and efficient paging, U3epoch/cache, U4ROI/financial redesign and U5new accessibility remain unimplemented. Do not ask user to accept them as delivered. T1/T1R/T2B remain blocked; manual results pending user.

### L14 — Explicitly unblock UI implementation, mostly manual QA
User, verbatim:
> hazlo asi pues esta bien ojo las prouebas las hare yo manuel en su mayoria asi que omitelas ya
- S13 changes only order and QA ownership; no missing proof becomes PASS. StartT3(U2), thenT6(U4), thenT7(U5). ExistingU1/T1R/T2Bremainblocked, U3notstarted. Backendpartialwork anduserdatapreserved. No blocked/fulltests/verifierretry. Parentdisclosedminimumfocused/typechecks stillrequired for code safety. UIunits are ordered around sharedpanel/tests/CSS, not disjoint parallelwriters. No new actor is needed for the first inline slice.

### L15 — U2 implemented with minimum focused evidence
- Onlypanel/workspacetests changed; valid current reconciliationtoken + currenteffectguard keep uncertaintyuntilfreshsuccess, includingdelay/failure/abort/stalelabresponse. Separate detail/sessioneffects, localerrors/retries andstableheaderduringpaging. No automaticPOST/retry.
- RED:6new U2 cases failed beforebehaviorchange, exit1,25.97s; raw `ui-route/u2/red.{stdout.log,stderr.log,exit}`. Initialtestfixtureliteraltypingerror corrected beforeRED; no syntax/setup failure counted as behaviorRED.
- GREEN: job-3pushedexit0 after8s; Vitest5.68s,10PASS/15notrun, empty stderr.6newrules +4existingexecute/ambiguity/delete/financialregressions selected. Raw `ui-route/u2/green.{stdout.log,stderr.log,exit}`. Nofullsuite or failedverifierretry. `git diff --check` exit0. No meaningful RED needed fortracking-onlyupdates.
- Remainingrisk:item4(asyncresponseordering). Independent/manualacceptance unobserved, soT3implementationisdeliveredbutnotaccepted; T8finalQAandblockedU1proofstayopen. S13allowscontinuingU4/U5inthisstate. Newdiscovery: frontendtypeandfixturealreadycontainrankings_sha256, so U4mustnotinventanotherAPIchange.

### L16 — U4 local presentation implementation
- ROI helper dividesnetbywageredbefore100, returnsnullfor0wagered andnormalizesnegativezero; Spanishsigned2decimalpresentation. Net/ROIprimary, threefinancialmetricsnext, fourclosurecounterssecondary:8originalmagnitudesunchanged +derivedROIonly. NoAPI/globalformatterchange.
- Selectedcoveragecopy, compacteligible/gaps, nativeprovenancewithconfigured/effectivewindowand3completehashes, emptyheading0of0. Localcontainer-drivenCSS, nowrap/tabular/right-alignedmoney, nolegacyrouteorfont/tokenchanges. Sixremovedparagraphsstayabsent.
- RED7behaviorcasesfailed/exit1beforeUIchanges; focusedGREENjob4pushedexit0after7s.7newUIcases+7purehelperchecks+4existingpresentationregressionsselected; othercasesnotrunbyfilter. Raw `ui-route/u4/{red,green}.{stdout.log,stderr.log,exit}`. `git diff --check`exit0. Noheavy/full/backendtests. Visual/mobile/keyboardchecksdelegatedtouser, notpassed. U1andU3statusunchanged.

### L17 — TODO review during U5, no completion claim
User, verbatim:
> The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.
- T3/U2implementationcommit84edcb7with10focusedPASS; T6/U4implementationcommitc45e0bfwith18focusedPASS. Both remainblockedonacceptance, notdone. No U3workorstoragechange.
- T7/U5iscurrentlyin_progress: focusedREDwasobservedbeforebehaviorchanges; Workspace/Formeditsarewritten, butCSScleanup/GREEN/typecheckarepending. Do not callU5verifiedoraccepted. Minimumfocusedchecks only; no broadsuite/backend/verifierretry. UserownsmanualbrowserQA.
- Pi-lensreportedonlyadvisories(high-fan-out/redundant-filter-map/typo), no redblocker. No unrelatedrefactor forstylewarnings.

### L18 — TODO review after observed U5 regression
User, verbatim:
> The todo plan has not been reviewed during several tool-use turns. Check whether it still matches the work performed and update tasks where needed. Do not mark work done without verification.
- Job5exit1after10s:9PASS/1FAIL/27notrun; existingaxecheckreportslandmark-banner-is-top-level onformheaderinside newgenericdivregion. U5notverified/done. Typecheck/builddidNOTrun because testsfailed.
- KeepT7in_progress. Correctsemanticstagecontainer, preservefailedGREENlogs and runonefocusedconfirmationafteractualfixusingnewartifactnames. No unrelatedrefactor or verifier/full-suite retry.
- ActiveLSPprobe7paths:0findings, only2confirmedclean/5inconclusive (3budgettimeouts,2silentpush-only). NOTglobalcleanproof; no repeatedprobe. CLItypecheckpending.
- Tracking edit partially applied its first task-line change; a truncated whole-file read made the second tail anchor invalid. Re-readactualtail and appended only the missingLogblock; never resubmitted appliededit. Filepreserved. Mirror now readinboundedchunks toavoid50KBtruncation.
- U2/U4codecommitsandfocusedproofunchanged; independent/humanacceptancestillblocked. U1/U3unchanged. No newcompletedtask.

### L19 — U5 code delivered, focused checks observed; acceptance still pending
- Job6pushedexit0after22s. Focusedpost-semantic-fixGREEN:10PASS/27notrun,4.87s. `tsc --noEmit`exit0, Viteproductionbuildexit0/73modules/3.72s; stderrfilesempty. Raw `ui-route/u5/green-correction1.*`, `typecheck.*`, `build.*`; preservefailedfirstGREENunchanged. No fullsuite/backend/failedverifierretry.
- ActualDOMreordersstablekeyedstage/sidebarat860/861, matchMedialistenercleansup, drafts/selectedrun/page/focuspersistwithoutextraGET/POST. StagefocustriggersonlyuserLinknavigation; formalertslinkinvalidfieldsandfocusfirstafterDOMcommit. Semanticsectionstagefixesrealaxeregressionwithoutweakeningtest. Removedorder:-1,localfocus/errortargetstylesonly.
- Gitdiffcheckinitiallyexit2foroneextratrackingEOFblankline. Formatting-onlytrailingblankremovedwhileappendingthisentry; sourcebehaviornotchangedforthis. No newcompletedtask; T7codewillbecommittedlocallybutacceptanceremainsblocked. U1/U3andotherpendingtasksunchanged.
- Manualnextsteps: refreshQAapp, inspectNeto/ROIandprovenancedetails, resizeacross860pxwithadraft/selectedpage, submitinvalidformandcheckTab/focus. No manual/visual/mobilePASSobserved. Independentverificationremainsunavailable; no newactor/retry/substitute. Risk:item4asyncordering; no globalswitch/bypass or acceptanceclaim.

### L20 — Documentation continuation and actionable human QA
User, verbatim:
> hazlo y dime que debo hacer yo continua con el odd y modo yolo
- StartT8D/docs-onlysliceofapprovedU6; T8fullregression/acceptancestayspending. Updatecurrentbrand/navigation/deliveredUIsemanticsandaddmanualchecklist. No meaningful RED forpassiveprose; verifylinks, source-backedclaims, diffsandstagedscopeinstead. No runtime/test retry needed.
- Source-backedcurrentstate: ShellshowsQuiniela/Laboratorios/Ajustes; database.pyregistersschema19, no20. PRODUCT/DESIGN/surfacebriefstilldescribeoldCorridas/staticcatalog. Preservepaper/ink/fonts/tokensandlegacydirectroutes.
- READMEcontains2pendingU1Ahunks. CapturedHEADandworkingtreebeforeedits; appliedonlyourexplicitdocumentationedits; preparedaHEAD-baseddocumentationpatch, notwholeREADME. ReadbackprovedtheoldU1Adeltaremainsunchanged. No backendsource/dataedits.
- Initialstructuralcheckcommandfailedexit1withPythonquotingSyntaxError; correctedtofile-based.tmp/mejoras-quiniela/docs-slice/check_docs.pyandobservedexit0:5docs/7links/READMEpreservation/patchcheck0. No app-testfailureorbroadsuiteretry. ProxyGEThttp://127.0.0.1:5173/api/v1/laboratoriesreturnedHTTP200/JSON4599bytes.
- .impeccable/surfaces/route-laboratorios.mdupdatedlocallybutgitignored(.gitignore:43); donotforce-add. MarkdownformatterreportedMarksmanincomplete/MD025warning; no globaldiagnostic-cleanclaim. Passiveprosehasno meaningfulRED; source-backedreadbackandGitchecksaretheapplicableverification.
- Precommitgitdiffcheckreturnedexit2foranextraEOFblankinthistrackingfile; removedthatformattingerrorbeforecommit. No application/testresultaffected.

### L21 — Documentation slice delivered without U1A contamination
- Commit0480e0c021497b319ed9a3a61313d8276e10cadccontains5documentationpaths/114insertions/18deletions. check_index.pyprovedexact5pathscopeandHEAD-basedREADMEcontent; cachedGitdiffcheckexit0; commitexit0. Exactly8oldU1Asource/READMEpathsremainunstaged, no backendcodeincluded. Sidecarremainslocal/ignored. Finaltrackingstatus/hashupdateisaseparateuncommitteddelta.
- T8Ddone; T8fullregression/independent/manualacceptanceremainspending. U1/T1R/T2BandU2/U4/U5acceptancegatesunchanged; U3deferred. No testsuites/verifierretry/newmigration/normaldatamutation/push/PR. Documentation-onlyrisk:none; existingasyncorderingriskitem4isnotcleared.
- Usernextaction: openhttp://127.0.0.1:5173/laboratoriosandfollowdocs/quiniela-ui-manual-qa.md(M1–M7,optionalofflinecheck). Reportcase/expected/observed/browser-width/errororcapture; donotlaunchthenormaldatabaseiftheQAURLfails. ObservedonlyHTTP200,notbrowser/manualPASS.

### L22 — Reopen technical closure by explicit interactive decision
User, verbatim:
> siii lo veo super bien perfecto continua termina con el odd
Selected, verbatim:
> Completar el plan técnico
> Autorizar retomar U3 y recuperar la verificación de U1 con pruebas focalizadas en datos aislados, sin tocar tu base normal ni relanzar suites amplias.
- Registergeneralvisualacceptance,notunobservedfunctionalsteps. S15reopensU3andfocusedU1recovery. T1Rstartswithold-process/candidateevidencebeforeanynewexecution; preserve8pendingU1Apathsandoldlogs. Independentnewfocusedproofauthorizedafterownchecks. No normaldatabase,broadsuite,push/PR,toolrepairorJDsubstitution.
- Runtimepublicationattemptreturnedsessionmessagingnotreadyonce; no retry. Agentinventoryavailable; useoneboundedread-onlyexplorerformapping,notparentduplicatecodereads.
- Explorermv9pf651-1-ype4returnedread-onlymap. Parentone-timespotcheckreadbotholdcontexts/command.jsonsuccessfully; explorer'sunreadablehelperclaimisnotabsenceproof. Get-CimInstancewithStopreturned0matchingprocesses/exit0,UTC2026-10-15T15:41:19Z; .tmp/mejoras-quiniela/s15-recovery/exclusivity.json. No processkilled, no oldresultrecovered.
- RouteT4first(disjointmigration/database/migrationtests), thenT5, thenfocusedall-pagesU1counterexamples: currentownedAPIloadsandvalidatesallrowsperpage, so old263-test/fullpagingreplaywouldrepeatunboundedwork. T1Rpendingbydependency, notdone; T4inprogress. Parentwillnotduplicateworkerexplorationorclaimperformancewithoutinstrumentation.
- Retainedsnapshotvalidationexit0:107U1Afiles/80U1BfilesmatchSHA; current7dirtyU1Abackendfilesmatcholdoverlay; READMEnewdocsintentionallyexcludedfromcurrentoverlaycomparison. .tmp/mejoras-quiniela/s15-recovery/snapshots.json. No checksuiteslaunched.
- T4expandedonlyasreviewableinfrastructuregroupwithinS7: migration/epochandstandaloneLRUprimitiveareindependent,nontrivialanddisjoint; launchcachewriterinparallel, leaveT5integrationdependent. Migrationwriteralreadyallocatedmv9pm696-2-l5fb; cachewriterwilltouchonlynewmodule/newtestanditsownscratch. OnevisibleT4phaseinprogress; parentdoesnoteditworkersurfaces. No JSON/APIreadchangesuntilT5.

### L23 — Infrastructure own checks observed, independent acceptance pending
- Migrationworkermv9pm696-2-l5fbcompleted3sourcefiles: RED3fail/exit1, GREEN11PASS/exit0/.87s, parent11PASS/exit0/.91s. Epochtriggerscoverphysicalrun/sessionwrites; migrationpreservesJSON/identities/deletedseeds,rollbacktested. .tmp/mejoras-quiniela/s15-u3-epoch/logs/{red,final,parent}.*. Ruffunavailable127; no install/retry. ActiveLSP2paths0findings,but1clean/1inconclusive; notglobalcleanproof. ASTfoundonlyintendedrollbackversion19assert.
- Cacheworkermv9pqd8c-3-rm2ucompletednewmodule137lines/newtest145lines. Initialcollection-onlyREDnotcounted; genuineRED6fail/3pass exit1, GREEN9PASS/.20s/exit0. Byte-onlyimmutablecertificates,64entries/16MiBpayload,LRU,keyseparation,epochinvalidations,lateoldputs/concurrency. APIhandoff:get/put(database_id,epoch,owner_id,run_id[,certificate]), certificate(metadata=compactbytes,session_digests=packedbytes). No SQLiteorintegrationclaim.
- Parentfocusedseamcommand(test_laboratory_migrations.py+test_owned_laboratory_read_cache.py)exit0,20PASS; logs.tmp/mejoras-quiniela/s15-u3-cache/parent-seam.*. No broad/backendfullsuite. Automaticformatterchangedmigration/cachetests; parentre-readbeforestaging, no manualsourceedits. Nativeper-unitassessmentandindependentverificationstillrequired. T4inprogress, notdone.
- Documentationupdatedforregistered20/isolatedepochproof, explicitlyleavingcache/SQLintegrationandacceptancepending; normaldatabasenotmigrated. READMEusesfreshHEAD-basedpatchtoexcludeoldU1Ahunks. Parentwillcommitmigrationandcacheasseparateworkunitsbeforerangeassessment.
