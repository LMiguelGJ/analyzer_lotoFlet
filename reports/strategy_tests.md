# Pruebas de estrategias de apuesta en Chance Express

- Fuente: `chance_express_history.json` (SHA-256 `d1c0e9ec047dfa6a…`, solo lectura)
- Sorteos: 105,426 · Días: 566 · Entrenamiento: 2025-03-05 → 2026-02-09 · Prueba ciega: 2026-02-10 → 2026-09-25
- Reglas: por cada peso, 70 si sale 1º, 8 si sale 2º, 4 si 3º, 2 si 4º, 1 si 5º. Bajo sorteos aleatorios con estos pagos desfavorables, el retorno esperado es 0,85 por peso (pérdida esperada del 15%); no es un juego justo.
- Criterio: α = 0.01, con corrección de Holm sobre todas las pruebas de cada dataset. ❌ FALLA = rechazo estadístico de la hipótesis nula, no prueba de un patrón real; ⚠️ SOSPECHOSA = p < 0,01 sin corregir, sin evidencia tras Holm.
- Controles: **sano** simula sorteos aleatorios (puede tener falsos positivos). **trampa** tiene 4 patrones sembrados a propósito (permite comprobar sensibilidad a los patrones buscados).

## 1. Veredicto por idea

| Idea | Pregunta | Loteka | sano (SHA-256) | trampa (4 patrones sembrados) |
|---|---|---|---|---|
| #1 Mitades tras racha | ¿Después de N iguales (par/impar, bajo/alto) sale más la otra mitad? | ✅ 0/40 pruebas válidas fallan | ✅ 0/40 pruebas válidas fallan | ❌ 3/40 pruebas válidas fallan, 2 sospechosas |
| #2 Números fríos | ¿Un número que lleva X sorteos sin salir 1º sale más? | ⚠️ 0/9 pruebas válidas fallan, 3 N/A | ⚠️ 0/9 pruebas válidas fallan, 3 N/A | ❌ 5/9 pruebas válidas fallan, 1 sospechosas, 3 N/A |
| #6 Arrastre | ¿Un número del sorteo anterior sube al 1º? | ✅ 0/6 pruebas válidas fallan | ✅ 0/6 pruebas válidas fallan | ❌ 6/6 pruebas válidas fallan |
| #12 Dobles | ¿Un número que salió doble vuelve pronto? | ✅ 0/6 pruebas válidas fallan | ✅ 0/6 pruebas válidas fallan | ❌ 6/6 pruebas válidas fallan |
| #21 Entrar tras N fallos | ¿Esperar N iguales y cubrir la otra mitad paga más? | ✅ 0/12 pruebas válidas fallan | ✅ 0/12 pruebas válidas fallan | ❌ 4/12 pruebas válidas fallan |
| #26 Audaz vs tímida | ¿Los datos reales se comportan como un juego justo al buscar una meta? | ✅ 0/4 pruebas válidas fallan | ✅ 0/4 pruebas válidas fallan | ✅ 0/4 pruebas válidas fallan |
| #29 Cambio de fuente | ¿premios.do y loteka.com.do se comportan igual? | ⚠️ 0/221 pruebas válidas fallan, 3 sospechosas, 17 N/A | ⚠️ 0/221 pruebas válidas fallan, 1 sospechosas, 17 N/A | ❌ 34/221 pruebas válidas fallan, 9 sospechosas, 17 N/A |
| #27 Regla de repetidos | ¿Cuánto cambia el margen según cómo paguen un número repetido? | margen 15.00% si pagan todas las posiciones, 15.26% si solo la mejor | — | — |

## Resumen de todos los N (Loteka)

E1 cuenta el cambio tras exactamente N iguales; E5 cuenta la entrada tras ≥N. Todas las variantes y N; el detalle estadístico completo sigue más abajo.

### E1: N=1–10, cambio de mitad

| Variante y N | Casos | Tasa observada |
|---|---:|---:|
| E1 par-g1 N=1 | 52,928 | 50.28% |
| E1 par-g1 N=2 | 26,180 | 49.80% |
| E1 par-g1 N=3 | 13,071 | 50.65% |
| E1 par-g1 N=4 | 6,418 | 50.56% |
| E1 par-g1 N=5 | 3,157 | 50.71% |
| E1 par-g1 N=6 | 1,551 | 49.97% |
| E1 par-g1 N=7 | 770 | 48.31% |
| E1 par-g1 N=8 | 397 | 48.11% |
| E1 par-g1 N=9 | 206 | 52.43% |
| E1 par-g1 N=10 | 96 | 46.88% |
| E1 par-5g N=1 | 263,766 | 49.96% |
| E1 par-5g N=2 | 131,288 | 50.08% |
| E1 par-5g N=3 | 65,201 | 50.14% |
| E1 par-5g N=4 | 32,336 | 50.23% |
| E1 par-5g N=5 | 16,017 | 50.46% |
| E1 par-5g N=6 | 7,896 | 50.23% |
| E1 par-5g N=7 | 3,904 | 49.41% |
| E1 par-5g N=8 | 1,966 | 49.34% |
| E1 par-5g N=9 | 990 | 50.91% |
| E1 par-5g N=10 | 482 | 50.00% |
| E1 alto-g1 N=1 | 52,704 | 49.77% |
| E1 alto-g1 N=2 | 26,327 | 50.25% |
| E1 alto-g1 N=3 | 13,015 | 50.46% |
| E1 alto-g1 N=4 | 6,418 | 50.02% |
| E1 alto-g1 N=5 | 3,188 | 50.50% |
| E1 alto-g1 N=6 | 1,569 | 49.14% |
| E1 alto-g1 N=7 | 795 | 48.43% |
| E1 alto-g1 N=8 | 405 | 43.70% |
| E1 alto-g1 N=9 | 225 | 52.44% |
| E1 alto-g1 N=10 | 106 | 48.11% |
| E1 alto-5g N=1 | 263,586 | 49.97% |
| E1 alto-5g N=2 | 131,198 | 50.20% |
| E1 alto-5g N=3 | 64,988 | 49.89% |
| E1 alto-5g N=4 | 32,408 | 50.06% |
| E1 alto-5g N=5 | 16,090 | 49.80% |
| E1 alto-5g N=6 | 8,041 | 49.96% |
| E1 alto-5g N=7 | 4,003 | 50.44% |
| E1 alto-5g N=8 | 1,976 | 48.48% |
| E1 alto-5g N=9 | 1,011 | 50.45% |
| E1 alto-5g N=10 | 495 | 47.68% |

