# Fríos · 50 números · escalera

El ranking archivado `cold` prioriza números de baja frecuencia histórica anterior; elige los primeros 50 distintos y los liquida en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. La escalera de diez rondas busca recuperar pérdidas previas más RD$10 al cubrir el primer premio: apuesta inicialmente RD$1 **por número**, costo RD$50 (`50 × 1`); rondas posteriores comienzan en RD$2, RD$6, RD$16, RD$42 por número, con costo total `50 × importe de ronda` y mínimo RD$1 cada uno. Primer premio reinicia la ronda, premios secundarios no; siguiente ronda inasequible implica quiebre aunque quede saldo.

Fila esperada: **1.429 metas / 3.502 completas (40,8%)**, 2.073 quiebres, neto medio **−RD$98,7** sobre completas. Se recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/frios_50_escalera/ejecutar.py`.

Una sesión comienza con RD$2.000 y puede abarcar muchos sorteos apostados, no uno solo. Quiebre no exige saldo cero y neto medio no garantiza ganancia. La cola inconclusa se excluye de tasas/medias de completas, pero entra en totales de ventana. Huecos sin ranking no reciben apuesta ni reinician ronda/sesión; folds tampoco. Contrafactual histórico reutilizado, censurado y elegido retrospectivamente; no pronóstico.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no funciona aislado. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
