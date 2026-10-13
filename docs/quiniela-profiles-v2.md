# Contrato de perfiles de quiniela v2

Este documento describe el contrato de datos inerte de `QuinielaRules` y
`QuinielaProfile`. Validar o guardar un perfil no habilita por sí solo una
corrida configurable; la ejecución requiere sus propios contratos y límites.
El contrato histórico v1 y sus resultados no se convierten ni reinterpretan.

## Perfil

Un perfil v2 tiene exactamente estos campos:

- `schema_version`: entero estricto `2`.
- `id`: UUID canónico en minúsculas. `create_profile` genera un UUID4 nuevo.
- `name`: texto no vacío, recortado y de hasta 120 bytes UTF-8. La fábrica
  recorta espacios exteriores; el decodificador exige la forma ya canónica.
- `rules`: el objeto de reglas v2 descrito abajo.

Los decodificadores rechazan campos desconocidos, campos faltantes, versiones
no soportadas y tipos coercibles (por ejemplo, booleanos como enteros). Los
arrays JSON se admiten únicamente en `universe`, `played_positions` y
`multipliers`; se copian y no se modifica el objeto de entrada. Los modelos son
inmutables. `to_mapping()` produce mappings JSON compatibles y el ciclo de ida
y vuelta conserva exactamente los valores admitidos.

## Reglas

Cada objeto `rules` contiene exactamente:

| Campo | Contrato |
|---|---|
| `schema_version` | Entero estricto `2`. |
| `universe` | Array de 2 a 1.000 enteros distintos, no negativos y seguros para JavaScript, ordenados ascendentemente. |
| `display_width` | Entero de 1 a 16; debe permitir representar el mayor valor del universo. |
| `positions` | Cantidad de posiciones de resultado: entero de 1 a 16. |
| `played_positions` | Array no vacío de índices de posición, distintos y ascendentes, entre `0` y `positions - 1`. Son índices base cero: la primera posición es `0`. |
| `order_matters` | Booleano estricto. Si es falso, todos los pagos de las posiciones jugadas deben ser iguales como racionales exactos. |
| `allows_repeats` | Booleano estricto; describe si un sorteo puede repetir valores. Sin repeticiones, `positions` no puede superar el tamaño del universo. |
| `multipliers` | Un objeto `{numerator, denominator}` por posición de resultado, usando `PayoutMultiplier` existente: numerador no negativo y denominador positivo, ambos acotados por `MAX_MONEY`. |
| `payout_mode` | `all` suma los pagos de todas las posiciones jugadas que coincidan; `best` paga el máximo racional entre las coincidencias de cada número. |
| `currency` | Código de tres letras ASCII mayúsculas, por ejemplo `DOP`. |
| `scale` | Entero de 0 a 6. Cada importe monetario es un entero expresado en unidades de `10 ** (-scale)` de la moneda. No se usan floats. |
| `minimum_stake`, `stake_increment`, `maximum_stake` | Enteros positivos en unidades de escala, acotados por `MAX_MONEY`. Los extremos deben ser múltiplos del incremento y mínimo no puede exceder máximo. |
| `max_coverage` | Entero positivo, no mayor que el universo. |
| `max_exposure` | Exposición máxima por sorteo, en unidades de escala; entero positivo no mayor que `MAX_MONEY`. |

Cada pago aplicado al incremento mínimo debe ser un entero exacto de la unidad de
escala. No se redondea una fracción. La exposición debe cubrir al menos una
apuesta mínima por número de la cobertura declarada. El máximo de apuesta no
puede superar la exposición. El límite conservador de pagos supone que cada
unidad de exposición puede coincidir en todas las posiciones jugadas en modo
`all`, o en la posición de mayor pago en modo `best`; se rechazan contratos cuyo
pago resultante pueda superar `MAX_MONEY`. Estos son límites de admisión de
contrato, no presupuestos de ejecución ni garantías de rendimiento.

## Semántica de pago y diferencia histórica

`best` significa el **máximo pago por cada número acertado** entre las posiciones
jugadas coincidentes. No significa la primera coincidencia. El contrato de
quiniela congelado v1 conserva su semántica histórica `first-match/v0`: paga la
primera posición coincidente, aunque otra posición coincidente pagaría más.
Esa diferencia se mantiene explícita para no cambiar resultados históricos al
introducir perfiles configurables. La validación de v2 no actualiza ni recalcula
registros v1.

## Ejemplo mínimo

```json
{
  "schema_version": 2,
  "universe": [0, 1, 2, 3, 4],
  "display_width": 1,
  "positions": 2,
  "played_positions": [0, 1],
  "order_matters": true,
  "allows_repeats": false,
  "multipliers": [
    {"numerator": 5, "denominator": 2},
    {"numerator": 3, "denominator": 1}
  ],
  "payout_mode": "best",
  "currency": "DOP",
  "scale": 2,
  "minimum_stake": 2,
  "stake_increment": 2,
  "maximum_stake": 100,
  "max_coverage": 3,
  "max_exposure": 300
}
```

El importe `2` representa `0,02 DOP` a escala `2`; un multiplicador `5/2`
produce exactamente `5` unidades de escala para una apuesta de `2`. Una
fracción no representable por el incremento se rechaza en vez de redondearse.