### E5: N≥3–8, cambio a la otra mitad

| Variante y N | Casos | Tasa observada |
|---|---:|---:|
| E5 par/impar N≥3 | 25,752 | 50.51% |
| E5 par/impar N≥4 | 12,681 | 50.37% |
| E5 par/impar N≥5 | 6,263 | 50.17% |
| E5 par/impar N≥6 | 3,106 | 49.61% |
| E5 par/impar N≥7 | 1,555 | 49.26% |
| E5 par/impar N≥8 | 785 | 50.19% |
| E5 bajo/alto N≥3 | 25,829 | 50.11% |
| E5 bajo/alto N≥4 | 12,814 | 49.76% |
| E5 bajo/alto N≥5 | 6,396 | 49.50% |
| E5 bajo/alto N≥6 | 3,208 | 48.50% |
| E5 bajo/alto N≥7 | 1,639 | 47.90% |
| E5 bajo/alto N≥8 | 844 | 47.39% |

## 2. La plata: comparación con el retorno aleatorio esperado

El parámetro se eligió mirando solo el entrenamiento (el que más devolvió), y se mide en la prueba ciega, que la estrategia nunca vio. Retorno = pesos cobrados por peso apostado, con intervalo bootstrap de 95%. Referencia aleatoria bajo estos pagos = 0,85; superar esa referencia no implica rentabilidad (que exige retorno > 1).
Los IC 95% de la grilla completa son descriptivos, sin ajuste simultáneo por comparar variantes; no son confirmación de estrategias seleccionadas después de ver los datos.

| Idea | Dataset | Parámetro elegido | Retorno entrenamiento | Retorno prueba ciega [IC 95%] | Apostado prueba ciega | Ganancia neta prueba ciega | Capital mínimo prueba ciega (escalera) | Comparación con 0,85 |
|---|---|---|---:|---:|---:|---:|---:|---|
| #2 Fríos | Loteka | frío en cualquier ≥200 | 1.3712 | 0.6350 [0.055–3.283] | 137 | -50 | — | INCONCLUSO VS AZAR |
| #2 Fríos | sano (SHA-256) | frío en cualquier ≥200 | 1.1949 | 1.4937 [0.326–2.224] | 160 | +79 | — | INCONCLUSO VS AZAR |
| #2 Fríos | trampa (4 patrones sembrados) | frío en 1º ≥400 | 2.1444 | 2.0979 [1.794–2.465] | 4,727 | +5,190 | — | SUPERA RETORNO ALEATORIO |
| #6 Arrastre | Loteka | jugar el 2º anterior | 0.8700 | 0.8716 [0.804–0.942] | 41,953 | -5,387 | — | INCONCLUSO VS AZAR |
| #6 Arrastre | sano (SHA-256) | jugar el 3º anterior | 0.8985 | 0.8668 [0.800–0.938] | 41,953 | -5,590 | — | INCONCLUSO VS AZAR |
| #6 Arrastre | trampa (4 patrones sembrados) | jugar el 2º anterior | 4.4595 | 4.5240 [4.362–4.692] | 41,953 | +147,841 | — | SUPERA RETORNO ALEATORIO |
| #12 Dobles | Loteka | jugar el doble 20 sorteos | 0.8839 | 0.8462 [0.796–0.893] | 77,405 | -11,908 | — | INCONCLUSO VS AZAR |
| #12 Dobles | sano (SHA-256) | jugar el doble 5 sorteos | 0.8816 | 0.8891 [0.795–0.990] | 20,326 | -2,254 | — | INCONCLUSO VS AZAR |
| #12 Dobles | trampa (4 patrones sembrados) | jugar el doble 1 sorteos | 5.7116 | 5.5943 [5.089–6.130] | 4,121 | +18,933 | — | SUPERA RETORNO ALEATORIO |
| #21 Tras N fallos (plana) | Loteka | par/impar tras ≥5 | 0.8589 | 0.8432 [0.816–0.871] | 126,850 | -19,894 | — | INCONCLUSO VS AZAR |
| #21 Tras N fallos (plana) | sano (SHA-256) | par/impar tras ≥3 | 0.8573 | 0.8360 [0.824–0.849] | 532,550 | -87,329 | — | BAJO RETORNO ALEATORIO |
| #21 Tras N fallos (plana) | trampa (4 patrones sembrados) | par/impar tras ≥5 | 0.9656 | 0.9427 [0.912–0.973] | 117,250 | -6,720 | — | SUPERA RETORNO ALEATORIO |
| #21 Tras N fallos (escalera) | Loteka | par/impar tras ≥5 | igual que plana | 0.9030 [0.504–1.168] | 18,414,450 | -1,786,283 | 7,814,155 | INCONCLUSO VS AZAR |
| #21 Tras N fallos (escalera) | sano (SHA-256) | par/impar tras ≥3 | igual que plana | 0.7082 [0.533–0.902] | 89,343,850 | -26,066,400 | 27,598,033 | INCONCLUSO VS AZAR |
| #21 Tras N fallos (escalera) | trampa (4 patrones sembrados) | par/impar tras ≥5 | igual que plana | 0.8136 [0.442–1.166] | 26,084,250 | -4,862,293 | 6,885,686 | INCONCLUSO VS AZAR |

**Control sano, E5 plana: criterio previsto INCUMPLIDO.** En prueba ciega, su IC 95% [0.824–0.849] excluye 0,85 por debajo. No se ajustaron semilla, umbrales ni pruebas para ocultarlo.

**E2 frío en cualquier posición ≥200:** las apuestas en prueba ciega son escasas; un bootstrap por días con pocos eventos puede dar intervalos inestables o poco informativos. La ganancia observada no demuestra rentabilidad.

**Escalera:** capital mínimo = máximo de (apuesta del sorteo − saldo neto acumulado antes de apostar), para poder financiar cada apuesta; no es la peor caída del saldo ya liquidado. Las escaleras perdidas se cuentan tras fallar la décima apuesta, aunque cierre el día sin undécima apuesta. Si no se observan pérdidas raras de escalera, un retorno histórico aparente >1 no es una estimación fiable del futuro.

## 3. Detalle de Loteka

