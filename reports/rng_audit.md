# Auditoría del generador de Chance Express

- Fuente: `chance_express_history.json` (SHA-256 `d1c0e9ec047dfa6a…`, solo lectura)
- Sorteos: 105,426 · Días: 566 · Bits NIST (6 bits, valores 00-63): 2,024,286
- Criterio: α = 0.01; pruebas específicas con corrección de Holm; NIST con la regla de proporción de SP 800-22 (y uniformidad de p cuando m ≥ 55).

## 1. Veredicto por dataset

| Dataset | Pruebas específicas que fallan | NIST 6 bits que fallan | NIST paridad que fallan |
|---|---:|---:|---:|
| **Loteka** | 0/52  | 0/15  | 0/15  |
| **sano (SHA-256)** | 0/52  | 0/15  | 0/15  |
| **LCG bits bajos** | 19/52 B3a, B3b, B3c, B4.12, B4.13, B4.14, B4.15, B4.23… | 7/15 longest_run, dft, non_overlapping_template, overlapping_template, universal, serial, approximate_entropy | 11/15 runs, longest_run, binary_matrix_rank, dft, non_overlapping_template, overlapping_template, linear_complexity, serial, approximate_entropy, random_excursions, random_excursions_variant |
| **sesgo módulo 8 bits** | 26/52 B1a, B1b, B2.1, B2.2, B2.3, B2.4, B2.5, B2.g… | 7/15 frequency, runs, longest_run, non_overlapping_template, overlapping_template, approximate_entropy, cumulative_sums | 1/15 linear_complexity |
| **semilla por hora** | 50/52 B1a, B1b, B2.1, B2.2, B2.3, B2.4, B2.5, B2.g… | 10/15 frequency, runs, longest_run, dft, non_overlapping_template, overlapping_template, universal, serial, approximate_entropy, cumulative_sums | 11/15 frequency, block_frequency, runs, longest_run, dft, non_overlapping_template, overlapping_template, linear_complexity, serial, approximate_entropy, cumulative_sums |

## 2. Pruebas específicas 00-99 (todas las columnas)

