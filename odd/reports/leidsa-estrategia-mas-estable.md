# Búsqueda de la config más estable (Leidsa Quiniela, premios 60/8/4)

Petición: «busca la mas estable a lo largo de los años con mejor patrimonio al final».

## Método
- Grilla: 8 sistemas × cobertura {1,2,3,5} × 8 estilos × capital {5000, 20000} × meta {+1%, +2%, +5%, +10%} × plazo {sin tope, 30 sorteos} = 4096, más `parity` (cobertura 50) × 8 estilos × 2 capitales × 4 metas × 2 plazos = 128. Total 4224 configs; las 4224 devolvieron 201 (0 rechazadas).
- Cada config se corrió en 3 ventanas continuas independientes: FULL 2019-01-01→2026-12-31 (2752 sorteos), H1 2019-01-01→2022-12-31 y H2 2023-01-01→2026-12-31.
- Monedero de la app: ratio = patrimonio final / bolsillo. Neto por año = suma de (saldo final − capital) de las sesiones que cierran ese año (la sesión abierta final cuenta en su año), con el índice de sesión mapeado a fecha con `datos/leidsa_quiniela_history.json` (2752 sorteos en la ventana, coincide con el run).
- «Días/meta» = promedio de días calendario (inclusive) entre el primer y el último sorteo de las sesiones que cierran en meta.
- Importes en pesos. Estable = ratio > 1 en FULL, H1 y H2; orden: años positivos (de 8) desc., luego ratio FULL.
- Datos crudos: `results_0..7.jsonl` (una línea por config), scripts `run_estable.py`, `analyze.py`, `pre2019.py`.

## 1. Conteos
- Configs totales: 4224; rechazadas (no 201): 0; válidas: 4224
- ratio > 1 en FULL: 134
- ratio > 1 en H1: 174; en H2: 357; en H1 y H2: 31
- ratio > 1 en FULL, H1 y H2 (estables): 31
- Distribución de años positivos entre estables: 8/8: 8, 6/8: 1, 5/8: 5, 4/8: 9, 3/8: 3, 2/8: 2, 1/8: 3

## 2. Top 15 estables (años+ desc, luego ratio FULL)
| # | Config | Años+ | Neto por año 2019…2026 | Peor año | Ruinas | Bolsillo | Patrimonio | Ratio FULL | H1 | H2 | Días/meta |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | freq_recent c1 bold cap5000 meta5100 dl- | 8/8 | +379 / +394 / +461 / +656 / +425 / +480 / +1080 / +373 | +373 | 0 | 5000 | 9248 | 1.85 | 1.38 | 1.47 | 83.3 |
| 2 | freq_recent c1 bold cap20000 meta20400 dl- | 8/8 | +1263 / +1279 / +1710 / +2118 / +1315 / +1676 / +3474 / +1364 | +1263 | 0 | 20000 | 34199 | 1.71 | 1.32 | 1.39 | 83.3 |
| 3 | cold c1 bold cap5000 meta5050 dl- | 8/8 | +251 / +427 / +174 / +271 / +419 / +324 / +215 / +669 | +174 | 0 | 5000 | 7750 | 1.55 | 1.22 | 1.32 | 87.1 |
| 4 | freq_recent c1 bold cap5000 meta5050 dl- | 8/8 | +288 / +215 / +328 / +428 / +211 / +324 / +583 / +232 | +211 | 0 | 5000 | 7609 | 1.52 | 1.25 | 1.28 | 83.3 |
| 5 | transition c1 bold cap20000 meta20200 dl- | 8/8 | +887 / +433 / +1000 / +1589 / +1171 / +478 / +2865 / +607 | +433 | 0 | 20000 | 29030 | 1.45 | 1.19 | 1.26 | 98.4 |
| 6 | cold c1 bold cap20000 meta20200 dl- | 8/8 | +670 / +1418 / +465 / +697 / +1259 / +949 / +686 / +1646 | +465 | 0 | 20000 | 27790 | 1.39 | 1.16 | 1.23 | 87.1 |
| 7 | freq_recent c1 bold cap20000 meta20200 dl- | 8/8 | +661 / +660 / +896 / +1170 / +687 / +876 / +1827 / +785 | +660 | 0 | 20000 | 27562 | 1.38 | 1.17 | 1.21 | 83.3 |
| 8 | freq_hist c1 bold cap20000 meta20200 dl- | 8/8 | +1359 / +919 / +1326 / +838 / +1642 / +458 / +438 / +343 | +343 | 0 | 20000 | 27323 | 1.37 | 1.21 | 1.14 | 79.6 |
| 9 | cold c1 fibonacci cap20000 meta22000 dl30 | 6/8 | +2914 / +280407 / -259789 / +273484 / +99861 / +67020 / -205437 / +429446 | -259789 | 66 | 140000 | 827906 | 5.91 | 2.98 | 31.60 | 18.5 |
| 10 | freq_hist c1 fibonacci cap20000 meta21000 dl30 | 5/8 | +97551 / -141648 / +446080 / +4205 / -115701 / -207199 / +210930 / +533175 | -207199 | 69 | 149296 | 976689 | 6.54 | 3.72 | 3.63 | 18.6 |
| 11 | cold c1 fibonacci cap20000 meta21000 dl30 | 5/8 | -142901 / +282371 / -230639 / +266162 / +99861 / +249965 / -205437 / +429446 | -230639 | 62 | 182892 | 931720 | 5.09 | 1.85 | 40.75 | 17.0 |
| 12 | freq_hist c1 fibonacci cap20000 meta21000 dl- | 5/8 | -141042 / -141693 / +582694 / +6741 / -117018 / +172988 / +210928 / +592152 | -141693 | 81 | 402735 | 1568485 | 3.89 | 1.76 | 10.16 | 18.9 |
| 13 | freq_hist c1 fibonacci cap20000 meta22000 dl- | 5/8 | -141042 / -183317 / +582694 / +4789 / -196117 / +149410 / +210928 / +592152 | -196117 | 83 | 444359 | 1463856 | 3.29 | 1.59 | 8.41 | 21.0 |
| 14 | digits c2 oscars_grind cap5000 meta5050 dl- | 5/8 | +122 / +0 / +82 / +172 / +52 / +0 / +74 / -58 | -58 | 0 | 5000 | 5444 | 1.09 | 1.06 | 1.01 | 314.0 |
| 15 | freq_recent c1 martingale cap20000 meta20200 dl- | 4/8 | +373073 / -106362 / -92926 / -97050 / +119671 / +200260 / +452749 / -192779 | -192779 | 138 | 238143 | 894779 | 3.76 | 1.32 | 3.42 | 12.6 |