| ID | Pregunta | Observado | Esperado | Casos | p | p Holm | Veredicto |
|---|---|---:|---:|---:|---:|---:|---|
| E1 par-g1 N=1 | Cambia de mitad (par/impar, globo 1) tras 1 iguales | 0.5028 | 0.5000 | 52,928 | 0.1997 | 1.0000 | ✅ PASA |
| E1 par-g1 N=2 | Cambia de mitad (par/impar, globo 1) tras 2 iguales | 0.4980 | 0.5000 | 26,180 | 0.5164 | 1.0000 | ✅ PASA |
| E1 par-g1 N=3 | Cambia de mitad (par/impar, globo 1) tras 3 iguales | 0.5065 | 0.5000 | 13,071 | 0.1370 | 1.0000 | ✅ PASA |
| E1 par-g1 N=4 | Cambia de mitad (par/impar, globo 1) tras 4 iguales | 0.5056 | 0.5000 | 6,418 | 0.3755 | 1.0000 | ✅ PASA |
| E1 par-g1 N=5 | Cambia de mitad (par/impar, globo 1) tras 5 iguales | 0.5071 | 0.5000 | 3,157 | 0.4336 | 1.0000 | ✅ PASA |
| E1 par-g1 N=6 | Cambia de mitad (par/impar, globo 1) tras 6 iguales | 0.4997 | 0.5000 | 1,551 | 1.0000 | 1.0000 | ✅ PASA |
| E1 par-g1 N=7 | Cambia de mitad (par/impar, globo 1) tras 7 iguales | 0.4831 | 0.5000 | 770 | 0.3676 | 1.0000 | ✅ PASA |
| E1 par-g1 N=8 | Cambia de mitad (par/impar, globo 1) tras 8 iguales | 0.4811 | 0.5000 | 397 | 0.4823 | 1.0000 | ✅ PASA |
| E1 par-g1 N=9 | Cambia de mitad (par/impar, globo 1) tras 9 iguales | 0.5243 | 0.5000 | 206 | 0.5307 | 1.0000 | ✅ PASA |
| E1 par-g1 N=10 | Cambia de mitad (par/impar, globo 1) tras 10 iguales | 0.4688 | 0.5000 | 96 | 0.6101 | 1.0000 | ✅ PASA |
| E1 par-5g N=1 | Cambia de mitad (par/impar, 5 globos) tras 1 iguales | 0.4996 | 0.5000 | 263,766 | 0.6869 | 1.0000 | ✅ PASA |
| E1 par-5g N=2 | Cambia de mitad (par/impar, 5 globos) tras 2 iguales | 0.5008 | 0.5000 | 131,288 | 0.5753 | 1.0000 | ✅ PASA |
| E1 par-5g N=3 | Cambia de mitad (par/impar, 5 globos) tras 3 iguales | 0.5014 | 0.5000 | 65,201 | 0.4712 | 1.0000 | ✅ PASA |
| E1 par-5g N=4 | Cambia de mitad (par/impar, 5 globos) tras 4 iguales | 0.5023 | 0.5000 | 32,336 | 0.4137 | 1.0000 | ✅ PASA |
| E1 par-5g N=5 | Cambia de mitad (par/impar, 5 globos) tras 5 iguales | 0.5046 | 0.5000 | 16,017 | 0.2487 | 1.0000 | ✅ PASA |
| E1 par-5g N=6 | Cambia de mitad (par/impar, 5 globos) tras 6 iguales | 0.5023 | 0.5000 | 7,896 | 0.6937 | 1.0000 | ✅ PASA |
| E1 par-5g N=7 | Cambia de mitad (par/impar, 5 globos) tras 7 iguales | 0.4941 | 0.5000 | 3,904 | 0.4714 | 1.0000 | ✅ PASA |
| E1 par-5g N=8 | Cambia de mitad (par/impar, 5 globos) tras 8 iguales | 0.4934 | 0.5000 | 1,966 | 0.5729 | 1.0000 | ✅ PASA |
| E1 par-5g N=9 | Cambia de mitad (par/impar, 5 globos) tras 9 iguales | 0.5091 | 0.5000 | 990 | 0.5890 | 1.0000 | ✅ PASA |
| E1 par-5g N=10 | Cambia de mitad (par/impar, 5 globos) tras 10 iguales | 0.5000 | 0.5000 | 482 | 1.0000 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=1 | Cambia de mitad (bajo/alto, globo 1) tras 1 iguales | 0.4977 | 0.5000 | 52,704 | 0.3019 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=2 | Cambia de mitad (bajo/alto, globo 1) tras 2 iguales | 0.5025 | 0.5000 | 26,327 | 0.4230 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=3 | Cambia de mitad (bajo/alto, globo 1) tras 3 iguales | 0.5046 | 0.5000 | 13,015 | 0.3010 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=4 | Cambia de mitad (bajo/alto, globo 1) tras 4 iguales | 0.5002 | 0.5000 | 6,418 | 0.9900 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=5 | Cambia de mitad (bajo/alto, globo 1) tras 5 iguales | 0.5050 | 0.5000 | 3,188 | 0.5830 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=6 | Cambia de mitad (bajo/alto, globo 1) tras 6 iguales | 0.4914 | 0.5000 | 1,569 | 0.5116 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=7 | Cambia de mitad (bajo/alto, globo 1) tras 7 iguales | 0.4843 | 0.5000 | 795 | 0.3947 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=8 | Cambia de mitad (bajo/alto, globo 1) tras 8 iguales | 0.4370 | 0.5000 | 405 | 0.0129 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=9 | Cambia de mitad (bajo/alto, globo 1) tras 9 iguales | 0.5244 | 0.5000 | 225 | 0.5051 | 1.0000 | ✅ PASA |
| E1 alto-g1 N=10 | Cambia de mitad (bajo/alto, globo 1) tras 10 iguales | 0.4811 | 0.5000 | 106 | 0.7709 | 1.0000 | ✅ PASA |
| E1 alto-5g N=1 | Cambia de mitad (bajo/alto, 5 globos) tras 1 iguales | 0.4997 | 0.5000 | 263,586 | 0.7274 | 1.0000 | ✅ PASA |
| E1 alto-5g N=2 | Cambia de mitad (bajo/alto, 5 globos) tras 2 iguales | 0.5020 | 0.5000 | 131,198 | 0.1519 | 1.0000 | ✅ PASA |
| E1 alto-5g N=3 | Cambia de mitad (bajo/alto, 5 globos) tras 3 iguales | 0.4989 | 0.5000 | 64,988 | 0.5695 | 1.0000 | ✅ PASA |
| E1 alto-5g N=4 | Cambia de mitad (bajo/alto, 5 globos) tras 4 iguales | 0.5006 | 0.5000 | 32,408 | 0.8458 | 1.0000 | ✅ PASA |
| E1 alto-5g N=5 | Cambia de mitad (bajo/alto, 5 globos) tras 5 iguales | 0.4980 | 0.5000 | 16,090 | 0.6194 | 1.0000 | ✅ PASA |
| E1 alto-5g N=6 | Cambia de mitad (bajo/alto, 5 globos) tras 6 iguales | 0.4996 | 0.5000 | 8,041 | 0.9467 | 1.0000 | ✅ PASA |
| E1 alto-5g N=7 | Cambia de mitad (bajo/alto, 5 globos) tras 7 iguales | 0.5044 | 0.5000 | 4,003 | 0.5910 | 1.0000 | ✅ PASA |
| E1 alto-5g N=8 | Cambia de mitad (bajo/alto, 5 globos) tras 8 iguales | 0.4848 | 0.5000 | 1,976 | 0.1844 | 1.0000 | ✅ PASA |
| E1 alto-5g N=9 | Cambia de mitad (bajo/alto, 5 globos) tras 9 iguales | 0.5045 | 0.5000 | 1,011 | 0.8014 | 1.0000 | ✅ PASA |
| E1 alto-5g N=10 | Cambia de mitad (bajo/alto, 5 globos) tras 10 iguales | 0.4768 | 0.5000 | 495 | 0.3228 | 1.0000 | ✅ PASA |
| E2 1º X=100 | Número frío (≥100 sorteos sin salir en 1º) sale 1º | 0.0101 | 0.0100 | 3,879,314 | 0.1932 | 1.0000 | ✅ PASA |
| E2 1º X=150 | Número frío (≥150 sorteos sin salir en 1º) sale 1º | 0.0101 | 0.0100 | 2,334,985 | 0.4166 | 1.0000 | ✅ PASA |
| E2 1º X=200 | Número frío (≥200 sorteos sin salir en 1º) sale 1º | 0.0101 | 0.0100 | 1,407,358 | 0.3624 | 1.0000 | ✅ PASA |
| E2 1º X=300 | Número frío (≥300 sorteos sin salir en 1º) sale 1º | 0.0100 | 0.0100 | 514,079 | 0.8171 | 1.0000 | ✅ PASA |
| E2 1º X=400 | Número frío (≥400 sorteos sin salir en 1º) sale 1º | 0.0101 | 0.0100 | 188,564 | 0.5550 | 1.0000 | ✅ PASA |
| E2 1º X=500 | Número frío (≥500 sorteos sin salir en 1º) sale 1º | 0.0100 | 0.0100 | 67,636 | 1.0000 | 1.0000 | ✅ PASA |
| E2 cualquier X=100 | Número frío (≥100 sorteos sin salir en cualquier) sale 1º | 0.0108 | 0.0100 | 70,073 | 0.0368 | 1.0000 | ✅ PASA |
| E2 cualquier X=150 | Número frío (≥150 sorteos sin salir en cualquier) sale 1º | 0.0107 | 0.0100 | 4,771 | 0.6102 | 1.0000 | ✅ PASA |
| E2 cualquier X=200 | Número frío (≥200 sorteos sin salir en cualquier) sale 1º | 0.0137 | 0.0100 | 366 | 0.4234 | 1.0000 | ✅ PASA |
| E2 cualquier X=300 | Número frío (≥300 sorteos sin salir en cualquier) sale 1º | — | 0.0100 | 0 | N/A | N/A | N/A (sin casos) |
| E2 cualquier X=400 | Número frío (≥400 sorteos sin salir en cualquier) sale 1º | — | 0.0100 | 0 | N/A | N/A | N/A (sin casos) |
| E2 cualquier X=500 | Número frío (≥500 sorteos sin salir en cualquier) sale 1º | — | 0.0100 | 0 | N/A | N/A | N/A (sin casos) |
| E3 1º→1º | El 1º de un sorteo sale 1º en el siguiente | 0.0096 | 0.0100 | 104,860 | 0.2144 | 1.0000 | ✅ PASA |
| E3 2º→1º | El 2º de un sorteo sale 1º en el siguiente | 0.0103 | 0.0100 | 104,860 | 0.2705 | 1.0000 | ✅ PASA |
| E3 3º→1º | El 3º de un sorteo sale 1º en el siguiente | 0.0102 | 0.0100 | 104,860 | 0.4287 | 1.0000 | ✅ PASA |
| E3 4º→1º | El 4º de un sorteo sale 1º en el siguiente | 0.0097 | 0.0100 | 104,860 | 0.3518 | 1.0000 | ✅ PASA |
| E3 5º→1º | El 5º de un sorteo sale 1º en el siguiente | 0.0098 | 0.0100 | 104,860 | 0.4753 | 1.0000 | ✅ PASA |
| E3 5→1º | Algún número del sorteo anterior sale 1º | 0.0488 | 0.0490 | 104,860 | 0.7755 | 1.0000 | ✅ PASA |
| E4 1º w=1 | Número doble sale 1º en los 1 sorteos siguientes | 0.0087 | 0.0100 | 10,204 | 0.1447 | 1.0000 | ✅ PASA |
| E4 any w=1 | Número doble sale en cualquier posición en los 1 siguientes | 0.0465 | 0.0490 | 10,204 | 0.2314 | 1.0000 | ✅ PASA |
| E4 1º w=5 | Número doble sale 1º en los 5 sorteos siguientes | 0.0100 | 0.0100 | 50,425 | 0.9546 | 1.0000 | ✅ PASA |
| E4 any w=5 | Número doble sale en cualquier posición en los 5 siguientes | 0.0480 | 0.0490 | 50,425 | 0.2752 | 1.0000 | ✅ PASA |
| E4 1º w=20 | Número doble sale 1º en los 20 sorteos siguientes | 0.0103 | 0.0100 | 193,168 | 0.1747 | 1.0000 | ✅ PASA |
| E4 any w=20 | Número doble sale en cualquier posición en los 20 siguientes | 0.0486 | 0.0490 | 193,168 | 0.4597 | 1.0000 | ✅ PASA |
| E5 par/impar N≥3 | Tras ≥3 iguales (par/impar) sale la otra mitad en el 1º | 0.5051 | 0.5000 | 25,752 | 0.1012 | 1.0000 | ✅ PASA |
| E5 par/impar N≥4 | Tras ≥4 iguales (par/impar) sale la otra mitad en el 1º | 0.5037 | 0.5000 | 12,681 | 0.4139 | 1.0000 | ✅ PASA |
| E5 par/impar N≥5 | Tras ≥5 iguales (par/impar) sale la otra mitad en el 1º | 0.5017 | 0.5000 | 6,263 | 0.8005 | 1.0000 | ✅ PASA |
| E5 par/impar N≥6 | Tras ≥6 iguales (par/impar) sale la otra mitad en el 1º | 0.4961 | 0.5000 | 3,106 | 0.6798 | 1.0000 | ✅ PASA |
| E5 par/impar N≥7 | Tras ≥7 iguales (par/impar) sale la otra mitad en el 1º | 0.4926 | 0.5000 | 1,555 | 0.5769 | 1.0000 | ✅ PASA |
| E5 par/impar N≥8 | Tras ≥8 iguales (par/impar) sale la otra mitad en el 1º | 0.5019 | 0.5000 | 785 | 0.9431 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥3 | Tras ≥3 iguales (bajo/alto) sale la otra mitad en el 1º | 0.5011 | 0.5000 | 25,829 | 0.7275 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥4 | Tras ≥4 iguales (bajo/alto) sale la otra mitad en el 1º | 0.4976 | 0.5000 | 12,814 | 0.5900 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥5 | Tras ≥5 iguales (bajo/alto) sale la otra mitad en el 1º | 0.4950 | 0.5000 | 6,396 | 0.4308 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥6 | Tras ≥6 iguales (bajo/alto) sale la otra mitad en el 1º | 0.4850 | 0.5000 | 3,208 | 0.0935 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥7 | Tras ≥7 iguales (bajo/alto) sale la otra mitad en el 1º | 0.4790 | 0.5000 | 1,639 | 0.0930 | 1.0000 | ✅ PASA |
| E5 bajo/alto N≥8 | Tras ≥8 iguales (bajo/alto) sale la otra mitad en el 1º | 0.4739 | 0.5000 | 844 | 0.1388 | 1.0000 | ✅ PASA |

