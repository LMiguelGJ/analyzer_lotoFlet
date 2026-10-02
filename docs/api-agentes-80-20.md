# API local para agentes: guía 80/20

Guía breve para automatizaciones locales; no es una API pública ni una frontera entre procesos. La aplicación trabaja sobre historiales guardados y simulaciones: no realiza apuestas ni predice sorteos en vivo. Los ejemplos no llevan credenciales ni datos reales.

## Acceso y confianza

1. Iniciá el servidor local y abrí la interfaz en su origen exacto. El puerto predeterminado es `8765`, pero puede configurarse.
2. En **Ajustes → Acceso para agentes**, pulsá **Consultar credencial de agente** y luego **Copiar credencial**. La consulta es explícita; la interfaz la oculta por defecto y no la guarda en almacenamiento del navegador. El servidor conserva la credencial localmente en `<Settings.data_dir>/agent-token`; los permisos del archivo son una medida de mejor esfuerzo, no aislamiento entre procesos.
3. Enviá la credencial como `Authorization: Bearer …` solo a rutas `/api/agent/v1`. No agregues Bearer globalmente a llamadas de la interfaz ni a la API nativa. Las mutaciones del facade de agentes también requieren `Origin` exactamente igual al origen local servido. `Host`/`Origin` reducen solicitudes cruzadas desde navegadores, pero un proceso local puede falsificarlos o llamar rutas nativas sin Bearer.

Las regresiones por encabezados Bearer malformados o duplicados y por publicación concurrente de credenciales están corregidas; una verificación independiente aprobó 8 pruebas enfocadas y Ruff. Esto no demuestra ACL de producción, durabilidad ante fallos ni aislamiento entre procesos. La API nativa sigue confiando en clientes locales y no requiere autenticación; el facade de agentes exige Bearer y, para mutaciones, el `Origin` local exacto, pero no aísla procesos locales.

## Preparar una sesión de `curl`

Pegá la credencial copiada en el prompt oculto; no la pongas en una URL, en un archivo, en el historial del shell ni en logs. Usá el mismo `BASE` para `Origin` y destino; si cambiaste host o puerto, actualizá ambos.

```bash
BASE=http://127.0.0.1:8765
read -rsp 'Credencial copiada desde Ajustes: ' AGENT_TOKEN; printf '\n'

curl -sS -H "Authorization: Bearer $AGENT_TOKEN" \
  "$BASE/api/agent/v1/profiles"
```

No uses `curl -v` con la credencial. Al terminar la sesión, ejecutá `unset AGENT_TOKEN`.

## Flujo típico: inspeccionar, validar, crear y consultar

El facade ofrece lecturas de catálogo, perfiles y revisiones, datasets y sorteos; alta/lectura de estrategias y revisiones; validación y alta idempotente de lotes; y detalle, comparación, reproducción, trayectoria y cancelación de experimentos. Todas esas rutas están bajo `/api/agent/v1` y requieren Bearer. Consultá primero `GET /profiles` y `GET /datasets`; abrí `GET /profiles/{profile_id}/revisions/{revision}`, `GET /datasets/{dataset_sha256}` y `GET /datasets/{dataset_sha256}/draws` para elegir un perfil registrado, un dataset compatible y un `start_draw` que coincida exactamente con un sorteo de ese dataset. Usá los identificadores y SHA-256 devueltos por el servidor, no los calcules ni los inventes.

Una estrategia nueva se registra como una definición versionada. Ejemplo mínimo de selección estática; el número es cero-indexado y la apuesta solo sirve si respeta el incremento, mínimo, máximo, moneda, cobertura y exposición del perfil elegido:

```json
{
  "definition": {
    "definition_version": 1,
    "name": "Ejemplo estático",
    "selector": "static-numbers/v1",
    "coverage": 1,
    "selector_parameters": {"numbers": [0]},
    "staking": "flat-per-number/v1",
    "staking_parameters": {"per_number_stake": 1},
    "closing_defaults": {}
  }
}
```

