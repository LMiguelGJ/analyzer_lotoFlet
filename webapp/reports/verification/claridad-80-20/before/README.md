# Evidencia «antes» — CI00 (claridad-interfaz-80-20)

- **Fecha:** 2026-09-30
- **Commit HEAD:** `c19dc64cd7d7258a3e3717161cfdfcdf67e471f1`
- **Tarea:** CI00 — línea base técnica y capturas «antes», previas a cualquier cambio de código de aplicación.

## 1. Estado de Git

```
git status --short
```

Resultado observado:

```
 D lottery-predictability-monte-carlo
?? .pi/plans/claridad-interfaz-80-20.md
?? odd/tasks/claridad-interfaz-80-20.md
```

Coincide con lo esperado: la única modificación preexistente es la eliminación del
gitlink `lottery-predictability-monte-carlo` (no tocada, no stageada, no restaurada) y
los dos artefactos ODD/plan agregados antes de esta tarea. No se modificó ningún
archivo fuente, prueba, configuración ni documentación de la aplicación.

## 2. Línea base técnica del frontend

Comandos ejecutados desde `webapp/frontend`:

| Comando | Resultado observado |
|---|---|
| `npm run test -- --run` | **251/251 pruebas verdes** (24 archivos de prueba, 24 passed). Duración 55.43 s. Se observan trazas de consola `Error: unknown execution status value: bogus` — corresponden a un caso de prueba intencional de `StatusLabel` con un valor de estado desconocido, no a fallos; el resumen final reporta 0 fallos. |
| `npm run typecheck` | `tsc --noEmit` sin salida — **0 errores de tipos**. |
| `npm run build` | `vite build` exitoso: 58 módulos transformados, `dist/index.html` (0.41 kB), `dist/assets/index-*.css` (15.47 kB), `dist/assets/index-*.js` (357.60 kB). El `dist/` regenerado está ignorado por Git (confirmado con `git status --short` tras el build: sin cambios nuevos). |

No se instalaron dependencias, no se ejecutó `npm audit fix`, no se modificó ningún
archivo fuente, de prueba, de configuración ni de backend.

## 3. Entorno aislado para capturas

- **Raíz del harness:** `%TEMP%/ci-80-20-harness` (bajo el directorio temporal del
  sistema operativo, fuera del repositorio y fuera de los datos personales del
  usuario en `%LOCALAPPDATA%\LaboratorioQuiniela`).
- **Directorio de datos aislado:** `%TEMP%/ci-80-20-harness/data`, provisto vía
  `LABORATORIO_DATA_DIR`.
- **Comando de arranque:** desde `webapp/backend`, con `LABORATORIO_DATA_DIR` y
  `LABORATORIO_PORT=8791` exportados:

  ```
  py -3 -B -m laboratorio.app
  ```

- **Puerto:** 8791 (no es el puerto por defecto 8765, evita colisión con una
  instancia personal del usuario). El servidor se vincula exclusivamente a
  `127.0.0.1`, sirviendo el frontend ya compilado (`dist/`) y la API en el mismo
  origen, tal como documenta `webapp/README.md`.
- **Proceso:** PID del proceso Python confirmado por identidad
  (`Get-Process -Id <pid>` → `python.exe`, ruta `C:\Python314\python.exe`) antes de
  detenerlo. No se usó kill por nombre ni por árbol de procesos.
- **Cierre:** el proceso se detuvo al finalizar esta tarea; el puerto 8791 queda
  libre. El directorio de datos del harness **se conserva** en
  `%TEMP%/ci-80-20-harness/data` para reutilizarse sin cambios en CI04.

## 4. Datos sembrados (fixtures sintéticas aisladas)

Todos los datos se crearon exclusivamente a través de la API pública del propio
servidor aislado (peticiones same-origin, sin cabeceras Host/Origin remotas ni
CORS), nunca editando la base de datos directamente. Son datos ficticios de
verificación, no experimentos reales del usuario:

1. **Configuración guardada (biblioteca):** «Plantilla frío conservadora» —
   estrategia individual con selector `system`/`cold`, cobertura 20, apuesta
   `flat`.