### Todas las variantes con plata (todos los datos)

| Idea | Variante | Apostado | Retorno [IC 95%] | Ganancia neta | Peor caída | Capital mínimo | Escaleras perdidas |
|---|---|---:|---:|---:|---:|---:|---:|
| #2 Fríos | frío en 1º ≥100 | 3,879,314 | 0.8552 [0.850–0.860] | -561,624 | 561,682 | 561,704 |  |
| #2 Fríos | frío en 1º ≥150 | 2,334,985 | 0.8535 [0.846–0.861] | -342,054 | 342,225 | 342,150 |  |
| #2 Fríos | frío en 1º ≥200 | 1,407,358 | 0.8546 [0.844–0.865] | -204,663 | 204,824 | 204,774 |  |
| #2 Fríos | frío en 1º ≥300 | 514,079 | 0.8508 [0.831–0.870] | -76,712 | 77,076 | 77,083 |  |
| #2 Fríos | frío en 1º ≥400 | 188,564 | 0.8616 [0.830–0.894] | -26,103 | 26,415 | 26,215 |  |
| #2 Fríos | frío en 1º ≥500 | 67,636 | 0.8537 [0.806–0.905] | -9,895 | 10,009 | 9,895 |  |
| #2 Fríos | frío en cualquier ≥100 | 70,073 | 0.9113 [0.859–0.964] | -6,216 | 6,905 | 6,708 |  |
| #2 Fríos | frío en cualquier ≥150 | 4,771 | 0.9195 [0.718–1.146] | -384 | 762 | 541 |  |
| #2 Fríos | frío en cualquier ≥200 | 366 | 1.0956 [0.367–2.539] | +35 | 151 | 39 |  |
| #2 Fríos | frío en cualquier ≥300 | 0 | — | +0 | 0 | 0 |  |
| #2 Fríos | frío en cualquier ≥400 | 0 | — | +0 | 0 | 0 |  |
| #2 Fríos | frío en cualquier ≥500 | 0 | — | +0 | 0 | 0 |  |
| #6 Arrastre | jugar el 1º anterior | 104,860 | 0.8206 [0.779–0.863] | -18,808 | 20,403 | 20,076 |  |
| #6 Arrastre | jugar el 2º anterior | 104,860 | 0.8706 [0.827–0.911] | -13,568 | 14,356 | 13,746 |  |
| #6 Arrastre | jugar el 3º anterior | 104,860 | 0.8636 [0.821–0.908] | -14,307 | 15,126 | 14,899 |  |
| #6 Arrastre | jugar el 4º anterior | 104,860 | 0.8318 [0.792–0.871] | -17,636 | 17,877 | 17,636 |  |
| #6 Arrastre | jugar el 5º anterior | 104,860 | 0.8382 [0.795–0.880] | -16,970 | 17,269 | 16,970 |  |
| #6 Arrastre | jugar los 5 anteriores | 513,994 | 0.8468 [0.828–0.865] | -78,736 | 80,374 | 79,283 |  |
| #12 Dobles | jugar el doble 1 sorteos | 10,204 | 0.7570 [0.634–0.887] | -2,480 | 2,481 | 2,482 |  |
| #12 Dobles | jugar el doble 5 sorteos | 50,425 | 0.8436 [0.785–0.906] | -7,884 | 7,999 | 7,974 |  |
| #12 Dobles | jugar el doble 20 sorteos | 193,168 | 0.8688 [0.836–0.900] | -25,348 | 25,536 | 25,539 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥3 | 1,287,600 | 0.8565 [0.848–0.866] | -184,766 | 185,019 | 184,893 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥4 | 634,050 | 0.8547 [0.842–0.868] | -92,101 | 92,216 | 92,229 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥5 | 313,150 | 0.8525 [0.834–0.871] | -46,184 | 46,264 | 46,259 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥6 | 155,300 | 0.8435 [0.819–0.866] | -24,306 | 24,366 | 24,381 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥7 | 77,750 | 0.8387 [0.809–0.872] | -12,544 | 12,593 | 12,619 |  |
| #21 Tras N fallos (plana) | par/impar tras ≥8 | 39,250 | 0.8502 [0.807–0.893] | -5,879 | 5,960 | 5,954 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥3 | 1,291,450 | 0.8505 [0.841–0.859] | -193,037 | 193,179 | 193,166 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥4 | 640,700 | 0.8463 [0.833–0.859] | -98,446 | 98,716 | 98,519 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥5 | 319,800 | 0.8417 [0.824–0.860] | -50,614 | 50,767 | 50,687 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥6 | 160,400 | 0.8271 [0.806–0.852] | -27,730 | 27,793 | 27,803 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥7 | 81,950 | 0.8204 [0.787–0.854] | -14,715 | 14,760 | 14,810 |  |
| #21 Tras N fallos (plana) | bajo/alto tras ≥8 | 42,200 | 0.8137 [0.770–0.858] | -7,862 | 7,990 | 7,985 |  |
| #21 Tras N fallos (escalera) | par/impar tras ≥3 | 173,822,550 | 0.9009 [0.772–1.033] | -17,217,855 | 25,848,263 | 27,259,843 | 9 |
| #21 Tras N fallos (escalera) | par/impar tras ≥4 | 78,581,750 | 0.9031 [0.730–1.076] | -7,612,400 | 14,369,301 | 10,484,478 | 4 |
| #21 Tras N fallos (escalera) | par/impar tras ≥5 | 35,298,750 | 0.8746 [0.613–1.139] | -4,424,965 | 8,604,531 | 10,452,837 | 2 |
| #21 Tras N fallos (escalera) | par/impar tras ≥6 | 16,509,200 | 1.1699 [1.127–1.192] | +2,804,968 | 1,181,746 | 4,012,382 | 0 |
| #21 Tras N fallos (escalera) | par/impar tras ≥7 | 4,702,700 | 1.1708 [1.129–1.193] | +803,452 | 337,635 | 1,145,813 | 0 |
| #21 Tras N fallos (escalera) | par/impar tras ≥8 | 1,336,700 | 1.1727 [1.132–1.195] | +230,790 | 96,460 | 326,541 | 0 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥3 | 215,132,250 | 0.9206 [0.812–1.019] | -17,081,573 | 20,713,465 | 18,783,469 | 10 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥4 | 93,612,000 | 0.9343 [0.772–1.081] | -6,153,753 | 7,922,224 | 7,232,809 | 4 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥5 | 39,593,500 | 0.9346 [0.704–1.162] | -2,587,992 | 6,597,221 | 9,034,061 | 2 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥6 | 17,736,000 | 0.6456 [0.391–1.166] | -6,285,541 | 7,433,120 | 8,127,838 | 2 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥7 | 11,506,450 | 0.7824 [0.306–1.210] | -2,503,644 | 4,939,758 | 8,142,200 | 1 |
| #21 Tras N fallos (escalera) | bajo/alto tras ≥8 | 6,507,150 | 0.5332 [0.285–1.211] | -3,037,292 | 3,734,281 | 4,649,228 | 1 |

