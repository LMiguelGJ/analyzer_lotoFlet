# Historiales de quiniela v2

La biblioteca v2 conserva cada historial como fuente inmutable vinculada a la identidad completa (SHA-256) de un perfil v2. Importar o confirmar una fuente **no** la activa, no fusiona datos del historial v1, no cambia corridas existentes y no genera rankings.

## JSON canónico de importación

El archivo UTF-8 debe ser un objeto exacto con `schema_version`, `timezone` y `draws`. `schema_version` es el entero `2`; `timezone` es un nombre IANA; `draws` es una lista no vacía de hasta 400.000 filas. Cada fila tiene exactamente `schema_version: 2`, `draw_id`, `timestamp` y `results`:

```json
{
  "schema_version": 2,
  "timezone": "America/Santo_Domingo",
  "draws": [
    {
      "schema_version": 2,
      "draw_id": "2026-06-10-1",
      "timestamp": "2026-06-10T12:00:00-04:00",
      "results": [7, 3, 91, 12, 0]
    }
  ]
}
```

`results` conserva el orden publicado. Cada valor debe pertenecer al universo del perfil; cantidad de posiciones y repetición deben cumplir sus reglas. No se convierten strings, floats ni booleanos a enteros. Se rechazan claves desconocidas/duplicadas, JSON no finito, zonas inválidas, archivos mayores de 64 MiB y perfiles incompatibles.

Los timestamps aceptan segundos ISO-8601 con `Z` o desplazamiento explícito, o una hora local sin zona. Una hora local requiere confirmación explícita del cliente sobre `timezone`; una zona declarada dentro del archivo no sustituye ese consentimiento. Horas locales inexistentes o ambiguas por cambios DST se rechazan: enviar un timestamp con desplazamiento explícito. Se normaliza cada instante a UTC (`YYYY-MM-DDTHH:MM:SSZ`) y se ordenan cronológicamente las filas sin reordenar `results`.

El adaptador del historial incluido conserva el hash de los bytes originales. En sus filas anidadas, `source_url` es opcional y solo se acepta como metadato de texto; se ignora para el replay, no se descarga ni se interpreta como procedencia verificada. No se aceptan otras claves anidadas.

Filas idénticas con el mismo ID, instante y resultados se cuentan como duplicados y se deduplican. Un mismo ID con datos distintos, o un mismo instante con resultados distintos, rechaza el archivo completo. IDs distintos con resultados iguales en el mismo instante se conservan. Nunca se recortan filas para cumplir el presupuesto.

## Preview, confirmación y lectura

- `POST /api/v2/history-sources/preview`: `{profile_id, name, raw_json, timezone?, timezone_confirmed?}`. `raw_json` contiene el texto UTF-8 exacto del archivo. La respuesta devuelve los hashes raw/canónico/preview, perfil, zona, confirmación, rango, conteos, límites y una muestra de hasta tres filas; no escribe datos.
- `POST /api/v2/history-sources`: mismo cuerpo más `expected_preview_sha256`. El servidor vuelve a validar los bytes y el perfil antes de guardar. El hash esperado debe coincidir con el preview recién calculado. Confirmar exactamente la misma identidad es idempotente.
- `GET /api/v2/history-sources?offset=0&limit=20`: página de metadatos y muestras, límite 1–100 y offset seguro para JavaScript.
- `GET /api/v2/history-sources/{uuid}`: metadatos y muestra acotada; no descarga el arreglo completo.
- `POST /api/v2/history-sources/included/preview` y `/included/confirm`: admiten solo el archivo incluido configurado por el servidor. No aceptan rutas ni bytes arbitrarios del cliente; su hash debe ser el SHA-256 congelado.

Un `SourceReference` expone ID UUID, hash canónico, hash completo del perfil, origen (`included`/`imported`), hash exacto de entrada y `rankings_sha256: null`. La confirmación y cualquier rechazo no alteran la fuente activa, historial, selección ni resultados v1. Los lectores verifican hashes, longitudes, perfil y metadata; corrupción se reporta, nunca se repara automáticamente. La cuota se evalúa y reserva dentro de la transacción de escritura.

## Ejemplo

`docs/examples/quiniela-history-v2.json` es un archivo sintético pequeño; sus fechas, identificadores y resultados no representan observaciones reales.
