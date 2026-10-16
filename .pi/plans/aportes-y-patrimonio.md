# Plan: aportes de bolsillo y patrimonio simulado

> Creado con `plan-mode-trae` y ODD. Solo planificación: falta aprobación explícita para implementar.
> Base explorada: `master`, commit `9275c03`. Idioma: español. Archivo: `.pi/plans/aportes-y-patrimonio.md`.

## Summary

Agregar una billetera simulada por corrida que distinga los aportes externos del dinero reinvertido y muestre primero **Aportado de tu bolsillo**, **Patrimonio al final** y **Ganancia / pérdida**. Conservar el motor, las sesiones y resultados históricos, la integridad, la cuota, la paginación y las métricas actuales; cambiar su jerarquía, no su significado.

Solicitud de esta fase, textual: «perfecto me gusta agrega esto sii haz un plan para implementarlo con odd».

Ejemplo aprobado, ilustrativo y no un resultado prometido:

```text
┌─────────────────────────┬─────────────────────┬────────────────────┐
│ Aportado de tu bolsillo │ Patrimonio al final │ Ganancia / pérdida │
├─────────────────────────┼─────────────────────┼────────────────────┤
│ RD$2.000                │ RD$2.800            │ +RD$800            │
└─────────────────────────┴─────────────────────┴────────────────────┘
```

Restricción original del usuario, textual: «asi como esta esta bien solo quiero un dato extra que me diga la verdad cuanto dinero salio de mi bolsillo».

## Current State Analysis

- **Motor existente:** `webapp/backend/laboratorio/engine/reference_labs.py`, `run_reference_lab`, recorre los sorteos y genera sesiones cronológicas. Al cerrar una sesión por meta o quiebra vuelve al capital configurado. No mantiene una billetera global entre sesiones. `total_net` ya suma `final_balance - capital` de todas las sesiones, incluidas las incompletas.
- **Resultados guardados:** `webapp/backend/laboratorio/storage/owned_laboratory_run_store.py` valida la corrida completa antes de certificar una lectura. `_compact_record` (zona 274) construye el resumen; `_certificate_for` serializa metadatos compactos y huellas; `_decode_certificate` exige claves exactas; `_load_certificate` carga las sesiones con `ORDER BY ordinal` en frío. Las lecturas cálidas reutilizan el certificado y las páginas siguen siendo consultas SQL acotadas.
- **Caché existente:** `webapp/backend/laboratorio/storage/owned_laboratory_read_cache.py`, certificado inmutable de bytes y huellas, límites de 64 entradas / 16 MiB, por repositorio. No persistir una segunda copia completa de las sesiones.
- **HTTP:** `webapp/backend/laboratorio/api/laboratory_runs.py` tiene dos proyecciones: `_projection` para la respuesta de creación y `_compact_projection` para el detalle guardado. Hoy ninguna comunica aportes o patrimonio. El listado de corridas publica solo sus métricas actuales.
- **Cliente:** `webapp/frontend/src/api/laboratories.ts` define `LaboratoryRunSummary`. `LaboratoryPanel.tsx` obtiene el detalle y una página de sesiones por separado: no calcular una billetera con las 50 sesiones visibles ni pedir todas las páginas.
- **Pantalla:** `LaboratoryPanel.tsx:205–240` prioriza Neto total / Retorno sobre apostado; después Apostado / Pagado / Media neta de cerradas, cuatro contadores, procedencia y tabla paginada. `laboratories.css` ya adapta la retícula al ancho del contenedor.
- **Formato y diseño:** `webapp/frontend/src/lib/format.ts` hace que tanto `formatDOP` como `formatSignedDOP` incluyan signo. No modificar estos contratos compartidos para obtener el ejemplo sin signo en aportes/patrimonio. La fuente visual vigente es `docs/DESIGN.md`, no el antiguo archivo raíz.
- **Pruebas disponibles:** backend `test_owned_laboratory_read_queries.py`, `test_owned_laboratory_read_api.py`, `test_owned_laboratory_run_store.py`, `test_owned_laboratory_run_list.py`, `test_owned_laboratory_read_cache.py`; frontend `Workspace.test.tsx`, `result-model.test.ts`, `LaboratoryForm.help.test.tsx` y `api/laboratories.test.ts`.
- **Exploración:** se leyeron las entradas y convenciones anteriores y se utilizó un scout solo de lectura para el camino certificado. Se comprobó directamente el tramo `_compact_record` → `_load_certificate`. No se ejecutaron pruebas, motores ni operaciones de base de datos durante la planificación.

