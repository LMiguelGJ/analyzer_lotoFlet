# Quiniela Extraordinaria 80/8/4/2/1 — simulación retrospectiva

## 1. Alcance y advertencias

Capital RD$2,000; meta RD$2,800; historial de 105,426 sorteos. El historial es Chance Express: contrafactual para Q80, no datos verificados de Rapidita. No es una predicción ni una recomendación de juego. Se suponen premios 80/8/4/2/1 por peso, sin comisiones ni impuestos.

## 2. Tabla principal (modo all)

| Fuente | Estrategia | Sesiones completas | Meta | IC Wilson 95 % | Quiebre | Neto medio (RD$) | Apostado medio (RD$) | Apostado total (RD$) | Retorno/peso | Sorteos mediana / p90 | Inconclusas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Historial | Paridad Markov (50) | 146 | 8.2 % | 4.8 % – 13.8 % | 91.8 % | -1,739.4 | 36,064.4 | 5,265,400.0 | 0.9518 | 619.5 / 1,299.5 | 1 |
| Historial | Azar 50 | 143 | 4.9 % | 2.4 % – 9.8 % | 95.1 % | -1,832.8 | 36,631.5 | 5,238,300.0 | 0.9500 | 637.0 / 1,279.2 | 1 |
| Historial | Escalera paridad | 5663 | 38.7 % | 37.4 % – 40.0 % | 61.3 % | -132.1 | 2,720.6 | 15,406,500.0 | 0.9515 | 20.0 / 29.0 | 1 |
| Historial | Audaz aleatoria | 1567 | 69.9 % | 67.6 % – 72.1 % | 30.1 % | -15.6 | 1,222.8 | 1,916,155.0 | 0.9873 | 67.0 / 119.0 | 1 |
| Montecarlo | Plana (50) | 20000 | 8.3 % | 8.0 % – 8.7 % | 91.7 % | -1,737.2 | 34,898.7 | 697,973,200.0 | 0.9502 | 620.0 / 1,209.0 | 0 |
| Montecarlo | Escalera (50) | 20000 | 38.3 % | 37.6 % – 38.9 % | 61.7 % | -138.7 | 2,698.9 | 53,978,500.0 | 0.9486 | 20.0 / 29.0 | 0 |
| Montecarlo | Audaz (1) | 20000 | 68.5 % | 67.9 % – 69.2 % | 31.5 % | -53.4 | 1,242.2 | 24,843,143.0 | 0.9570 | 68.0 / 119.0 | 0 |

## 3. Sensibilidad (modo best)

| Fuente | Estrategia | Sesiones completas | Meta | IC Wilson 95 % | Quiebre | Neto medio (RD$) | Apostado medio (RD$) | Apostado total (RD$) | Retorno/peso | Sorteos mediana / p90 | Inconclusas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Historial | Paridad Markov (50) | 156 | 9.0 % | 5.4 % – 14.5 % | 91.0 % | -1,720.0 | 33,761.5 | 5,266,800.0 | 0.9491 | 566.5 / 1,212.0 | 1 |
| Historial | Azar 50 | 155 | 7.1 % | 4.0 % – 12.3 % | 92.9 % | -1,773.2 | 33,593.9 | 5,207,050.0 | 0.9472 | 632.0 / 1,088.4 | 1 |
| Historial | Escalera paridad | 5626 | 38.3 % | 37.0 % – 39.6 % | 61.7 % | -140.0 | 2,738.4 | 15,406,500.0 | 0.9489 | 20.0 / 29.0 | 1 |
| Historial | Audaz aleatoria | 1568 | 69.8 % | 67.5 % – 72.1 % | 30.2 % | -18.7 | 1,221.7 | 1,915,655.0 | 0.9847 | 67.0 / 118.0 | 1 |
| Montecarlo | Plana (50) | 20000 | 7.3 % | 7.0 % – 7.7 % | 92.7 % | -1,764.9 | 33,529.7 | 670,593,100.0 | 0.9474 | 596.0 / 1,154.0 | 0 |
| Montecarlo | Escalera (50) | 20000 | 37.9 % | 37.2 % – 38.6 % | 62.1 % | -144.6 | 2,729.9 | 54,597,650.0 | 0.9470 | 20.0 / 29.0 | 0 |
| Montecarlo | Audaz (1) | 20000 | 68.2 % | 67.5 % – 68.8 % | 31.8 % | -65.3 | 1,259.3 | 25,185,473.0 | 0.9482 | 71.0 / 119.0 | 0 |

## 4. Glosario

Sesiones completas: meta o quiebre; la última sesión histórica sin desenlace queda inconclusa y se excluye de tasas y promedios. Meta y quiebre: fracciones de sesiones completas. IC Wilson 95 %: intervalo descriptivo de la fracción de meta; en historial usa una aproximación de independencia, sin garantizar que los sorteos sean IID. Neto medio: saldo final menos capital, con signo. Apostado medio: promedio por sesión completa; apostado total: suma sobre sesiones completas. Retorno/peso: pagos totales divididos por apuestas totales, no beneficio neto. Sorteos mediana/p90: duración de sesiones completas. Quiebre significa no poder financiar la próxima apuesta prescrita (en audaz, saldo agotado); puede quedar saldo, no necesariamente bancarrota total.

## 5. Lectura de los resultados

Se computaron 135024 sesiones completas entre todas las filas y modos (no son sesiones únicas entre estrategias), y 8 colas históricas inconclusas entre las filas y modos. Las tasas y los importes de cada fila están arriba; las colas censuradas pueden sesgar la comparación histórica. No extrapolar la muestra histórica como garantía de resultados futuros.

## 6. Supuestos y trazabilidad [A1]–[T2]

- [A1] Q80 usa premios 80/8/4/2/1 para posiciones 1–5; all suma posiciones repetidas y best paga solo la mejor posición por número.
- [A2] Plana y control apuestan un peso a 50 números; escalera usa 1, 2, 6, 16… por número y reinicia al cubrir el primer premio. Cuatro rondas financiables describen solo la trayectoria de pérdidas totales desde RD$2.000, no un límite universal con premios secundarios.
- [A3] Audaz elige un número y apuesta el mínimo entre saldo y ceil((meta − saldo)/79). La meta se evalúa después de cada sorteo.
- [T1] Historial cronológico validado; Markov arranca vacío, emite 27 votos antes de actualizar con el sorteo actual. No se mezcla JSON legado sin fecha. Paridad y selecciones azar 50/audaz se generan una vez con semillas 20260929/20260930 y se reutilizan entre all/best.
- [T2] MC genera cinco posiciones uniformes independientes (se admiten repeticiones). Cobertura fija par o número 0: bajo sorteos IID uniformes la cobertura fija tiene la misma distribución que otra cobertura igual, no los mismos resultados en una muestra. Semilla base 20260928; flat all/best usa +0/+1, ladder +2/+3, bold +4/+5. Sin ajuste de semillas según los resultados.
