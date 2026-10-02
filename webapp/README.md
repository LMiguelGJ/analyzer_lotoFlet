# Laboratorio web — Quiniela 80

Herramienta local para explorar estrategias sobre el historial de Quiniela 80
ya recopilado. Corre en la propia computadora, sobre datos históricos
congelados; **no realiza apuestas reales, no predice sorteos en vivo y no se
publica en Internet**.

Detalle funcional completo en `../especificaciones-laboratorio-web.md` y plan
de trabajo en `../odd/tasks/laboratorio-web.md`.

## Inicio rápido (Windows)

1. Prepará una vez Python 3.12+ con `py` y pip, y Node/npm para instalar las
   dependencias y compilar el frontend. Seguí los [comandos de preparación](#inicio-local-en-windows-lw16);
   **no es un ejecutable autónomo**. Para el uso diario sigue siendo necesario
   Python con sus dependencias, pero Node solo hace falta al compilar.
2. Hacé doble clic en `iniciar-laboratorio.bat` en la raíz. Dejá abierta la
   consola: sirve el backend y el frontend **ya compilado** en el mismo origen,
   `http://127.0.0.1:8765/` por defecto, solo en esta computadora.
3. Para terminar, presioná **Ctrl+C en esa consola** y esperá la salida.
   Cerrar la pestaña o el navegador **no** detiene el servidor ni la cola.

## Estado actual

**18/18 tareas cerradas (LW01–LW18).** LW18 cerró con evidencia acotada de
seis pantallas, 30 pares pantalla/ancho, contraste, movimiento reducido,
carga, error 503 inyectado y comparación incompleta **preparada** (1/2).
Las seis pantallas y el cajón de cola están implementados; el usuario aceptó
manualmente el lanzador LW16. Esa aceptación no convierte el doble clic, la
apertura del navegador predeterminado ni Ctrl+C en pruebas automatizadas: el
smoke aislado usó un stub de navegador y `CTRL_BREAK_EVENT`; un intento seguro
de probar `CTRL_C_EVENT` terminó en WinError 5 sin emitir la señal. No se afirma
aceptación integral de todos los estados o conformidad WCAG.

La API nativa que usa la interfaz local no requiere credencial Bearer y confía en clientes locales; no es una frontera frente a otros procesos. El facade para agentes (`/api/agent/v1`) requiere Bearer y sus mutaciones también validan el `Origin` local exacto, pero esto no aísla procesos ni habilita acceso remoto. Las regresiones de Bearer malformado/duplicado y publicación concurrente de credenciales están corregidas; la verificación independiente aprobó 8 pruebas enfocadas y Ruff. La re-verificación independiente de Ajustes aprobó 31 pruebas y typecheck, tras resolver tres correcciones. Esto no demuestra ACL de producción, durabilidad ante fallos ni aislamiento entre procesos. La credencial se consulta explícitamente desde Ajustes; consultá la [guía breve de API para agentes](../docs/api-agentes-80-20.md).

La cola comparte un único sondeo y conserva el registro de acciones durante la navegación entre rutas de
la misma sesión React; cerrar el cajón no lo descarta. Si una solicitud de
inicio/cancelación queda incierta, «Comprobar estado» consulta el detalle guardado.
Solo tras comprobarlo se ofrece reintentar un inicio aún retenido o reenviar
una cancelación en un estado permitido, con confirmación explícita; el servidor
rechaza inicios duplicados. Nunca se reenvía automáticamente. Una **recarga
completa** descarta el registro de acciones en memoria: comprobá cola y detalle
antes de volver a actuar.

## Uso cotidiano

| Pantalla | Qué hacer / qué significa |
| --- | --- |
| **Experimentos** (`/experimentos`) | Buscá, filtrá y ordená el listado paginado; abrí un detalle, usá una solicitud histórica como base para **otro** experimento o borrá con confirmación. |
| **Nuevo experimento** (`/experimentos/nuevo`) | Elegí sorteo del catálogo, capital, meta (saldo final), semilla y hasta cinco estrategias; revisá y agregá a la cola. La mezcla suma puntos de ranking, no probabilidades. |
| **Detalle** (`/experimentos/:id`) | Consultá estados de cada ejecución, apuestas guardadas paginadas, gráfico y reproducción **visual**; reproducir o pausar no vuelve a calcular. |
| **Comparación** (`/experimentos/:id/comparacion`) | Compará resultados completados; N/M cuenta las configuraciones solicitadas, y las faltantes no reciben métricas inventadas. Las curvas unen solo puntos cargados, sin proyectar los que faltan. |
| **Configuraciones** (`/configuraciones`) | Guardá y reutilizá una estrategia por configuración; editarla o borrarla no cambia los experimentos históricos, que conservan sus parámetros. La búsqueda por nombre filtra solo la página cargada. |
| **Ajustes** (`/ajustes`) | Consultá cuota, uso lógico, disco libre, tamaño físico y procedencia de fuentes; editá la cuota si no la fija el entorno. No hay limpieza, compactación ni recuperación de espacio garantizada. |

Abrí **Cola** desde la cabecera para ver activo, pendientes y retenidos en
páginas separadas. Un trabajo retenido tras reiniciar requiere «Iniciar» manual;
la ejecución interrumpida **no se reanuda**. Cancelar preserva configuraciones
completadas, descarta el resultado parcial de la activa y deja las restantes
sin ejecutar. Una respuesta a la solicitud de cancelación no confirma el estado
terminal: comprobá el detalle. Una desconexión del navegador tampoco demuestra
que se haya detenido el trabajo del servidor.

Los resultados son simulaciones históricas sobre datos ya investigados, **no
una validación independiente ni una probabilidad de éxito o promesa de ganancias**.
Cada experimento guarda la solicitud y la procedencia de sus fuentes (IDs,
SHA-256, versión); no acredita un período de validación separado.

### Datos, cuota y copia de seguridad

Por defecto, los datos generados se guardan en
`%LOCALAPPDATA%\LaboratorioQuiniela\`; `LABORATORIO_DATA_DIR` cambia esa
carpeta. Los insumos congelados del repositorio son de **solo lectura** y no se
incluyen en el presupuesto de experimentos. La cuota efectiva sigue el orden
`LABORATORIO_QUOTA_BYTES` (entero positivo en bytes, solo lectura en la web) >
preferencia guardada en Ajustes > valor por defecto. **Si la variable existe
pero está vacía**, el código toma el valor por defecto de **5 GiB** y aun así
la considera explícita: Ajustes queda de solo lectura y no aplica la
preferencia guardada. Quitá la variable del entorno para volver a usar esa
preferencia; otros valores mal formados impiden el arranque. El valor
implementado por defecto es **5 GiB = 5.368.709.120 bytes**; la
especificación [D6] dice «5 GB». Se deja visible esa diferencia de unidades, sin cambiar la
especificación ni interpretar 5 GB como 5.000.000.000 bytes. Uso lógico,
tamaño físico SQLite/WAL y disco libre son medidas distintas. No hay purga ni
`VACUUM` automático; borrar registros no garantiza achicar el archivo.

**Antes de hacer una copia de seguridad, detené la aplicación con Ctrl+C y
esperá a que el proceso cierre.** Luego copiá la carpeta de datos completa
(incluida `laboratorio.db` y los archivos asociados que existan) a una ubicación
segura; no copies la base abierta como un archivo «en caliente». Conservá
aparte los insumos congelados con sus huellas si necesitás reproducir cálculos.
No alteres el historial JSON ni el NPZ originales para liberar espacio.

### Si algo falla

| Síntoma | Qué comprobar |
| --- | --- |
| Falta Python o dependencias | Prepará el entorno Python local y sus dependencias según [Inicio local](#inicio-local-en-windows-lw16). Node/npm no reemplazan Python. |
| Falta el build | Desde `webapp/frontend`, ejecutá `npm ci` y `npm run build` tras preparar Node/npm; el lanzador no lo hace por vos. |
| Puerto ocupado | Cerrá la otra instancia **solo si es tuya** o elegí `LABORATORIO_PORT` libre (1024–65535) antes de iniciar; no abre una pestaña hacia el proceso ajeno ni lo mata. |
| HTTP 403 en mutaciones | Usá la web desde el mismo origen/puerto del servidor; la API exige Host local y Origin exacto, sin CORS remoto. |
| HTTP 507 | Falta margen en la cuota lógica o en el disco libre: revisá Ajustes; ampliar cuota no crea espacio físico, y borrar filas no promete recuperar disco. |
| Desconexión o solicitud incierta | El servidor podría seguir trabajando o haber recibido la acción. Reconectá, consultá Cola y detalle y confirmá el estado antes de reintentar; no asumas parada. |
| `WinError 5` en un test del harness LW17 | Un intento aislado de reemplazo de caché NPZ falló y las repeticiones pasaron; la causa no está demostrada. No se atribuye automáticamente a OneDrive ni se toma como fallo habitual del usuario. |

El detalle conserva la URL durante el cálculo y consulta el estado guardado;
una desconexión del navegador no demuestra que la ejecución se haya detenido.
Cada configuración finalizada conserva sus métricas incluso si el experimento
se canceló o interrumpió. La reproducción mueve únicamente un cursor visual:
lee páginas de hasta 20 apuestas guardadas, no recalcula ni realiza apuestas.
El gráfico muestra solo los saldos de la página cargada y señala cuando la
serie está incompleta. Para cada resultado guardado, la API proyecta el delta
como saldo final menos capital de la solicitud inmutable; la pantalla lo muestra
en DOP sin recalcularlo en el navegador. Las ejecuciones sin resultado no tienen delta.
La comparación en `/experimentos/:id/comparacion` muestra el progreso N/M
solicitado que devuelve la API, sin completar métricas de ejecuciones sin
resultado. Las filas enlazan al detalle de la ejecución y el retorno conserva
la selección y hasta 500 apuestas cargadas por serie en `sessionStorage` de
ese experimento; más páginas se pueden cargar manualmente, pero al volver a
la vista se recuperan solo las primeras 500. Cada serie consulta hasta 100
apuestas por página, solo tras completar la ejecución y bajo demanda después
de la primera. El eje compartido usa fechas/horas de las apuestas guardadas;
las líneas son conectores visuales entre puntos cargados, no observaciones
intermedias ni proyecciones. Los controles de series no modifican los
resultados. Las fuentes registran IDs, hashes y versión, no un período de validación.
Estos resultados históricos sobre datos ya investigados no validan rentabilidad
independiente ni permiten inferir probabilidades de éxito. La aceptación visual
en navegador y con zoom no queda demostrada por las pruebas unitarias.

## Estructura

```text
webapp/
├── README.md
├── backend/
│   ├── pyproject.toml            # dependencias, pytest y ruff
│   ├── laboratorio/
│   │   ├── app.py                # fábrica FastAPI y ciclo de vida explícito
│   │   ├── settings.py           # puerto, loopback, ubicación de datos
│   │   ├── domain/               # reglas puras: contratos, selección y sesiones
│   │   ├── engine/               # único lector del historial JSON y el NPZ de rankings
│   │   ├── storage/               # migración SQLite y repositorio
│   │   ├── jobs/                  # cola serial y proceso aislado de cálculo
│   │   └── api/                   # rutas HTTP /api/v1
│   └── tests/                    # un archivo de pruebas por módulo
└── frontend/                     # seis pantallas (LW08–LW14) y cajón de cola (LW15)
    ├── package.json · vite.config.ts · tsconfig.json · index.html
    ├── src/
    │   ├── main.tsx · App.tsx     # data router y rutas (react-router-dom)
    │   ├── api/                  # cliente HTTP tipado para /api/v1 y mapeo de errores
    │   ├── lib/                  # formateadores DOP/00-99 y utilidad de contraste WCAG
    │   ├── styles/tokens.css     # paleta, tipografía y espaciado (UX2-UX11)
    │   ├── components/           # Shell, StatusLabel, ConfirmDialog, StrategyEditor, DataTable
    │   └── pages/                # asistente, listado, detalle, comparación, biblioteca y ajustes
    └── dist/                     # generado por `npm run build`, ignorado por Git
```

## Datos de entrada (congelados, solo lectura)

El laboratorio nunca modifica estos archivos; el motor verifica su SHA-256
al cargarlos y conserva una copia verificada del NPZ para las lecturas diferidas
de rankings. Reemplazar el archivo después de cargarlo no altera los datos ya
validados de esa instancia.

| Archivo | SHA-256 |
| --- | --- |
| `chance_express_history.json` | `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711` |
| `repo_ref/reports/chance_rank_v1/predictions/pos1.npz` | `b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d` |

`repo_ref/` es exclusivamente material de referencia de lectura (reglas de
negocio y datos de rankings). El motor de esta web se escribió desde cero en
`webapp/backend/laboratorio/`; no importa ni depende en tiempo de ejecución
de ese código.

## Dónde viven los datos generados por la web

Fuera del repositorio, para no interferir con la sincronización de OneDrive:

```text
%LOCALAPPDATA%\LaboratorioQuiniela\
├── laboratorio.db   # configuraciones y experimentos; creación explícita
├── cache\           # votos par/impar calculados sobre el historial
└── logs\
```

La variable de entorno `LABORATORIO_DATA_DIR` reemplaza esa ubicación (las
pruebas automatizadas siempre usan un directorio temporal aislado). La caché
de votos es un único archivo NPZ por historial y versión del algoritmo: incluye
huella SHA-256 de los votos, identificador del algoritmo y SHA-256 del historial.
Si falta, está incompleta o no coincide, se recalcula y se reemplaza de forma
atómica. Detecta corrupción accidental; no autentica datos frente a alguien
capaz de modificar tanto la caché como sus metadatos.

## Motor de sesiones (LW03)

`domain/session.py` recibe condiciones, estrategia y sorteos cronológicos ya
preparados; no accede a archivos, HTTP ni SQLite. `engine/adapter.py` prepara
esos sorteos desde el historial y rankings verificados y selecciona números
mediante sistema, mezcla, azar o par/impar. Exige que el sorteo inicial tenga
ranking; los huecos posteriores consumen tiempo, sin generar apuestas.

La meta es saldo final. Cada apuesta registra fecha, números, importe por número,
gasto, cinco resultados, cobro y saldo. Los pagos Q80 son acumulados por posición
o solo el mayor por número repetido. El reloj empieza en el sorteo inicial: el
sorteo que alcanza el límite temporal ya no se apuesta. Después de liquidar una
apuesta se evalúa meta, luego si el saldo financia la próxima apuesta prescrita
y por último el límite de cantidad de apuestas. Al terminar el historial sin
otro desenlace se devuelve `history_exhausted`. Los resultados de sesión son inmutables; la cancelación entre sorteos pertenece
a la cola de trabajos.

La prueba de regresión compara **las 141 combinaciones y todas sus primeras
sesiones** con `tests/fixtures/reference_sessions.json`, sin regenerarlo.

## Persistencia local (LW04)

El ciclo de vida de `create_app(settings)` llama explícitamente a
`initialize_database(settings.database_path)` antes de crear
`Repository(settings.database_path)`. No se crea la base al importar módulos
ni al construir la aplicación; se inicializa al entrar en el ciclo de vida. La migración inicial es repetible y una versión desconocida se
rechaza sin reemplazar sus tablas. No se migran versiones futuras ni se purgan
datos automáticamente. Para pruebas se usa exclusivamente una ruta temporal.

`Repository` guarda estrategias con nombre mediante `create_configuration`,
`get_configuration`, `list_configurations`, `update_configuration` y
`delete_configuration`. `create_experiment` recibe un `ExperimentRequest`
validado (condiciones, semilla y hasta cinco estrategias), IDs y SHA-256 de
historial/rankings, versión del código y, opcionalmente, IDs de configuraciones
en el mismo orden. Congela esos parámetros y fuentes al crear el experimento.
Los IDs son cadenas generadas; las consultas inexistentes devuelven `None` y
los borrados inexistentes, `False`.

`start_run`, `complete_run` y `complete_experiment` exigen transiciones
válidas; el resultado terminado incluye todas las apuestas con sus importes
enteros y se lee mediante `get_experiment` o `list_experiments` sin consultar
el motor ni los archivos originales. `mark_run` y `mark_experiment` permiten
registrar estados incompletos (`held`, `cancelled`, `interrupted`, `failed`,
`not_run`) sin convertirlos en resultados terminados. `recover_jobs` retiene
los experimentos pendientes e interrumpe los abandonados al inicio;
`finish_incomplete` registra de manera atómica la activa y las restantes sin
tocar resultados completados. Borrar una configuración desvincula sus experimentos
pero conserva sus copias de parámetros y apuestas. `delete_experiment` borra
explícitamente ese experimento y rechaza uno activo. La confirmación humana de
borrado corresponde a la API de LW07, no al repositorio.

## Cola local (LW05)

La API inicializa la base, crea **una sola** `JobQueue` por base y proceso,
llama a `start()` antes de admitir peticiones y a `shutdown()` al salir del
ciclo de vida. `start()` convierte ejecuciones abandonadas en
`interrupted` y experimentos pendientes en `held`; nunca retoma una activa ni
arranca trabajos guardados automáticamente. Después de crear un experimento
nuevo, debe llamar a `enqueue(id)`; `start_held(id)` exige una acción manual
explícita. `cancel(id)` admite un trabajo activo, en cola o retenido.
`active_id`, `pending_ids()` y los estados persistidos del repositorio permiten
consultar la cola. `last_error` expone el último error del coordinador para
registro/diagnóstico; no constituye un resultado de sesión.

Cada configuración corre en un proceso nuevo mediante `spawn` de Windows. Solo
el proceso padre guarda resultados completos verificados; el hijo no abre
SQLite. La cancelación se comprueba entre sorteos, sin esperar una sesión
completa; si un paso se bloquea, el padre termina el proceso tras un breve
plazo de gracia. Se conservan configuraciones terminadas, se descarta la activa
y las restantes quedan `not_run`. Una muerte inesperada o datos inválidos
marca la activa y el experimento como `failed`, sin guardar resultados parciales;
la siguiente tarea puede continuar. `shutdown()` marca como `interrupted` la
activa, deja los pendientes para retención en el siguiente arranque y espera a
que finalice la limpieza del hijo. Cerrar el navegador no afecta al servidor.
La API de LW07 integra ese ciclo de vida; un fallo de carga de datos congelados
impide iniciar, y un fallo de arranque de la cola intenta cerrar los recursos.

## Cuota y protección del disco (LW06)

`Settings.quota_bytes` tiene un valor inicial de **5 GiB** (5 × 1024³ bytes).
Se puede configurar al iniciar el proceso mediante `LABORATORIO_QUOTA_BYTES`,
con un entero decimal positivo en bytes, hasta 2⁶³−1; un valor no vacío
mal formado impide iniciar. Si está **definida pero vacía**, se usa 5 GiB
(`_quota_from("")`) y se marca como entorno explícito, por lo que la web
queda de solo lectura aunque haya una preferencia guardada. Sin la variable,
`PUT /api/v1/settings` guarda una cuota persistente en SQLite; el orden
efectivo es entorno explícito > preferencia guardada > 5 GiB. No aumenta sola.

`Repository.quota_status(settings.quota_bytes, quota_explicit=settings.is_quota_explicit)`
devuelve `limit_bytes`, `logical_used_bytes`, `logical_margin_bytes`, `free_disk_bytes`,
`disk_margin_bytes`, `database_bytes`, `wal_bytes`, `shm_bytes`, `temp_bytes`,
`sqlite_bytes` (suma de los cuatro archivos locales) y `warning`. El uso lógico
suma los **bytes UTF-8 de campos de experimentos y ejecuciones** (parámetros
copiados, IDs, origen y hashes, versión, estados, JSON de resultados y 8 bytes
por ordinal). No cuenta configuraciones reutilizables, caché, JSON/NPZ originales,
páginas libres de SQLite ni sus índices. El tamaño físico incluye la base y los
archivos locales conocidos `-wal`, `-shm`, `-journal` y `-stmtjrnl`; SQLite también
puede usar temporales administrados por el sistema operativo que no se pueden
atribuir ni medir aquí. `free_disk_bytes` es el espacio libre del volumen de la
base, **no** el espacio recuperable al borrar filas.

La admisión de ejecuciones (`enqueue`, `start_held` y justo antes de cada
configuración pendiente) exige espacio lógico restante **mayor** que un margen
de `min(1 MiB, max(1 byte, cuota/20))` y disco libre **mayor** que 64 MiB.
Antes de guardar un resultado se comprueba bajo la transacción SQLite el tamaño
UTF-8 serializado exacto más el cambio de estado, conservando ambos márgenes.
Son reservas conservadoras para nuevas escrituras, no una garantía contra el
crecimiento real de WAL, journal o temporales. Al superar un umbral se rechaza
una ejecución nueva; un trabajo pendiente previamente admitido puede quedar
`held` si cambia el espacio antes de comenzar. Un trabajo activo que ya no
puede continuar se marca `failed` si el almacenamiento lo permite, conservando
las configuraciones completadas y sin presentar resultados parciales como
terminados. No se borran datos ni se ejecuta `VACUUM` automáticamente.

La API obtiene el estado con `Repository.quota_status(...)`, traduce
`QuotaExceeded` a HTTP 507 y expone `JobQueue.last_failure` de manera
sanitizada para diagnóstico: contiene ID,
error, `persisted` y `persistence_error`. `persisted=True` **solo** confirma que
se pudo guardar `failed`. Si el disco o SQLite impiden registrar el fallo,
queda un error observable en memoria y la cola deja de admitir tareas; tras
reiniciar, `recover_jobs()` marca la antigua ejecución activa como
`interrupted` y retiene las pendientes para inicio manual. No se afirma que el
fallo haya quedado persistido ni que borrar un experimento reduzca el archivo.
La API lee la cuota efectiva y permite guardar la preferencia; la pantalla de
Ajustes presenta estos límites sin confundir el uso lógico con el tamaño físico.
La admisión de creación suma, en una transacción de escritura SQLite, los bytes
lógicos proyectados del nuevo experimento y sus ejecuciones antes de insertar.
La cola vuelve a comprobar capacidad al encolar y antes de ejecutar; si falla
el encolado se elimina la fila pendiente recién creada. La medición de disco
sigue siendo una instantánea con carrera frente a escrituras externas: **no
constituye un límite físico estricto** ni asegura espacio real para WAL.

## API local (LW07)

Desde `webapp/backend`, `py -3 -B -m laboratorio.app` inicia el servidor de
producción (API y `frontend/dist` en el mismo origen). El lanzador usa ese mismo
módulo. `LABORATORIO_PORT` acepta 1024–65535 (por defecto 8765); el servidor
se vincula exclusivamente a `127.0.0.1`.
`Settings.from_environment()` usa `%LOCALAPPDATA%` para los datos y exige que
los dos insumos congelados existan y coincidan con sus huellas. La ausencia o
corrupción de un insumo impide el arranque; no se inventa un catálogo vacío.
Sin `frontend/dist/index.html` se rechaza el arranque con instrucciones para
compilar: nunca se abre una API sin UI de manera silenciosa. Cerrá el proceso
servidor con Ctrl+C para detenerlo; cerrar el navegador no detiene la cola.

Base: `http://127.0.0.1:8765/api/v1` (también se admite `localhost` para el
mismo puerto). El servidor rechaza `Host` no local o puerto distinto; las
mutaciones requieren un encabezado `Origin` **exactamente igual** a
`http://<Host>` y rechazan `Sec-Fetch-Site: cross-site`. Sin CORS comodín ni
cuentas. El build de producción comparte origen con la API; el frontend de
desarrollo en otro puerto usa el proxy de Vite. La API no debe exponerse mediante
proxy remoto ni escuchando en `0.0.0.0`.