## Proposed Changes

### 1. Regla contable: una billetera por corrida seleccionada

Agregar el módulo **nuevo** `webapp/backend/laboratorio/domain/laboratory_wallet.py` con una proyección pura de las sesiones completas y ya validadas. Usar el capital del **snapshot de esa corrida**, nunca la definición actual ni un valor escrito en el navegador.

Política fija `retain-gains-top-up-v1`:

```text
aporte = 0
billetera = 0
para cada sesión existente, en su orden original:
    adicional = max(0, capital_por_sesion - billetera)
    aporte += adicional
    billetera += adicional
    billetera = billetera - capital_por_sesion + saldo_final_de_la_sesion
```

- La parte no usada para financiar una sesión queda reservada en la billetera.
- Las ganancias y los saldos residuales pueden financiar la siguiente sesión; no se cuentan como otro aporte.
- El aporte adicional se realiza solamente **antes de una sesión que efectivamente existe**. No recargar después de la última quiebra si no hay otra sesión.
- Incluir la última sesión incompleta. No inventar lo que hubiera sucedido después del fin del historial.
- Con cero sesiones: aporte `0`, patrimonio `0`, neto `0`.
- Comprobar la identidad exacta `patrimonio_final - aporte = total_net` existente, sin recalcular ni reemplazar el neto del motor.
- Trabajar con enteros seguros; no usar flotantes, redondeos ni conversiones que acepten booleanos como importes. Una incongruencia en el camino validado no produce una cifra parcial ni una cifra inventada.

El aporte no es `capital × cantidad_de_sesiones`. Tampoco se deduce solo del total neto: depende del orden de ganancias y pérdidas.

### 2. Contrato aditivo de respuesta, sin persistencia nueva

Agregar únicamente al detalle y a la respuesta POST:

```json
{
  "summary": {
    "wallet": {
      "policy": "retain-gains-top-up-v1",
      "out_of_pocket": 2000,
      "final_wealth": 2800
    }
  }
}
```

Es un fragmento aditivo: conservar todos los campos actuales de `summary`, `totals`, snapshot y capacidades. `Ganancia / pérdida` usa `summary.totals.total_net`; no duplicarlo en `wallet`. No cambiar `contract_version`, las rutas ni el cuerpo del POST.

**`webapp/backend/laboratorio/storage/owned_laboratory_run_store.py`:**

- En `_compact_record`, obtener `summary.wallet` del capital del snapshot y de `record["sessions"]`, ya completo y validado, con la función pura compartida.
- Mantener `wallet` fuera del resultado persistido, de `result_json`, del snapshot y de las huellas. No agregarlo a los validadores del formato histórico almacenado.
- Incluirlo en los bytes compactos del certificado. Actualizar la lista exacta de claves de `summary` en `_decode_certificate` y validar política, enteros no negativos y concordancia con el neto. No relajar las validaciones actuales de identidad, owner, snapshot y huellas.
- Evitar un segundo cálculo sobre todas las sesiones: hoy `_load_certificate` llama `_compact_record` dentro de `_certificate_for` y otra vez al devolver el frío. Después de certificar, devolver la proyección mediante `_decode_certificate(certificate, owner_id, run_id)`, en lugar de recalcular `_compact_record(record)`. Así frío y cálido comparten el mismo metadato certificado.
- Preservar `BEGIN`, época y datos de la misma instantánea. No añadir consultas ni cálculos completos al camino cálido.
- No modificar la clase de caché, sus claves, límites o política de rechazo por tamaño; los nuevos bytes cuentan dentro de su presupuesto existente.
- Conservar el listado y las páginas de sesiones con sus formas actuales. El listado puede usar internamente un certificado enriquecido, pero no necesita publicar `wallet` ni cargar páginas adicionales.

