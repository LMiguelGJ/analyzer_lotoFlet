# Selector automático · 1 número · audaz

El selector interpretable archivado (`select_interpretable`) elige un ranking usando solo información previa; se apuesta a su primer número (`k=1`). Cobra pagos acumulados en las cinco posiciones. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 1)), floor(saldo/1))` por número, mínimo RD$1; costo total `1 × apuesta`, inicialmente RD$11.

Fila esperada: **663 metas / 946 completas (70,1%)**, 283 quiebres, neto medio **−RD$8,2** sobre completas; la ejecución lo calcula nuevamente.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/selector_1_audaz/ejecutar.py`.

Sesión no equivale a sorteo: reinicia con RD$2.000 solo después de llegar a meta o no poder financiar la próxima apuesta (quiebre, posiblemente con saldo remanente). El neto medio no garantiza ganancias. La cola inconclusa no entra en medias ni tasas de completas, sí en totales de ventana; huecos sin ranking no reciben apuestas, sin reinicio por fold. Contrafactual histórico reutilizado y selección retrospectiva: censura y falta de pronóstico futuro.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no es un script autónomo. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
