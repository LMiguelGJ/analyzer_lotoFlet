# Quiniela Extraordinaria: resultados históricos y cómo interpretarlos

Resumen de combinaciones seleccionadas para intentar pasar de **RD$2.000 a RD$2.800 o más**. La tabla reproduce los resultados solicitados por el usuario, con **pagos acumulados**. No es la lista completa ni un ranking ordenado de todas las alternativas.

> Son apuestas simuladas sobre resultados históricos de Chance Express con pagos hipotéticos de Quiniela Extraordinaria. No son apuestas realizadas, resultados verificados de Rapidita ni una garantía de ganancias futuras.

## Tabla solicitada — pagos acumulados

| Método | Números | Apuesta | Llegaron / completas | Meta | Quiebres | Neto medio RD$ |
|---|---:|---|---:|---:|---:|---:|
| Transición | 1 | Audaz | 681 / 963 | 70,7% | 282 | +10,3 |
| Fríos | 1 | Audaz | 684 / 974 | 70,2% | 290 | −3,4 |
| Selector automático | 1 | Audaz | 663 / 946 | 70,1% | 283 | −8,2 |
| Mezclas | 1 | Audaz | 676 / 968 | 69,8% | 292 | −15,6 |
| Ensemble | 5 | Audaz | 3.226 / 4.720 | 68,3% | 1.494 | −51,2 |
| Ensemble | 10 | Audaz | 6.140 / 9.061 | 67,8% | 2.921 | −56,9 |
| Ensemble | 20 | Audaz | 10.785 / 16.086 | 67,0% | 5.301 | −59,2 |
| Fríos | 25 | Escalera | 677 / 1.105 | 61,3% | 428 | −162,2 |
| Mezclas | 50 | Audaz | 12.845 / 20.605 | 62,3% | 7.760 | −117,0 |
| Transición | 50 | Audaz | 12.890 / 20.682 | 62,3% | 7.792 | −116,0 |
| Tu par/impar | 50 | Audaz | 12.698 / 20.404 | 62,2% | 7.706 | −120,8 |
| Fríos | 50 | Escalera | 1.429 / 3.502 | 40,8% | 2.073 | −98,7 |
| Tu par/impar | 50 | Escalera | 1.368 / 3.496 | 39,1% | 2.128 | −124,4 |
| Tu par/impar | 50 | Plana | 13 / 91 | 14,3% | 78 | −1.572,8 |

## Qué significa cada columna

| Columna | Interpretación |
|---|---|
| Método | Regla que elige los números antes del siguiente resultado. No es la regla que decide cuánto apostar. |
| Números | Cantidad de números distintos cubiertos en cada sorteo; la selección puede cambiar entre sorteos. |
| Apuesta | Forma de calcular el importe por número: plana, escalera o audaz. |
| Llegaron / completas | Sesiones que alcanzaron al menos RD$2.800, divididas por sesiones terminadas en meta o quiebre. No cuenta sorteos ni simples aciertos. |
| Meta | Porcentaje de sesiones completas que alcanzaron la meta, redondeado a un decimal. No es una probabilidad futura garantizada. |
| Quiebres | Número de sesiones terminadas por no poder financiar la siguiente apuesta prescrita. Puede quedar saldo; con audaz a un número, el saldo se agota. |
| Neto medio | Promedio de saldo final menos RD$2.000 sobre sesiones completas, incluyendo ganadoras y perdedoras. Positivo es ganancia observada; negativo es pérdida observada. |

**Saldo final medio = RD$2.000 + neto medio.** Los porcentajes redondeados pueden coincidir aunque las tasas exactas difieran; no desempatar candidatos usando solo el porcentaje mostrado.

## Qué es una sesión

1. Arranca con RD$2.000 y sin deuda ni aportes durante esa sesión.
2. Apuesta en los sorteos evaluables, con mínimo RD$1 por número y sin superar el saldo.
3. Continúa hasta llegar a RD$2.800 o más, o hasta no poder financiar la siguiente apuesta según su regla. No tiene límite temporal de juego.
4. La siguiente sesión arranca de nuevo con RD$2.000 en el siguiente sorteo disponible, sin reutilizar los sorteos de la anterior dentro de esa combinación.