**`webapp/backend/laboratorio/api/laboratory_runs.py`:**

- `_projection` utiliza la misma función pura con el registro completo validado que ya obtiene después de guardar. No calcula a partir de resultados parciales.
- `_compact_projection` conserva el resumen certificado enriquecido.
- POST, primer GET frío y GET cálido de la misma corrida deben devolver idéntico `summary.wallet`.
- Mantener los estados y mensajes existentes de 404/409, aislamiento por owner, cuotas, contadores y bloqueo de envíos inciertos. Los GET no escriben ni actualizan cuotas.

Las corridas antiguas obtienen la nueva proyección al leerlas, sin volver a ejecutarlas ni reescribir sus datos.

### 3. Cliente y presentación: tres cifras principales, sin duplicados

**`webapp/frontend/src/api/laboratories.ts`:** agregar `LaboratoryWallet` y `wallet?: LaboratoryWallet` en `LaboratoryRunSummary`. Es opcional para tolerar respuestas anteriores; no modificar los DTO compartidos de referencia/legacy ni el listado.

**`webapp/frontend/src/pages/laboratories/result-model.ts`:**

- Añadir un lector/validador local de la billetera: política conocida, importes enteros seguros no negativos y `final_wealth - out_of_pocket === total_net`.
- Si falta o es inválida, los dos importes nuevos muestran **No disponible**; las métricas anteriores siguen visibles. No inferir aportes desde la página actual o desde el capital multiplicado por sesiones.
- Añadir un formateador local para los dos importes absolutos: `RD$` + agrupación de `formatNumber`, validando enteros no negativos. Mantener `formatSignedDOP` para Ganancia / pérdida.
- No cambiar las funciones existentes de retorno ni los formateadores globales en `src/lib/format.ts`.

**`webapp/frontend/src/pages/laboratories/LaboratoryPanel.tsx`:**

1. En Resultado guardado, encabezado **Tu dinero · Simulación** y fila principal, en este orden:
   - **Aportado de tu bolsillo** → `wallet.out_of_pocket`.
   - **Patrimonio al final** → `wallet.final_wealth`.
   - **Ganancia / pérdida** → el `total_net` existente con signo.
2. Conservar la columna **Neto total** del listado de corridas. El cambio de nombre corresponde al resultado seleccionado; no crear otra tarjeta que duplique el mismo neto.
3. Debajo, **Movimiento de apuestas**, con **Volumen apostado**, **Premios recibidos** y **Retorno sobre apostado**. Son los mismos valores actuales de Apostado, Pagado y retorno; premios recibidos son brutos, no ganancia.
4. Conservar los cuatro contadores y la tabla de sesiones sin cambios de significado ni de paginación. Mover **Media neta de cerradas**, sin eliminarla, a un desplegable nativo **Detalle de sesiones**, cerrado inicialmente.
5. Conservar aparte **Datos de la reproducción**, sorteos, huecos, ventana y SHA completos. No mezclar procedencia con el nuevo detalle financiero.
6. Ayuda cerrada por defecto **ⓘ Cómo se calcula**, mediante `details/summary` nativo dentro de la nueva sección. Explica: saldos retenidos, recarga solo cuando falta capital para la siguiente sesión, sin retiros y sin cambiar apuestas. Funciona con toque y teclado, sin hover obligatorio. No refactorizar la ayuda existente de las opciones ni sus estados.
7. No añadir llamadas de red, efectos de carga, nuevos porcentajes o cálculos de negocio en React. Los importes son de la corrida completa y no varían al paginar.

**`webapp/frontend/src/pages/laboratories/laboratories.css`:** adaptar solo los grupos de resultado nuevos. Usar la retícula existente: tres columnas cuando el contenedor lo permita y apilado natural en móvil; sin forzar anchuras, cortar dinero o introducir scroll horizontal de toda la página. Preservar papel frío, Archivo, esquinas rectas, foco visible y contadores.

### 4. Documentación y pruebas