### #26 Apuesta audaz vs tímida (llegar a la meta)

Audaz = apostar a un número lo justo para llegar a la meta si sale 1º. Tímida = 10 pesos por sorteo. Sesiones reales una detrás de otra, sin compartir sorteos.

| Meta | Estilo | Datos reales [IC 95%] | Sesiones | Sorteos aleatorios con estos pagos [IC 95%] | Sorteos por sesión (mediana) | Si los pagos fueran justos |
|---|---|---:|---:|---:|---:|---:|
| 1,000 → 2,000 | audaz | 43.72% [41.77%–45.69%] | 2,461 | 42.80% [42.11%–43.48%] | 49 | 50.00% |
| 1,000 → 2,000 | tímida (10 por sorteo) | 34.20% [30.32%–38.29%] | 541 | 31.08% [30.44%–31.72%] | 170 | 50.00% |
| 5,000 → 10,000 | audaz | 44.13% [42.17%–46.12%] | 2,429 | 43.31% [42.62%–44.00%] | 49 | 50.00% |
| 5,000 → 10,000 | tímida (10 por sorteo) | 3.57% [0.63%–17.71%] | 28 | 5.45% [5.14%–5.77%] | 2347 | 50.00% |

| ID | Pregunta | Observado | Esperado | Casos | p | p Holm | Veredicto |
|---|---|---:|---:|---:|---:|---:|---|
| E6 1000→2000 bold | Datos reales vs sorteos aleatorios con estos pagos: audaz, 1000→2000 | 0.4372 | 0.4279 | 2,461 | 0.3593 | 1.0000 | ✅ PASA |
| E6 1000→2000 timid | Datos reales vs sorteos aleatorios con estos pagos: tímida (10 por sorteo), 1000→2000 | 0.3420 | 0.3108 | 541 | 0.1252 | 1.0000 | ✅ PASA |
| E6 5000→10000 bold | Datos reales vs sorteos aleatorios con estos pagos: audaz, 5000→10000 | 0.4413 | 0.4331 | 2,429 | 0.4129 | 1.0000 | ✅ PASA |
| E6 5000→10000 timid | Datos reales vs sorteos aleatorios con estos pagos: tímida (10 por sorteo), 5000→10000 | 0.0357 | 0.0545 | 28 | 1.0000 | 1.0000 | ✅ PASA |

