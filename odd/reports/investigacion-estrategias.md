# Investigación: estrategias y modalidades para la Quiniela Leidsa

Fecha: 2026-11-24. Datos: `datos/leidsa_quiniela_history.json` (5.836 sorteos, 2010-07-19 → 2026-11-23).

## Conclusión

No se encontró en internet ni en GitHub ninguna estrategia con evidencia pública de ganarle a la quiniela
de forma sostenida. Con sorteos justos, ninguna forma de elegir números ni de manejar el dinero cambia el
retorno esperado de **0,72 por peso** (premios 60/8/4). La única ventaja real posible es un **sesgo físico**
del sorteo, y en Leidsa 2019–2026 no aparece.

## 1. Qué se encontró

### Repositorios de GitHub (búsqueda `gh search repos`, ordenado por estrellas)

| Repositorio | Qué hace | Evidencia de rentabilidad |
|---|---|---|
| yangboz/LotteryPrediction (292★) | ML genérico; vende planes de $9,99–$49,99/mes | Ninguna publicada |
| CorvusCodex/LotteryAi (158★) | Red neuronal; cobra en cripto | Su propio aviso: "Lottery results are inherently random and unpredictable" |
| engineer1982/Machine-Learning-Lottery-Prediction (82★) | Keras/TensorFlow | Ninguna |
| tiyh/rnn_lottery_prediction (22★) | LSTM | Ninguna |
| orlandomp90/AI_Oracle_Pick3 (2★) | CNN + Transformer para Pick 3 | Ninguna |
| carpenterma7/lottery_easy (50★) | Mezcla de I Ching, astrología y deep learning | Ninguna |

Ningún repositorio publica una prueba fuera de muestra (elegir con un período, comprobar con otro) con
ganancia. Varios cobran por las "predicciones".

### Estudios

- *Investigating randomness and fairness in the Romanian 6/49 lottery* (doi 10.56043/reveco-2025-0002) y
  *Time-Series Statistics and Statistical Balance in 6/45 Lotto* (doi 10.47116/apjcri.2025.02.43):
  analizan sorteos reales con pruebas de frecuencia y los encuentran compatibles con azar.
- *Is it possible to cheat the lottery draw by weighing* (TCI Thaijo, art. 83061): un bolo con peso
  distinto sí altera las frecuencias en una máquina de aire; es el único mecanismo real de ventaja.
- *A longitudinal analysis of the hot hand and gambler's fallacy biases* (doi 10.1017/jdm.2023.23):
  "números calientes" y "números atrasados" son sesgos de los jugadores, no del sorteo.

## 2. Catálogo de estrategias

**Elegir números**

| Estrategia | Idea | En la app |
|---|---|---|
| Calientes / frecuencia | El que más salió | Frec. histórica, Frec. reciente, Decaimiento |
| Fríos / atrasados | El que lleva más tiempo sin salir | Fríos |
| Ciclo vencido | El que superó su espera promedio | Pendiente (sistema nuevo) |
| Transición (Markov) | Qué número suele seguir al de ayer | Pendiente para Leidsa |
| Terminaciones y decenas | Dígito final o decena que más sale | Pendiente (sistema nuevo) |
| Ensamble | Combinar varios sistemas | Pendiente para Leidsa |
| Machine learning (LSTM, Transformer) | Red neuronal sobre la serie | No se agrega: sin evidencia y caro de validar |
| Charada, sueños, espejos, sumas | Tradición popular | Sin base estadística |

**Manejar el dinero** — martingala, D'Alembert, Fibonacci, Labouchère, escalera, audaz, metas y stop-loss.
Por el teorema de parada opcional, si cada apuesta tiene esperanza negativa, ninguna secuencia de montos
la vuelve positiva: solo cambia la forma de perder (pocas pérdidas grandes o muchas chicas). El criterio de
Kelly indica apostar 0 cuando la ventaja es negativa.

**Modalidades** (pagos típicos de bancas; verificar con la banca real)

| Modalidad | Qué hay que acertar | Retorno esperado por peso |
|---|---|---|
| Quiniela directa 60/8/4 | Un número en 1.ª, 2.ª o 3.ª | **0,72** |
| Palé 1000/1000/100 | Dos números en dos posiciones | ≈ 0,42 |
| Tripleta 20.000 | Los tres números | ≈ 0,12 |

La quiniela directa es la modalidad que menos pierde.

## 3. Prueba de sesgo en Leidsa (chi-cuadrado, 100 números por posición)

| Período | Posición | chi² (azar ≈ 99) | p | Más salido |
|---|---|---|---|---|
| 2019–2026 (2.751) | 1.ª | 88,0 | 0,78 | 63: 1,56 % |
| 2019–2026 | 2.ª | 115,8 | 0,12 | 51: 1,49 % |
| 2019–2026 | 3.ª | 128,7 | 0,02 | 74: 1,49 % |
| 2010–2018 (3.085) | 1.ª | 443,3 | ≈ 0 | 36: 2,85 % |
| 2010–2018 | 2.ª | 439,2 | ≈ 0 | 17: 2,85 % |
| 2010–2018 | 3.ª | 392,7 | ≈ 0 | 52: 2,66 % |

