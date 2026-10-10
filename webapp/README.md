# Laboratorio de corridas — Quiniela 80

Herramienta local para probar una estrategia sobre el historial de Quiniela 80 ya recopilado y medir cómo le habría ido. Corre en tu computadora sobre datos históricos congelados: **no hace apuestas reales, no predice sorteos y no calcula probabilidades futuras**. Un resultado describe lo ocurrido en el historial; no promete nada hacia adelante.

## Estado

**En reconstrucción desde cero.** El plan está en `.pi/plans/reconstruccion-corridas.md` y su avance en `odd/tasks/reconstruccion-corridas.md`.

Hoy existe:

- **Backend** (`backend/`): el motor de corridas históricas (sesiones consecutivas con reinicio de capital), la traza acotada de sesiones y apuestas, la cuota de almacenamiento y la carga verificada del historial y los rankings.
- **Frontend** (`frontend/`): un esqueleto con dos secciones, **Corridas** y **Ajustes**, todavía como páginas de relleno. Las pantallas reales llegan en la tarea R5.

Se retiraron la simulación clásica, los perfiles de juego, los lotes, la cola, el acceso para agentes y todos los tests anteriores. Los datos que ya estaban guardados siguen en disco, pero la interfaz nueva no los muestra.

## Uso

1. Python 3.12 o superior con las dependencias de `backend/pyproject.toml` (`fastapi`, `uvicorn`, `pydantic`, `numpy`), y Node/npm solo para compilar el frontend.
2. En `frontend/`: `npm ci` y `npm run build`.
3. Doble clic en `iniciar-laboratorio.bat` (raíz). Sirve el backend y el frontend compilado en `http://127.0.0.1:8765/`, solo en esta computadora.
4. Para terminar, **Ctrl+C en esa consola**. Cerrar el navegador no detiene el servidor.

## API disponible

Todo bajo `/api/v1`, solo desde el mismo origen local:

| Ruta | Qué hace |
| --- | --- |
| `GET /settings` | Cuota, uso de almacenamiento, fuentes con sus huellas y conexión. |
| `PUT /settings` | Cambia la cuota, salvo que la fije `LABORATORIO_QUOTA_BYTES`. |
| `POST /backtests` | Ejecuta y guarda una corrida histórica. |
| `GET /backtests` | Lista paginada de corridas. |
| `GET /backtests/{id}` | Informe de una corrida. |
| `GET /backtests/{id}/sessions` y `/sessions/{n}/bets` | Detalle paginado, cuando se guardó. |

Estas rutas se reemplazan por `/api/v1/runs` en la tarea R4.

## Datos

- Entradas congeladas y de solo lectura: `chance_express_history.json` y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`. El servidor comprueba su SHA-256 al arrancar y no arranca si cambian.
- Datos generados: `%LOCALAPPDATA%\LaboratorioQuiniela\` (cambia con `LABORATORIO_DATA_DIR`). El esquema de la base es la versión 13 y las migraciones SQL no se modifican.
- **Antes de copiar la base, detené la aplicación con Ctrl+C.** No copies un archivo SQLite abierto.

## Estructura

```text
webapp/
├── backend/laboratorio/
│   ├── app.py            # fábrica FastAPI, middleware local y arranque
│   ├── settings.py       # puerto, carpeta de datos, entradas congeladas
│   ├── api/              # rutas /api/v1 (settings, backtests)
│   ├── domain/           # contratos, selección y motor de corridas
│   ├── engine/           # único lector del historial y los rankings
│   └── storage/          # SQLite, repositorio, cuota y traza
└── frontend/src/
    ├── App.tsx · main.tsx
    ├── components/       # Shell, ConfirmDialog, ui/
    ├── api/client.ts     # cliente HTTP
    └── styles/           # tokens y CSS base
```
