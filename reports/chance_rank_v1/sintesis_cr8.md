# Síntesis final — chance-rank-v1 (CR-8)

**Protocolo:** `chance-rank-v1`, hash `ed329fe9a50e2fa1b4e5879b1d6b39b41febf5aaba23e548068be689a43572b4`.
**Fuente:** `chance_express_history.json`, SHA-256 `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`, 105.426 sorteos, 566 días observados (2025-03-05 a 2026-09-25), 4 días vacíos, 0 duplicados fusionados.

**Estado del estudio: fase interpretable completa (12/12 familias evaluadas). Fase supervisada (CR-7) cancelada por decisión explícita del usuario, no por bloqueo técnico. Controles reducidos de 70 a 23 por decisión explícita del usuario, no por bloqueo técnico.**

Todo resultado presentado es **retrospectivo/exploratorio sobre el historial ya observado**, nunca confirmación prospectiva. Ninguna cifra aquí es garantía de resultado futuro. No hay dinero, martingalas ni recomendaciones de apuesta.

## 1. Resumen principal

Pregunta predeclarada: ¿algún sistema de las familias evaluadas logra, de forma sostenida y con evidencia estadística, un acierto Top-25 del primer puesto en el siguiente sorteo consecutivo mejor que el azar uniforme y que la frecuencia reciente-500?

**Respuesta con la evidencia disponible: no.** De 16 sistemas predeclarados (12 familias interpretables + `select_interpretable` + 3 N/A por cancelación de CR-7), **14 quedaron "sin mejora detectada"**, **1 ("Ensemble") quedó "señal exploratoria"** (no pasa el criterio práctico completo), y **3 quedaron N/A** (`logistic`, `tree`, `select_all`) por la cancelación de CR-7.

## 2. Contraste principal (65.235 targets primarios elegibles, K=25, H1 actualizado)

| Sistema | Δ vs uniforme | p ajustado (Holm) | Δ vs reciente500 | p ajustado | % folds positivos | Clasificación |
|---|---:|---:|---:|---:|---:|---|
| freq_hist | −0,027pp | 1,000 | −0,032pp | 1,000 | 0,64 | sin mejora detectada |
| freq_recent | −0,191pp | 1,000 | −0,196pp | 1,000 | 0,29 | sin mejora detectada |
| decay | −0,196pp | 1,000 | −0,201pp | 1,000 | 0,36 | sin mejora detectada |
| cold | +0,167pp | 1,000 | +0,162pp | 1,000 | 0,71 | sin mejora detectada |
| notebook | −0,174pp | 1,000 | −0,179pp | 1,000 | 0,36 | sin mejora detectada |
| mix | −0,093pp | 1,000 | −0,098pp | 1,000 | 0,50 | sin mejora detectada |
| transition | +0,031pp | 1,000 | +0,026pp | 1,000 | 0,57 | sin mejora detectada |
| carry | −0,020pp | 1,000 | −0,025pp | 1,000 | 0,50 | sin mejora detectada |
| doubles | −0,188pp | 1,000 | −0,193pp | 1,000 | 0,29 | sin mejora detectada |
| category | −0,211pp | 1,000 | −0,216pp | 1,000 | 0,43 | sin mejora detectada |
| time | −0,303pp | 1,000 | −0,308pp | 1,000 | 0,36 | sin mejora detectada |
| **ensemble** | **+0,339pp** | **0,438** | +0,334pp | 0,812 | 0,79 | **señal exploratoria** |
| logistic | N/A | — | — | — | — | N/A (CR-7 cancelada) |
| tree | N/A | — | — | — | — | N/A (CR-7 cancelada) |
| select_interpretable | −0,167pp | 1,000 | −0,172pp | 1,000 | 0,50 | sin mejora detectada |
| select_all | N/A | — | — | — | — | N/A (CR-7 cancelada) |

MDE (detectabilidad óptima, aproximación binomial): **0,60pp** con n=65.235 y m=32 contrastes. El Ensemble (+0,339pp) queda por debajo del MDE, consistente con "no significativo".

## 3. Cobertura K (select_interpretable, primer puesto)

Reportado como referencia descriptiva, no como criterio de éxito: más cobertura (K mayor) no es mejor selección, es un tamaño de lista distinto. Ver `reports/chance_rank_v1/steps/secondary.json` para la tabla completa K=1..50.

## 4. Horizontes actualizado/congelado

H1 actualizado y H1 congelado coinciden en origen, por construcción (verificado en CR-3 test-first). H5/H10/H20 descriptivos en `secondary.json`, sin afirmaciones confirmatorias.

## 5. Posiciones y objetivo "cualquier puesto"

Calculado para las 5 posiciones y el objetivo agregado "any" (media de percentiles); resultados descriptivos en el store, no promovidos a criterio principal (decisión predeclarada del protocolo).

## 6. Baselines

Uniforme analítica (K/100), 100 realizaciones aleatorias (semillas `chance-rank-v1/random/000..099`), lista fija (`chance-rank-v1/fixed`), frecuencia de entrenamiento externo congelada por fold, frecuencia reciente-500 actualizada causalmente. Usadas en el contraste principal (uniforme y reciente500) y como referencia descriptiva las demás.

## 7. Esperas y supervivencia (Kaplan-Meier)

Calculado en `secondary.json` para el Top-25 de cada sistema sobre el target primario, con censura al terminar segmento. No repetido aquí por espacio; disponible en el artefacto.

## 8. Probabilísticos (log-loss, Brier, calibración)

Calculado para las configuraciones probabilísticas (freq_hist, freq_recent, category, doubles, transition, carry, time) en `secondary.json`, con calibración de 10 bins fijos. Ninguno mostró calibración que cambie la conclusión principal.

