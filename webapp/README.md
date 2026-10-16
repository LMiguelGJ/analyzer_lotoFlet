# Quiniela

Aplicación local para probar estrategias sobre el historial de Quiniela 80 y consultar qué habría ocurrido. **No hace apuestas reales, no predice sorteos ni calcula probabilidades futuras.** Los informes describen resultados históricos; no prometen resultados futuros.

## Qué está implementado

El inicio abre **Laboratorios**. El menú principal contiene **Laboratorios** y **Ajustes**:

- **Laboratorios:** una sola pantalla con los laboratorios guardados a un lado y, en el centro, su configuración, la ejecución, las corridas guardadas y sus resultados. Cada laboratorio tiene su propia ruta (`/laboratorios/<id>`); `/laboratorios/nuevo` abre el formulario de creación manual.
- **Ajustes:** revisar el uso y la cuota de almacenamiento; importar un historial JSON que se valida y fusiona con el historial activo.

**Corridas anteriores:** se conserva el acceso directo a `/corridas`, `/corridas/nueva` y `/corridas/<id>` para consultar, crear, repetir o borrar pruebas sobre el historial activo. Se retiró esta sección del menú principal para evitar dos entradas que parecen equivalentes. No se borraron datos ni se modificó su motor.

Una corrida de esa sección usa apuesta fija: la apuesta mínima indicada por cada número de la cobertura. Cada sesión empieza con el capital configurado; se cierra al alcanzar la meta, no poder financiar la apuesta siguiente o llegar al límite opcional de sorteos. La sesión que queda abierta al terminar los datos se informa como incompleta. Las mezclas usan rankings disponibles de pos1; la paridad es la otra estrategia ejecutable. El inventario más amplio de estrategias y presets es referencia histórica, no una lista de funciones actuales: [catálogo de referencia](../docs/catalogo-estrategias.md).

La interfaz usa la dirección visual de la libreta cuadriculada descrita en [DESIGN.md](../DESIGN.md).

## Preparación e inicio

1. Usá Python 3.12 o superior y las dependencias declaradas en `backend/pyproject.toml`. El launcher usa `webapp/backend/.venv` si existe; de lo contrario busca el launcher de Python `py`.
2. En `frontend/`, instalá las dependencias con `npm ci` y compilá con `npm run build`. El launcher requiere `frontend/dist/index.html`.
3. Ejecutá [`iniciar-laboratorio.bat`](../iniciar-laboratorio.bat) desde el explorador o una consola. El servidor escucha solo en `127.0.0.1:8765` por defecto y abre el navegador cuando está listo. Para detenerlo, presioná **Ctrl+C en esa consola**; cerrar el navegador no detiene el servidor.

Podés configurar `LABORATORIO_PORT`, `LABORATORIO_DATA_DIR` y `LABORATORIO_QUOTA_BYTES`. La cuota predeterminada es 5 GiB; si `LABORATORIO_QUOTA_BYTES` está definida, la cuota se muestra como solo lectura en la aplicación. El directorio de datos predeterminado es `%LOCALAPPDATA%\LaboratorioQuiniela` (o `~/.local/share/LaboratorioQuiniela` si `LOCALAPPDATA` no existe). El servidor se niega a iniciar si los archivos congelados no coinciden con sus hashes esperados.

## API local

Todas las rutas viven bajo `/api/v1` y el servidor acepta solicitudes solo desde el origen local. Los límites de página aplican a listados y detalles.

| Método y ruta | Uso |
| --- | --- |
| `GET /settings` | Cuota, uso de almacenamiento, huellas de las fuentes y conexión. |
| `PUT /settings` | Guarda la cuota en bytes; responde conflicto si es de solo lectura o menor que el uso actual. |
| `GET /history` | Consulta el historial activo y las fuentes guardadas. |
| `POST /history` | Importa el cuerpo JSON sin multipart; máximo 32 MiB. La importación se valida, se fusiona con la fuente activa y puede rechazarse por conflicto o cuota. |
| `GET /runs/options` | Sistemas de ranking, valores predeterminados, límites de detalle e información del historial activo. |
| `POST /runs` | Ejecuta y guarda una corrida; el cuerpo de la solicitud admite hasta 64 KiB. |
| `GET /runs?offset=0&limit=20` | Lista corridas guardadas; `limit` entre 1 y 100. |
| `GET /runs/{id}` | Lee el informe guardado. |
| `DELETE /runs/{id}` | Borra una corrida guardada. |
| `GET /runs/{id}/sessions?offset=0&limit=50&outcome=…` | Lista sesiones; filtro opcional: `goal`, `ruin`, `limit` o `incomplete`. |
| `GET /runs/{id}/sessions/{ordinal}/bets?offset=0&limit=20` | Consulta apuestas de una sesión. |
| `GET /laboratories?offset=0&limit=20` | Lista definiciones administrables; `limit` entre 1 y 100. |
| `POST /laboratories` | Crea un UUID nuevo con `name` y `config` versionada; cuerpo máximo 64 KiB. |
| `GET /laboratories/{id}` | Definición y contadores de corridas/sesiones owned. |
| `DELETE /laboratories/{id}` | Confirma `confirmed_run_count`; elimina definición y sus resultados, sin borrar corridas heredadas. |
| `POST /laboratories/{id}/runs` | Ejecuta la configuración guardada contra la referencia fija; requiere `required_history_sha256`, máximo 64 KiB. |
| `GET /laboratories/{id}/runs?offset=0&limit=20` | Lista resúmenes por owner explícito; `limit` entre 1 y 100. |
| `GET /laboratories/{id}/runs/{run_id}` | Snapshot histórico, resumen y capacidades; no devuelve sesiones completas. |
| `GET /laboratories/{id}/runs/{run_id}/sessions?offset=0&limit=50` | Página estable de sesiones con ordinal; `limit` entre 1 y 100. |