- **2019–2026 es compatible con azar.** La 3.ª posición (p = 0,02) no es significativa al corregir por
  las tres pruebas. Aun eligiendo el mejor número *conociendo el resultado de antemano*, devuelve 1,069 por
  peso, y elegirlo antes de tiempo no funciona (las búsquedas de estrategias pierden en este período).
- **2010–2018 no es azar:** frecuencias de hasta 2,85 % (lo normal es 1 %). O los sorteos de esos años
  tenían un sesgo real, o los datos de esa fuente (miresultadoloteria.com, sin otra fuente para verificar,
  con 16 días que repiten el sorteo anterior) están mal. Por eso las estrategias de "frecuencia" ganaron en
  2010–2018 y pierden desde 2019. **No usar 2010–2018 para elegir estrategias.**

## 4. Las únicas formas reales de retorno positivo

1. Un sesgo físico demostrado en sorteos recientes (no hay evidencia en 2019–2026).
2. Una banca que pague más que la suma 100 (por ejemplo 70/15/15) — no se conoce ninguna.
3. Bonos, promociones o reembolsos de bancas en línea.

## 5. Próximo paso decidido

Agregar a la app, para Leidsa, los sistemas Transición, Ciclo vencido, Terminaciones/decenas y Ensamble,
y probarlos eligiendo con un período y confirmando con otro, empezando por 2019–2026.

## 6. Formas de apostar (staking) y qué se puede aprender de Stake.com

Fecha: 2026-11-24. Fuentes: `gh search repos --topic martingale|betting-strategy` y help.stake.com
(stake.com responde 403 de Cloudflare a clientes automáticos; se leyó su centro de ayuda).

### Sistemas de apuesta conocidos

| Sistema | Regla | Qué hace con el riesgo |
|---|---|---|
| Plana (ya en la app) | Siempre el mismo monto | Pérdida lenta y pareja |
| Escalera (ya en la app) | Sube tras fallar, vuelve al inicio al acertar | Parecido a una martingala suave |
| Audaz (ya en la app) | Lo justo para llegar a la meta de un golpe | Pocas pérdidas grandes |
| Martingala | Duplica tras perder | Ganancias chicas, quiebra rara pero total |
| Paroli (martingala inversa) | Duplica tras ganar, vuelve al inicio al perder | Pérdidas chicas, ganancias en rachas |
| D'Alembert | +1 unidad tras perder, −1 tras ganar | Martingala más lenta |
| Fibonacci | Sube según la serie 1,1,2,3,5… tras perder | Intermedio |
| Labouchère | Tacha números de una lista al ganar | Variante de martingala |
| Oscar's Grind | Busca +1 unidad por ciclo | Muy lenta, pocas quiebras |
| Kelly | Apuesta una fracción proporcional a la ventaja | Con ventaja negativa indica **no apostar** |

Ningún sistema cambia lo que devuelve cada peso apostado: si el juego paga 0,72 por peso, todos pierden
28 % de lo que apuestan; solo cambian cuándo y cuánto de golpe.

### GitHub

Los repositorios más populares son bots de casino (Aviator, Bloxflip con martingala, Binary.com) sin
evidencia de ganancia, y bots de **arbitraje** (Polymarket ↔ Kalshi, casas de apuestas deportivas). El
arbitraje es la única ganancia sin riesgo documentada, pero necesita **dos operadores que paguen distinto
por el mismo resultado**; con una sola lotería no aplica.

### Stake.com

- **Ventaja de la casa:** su centro de ayuda llama "house edge" al porcentaje que se queda la casa. La
  quiniela 60/8/4 se queda el **28 %**; un juego de casino típico entre 1 % y 5 %.
- **Rakeback:** devuelve 3,5 % de la ventaja de la casa (ej. sobre 1 BTC apostado en un juego de 2 % de
  ventaja: 0,0007 BTC). No cambia el signo del resultado.
- **Límites de pérdida y de apuesta** diarios, semanales y mensuales, con 24 h de espera para subirlos.
- **Juego demostrablemente justo** (provably fair): cada resultado se puede verificar; en Leidsa no.

### Lo aplicable a la app

1. Agregar Martingala, Paroli, D'Alembert, Fibonacci y Oscar's Grind como estilos de apuesta, para
   compararlos con los mismos datos.
2. Agregar **límite de pérdida y límite de ganancia** por día, semana o mes (stop-loss / stop-win), como
   hace Stake; reduce el tamaño de las pérdidas, no la pérdida esperada.
3. Mostrar en cada resultado el **retorno por peso apostado** y la ventaja de la casa, para que se vea que
   ronda 0,72.
