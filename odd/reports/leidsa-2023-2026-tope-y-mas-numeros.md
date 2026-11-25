# Búsquedas Leidsa (quiniela) – resumen

Rejilla completa con los 8 sistemas (cold, freq_recent, freq_hist, decay, transition, overdue, digits, ensemble). Cada config se simula una vez por año natural 2023–2026 desde el capital; retorno = total_net / capital del año. Premios [60,8,4]. Meta = capital + round(capital·pct). Búsqueda A: 3840 configs; B: 3840 configs (0 rechazadas en ambas; 15 360 corridas por búsqueda). Datos crudos: `results_A_*.jsonl`, `results_B_*.jsonl`.

Notas de lectura:
- El retorno suma el neto de todas las sesiones del año (cada ruina/timeout reinicia desde el capital), por eso puede superar ±100%; "Ruinas" y "Metas" son totales de los 4 años.
- Las filas de A con 0 ruinas son degeneradas: oscars_grind con cobertura 4 y msd=30 casi nunca alcanza la meta (0 metas), solo pierde unas décimas por sesión; no son resultados útiles. El resultado idéntico para distintos pct es porque la meta nunca se alcanza.
- Los ganadores "todos los años > +15%" son configs fibonacci con 17–41 ruinas en 4 años: ganancias enormes en pocas sesiones y muchas pérdidas totales; alta varianza, no un perfil de bajo riesgo.
- "Fuera de muestra": las medias de 2025/2026 de las configs seleccionadas por 2023-2024 son fuertemente negativas (ver líneas); casi toda la selección se desvanece.

### Búsqueda A

- Configs ejecutadas: 3840 (rechazadas: 0; total evaluadas: 3840)
- Con los 4 años > 0: 3
- Con los 4 años > +15%: 2
- Con media > +15%: 96

**Top 10 por peor año**

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| overdue c5 fibonacci cap20000 +10% msd=30 | +144.7% | +301.5% | +110.9% | +772.9% | +110.9% | +332.5% | 18 | 35 |
| overdue c5 fibonacci cap20000 +5% msd=30 | +103.9% | +46.5% | +234.0% | +745.3% | +46.5% | +282.4% | 17 | 37 |
| overdue c7 fibonacci cap20000 +10% msd=- | +145.6% | +3.0% | +533.5% | +88.2% | +3.0% | +192.6% | 18 | 45 |
| decay c4 oscars_grind cap20000 +2% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +1% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +10% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +5% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| cold c4 oscars_grind cap20000 +2% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| cold c4 oscars_grind cap20000 +1% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| cold c4 oscars_grind cap20000 +10% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |

**Top 10 con 0 ruinas en los 4 años** (hay 1015 configs con 0 ruinas)

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| decay c4 oscars_grind cap20000 +2% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +1% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +10% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| decay c4 oscars_grind cap20000 +5% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 |
| cold c4 oscars_grind cap20000 +2% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| cold c4 oscars_grind cap20000 +1% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| cold c4 oscars_grind cap20000 +10% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| cold c4 oscars_grind cap20000 +5% msd=30 | -1.9% | +0.5% | -0.8% | -0.5% | -1.9% | -0.7% | 0 | 0 |
| overdue c4 oscars_grind cap20000 +5% msd=30 | -1.2% | +0.1% | -2.1% | -1.0% | -2.1% | -1.1% | 0 | 0 |
| overdue c4 oscars_grind cap20000 +2% msd=30 | -1.2% | +0.1% | -2.1% | -1.0% | -2.1% | -1.1% | 0 | 0 |

**Fuera de muestra**: configs con 2023 y 2024 > +15%: 74. De ellas, con 2025 y 2026 > +15%: 2; con 2025 y 2026 > 0: 2.
(Media 2025: -263.7%, media 2026: -324.5%)

**Mejor por cobertura (por peor año)**

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| decay c4 oscars_grind cap20000 +2% msd=30 | -0.9% | -1.6% | -1.8% | -1.7% | -1.8% | -1.5% | 0 | 0 | <- cob 4: 0 con 4 años>0 de 640
| overdue c5 fibonacci cap20000 +10% msd=30 | +144.7% | +301.5% | +110.9% | +772.9% | +110.9% | +332.5% | 18 | 35 | <- cob 5: 2 con 4 años>0 de 640
| overdue c7 fibonacci cap20000 +10% msd=- | +145.6% | +3.0% | +533.5% | +88.2% | +3.0% | +192.6% | 18 | 45 | <- cob 7: 1 con 4 años>0 de 640
| decay c10 oscars_grind cap20000 +2% msd=30 | -5.8% | -4.2% | -2.6% | -7.8% | -7.8% | -5.1% | 0 | 0 | <- cob 10: 0 con 4 años>0 de 640
| decay c15 oscars_grind cap20000 +5% msd=30 | -8.8% | -8.6% | -5.9% | -9.4% | -9.4% | -8.2% | 0 | 0 | <- cob 15: 0 con 4 años>0 de 640
| transition c20 oscars_grind cap20000 +1% msd=30 | -17.8% | -6.1% | -12.9% | -15.5% | -17.8% | -13.1% | 0 | 2 | <- cob 20: 0 con 4 años>0 de 640

