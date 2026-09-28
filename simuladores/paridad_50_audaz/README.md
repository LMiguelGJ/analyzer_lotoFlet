# Paridad · 50 números · audaz

El consenso par/impar causal (`parity`) observa **todo** el historial anterior, incluso sorteos sin ranking seleccionado, y elige los 50 números de la paridad preferida; liquida ese conjunto en cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 50)), floor(saldo/50))` pesos **por número**; mínimo RD$1 cada uno, costo total `50 × apuesta`, inicialmente RD$1.350 (RD$27 por número).

Fila esperada: **12.698 metas / 20.404 completas (62,2%)**, 7.706 quiebres, neto medio **−RD$120,8** sobre completas. El script la recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/paridad_50_audaz/ejecutar.py`.

Una sesión comienza con RD$2.000 y abarca varios sorteos apostados; quiebre significa no poder financiar la próxima apuesta, no siempre saldo cero. Neto medio no garantiza ganancia. La cola inconclusa se excluye de tasas/medias de completas, se incluye en totales de ventana. Huecos sin ranking no reciben apuestas ni reinician sesión; folds tampoco. Contrafactual histórico de datos reutilizados, censura y selección retrospectiva; no pronóstico.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