| Método y ruta relativa | Respuesta y función |
| --- | --- |
| `GET /catalog` | Juego Q80, 13 sistemas, coberturas, fuentes y primeras 100 fechas iniciales con `starting_draws_total` |
| `GET /catalog/starting-draws?offset=0&limit=100` | Fechas con ranking paginadas; máximo 100 |
| `POST /experiments` | `201 {id,status}`; cuerpo `{request: ExperimentRequest, configuration_ids?: (string|null)[]}`; crea y encola |
| `GET /experiments?offset=0&limit=20` | `{total,offset,limit,items}`; máximo 100; búsqueda `name_contains` (literal Unicode, sin distinguir mayúsculas, ≤80), `status` de ejecución, `sort=created_at|name|status`, `order=asc|desc`; total filtrado y desempate por ID en la misma dirección; sin apuestas masivas |
| `GET /experiments/{id}` | Condiciones, estrategias, fuentes y resumen por ejecución; sin replay completo |
| `GET /experiments/{id}/runs/{ordinal}/replay?offset=0&limit=20` | Apuestas persistidas, máximo 100; nunca recalcula |
| `GET /experiments/{id}/compare` | Resumen de N/M ejecuciones terminadas; incompletas separadas |
| `DELETE /experiments/{id}` | `204`; cuerpo `{confirm_id: id}`; rechaza trabajo activo/en cola |
| `POST /configurations`, `GET /configurations`, `GET /configurations/{id}`, `PUT /configurations/{id}` | Estrategias guardadas; crear/editar con `{name,strategy}`; listado paginado |
| `DELETE /configurations/{id}` | `204`; cuerpo `{confirm_id: id}`; conserva copias previas de experimentos |
| `GET /queue?offset=0&limit=20` | Activo, páginas de pendientes y retenidos (máximo 100 cada una), y `last_failure` sanitizado con `persisted` explícito |
| `POST /queue/{id}/start` | `200`; inicio manual **solo** de una retenida (`held`) |
| `POST /queue/{id}/cancel` | `200`; solicita cancelar activa o cancela en cola/retenida |
| `GET /settings` | Vista completa de cuota efectiva/persistida y procedencia, uso lógico exacto, disco libre, archivos físicos locales, fuentes y conexión |
| `PUT /settings` | `{ "quota_bytes": "5368709120" }` (cadena decimal ASCII canónica 1..2⁶³−1); devuelve la misma vista completa y guarda la preferencia si no hay cuota de entorno |