**No son miles de sesiones financiadas por un único depósito de RD$2.000.** Cada reinicio representa un nuevo escenario con capital inicial propio. Tampoco son muestras independientes entre métodos: todas las combinaciones reutilizan el mismo tramo histórico.

Las estrategias tienen duraciones distintas y, por eso, completan cantidades distintas de sesiones en el mismo historial. Las sesiones inconclusas al terminar los datos se excluyen de esta tabla de tasas y medias; el informe completo muestra sus conteos y los totales de ventana que sí las incluyen. Esta censura puede sesgar la comparación de sesiones completas.

## Pagos y reglas de apuesta

### Pagos acumulados

Se aplican premios **80 / 8 / 4 / 2 / 1** por peso apostado, para las posiciones primera a quinta. Son importes brutos cobrados: la apuesta se descuenta por separado.

El mismo conjunto seleccionado se cobra contra las cinco posiciones. Si un número aparece repetido en varias posiciones, cada aparición paga en esta modalidad. Sin comisiones ni impuestos. La sensibilidad que paga solo el mejor premio por número está en el informe completo, no en esta tabla.

### Plana

RD$1 a cada uno de los `k` números: gasto total de `k` pesos por sorteo. Para 50 números, RD$50.

### Escalera

Se calcula una escalera de diez rondas para cada cobertura, con objetivo de recuperar los costos de las rondas previas más RD$10 cuando se cubre el primer premio. Para 50 números comienza en **1, 2, 6, 16, 42… pesos por número**.

- Si se cubre el primer puesto, reinicia en la primera ronda.
- Los premios secundarios suman saldo, pero no reinician la ronda.
- Si no se cubre el primero, avanza; tras la décima ronda perdida, vuelve a la primera según la regla evaluada.
- Si no alcanza para la próxima ronda completa, termina en quiebre de la estrategia, aunque quede dinero.

### Audaz adaptada a la cobertura

Con saldo `B`, meta `G` y `k < 80` números, la apuesta entera **por número** es:

```text
b = mínimo(redondear_hacia_arriba((G − B) / (80 − k)), piso(B / k))
Gasto total = k × b
```

La fórmula busca que un primer premio alcance la meta, descontando el costo de cubrir los `k` números. Si no alcanza el capital para ese importe, apuesta lo máximo financiable por número. Termina cuando el saldo es menor que `k`; no se permiten apuestas fraccionarias menores de RD$1 por número. Se recalcula después de cada sorteo y también cobra premios secundarios.

| Ejemplo inicial | Apuesta por número | Costo total | Saldo si solo acierta el primero |
|---|---:|---:|---:|
| 1 número | RD$11 | RD$11 | 2.000 − 11 + 880 = **RD$2.869** |
| 50 números | RD$27 | RD$1.350 | 2.000 − 1.350 + 2.160 = **RD$2.810** |

**Nunca se repartieron RD$11 entre 50 números.** La audaz de un número y la audaz de 50 son escenarios diferentes.

## Ejemplo explicado: transición + 1 número + audaz

- Se completaron **963 sesiones**, cada una iniciada con RD$2.000.
- **681** alcanzaron al menos RD$2.800: **70,7%**.
- **282** agotaron los RD$2.000: **29,3%**.
- Hubo además **una sesión histórica inconclusa**, fuera de esos 963 desenlaces.
- El neto medio de las sesiones completas fue **+RD$10,3**; el saldo final medio, **RD$2.010,3**.
- La duración mediana de las sesiones completas fue **66 sorteos apostados**, no 66 sesiones ni necesariamente 66 sorteos consecutivos del calendario.

El promedio +RD$10,3 **no significa que cada sesión ganó esa cantidad**: unas ganaron RD$800 o más y otras perdieron RD$2.000. El promedio combina ambos resultados. Los totales de ventana del informe incluyen también la cola inconclusa, por lo que no se reconstruyen multiplicando este promedio redondeado por 963.