## 9. Fuentes, meses, folds y reinicio por fuente

Dos fuentes: `premios.do` (76.896 filas, hasta 2026-04-24) y `loteka.com.do` (28.530 filas, desde 2026-04-25). 14 folds externos (13 de 28 días + 1 final de 22 días), manifiesto completo en `fold_manifest.json`.

**Reinicio por fuente** (estado del selector interpretable reiniciado en la primera fila de `loteka.com.do`, warmup 2.000 aplicado dentro del sub-historial): tasa de acierto Top-25 tras el cambio de fuente = **24,71%** sobre 24.109 targets, 0 folds N/A. Prácticamente idéntica a la tasa base (~25% teórica del azar); no hay efecto de fuente detectable. No se interpreta como efecto causal de la fuente (aclaración predeclarada).

## 10. Ablaciones y ensemble

17 ablaciones (12 de la mezcla notebook sin uno de sus tres componentes, 5 del ensemble sin uno de sus cinco miembros) calculadas y almacenadas; ninguna superó al azar de forma sostenida. Tabla completa en `secondary.json`.

## 11. Correlación entre sistemas

Correlación φ de indicadores de acierto entre sistemas calculada en `secondary.json` (target primario). Jaccard de listas Top-25 se omitió explícitamente por presupuesto de memoria (decisión D13, documentada en el ODD), no por descuido.

## 12. Controles — evidencia clave para interpretar el Ensemble

**Reducidos de 70 a 23 por decisión explícita del usuario** (D17 en el ODD), tras conocer el resultado preliminar. Esto debilita, no invalida, la conclusión.

- **Sanos (13/20 planeados):** 0/13 streams con algún rechazo primario Holm. Sin evidencia de que el método produzca falsos positivos, aunque con menos potencia que el diseño de 20.
- **Señal plantada (6/30 planeados, solo intensidad fuerte q=,10, 3 de los 5 tipos: repetición, arrastre, hora):** **6 de 6 detectadas**, con Δ entre +7,18pp y +7,73pp vs uniforme, `p_adj≈0,0005` en las seis. El método demuestra sensibilidad real a sesgos de ese tamaño. **El +0,339pp del Ensemble en datos reales es ~20 veces más chico que la señal más débil que el método logró detectar con confianza.** Esta es la evidencia más fuerte de que el Ensemble no refleja una ventaja real, sino ruido dentro de lo esperable.
- **Nulo de orden (4/20 planeados):** el Ensemble no rechaza en ninguna de las 4 permutaciones (Δ entre −0,098pp y +0,171pp), consistente con ausencia de dependencia explotable del orden temporal.
- **No cubierto:** intensidad débil (q=,02), los tipos `shift` y `streak`, y la mayoría de las permutaciones de orden y streams sanos del diseño original. Cualquier afirmación sobre esos casos específicos queda sin evidencia, no confirmada ni refutada.

## 13. Fallos de ejecución, volumen y limitaciones operativas

- Tres relanzamientos completos del store por invalidación de checkpoint (dos por cambios de código legítimos —fix de fuga de memoria en `export`, fix de checkpoint granular de CR-7—, uno por reducción de controles). Documentado en el ODD (D16).
- Bug real corregido antes de resultados: empates matemáticos por redondeo flotante en mezclas/ensemble/ablaciones, con oráculo de fuerza bruta independiente (CR-2).
- Bug real corregido antes de resultados: fuga de resultado en el archivo de predicciones exportado (`ranking100` + `winner_rank` en el mismo archivo permitía reconstruir el valor oculto sin `--reveal`); corregido separando predicciones y resultados en archivos distintos.
- Bug real corregido: `waits()`/Kaplan-Meier censuraba mal la primera fila de cada segmento.
- Volumen: ~4,4 GB de artefactos de store (eliminados tras el cómputo salvo los conservados), 23 archivos de control persistidos, protocolo y manifiesto congelados en disco.

## 14. Conclusión

**No se cumple el criterio práctico predeclarado para ningún sistema.** El único candidato con una diferencia positiva no despreciable (Ensemble, +0,339pp) no pasa el filtro estadístico (Holm, ambos baselines) ni el MDE, y los controles de señal plantada muestran que el método detecta sesgos reales de forma clara cuando existen — muy por encima de lo que el Ensemble mostró. La interpretación más razonable con la evidencia disponible es que **Chance Express se comporta, en el primer puesto y en la ventana de tiempo estudiada, como un generador aleatorio sin sesgo explotable por ninguna de las 12 familias interpretables evaluadas.**

Esto es consistencia con la conclusión ya obtenida en el estudio Quiniela80 (retorno real <1 en las 4 estrategias probadas) y con la auditoría RNG previa. Tres estudios independientes, mismo historial, misma conclusión.

**Lo que este estudio NO dice:** no dice que el futuro se comportará igual (no hay confirmación prospectiva posible con este JSON). No dice que la fase supervisada (CR-7) habría dado igual — quedó sin ejecutar por decisión del usuario. No dice que los tipos de señal no cubiertos (shift, streak, q débil) estén ausentes — quedan sin evidencia.

## Datos futuros necesarios para una confirmación prospectiva real

1. Snapshots de predicciones selladas **antes** de conocer nuevos sorteos, con protocolo y tamaño de muestra fijados de antemano.
2. Un período de observación nuevo, no usado en este estudio, evaluado una sola vez.
3. Si se quisiera evidencia sobre Rapidita/Quiniela Extraordinaria específicamente: su propio historial de sorteos, hoy no disponible.
