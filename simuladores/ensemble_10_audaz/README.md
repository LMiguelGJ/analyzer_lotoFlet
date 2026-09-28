# Ensemble · 10 números · audaz

El ranking congelado `ensemble` combina modelos previos y selecciona sus primeros diez números distintos; el mismo conjunto se liquida en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Audaz recalcula `min(ceil((2800 − saldo)/(80 − 10)), floor(saldo/10))` pesos por número; mínimo RD$1 cada uno, costo total `10 × apuesta`, inicialmente RD$120 (RD$12 por número).

Fila esperada: **6.140 metas / 9.061 completas (67,8%)**, 2.921 quiebres, neto medio **−RD$56,9** sobre completas. Se recalcula, no se usa como entrada.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/ensemble_10_audaz/ejecutar.py`.

Una sesión arranca con RD$2.000 y abarca varios sorteos apostados; quiebre significa siguiente apuesta no financiable, no siempre saldo cero. Neto medio no garantiza ganancias. La cola inconclusa se excluye de tasas/medias de completas, pero cuenta en totales de ventana. Huecos sin ranking no reciben apuesta y folds no reinician sesiones. Contrafactual histórico reutilizado, censurado y elegido retrospectivamente; no pronóstico.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no es autónomo. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