El JSON usa los identificadores y enteros de `domain/contracts.py` (capital,
meta, apuestas y saldos son enteros DOP, sin decimales). Ejemplo mínimo de
`POST /experiments`:

```json
{"request":{"name":"Prueba","conditions":{"start_draw":"2025-09-02 05:10","capital":100,"goal":200,"seed":42,"settlement":"all"},"strategies":[{"name":"Fríos","selector":"system","system":"cold","coverage":1,"staking":"flat"}]}}
```

Elegí la fecha real mediante `/catalog/starting-draws`; el ejemplo no garantiza
que se financie una apuesta ni un desenlace favorable. Los campos desconocidos
y validaciones de Pydantic reciben `422`; fecha sin ranking o confirmación
incorrecta, `400`; inexistente, `404`; transición o borrado activo, `409`;
cuota/disco insuficiente, `507`; Host/Origin inválidos, `403`. El borrado nunca
se ejecuta por GET ni automáticamente. Un resultado completo es inmutable;
replay, listado y comparación consultan SQLite sin ejecutar el motor.
`GET /queue` devuelve `active_id` (ID o `null`), `pending` y `held` con
`{total,offset,limit,count,items}`, además de `last_failure` (objeto o `null`).
El mismo `offset` (índice desde cero) y `limit` (entre 1 y 100; predeterminado
20) se aplican **por separado** a pendientes y retenidos: `total` es el tamaño
de cada conjunto antes de paginar, `items` son sus IDs en orden de cola para
pendientes y de inserción para retenidos, y `count` es la cantidad de IDs en
esa página (`0` si `offset >= total`). Para recorrer ambos conjuntos hay que
avanzar cada uno hasta alcanzar su propio `total`; los totales pueden cambiar
entre peticiones si avanza la cola. La respuesta no materializa todos los IDs
pendientes para generar una página. **Cambio incompatible en esta API previa a
la integración inicial del frontend:** se retiró `pending_ids` (antes incluía la cola completa); los clientes
que lo consumían deben leer `pending.items` y `pending.total`, y paginar si
necesitan recorrerla. No se ofrece un alias sin límite que oculte este cambio.