Los informes fijan la huella y el origen del historial usados al ejecutar; una importación posterior no reescribe corridas anteriores. Las corridas históricas/legacy y las de referencia conservan sus límites existentes de 50.000 sesiones, 250.000 apuestas y 32 MiB; el informe indica si su detalle quedó completo, parcial o truncado.

### Laboratorios administrables

La configuración manual v1 incluye sistema, cobertura, estilo (`bold`, `ladder`, `flat`), capital, meta, cinco premios y ventana `YYYY-MM-DD HH:MM`. El replay usa esos valores y el UUID real, no sustituye la definición por un nombre del catálogo. Los resultados guardan la definición y huellas originales; no inventan trazas por apuesta (`per_bet_trace: false`).

Estas corridas usan únicamente la historia congelada: importar otra historia en Ajustes no cambia esta fuente ni reescribe resultados. POST/detalle devuelven un resumen y `snapshot`, mientras las sesiones se consultan aparte. Se conserva el resultado completo: el máximo de sesiones admitido deriva de los sorteos elegibles de esa ejecución, no del límite histórico/legacy de 50.000. La escritura sigue limitada a 32 MiB por corrida y a la cuota/disco disponibles; una ejecución válida que exceda los bytes reales permitidos responde 409 («El resultado completo supera el límite de almacenamiento de una corrida.»), igual que una cuota insuficiente, y no se guarda parcialmente. Una huella distinta, cambio/borrado de definición durante el replay o datos dañados también producen conflicto 409. Datos/cuerpo inválidos responden 422; IDs inexistentes, 404.

Las catorce definiciones iniciales se insertan una sola vez. Podés eliminarlas; reiniciar no las repone. Recrear manualmente un nombre/configuración genera otro UUID sin recuperar resultados de la identidad eliminada. El DELETE exige el contador owned leído recientemente; si cambió, responde 409 para volver a confirmar.

### Aportes y patrimonio simulado

El POST de una corrida administrable y su GET de detalle agregan `summary.wallet`: `policy: "retain-gains-top-up-v1"`, `out_of_pocket` y `final_wealth`. Los demás campos, el listado y las páginas de sesiones conservan su contrato. Es una proyección de todas las sesiones validadas y del capital del snapshot: no reescribe resultados ni huellas, no requiere migraciones y no vuelve a ejecutar corridas antiguas.

La billetera conserva ganancias y saldos entre sesiones. Antes de una sesión existente, solo suma el aporte externo que falte para financiar su capital; no recarga después de la última quiebra. No supone retiros ni combina corridas. Sin sesiones, ambos importes son cero. Siempre se cumple `final_wealth - out_of_pocket = totals.total_net`.

Por ejemplo, aportar RD$2.000 y ganar RD$800 deja RD$2.800 de patrimonio; reutilizar ese saldo no es otro aporte. «Volumen apostado» sí puede contar el mismo dinero varias veces. Estos importes son una simulación histórica, no depósitos bancarios reales ni una garantía de ganancias futuras. Una respuesta anterior sin billetera muestra «No disponible» en las dos cifras nuevas, sin ocultar las métricas existentes.

### Pantalla de laboratorios