## 3. Top 10 por ratio FULL (sin exigir estabilidad)
| # | Config | Años+ | Neto por año 2019…2026 | Peor año | Ruinas | Bolsillo | Patrimonio | Ratio FULL | H1 | H2 | Días/meta |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | overdue c1 fibonacci cap20000 meta20200 dl- | 3/8 | +620913 / -113796 / -238143 / +243125 / -236757 / -104772 / -85871 / +281664 | -238143 | 75 | 63257 | 429620 | 6.79 | 13.74 | 0.74 | 14.0 |
| 2 | freq_hist c1 fibonacci cap20000 meta21000 dl30 | 5/8 | +97551 / -141648 / +446080 / +4205 / -115701 / -207199 / +210930 / +533175 | -207199 | 69 | 149296 | 976689 | 6.54 | 3.72 | 3.63 | 18.6 |
| 3 | freq_hist c3 fibonacci cap5000 meta5050 dl- | 5/8 | +25292 / -28132 / +22184 / -17245 / +15355 / +62710 / +48019 / -8069 | -28132 | 86 | 21738 | 141852 | 6.53 | 0.88 | 8.62 | 10.2 |
| 4 | freq_hist c2 fibonacci cap20000 meta22000 dl- | 4/8 | +106940 / +93864 / +8924 / +90828 / -31108 / -14626 / -125396 / -19324 | -125396 | 78 | 20000 | 130102 | 6.51 | 16.02 | 0.23 | 19.9 |
| 5 | cold c1 fibonacci cap20000 meta22000 dl30 | 6/8 | +2914 / +280407 / -259789 / +273484 / +99861 / +67020 / -205437 / +429446 | -259789 | 66 | 140000 | 827906 | 5.91 | 2.98 | 31.60 | 18.5 |
| 6 | ensemble c2 martingale cap5000 meta5250 dl30 | 4/8 | +33322 / +71724 / +86300 / -78022 / -16332 / +62632 / -2254 / -67190 | -78022 | 136 | 20000 | 110180 | 5.51 | 6.66 | 0.65 | 10.8 |
| 7 | ensemble c2 martingale cap5000 meta5050 dl30 | 4/8 | +33788 / +71724 / +86300 / -77892 / -19456 / +62690 / -2010 / -67996 | -77892 | 136 | 19884 | 107032 | 5.38 | 6.73 | 0.62 | 8.5 |
| 8 | ensemble c2 martingale cap5000 meta5100 dl30 | 4/8 | +33788 / +71724 / +86300 / -77892 / -19522 / +62632 / -2010 / -67958 | -77892 | 136 | 19884 | 106946 | 5.38 | 6.73 | 0.62 | 9.1 |
| 9 | freq_hist c3 fibonacci cap5000 meta5050 dl30 | 5/8 | +21999 / -28132 / +18238 / -17245 / +15355 / +62710 / +38664 / -7544 | -28132 | 84 | 25031 | 129076 | 5.16 | 0.60 | 3.83 | 9.6 |
| 10 | cold c1 fibonacci cap20000 meta21000 dl30 | 5/8 | -142901 / +282371 / -230639 / +266162 / +99861 / +249965 / -205437 / +429446 | -230639 | 62 | 182892 | 931720 | 5.09 | 1.85 | 40.75 | 17.0 |