Si `shutdown()` no confirma la parada del coordinador, el ciclo de vida
propaga el error y retiene la propiedad de la base: una segunda instancia no
puede iniciarse mientras siga vivo. Cuando termina la limpieza y el hilo ya
se detuvo, un nuevo inicio puede recuperar esa propiedad; no se anuncia una
parada exitosa ante un timeout. `last_failure.persisted=false` indica que no se
pudo confirmar el estado de fallo en SQLite; la API no entrega trazas internas.
`quota.effective_bytes` y `quota.persisted_bytes` son cadenas decimales exactas
(`persisted_bytes` puede ser `null`); `quota.source` es `default`, `persisted`
o `environment`, y `quota.writable` indica si se puede guardar. La cuota de
entorno explícita prevalece incluso sobre una preferencia anterior y bloquea
PUT con `409`. Un presupuesto inferior al uso lógico también devuelve `409`
sin mutar la preferencia. `storage.logical_used_bytes_exact` es la cadena
exacta para presentar y comparar uso; los campos numéricos previos de
`storage`, incluido `limit_bytes`, son de compatibilidad y no deben usarse
para redondear la cuota en JavaScript. Un cuerpo de PUT numérico, booleano,
con signo, fracción, exponente o fuera de rango devuelve `422` localizado en
`body.quota_bytes`. Una mutación con Host/Origin no autorizado devuelve `403`.
El cambio se evalúa en la próxima admisión o escritura, no cancela de forma
retroactiva una ejecución activa. No se limpia, compacta ni aumenta sola la
cuota.