- **Crear:** el formulario valida en el cliente las mismas reglas que el servidor (el servidor sigue siendo la autoridad) y solo guarda las reglas; no ejecuta nada. Los valores iniciales copian la configuración de referencia, pero todos los campos se pueden editar. Las reglas de un laboratorio no se editan: para cambiarlas se crea otro.
- **Ejecutar:** usa el resumen SHA-256 de la fuente congelada que informa el servidor. Si la respuesta se pierde por un fallo de red, la pantalla no reenvía la ejecución: pide actualizar las corridas guardadas antes de intentar otra.
- **Resultados:** primero «Tu dinero · Simulación», con Aportado de tu bolsillo, Patrimonio al final y Ganancia / pérdida (el neto existente). Debajo, Movimiento de apuestas conserva volumen, premios recibidos y retorno; la media neta de cerradas queda en «Detalle de sesiones». Se mantienen contadores, procedencia y tabla paginada. «ⓘ Cómo se calcula» explica la billetera sin texto permanente. No hay detalle por apuesta.
- **Eliminar:** el diálogo indica cuántas corridas y sesiones se perderán y envía ese conteo al servidor. Si cambió mientras tanto, el servidor responde 409 y la pantalla recarga los datos para volver a confirmar. No existe borrado individual de corridas.
- Los montos históricos conservan su signo explícito; por ejemplo, el capital configurado aparece como `+RD$2.000`. Solo los dos importes absolutos nuevos de billetera omiten el `+`: `RD$2.000` aportados y `RD$2.800` de patrimonio. Ganancia / pérdida y retorno mantienen el signo.

## Interfaz entregada y validación pendiente

- Ante una ejecución sin confirmación, no se reenvía automáticamente. «Actualizar corridas guardadas» mantiene el bloqueo hasta que termina correctamente una consulta nueva; si falla o se cancela, la incertidumbre continúa.
- Cambiar la página de sesiones conserva el resumen y consulta solo sesiones. El backend usa certificados compactos por instancia de Repository: la lectura fría valida toda la corrida; las lecturas calientes usan el resumen certificado y `ORDER BY ordinal LIMIT/OFFSET` para las sesiones. La caché está limitada a 64 entradas y 16 MiB de payload; una época SQLite invalida los certificados ante mutaciones. No se promete coste O(página) en frío ni aceptación integral de integridad.
- Los tres importes de billetera encabezan el resultado; Ganancia / pérdida reutiliza el neto existente. «Retorno sobre apostado» se conserva en Movimiento de apuestas: ROI = `100 × neto / apostado`, incluidas las incompletas, con dos decimales y signo; sin apuestas se muestra «No disponible». Las métricas anteriores conservan sus valores; no se agrega otro ROI sobre aportes.
- «Números seleccionados» describe cobertura, no probabilidad. «Sin ranking entre extremos» cuenta `gaps` dentro del tramo elegible, no todos los sorteos excluidos. «Datos de la reproducción» conserva completas las huellas de historial, rankings y sesiones.
- A 860 px o menos, el panel seleccionado precede a la lista en el DOM; sin selección, la lista queda primero. Redimensionar conserva borrador, selección y página. El formulario inválido anuncia un resumen y enfoca el primer campo que requiere corrección.

U1B/U2 tienen verificación técnica independiente focalizada y U4 revisión favorable de presentación/lógica; no equivalen a validación visual integral. El usuario solicitó cerrar la entrega de código y revisar el resto personalmente. **La aceptación manual y la matriz completa de integridad de U1/U3 siguen pendientes**; no se ejecutó una regresión completa ni los dos contraejemplos API de más de 50.000 sesiones. Seguí la [guía de QA manual](../docs/quiniela-ui-manual-qa.md) y registrá lo observado, sin dar casos no ejecutados por aprobados.

## Datos y migraciones

- Entradas congeladas de solo lectura: `chance_express_history.json` y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`. El servidor verifica sus SHA-256 al iniciar; si no coinciden, no inicia.
- Los datos generados se guardan fuera del repositorio y de OneDrive, en `%LOCALAPPDATA%\LaboratorioQuiniela` por defecto; `LABORATORIO_DATA_DIR` permite cambiar esa ubicación.
- El código registra SQLite versión 20, con época de integridad y triggers. La caché y las lecturas SQL paginadas de U3 están integradas, con comprobaciones focalizadas; su aceptación completa de integridad sigue pendiente. Esto no autoriza migrar la base habitual. El arranque inicializa una base nueva o aplica, en orden, las migraciones conocidas hasta la versión actual; una versión desconocida se rechaza. **No edites ni reemplaces las migraciones SQL.**
- Antes de copiar la base, detené la aplicación con Ctrl+C. No copies un archivo SQLite mientras el servidor está ejecutándose.

## Estructura actual

```text
webapp/
├── backend/
│   ├── laboratorio/
│   │   ├── api/             # settings, history y runs bajo /api/v1
│   │   ├── domain/          # reglas y motor de sesiones históricas
│   │   ├── engine/          # historial activo, rankings y preparación de corridas
│   │   └── storage/         # SQLite, cuota y persistencia de informes/detalle
│   └── pyproject.toml
└── frontend/
    └── src/
        ├── api/             # cliente y contratos HTTP
        ├── components/      # navegación y controles compartidos
        ├── pages/runs/      # formulario, lista e informes de corridas
        ├── pages/settings/  # cuota e importación del historial
        └── styles/          # tokens y estilos compartidos
```
