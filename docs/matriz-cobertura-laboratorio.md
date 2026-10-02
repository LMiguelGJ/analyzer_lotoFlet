# Matriz de cobertura y aceptación — borrador ODD-00

**Estado:** trazabilidad ODD-00 con **G1 inicial aprobado**; no equivale a implementación ni verificación funcional. Cada ID procede del [contrato de este borrador](especificaciones-laboratorio-integral.md); la elicitación literal no fue entregada con numeración original. [Catálogo](catalogo-estrategias.md) define R01–R13, S01–S03, B01–B08 (B06–B08 aprobados sólo como inventario, no implementados), L01, C01, PR01–PR14 y X01–X09. «Prueba» aquí significa comprobación futura; no se ejecutaron tests. Un ID sólo se marca cubierto cuando exista evidencia ejecutada y puertas resueltas, no por estar escrito.

## Recorrido para revisión

1. Revisar **P02** y G1 inicial aprobado; G2/G5 son contratos configurables, no permisos para asumir valores ocultos.
2. Implementar por unidad con validación de perfil/protocolo; elegir G6 antes de ejecutar el ejemplo. Familias externas nuevas requieren otra aprobación.
3. Durante cada unidad, sustituir «pendiente» por prueba concreta, resultado, versión/fixture y decisión; no sustituir la matriz por una lista de tareas marcadas.

| Requisito | Unidad principal | Aceptación observable pendiente / bloqueo |
| --- | --- | --- |
| A01 | 00, 02, 12 | App local y UI en español, operaciones monetarias sólo backend; recorrido accesible. Pendiente. |
| A02 | 00, 13 | **G1 inicial aprobado** (R/S/B y referencias del catálogo); implementación y cada prueba siguen pendientes. Una familia externa nueva requiere aprobación separada. |
| P01 | 02, 04 | Perfiles explícitos con 1/3/5 y otra cantidad válida de posiciones; universo, repetición, k, premios y apuestas inválidas rechazados; datos/ranking compatibles. Sin valores ocultos G2. |
| P02 | 02, 04 | Fixtures para stake por número × multiplicador, pago total y saldo anterior − costo + pago; `all`/`best` con repetido; ningún reintegro extra. Fórmula decidida, pruebas pendientes. |
| P03 | 02, 04 | Perfil nuevo declara escala/incremento/unidad, mínimo/máximo y límites; operaciones exactas o política de redondeo explícita versionada, sin inferir fracciones. Rechazar faltantes/desborde; herencia RD$1 entera conservada. Contrato G2, implementación pendiente. |
| P04 | 02, 13 | Abrir snapshots heredados sin recálculo; Quiniela80 80/8/4/2/1 y Original70 70/8/4/2/1 etiquetados, hashes/versiones persistidos. **G2**. |
| P05 | 02, 04 | Selección explícita de `all`/`best`; `best` toma máximo pago por número ante posiciones repetidas. `custom` sólo con regla/versionado explícitos y validación, no habilitado por la aprobación G1. Fixtures con stakes distintos. |
| F01 | 04 | Selector, entrada, k, stake, liquidación y cierre versionados, incompatibilidad rechazada. B06–B08 están en catálogo G1, no habilitados hasta implementar y comprobar entradas G2/G5, calibración y exposición. |
| F02 | 04, 10, 12 | Configuración visual declarativa sin `eval`; importación de código no convertida automáticamente; catálogo G1 inicial aprobado, extensión deshabilitada sin aislamiento G3. |
| F03 | 04 | Límites independientes; inicio incluido, corte fecha/duración exclusivo, N filas transcurridas incluye esperas; tras liquidar: meta → imposibilidad siguiente → tope apuestas. Probar frontera/empate y preservar cronología heredada G2. |
| F04 | 01 | Capital inicial imposible falla antes de crear experimento/encolar, error por estrategia; motor y preflight comparten stake, quiebre posterior distinto. |
| F05 | 01 | Una estrategia falla, otra termina; fallo común interrumpe lote; agregado parcial no aparece completo. |
| F06 | 06 | Sesiones no solapadas reinician en sorteo siguiente, cola censurada y cardinalidad de barridos antes de admitir lote. Protocolo G5 explícito, versionado, sin default universal. |
| F07 | 05 | Curva >20 apuestas cubre extremos e inicio/fin, punto reducido abre detalle exacto; replay paginado intacto. |
| F08 | 05, 06 | Apostado/pagado/neto/retorno/ROI/drawdown reconciliados con backend, nulo si denominador cero; completas vs ventana con cola. **G5 en intervalos**. |
| F09 | 08 | MC reproduce la misma semilla en serial/paralelo, repetidos y perfiles válidos; uniformes y sesgo conocido separados de historia. **G5**. |
| F10 | 09 | Recálculo causal para posiciones declaradas del catálogo G1, caché invalida por versión, top-k/espera/supervivencia y auditorías con aplicabilidad/protocolo G5 explícito. |
| D01 | 03 | CSV/JSON con preview: archivo inválido o conflicto no promueve datos parciales; ejemplos 1/3/5 posiciones. **G2**. |
| D02 | 03 | Hash, esquema, zona/fuente y corrección reproducibles; snapshot anterior legible tras actualización; conectores sólo tras **G4**. |
| D03 | 03 | Buscar fecha tardía directamente, paginar estable y mostrar ranking ausente sin inventar resultado. |
| U01 | 12 | Asistente↔mesa avanzada conserva configuración; bloques reflejan sólo capacidades implementadas/compatibles del catálogo G1, no ejecución de extensiones sin G3. |
| U02 | 12 | Prueba de teclado, foco, errores, vacíos, responsive y confirmaciones en navegador. |
| NF01 | 06, 11 | Lote excedido no encola; cuotas/prioridades/recursos/confirmación comprobados, estimación identificada como orientativa. |
| NF02 | 11 | Crash, cancelación, reanudación compatible sin doble apuesta; caso no compatible cancela/reinicia explícitamente. |
| NF03 | 10 | Pruebas adversariales niegan filesystem ajeno/red/procesos/agotamiento y salida malformada; sin evidencia, ejecución deshabilitada. **G3**. |
| T01 | 07, 13 | Folds y warmup causales, etiquetas historia reutilizada/holdout nuevo/MC, test de fuga futura. **G5**. |
| T02 | 07, 09 | Protocolo G5 seleccionado/versionado y completo: splits, warmup, denominadores, semillas, reinicio, censura, bootstrap por unidad declarada, intervalos y multiplicidad; rechazar faltantes/fuga, controles positivos/negativos. Referencias 60/40+2000 y walk-forward+10000 no son defaults universales. |
| T03 | 01, 06, 13 | Oráculo original inmutable + k20/30/40 y `best`; fixtures separados random/blend; comprobar ejecución de los 14 launchers con rutas/entradas/hashes reales antes de llamar reproducibles; grilla 339 por modo, 678 ambos, nominal antes de filtros. No se ejecutaron en ODD-00. |
| E01 | 13 | Caso 00–99/3/repetidos/60-10-5/k10/transición60-fríos40/2000→2800/12 transcurridos, con stake y settlement **elegidos en G6**; balance manual. |
| E02 | 13 | Cada fila tiene evidencia o exclusión humana; README diferencia funcionamiento real de propuesta, historial de MC y validación. |

