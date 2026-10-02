# Catálogo de estrategias y protocolos — inventario ODD-00

**Estado: inventario inicial G1 aprobado por el usuario; implementación/compatibilidad pendientes.** Una estrategia completa combina **selector → decisión de entrada/espera → cobertura → stake por número → liquidación → cierre**, con perfil, fuente y versión fijados. Un ranking no es una apuesta, un preset no es un método predictivo y una prueba estadística no es un selector. Véanse [contratos F01–F02](especificaciones-laboratorio-integral.md) y [matriz](matriz-cobertura-laboratorio.md).

## Inventario local comprobable

En `webapp/backend/laboratorio/domain/contracts.py` existe Quiniela80 (100 números, cinco posiciones, pagos 80/8/4/2/1), sistemas del export pos1, coberturas 1/5/10/20/25/30/40/50, máximo cinco estrategias por solicitud y `all`/`best`. `webapp/backend/laboratorio/domain/selection.py` implementa combinaciones/azar/paridad; `engine/adapter.py` usa rankings congelados de 100 valores para la cobertura y no infiere posiciones ausentes. Este alcance **no** prueba portabilidad a otros universos. El catálogo de referencia en `repo_ref/chance_rank/protocol.py` contiene grillas y familias adicionales; `repo_ref/quiniela_compare.py` excluye explícitamente `logistic`, `tree`, `select_all` por no disponibles y `recent500` por ser baseline auxiliar.

| ID | Selector de ranking pos1 existente | Parámetros/semántica verificable en referencia | Estado |
| --- | --- | --- | --- |
| R01 | `freq_hist` | Frecuencia histórica, scope posición/global y ventana total/20000 en protocolo v1. | Export congelado/local |
| R02 | `freq_recent` | Ventanas 20/100/500/2000. | Export congelado/local |
| R03 | `decay` | Vida media 20/100/500/2000. | Export congelado/local |
| R04 | `cold` | Edad desde aparición, scope posición/cualquiera. | Export congelado/local |
| R05 | `notebook` | Componentes ponderados 0,45/0,45/0,10; ventanas del protocolo. | Export congelado/local |
| R06 | `mix` | Grilla de pesos histórico/reciente/edad y ventana si peso reciente > 0. | Export congelado/local |
| R07 | `transition` | Transición con parámetro `lam` 100/1000. | Export congelado/local |
| R08 | `carry` | Arrastre por posición origen 1–5 y `lam` 100/1000. | Export congelado/local |
| R09 | `doubles` | Repeticiones/«dobles», `lam` 100/1000. | Export congelado/local |
| R10 | `category` | Paridad, bajo/alto, decena, terminación; `lam` 100/1000. | Export congelado/local |
| R11 | `time` | Hora, día de semana, posición del día; `lam` 100/1000. | Export congelado/local |
| R12 | `ensemble` | Borda/voto de miembros de referencia. | Export congelado/local |
| R13 | `select_interpretable` | Elige configuración interpretable usando entrenamiento interno anterior al fold evaluado. | Export congelado/local |

**«Export congelado/local»** significa ranking disponible bajo su archivo/protocolo original, no que hoy se recalcule en producción o tenga eficacia validada. Conservar ID, configuración por fold, tie-break y corte causal cuando se habilite recálculo. No aplicar un ranking de 100 números a universo distinto sin nuevo cálculo validado.

| ID | Composición/selector | Contrato y límite |
| --- | --- | --- |
| S01 | `blend` | Dos o más sistemas distintos y pesos enteros positivos que suman 100; ejemplo transición 60/fríos 40. En el motor local, posición 1…100 da 100…1 puntos; score(n) = Σ peso% × puntos del ranking para n, orden descendente y empate por número menor. Es mezcla de **rankings**, no probabilidades pagadoras ni liquidación (`domain/selection.py`); nuevos perfiles requieren soporte expreso. |
| S02 | `random` | Permutación reproducible por semilla y sorteo; baseline/control, no predicción. Prueba determinista propia separada del oráculo de sistemas. |
| S03 | `parity` | Consenso par/impar causal; cobertura histórica fija k=50, no ranking portable ni regla automática de entrada tras racha. |

### Apuesta, entrada y cierre: ejes independientes