## 4. Mejor config con 0 ruinas en FULL y ratio > 1
Hay 56 configs con 0 ruinas y ratio>1. Top 5:
| # | Config | Años+ | Neto por año 2019…2026 | Peor año | Ruinas | Bolsillo | Patrimonio | Ratio FULL | H1 | H2 | Días/meta |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | freq_recent c1 bold cap5000 meta5100 dl- | 8/8 | +379 / +394 / +461 / +656 / +425 / +480 / +1080 / +373 | +373 | 0 | 5000 | 9248 | 1.85 | 1.38 | 1.47 | 83.3 |
| 2 | freq_recent c1 bold cap20000 meta20400 dl- | 8/8 | +1263 / +1279 / +1710 / +2118 / +1315 / +1676 / +3474 / +1364 | +1263 | 0 | 20000 | 34199 | 1.71 | 1.32 | 1.39 | 83.3 |
| 3 | cold c1 bold cap5000 meta5050 dl- | 8/8 | +251 / +427 / +174 / +271 / +419 / +324 / +215 / +669 | +174 | 0 | 5000 | 7750 | 1.55 | 1.22 | 1.32 | 87.1 |
| 4 | freq_recent c1 bold cap5000 meta5050 dl- | 8/8 | +288 / +215 / +328 / +428 / +211 / +324 / +583 / +232 | +211 | 0 | 5000 | 7609 | 1.52 | 1.25 | 1.28 | 83.3 |
| 5 | transition c1 bold cap20000 meta20200 dl- | 8/8 | +887 / +433 / +1000 / +1589 / +1171 / +478 / +2865 / +607 | +433 | 0 | 20000 | 29030 | 1.45 | 1.19 | 1.26 | 98.4 |

De ellas, estables (H1 y H2 > 1): 16

## 5. Top 3 estables en 2010-07-19 → 2018-12-31 (datos dudosos; 2011 tiene artefacto de ciclo repetido; solo informativo)
| # | Config | Ratio 2010-07-19→2018-12-31 | Ruinas | Metas | Bolsillo | Patrimonio | Ratio FULL 2019+ |
|---|---|---|---|---|---|---|---|
| 1 | freq_recent c1 bold cap5000 meta5100 dl- | 0.20 | 4 | 28 | 21367 | 4356 | 1.85 |
| 2 | freq_recent c1 bold cap20000 meta20400 dl- | 0.20 | 4 | 28 | 87707 | 17806 | 1.71 |
| 3 | cold c1 bold cap5000 meta5050 dl- | 0.32 | 3 | 24 | 19371 | 6283 | 1.55 |

## Lectura
- Solo 31 de 4224 configs (0,7 %) ganan en FULL, H1 y H2 a la vez; las 31 son exactamente las que ganan en H1 y H2 (todas las que ganan en ambas mitades también ganan en FULL).
- Las únicas 8 con 8/8 años positivos y 0 ruinas son todas de **cobertura 1, estilo `bold`, sin plazo** (freq_recent, cold, transition, freq_hist). La mejor por patrimonio es **freq_recent c1 bold, capital 5000, meta 5100**: patrimonio 9248 con bolsillo 5000 (ratio 1.85; H1 1.38, H2 1.47), peor año +373. La mejor en pesos absolutos con el mismo perfil es freq_recent c1 bold capital 20000 meta 20400: patrimonio 34199 (ratio 1.71).
- Las configs con ratios 4–7 (fibonacci/martingale c1–c3) tienen 60–140 ruinas, años de ±200 000 y ratios que oscilan entre mitades (p. ej. 16.02 en H1 vs 0.23 en H2): son varianza, no estabilidad.
- Contraste fuera de muestra: las 3 mejores estables, aplicadas a 2010-2018, pierden (ratio 0.20–0.32 con 3–4 ruinas), lo que sugiere que la «estabilidad» 2019-2026 puede ser en buena parte suerte de racha/ajuste a esos años. Los datos previos a 2019 son dudosos, así que se reporta sin concluir.
- Sesgo de selección: son 4224 configs probadas sobre los mismos datos; que alguna salga 8/8 con ratio 1.85 es esperable por azar. No se demuestra ventaja real: un sorteo aleatorio con estos premios no la tiene, y la caída en 2010-2018 apunta a lo mismo.