```sh
curl -sS -X POST "$BASE/api/agent/v1/strategies" \
  -H "Authorization: Bearer $AGENT_TOKEN" -H "Origin: $BASE" \
  -H 'Content-Type: application/json' --data-binary @strategy.json
```

`strategy.json` es un archivo local del cliente, no una ruta enviada al servidor. Conservá del resultado `id`, `revision` y `definition_sha256`; consultá la revisión exacta con `GET /strategies/{id}/revisions/{revision}`. La compatibilidad de ejecución con perfil/dataset se comprueba en la validación del lote.

El cuerpo de ejemplo para validar y luego crear un lote (guardalo localmente como `batch.json`) tiene este esquema. Reemplazá cada valor de identidad con el valor leído del servidor; las fechas, condiciones y montos son ejemplos, no valores válidos para todo perfil.

```json
{
  "schema_version": 1,
  "profile": {
    "id": "ID_DEL_PERFIL",
    "revision": 1,
    "sha256": "SHA256_DEL_PERFIL"
  },
  "dataset_sha256": "SHA256_DEL_DATASET",
  "strategies": [{
    "id": "ID_DE_ESTRATEGIA",
    "revision": 1,
    "definition_sha256": "SHA256_DE_LA_REVISION"
  }],
  "conditions": {
    "schema_version": 1,
    "start_draw": "FECHA HORA",
    "capital": 10000,
    "goal": 12000,
    "settlement": "best",
    "max_elapsed_draws": null,
    "max_bet_draws": null,
    "end_minute": null,
    "duration_minutes": null
  },
  "max_draws": 20,
  "client_request_id": "demo-lote-01"
}
```

`capital`, `goal` y `per_number_stake` son enteros en las unidades monetarias exactas del perfil: una unidad equivale a `10**(-scale)` de `currency`. Leé `currency`, `scale` y los límites del perfil; no asumas DOP ni uses decimales JSON. `settlement` es `best` o `all`. Las condiciones temporales opcionales pueden ser `null`. `profile` contiene la identidad registrada exacta (`id`, `revision`, `sha256`); debe coincidir con la instantánea del dataset. Cada estrategia referencia una revisión registrada exacta. `conditions.schema_version` debe ser `1`.

Validá antes de encolar. La validación no reserva capacidad ni cuota, y el estado puede cambiar antes de crear:

```sh
curl -sS -X POST "$BASE/api/agent/v1/profile-batches/validate" \
  -H "Authorization: Bearer $AGENT_TOKEN" -H "Origin: $BASE" \
  -H 'Content-Type: application/json' --data-binary @batch.json
```

Revisá `valid`, `dataset` (incluye la identidad de fuente), `requested_constraints`, `effective_constraints`, `limits` (incluye `reservation_created: false`) y `policy.revision` junto con los valores efectivos de política. Los límites efectivos pueden reducir lo solicitado; la política es del servidor, no una garantía calibrada ni un parámetro que este facade permita cambiar. `max_draws` admite 1–10.000 y la solicitud 1–3 estrategias, pero la política actual puede imponer límites menores; el cuerpo de lote está limitado a 64 KiB. El endpoint de validación no garantiza que la admisión posterior tenga cuota/cupo.

Para crear, enviá **el mismo cuerpo validado**:

```sh
curl -sS -X POST "$BASE/api/agent/v1/profile-batches" \
  -H "Authorization: Bearer $AGENT_TOKEN" -H "Origin: $BASE" \
  -H 'Content-Type: application/json' --data-binary @batch.json
```

Un `client_request_id` de 1–128 bytes UTF-8 identifica la solicitud: si se repite con el mismo contenido se devuelve el lote existente (201 al crear; 200 al recuperar el duplicado); si se reutiliza con contenido diferente, hay conflicto. No generes otro identificador para resolver un timeout. Primero consultá `GET /profile-batches/by-client-request/{client_request_id}`; si devuelve 404 y decidís reintentar, reenviá exactamente el cuerpo original con el mismo identificador. Nunca reintentes a ciegas una mutación incierta.

