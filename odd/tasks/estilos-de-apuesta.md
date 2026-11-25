# Estilos de apuesta nuevos y retorno por peso

Agregar cinco estilos de apuesta a los laboratorios (además de Plana, Escalera y Audaz) y mostrar en cada
resultado cuánto devolvió cada peso apostado frente a la ventaja de la casa.

## Specs

- S1 — Pedido literal: "Apuesta solo tenemos estos tres tipos podemos investigar en internet o aprender de otros proyectos de github". Decisión del usuario: "5 estilos de apuesta nuevos" — Martingala, Paroli, D'Alembert, Fibonacci y Oscar's Grind.
- S2 — Decisión del usuario: "Retorno por peso en cada resultado" — mostrar cuánto devolvió cada peso apostado y la ventaja de la casa (Leidsa 60/8/4: 28 %).
- S3 — Plana, Escalera, Audaz y todos los resultados guardados y dorados de Loteka quedan idénticos.

### Reglas de los estilos (por número jugado; la apuesta del sorteo es `b × cobertura`)

"Ganar un sorteo" = lo cobrado en ese sorteo supera lo apostado en ese sorteo. Toda apuesta se recorta a
`saldo // cobertura`; si queda en 0 la sesión es quiebra; la meta y el máximo de días funcionan igual que hoy.

| id | Etiqueta | Regla de `b` (empieza en 1) |
|---|---|---|
| `martingale` | Martingala | Pierde → `b × 2`. Gana → `1`. |
| `paroli` | Paroli | Gana → `b × 2`; tras 3 ganadas seguidas → `1`. Pierde → `1`. |
| `dalembert` | D'Alembert | Pierde → `b + 1`. Gana → `max(1, b − 1)`. |
| `fibonacci` | Fibonacci | Índice `i` en 1,1,2,3,5,8…; pierde → `i + 1`; gana → `max(0, i − 2)`; `b = fib(i)`. |
| `oscars_grind` | Oscar's Grind | Ciclo con objetivo `+cobertura`. Pierde → mismo `b`. Gana → si la ganancia del ciclo llegó al objetivo, nuevo ciclo con `b = 1`; si no, `b = min(b + 1, max(1, ceil((objetivo − ganancia_ciclo) / (premio_1 − cobertura))))`. |

## Tasks

- T1 — S1, S3: backend — validación de `stake_style`, reglas en el motor de laboratorios, tests (RED primero) con secuencias calculadas a mano; dorados de Loteka sin cambios. Commit: 17eb230.
- T2 — S1, S2: frontend — los 5 estilos en el formulario con ayuda en español simple; retorno por peso y ventaja de la casa en el resultado; build. Commit: 17eb230.
- T3 — S1: correr los 8 estilos en la búsqueda 5000 → 5500 de Leidsa (2019–2026) y crear los mejores en la app. Commit: n/a.

## Log

- L1 — "Apuesta solo tenemos estos tres tipos podemos investigar en internet o aprender de otros proyectos de github usa mi cli vamos investiga dime si se puede aprender algo de https://stake.com/". Investigación en `odd/reports/investigacion-estrategias.md` §6.
- L2 — El usuario eligió: "5 estilos de apuesta nuevos" y "Retorno por peso en cada resultado".