Transición usa información de resultados anteriores para ordenar candidatos. Su primer número del ranking es el seleccionado en cada sorteo de este escenario. No se eligió usando el resultado del sorteo que se iba a apostar.

## Datos y alcance de la comparación

- Historial original: **105.426 sorteos de Chance Express**.
- Población común de esta comparación: **65.235 sorteos con rankings disponibles**, del **2025-09-02 05:10** al **2026-09-25 18:20**, distribuidos en 14 folds cronológicos.
- Hay **6.543 filas históricas no seleccionadas dentro de ese tramo**. No se apuesta en ellas; saldo y ronda continúan. Las duraciones cuentan sorteos apostados, no tiempo calendario.
- Los rankings de primera posición se usan para elegir un único conjunto top-k, liquidado contra las cinco posiciones. Se conserva el orden exportado de desempate.
- Par/impar reproduce el consenso causal de 27 votos del legado: tres votos por cada orden del 1 al 9, usando datos anteriores. Solo se evaluó con su cobertura original de 50 números.
- Comparación total: 13 sistemas de ranking, coberturas 1, 5, 10, 20, 25, 30, 40 y 50; tres apuestas; control al azar y paridad. Dos modalidades de pago.
- Informe completo: **678 filas históricas y 48 filas Monte Carlo**, más diez líderes repetidos como resumen. Esta tabla contiene solo las 14 combinaciones solicitadas.

Los resultados anteriores de `informe_quiniela_sim.md` usaban otra población histórica. No deben mezclarse directamente con los de este resumen.

## Qué podemos concluir y qué no

**Lo observado:** transición + audaz a un número tuvo la mayor tasa histórica de meta de la comparación principal y un neto medio ligeramente positivo. Muchas alternativas llegaron frecuentemente a la meta y aun así tuvieron pérdida media: ganar más sesiones que perder no garantiza ganar dinero, porque los importes son distintos.

**Lo no demostrado:** que ese ganador histórico mantenga rentabilidad, que sea la mejor estrategia posible o que su 70,7% sea una probabilidad futura estable. Los datos ya se habían examinado y se compararon muchas alternativas; seleccionar la mejor después de observar los resultados introduce sesgo de selección. No hay un holdout intacto ni una validación prospectiva independiente.

La tabla no muestra intervalos de incertidumbre; están en el informe completo. En transición/1/audaz, el intervalo Wilson descriptivo de meta es **67,8%–73,5%**. No corrige selección entre muchas estrategias ni garantiza independencia histórica.

Como referencia separada, en sorteos artificiales uniformes la audaz de 50 números alcanzó la meta en **12.303 de 20.000 sesiones (61,5%)**, con neto medio **−RD$142,1**. Bajo esos supuestos, el retorno teórico acumulado es RD$0,95 por peso apostado, no un beneficio positivo. Monte Carlo comprueba apuesta y cobertura bajo su modelo; no valida por sí solo una ventaja predictiva de los métodos históricos.

## Fuentes, reproducción y verificación

- [Informe completo generado](informe_quiniela_comparacion.md): conteos, intervalos, saldos, duración, totales de ventana, modalidades y semillas.
- [Comparador](quiniela_compare.py) y [pruebas](test_quiniela_compare.py).
- [Seguimiento ODD](odd/tasks/quiniela-sim.md).
- Rankings: `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`.
- SHA-256 del historial: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`.
- SHA-256 de rankings: `b405041fff1f45fe24fd9ab09fed2c6709e979576811c703e7d27e57f3ded94d`.

Comando para repetir la comparación, usando un nombre de salida que todavía no exista:

```bash
py -B quiniela_compare.py --capital 2000 --meta 2800 --mc-sessions 20000 --report informe_quiniela_nueva_corrida.md
```

La implementación pasó **58 pruebas y Ruff**, con revisión independiente. La revisión del artefacto comprobó aritmética, conteos y los rankings binarios; **no regeneró íntegramente los resultados ni auditó de forma independiente toda la generación causal original**. Este documento es un resumen explicativo de esa corrida, no un experimento nuevo.