### #27 Regla de números repetidos

| | Teórico | Real (tus datos) |
|---|---:|---:|
| Retorno si pagan todas las posiciones | 0.8500 | 0.8500 |
| Retorno si pagan solo la mejor | 0.8474 | 0.8474 |
| Sorteos con algún número repetido | 9.65% | 9.58% |

### #29 Cambio de fuente

- `loteka.com.do`: 28,530 sorteos, 2026-04-25 → 2026-09-25
- `premios.do`: 76,896 sorteos, 2025-03-05 → 2026-04-24

Se intentaron 238 filas: distribución por globo, tasa de repetidos, las 52 pruebas de la auditoría RNG y E1–E4, cada una por separado en cada fuente.


| ID | Pregunta | Observado | Esperado | Casos | p | p Holm | Veredicto |
|---|---|---:|---:|---:|---:|---:|---|
| E8 globo 1 | Misma distribución por fuente, globo 1 | — | — | 105,426 | 0.5381 | 1.0000 | ✅ PASA |
| E8 globo 2 | Misma distribución por fuente, globo 2 | — | — | 105,426 | 0.6039 | 1.0000 | ✅ PASA |
| E8 globo 3 | Misma distribución por fuente, globo 3 | — | — | 105,426 | 0.9741 | 1.0000 | ✅ PASA |
| E8 globo 4 | Misma distribución por fuente, globo 4 | — | — | 105,426 | 0.8804 | 1.0000 | ✅ PASA |
| E8 globo 5 | Misma distribución por fuente, globo 5 | — | — | 105,426 | 0.0926 | 1.0000 | ✅ PASA |
| E8 repetidos | Misma tasa de sorteos con repetidos por fuente | — | — | 105,426 | 0.5755 | 1.0000 | ✅ PASA |

