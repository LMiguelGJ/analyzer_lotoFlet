# Apuesta máxima por número

Permitir fijar en un laboratorio un tope de apuesta por número, como el que imponen las bancas, para que
las simulaciones respeten reglas reales.

## Specs

- S1 — Decisión del usuario ("si hazlo") a la propuesta: agregar a los laboratorios una opción de "apuesta máxima por número" (por ejemplo 500 o 1.000 pesos) y repetir la búsqueda con ese límite.
- S2 — Regla: si un estilo pide apostar más que el tope por número, se apuesta el tope (y nunca más que `saldo // cobertura`). El estado de las progresiones baja a lo realmente apostado, igual que hoy con el saldo.
- S3 — Sin el campo, todo resultado guardado, todo laboratorio de Loteka y todo dorado queda idéntico.

## Tasks

- T1 — S1–S3: backend + frontend del campo `max_stake_per_number`. Commit: PENDING_HASH.
- T2 — S1: búsqueda 2023–2026 con tope 500 y 1.000 y laboratorios de las mejores en la app. Commit: n/a.

## Log

- L1 — Propuesta: "Agregar a los laboratorios una opción de 'apuesta máxima por número' (por ejemplo, 500 o 1.000 pesos) y repetir la búsqueda con ese límite. ¿Lo agrego?" Respuesta: "si hazlo dime como vamos ahora".
