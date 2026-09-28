# Paridad · 50 números · plana

El consenso par/impar causal (`parity`) observa todo el historial anterior, incluso sorteos sin ranking evaluable, y elige los 50 números de la paridad preferida; liquida ese conjunto en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Apuesta plana: **RD$1 por cada número**, mínimo RD$1 por número, costo total fijo RD$50 por sorteo (`50 × 1`), hasta meta o quiebre.

Fila esperada: **13 metas / 91 completas (14,3%)**, 78 quiebres, neto medio **−RD$1.572,8** sobre completas. El script recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/paridad_50_plana/ejecutar.py`.

Una sesión empieza con RD$2.000 y dura varios sorteos apostados; no equivale a un sorteo. Quiebre es no poder financiar los siguientes RD$50, aunque pueda quedar saldo. Neto medio no es ganancia garantizada. La cola inconclusa se excluye de tasas/medias de completas, pero entra en totales de ventana. Huecos sin ranking no reciben apuestas ni reinician sesiones; folds tampoco. Contrafactual histórico con datos reutilizados, censura y selección retrospectiva; no pronóstico.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
