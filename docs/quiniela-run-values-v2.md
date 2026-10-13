# Valores de traza de quiniela configurable (v2)

`laboratorio.domain.configurable_runs` define valores de dominio inmutables y codecs de mapping para `QuinielaDraw`, `QuinielaBet` y `RunWindow`. Son contratos estructurales: **no** prueban compatibilidad con un perfil, validez de estrategia ni corrección de replay/liquidación. No calculan ni inventan premios.

Todos los mappings exigen `schema_version: 2`, exactamente las claves documentadas y tipos estrictos. Las listas de entrada de `results` y `numbers` se copian a tuplas; `to_mapping()` devuelve listas y diccionarios nuevos. No se convierten strings, floats ni booleanos en enteros.

## Límites y reglas

- Timestamps: UTC canónico `YYYY-MM-DDTHH:MM:SSZ`, con fecha/hora válida; no se convierten zonas ni offsets.
- Identificadores de sorteo: texto no vacío, se recorta en los extremos y queda limitado a 120 bytes UTF-8.
- Resultados: entre 1 y 16 enteros no negativos hasta `2**53 - 1`; se permiten resultados repetidos estructuralmente.
- Ventana: inicio y fin en formato canónico; `start <= end`.
- Apuesta: ordinales no negativos hasta `2**53 - 1`; de 1 a 1.000 números distintos y de 1 a 16 resultados. Los resultados sí pueden repetirse.
- `per_number` es positivo; `wagered == len(numbers) * per_number`. El agregado apostado, `paid`, saldos y `balance_after` quedan dentro de `MAX_MONEY` de `domain.contracts`. El saldo inicial financia la apuesta y `balance_after == balance_before - wagered + paid`.
- `rules_used` contiene únicamente `profile_sha256`, `strategy_sha256` (hex SHA-256 minúsculo de 64 caracteres) y `engine_version` (texto no vacío, sin espacios externos, de hasta 80 bytes UTF-8).

Un mapping de sorteo:

```json
{
  "schema_version": 2,
  "draw_id": "draw-001",
  "timestamp": "2025-03-04T05:06:07Z",
  "results": [7, 7, 12]
}
```

El codec rechaza esquemas/versiones no admitidos, claves ausentes o extra, fechas no canónicas/inválidas, números fuera de límites y aritmética inconsistente. La validación no consulta perfiles ni interpreta las reglas identificadas por sus hashes.