### Ledger de Judgment Day (obligatorio, no prueba de defectos)

| ID | Requisitos / unidad | Evidencia exigida |
| --- | --- | --- |
| JD01 | F04–F05 / 01 | Preflight antes de persistir, asequibilidad y fallos independientes; no confundir saldo insuficiente posterior con configuración inválida. |
| JD02 | F06, T03 / 06 | Sesiones consecutivas, PR01–PR14 y grilla nominal 339 por modo/678 ambos antes de filtros; validar rutas/hashes/ejecución, tasas completas, cola censurada, Wilson, neto, mediana/p90 y totales. |
| JD03 | T01–T02 / 07 | Validación temporal causal y estabilidad por fecha/semilla; splits, corrección y denominadores declarados. |
| JD04 | D03 / 03 | Búsqueda directa de fecha/sorteo y paginación sin avance página a página. |
| JD05 | F07 / 05 | Curva completa y extremo preservado con detalle exacto, sin límite de 20 puntos. |
| INFO-01 | F01, B05, X01–X05 / 04 | Entrada condicional/espera/salida no confundidas con ranking. |
| INFO-02 | F09, X06 / 08 | MC uniforme/controles, fuentes y semillas separados. |
| INFO-03 | F08 / 05–06 | Apostado, pagado, ROI y drawdown con fórmula/denominador. |
| INFO-04 | F10, P01 / 09 | Recalcular rankings y declarar posiciones soportadas; no reutilizar pos1 en universo ajeno. |
| INFO-05 | P04–P05 / 02 | Original70 conservado y modos de pago con repetidos. |
| INFO-06 | T03 / 01 | Oráculo k20/30/40/`best`; pruebas de azar y blend independientes. |
| INFO-07 | E02 / 13 | README veraz; observación unilateral no elevada a bug probado. |

