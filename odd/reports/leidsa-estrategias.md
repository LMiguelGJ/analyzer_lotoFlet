# Estrategias del laboratorio sobre Quiniela Leidsa: ¿hay alguna rentable?

Fecha del análisis: 2026-11-24. Historial: `datos/leidsa_quiniela_history.json`, 1381 sorteos (1/día, 20:50), 2023-01-04 → 2026-11-16, 3 números 00-99 por sorteo. Premios 60/8/4.

**Conclusión corta:** no se encontró una estrategia rentable de forma creíble. De 555 configuraciones válidas, solo **1** fue rentable en TRAIN *y* en TEST (`freq_recent`, cobertura 1, estilo audaz, 5000→6000), y ese resultado es compatible con suerte: con selección al azar, entre ~8 % y ~15 % de las veces aparece al menos un "superviviente" así al probar 4 sistemas. Ver §6.

## 1. Cómo paga una apuesta (motor del laboratorio)

- Cada sorteo da 3 números (posición 1, 2, 3). Se apuesta `s` pesos a cada uno de los `cobertura` números elegidos (los primeros del ranking del sistema; paridad = los 50 pares o los 50 impares según un voto causal).
- Costo del sorteo = `cobertura × s`. Cobro = `s × (60·[pos1 ∈ elegidos] + 8·[pos2 ∈ elegidos] + 4·[pos3 ∈ elegidos])`. O sea, los premios 60/8/4 son **multiplicadores por peso apostado a un número** según la posición donde sale.
- **Retorno esperado por peso, un número:** (60 + 8 + 4) / 100 = **0,72**. Es independiente de la cobertura y del estilo de apuesta (verificado con el historial: el promedio sobre los 100 números es 0,720; la uniformidad por posición pasa un χ² con 99 gl: 104,4 / 93,7 / 110,6). Perdida esperada: 28 centavos por peso.
- Estilos: `flat` = 1 por número siempre; `ladder` = escalera de 10 pasos que sube la apuesta tras fallar y vuelve a 1 al acertar la posición 1; `bold` = apuesta lo justo para llegar a la meta si cae el premio 60 (`min(ceil((meta−saldo)/(60−cob)), saldo//cob)`).
- Sesiones: cada sesión arranca con `capital` y termina al llegar a `meta` (saldo ≥ meta) o en ruina (saldo no alcanza la siguiente apuesta); la siguiente empieza en el sorteo siguiente con el capital completo. La última puede quedar `incompleta`.
- Totales: `total_wagered` = suma apostada, `total_paid` = suma cobrada, `total_net` = paid − wagered (equivale a Σ(saldo final − capital) de todas las sesiones, incluida la incompleta), retorno = paid / wagered. `wallet.out_of_pocket` = dinero propio que hay que reponer al reiniciar sesiones (política "retiene ganancias y repone"), `final_wealth` = patrimonio final.
- **Consecuencia importante:** como `total_net = paid − wagered`, ningún estilo cambia la esperanza por peso (0,72). Meta/ruina y escalera/audaz solo redistribuyen *cuánto* se apuesta y la varianza; un estilo audaz con pocas sesiones produce resultados muy aleatorios, no ventaja.
- Paridad solo admite cobertura 50 (el sistema rechaza otras con 422: `parity selection requires all 50 numbers`).
- Sin fuga de datos: el ranking del sorteo *t* usa solo sorteos *< t*; la ventana TEST usa el historial anterior pero no se entrena nada con ella.

## 2. Tamaño de la rejilla y tiempos

- Sistemas {parity, cold, freq_hist, freq_recent, decay} × cobertura {1,2,3,5,10,15,20,30,50} × estilo {flat, ladder, bold} × (capital, meta) {(500,750), (1000,1500), (2000,2800), (2000,4000), (5000,6000)} = **675 combinaciones**; 120 inválidas (paridad con cobertura ≠ 50 → 422), **555 válidas**.
- Cada una se corrió en 3 ventanas (completa, TRAIN, TEST): **2025 ejecuciones** reales por la API de laboratorios (FastAPI `TestClient`, base temporal aislada, nunca la base del usuario ni el servidor :8765). Una ejecución ≈ 0,1–0,2 s; rejilla total ≈ **346 s** (≈ 5,8 min). No hizo falta recortarla.
- TRAIN = 2023-01-04 00:00 → 2025-06-30 23:59 (887 sorteos). TEST = 2025-07-01 00:00 → 2026-11-16 23:59 (494 sorteos).
- Línea base aleatoria (§5): 300 semillas de ranking aleatorio × 135 configs × 3 ventanas (≈ 635 s) y 100 semillas con el historial barajado en el tiempo (≈ 228 s), usando el mismo motor de repetición.

## 3. Historial completo: mejores resultados

Solo **13 de 555** configuraciones tienen `total_net` > 0 en el historial completo, todas `freq_recent` con cobertura 1:

| Sistema | Cob. | Estilo | Capital/Meta | Neto | Retorno |
|---|---|---|---|---|---|
| freq_recent | 1 | bold | 5000/6000 | **+4 873** | **1,102** (47 699 apostado; 24 sesiones: 20 metas, 3 ruinas, 1 incompleta; out_of_pocket 8 982, patrimonio final 13 855) |
| freq_recent | 1 | bold | 2000/2800 | +2 060 | 1,061 |
| freq_recent | 1 | bold | 1000/1500 | +145 | 1,007 |
| freq_recent | 1 | flat/ladder (10 combinaciones idénticas) | cualquiera | +7 | 1,005 |

