# Transición · 1 número · audaz

Este ejecutable reproduce una simulación histórica: **selecciona un número por sorteo a partir del ranking de transición guardado y recalcula cuánto apostar para pasar de RD$2.000 a RD$2.800 o más**. No pronostica el próximo sorteo en vivo ni realiza apuestas reales.

Resultado esperado con los insumos originales: **681 metas / 963 sesiones completas (70,7%)**, 282 quiebres y neto medio **+RD$10,3** sobre sesiones completas. El resultado se recalcula; no se imprime como una constante.

## Cómo ejecutarlo

Desde esta carpeta:

```powershell
py -B ejecutar.py
```

Desde la raíz del repositorio:

```powershell
py -B simuladores/transicion_1_audaz/ejecutar.py
```

También funciona `py ejecutar.py`; `-B` evita crear caché de bytecode. No hay que ingresar números ni montos: el escenario está fijado para reproducir la tabla (`transition`, `k=1`, `bold`, modo `all`, capital 2000, meta 2800).

## Entradas: qué necesita para funcionar

Las rutas siguientes son relativas a la raíz del repositorio, no a esta carpeta:

| Entrada | Función |
|---|---|
| `chance_express_history.json` | Fechas, horas y los cinco números que salieron en cada sorteo. Indica qué ocurrió. |
| `repo_ref/reports/chance_rank_v1/predictions/pos1.npz` | Rankings históricos congelados y sus filas, fechas y cortes de información. Indica qué habría elegido el método antes de cada resultado evaluado. |
| `simuladores/runner.py` | Verifica los hashes, carga entradas, ejecuta un escenario y muestra el resumen. |
| `quiniela_compare.py` y `quiniela_sim.py` | Motor de selección archivada, apuestas, pagos, sesiones y métricas; reutiliza también módulos de `repo_ref/`. |

Necesita el repositorio completo y el entorno Python/NumPy existente. No es un script autónomo para copiar fuera de esta estructura. Las rutas se resuelven desde el archivo del ejecutable, no desde el directorio actual.

El runner comprueba los SHA-256 fijados del JSON y del NPZ antes de cargarlos. Si falta una entrada o cambia su contenido, termina con un error: no presenta una corrida distinta como reproducción idéntica.

### Cómo aparece un sorteo en el JSON

Fragmento ilustrativo del registro real usado en la primera apuesta:

```json
{
  "sorteos_por_fecha": {
    "2025-09-02": [
      {
        "hora": "05:10",
        "numeros": ["90", "66", "90", "32", "31"],
        "source_url": "https://premios.do/resultados-chance-express-2025-09-02"
      }
    ]
  }
}
```

El archivo completo tiene más fechas/registros y una sección `metadata`. Los cinco números representan primera, segunda, tercera, cuarta y quinta posición. El cargador valida y normaliza los registros en orden cronológico.

## Dónde comienza a apostar

La primera apuesta evaluada corresponde al **2 de septiembre de 2025 a las 05:10**. Su ranking declara corte de información a las **05:05** de ese día.

El historial completo tiene 105.426 sorteos, pero esta reproducción apuesta solo en las **65.235 filas con rankings disponibles**, hasta el 25 de septiembre de 2026 a las 18:20. Los sorteos anteriores no se apuestan en este replay; pertenecen al contexto histórico del estudio que generó los rankings.

La primera fila evaluada tiene `row_id = 33648`, un índice basado en cero del historial normalizado. **No es un número oficial de sorteo.**

Los huecos sin ranking no reciben apuesta. El saldo continúa entre filas evaluables, días y folds; no se reinicia por esos límites.

## Qué hace en cada apuesta

1. Toma el primer número de `ranking100__transition` para la fila evaluada. El número puede cambiar en cada sorteo.
2. Calcula la apuesta audaz usando el saldo anterior al sorteo.
3. Consulta las cinco posiciones reales del JSON y calcula el premio.
4. Descuenta la apuesta y suma lo cobrado.
5. Termina la sesión si el saldo alcanza RD$2.800 o más, o si se agota; en otro caso continúa.

La apuesta por número es:

```text
mínimo(redondear_hacia_arriba((2800 − saldo) / 79), saldo)
```

Se apuesta a **un único número**, con pesos enteros y mínimo RD$1 cuando el saldo permite continuar. El divisor es 79 porque un primer premio de 80 deja 79 netos después de descontar el peso apostado.

El modo `all` aplica premios **80/8/4/2/1** por peso en las cinco posiciones. Si el número elegido aparece varias veces, se suman los premios correspondientes. No se incluyen impuestos ni comisiones.

**Se reutiliza la selección histórica archivada; se recalculan apuestas, premios y saldos.** El ejecutable no vuelve a entrenar transición, ni usa el resultado objetivo del JSON para elegir el número de esa apuesta. El JSON por sí solo no alcanza para reproducir la selección: también necesita el NPZ compatible.

## Primera sesión real: del inicio al objetivo

La siguiente traza se obtuvo con los insumos originales y las mismas funciones de liquidación del motor, mediante una inspección acotada de solo lectura. Todos los eventos son del **2025-09-02**. La tabla muestra eventos seleccionados, no las 60 apuestas completas.