## Frontend local (LW08)

Shell React 18 + TypeScript + Vite 7 + React Router 7 + Tailwind CSS 3,
con Vitest 5 + Testing Library + jsdom + jest-axe para pruebas. Las versiones
locales se verificaron con Node 24.14.0: Vite 7 admite Node ^20.19.0 o
>=22.12.0, Vitest 5 admite ^22.12.0, ^24.0.0 o >=26.0.0, y React Router 7
admite Node >=20 y React >=18. El lockfile evita resolver versiones distintas
en cada instalación. El asistente `pages/new-experiment/` crea experimentos y la biblioteca
`pages/configurations/` administra estrategias guardadas; `pages/settings/`
consulta y edita la cuota cuando el servidor lo permite. El cajón de Cola
(LW15) está implementado y verificado funcionalmente; LW18 cerró con una
aceptación visual **muestreada**, no integral. La cola
comparte el sondeo de página del Shell (cada cinco segundos): pendientes y
retenidos se paginan por separado y sus consultas no son una instantánea
atómica. La ausencia de un ID de una página no demuestra que salió de la cola.
Tras iniciar, el estado pendiente o activo confirma la transición; una fila
retenida desactualizada no vuelve a ofrecer «Iniciar» hasta actualizarse. Tras
solicitar cancelar, la respuesta solo acusa recibo: se espera un estado terminal
del experimento, y una fila desactualizada conserva sus acciones bloqueadas.
Si falla la red, la acción puede haber llegado: se reconcilia con la cola
compartida y, si falta evidencia suficiente, con el detalle del experimento;
una consulta de detalle fallida no autoriza repetirla. La navegación incluye
Experimentos, Configuraciones y Ajustes con URLs estables, enlace «saltar al
contenido», `Shell`, `StatusLabel` (vocabulario de estado de ejecución
distinto del desenlace de sesión, texto + forma, nunca solo color),
`ConfirmDialog` (foco atrapado, Escape, devolución de foco), cliente HTTP
tipado para `/api/v1` con mapeo de errores (400/403/404/409/422/507 y
desconexión de red distinguida de un error del servidor) y formateadores DOP
/ 00-99.

### Ajustes (LW14)

`/ajustes` consulta `GET /api/v1/settings` y presenta la cuota efectiva,
preferencia persistida y procedencia. El formulario usa texto decimal de bytes
(1..2⁶³−1), valida antes de enviar y guarda con `PUT /api/v1/settings`;
únicamente la respuesta completa del servidor actualiza el valor mostrado.
Con una cuota de entorno explícita, la pantalla explica por qué no ofrece
editarla. Un rechazo 422 se localiza junto al campo; 409 por cuota inferior
al uso no afirma que se liberó espacio. Las fallas de red conservan el borrador
y advierten que la solicitud podría haber llegado; «Actualizar estado» consulta
la verdad del servidor sin pisar cambios sin guardar. La navegación y el cierre
del navegador advierten si hay un borrador modificado.

Uso lógico y cuota se muestran como enteros exactos. En otra sección figuran
el disco libre del volumen y los archivos físicos locales de SQLite (base,
WAL, SHM, temporales y total informado): no son consumo de presupuesto ni
espacio recuperable. El aviso de capacidad lo decide el backend; no se estima
cuánto liberará un borrado ni se ofrecen limpieza o compactación. Fuentes,
hashes y versión se consultan en una sección expandible de solo lectura; la
API no proporciona un período de cobertura. La conexión indica host/puerto y
versión informados, pero no permite administrar el proceso. Para detener la
aplicación usá Ctrl+C en la consola del lanzador; cerrar el navegador no
detiene la cola.

### Biblioteca de configuraciones (LW13)

`/configuraciones` consulta páginas acotadas de 20 filas; la búsqueda por nombre
filtra **solo la página cargada**, porque la API de configuraciones no admite
búsqueda en servidor. «Nueva» y «Editar» comparten `StrategyEditor` con el
asistente; el catálogo limita selectores, sistemas y coberturas. La edición
ordinaria es en línea. Guardar valida campos y muestra los rechazos 422 junto
al nombre de biblioteca, el campo o el bloque correspondiente; el detalle
técnico queda en texto secundario. El borrador permanece si falla la red o el
servidor, y la navegación o cancelación de un borrador modificado advierte de
la pérdida de cambios. Una confirmación de borrado exige el mismo ID en
`confirm_id`; Escape cancela y el foco vuelve al control de origen. Si la fila
ya no existe, se actualiza la página; si era la última, se retrocede a la
anterior. Borrar una estrategia de la biblioteca **no** borra resultados
históricos: cada experimento conserva la copia de parámetros de su ejecución.

### Asistente de nuevo experimento (LW09)

