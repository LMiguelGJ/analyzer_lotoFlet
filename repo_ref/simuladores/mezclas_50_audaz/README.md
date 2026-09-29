# Mezclas · 50 números · audaz

El ranking `mix` combina señales previas; selecciona sus primeros 50 números distintos y liquida ese conjunto en las cinco posiciones (pagos acumulados). Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 50)), floor(saldo/50))` pesos **por número**; mínimo RD$1 cada uno, costo total `50 × apuesta`, inicialmente RD$1.350 (RD$27 por número).

Fila esperada: **12.845 metas / 20.605 completas (62,3%)**, 7.760 quiebres, neto medio **−RD$117,0** sobre completas. La ejecución recalcula esta cifra.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/mezclas_50_audaz/ejecutar.py`.

Una sesión comienza con RD$2.000 y puede durar varios sorteos apostados; quiebra cuando no puede cubrir la siguiente apuesta, no siempre al llegar a saldo cero. Neto medio no es ganancia garantizada. La sesión final inconclusa se excluye de tasas/medias de completas, no de totales de ventana. Huecos sin ranking no reciben apuesta y folds no reinician sesiones. Contrafactual histórico reutilizado, censurado y seleccionado retrospectivamente; no predice el futuro.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
