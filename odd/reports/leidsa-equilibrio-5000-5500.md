# Leidsa 5.000 → 5.500: equilibrio entre días y meta con los 8 estilos de apuesta

Fecha: 2026-11-24. Datos confiables 2019-01-01 → 2026-11-23. Cada configuración se corrió por año calendario
(cada año arranca con 5.000). Se elige con 2019–2022 y se confirma con 2023–2026.

## Tamaño de la búsqueda

| Búsqueda | Configuraciones | Corridas |
|---|---|---|
| Plana, Escalera, Audaz × 9 sistemas × cobertura {1,2,3,4,5,7,10} × máx días {—,7,10,14,21,30,45,60,90} | 1.539 | 12.312 |
| Martingala, Paroli, D'Alembert, Fibonacci, Oscar's Grind × 9 sistemas × cobertura {1,2,3,5,10} × máx días {—,14,30,60} | 820 | 6.560 |
| **Total** | **2.359** | **18.872** |

## Resultado

- Positivas en total 2019–2026: **16 de 2.359**, todas con Martingala, Fibonacci o D'Alembert.
- Positivas en 2019–2022 **y** en 2023–2026: **0**.

## Mejor por estilo (total 2019–2026, suma de años)

| Estilo | Configuración | Metas | Quiebras | Años > 0 | Total | Peor año |
|---|---|---|---|---|---|---|
| Martingala | Decaimiento 1 · máx 14 | 35 | 151 | 5/8 | +215.247 | −100.994 |
| Fibonacci | Transición 1 | 32 | 92 | 5/8 | +62.963 | −61.128 |
| D'Alembert | Frec. histórica 1 | 31 | 7 | 4/8 | +3.980 | −6.703 |
| Oscar's Grind | Frec. reciente 1 | 0 | 0 | 3/8 | +99 | −269 |
| Paroli | Frec. reciente 1 · máx 30 | 0 | 0 | 3/8 | −164 | −154 |
| Plana / Escalera | Fríos 1 | 0 | 0 | 2/8 | −371 | −222 |
| Audaz | Transición 1 | 29 | 3 | 5/8 | −2.804 | −4.722 |

## Fuera de muestra (elegidas en 2019–2022)

| Configuración | 2019–2022 | 2023–2026 |
|---|---|---|
| Martingala · Decaimiento 1 · máx 14 | +325.268 | **−110.021** |
| Martingala · Ensamble 2 · máx 30 | +93.384 | **−77.754** |
| Fibonacci · Transición 1 | +69.860 | **−6.897** |
| D'Alembert · Frec. histórica 1 | +5.393 | **−1.413** |

## Por qué Martingala y Fibonacci muestran ganancias enormes

Suben la apuesta tras cada fallo hasta usar casi todo el saldo. Cuando el número sale después de una racha
larga, cobra 60 veces una apuesta grande (por ejemplo 60 × 2.048) y supera la meta por mucho. A cambio, cada
quiebra cuesta 5.000 y hay **151 quiebras en 8 años** (≈ 755.000 repuestos de bolsillo). El retorno por peso
mayor a 1 sale de **cuándo** cayeron los aciertos, no de una ventaja: en el tramo de confirmación pierden.

## Laboratorios creados en la app (ventana completa, no por año)

| Laboratorio | Neto | Metas | Quiebras | Apostado | Retorno por peso |
|---|---|---|---|---|---|
| 2019–2026 · D'Alembert · Frec. hist. 1 | +6.653 | 32 | 8 | 109.355 | 1,061 |
| 2026 · D'Alembert · Frec. hist. 1 | +1.256 | 3 | 0 | 14.824 | 1,085 |
| 2019–2026 · Fibonacci · Transición 1 | +12.848 | 29 | 97 | 560.348 | 1,023 |
| 2026 · Fibonacci · Transición 1 | −16.331 | 3 | 12 | 69.523 | 0,765 |
| 2019–2026 · Martingala · Decaimiento 1 · máx 14 | +188.490 | 34 | 154 | 884.022 | 1,213 |
| 2026 · Martingala · Decaimiento 1 · máx 14 | +28.274 | 4 | 15 | 91.890 | 1,308 |

## Conclusión

El mejor equilibrio entre llegar a la meta y no quebrar es **D'Alembert · Frecuencia histórica · 1 número**:
~4 metas por año, 7–8 quiebras en 8 años, pérdidas anuales acotadas (peor año −6.703). Aun así pierde en el
tramo de confirmación. Ningún estilo cambia que la quiniela devuelve 0,72 por peso en promedio.
