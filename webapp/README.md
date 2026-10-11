# Laboratorio de corridas — Quiniela 80

Aplicación local para probar estrategias sobre el historial de Quiniela 80 y consultar qué habría ocurrido. **No hace apuestas reales, no predice sorteos ni calcula probabilidades futuras.** Los informes describen resultados históricos; no prometen resultados futuros.

## Qué está implementado

La aplicación tiene dos pantallas:

- **Corridas:** crear una corrida histórica con mezcla de rankings o paridad, consultar informes y detalle disponible, repetir una configuración con cambios y borrar corridas guardadas.
- **Ajustes:** revisar el uso y la cuota de almacenamiento; importar un historial JSON que se valida y fusiona con el historial activo.

Una corrida usa apuesta fija: la apuesta mínima indicada por cada número de la cobertura. Cada sesión empieza con el capital configurado; se cierra al alcanzar la meta, no poder financiar la apuesta siguiente o llegar al límite opcional de sorteos. La sesión que queda abierta al terminar los datos se informa como incompleta. Las mezclas usan rankings disponibles de pos1; la paridad es la otra estrategia ejecutable. El inventario más amplio de estrategias y presets es referencia histórica, no una lista de funciones actuales: [catálogo de referencia](../docs/catalogo-estrategias.md).

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

Los informes fijan la huella y el origen del historial usados al ejecutar; una importación posterior no reescribe corridas anteriores. El detalle de sesiones y apuestas se guarda sujeto a límites de 50.000 sesiones, 250.000 apuestas y 32 MiB; el informe indica si el detalle quedó completo, parcial o truncado.

## Datos y migraciones

- Entradas congeladas de solo lectura: `chance_express_history.json` y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`. El servidor verifica sus SHA-256 al iniciar; si no coinciden, no inicia.
- Los datos generados se guardan fuera del repositorio y de OneDrive, en `%LOCALAPPDATA%\LaboratorioQuiniela` por defecto; `LABORATORIO_DATA_DIR` permite cambiar esa ubicación.
- El esquema actual de SQLite es la versión 15. El arranque inicializa una base nueva o aplica, en orden, las migraciones conocidas hasta la versión actual; una versión desconocida se rechaza. **No edites ni reemplaces las migraciones SQL.**
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