**Candidata para 2019–2022** (todos los años > +15%): overdue c5 fibonacci cap20000 +10% msd=30

---

### Búsqueda B

- Configs ejecutadas: 3840 (rechazadas: 0; total evaluadas: 3840)
- Con los 4 años > 0: 47
- Con los 4 años > +15%: 14
- Con media > +15%: 201

**Top 10 por peor año**

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| freq_recent c1 fibonacci cap5000 +2% msd=30 cap_num=1000 | +629.4% | +459.7% | +346.3% | +1258.1% | +346.3% | +673.4% | 41 | 28 |
| freq_recent c1 fibonacci cap5000 +2% msd=- cap_num=1000 | +629.4% | +459.7% | +249.3% | +864.3% | +249.3% | +550.7% | 43 | 28 |
| freq_hist c3 fibonacci cap5000 +1% msd=- cap_num=1000 | +232.1% | +868.2% | +620.3% | +327.7% | +232.1% | +512.0% | 40 | 44 |
| freq_recent c1 fibonacci cap5000 +1% msd=30 cap_num=1000 | +629.4% | +461.6% | +346.3% | +184.7% | +184.7% | +405.5% | 42 | 31 |
| freq_recent c1 fibonacci cap5000 +1% msd=- cap_num=1000 | +629.4% | +461.6% | +249.3% | +184.7% | +184.7% | +381.3% | 43 | 31 |
| freq_hist c3 fibonacci cap20000 +2% msd=- cap_num=1000 | +813.0% | +278.3% | +196.8% | +63.8% | +63.8% | +338.0% | 25 | 36 |
| freq_hist c3 fibonacci cap20000 +1% msd=- cap_num=1000 | +775.3% | +279.4% | +193.5% | +63.8% | +63.8% | +328.0% | 25 | 39 |
| cold c3 fibonacci cap20000 +1% msd=30 cap_num=1000 | +119.9% | +118.8% | +60.0% | +95.7% | +60.0% | +98.6% | 15 | 46 |
| freq_hist c3 fibonacci cap20000 +1% msd=30 cap_num=1000 | +930.2% | +323.7% | +59.8% | +90.5% | +59.8% | +351.1% | 16 | 38 |
| overdue c5 fibonacci cap20000 +5% msd=- cap_num=1000 | +105.6% | +52.9% | +451.1% | +399.7% | +52.9% | +252.3% | 25 | 35 |

**Top 10 con 0 ruinas en los 4 años** (hay 1730 configs con 0 ruinas)

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| decay c2 bold cap20000 +2% msd=- cap_num=500 | +19.2% | +13.4% | +18.9% | +14.1% | +13.4% | +16.4% | 0 | 31 |
| decay c2 bold cap20000 +2% msd=- cap_num=1000 | +19.2% | +13.4% | +18.9% | +14.1% | +13.4% | +16.4% | 0 | 31 |
| freq_hist c2 bold cap5000 +1% msd=- cap_num=500 | +13.4% | +10.0% | +8.9% | +10.3% | +8.9% | +10.7% | 0 | 34 |
| freq_hist c2 bold cap5000 +1% msd=- cap_num=1000 | +13.4% | +10.0% | +8.9% | +10.3% | +8.9% | +10.7% | 0 | 34 |
| decay c2 bold cap5000 +1% msd=- cap_num=500 | +13.5% | +8.9% | +13.0% | +9.4% | +8.9% | +11.2% | 0 | 31 |
| decay c2 bold cap5000 +1% msd=- cap_num=1000 | +13.5% | +8.9% | +13.0% | +9.4% | +8.9% | +11.2% | 0 | 31 |
| cold c2 bold cap20000 +1% msd=- cap_num=500 | +11.6% | +8.6% | +8.4% | +11.9% | +8.4% | +10.1% | 0 | 35 |
| cold c2 bold cap20000 +1% msd=- cap_num=1000 | +11.6% | +8.6% | +8.4% | +11.9% | +8.4% | +10.1% | 0 | 35 |
| freq_hist c2 bold cap20000 +1% msd=- cap_num=500 | +12.0% | +8.6% | +7.3% | +7.7% | +7.3% | +8.9% | 0 | 34 |
| freq_hist c2 bold cap20000 +1% msd=- cap_num=1000 | +12.0% | +8.6% | +7.3% | +7.7% | +7.3% | +8.9% | 0 | 34 |