`/experimentos/nuevo` guía por Condiciones → Estrategias → Revisión. El sorteo
inicial se elige exclusivamente de `/catalog/starting-draws` paginado (100 por
página): no se descarga todo el historial ni se preselecciona una fecha no
confirmada. Se validan enteros decimales antes de construir `{request:…}`;
los campos se conservan como texto durante la edición y no se redondean.
La semilla admite el rango entero 0..9.007.199.254.740.991 (2⁵³ − 1,
`Number.MAX_SAFE_INTEGER`): es el mayor entero que `JSON.parse`/`response.json()`
representan sin redondeo en el navegador, de modo que la semilla mostrada tras
crear el experimento siempre coincide con la ingresada (ver [F16] en
`especificaciones-laboratorio-web.md`; antes se aceptaba un entero de 64 bits
que Pydantic validaba pero que se redondeaba al volver del backend como
número JSON). La meta significa saldo final, no ganancia adicional. La mezcla
combina puntos de ranking mediante porcentajes, nunca probabilidades, y
par/impar fuerza cobertura 50. `src/components/StrategyEditor.tsx` es el
único editor reutilizable para la biblioteca LW13; no hay cálculo financiero
en React.

Los nombres de estrategia duplicados se detectan con la **misma** regla de
normalización en frontend (`normalizeStrategyName` en
`src/pages/new-experiment/model.ts`) y backend (`normalize_strategy_name` en
`webapp/backend/laboratorio/domain/contracts.py`): normalización Unicode NFKC,
recorte de un conjunto explícito de espacios (categoría Unicode Zs más
controles ASCII de espacio en blanco —deliberadamente distinto de
`str.strip()`/`trim()`, que difieren en caracteres como U+FEFF—) y plegado de
mayúsculas/minúsculas vía `upper()` seguido de `lower()` (no `casefold()`/
`toLocaleLowerCase()`, que pliegan casos como la eszett alemana de forma
asimétrica entre los dos lenguajes). Ambos lados se prueban contra el mismo
fixture `webapp/backend/tests/fixtures/strategy_name_cases.json`. El backend
localiza el error de nombre duplicado en el campo del 422
(`["body","request","strategies",i,"name"]`) en vez de la raíz de la
solicitud, y el asistente bloquea el avance junto al campo antes de enviar
(UX29).

El envío usa `POST /api/v1/experiments` y navega a
`/experimentos/{id}` después del `201`. El detalle consulta el estado guardado
mientras se procesa, sin inventar resultados. Los
errores 422 vuelven al campo/paso afectado; 507, 409 y desconexión dejan
los valores editados. Ante desconexión después de enviar, revisá el listado
antes de reintentar: el servidor podría haber recibido la solicitud. La
navegación interna y el botón Atrás del navegador usan el bloqueador de
React Router (data router creado una sola vez en `main.tsx`) y un diálogo
accesible para borradores con cambios; recargar/cerrar usa la confirmación
nativa del navegador. Salir nunca llama a cancelar la cola del backend.
La biblioteca LW13 guarda **una estrategia por configuración**, con nombre
propio de biblioteca y nombre independiente de estrategia. No guarda condiciones
comunes ni semillas. Desde `/configuraciones`, «Usar» abre
`/experimentos/nuevo?configuration=<id>`: reemplaza la única estrategia vacía
inicial con la guardada, pero deja nombre del experimento, sorteo, capital, meta,
límites y semilla sin completar. `?base=<id>` es diferente: copia la solicitud
histórica completa de un experimento. Si llegan `base` y `configuration` juntos,
el asistente muestra un error y no elige uno en silencio. Una precarga limpia no
advierte al salir; tras editar, cambiar o quitar el parámetro requiere confirmar.
Una respuesta tardía de otro origen no debe reemplazar el borrador actual.

En el paso Estrategias se puede añadir **una** estrategia de una página de
biblioteca a la vez (20 por página), repetir hasta cinco y conservar todas las
condiciones y estrategias ya editadas. El nombre duplicado normalizado y una
estrategia incompatible con el catálogo impiden añadirla; no se crean condiciones
implícitas. «Guardar estrategia en biblioteca» guarda únicamente la estrategia
activa con el nombre de biblioteca ingresado: no envía un experimento ni hace
cálculos. El envío del experimento mantiene su solicitud inmutable como fuente
autoritativa; no declara `configuration_ids` sin procedencia confiable.

Endurecimiento posterior de LW09:

- El nombre de cada estrategia se recorta con el **mismo** conjunto explícito
  de espacios en frontend (`trimName`) y backend (`_NAME_TRIM_RE`), tanto al
  guardar como al comparar duplicados. U+FEFF, U+0085 y U+200B no se recortan
  en ninguno de los dos lados, así que ambos llegan al mismo veredicto.
- `seed`, `capital`, `goal`, `max_bets`, `max_minutes`, `coverage` y el
  `weight` de cada componente de mezcla son enteros estrictos en el backend:
  un número enviado como texto o con decimales se rechaza con un 422
  localizado en el campo.
- Ubicación de los errores 422 en el asistente:

  | `loc` (después de `request`) | Dónde se muestra |
  | --- | --- |
  | `conditions.<campo>` | Junto a ese campo de condiciones |
  | `conditions` | Mensaje de la sección de condiciones |
  | `strategies.N.<campo>` | Junto a ese campo de la estrategia |
  | `strategies.N` | Mensaje del bloque de la estrategia, que se expande |
  | `name` | Campo de nombre del experimento |
  | Cualquier otro | Aviso general |

  El detalle técnico del servidor se muestra como texto secundario.
- Editar un campo limpia solo su error y el aviso general; los demás errores
  siguen visibles. Tras un 422, el foco va al primer campo con error y su
  bloque de estrategia se expande.
- Riesgo aceptado: Chrome/Node (ICU 78, Unicode 17) y Python 3.14
  (Unicode 16) difieren en 29 caracteres de bloques poco usados. Para esos
  caracteres la comparación de nombres podría diferir entre ambos lados; si
  el servidor detecta un duplicado, el error igual aparece junto al campo.

### Listado de experimentos (LW10)

`/experimentos` lista páginas de 20 según `offset`/`limit`/`total` del
servidor; busca por nombre (`name_contains`, literal Unicode, sin distinguir
mayúsculas) y filtra por estado real de ejecución, no por desenlace. La URL
conserva `name`, `status`, `sort`, `order` y `page` para recarga y Atrás;
valores inválidos se normalizan y cambiar filtros u orden vuelve a la página
1. El nombre se envía después de una pausa de 300 ms; respuestas anteriores
no pueden sobrescribir la consulta vigente. Solo Nombre, Creado y Estado
ordenan **todo el resultado filtrado en el servidor**, no solo la página
visible. La tabla muestra nombre (enlace estable al detalle),
cantidad de estrategias solicitadas, creación y estado con `StatusLabel`.
`created_at` llega en UTC ISO; se presenta en hora local con zona horaria
visible. Los registros anteriores a la migración 0002 tienen `null` y
muestran «—», nunca una fecha supuesta.

