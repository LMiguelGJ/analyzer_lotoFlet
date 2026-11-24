# Leidsa 2010–2026: los 4 sistemas nuevos

Fecha: 2026-11-24. Datos: `datos/leidsa_quiniela_history.json` (5.836 sorteos, 2010-07-19 → 2026-11-23).
Sistemas nuevos: Transición, Ciclo vencido, Terminaciones y decenas, Ensamble (junto a Fríos,
Frecuencia histórica, Frecuencia reciente, Decaimiento y Paridad).

## Cómo se probó

48 configuraciones: cada sistema × 6 combinaciones de cobertura, estilo de apuesta, capital y meta
(`--` = sin límite de días por sesión). Todo con premios 60/8/4 y el rango completo de fechas.

La prueba que decide es **fuera de muestra**: se elige con los sorteos de **2019-01-01 → 2022-12-31** y se
confirma, sin tocar la configuración, con **2023-01-01 → 2026-11-24**. 2010–2018 se informa aparte porque
sus sorteos no se comportan como azar (ver `investigacion-estrategias.md` §3).

## Mejor configuración por sistema: neto por año (RD$)

| Sistema | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | Total | %/año |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Transición | 1.057 | **231.861** | 6.205 | 3.070 | 7.200 | −16.944 | −17.965 | −18.960 | 15.084 | 4.123 | −17.947 | 4.362 | 7.191 | 5.117 | 2.053 | −17.412 | −17.063 | **+181.032** | +55,4 % |
| Frecuencia histórica | 1.344 | **131.655** | −11.806 | −3.214 | −7.690 | 2.683 | −8.486 | 1.732 | −10.772 | 4.880 | −8.812 | −4.657 | −11.796 | −1.494 | −3.350 | −1.704 | −8.987 | **+59.526** | +364,1 % |
| Decaimiento | −5.904 | **125.512** | −11.806 | −4.192 | −7.731 | 6.052 | −2.575 | −6.629 | −13.770 | −10.691 | −7.750 | −11.789 | −2.566 | −4.575 | −7.689 | −3.396 | −2.824 | **+27.677** | +169,3 % |
| Frecuencia reciente | 1.344 | **131.650** | −14.829 | −6.571 | −9.584 | −4.498 | 1.480 | −7.589 | −8.496 | −11.756 | −11.843 | −10.863 | −1.578 | −9.703 | −8.513 | −3.576 | −8.712 | **+16.363** | +100,1 % |
| Terminaciones y decenas | 0 | 4.008 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | −4.324 | **−316** | −0,4 % |
| Ensamble | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | −5.216 | **−5.216** | −6,4 % |
| Ciclo vencido | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | −4.998 | 0 | 0 | 0 | −238 | **−5.236** | −6,4 % |

Los ceros significan que ese año ninguna sesión cerró: con un solo número y meta lejana, una sesión puede
durar años.

## Las 12 mejores por neto total

| Sistema | Cobertura | Apuesta | Capital → meta | Neto | %/año |
|---|---|---|---|---|---|
| Transición | 1 | Audaz | 20.000 → 21.000 | +181.032 | +55,4 % |
| Transición | 3 | Audaz | 1.000 → 2.000 | +154.800 | +946,8 % |
| Frecuencia histórica | 3 | Audaz | 1.000 → 2.000 | +59.526 | +364,1 % |
| Decaimiento | 3 | Audaz | 1.000 → 2.000 | +27.677 | +169,3 % |
| Frecuencia reciente | 3 | Audaz | 1.000 → 2.000 | +16.363 | +100,1 % |
| Transición | 3 | Plana | 5.000 → 5.100 | +9.580 | +11,7 % |
| Frecuencia histórica | 2 | Audaz | 5.000 → 5.050 | +4.996 | +6,1 % |
| Frecuencia histórica | 3 | Plana | 5.000 → 5.100 | +3.996 | +4,9 % |
| Frecuencia reciente | 3 | Plana | 5.000 → 5.100 | +2.588 | +3,2 % |
| Decaimiento | 3 | Plana | 5.000 → 5.100 | +2.488 | +3,0 % |
| Terminaciones y decenas | 3 | Plana | 5.000 → 5.100 | −316 | −0,4 % |
| Terminaciones y decenas | 1 | Audaz | 20.000 → 21.000 | −649 | −0,2 % |

## Prueba fuera de muestra

| | Resultado |
|---|---|
| Configuraciones probadas | 48 |
| Ganan en 2019–2022 **y** en 2023–2026 | **0** |
| Superan 10 % anual en ambos tramos | **0** |

Las ocho mejores por el peor de los dos tramos:

| Sistema | Config | 2019–2022 | 2023–2026 |
|---|---|---|---|
| Frecuencia histórica | 3 · Plana · 5000→5100 | −907 (−4,5 %) | −702 (−3,6 %) |
| Frecuencia reciente | 1 · Audaz · 20000→21000 | −4.613 (−5,8 %) | **+18.685 (+24,0 %)** |
| Ensamble | 3 · Plana · 5000→5100 | −1.139 (−5,7 %) | −1.146 (−5,9 %) |
| Terminaciones y decenas | 3 · Plana · 5000→5100 | −887 (−4,4 %) | −1.234 (−6,3 %) |
| Decaimiento | 3 · Plana · 5000→5100 | −1.275 (−6,4 %) | −850 (−4,4 %) |
| Transición | 3 · Plana · 5000→5100 | −1.187 (−5,9 %) | −1.310 (−6,7 %) |
| Frecuencia reciente | 3 · Plana · 5000→5100 | −1.491 (−7,5 %) | −1.162 (−6,0 %) |
| Fríos | 3 · Plana · 5000→5100 | −1.495 (−7,5 %) | −114 (−0,6 %) |

## Conclusión

- **Ninguna de las 48 configuraciones, con ninguno de los 9 sistemas, gana en los dos tramos recientes.**
  Tampoco supera el 10 % anual de un certificado de inversión.
- **Transición es el único sistema nuevo que muestra algo**, y su resultado total (+181.032) sale casi
  entero de **2011** (+231.861), uno de los años cuyos datos no se pueden verificar y no se comportan como
  azar. En 2023–2026 alterna años buenos y malos (+5.117, +2.053, −17.412, −17.063) y en el tramo
  2019–2022 pierde.
- **Ciclo vencido, Terminaciones y decenas y Ensamble no aportan nada**: pierden en casi todos los años y
  cierran pocas sesiones.
- La razón sigue siendo la misma: cada peso apostado devuelve 0,72 en promedio. Ningún patrón de los
  sorteos recientes cambia esa cuenta.

**Recomendación:** usar los sistemas nuevos para explorar y comparar en la app, no como base para apostar
dinero real esperando una rentabilidad superior a un certificado.