| ID | Prueba | Loteka | sano (SHA-256) | LCG bits bajos | sesgo módulo 8 bits | semilla por hora |
|---|---|---|---|---|---|---|
| B1a | Sesgo de módulo, fuente de 8 bits (00-55) | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ 2.60e-07 |
| B1b | Sesgo de módulo, fuente de 16 bits (00-35) | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ 8.84e-54 |
| B2.1 | Uniformidad globo 1 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B2.2 | Uniformidad globo 2 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B2.3 | Uniformidad globo 3 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B2.4 | Uniformidad globo 4 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B2.5 | Uniformidad globo 5 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B2.g | Uniformidad global | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B3a | Sorteo N → N+1, globo 1 (100×100) | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ⚠️ 0.1681 | ❌ <1e-300 |
| B3b | Sorteo N → N+1, 5 globos juntos | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B3c | Paridad N → N+1, globo 1 (tu Markov orden 1) | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ 1.75e-294 |
| B4.12 | Globo 1 vs globo 2 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 0.3124 | ❌ <1e-300 |
| B4.13 | Globo 1 vs globo 3 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.14 | Globo 1 vs globo 4 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.15 | Globo 1 vs globo 5 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.23 | Globo 2 vs globo 3 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.24 | Globo 2 vs globo 4 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.25 | Globo 2 vs globo 5 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.34 | Globo 3 vs globo 4 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.35 | Globo 3 vs globo 5 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B4.45 | Globo 4 vs globo 5 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B5.1d | Decenas globo 1 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B5.1u | Unidades globo 1 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 1.67e-05 | ❌ <1e-300 |
| B5.1i | Decena vs unidad globo 1 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 3.88e-56 | ❌ <1e-300 |
| B5.2d | Decenas globo 2 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ 1.99e-189 |
| B5.2u | Unidades globo 2 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 1.95e-04 | ❌ <1e-300 |
| B5.2i | Decena vs unidad globo 2 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 2.40e-64 | ❌ <1e-300 |
| B5.3d | Decenas globo 3 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B5.3u | Unidades globo 3 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 7.76e-11 | ❌ <1e-300 |
| B5.3i | Decena vs unidad globo 3 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 2.10e-45 | ❌ <1e-300 |
| B5.4d | Decenas globo 4 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B5.4u | Unidades globo 4 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 0.0017 | ❌ <1e-300 |
| B5.4i | Decena vs unidad globo 4 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 7.09e-37 | ❌ <1e-300 |
| B5.5d | Decenas globo 5 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 |
| B5.5u | Unidades globo 5 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ⚠️ 0.0409 | ❌ <1e-300 |
| B5.5i | Decena vs unidad globo 5 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ 1.44e-48 | ❌ <1e-300 |
| B6 | Tiempo de retorno de cada número (gaps) | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ 6.90e-67 | ❌ <1e-300 |
| B7.1 | Memoria a 1-185 sorteos, globo 1 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B7.2 | Memoria a 1-185 sorteos, globo 2 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B7.3 | Memoria a 1-185 sorteos, globo 3 | ✅ 1.0000 | ✅ 0.6518 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B7.4 | Memoria a 1-185 sorteos, globo 4 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B7.5 | Memoria a 1-185 sorteos, globo 5 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B7.p | Memoria de la paridad a 1-185 sorteos, globo 1 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ✅ 1.0000 | ❌ <1e-300 |
| B8a | Misma hora, días consecutivos (coincidencias) | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ 1.06e-04 | ❌ <1e-300 |
| B8b | ¿Cada horario tiene números propios? (horario × número) | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B9a | Sorteos completos repetidos (5 números iguales) | ✅ 1.0000 | ✅ 1.0000 | ❌ 1.33e-295 | ✅ 0.4363 | ❌ <1e-300 |
| B9b | Secuencia repetida más larga (globo 1) | ✅ 1.0000 | ✅ 1.0000 | ⚠️ 0.1829 | ✅ 1.0000 | ❌ <1e-300 |
| B10a | Fórmula lineal entre sorteos (x' = a·x + c mod 100) | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 | ❌ <1e-300 |
| B10b | Fórmula lineal entre globos del mismo sorteo | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 | ❌ <1e-300 | ❌ <1e-300 |
| B11a | Hora del día × número | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ❌ <1e-300 |
| B11b | Día de la semana × número | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 |
| B11c | Mes × número | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 | ✅ 1.0000 |

Cada celda: veredicto y p corregido por Holm.

## 3. NIST SP 800-22

### Flujo de 6 bits (20 × 100.000 bits; Maurer y excursiones: 2 × 1.000.000)

| Prueba NIST | Loteka | sano (SHA-256) | LCG bits bajos | sesgo módulo 8 bits | semilla por hora |
|---|---|---|---|---|---|
| frequency | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ❌ 0/20 | ❌ 0/20 |
| block_frequency | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 |
| runs | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ❌ 0/20 | ❌ 0/20 |
| longest_run | ✅ 20/20 | ✅ 20/20 | ❌ 0/20 | ❌ 0/20 | ❌ 0/20 |
| binary_matrix_rank | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ✅ 20/20 | ✅ 19/20 |
| dft | ✅ 19/20 | ✅ 20/20 | ❌ 8/20 | ✅ 19/20 | ❌ 0/20 |
| non_overlapping_template | ✅ 2919/2960 | ✅ 2924/2960 | ❌ 2028/2960 | ❌ 2842/2960 | ❌ 1869/2960 |
| overlapping_template | ✅ 20/20 | ✅ 20/20 | ❌ 5/20 | ❌ 9/20 | ❌ 0/20 |
| universal | ✅ 2/2 | ✅ 2/2 | ❌ 0/2 | ✅ 2/2 | ❌ 0/2 |
| linear_complexity | ✅ 19/20 | ✅ 19/20 | ✅ 19/20 | ✅ 20/20 | ✅ 20/20 |
| serial | ✅ 40/40 | ✅ 40/40 | ❌ 0/40 | ✅ 38/40 | ❌ 0/40 |
| approximate_entropy | ✅ 20/20 | ✅ 20/20 | ❌ 0/20 | ❌ 8/20 | ❌ 0/20 |
| cumulative_sums | ✅ 40/40 | ✅ 40/40 | ✅ 40/40 | ❌ 0/40 | ❌ 0/40 |
| random_excursions | ✅ 16/16 | ✅ 8/8 | — | — | — |
| random_excursions_variant | ✅ 36/36 | ✅ 18/18 | — | — | — |

Cada celda: veredicto y p-values ≥ 0,01 sobre el total. — = no aplicable al largo de la secuencia.

### Paridad de cada globo (5 × 100.000 bits)

| Prueba NIST | Loteka | sano (SHA-256) | LCG bits bajos | sesgo módulo 8 bits | semilla por hora |
|---|---|---|---|---|---|
| frequency | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 |
| block_frequency | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ✅ 5/5 | ❌ 3/5 |
| runs | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ❌ 0/5 |
| longest_run | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ❌ 0/5 |
| binary_matrix_rank | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ✅ 5/5 |
| dft | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ❌ 0/5 |
| non_overlapping_template | ✅ 731/740 | ✅ 733/740 | ❌ 0/740 | ✅ 732/740 | ❌ 0/740 |
| overlapping_template | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ❌ 0/5 |
| universal | — | — | — | — | — |
| linear_complexity | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ❌ 4/5 | ❌ 0/5 |
| serial | ✅ 10/10 | ✅ 10/10 | ❌ 0/10 | ✅ 10/10 | ❌ 0/10 |
| approximate_entropy | ✅ 5/5 | ✅ 5/5 | ❌ 0/5 | ✅ 5/5 | ❌ 0/5 |
| cumulative_sums | ✅ 10/10 | ✅ 10/10 | ✅ 10/10 | ✅ 10/10 | ❌ 0/10 |
| random_excursions | ✅ 8/8 | ✅ 8/8 | ❌ 0/40 | ✅ 15/16 | — |
| random_excursions_variant | ✅ 18/18 | ✅ 18/18 | ❌ 5/90 | ✅ 36/36 | — |

Cada celda: veredicto y p-values ≥ 0,01 sobre el total. — = no aplicable al largo de la secuencia.

## 4. Detalle de Loteka

| ID | Prueba | p | p Holm | Veredicto | Detalle |
|---|---|---:|---:|---|---|
| B1a | Sesgo de módulo, fuente de 8 bits (00-55) | 0.8045 | 1.0000 | ✅ PASA | observado 0.56017, justo 0.56000, con sesgo sería 0.65625 (z=+0.25) |
| B1b | Sesgo de módulo, fuente de 16 bits (00-35) | 0.4746 | 1.0000 | ✅ PASA | observado 0.36047, justo 0.36000, con sesgo sería 0.36035 (z=+0.72) |
| B2.1 | Uniformidad globo 1 | 0.4307 | 1.0000 | ✅ PASA | chi²=100.8 (gl=99) |
| B2.2 | Uniformidad globo 2 | 0.2692 | 1.0000 | ✅ PASA | chi²=107.2 (gl=99) |
| B2.3 | Uniformidad globo 3 | 0.2877 | 1.0000 | ✅ PASA | chi²=106.4 (gl=99) |
| B2.4 | Uniformidad globo 4 | 0.3010 | 1.0000 | ✅ PASA | chi²=105.8 (gl=99) |
| B2.5 | Uniformidad globo 5 | 0.5191 | 1.0000 | ✅ PASA | chi²=97.7 (gl=99) |
| B2.g | Uniformidad global | 0.1870 | 1.0000 | ✅ PASA | chi²=111.3 (gl=99) |
| B3a | Sorteo N → N+1, globo 1 (100×100) | 0.0450 | 1.0000 | ✅ PASA | chi²=10040 (gl=9801), 104860 pares |
| B3b | Sorteo N → N+1, 5 globos juntos | 0.3700 | 1.0000 | ✅ PASA | chi²=9847 (gl=9801), 524300 pares |
| B3c | Paridad N → N+1, globo 1 (tu Markov orden 1) | 0.1596 | 1.0000 | ✅ PASA | chi²=1.98 (gl=1) |
| B4.12 | Globo 1 vs globo 2 | 0.4819 | 1.0000 | ✅ PASA | chi²=9807 (gl=9801) |
| B4.13 | Globo 1 vs globo 3 | 0.7230 | 1.0000 | ✅ PASA | chi²=9718 (gl=9801) |
| B4.14 | Globo 1 vs globo 4 | 0.2574 | 1.0000 | ✅ PASA | chi²=9892 (gl=9801) |
| B4.15 | Globo 1 vs globo 5 | 0.7530 | 1.0000 | ✅ PASA | chi²=9705 (gl=9801) |
| B4.23 | Globo 2 vs globo 3 | 0.1153 | 1.0000 | ✅ PASA | chi²=9969 (gl=9801) |
| B4.24 | Globo 2 vs globo 4 | 0.2704 | 1.0000 | ✅ PASA | chi²=9886 (gl=9801) |
| B4.25 | Globo 2 vs globo 5 | 0.1543 | 1.0000 | ✅ PASA | chi²=9944 (gl=9801) |
| B4.34 | Globo 3 vs globo 4 | 0.3562 | 1.0000 | ✅ PASA | chi²=9852 (gl=9801) |
| B4.35 | Globo 3 vs globo 5 | 0.6039 | 1.0000 | ✅ PASA | chi²=9763 (gl=9801) |
| B4.45 | Globo 4 vs globo 5 | 0.8018 | 1.0000 | ✅ PASA | chi²=9682 (gl=9801) |
| B5.1d | Decenas globo 1 | 0.6679 | 1.0000 | ✅ PASA | chi²=6.7 |
| B5.1u | Unidades globo 1 | 0.3757 | 1.0000 | ✅ PASA | chi²=9.7 |
| B5.1i | Decena vs unidad globo 1 | 0.3765 | 1.0000 | ✅ PASA | chi²=84.4 |
| B5.2d | Decenas globo 2 | 0.3126 | 1.0000 | ✅ PASA | chi²=10.5 |
| B5.2u | Unidades globo 2 | 0.2089 | 1.0000 | ✅ PASA | chi²=12.1 |
| B5.2i | Decena vs unidad globo 2 | 0.3606 | 1.0000 | ✅ PASA | chi²=84.9 |
| B5.3d | Decenas globo 3 | 0.3964 | 1.0000 | ✅ PASA | chi²=9.5 |
| B5.3u | Unidades globo 3 | 0.3819 | 1.0000 | ✅ PASA | chi²=9.6 |
| B5.3i | Decena vs unidad globo 3 | 0.2938 | 1.0000 | ✅ PASA | chi²=87.4 |
| B5.4d | Decenas globo 4 | 0.0195 | 1.0000 | ✅ PASA | chi²=19.8 |
| B5.4u | Unidades globo 4 | 0.0994 | 1.0000 | ✅ PASA | chi²=14.7 |
| B5.4i | Decena vs unidad globo 4 | 0.7696 | 1.0000 | ✅ PASA | chi²=71.3 |
| B5.5d | Decenas globo 5 | 0.1963 | 1.0000 | ✅ PASA | chi²=12.3 |
| B5.5u | Unidades globo 5 | 0.4409 | 1.0000 | ✅ PASA | chi²=9.0 |
| B5.5i | Decena vs unidad globo 5 | 0.6259 | 1.0000 | ✅ PASA | chi²=76.3 |
| B6 | Tiempo de retorno de cada número (gaps) | 0.4895 | 1.0000 | ✅ PASA | chi²=18.5 (gl=19), 526630 gaps, media 99.91 (justa 100) |
| B7.1 | Memoria a 1-185 sorteos, globo 1 | 0.2191 | 1.0000 | ✅ PASA | Q=199.6 (gl=185); lag más extremo 172 (z=-3.05) |
| B7.2 | Memoria a 1-185 sorteos, globo 2 | 0.2593 | 1.0000 | ✅ PASA | Q=197.0 (gl=185); lag más extremo 174 (z=+3.06) |
| B7.3 | Memoria a 1-185 sorteos, globo 3 | 0.0690 | 1.0000 | ✅ PASA | Q=214.3 (gl=185); lag más extremo 72 (z=-3.17) |
| B7.4 | Memoria a 1-185 sorteos, globo 4 | 0.1128 | 1.0000 | ✅ PASA | Q=208.6 (gl=185); lag más extremo 3 (z=+2.79) |
| B7.5 | Memoria a 1-185 sorteos, globo 5 | 0.6655 | 1.0000 | ✅ PASA | Q=176.2 (gl=185); lag más extremo 99 (z=-2.83) |
| B7.p | Memoria de la paridad a 1-185 sorteos, globo 1 | 0.7404 | 1.0000 | ✅ PASA | Q=172.2 (gl=185); lag más extremo 162 (z=-2.83) |
| B8a | Misma hora, días consecutivos (coincidencias) | 0.9213 | 1.0000 | ✅ PASA | 5198 coincidencias en 520575 comparaciones, esperadas 5206 |
| B8b | ¿Cada horario tiene números propios? (horario × número) | 0.2664 | 1.0000 | ✅ PASA | chi²=18533 (gl=18414) |
| B9a | Sorteos completos repetidos (5 números iguales) | 1.0000 | 1.0000 | ✅ PASA | 0 repetidos, esperados 0.56 |
| B9b | Secuencia repetida más larga (globo 1) | 1.0000 | 1.0000 | ✅ PASA | la más larga mide 4 sorteos; con azar lo típico es 4.9 |
| B10a | Fórmula lineal entre sorteos (x' = a·x + c mod 100) | 1.0000 | 1.0000 | ✅ PASA | peor a=54, p corregido por 100 pruebas |
| B10b | Fórmula lineal entre globos del mismo sorteo | 0.1157 | 1.0000 | ✅ PASA | peor a=50, p corregido por 100 pruebas |
| B11a | Hora del día × número | 0.5360 | 1.0000 | ✅ PASA | chi²=1578 (gl=1584) |
| B11b | Día de la semana × número | 0.4766 | 1.0000 | ✅ PASA | chi²=595 (gl=594) |
| B11c | Mes × número | 0.3221 | 1.0000 | ✅ PASA | chi²=1110 (gl=1089) |

## 5. Limitaciones

- Dieharder no se corrió: necesita cientos de MB y aquí hay ~250 KB; reciclaría datos y daría falsos fallos.
- TestU01 no se corrió: no hay compilador C y no se instalaron dependencias.
- NIST se implementó en numpy/scipy y se validó con los ejemplos numéricos de SP 800-22 (`rng_audit/test_nist_examples.py`).
- B1b (fuente de 16 bits) tiene poca potencia: el sesgo esperado (0,00035) es menor que el error estadístico con este volumen de datos.
- Ninguna prueba identifica el algoritmo exacto: al reducir cada salida a 00-99 se pierde la información necesaria.