| Apuesta | Hora | Elegido | Resultados reales, posiciones 1–5 | Saldo anterior | Apostó | Cobró | Saldo posterior |
|---:|---|---:|---|---:|---:|---:|---:|
| 1 | 05:10 | 78 | 90 · 66 · 90 · 32 · 31 | RD$2.000 | RD$11 | RD$0 | RD$1.989 |
| 2 | 05:15 | 34 | 01 · 60 · 45 · 18 · 80 | RD$1.989 | RD$11 | RD$0 | RD$1.978 |
| 3 | 05:20 | 12 | 69 · 95 · 74 · 06 · 17 | RD$1.978 | RD$11 | RD$0 | RD$1.967 |
| 14 | 06:25 | 38 | 75 · 17 · 38 · 03 · 91 | RD$1.851 | RD$13 | RD$52 | RD$1.890 |
| 60 | 10:55 | 80 | 80 · 07 · 27 · 39 · 36 | RD$1.538 | RD$16 | RD$1.280 | **RD$2.802** |

### Primer cobro: apuesta 14

El **38 salió tercero**, por lo que pagó 4 por peso:

```text
Cobro = 13 × 4 = RD$52
Saldo = 1.851 − 13 + 52 = RD$1.890
```

Fue un acierto, pero no alcanzó la meta. La sesión continuó.

### Primer acierto en primera posición y fin de sesión: apuesta 60

El **80 salió primero**:

```text
Cobro = 16 × 80 = RD$1.280
Saldo = 1.538 − 16 + 1.280 = RD$2.802
Ganancia de la sesión = 2.802 − 2.000 = RD$802
```

Esta sesión llegó a la meta en 60 apuestas. Desde las 05:10 hasta las 10:55 transcurrieron **5 horas y 45 minutos**; no se apostó en todos los registros del tramo porque existen filas sin ranking.

La siguiente sesión empieza en el siguiente sorteo evaluable con **RD$2.000 nuevos de capital inicial**, no con RD$2.802. Las sesiones son escenarios reiniciados: no representan miles de intentos financiados con un solo depósito de RD$2.000.

## Salida normal del programa

El ejecutable muestra un resumen en la terminal, no la traza apuesta por apuesta de la sección anterior. Estas son las líneas principales esperadas:

```text
Sistema: transition; k: 1; Apuesta: bold; Modo: all
Capital: RD$2000; meta de saldo: RD$2800
Completas: 963; Inconclusas: 1; Sesiones iniciadas: 964
Meta: 681/963 (70.7%)
Quiebre: 282/963 (29.3%)
Wilson 95% descriptivo (meta, completas): 67.8%–73.5%
Neto medio: RD$+10.3; Saldo final medio: RD$2010.3
Mediana/p90 de sorteos apostados por sesión completa: 66.0/118.0
```

También imprime rutas, hashes, población evaluada, totales de ventana y advertencias. La consola usa punto decimal; este README usa coma decimal en la prosa.

| Campo | Cómo interpretarlo |
|---|---|
| Completas | Sesiones terminadas en meta o quiebre; no cantidad de sorteos. |
| Inconclusas | Sesiones abiertas cuando se acabaron los datos. |
| Meta | 681 de 963 completas alcanzaron RD$2.800 o más. |
| Quiebre | En esta audaz de un número, 282 sesiones agotaron el saldo. En otras estrategias puede quedar dinero insuficiente para la siguiente apuesta. |
| Neto medio +RD$10,3 | Promedio de ganancias y pérdidas de las sesiones completas; no ganancia fija por intento. |
| Saldo final medio | RD$2.000 más el neto medio: RD$2.010,3. |
| Mediana 66 / p90 118 | Duración de sesiones completas en sorteos apostados, no tiempo calendario ni límite máximo. La primera sesión de 60 apuestas es solo una de ellas. |
| Wilson 95% | Intervalo descriptivo de la tasa histórica; no corrige por selección entre muchas estrategias ni garantiza independencia. |

La cola inconclusa queda fuera de las tasas y medias de sesiones completas, pero entra en los totales de ventana. Por eso los totales no se reconstruyen simplemente multiplicando el neto medio redondeado por 963.

## Límites y reproducibilidad

- Repetir con el mismo código e insumos debe reproducir los mismos resultados: no se sortean nuevas selecciones en este escenario.
- No descarga sorteos, no elige un número para jugar hoy, no admite cambiar capital/meta y no guarda un informe automáticamente.
- La historia es Chance Express con pagos hipotéticos de Quiniela Extraordinaria; no valida reglas ni resultados de Rapidita.
- Los datos se reutilizaron y esta combinación destacó después de comparar muchas alternativas. El neto ligeramente positivo **no demuestra rentabilidad futura**.
- Las sesiones inconclusas y las diferencias de duración afectan la interpretación; el 70,7% no equivale a una probabilidad de alcanzar la meta dentro de una hora.

## Referencias

- [Resumen original](../../docs/resumen_resultados_quiniela.md)
- [Informe completo](../../docs/informe_quiniela_comparacion.md)
- [Reglas e índice de los 14 simuladores](../README.md)