- **Nuevo** `webapp/backend/tests/test_laboratory_wallet.py`: tabla contable siguiente, identidad y límites numéricos.
- Extender `webapp/backend/tests/test_owned_laboratory_read_api.py` y `test_owned_laboratory_read_queries.py` con respuestas públicas y certificados fríos/cálidos; mantener pruebas existentes de store/list/cache como regresión acotada.
- Extender `webapp/frontend/src/pages/laboratories/result-model.test.ts`, `Workspace.test.tsx` y, si requiere actualizar el contrato de ejemplo de HTTP, `webapp/frontend/src/api/laboratories.test.ts`. Mantener la ayuda de opciones y sus pruebas.
- Actualizar `webapp/README.md` con la proyección opcional y su política; `docs/quiniela-ui-manual-qa.md` con casos de billetera; `docs/DESIGN.md` con la nueva jerarquía. Explicitar la excepción local de los dos importes absolutos sin signo, sin cambiar las convenciones históricas ni tokens.

## Assumptions & Decisions

1. **Solo simulación por corrida:** no es una billetera personal real ni una suma entre laboratorios/corridas que podrían repetir los mismos sorteos. Usar exclusivamente el snapshot y sesiones del resultado seleccionado.
2. **Sin retiros, intereses, comisiones, impuestos ni inflación.** Mantener ganancias/residuos disponibles. El patrimonio incluye reserva más saldo final de la última sesión; no es la suma de todos los saldos finales.
3. **Financiación suficiente simulada:** si falta capital antes de una sesión existente, simular y contabilizar exactamente ese aporte. No imponer un nuevo límite de bolsillo ni detener/cambiar la ejecución. El importe informa cuánto dinero externo habría hecho falta bajo esta regla.
4. **Mismo motor:** continúan su capital por sesión, metas, selección, cobertura, estilo y reglas de cierre. La billetera es una capa contable derivada, no otra estrategia.
5. **Ganancia/pérdida conserva el neto existente.** No prometer rentabilidad futura, mostrar estados «rentable» ni añadir un segundo ROI sobre aportes.
6. **Extensión en memoria/HTTP únicamente:** sin migraciones, nuevos registros, backfills, cambios de versión almacenada, huellas, ficheros de referencia, caché global o dependencias.
7. **Datos ausentes no significan cero.** Cero es válido cuando el backend certifica una corrida sin sesiones; si una respuesta anterior no tiene `wallet`, mostrar No disponible.
8. **Fase 2 resuelta sin preguntas:** se aplican las reglas de conservación/reutilización ya explicadas y aceptadas. Estas decisiones quedan visibles para su aprobación conjunta; no empezar a implementar por inferir aprobación del interés del usuario.

## Ejecución ODD después de aprobar

**Todavía no ejecutar esta sección.** La aprobación del plan habilita implementación y verificaciones en alcance; no implica publicación, PR, merge o una operación sobre la base habitual.

1. Releer este plan y comprobar el estado de Git. Si continúa en `master`, preparar una rama de trabajo `feat/aportes-y-patrimonio`; no arrastrar ni borrar cambios ajenos.
2. Antes del primer cambio fuente, crear el documento de seguimiento **nuevo** `odd/tasks/aportes-y-patrimonio.md`, su espejo Engram `odd/aportes-y-patrimonio/tasks` y el TODO de ejecución. Especificaciones con citas del usuario, reglas contables y ejemplos aprobados; Log original textual y evidencias por unidad. No reabrir el backlog ni convertir la antigua QA pendiente en aprobada.
3. Ejecutar estas unidades con RED → GREEN y commits convencionales de unidad, con tests/docs junto al comportamiento:

| Unidad | Resultado y ruta | Superficie de edición | Commit previsto |
| --- | --- | --- | --- |
| T1 | Cálculo y proyección backend certificada; worker acotado. | Nuevo módulo/prueba de wallet; store owned; API owned; pruebas backend de lectura enumeradas. | `feat(laboratories): derive retained-wallet funding from saved sessions` |
| T2 | DTO, formato y jerarquía frontend; worker acotado. | API frontend owned; Panel; result-model; CSS local; pruebas frontend enumeradas. | `feat(laboratories): show contributed funds and final wealth` |
| T3 | Integración, ayuda/documentación y comprobación funcional; parent inline. | Solo los tres documentos enumerados y correcciones estrictamente necesarias en T1/T2. | `docs(laboratories): explain simulated wallet contributions` |
| T4 | Verificación independiente de contabilidad e integración certificada, solo lectura. | Leer el documento completo y ejecutar sus ejemplos contra estado aislado; sin editar el candidato. | Evidencia en el documento/espejo; si descubre defecto, corrección y commit en la unidad afectada, nunca «PASS» por ausencia de informe. |

