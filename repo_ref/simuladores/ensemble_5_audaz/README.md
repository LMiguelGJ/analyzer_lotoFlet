# Ensemble · 5 números · audaz

El ranking exportado `ensemble` combina modelos causales; se toman sus primeros cinco números distintos y se cobra el mismo conjunto en las cinco posiciones (pagos acumulados). Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 5)), floor(saldo/5))` pesos **por cada número**; mínimo RD$1 cada uno, costo total `5 × apuesta`, inicialmente RD$55 (RD$11 por número).

Fila esperada: **3.226 metas / 4.720 completas (68,3%)**, 1.494 quiebres, neto medio **−RD$51,2** sobre completas. El script recalcula el resultado.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/ensemble_5_audaz/ejecutar.py`.

Una sesión arranca con RD$2.000 y puede contener varios sorteos apostados; quiebra si no puede financiar la siguiente apuesta, aunque pueda quedar saldo. Neto medio no es ganancia garantizada. La sesión final inconclusa queda fuera de tasas/medias de completas y dentro de totales de ventana. No se apuesta en huecos sin ranking ni se reinicia al cambiar de fold. Es contrafactual histórico de datos reutilizados, con censura y selección retrospectiva; no predicción futura.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no sirve copiar solo este script. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
