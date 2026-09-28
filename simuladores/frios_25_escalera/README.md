# Fríos · 25 números · escalera

El ranking congelado `cold` prioriza números históricamente poco frecuentes; selecciona los primeros 25 distintos, cobrados en las cinco posiciones con pagos acumulados. Capital RD$2.000, meta RD$2.800. La escalera de diez rondas busca recuperar pérdidas previas más RD$10 si acierta el primer premio: apuesta RD$1 **por número** al inicio, costo inicial RD$25 (`25 × 1`); mínimo RD$1 por número, y el costo de rondas posteriores es `25 × apuesta de esa ronda`. Primer acierto reinicia la ronda; premios secundarios no. Si la próxima ronda es inasequible, quiebra aunque quede saldo.

Fila esperada: **677 metas / 1.105 completas (61,3%)**, 428 quiebres, neto medio **−RD$162,2** sobre completas; el script la recalcula.

Desde esta carpeta: `py -B ejecutar.py` (también `py ejecutar.py`). Desde la raíz: `py -B simuladores/frios_25_escalera/ejecutar.py`.

Una sesión inicia con RD$2.000 y no equivale a un sorteo; puede durar muchos sorteos apostados. Quiebre no exige saldo cero, y neto medio no garantiza ganancias. La cola inconclusa se excluye de tasas/medias de completas, se incluye en totales de ventana. Los huecos sin ranking no reciben apuesta ni reinician sesión/ronda; tampoco los folds. Contrafactual histórico reutilizado, censurado y seleccionado retrospectivamente: no pronóstico.

Necesita repositorio completo, motor Python/NumPy, JSON y NPZ compartidos; no es autónomo. [Resumen original](../../docs/resumen_resultados_quiniela.md) · [Informe completo](../../docs/informe_quiniela_comparacion.md) · [Índice](../README.md).