La acción primaria enlaza al asistente; un enlace «Volver a experimentos»
permite comprobar el guard de salida desde un borrador. La tarea activa se
consulta con `/queue?offset=0&limit=20` cada cinco segundos mientras la
pantalla está montada; `active_id` se resuelve mediante detalle y se enlaza
al experimento real, sin ETA ni métricas inventadas. Estados separados:
cargando, vacío sin filtros, sin coincidencias de la consulta global,
desconectado (`NetworkError` no confirma parada del servidor) y error
genérico; búsqueda y estado siguen disponibles para corregir o reintentar.

El menú de acciones de cada fila se abre con teclado, mueve el foco a la
primera acción, se cierra con Escape y devuelve el foco al botón; se dibuja
fuera de la región desplazable para evitar recortes. «Usar como base» abre
`/experimentos/nuevo?base=<id>` y lee `GET /experiments/{id}`: copia sin
mutar el original todas las condiciones y estrategias (incluidos componentes
y pesos). Busca el sorteo guardado en el catálogo paginado completo, sin
sustituirlo por el primero ni aprobarlo solo por estar entre los primeros
100. Mientras se carga, falta, falla la red o el catálogo ya no valida
el request, no se ofrece envío. La precarga sola queda **limpia**; cualquier
edición posterior activa la advertencia de salida, y únicamente «Agregar a
la cola» después de la revisión envía un POST nuevo. Salir no cancela la cola.

Eliminar usa el `ConfirmDialog` existente y envía `confirm_id` igual al id
del experimento (contrato de `DELETE /experiments/{id}`). Un 409 (experimento
activo o en cola) se explica en línea sin quitar la fila; un 404 (ya
eliminado por otra pestaña u otro proceso) refresca el listado en vez de
mostrar una confirmación sobre un recurso muerto. Tras un borrado exitoso se
vuelve a pedir la página actual y, si quedó vacía pero quedan experimentos
anteriores, retrocede una página en vez de mostrar una página muerta. El
foco no se pierde al desaparecer la fila eliminada: al cerrar el diálogo
vuelve primero al botón que lo abrió (todavía presente en ese momento) y,
cuando la fila se quita del listado, se mueve explícitamente al aviso
transitorio de confirmación (`role="status"`), que también sirve de anuncio.

`src/components/DataTable.tsx` conserva región desplazable, etiqueta y
`<caption>` accesibles; `aria-sort` se limita a los tres encabezados respaldados
por orden real del servidor. El botón «Cola» abre el cajón implementado en LW15; el indicador discreto
no sustituye la consulta del estado de la cola. El detalle, replay y biblioteca
se describen en las secciones anteriores.

### Desarrollo frontend

Desde `webapp/frontend` (dependencias instaladas **localmente**, sin paquetes
globales):

```bash
npm ci            # instalación reproducible desde package-lock.json
npm run dev        # servidor de desarrollo con proxy hacia el backend
npm run build       # compila a dist/ (servido por el backend)
npm run preview     # sirve el build de producción localmente
npm test -- --run   # Vitest
npm run typecheck   # tsc --noEmit
```

### Proxy de desarrollo y same-origin

El backend exige `Host` local y, para mutaciones, un `Origin` **exactamente
igual** a `http://<Host>` (`webapp/backend/laboratorio/app.py`); no tiene
CORS. Como el servidor de desarrollo de Vite corre en un puerto distinto al
backend, `vite.config.ts` reescribe **tanto** el encabezado `Host`
(`changeOrigin: true`) **como** el `Origin` (mediante `configure` +
`proxy.on("proxyReq", …)`) para que coincidan con el origen del backend
(`http://127.0.0.1:8765` por defecto, o `LABORATORIO_BACKEND_URL` si se
cambia el puerto del backend). El cliente HTTP del frontend (`src/api/client.ts`)
solo usa rutas relativas bajo `/api/v1`, de modo que toda petición del
navegador es same-origin frente a Vite; no se agregó CORS al backend.

### Tokens de diseño y contraste medido

`src/styles/tokens.css` fija la paleta UX2 exacta del documento de
especificación. `src/lib/contrast.ts` implementa el cálculo de contraste
WCAG (luminancia relativa) y `src/lib/tokens.test.ts` lo aplica sobre los
valores reales del archivo (no sobre una copia), verificando 4.5:1 para texto
y 3:1 para componentes de interfaz (UX3). Ratios medidos:

| Par | Ratio |
| --- | --- |
| Texto principal / fondo | 11.27:1 |
| Texto principal / superficie | 9.96:1 |
| Texto principal / campo | 9.12:1 |
| Texto secundario / fondo | 8.11:1 |
| Texto secundario / superficie | 7.17:1 |
| Texto secundario / campo | 6.56:1 |
| Acento / fondo | 7.48:1 |
| Acento / superficie | 6.61:1 |
| Acento / campo | 6.05:1 |

**Ajuste de token:** el separador decorativo `--color-border` (`#3b4652`, UX2
exacto) mide solo ~1.4–1.75:1 contra las superficies que separa, lo cual es
aceptable para un divisor decorativo entre paneles pero no para un borde de
control funcional. Se agregó un segundo token, `--color-border-control`
(`#6c7f92`), usado en bordes estáticos de campos, botones y el panel de
`ConfirmDialog` (no en el foco visible: `:focus-visible` usa `--color-accent`,
ver `src/styles/index.css`), que mide 4.07:1 contra fondo, 3.60:1 contra
superficie y 3.29:1 contra campo (los tres ≥3:1). `--color-border` se
mantiene sin cambios para separadores puramente decorativos, que no
requieren la medida de 3:1. El acento también se usa como texto plano en
`StatusLabel` (tono "positive"), así que `tokens.test.ts` exige además que
cumpla el umbral de texto (≥4.5:1), no solo el de componente (≥3:1); los tres
ratios de la tabla (7.48/6.61/6.05) superan ambos.

### Evidencia y límites de aceptación (LW17–LW18)

[Regresión y mediciones LW17](reports/verification/lw17/phase2-report.md): base de
**166 pruebas backend y 251 frontend** (más Ruff, typecheck y build), oráculo
con 141 casos/417 sesiones del fixture; el fallo previo `WinError 5` de un
intento de test quedó registrado en el [reporte inicial](reports/verification/lw17/report.md)
y no se reprodujo en las repeticiones aisladas. No se ejecutaron esas suites
para escribir esta guía. Medidas acotadas: inicio frío p50/p95
**2.074,729/2.187,529 ms (n=3)**; `GET /settings` con cola activa
**11,975/30,436 ms (n=10)**; `GET /experiments/{id}` sin carga activa
**32,433/41,106 ms (n=10)**; navegación de teclado hasta encabezado bajo
carga **24,700/31,900 ms (n=10)**. Son muestras distintas, no SLA ni
capacidad extrapolable. El POST de cancelar respondió en 7,104 ms, pero eso
**no mide** la llegada al estado terminal ni comprobó en vivo la retención de
una configuración previamente completada.

