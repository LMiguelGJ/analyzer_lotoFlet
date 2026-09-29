# Transición · 50 números · audaz

El ranking `transition` ordena por transiciones previas; selecciona los primeros 50 números distintos, liquidados en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 50)), floor(saldo/50))` pesos **por número**; mínimo RD$1 cada uno, costo total `50 × apuesta`, inicialmente RD$1.350 (RD$27 por número).

Fila esperada: **12.890 metas / 20.682 completas (62,3%)**, 7.792 quiebres, neto medio **−RD$116,0** sobre completas. El script la recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/transicion_50_audaz/ejecutar.py`.

Una sesión comienza con RD$2.000 y abarca varios sorteos apostados; quiebre significa no poder financiar la próxima apuesta, no necesariamente saldo cero. Neto medio no es ganancia garantizada. La cola inconclusa se excluye de tasas/medias de completas, pero se cuenta en totales de ventana. Huecos sin ranking no reciben apuesta ni reinician la sesión; tampoco los folds. Contrafactual histórico con datos reutilizados, censura y elección retrospectiva; no pronóstico futuro.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