### Catálogo → resultado esperado

| IDs | Unidad / comprobación |
| --- | --- |
| R01–R13 | 04 conserva identificación del export pos1; 09 recálculo con protocolo/versiones G5 y tests causales, sólo perfiles compatibles del inventario G1 aprobado. |
| S01–S03 | 01 fixtures para blend/azar, 04 compatibilidad y reproducibilidad; paridad histórica k50. |
| B01–B05, L01, C01 | 02/04 cálculo y condiciones, 07 validación condicional; G2 y G5 según caso. Tímida y escalera histórica no se confunden con staking actual. |
| B06–B08 (G1 catálogo aprobado; ejecución pendiente) | 02/04/07: perfil G2 y protocolo G5 explícitos antes de usar. Fracción fija: saldo, escala, mínimo/topes/exposición; Kelly binario: `p`, `q=1−p`, `b` **neto** y evento binario calibrados; fraccional: factor, incertidumbre/sensibilidad. Tests de pérdida completa, estimación errónea, correlación y resultados múltiples deben impedir aplicar `f*` binario a cartera multinúmero/multiposición. Puntos de ranking no son probabilidades; pago bruto no es `b`. |
| PR01–PR14 | 06 **comprobar** rutas, entradas/hashes y ejecución de referencia, 2000→2800, `all`, reinicios y censura, uno por nombre; inspección sugiere posible desajuste de rutas pero no demuestra fallo. No cerrar sólo por listar nombres. |
| X01–X05 | 04 reglas de entrada sólo tras contrato G1; 07 pruebas causales y controles con multiplicidad G5. |
| X06 | 06/08 sesiones tímida/audaz y comparación MC bajo mismo perfil/modo; censura explícita. |
| X07–X08 | 02/03/09 auditoría de repetidos y fuentes, nunca selectores. |
| X09 | 09 matriz descriptiva de transiciones pos1 dentro del día; no inferencia por valor sin nuevo protocolo. |

## Puertas y protocolo de evidencia

| Puerta | Estado actual | Decisión que falta / efecto |
| --- | --- | --- |
| G1 | **Aprobado por el usuario para inventario inicial** R01–R13/S01–S03/B01–B08 y referencias locales. Thorp inspeccionado por padre para B07/B08; PDF Berkeley no verificado. | Implementación/compatibilidad/validación aún pendientes; nuevas familias fuera del inventario requieren ficha y aprobación adicional. |
| G2 | **Contrato técnico definido, implementación pendiente**: P02 aprobado; P03/F03 exigen valores explícitos en perfil nuevo, máximo pago por número en `best`, herencia entera inalterada. | Rechazar perfil sin escala/incremento/topes/condiciones necesarios, redondeo no especificado si se necesita o `custom` sin regla. No hay elección global de precisión o denominación pendiente para ODD-01. |
| G3 | **Pendiente**. | Aislamiento Windows probado y autorización de dependencias; sin ello, terceros deshabilitados. |
| G4 | **Pendiente**. | Conectores reales, timezone, duplicados/correcciones y programación aprobada; importación local no presupone conectores. |
| G5 | **Contrato técnico definido, implementación pendiente**: cada evaluación selecciona protocolo completo y versionado, sin default universal; referencias históricas 60/40+2000 y walk-forward+10000 etiquetadas como reutilizadas. | Rechazar protocolo incompleto o con fuga; diseñar, congelar y probar configuración nueva antes de observar resultados. No bloquea ODD-01 heredado. |
| G6 | **Pendiente**. | Elegir stake y liquidación de E01 antes de ejecutar; RD$1 mínimo no decide ninguno. |

**Regla estadística de contraste:** `strategy_tests/run_experiments.py` fija 60/40 por días y `experiments.py` usa 2000 remuestreos por día; `chance_rank/protocol.py` fija walk-forward por folds y 10000 remuestreos en bloques de siete días (sensibilidad 1/14). Son evidencia de referencia, no decisiones G5. Métricas de completas excluyen cola; totales de ventana la incluyen. Una reconstrucción explorada no es holdout independiente.

**Siguiente paso:** ODD-01 (preflight, aislamiento de fallos, oráculo y fixtures adicionales) está listo para implementación/verificación independiente sin inventar valores de perfiles nuevos. G3 sólo condiciona extensiones, G4 conectores y G6 ejecución del caso E01; no bloquean el trabajo previo. G1 es la única puerta aprobada por el usuario aquí; G2/G5 son contratos técnicos pendientes de implementar, no decisiones humanas globales asumidas.
