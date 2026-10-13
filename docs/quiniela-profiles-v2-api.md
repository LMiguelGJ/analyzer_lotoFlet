# Immutable quiniela profiles — v2 API

This additive API stores validated game rules; it does **not** execute a strategy.
The existing `/api/v1` application and results retain their original contracts.
Do not open an existing user database from developer tools to test this feature.
On the owner's next ordinary startup, migration18 adds an empty profile table.
Fresh installations still receive the fourteen original laboratories; upgrading17
never recreates laboratories that the owner deleted.

## Resources

- `POST /api/v2/game-profiles`: body contains exactly `name` and `rules`.
  Creates a fresh UUID4 profile, returns201 with `{profile,sha256,created_at}`.
- `GET /api/v2/game-profiles?offset=0&limit=20`: returns
  `{items,total,offset,limit}`; limit1..100, offset0..9007199254740991.
  Items are the complete record above, newest first (creation time, then UUID).
- `GET /api/v2/game-profiles/{id}`: the same immutable record, or404:
  `El perfil de quiniela no existe.` Invalid/noncanonical IDs return422.

Names are trimmed, at most120 UTF-8 bytes, and unique by Unicode case-folding.
Profiles cannot be modified through these resources. Changes require a new
identity/name; no profile write changes the legacy active game or history.
`sha256` covers UTF-8, sorted-key compact JSON of the complete profile, excluding
`created_at`; readers revalidate rules, identity, digest, canonical text and length.
See [rule fields](quiniela-profiles-v2.md) for the mandatory v2 schema.

Example small game (amounts are integer units, not floating-point currency):

```json
{
  "name": "Quiniela 4/2",
  "rules": {
    "schema_version": 2,
    "universe": [0, 1, 2, 3],
    "display_width": 1,
    "positions": 2,
    "played_positions": [0, 1],
    "order_matters": true,
    "allows_repeats": false,
    "multipliers": [
      {"numerator": 1, "denominator": 1},
      {"numerator": 1, "denominator": 1}
    ],
    "payout_mode": "all",
    "currency": "DOP",
    "scale": 0,
    "minimum_stake": 10,
    "stake_increment": 10,
    "maximum_stake": 100,
    "max_coverage": 4,
    "max_exposure": 400
  }
}
```

## Admission and errors

All mutations require the existing local Host and same-origin Origin headers.
Cross-site requests remain forbidden. Profile POSTs are limited to64 KiB of
actual bytes, including streamed bodies, and Content-Length is checked without
parsing unbounded integers. Oversized requests return413:
`La solicitud supera el límite de 64 KiB.` Duplicate object keys return422:
`La solicitud contiene claves JSON duplicadas.` Malformed/nonfinite JSON returns422:
`La solicitud JSON no es válida.` Domain errors return422 with
`El perfil no es válido: ...`; request-envelope errors use FastAPI field details.

Creation checks effective quota **inside** the SQLite writer transaction.
Duplicate names and quota refusal return409:
`No se pudo crear el perfil por un conflicto o límite de cuota.`
Failed admission adds no profile or logical quota bytes. Stored corruption returns409:
`Un perfil guardado está dañado y no se puede mostrar.` It is not silently repaired.
Existing `/api/v1/settings` profile/admission counters include each v2 profile
JSON's actual UTF-8 bytes once; stored byte-count claims cannot lower the budget.
No data, source file, launcher, installer or packaging is replaced by this API.