**Fuera de muestra**: configs con 2023 y 2024 > +15%: 211. De ellas, con 2025 y 2026 > +15%: 14; con 2025 y 2026 > 0: 15.
(Media 2025: -182.5%, media 2026: -292.5%)

**Tope por número 500 vs 1000**

| Tope | Configs | 4 años>0 | 4 años>15% | media>15% | mejor peor-año | peor-año mediano | media de medias | ruinas medias |
|---|---|---|---|---|---|---|---|---|
| 500 | 1920 | 20 | 2 | 89 | +49.4% | -122.0% | -132.0% | 13.29 |
| 1000 | 1920 | 27 | 12 | 112 | +346.3% | -122.0% | -153.3% | 17.53 |

**Mejor por cobertura y tope (por peor año)**

| Config | 2023 | 2024 | 2025 | 2026 | Peor | Media | Ruinas | Metas |
|---|---|---|---|---|---|---|---|---|
| cold c1 bold cap5000 +2% msd=- cap_num=500 | +11.0% | +10.1% | +6.9% | +20.2% | +6.9% | +12.1% | 0 | 19 | <- cob 1, tope 500
| decay c2 bold cap20000 +2% msd=- cap_num=500 | +19.2% | +13.4% | +18.9% | +14.1% | +13.4% | +16.4% | 0 | 31 | <- cob 2, tope 500
| overdue c3 fibonacci cap5000 +2% msd=30 cap_num=500 | +110.3% | +521.3% | +16.5% | +55.3% | +16.5% | +175.8% | 33 | 39 | <- cob 3, tope 500
| overdue c5 fibonacci cap20000 +5% msd=- cap_num=500 | +107.8% | +61.5% | +49.4% | +76.9% | +49.4% | +73.9% | 17 | 39 | <- cob 5, tope 500
| freq_recent c1 fibonacci cap5000 +2% msd=30 cap_num=1000 | +629.4% | +459.7% | +346.3% | +1258.1% | +346.3% | +673.4% | 41 | 28 | <- cob 1, tope 1000
| decay c2 bold cap20000 +2% msd=- cap_num=1000 | +19.2% | +13.4% | +18.9% | +14.1% | +13.4% | +16.4% | 0 | 31 | <- cob 2, tope 1000
| freq_hist c3 fibonacci cap5000 +1% msd=- cap_num=1000 | +232.1% | +868.2% | +620.3% | +327.7% | +232.1% | +512.0% | 40 | 44 | <- cob 3, tope 1000
| overdue c5 fibonacci cap20000 +5% msd=- cap_num=1000 | +105.6% | +52.9% | +451.1% | +399.7% | +52.9% | +252.3% | 25 | 35 | <- cob 5, tope 1000

**Candidata para 2019–2022** (todos los años > +15%): freq_recent c1 fibonacci cap5000 +2% msd=30 cap_num=1000

---

### Candidata global y años 2019–2022

Candidata global: la de mayor peor-año con los 4 años > +15% entre A y B = freq_recent c1 fibonacci cap5000 +2% msd=30 tope/nº=1000 (peor año 2023–2026: +346.3%). Se añaden la mejor de A y la mejor con 0 ruinas de B para contraste.

| Config | 2019 | 2020 | 2021 | 2022 | Ruinas | Metas |
|---|---|---|---|---|---|---|
| freq_recent c1 fibonacci cap5000 +2% msd=30 tope/nº=1000 (mejor global, búsqueda B) | +661.5% | -128.8% | -1347.7% | -854.4% | 46 | 16 |
| overdue c5 fibonacci cap20000 +10% msd=30 (mejor de la búsqueda A) | -981.5% | -216.0% | -647.9% | -209.5% | 26 | 20 |
| decay c2 bold cap20000 +2% sin msd, tope/nº=500 (extra: mejor con 0 ruinas, B) | -87.3% | -93.9% | -103.4% | +23.4% | 3 | 26 |

Conclusión: ninguna de las candidatas sostiene el resultado en 2019–2022 (la mejor global gana solo en 2019 y pierde con claridad en 2020–2022; la mejor de A pierde los 4 años; la config de 0 ruinas, que era la más estable en 2023–2026, pierde ~90–100% en 2019–2021 con una ruina por año y solo gana en 2022). Las ventajas de 2023–2026 no parecen robustas.