- T1 y T2 pueden lanzarse juntos en background porque este plan fija el DTO y sus superficies son disjuntas. Cada writer recibe `## Allowed edit surfaces` exactas y la referencia al documento/tarea/specs; no otorgar globs de todo el repositorio.
- No compartir ediciones en los mismos archivos entre writers; README/diseño/QA quedan en T3, no en ambos productores.
- La sensibilidad contable y del camino de caché/instantánea requiere una verificación independiente focalizada después de los checks propios. No sustituirla por una lectura estética o por el resultado de otro trabajo anterior. Seguir la evaluación nativa y el switch RDD vigentes cuando corresponda, sin reparar autoridad ni inventar cierres.
- La suma de código, pruebas y documentación puede superar 400 líneas. Mantener unidades pequeñas de revisión; si luego se solicita PR, proponer PRs encadenados, no una macro-PR. No crear ni publicar PRs automáticamente.
- Cerrar tareas solo con resultados observados; un timeout o verificador no disponible se registra, no se reintenta a ciegas ni se marca como prueba aprobada. Usar background para builds, servidores y verificaciones de duración desconocida, sin polling.

## Verification

### Tabla contable obligatoria

Capital por sesión: `2000`. La lista muestra los saldos finales cronológicos; cada fixture debe ser consistente con sus premios/apuestas y con el neto almacenado. Los ejemplos incompletos corresponden al final del período.

| Caso | Saldos finales de las sesiones | Aporte total | Patrimonio final | Neto existente |
| --- | --- | ---: | ---: | ---: |
| Sin sesiones | `[]` | 0 | 0 | 0 |
| Ejemplo aprobado | `[2800]` | 2000 | 2800 | +800 |
| Reinversión sin otro aporte | `[2800, 2000]` | 2000 | 2800 | +800 |
| Ganancia y luego quiebra | `[2800, 0]` | 2000 | 800 | −1200 |
| Mismo neto, orden inverso | `[0, 2800]` | 4000 | 2800 | −1200 |
| Recarga parcial, no otro capital entero | `[2800, 0, 2000]` | 3200 | 2000 | −1200 |
| Última sesión incompleta | `[2800, 1500]` | 2000 | 2300 | +300 |
| No recargar después del final | `[0]` | 2000 | 0 | −2000 |

### Pruebas y criterios de aceptación

- [ ] Observar RED antes de implementar cada regla nueva y GREEN después. Los fixtures de los casos anteriores deben incluir capital del snapshot, orden real e incompletas; afirmar enteros exactos y la identidad patrimonio − aportes = neto.
- [ ] Los dos órdenes con neto −1200 producen aportes y patrimonio diferentes: protege contra derivar la billetera desde agregados.
- [ ] Probar valores grandes dentro del rango seguro y rechazo de importes de wallet inválidos, sin flotantes o silencios. Ninguna prueba modifica reglas numéricas ya existentes del motor.
- [ ] API pública en SQLite temporal: POST `201`, GET frío `200`, GET cálido `200`, mismo wallet; las demás claves/valores, snapshot y SHA permanecen iguales. Un owner incorrecto y un resultado dañado conservan exactamente sus errores anteriores.
- [ ] GET no modifica uso/cuota, contadores, resultados o sesiones almacenadas. Las pruebas de corrupción usan únicamente fixtures aislados; nunca la base del usuario.
- [ ] Certificado: cálculo completo solo en frío; cálido no vuelve a decodificar toda la corrida ni a recorrer sesiones para wallet. Se mantienen SQL paginado, época/instantánea, rechazo por tamaño y límites de caché, con los nuevos bytes contabilizados.
- [ ] Un resultado sintético de más de 50 sesiones tiene exactamente los mismos tres importes antes/después de paginar. No se añaden llamadas para descargar todas las páginas.
- [ ] Frontend: ejemplo `RD$2.000 / RD$2.800 / +RD$800`, pérdida con signo, cero y billetera ausente/inválida. El fallback no oculta las métricas anteriores ni inventa aportes.
- [ ] Conservar Volumen apostado, Premios recibidos, retorno, contadores, media de cerradas en su detalle, tabla, ventana, huecos y SHA completos. No duplicar Neto en el resultado seleccionado ni añadir ROI sobre aportes.
- [ ] Preservar reconciliación de POST incierto, separación de cargas detalle/sesiones, selección y página, foco, validación del formulario y ayuda de opciones. Ejecutar su regresión acotada, no solo los tests del nuevo cálculo.
- [ ] Navegador real en entorno aislado, API de pruebas o interceptada sin escrituras reales: escritorio, 600/390/320 px, teclado/toque y texto ampliado; importes legibles, sin overflow global; ayuda/detalles cerrados inicialmente. No confundir ampliación de texto con zoom real del navegador ni declarar WCAG global.
- [ ] Verificador independiente devuelve un veredicto por requisito y los resultados exactos de los ejemplos. Evidencia ausente o parcial queda explícita; no aprueba la QA histórica pendiente.