Guardá el `id` del experimento del resultado. Consultá `GET /experiments/{id}` para estado y detalle; la respuesta informa si cada ejecución terminó o quedó incompleta. Para comparar, usá `GET /experiments/{id}/compare`; para una página de apuestas, `GET /experiments/{id}/runs/{ordinal}/replay?offset=0&limit=50`; para trayectoria, `GET /experiments/{id}/runs/{ordinal}/trajectory`. Los parámetros `offset`/`limit` permiten paginar. Una ejecución incompleta no equivale a un resultado completo.

La cancelación solicita detener el trabajo; no demuestra que ya terminó. Después del `POST /experiments/{id}/cancel`, volvé a consultar `GET /experiments/{id}` hasta confirmar el estado final.

```sh
curl -sS -X POST "$BASE/api/agent/v1/experiments/$EXPERIMENT_ID/cancel" \
  -H "Authorization: Bearer $AGENT_TOKEN" -H "Origin: $BASE"
curl -sS -H "Authorization: Bearer $AGENT_TOKEN" \
  "$BASE/api/agent/v1/experiments/$EXPERIMENT_ID"
```

## Importar historial bruto

`POST /history/preview` y `POST /history/promote` reciben los **bytes originales del historial JSON** en el cuerpo —no JSON envuelto en Base64 ni una ruta del sistema de archivos del servidor—. Enviá `X-Profile-Id`, `X-Profile-Revision`, `X-Profile-Sha256`, `X-Confirm-Source` (igual a `metadata.origen`) y `X-Confirm-Timezone` (igual a `metadata.zona_horaria`). El preview valida perfil/formato y devuelve identidades SHA-256; para promover, repetí los bytes y encabezados y agregá `X-Expected-Dataset-Sha256` con el hash exacto obtenido en el preview. No confirmes una promoción tras cambiar los bytes. El historial admite hasta 32 MiB y 200.000 sorteos; los límites del perfil y su compatibilidad también aplican.

```bash
curl -sS -X POST "$BASE/api/agent/v1/history/preview" \
  -H "Authorization: Bearer $AGENT_TOKEN" -H "Origin: $BASE" \
  -H 'Content-Type: application/json' \
  -H "X-Profile-Id: $PROFILE_ID" -H "X-Profile-Revision: $PROFILE_REVISION" \
  -H "X-Profile-Sha256: $PROFILE_SHA256" \
  -H "X-Confirm-Source: $SOURCE" -H "X-Confirm-Timezone: $TIMEZONE" \
  --data-binary @history.json
```

Para promover usá la misma petición con `/history/promote` y agregá `-H "X-Expected-Dataset-Sha256: $DATASET_SHA256"`, usando el hash exacto del preview.

## Errores y límites prácticos

- `401`: el facade rechazó la autenticación; verificá que `Authorization` tenga exactamente un encabezado Bearer ASCII válido y una credencial correcta antes de reintentar.
- `403`: origen/host local no aceptado en una mutación; comprobá que `Origin` coincide exactamente con `BASE` y que abriste la interfaz desde ese origen.
- `404`: recurso o revisión no encontrado; copiá la identidad exacta del resultado del servidor.
- `409`: conflicto de identidad/idempotencia, límite operativo, cuota/cupo o estado incompatible; leé el detalle y consultá el recurso antes de actuar otra vez.
- `413`: cuerpo mayor que el límite del endpoint. `422`: JSON, perfil, estrategia, dataset o condiciones inválidas; corregí los campos señalados, no reintentes el mismo cuerpo sin cambios.

No se promete un `400` genérico para errores de autenticación: los status y detalles dependen del contrato concreto del endpoint; usá el status recibido y la guía anterior, sin asumir un estado pendiente general de endurecimiento. Para revisar un error, conservá status y cuerpo JSON, pero redactá siempre `Authorization`, tokens y datos privados.