E8: 238 filas intentadas, 221 con p válido; 17 N/A (11 tablas 100×100 con conteos esperados <5/celda, 6 sin casos):
- E8 loteka.com.do B3a: N/A — chi²=9830 (gl=9801), 28376 pares; N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.12: N/A — chi²=9925 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.13: N/A — chi²=9706 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.14: N/A — chi²=9698 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.15: N/A — chi²=9887 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.23: N/A — chi²=9922 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.24: N/A — chi²=9952 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.25: N/A — chi²=9830 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.34: N/A — chi²=9917 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.35: N/A — chi²=9911 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.45: N/A — chi²=9657 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do E2 cualquier X=300: N/A — sin casos
- E8 loteka.com.do E2 cualquier X=400: N/A — sin casos
- E8 loteka.com.do E2 cualquier X=500: N/A — sin casos
- E8 premios.do E2 cualquier X=300: N/A — sin casos
- E8 premios.do E2 cualquier X=400: N/A — sin casos
- E8 premios.do E2 cualquier X=500: N/A — sin casos

Pruebas válidas de E8 con p < 0,01 sin corregir: 3 de 221 (por azar se esperan ~2.2). Rechazos después de Holm: 0.
- E8 loteka.com.do E1 par-5g N=5: observado 0.5209, p 0.0061, p Holm 1.0000
- E8 loteka.com.do E4 1º w=1: observado 0.0057, p 0.0019, p Holm 0.5805
- E8 premios.do E1 alto-g1 N=8: observado 0.4186, p 0.0056, p Holm 1.0000

## 4. Controles: sensibilidad a patrones sembrados (no validación universal)

| Patrón sembrado en *trampa* | Prueba | Loteka | sano (SHA-256) | trampa (4 patrones sembrados) |
|---|---|---|---|---|
| Tras ≥5 impares en el 1º, par 65% | E1 par-g1 N=5 | ✅ obs 0.5071 (esp 0.5000), Holm 1.0000 | ✅ obs 0.4928 (esp 0.5000), Holm 1.0000 | ❌ obs 0.5927 (esp 0.5000), Holm 2.08e-24 |
| Tras ≥5 impares en el 1º, par 65% | E5 par/impar N≥5 | ✅ obs 0.5017 (esp 0.5000), Holm 1.0000 | ✅ obs 0.4921 (esp 0.5000), Holm 1.0000 | ❌ obs 0.5771 (esp 0.5000), Holm 2.59e-29 |
| El 2º pasa al 1º del siguiente (5%) | E3 2º→1º | ✅ obs 0.0103 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0099 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0620 (esp 0.0100), Holm <1e-300 |
| Un doble sale 1º en el siguiente (5%) | E4 1º w=1 | ✅ obs 0.0087 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0109 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0787 (esp 0.0100), Holm 7.64e-156 |
| Frío ≥300 sorteos sale 1º con 3% | E2 1º X=300 | ✅ obs 0.0100 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0100 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0283 (esp 0.0100), Holm <1e-300 |

## E9. Tras X exacto (00–99): siguiente primer globo, solo Loteka

Exploratorio y descriptivo, añadido después de E1–E8. Solo pares de sorteos consecutivos del mismo día; el siguiente primer globo es el destino. Referencia bajo azar: 1% de repetición de X (no un umbral de decisión). Las transiciones adyacentes se solapan y esta búsqueda es post hoc: no hay p por X, ni nueva familia Holm, ni un X elegido como predicción. La matriz completa 100×100 de conteos por origen y destino está en el JSON.

