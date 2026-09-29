# Simuladores individuales de Quiniela

Cada carpeta reproduce **una** fila histórica del [resumen original](../docs/resumen_resultados_quiniela.md), no las 339 combinaciones ni Monte Carlo. Necesitás Python con NumPy y dependencias **ya instaladas** para este repositorio; no hay instalación automática. Ejecutá desde la raíz `py -B simuladores/<carpeta>/ejecutar.py`, o entrá a la carpeta y usá `py -B ejecutar.py` (`py ejecutar.py` también funciona, pero puede generar el caché normal de Python). `--help` muestra el uso; no hay banderas que cambien el escenario.

| Carpeta (abrir instrucciones) | Sistema · números · apuesta | Meta / completas | Quiebres | Neto medio RD$ |
|---|---|---:|---:|---:|
| [transicion_1_audaz](transicion_1_audaz/README.md) | Transición · 1 · audaz | 681 / 963 | 282 | +10,3 |
| [frios_1_audaz](frios_1_audaz/README.md) | Fríos · 1 · audaz | 684 / 974 | 290 | −3,4 |
| [selector_1_audaz](selector_1_audaz/README.md) | Selector interpretable · 1 · audaz | 663 / 946 | 283 | −8,2 |
| [mezclas_1_audaz](mezclas_1_audaz/README.md) | Mezclas · 1 · audaz | 676 / 968 | 292 | −15,6 |
| [ensemble_5_audaz](ensemble_5_audaz/README.md) | Ensemble · 5 · audaz | 3.226 / 4.720 | 1.494 | −51,2 |
| [ensemble_10_audaz](ensemble_10_audaz/README.md) | Ensemble · 10 · audaz | 6.140 / 9.061 | 2.921 | −56,9 |
| [ensemble_20_audaz](ensemble_20_audaz/README.md) | Ensemble · 20 · audaz | 10.785 / 16.086 | 5.301 | −59,2 |
| [frios_25_escalera](frios_25_escalera/README.md) | Fríos · 25 · escalera | 677 / 1.105 | 428 | −162,2 |
| [mezclas_50_audaz](mezclas_50_audaz/README.md) | Mezclas · 50 · audaz | 12.845 / 20.605 | 7.760 | −117,0 |
| [transicion_50_audaz](transicion_50_audaz/README.md) | Transición · 50 · audaz | 12.890 / 20.682 | 7.792 | −116,0 |
| [paridad_50_audaz](paridad_50_audaz/README.md) | Paridad · 50 · audaz | 12.698 / 20.404 | 7.706 | −120,8 |
| [frios_50_escalera](frios_50_escalera/README.md) | Fríos · 50 · escalera | 1.429 / 3.502 | 2.073 | −98,7 |
| [paridad_50_escalera](paridad_50_escalera/README.md) | Paridad · 50 · escalera | 1.368 / 3.496 | 2.128 | −124,4 |
| [paridad_50_plana](paridad_50_plana/README.md) | Paridad · 50 · plana | 13 / 91 | 78 | −1.572,8 |

## Cómo funciona

Los 14 `ejecutar.py` fijan explícitamente sistema, `k` y apuesta; resuelven la raíz desde su propio `__file__` (independiente del directorio de ejecución) e importan `simuladores/runner.py`. Este valida **ambos SHA-256** antes de cargar `chance_express_history.json` y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz`; entradas ausentes o distintas producen error y salida no cero, sin presentar cifras como idénticas. No copies un script fuera del repositorio: depende del motor y de esas entradas compartidas. El runner usa `historical_scenario` una sola vez con capital RD$2.000, meta RD$2.800, liquidación acumulada `all`, sin búsqueda de grilla ni simulaciones MC. No escribe informes ni cachés propios.

Los rankings cubren 65.235 sorteos evaluables de 105.426 sorteos históricos, 14 folds y huecos sin apuesta. Paridad calcula consenso con **todo** el historial anterior y luego restringe los sorteos; los otros métodos leen solo su familia de ranking. El conjunto top-`k` se liquida contra las cinco posiciones con premios 80/8/4/2/1 por peso. Audaz busca alcanzar la meta con el primer premio y recalcula por número (`ceil((meta − saldo)/(80 − k))`, limitado por `floor(saldo/k)`); escalera usa diez rondas para recuperar costos y RD$10 con el primero; plana apuesta RD$1 por número. Nunca se apuesta menos de RD$1 por número: costo total es `k × importe por número`.

Una **sesión** arranca con RD$2.000 y recorre sorteos apostados hasta meta o quiebre (no poder financiar la próxima apuesta, incluso si queda saldo); no es un sorteo ni una sola cuenta común a todas las sesiones. La sesión inconclusa al final de los datos queda fuera de tasas y promedios de completas, pero sus apuestas se incluyen en los totales de ventana: esta censura limita la interpretación. Los folds y huecos no reinician la sesión. Neto medio es saldo final menos RD$2.000 promediado en completas, no ganancia garantizada. Wilson es descriptivo: datos reutilizados, múltiples alternativas inspeccionadas y falta de validación prospectiva impiden inferir una ventaja futura.

Más detalles: [informe completo original](../docs/informe_quiniela_comparacion.md). Para la integración real secuencial de las 14 carpetas, opt-in reservado a SI3: `QUINIELA_RUN_INTEGRATION=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest test_simuladores.py -q -p no:cacheprovider`. Puede tardar mucho; no hay tiempo medido aún.
