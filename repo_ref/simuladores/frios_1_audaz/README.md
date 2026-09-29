# Fríos · 1 número · audaz

El ranking `cold` prioriza números de baja frecuencia histórica previa; se selecciona el primero (`k=1`) antes de liquidar las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 1)), floor(saldo/1))` pesos por número, mínimo RD$1; costo total `1 × apuesta`, inicialmente RD$11.

Fila esperada: **684 metas / 974 completas (70,2%)**, 290 quiebres, neto medio **−RD$3,4** sobre completas. El script recalcula esta fila.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/frios_1_audaz/ejecutar.py`.

Una sesión comienza con RD$2.000 y puede abarcar muchos sorteos apostados; quiebre es no poder financiar la próxima apuesta (no necesariamente saldo cero en general). Neto medio de completas no es ganancia garantizada. La sesión final inconclusa se excluye de tasas/medias de completas, no de totales de ventana. Huecos sin ranking no reciben apuesta y folds no reinician sesiones. Contrafactual histórico con reutilización de datos, censura y selección retrospectiva; no pronóstico.

Requiere el repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; copiar este script solo no funciona. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