| X anterior | Casos | Repite X | Tasa de repetición | Nota |
|---|---:|---:|---:|---|
| 00 | 1,081 | 10 | 0.93% | descriptivo; no predice |
| 01 | 1,048 | 7 | 0.67% | descriptivo; no predice |
| 02 | 1,097 | 11 | 1.00% | descriptivo; no predice |
| 03 | 1,046 | 5 | 0.48% | descriptivo; no predice |
| 04 | 1,049 | 10 | 0.95% | descriptivo; no predice |
| 05 | 1,038 | 11 | 1.06% | descriptivo; no predice |
| 06 | 1,033 | 8 | 0.77% | descriptivo; no predice |
| 07 | 1,023 | 10 | 0.98% | descriptivo; no predice |
| 08 | 974 | 4 | 0.41% | descriptivo; no predice |
| 09 | 1,006 | 11 | 1.09% | descriptivo; no predice |
| 10 | 1,109 | 11 | 0.99% | descriptivo; no predice |
| 11 | 992 | 7 | 0.71% | descriptivo; no predice |
| 12 | 1,020 | 10 | 0.98% | descriptivo; no predice |
| 13 | 1,090 | 10 | 0.92% | descriptivo; no predice |
| 14 | 1,082 | 9 | 0.83% | descriptivo; no predice |
| 15 | 1,088 | 13 | 1.19% | descriptivo; no predice |
| 16 | 1,076 | 7 | 0.65% | descriptivo; no predice |
| 17 | 1,071 | 9 | 0.84% | descriptivo; no predice |
| 18 | 1,056 | 8 | 0.76% | descriptivo; no predice |
| 19 | 1,065 | 11 | 1.03% | descriptivo; no predice |
| 20 | 1,015 | 11 | 1.08% | descriptivo; no predice |
| 21 | 1,063 | 6 | 0.56% | descriptivo; no predice |
| 22 | 1,076 | 10 | 0.93% | descriptivo; no predice |
| 23 | 1,058 | 9 | 0.85% | descriptivo; no predice |
| 24 | 1,036 | 7 | 0.68% | descriptivo; no predice |
| 25 | 1,095 | 19 | 1.74% | descriptivo; no predice |
| 26 | 1,032 | 7 | 0.68% | descriptivo; no predice |
| 27 | 1,005 | 11 | 1.09% | descriptivo; no predice |
| 28 | 984 | 9 | 0.91% | descriptivo; no predice |
| 29 | 1,015 | 11 | 1.08% | descriptivo; no predice |
| 30 | 1,121 | 14 | 1.25% | descriptivo; no predice |
| 31 | 1,036 | 11 | 1.06% | descriptivo; no predice |
| 32 | 1,052 | 7 | 0.67% | descriptivo; no predice |
| 33 | 1,058 | 13 | 1.23% | descriptivo; no predice |
| 34 | 1,059 | 10 | 0.94% | descriptivo; no predice |
| 35 | 1,106 | 20 | 1.81% | descriptivo; no predice |
| 36 | 1,036 | 14 | 1.35% | descriptivo; no predice |
| 37 | 1,046 | 7 | 0.67% | descriptivo; no predice |
| 38 | 1,018 | 9 | 0.88% | descriptivo; no predice |
| 39 | 1,000 | 9 | 0.90% | descriptivo; no predice |
| 40 | 1,049 | 11 | 1.05% | descriptivo; no predice |
| 41 | 1,053 | 15 | 1.42% | descriptivo; no predice |
| 42 | 1,033 | 15 | 1.45% | descriptivo; no predice |
| 43 | 1,063 | 8 | 0.75% | descriptivo; no predice |
| 44 | 1,020 | 10 | 0.98% | descriptivo; no predice |
| 45 | 1,023 | 9 | 0.88% | descriptivo; no predice |
| 46 | 1,074 | 5 | 0.47% | descriptivo; no predice |
| 47 | 1,044 | 13 | 1.25% | descriptivo; no predice |
| 48 | 1,011 | 8 | 0.79% | descriptivo; no predice |
| 49 | 1,002 | 9 | 0.90% | descriptivo; no predice |
| 50 | 1,057 | 15 | 1.42% | descriptivo; no predice |
| 51 | 1,089 | 7 | 0.64% | descriptivo; no predice |
| 52 | 992 | 9 | 0.91% | descriptivo; no predice |
| 53 | 1,052 | 10 | 0.95% | descriptivo; no predice |
| 54 | 999 | 15 | 1.50% | descriptivo; no predice |
| 55 | 1,050 | 9 | 0.86% | descriptivo; no predice |
| 56 | 1,066 | 9 | 0.84% | descriptivo; no predice |
| 57 | 1,084 | 9 | 0.83% | descriptivo; no predice |
| 58 | 1,030 | 12 | 1.17% | descriptivo; no predice |
| 59 | 1,079 | 9 | 0.83% | descriptivo; no predice |
| 60 | 1,004 | 16 | 1.59% | descriptivo; no predice |
| 61 | 1,026 | 12 | 1.17% | descriptivo; no predice |
| 62 | 1,089 | 15 | 1.38% | descriptivo; no predice |
| 63 | 994 | 5 | 0.50% | descriptivo; no predice |
| 64 | 1,040 | 8 | 0.77% | descriptivo; no predice |
| 65 | 1,093 | 8 | 0.73% | descriptivo; no predice |
| 66 | 1,022 | 10 | 0.98% | descriptivo; no predice |
| 67 | 1,036 | 12 | 1.16% | descriptivo; no predice |
| 68 | 1,050 | 3 | 0.29% | descriptivo; no predice |
| 69 | 1,105 | 11 | 1.00% | descriptivo; no predice |
| 70 | 1,066 | 16 | 1.50% | descriptivo; no predice |
| 71 | 1,083 | 8 | 0.74% | descriptivo; no predice |
| 72 | 1,017 | 9 | 0.88% | descriptivo; no predice |
| 73 | 1,034 | 4 | 0.39% | descriptivo; no predice |
| 74 | 1,057 | 9 | 0.85% | descriptivo; no predice |
| 75 | 995 | 10 | 1.01% | descriptivo; no predice |
| 76 | 1,008 | 14 | 1.39% | descriptivo; no predice |
| 77 | 1,104 | 9 | 0.82% | descriptivo; no predice |
| 78 | 1,066 | 12 | 1.13% | descriptivo; no predice |
| 79 | 1,050 | 10 | 0.95% | descriptivo; no predice |
| 80 | 1,072 | 15 | 1.40% | descriptivo; no predice |
| 81 | 1,089 | 13 | 1.19% | descriptivo; no predice |
| 82 | 998 | 8 | 0.80% | descriptivo; no predice |
| 83 | 1,082 | 11 | 1.02% | descriptivo; no predice |
| 84 | 1,043 | 5 | 0.48% | descriptivo; no predice |
| 85 | 1,048 | 12 | 1.15% | descriptivo; no predice |
| 86 | 1,035 | 14 | 1.35% | descriptivo; no predice |
| 87 | 1,096 | 19 | 1.73% | descriptivo; no predice |
| 88 | 1,081 | 8 | 0.74% | descriptivo; no predice |
| 89 | 1,017 | 11 | 1.08% | descriptivo; no predice |
| 90 | 1,066 | 5 | 0.47% | descriptivo; no predice |
| 91 | 1,036 | 15 | 1.45% | descriptivo; no predice |
| 92 | 1,021 | 6 | 0.59% | descriptivo; no predice |
| 93 | 1,063 | 11 | 1.03% | descriptivo; no predice |
| 94 | 1,027 | 5 | 0.49% | descriptivo; no predice |
| 95 | 1,051 | 8 | 0.76% | descriptivo; no predice |
| 96 | 1,060 | 7 | 0.66% | descriptivo; no predice |
| 97 | 1,109 | 15 | 1.35% | descriptivo; no predice |
| 98 | 1,067 | 8 | 0.75% | descriptivo; no predice |
| 99 | 1,035 | 8 | 0.77% | descriptivo; no predice |

## 5. Limitaciones

- Las reglas no dicen cómo se paga un número que sale en 2 posiciones. La plata se calculó pagando todas las posiciones; #27 muestra cuánto cambia con la otra lectura. Solo Loteka puede confirmarlo.
- #26: las sesiones se juegan una detrás de otra (no una por día, como decía el plan) para que no compartan sorteos y la prueba sea válida. Con 5.000 → 10.000 en modo tímido hay pocas sesiones, así que esa fila tiene poca precisión.
- El corte entrenamiento/prueba ciega cae antes del cambio de fuente (2026-04-25), así que la prueba ciega mezcla las dos fuentes. E8 compara directamente las distribuciones 2×100 y la tasa de repetidos; las pruebas dentro de cada fuente no prueban equivalencia entre fuentes. Los períodos son disjuntos: no detectar diferencias no implica mismo RNG ni equivalencia.
- En el control trampa, los patrones sembrados también mueven un poco otras pruebas (por ejemplo, meter números fríos en el 1º toca el arrastre). Es esperable: esos datos no son aleatorios.
- E4 usa inferencia bilateral robusta por día sobre aciertos menos aciertos esperados (1% para 1º; 1−0,99⁵ para cualquier posición), no binomial de ventanas solapadas. Supone independencia entre días; Holm no corrige dependencia dentro del día.
- Los intervalos de plata usan bootstrap por días (2.000 remuestreos), que agrupa sorteos del mismo día pero supone independencia entre días; con eventos escasos, como E2 ≥200 en cualquier posición, pueden ser poco fiables.