| ID | Eje | Estado/requisito |
| --- | --- | --- |
| B01 | `flat` | Un peso entero por número en motor Quiniela80 actual; **no** es el stake elegido para el ejemplo E01. |
| B02 | `ladder` | Escalera local calculada para diez rondas con margen primer premio − cobertura y recuperación +RD$10; referencia `strategy_tests/rules.py` conserva otra escalera histórica fija (1,3,10,35,123,430,1505,5268,18438,64533) de 50 números y perfil Original70. No tratarlas como idénticas ni aplicarlas a cualquier premio. |
| B03 | `bold` | Stake acotado por saldo/cobertura y brecha a meta bajo primer premio; cálculo local depende del margen positivo. |
| B04 | Tímida | Referencia E6: hasta RD$10 por sorteo para un número; no está en enum de staking local. |
| B05 | Entrada/salida condicional | Esperar racha, edad, repetición, horario u otra señal causal y decidir entrada o salida sin consumir cupo de apuesta al esperar. Referencias E1–E5 son **candidatas para especificar**, no traslado automático al motor; definir reset y horizonte por perfil antes de implementar. |
| B06 | Fracción fija **aprobada para catálogo, no implementada** | Stake como fracción configurada `f` del saldo disponible antes del sorteo; exige escala/incremento y redondeo explícito o rechazo, mínimo, topes, exposición simultánea y límite de pérdida del perfil G2. No implica probabilidad de acierto. |
| B07 | Kelly binario **aprobado para catálogo, no implementado** | Modelo de Thorp, §2: una apuesta pierde una unidad con probabilidad `q=1−p` o gana **neto** `b` unidades por unidad apostada con probabilidad `p`, `b>0`; ventaja `bp−q>0`. Maximizar `p·log(1+bf)+q·log(1−f)` da `f*=(bp−q)/b` en ese modelo, con `0≤f<1` y `0<p<1`. Exige probabilidades estimadas/calibradas independientemente, resultado binario y validación de exposición; no derivar `p` de puntos de ranking. |
| B08 | Kelly fraccional **aprobado para catálogo, no implementado** | Thorp, §7.3, analiza medio Kelly `0,5 × f*` estimado y advierte sobre incertidumbre y sobreapostar. Factor fraccional explícito sólo con estimación, restricciones, error y sensibilidad declarados; ni medio Kelly ni Kelly pleno garantizan beneficio. |
| L01 | `all`/`best`/`custom` | Suma de coincidencias o mayor multiplicador del mismo número repetido; `custom` sólo tras contrato/aprobación. Premio total = stake × multiplicador, saldo resta costo una sola vez. |
| C01 | Condiciones | Meta, quiebre, sorteos transcurridos/apostados, fecha/hora y duración simulada independientes; primer límite activado. Contrato técnico F03 fija fronteras exclusivas y prioridad tras liquidar, conservando herencia; pruebas pendientes. |

### Catorce presets de referencia; reproducción pendiente

Cada nombre bajo `repo_ref/simuladores/<nombre>/ejecutar.py` define un escenario de selector, k y estilo; `runner.py` declara capital 2000, meta 2800, modo `all`, hashes de entradas y reporte de completas/inconclusas. La inspección de rutas sugiere posibles desajustes entre rutas calculadas desde `repo_ref` y ubicaciones reales de histórico/NPZ; **no se ejecutaron los launchers**, por lo que ni reproducibilidad ni fallo de ejecución están verificados. Reproducción con entradas identificadas y hashes es criterio futuro de aceptación ODD-06, no estado actual. Son escenarios históricos, **no** 14 familias predictivas ni opciones automáticamente recomendadas.

| ID | Nombre exacto | Selector / k / staking |
| --- | --- | --- |
| PR01 | `transicion_1_audaz` | transición / 1 / bold |
| PR02 | `frios_1_audaz` | fríos / 1 / bold |
| PR03 | `selector_1_audaz` | selector interpretable / 1 / bold |
| PR04 | `mezclas_1_audaz` | mix / 1 / bold |
| PR05 | `ensemble_5_audaz` | ensemble / 5 / bold |
| PR06 | `ensemble_10_audaz` | ensemble / 10 / bold |
| PR07 | `ensemble_20_audaz` | ensemble / 20 / bold |
| PR08 | `frios_25_escalera` | fríos / 25 / ladder |
| PR09 | `mezclas_50_audaz` | mix / 50 / bold |
| PR10 | `transicion_50_audaz` | transición / 50 / bold |
| PR11 | `paridad_50_audaz` | paridad / 50 / bold |
| PR12 | `frios_50_escalera` | fríos / 50 / ladder |
| PR13 | `paridad_50_escalera` | paridad / 50 / ladder |
| PR14 | `paridad_50_plana` | paridad / 50 / flat |

Grilla histórica `quiniela_compare.py`: 13 sistemas y azar × ocho k (1,5,10,20,25,30,40,50) × tres estilos × dos modos; paridad sólo k=50 × tres × dos. **339 filas nominales por modo de liquidación**: `(13 sistemas + azar) × 8 coberturas × 3 estilos + paridad × 1 cobertura × 3 estilos = 339`; **678 para ambos modos** (`all` y `best`). Son cardinalidades nominales antes de filtros, admisión o financiación; Monte Carlo es otra población (8×3×2 = 48). No presentar 339 sin indicar el modo. Verificar admisión y conteo real antes de cada grilla.

## Experimentos y auditorías de referencia, no «estrategias» homogéneas