### Comandos previstos — no ejecutados en esta fase

Usar el entorno Python del proyecto ya configurado, sin instalar dependencias automáticamente. Elegir los casos API sintéticos y acotados; no incluir los dos contraejemplos completos de más de 50.000 sesiones del backlog histórico.

Desde `webapp/backend`:

```text
python -B -m pytest tests/test_laboratory_wallet.py tests/test_owned_laboratory_read_api.py tests/test_owned_laboratory_read_queries.py tests/test_owned_laboratory_run_store.py tests/test_owned_laboratory_run_list.py tests/test_owned_laboratory_read_cache.py -q
```

Desde `webapp/frontend`:

```text
node node_modules/vitest/vitest.mjs run src/pages/laboratories/result-model.test.ts src/pages/laboratories/Workspace.test.tsx src/pages/laboratories/LaboratoryForm.help.test.tsx src/api/laboratories.test.ts
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
```

Completar con diagnóstico LSP activo de los archivos cambiados, `git diff --check`, lectura de diff y comprobación funcional aislada. Las pruebas/backend, build, servidor y navegador se ejecutan solo tras aprobar, con comandos y salidas registrados; no se declara aquí ningún check como PASS.

## Out of Scope

- Cambiar apuestas, capital operativo por sesión, rankings, historial, modelos, precios/premios, objetivos, cierres, resultados o detección de corrupción.
- Una billetera global entre corridas/laboratorios, depósitos/retiros reales, límite nuevo de fondos, simulación con quiebra personal o una estrategia distinta de reinversión.
- Nuevas migraciones, reescritura/backfill de corridas, cambios de huellas o formatos persistidos, visitas a la base habitual, `.env`, `repo_ref/`, `lagacy_loto/` o los datos congelados.
- Eliminar métricas, menús o rutas actuales; modificar los contratos de referencia/v1 legacy o los formateadores compartidos.
- Introducir dependencias, nuevas pantallas, un segundo ROI, gráficos, promesas de ganancias futuras o una revisión estética general.
- Reejecutar automáticamente la suite global o la QA pendiente transferida al usuario; restaurar el antiguo gate JD, reparar autoridad RDD o reinterpretar faltas de evidencia como aprobaciones.
- Implementar, crear rama/commits, publicar, borrar ramas o abrir PR durante esta fase de plan.

## Estado de las fases y aprobación

1. **Explore:** completada con lectura del código y scout sin escritura.
2. **Clarify:** evaluada; sin preguntas pendientes. Política y límites quedan explícitos arriba.
3. **Generate Plan:** este archivo es el único artefacto creado.
4. **Notify & Execute:** notificar que el plan está listo y esperar aprobación explícita. **Ejecución pendiente de autorización.**

No se omitió ninguna fase de planificación. No se implementó nada ni se ejecutaron tests. Aprobar este plan es un paso separado del pedido de elaborarlo.
