# Mezclas · 1 número · audaz

El ranking congelado `mix` combina señales previas para ordenar números y selecciona su primero (`k=1`); el mismo número se liquida en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 1)), floor(saldo/1))` por número, mínimo RD$1; costo total `1 × apuesta`, inicialmente RD$11.

Fila esperada: **676 metas / 968 completas (69,8%)**, 292 quiebres, neto medio **−RD$15,6** sobre completas. La ejecución recalcula la fila.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/mezclas_1_audaz/ejecutar.py`.

Sesión y sorteo no son lo mismo: una sesión empieza con RD$2.000 y continúa por múltiples sorteos apostados hasta meta o quiebre (siguiente apuesta no financiable, no siempre saldo cero). Neto medio no es ganancia garantizada. Cola inconclusa excluida de medias/tasas de completas pero incluida en totales de ventana; huecos sin ranking no reciben apuesta y folds no reinician sesiones. Contrafactual histórico reutilizado, censurado y seleccionado retrospectivamente; no predicción futura.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