2. **Experimento corto (dos estrategias):** «Captura línea base 80-20» — sorteo
   inicial `2025-09-02 05:10`, capital RD$1.000, meta RD$2.000, semilla 42,
   liquidación `all`, `max_bets=25`. Estrategias: una individual (`system`/`cold`,
   cobertura 20, apuesta `flat`) y una aleatoria reproducible (`random`, cobertura
   10, apuesta `ladder`). Completó de inmediato (outcome `limit` en ambas
   ejecuciones, deltas +131 y +264 DOP) gracias al límite bajo de apuestas.
3. **Experimento con nombre largo:** nombre de 79 caracteres, cercano al límite de
   80, sorteo `2025-09-02 05:10`, capital RD$500, meta RD$1.000, semilla 7,
   liquidación `best`, `max_bets=25`. Estrategia mezcla (`blend`) de dos sistemas
   (`cold` + `decay`, 50/50), cobertura 10, apuesta `bold`. Completó de inmediato
   (outcome `goal`, delta +550 DOP).

La finalización de cada experimento se confirmó sondeando `GET
/experiments/{id}` hasta observar `status: completed` (ambos completaron en la
primera consulta por el `max_bets` bajo).

## 5. Capturas realizadas

Todas en `webapp/reports/verification/claridad-80-20/before/`, formato
`<pantalla>-<ancho>.png`, página completa (`--full-page`), anchos 1280 px y
390 px:

| Pantalla | Descripción |
|---|---|
| `experiments-empty` | Listado de experimentos con el directorio de datos recién creado, **antes** de sembrar datos. |
| `experiments` | Listado de experimentos ya con las dos filas sembradas. |
| `wizard-conditions` | Paso 1 («Condiciones») del asistente de nuevo experimento, formulario en blanco. |
| `wizard-strategies` | Paso 2 («Estrategias») tras completar el paso 1 con datos válidos (sorteo, capital, meta, semilla) y avanzar con «Continuar», sin enviar el experimento. |
| `detail` | Detalle del experimento corto (dos ejecuciones completadas). |
| `comparison` | Comparación del mismo experimento (2/2 ejecuciones terminadas). |
| `library` | Biblioteca de configuraciones con la plantilla sembrada. |
| `settings` | Página de ajustes (cuota, formato es-DO). |
| `queue-drawer` | Cajón de cola abierto desde el botón «Cola». |
| `not-found` | Ruta inexistente (`/ruta-que-no-existe`). |

Tamaño total de la carpeta: **~1,3 MB** (20 archivos), sin perfiles de navegador,
bases de datos, cachés ni trazas incluidas en el repositorio.

## 6. Límites de esta evidencia

- Navegación **headless** (Chromium vía playwright-cli); no se validó
  comportamiento con navegador visible ni interacción manual del usuario.
- **No se midió zoom real al 200 %** en esta tarea; queda pendiente para CI04
  como validación manual o medición dedicada, nunca emulado vía viewport o CSS
  transform como si fuera zoom real.
- No se afirma conformidad WCAG ni contraste medido; esta tarea es solo
  levantamiento de línea base y capturas «antes».
- El asistente («wizard-strategies») se capturó tras avanzar del paso 1 al 2 con
  datos válidos, sin enviar el experimento, como pide la consigna; no se probó el
  paso «Revisar» ni el envío real desde el asistente en esta tarea.
- Las capturas usan datos sintéticos de verificación generados por esta tarea, no
  datos reales de uso del laboratorio.

## 7. Comandos para relanzar el mismo harness en CI04 («después»)

Para reutilizar exactamente el mismo directorio de datos sembrado (sin volver a
sembrar), desde `webapp/backend`:

```bash
export LABORATORIO_DATA_DIR="$LOCALAPPDATA/Temp/ci-80-20-harness/data"
export LABORATORIO_PORT=8791
py -3 -B -m laboratorio.app
```

En PowerShell/cmd equivalente:

```bat
set LABORATORIO_DATA_DIR=%LOCALAPPDATA%\Temp\ci-80-20-harness\data
set LABORATORIO_PORT=8791
py -3 -B -m laboratorio.app
```

El servidor quedará disponible en `http://127.0.0.1:8791/` con los mismos dos
experimentos completados y la configuración guardada descritos en la sección 4.
Detener el proceso propio (identity-checked) al finalizar, sin matar árboles de
procesos ni procesos ajenos.
