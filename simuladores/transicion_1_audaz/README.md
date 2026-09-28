# Transición · 1 número · audaz

Ordena números según transiciones observadas antes del sorteo; apuesta al primero del ranking congelado (`transition`, `k=1`, `bold`, pagos acumulados en cinco posiciones). Capital RD$2.000, meta RD$2.800. Audaz recalcula por sorteo `min(ceil((2800 − saldo)/(80 − 1)), floor(saldo/1))` pesos **por número**; mínimo RD$1, costo total `1 × apuesta`. Comienza con RD$11 en total.

Fila esperada: **681 metas / 963 completas (70,7%)**, 282 quiebres, neto medio **+RD$10,3** sobre completas. El script recalcula, no imprime esta fila como resultado fijo.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/transicion_1_audaz/ejecutar.py`.

Una sesión empieza con RD$2.000 y abarca varios sorteos apostados; no es un sorteo. Quiebre significa no poder financiar la siguiente apuesta prescrita (no necesariamente saldo cero en general); el neto medio no es ganancia garantizada. La última sesión inconclusa se excluye de tasas/medias de completas, pero se incluye en los totales de ventana. Los huecos sin ranking no reciben apuestas; las sesiones no se reinician entre folds. Es un contrafactual histórico con datos reutilizados, sesgo de selección y cola censurada, no pronóstico futuro.

Necesita el repositorio completo, motor Python/NumPy, JSON y NPZ compartidos: no es autónomo para copiar fuera. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Reglas e índice](../README.md).