La [auditoría Chrome LW18](reports/verification/lw18/report.md) muestreó las seis rutas,
30 pares de pantalla/ancho (799/800/1099/1100/1280 px), tablas con scroll
local, teclado/diálogos, contraste computado y movimiento reducido. La muestra
corregida de contraste registró 93 resultados conformes al umbral aplicable,
37 selectores no observados y 6 bordes sin borde visible no aplicables. El
[seguimiento final acotado](reports/verification/lw18/final-followup.md) y su
[registro v2](reports/verification/lw18/final-followup-v2.json) observaron además
«Cargando experimentos…» con **respuesta real 200 retenida y luego liberada**,
un **503 inyectado** en el listado que mostró error genérico y se recuperó al
reintentar contra la API real, texto de estado «Completado» renderizado con
contraste **7,48:1**, y un contorno de foco de Cola contra el fondo **exterior**
con **7,48:1**. La retención de la respuesta no mide latencia; el 503 no fue
una caída real del servidor. El desenlace positivo no estuvo renderizado en
esa muestra y no se infiere su contraste.

Como evidencia **anterior de LW15, no repetida en LW18**, la
[cola retenida preparada](reports/verification/lw15/evidence/report.md) mostró
inicio manual (sin afirmar un crash observado); el
[retest de foco](reports/verification/lw15/evidence/focus-retest.md) observó que
Escape del diálogo anidado devuelve foco al botón de origen y el segundo Escape
cierra el cajón; el [retest del aviso](reports/verification/lw15/evidence/notice-retest.md)
observó el aviso enfocado a los **6.509 ms** y su retiro al salir con Tab.
El primer intento del seguimiento LW18 falló en el **harness**, antes de las
comprobaciones de navegador, y registró un cambio concurrente del hash del
README durante el trabajo documental planificado; los logs por sí solos no
identifican quién escribió exactamente esos bytes. El segundo intento conservó
su propio conjunto de 93 fuentes sin cambios. El 404 de consola sin URL del
muestreo inicial sigue **sin atribución histórica**; una petición explícita
posterior a `/favicon.ico` dio 404, pero no demuestra que fuera aquel 404.

El [seguimiento de comparación incompleta](reports/verification/lw18/incomplete-followup.md)
observó en navegador y API reales «1/2 terminadas», una ejecución calculada y
la otra sin resultado (guiones, no ceros fabricados). **La instantánea fue
preparada mediante persistencia controlada; no se observó una interrupción real.**
Esto completa el criterio acotado de LW18, sin atribuirle una caída del worker.

Estos son muestreos, **no una certificación WCAG AA general**. Las capturas y
reportes seleccionados están en el [archivo de verificación](reports/verification/README.md),
no forman parte del runtime de la aplicación ni garantizan estados no
capturados. Siguen sin medirse el zoom real al 200 % en LW18 y la cobertura
exhaustiva de estados, contrastes y foco. El zoom de LW08 y el lanzador LW16
tienen aceptación **manual** previa, no son nuevas mediciones de LW18. LW18
está cerrada **con esos límites**, no con una aceptación integral.

El runtime aislado de medición LW17 en el temporal del sistema operativo fue
retirado por el padre tras comprobar que no había procesos propios activos
(175 archivos; 4.874.833 bytes). Los insumos congelados y reportes conservados
son evidencia de lectura, no promesa de rendimiento futuro. Las referencias
a scripts y rutas temporales en los reportes archivados son procedencia
**histórica**, no instrucciones para ejecutarlos desde el archivo.

## Inicio local en Windows (LW16)

Preparación inicial, desde la raíz del repositorio (en `cmd.exe`):

```bat
py -3.12 -m venv "webapp\backend\.venv"
"webapp\backend\.venv\Scripts\python.exe" -m pip install -e "webapp/backend"
cd /d "webapp\frontend"
npm ci
npm run build
```

Necesitás Python 3.12 o superior, el lanzador `py`, pip y Node/npm **solo
para esta preparación o para recompilar**. Si `py -3.12` no está disponible,
seleccioná una versión compatible instalada para crear el entorno. Las
dependencias Python quedan en el entorno local del backend; `npm ci` instala
las del frontend localmente. No hay instalación global, servicio ni instalador
autónomo. `dist/` es generado e ignorado por Git: reconstruí después de
actualizar el frontend. Para el uso diario Node no hace falta.

Después, hacé doble clic en `iniciar-laboratorio.bat` desde cualquier carpeta,
incluso si la ruta contiene espacios. El script se ubica en su propia carpeta,
usa el Python del entorno local si existe (o `py -3` si ya tiene las
dependencias), verifica versión, dependencias, build y backend, y ejecuta un
único servidor **en primer plano**. Abre una sola vez el navegador **después**
de que su propia instancia haya cargado los datos y escuchado en
`http://127.0.0.1:8765/` (o el puerto de `LABORATORIO_PORT`). Si el puerto
está ocupado, informa el error sin matar procesos, cambiar el puerto ni abrir
una pestaña apuntando a otra instancia. Si faltan el build o los insumos
congelados, el servidor no abre el navegador; el error queda en la consola.
No compila ni instala automáticamente.

Para detenerlo presioná **Ctrl+C en la ventana de consola**; esperá la salida
de la cola antes de cerrar esa ventana. Cerrar solo el navegador no detiene
los trabajos. En una salida normal, la ejecución activa se interrumpe y las
configuraciones ya terminadas quedan guardadas; los experimentos pendientes
quedan retenidos al reiniciar y necesitan «Iniciar» manual. Cerrar la ventana
a la fuerza, cortar la energía o matar el proceso **no garantiza** la limpieza
de la ejecución activa en ese momento; el próximo arranque recupera una activa
abandonada como interrumpida y retiene pendientes, sin reanudar trabajo solo.
Si falla el arranque, la ventana espera una tecla para que puedas leer el error.
El usuario aceptó manualmente LW16 tras probar el lanzador. El smoke aislado
comprobó ruta con espacios, build ausente y puerto ocupado, pero usó
`CTRL_BREAK_EVENT` y un navegador stub: no verificó Ctrl+C auténtico ni apertura
del navegador predeterminado. El intento posterior de señal Ctrl+C se detuvo
por WinError 5 antes de emitirla; no se equiparan esas pruebas con la aceptación
manual.

## Desarrollo

Desde `webapp/backend`:

```bash
# suite de pruebas (incluye pruebas marcadas real_data, que usan los archivos congelados)
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -3 -B -m pytest tests -q -p no:cacheprovider

# análisis estático
PYTHONDONTWRITEBYTECODE=1 py -3 -B -m ruff check --no-cache .
```

Estos comandos requieren las dependencias Python disponibles en el intérprete
`py -3`; si preparaste el entorno local anterior, reemplazá `py -3` por
`".venv\Scripts\python.exe"` desde `webapp/backend`. El frontend requiere
`npm ci` local (ver arriba); el lanzador no instala nada.
