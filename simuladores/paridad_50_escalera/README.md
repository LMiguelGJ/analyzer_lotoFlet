# Paridad · 50 números · escalera

El consenso par/impar causal (`parity`) observa todo el historial anterior, incluidos sorteos sin ranking evaluable, y elige los 50 números de la paridad preferida; los liquida en cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. Escalera de diez rondas: recupera costos previos más RD$10 al cubrir el primer premio; comienza RD$1 **por número**, costo total RD$50 (`50 × 1`); próximas rondas RD$2, RD$6, RD$16, RD$42 por número, costo `50 × importe de ronda`, mínimo RD$1 cada uno. Primer premio reinicia ronda; premios secundarios no. Si no puede financiar siguiente ronda, quiebra aunque quede saldo.

Fila esperada: **1.368 metas / 3.496 completas (39,1%)**, 2.128 quiebres, neto medio **−RD$124,4** sobre completas. Se recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/paridad_50_escalera/ejecutar.py`.

Una sesión comienza con RD$2.000 y puede durar muchos sorteos apostados; no equivale a un sorteo. Quiebre no exige saldo cero y neto medio no garantiza ganancias. La cola inconclusa se excluye de tasas/medias de completas, se incluye en totales de ventana. Huecos sin ranking no reciben apuesta ni reinician ronda/sesión; folds tampoco. Contrafactual histórico reutilizado, censurado y elegido retrospectivamente; no pronóstico.

Requiere repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