| ID | Pregunta y uso posible | Categoría |
| --- | --- | --- |
| X01 / E1 | Tras racha igual de paridad o mitad bajo/alto, ¿cambia la categoría? Observación de pos1 o cinco posiciones y N=1…10. | Prueba condicional; posible entrada sólo con regla aprobada |
| X02 / E2 | Fríos tras 100/150/200/300/400/500 sorteos ausentes en pos1 o cualquiera. | Test y candidatos de apuesta condicional |
| X03 / E3 | Arrastre del número de posición anterior (1–5) hacia pos1 siguiente dentro del día. | Test y candidatos de apuesta |
| X04 / E4 | Dobles seguidos en ventanas 1/5/20 dentro del día. | Test y candidatos de apuesta |
| X05 / E5 | Entrada después de ≥3…8 fallos virtuales de mitad opuesta, plana o escalera explícita. | Entrada condicional/candidatos; distinto de R09 |
| X06 / E6 | Sesiones consecutivas real vs MC bajo juego tímido/audaz, escenarios 1000→2000 y 5000→10000. | Protocolo comparativo, no selector |
| X07 / E7 | Comparar reglas `all` y `best` frente a repetidos, perfil Original70. | Auditoría de liquidación, no selector |
| X08 / E8 | Comparar regímenes/fuentes y aplicabilidad de tests por muestra. | Auditoría de fuentes, no selector |
| X09 / E9 | Matriz descriptiva de transición de primer puesto del siguiente sorteo **dentro del día**, sólo exploratoria, sin inferencia por número. | Diagnóstico, no estrategia validada |

`repo_ref/strategy_tests/run_experiments.py` usa separación por días 60/40 y `experiments.py` remuestrea por **día**, 2000 iteraciones, para retorno monetario; no convertir su «prueba ciega» histórica ya usada en nuevo holdout. `repo_ref/chance_rank/protocol.py` fija walk-forward externo (180 días iniciales, bloques 28, tres bloques internos), warmup 2000 y bootstrap **10000** de bloques de siete días con sensibilidad de 1/14 días; son protocolos diferentes y no parámetros predeterminados del nuevo G5. `quiniela_compare.py` describe sesiones consecutivas y MC uniforme por perfil/modo: no mezclar tasas de completas con totales de ventana incluyendo cola.

## Fuentes del catálogo inicial y límites de aplicación

| Fuente/candidato | Lo que sí consta | Lo que **no** autoriza |
| --- | --- | --- |
| NIST, [Random Bit Generation: Documentation and Software](https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software) | El padre reportó recuperación de la página oficial: SP 800-22 rev.1a, abril 2010; recomendación espectral de **un millón de bits** y advertencia de carácter experimental. Fuente para límites/metodología de auditoría binaria; esta unidad no hizo nueva recuperación web. | No aplicar directamente pruebas binarias a sorteos incompatibles ni concluir aleatoriedad/ventaja por un p-valor. |
| Edward O. Thorp, [*The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market*](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf), *Handbook of Asset and Liability Management*, vol. 1, ©2006, DOI:10.1016/S1872-0978(06)01009-X | El padre recuperó el PDF primario e inspeccionó §§2 y 7.3. §2 sustenta B07 **sólo** bajo ganancia neta binaria `b`/pérdida completa; §7.3 sustenta el ejemplo de medio Kelly y la cautela por estimación/sobreapostar en B08. Esta unidad no hizo nueva recuperación. | No prueba probabilidades de lotería, independencia, rentabilidad ni transferencia de esa fórmula a carteras de apuestas. |
| [PDF candidato previamente comunicado (Berkeley)](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf) | Contenido **no verificado**; fuente distinta de Thorp inspeccionada. | No atribuirle fórmulas, autoría, conclusiones ni respaldo. |
| Otras familias externas | Sin fuentes, versión, fórmula, parámetros y evidencia validadas aún. | No agregar familias al inventario inicial aprobado sin ficha y aprobación nueva. |

**Límite de aplicación:** `b` en B07 es **ganancia neta** sobre la unidad jugada cuando se gana, no el multiplicador de **pago bruto total** P02. Una cuota que paga `M` en total por unidad y pierde toda la apuesta al fallar daría `b=M−1` sólo para ese evento binario aislado. Una cartera de varios números, posiciones y premios simultáneos/correlacionados tiene otros resultados y exposiciones; no aplicarle automáticamente `f*`, ni usar puntos de ranking como `p`.

**Ficha para futuras incorporaciones ajenas al G1 inicial:** nombre/ID, clase, editor/URL/fecha/versión, fórmula y derivación para resultados realmente modelados, parámetros/límites, procedencia/calibración de probabilidades, supuestos, compatibilidad, controles negativos, sensibilidad a error/exposición y riesgo de selección retrospectiva. B06–B08 **ya pertenecen al catálogo aprobado**, pero su ejecución requiere contratos G2/G5 completos en perfil/protocolo, implementación y evidencia de compatibilidad; si faltan entradas, rechazar, no elegir un default. La aprobación del inventario no autoriza nuevas familias, rentabilidad ni Kelly binario sobre carteras correlacionadas.