El orden por retorno es el mismo. Mejor fuera de ese grupo: `cold` 3 bold 2000/2800, −2 736 (retorno 0,973). Retorno agregado (todo lo apostado) por sistema en historial completo: parity 0,699 · cold 0,755 · freq_hist 0,717 · freq_recent 0,728 · decay 0,716; global 0,726 ≈ el 0,72 teórico. Es decir: los sistemas, en conjunto, no baten al azar.

## 4. Validación fuera de muestra (TRAIN → TEST)

Se escogieron los 10 mejores por `total_net` de TRAIN y los 10 mejores por retorno de TRAIN (colapsando configuraciones que generan exactamente la misma serie de apuestas, p. ej. flat/ladder con capitales distintos) y se corrieron en TEST. Unión de ambas listas (14 filas):

| Sistema | Cob. | Estilo | Cap/Meta | TRAIN ses | TRAIN apost. | TRAIN cobr. | TRAIN neto | TRAIN ret | TEST ses | TEST apost. | TEST cobr. | TEST neto | TEST ret |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **freq_recent** | **1** | **bold** | **5000/6000** | 15 | 31 326 | 32 668 | **+1 342** | 1,043 | 10 | 15 353 | 17 932 | **+2 579** | 1,168 |
| cold | 3 | bold | 2000/2800 | 49 | 65 061 | 66 076 | +1 015 | 1,016 | 30 | 35 949 | 32 240 | −3 709 | 0,897 |
| freq_recent | 1 | flat | 500/750 | 1 | 887 | 832 | −55 | 0,938 | 1 | 494 | 556 | +62 | 1,126 |
| freq_hist | 1 | flat | 500/750 | 1 | 887 | 768 | −119 | 0,866 | 1 | 494 | 256 | −238 | 0,518 |
| decay | 1 | flat | 500/750 | 1 | 887 | 688 | −199 | 0,776 | 1 | 494 | 564 | +70 | 1,142 |
| cold | 1 | flat | 500/750 | 1 | 887 | 684 | −203 | 0,771 | 1 | 494 | 532 | +38 | 1,077 |
| cold | 3 | flat | 500/750 | 3 | 2 661 | 2 436 | −225 | 0,915 | 1 | 1 482 | 1 356 | −126 | 0,915 |
| cold | 3 | flat | 1000/1500 | 1 | 2 661 | 2 436 | −225 | 0,915 | 1 | 1 482 | 1 356 | −126 | 0,915 |
| freq_recent | 2 | flat | 500/750 | 1 | 1 774 | 1 376 | −398 | 0,776 | 1 | 988 | 840 | −148 | 0,850 |
| freq_recent | 1 | bold | 500/750 | 20 | 6 665 | 6 260 | −405 | 0,939 | 12 | 3 591 | 4 184 | +593 | 1,165 |
| freq_recent | 1 | bold | 2000/2800 | 18 | 21 596 | 20 828 | −768 | 0,964 | 11 | 11 265 | 13 364 | +2 099 | 1,186 |
| decay | 1 | bold | 5000/6000 | 13 | 32 060 | 29 828 | −2 232 | 0,930 | 10 | 15 273 | 17 904 | +2 631 | 1,172 |
| cold | 3 | bold | 500/750 | 57 | 19 620 | 18 072 | −1 548 | 0,921 | 32 | 11 061 | 10 352 | −709 | 0,936 |
| cold | 3 | bold | 2000/4000 | 73 | 122 835 | 114 864 | −7 971 | 0,935 | 43 | 69 255 | 62 372 | −6 883 | 0,901 |

- Top 10 por neto TRAIN: 5 son rentables en TEST (5/10); top 10 por retorno TRAIN: 5/10. **Pero solo 2 de las 555 configuraciones fueron rentables en TRAIN** (la propia `freq_recent` 1 bold 5000/6000 y `cold` 3 bold 2000/2800). De esas 2, solo **1 sobrevive en TEST**. Las demás "rentables en TEST" ya perdían en TRAIN (no cuentan como rentables).
- **Tasa de suerte (TEST solo):** 60 de 555 configuraciones (**10,8 %**) son rentables en TEST (44 de 60 con cobertura 1; 15 con cobertura 2; 1 con cobertura 3; 0 con cobertura ≥ 5). Por sistema: cold 30/135, freq_recent 15/135, decay 15/135, freq_hist 0/135, parity 0/15. Esas 60 están muy correlacionadas (flat y ladder cobertura 1 son series idénticas y los sistemas eligen números parecidos), así que equivalen a muy pocas apuestas independientes. TEST son 494 sorteos y un solo número por sorteo tiene desviación típica del retorno ≈ 0,27: un 1,13 es ≈ +1,5σ.
- Rentable en TRAIN y TEST: **1/555**.

## 5. Línea base de azar

Mismo motor, 135 configs de ranking por semilla (9 coberturas × 3 estilos × 5 pares capital/meta):

| Línea base | % configs r
