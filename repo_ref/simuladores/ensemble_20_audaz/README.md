# Ensemble · 20 números · audaz

El ranking exportado `ensemble` combina modelos causales y selecciona los primeros 20 números distintos; el mismo conjunto se liquida en las cinco posiciones (pagos acumulados). Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 20)), floor(saldo/20))` por número; mínimo RD$1 cada uno, costo total `20 × apuesta`, inicialmente RD$280 (RD$14 por número).

Fila esperada: **10.785 metas / 16.086 completas (67,0%)**, 5.301 quiebres, neto medio **−RD$59,2** sobre completas. El script recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/ensemble_20_audaz/ejecutar.py`.

Una sesión comienza con RD$2.000 y puede recorrer varios sorteos apostados; quiebre es no poder cubrir la próxima apuesta, no necesariamente saldo cero. Neto medio no garantiza ganancia. La última sesión inconclusa se excluye de tasas/medias de completas, pero se incluye en totales de ventana. No se apuesta en huecos sin ranking ni se reinicia por fold. Contrafactual histórico con reutilización de datos, censura y selección retrospectiva: no pronóstico.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
