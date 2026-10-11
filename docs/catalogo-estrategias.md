# Catálogo de estrategias y protocolos — inventario ODD-00 (referencia histórica)

> **Referencia histórica, no catálogo de funciones actuales.** Las familias, presets, reglas y protocolos descritos abajo no se habilitan por aparecer aquí; varios no están implementados o no son compatibles con el laboratorio actual. No uses estas tablas para inferir capacidades disponibles ni para asumir cobertura de una matriz histórica. La aplicación actual se limita a las funciones resumidas en [webapp/README.md](../webapp/README.md); su dirección visual está en [DESIGN.md](../DESIGN.md).

Este inventario G1 aprobado documenta propuestas y referencias previas. Una estrategia completa combina **selector → decisión de entrada/espera → cobertura → stake por número → liquidación → cierre**, con perfil, fuente y versión fijados. Un ranking no es una apuesta, un preset no es un método predictivo y una prueba estadística no es un selector. Los contratos F01–F02 y la matriz de cobertura mencionados en la versión histórica no están disponibles en este checkout; no se enlazan como documentación vigente.

## Implementado actualmente

La aplicación local tiene dos pantallas, **Corridas** y **Ajustes**. En Corridas se puede ejecutar y guardar únicamente una de estas estrategias:

- **Mezcla de rankings:** combinación de uno o más sistemas del export congelado de pos1 (los trece sistemas documentados en `webapp/backend/laboratorio/domain/contracts.py`), con porcentajes enteros positivos que suman 100; la cobertura es de 1 a 50 números. El orden de los números se calcula por puntos de ranking ponderados, con desempate por número menor. Los sorteos sin ranking no reciben apuesta de mezcla.
- **Paridad:** cobertura de 1 a 50 números seleccionados desde la partición par/impar determinada para el historial. No usa sistemas de ranking.

En ambas opciones se apuesta el mismo monto mínimo por número cubierto; no hay staking variable, escalera, entrada condicional ni estrategias de las tablas históricas disponibles para ejecutar. La corrida configura reglas de Quiniela 80 (00–99, de una a cinco posiciones y premios por posición), capital, meta, límite opcional de sorteos, fechas inclusivas e historial. Las sesiones consecutivas reinician al capital configurado y el informe conserva la huella del historial usado. La importación de historial, la cuota, los límites de detalle y el comportamiento de informes están descritos en [webapp/README.md](../webapp/README.md).

## Instantánea histórica del inventario local (no es una función de Corridas)

> **Alcance histórico:** todo el inventario que sigue hasta el final de este documento conserva tablas y notas de una instantánea anterior. No es una descripción de contratos ni de comportamiento actuales y **ninguna estrategia, stake, preset, protocolo o modo listado aquí debe considerarse soportado en Corridas**. Las únicas estrategias ejecutables hoy son mezcla de rankings y paridad con apuesta fija, descritas arriba.

La instantánea original registró en `webapp/backend/laboratorio/domain/contracts.py` Quiniela80 (100 números, cinco posiciones, pagos 80/8/4/2/1), sistemas del export pos1, coberturas 1/5/10/20/25/30/40/50, un máximo de cinco estrategias por solicitud y modos `all`/`best`. También describió `webapp/backend/laboratorio/domain/selection.py` como implementación de combinaciones/azar/paridad, y `engine/adapter.py` como lector de rankings congelados de 100 valores. Son notas del inventario histórico, no prestaciones de la pantalla Corridas ni una afirmación de compatibilidad actual; no prueban portabilidad a otros universos. El catálogo de referencia en `repo_ref/chance_rank/protocol.py` registraba grillas y familias adicionales; `repo_ref/quiniela_compare.py` excluía explícitamente `logistic`, `tree`, `select_all` por no disponibles y `recent500` como baseline auxiliar.

| ID | Selector de ranking pos1 descrito en la instantánea | Parámetros/semántica registrados en la referencia | Estado histórico |
| --- | --- | --- | --- |
| R01 | `freq_hist` | Frecuencia histórica, scope posición/global y ventana total/20000 en protocolo v1. | Export citado como congelado en la instantánea |
| R02 | `freq_recent` | Ventanas 20/100/500/2000. | Export citado como congelado en la instantánea |
| R03 | `decay` | Vida media 20/100/500/2000. | Export citado como congelado en la instantánea |
| R04 | `cold` | Edad desde aparición, scope posición/cualquiera. | Export citado como congelado en la instantánea |
| R05 | `notebook` | Componentes ponderados 0,45/0,45/0,10; ventanas del protocolo. | Export citado como congelado en la instantánea |
| R06 | `mix` | Grilla de pesos histórico/reciente/edad y ventana si peso reciente > 0. | Export citado como congelado en la instantánea |
| R07 | `transition` | Transición con parámetro `lam` 100/1000. | Export citado como congelado en la instantánea |
| R08 | `carry` | Arrastre por posición origen 1–5 y `lam` 100/1000. | Export citado como congelado en la instantánea |
| R09 | `doubles` | Repeticiones/«dobles», `lam` 100/1000. | Export citado como congelado en la instantánea |
| R10 | `category` | Paridad, bajo/alto, decena, terminación; `lam` 100/1000. | Export citado como congelado en la instantánea |
| R11 | `time` | Hora, día de semana, posición del día; `lam` 100/1000. | Export citado como congelado en la instantánea |
| R12 | `ensemble` | Borda/voto de miembros de referencia. | Export citado como congelado en la instantánea |
| R13 | `select_interpretable` | Elige configuración interpretable usando entrenamiento interno anterior al fold evaluado. | Export citado como congelado en la instantánea |

**«Export congelado/local»** era la etiqueta de la instantánea para rankings guardados bajo su archivo/protocolo original; no significa que hoy se recalculen en producción, que estén disponibles en Corridas ni que tengan eficacia validada. La recomendación histórica era conservar ID, configuración por fold, tie-break y corte causal si se habilitaba recálculo; no aplicar un ranking de 100 números a otro universo sin un nuevo cálculo validado.

| ID | Composición/selector | Contrato y límite |
| --- | --- | --- |
| S01 | `blend` | La descripción histórica contemplaba dos o más sistemas distintos y pesos enteros positivos que suman 100; ejemplo transición 60/fríos 40. Según esa descripción, posición 1…100 daba 100…1 puntos; score(n) = Σ peso% × puntos del ranking para n, orden descendente y empate por número menor. Se distinguía la mezcla de **rankings** de probabilidades pagadoras y liquidación (`domain/selection.py`); no implica que este contrato histórico esté disponible hoy en Corridas. |
| S02 | `random` | Permutación reproducible por semilla y sorteo; baseline/control, no predicción. Prueba determinista propia separada del oráculo de sistemas. |
| S03 | `parity` | Consenso par/impar causal; cobertura histórica fija k=50, no ranking portable ni regla automática de entrada tras racha. |

### Apuesta, entrada y cierre: ejes independientes

| ID | Eje | Estado/requisito |
| --- | --- | --- |
| B01 | `flat` | La instantánea describía un peso entero por número en el motor Quiniela80 de entonces; **no** era el stake del ejemplo E01 ni acredita soporte actual en Corridas. |
| B02 | `ladder` | La instantánea mencionaba una escalera calculada para diez rondas con margen primer premio − cobertura y recuperación +RD$10; `strategy_tests/rules.py` conservaba otra escalera histórica fija (1,3,10,35,123,430,1505,5268,18438,64533) de 50 números y perfil Original70. No son idénticas ni están disponibles hoy en Corridas. |
| B03 | `bold` | La referencia histórica describía stake acotado por saldo/cobertura y brecha a meta bajo primer premio; su cálculo dependía de un margen positivo. No es una opción de stake en Corridas. |
| B04 | Tímida | La referencia E6 mencionaba hasta RD$10 por sorteo para un número; la instantánea anotaba que no figuraba en el enum de staking descrito. |
| B05 | Entrada/salida condicional | La propuesta histórica describía esperar racha, edad, repetición, horario u otra señal causal y decidir entrada o salida sin consumir cupo al esperar. En esa instantánea, E1–E5 eran **candidatas para especificar**, no una implementación del motor; se recomendaba definir reset y horizonte por perfil antes de cualquier implementación. |
| B06 | Fracción fija **registrada como aprobada para el catálogo histórico, no implementada allí** | Stake como fracción configurada `f` del saldo disponible antes del sorteo; exige escala/incremento y redondeo explícito o rechazo, mínimo, topes, exposición simultánea y límite de pérdida del perfil G2. No implica probabilidad de acierto. |
| B07 | Kelly binario **registrado como aprobado para el catálogo histórico, no implementado allí** | Modelo de Thorp, §2: una apuesta pierde una unidad con probabilidad `q=1−p` o gana **neto** `b` unidades por unidad apostada con probabilidad `p`, `b>0`; ventaja `bp−q>0`. Maximizar `p·log(1+bf)+q·log(1−f)` da `f*=(bp−q)/b` en ese modelo, con `0≤f<1` y `0<p<1`. Exige probabilidades estimadas/calibradas independientemente, resultado binario y validación de exposición; no derivar `p` de puntos de ranking. |
| B08 | Kelly fraccional **registrado como aprobado para el catálogo histórico, no implementado allí** | Thorp, §7.3, analiza medio Kelly `0,5 × f*` estimado y advierte sobre incertidumbre y sobreapostar. Factor fraccional explícito sólo con estimación, restricciones, error y sensibilidad declarados; ni medio Kelly ni Kelly pleno garantizan beneficio. |
| L01 | `all`/`best`/`custom` | Suma de coincidencias o mayor multiplicador del mismo número repetido; `custom` sólo tras contrato/aprobación. Premio total = stake × multiplicador, saldo resta costo una sola vez. |
| C01 | Condiciones | La propuesta histórica separaba meta, quiebre, sorteos transcurridos/apostados, fecha/hora y duración simulada; el primer límite activado cerraría la sesión. El contrato técnico F03 de referencia fijaba fronteras exclusivas y prioridad tras liquidar, conservando herencia; sus pruebas constaban como pendientes. |

### Catorce presets citados en la instantánea; reproducción no verificada entonces

La instantánea describía cada nombre bajo `repo_ref/simuladores/<nombre>/ejecutar.py` como un escenario de selector, k y estilo; indicaba que `runner.py` declaraba capital 2000, meta 2800, modo `all`, hashes de entradas y reporte de completas/inconclusas. La inspección histórica de rutas había señalado posibles desajustes entre rutas calculadas desde `repo_ref` y ubicaciones del histórico/NPZ; en aquella revisión **no se ejecutaron los launchers**, así que no se verificaron ni la reproducibilidad ni un posible fallo de ejecución. Reproducción con entradas identificadas y hashes es criterio futuro de aceptación ODD-06, no estado actual. Son escenarios históricos, **no** 14 familias predictivas ni opciones automáticamente recomendadas.

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

Las notas históricas indicaban que `repo_ref/strategy_tests/run_experiments.py` usaba separación por días 60/40 y que `experiments.py` remuestreaba por **día**, 2000 iteraciones, para retorno monetario; advertían no convertir su «prueba ciega» ya usada en nuevo holdout. También registraban que `repo_ref/chance_rank/protocol.py` fijaba walk-forward externo (180 días iniciales, bloques 28, tres bloques internos), warmup 2000 y bootstrap **10000** de bloques de siete días con sensibilidad de 1/14 días; eran protocolos distintos, no parámetros predeterminados del nuevo G5. `quiniela_compare.py` describía sesiones consecutivas y MC uniforme por perfil/modo: las notas recomendaban no mezclar tasas de completas con totales de ventana incluyendo cola.

## Fuentes del catálogo inicial y límites de aplicación

| Fuente/candidato | Lo que sí consta | Lo que **no** autoriza |
| --- | --- | --- |
| NIST, [Random Bit Generation: Documentation and Software](https://csrc.nist.gov/projects/random-bit-generation/documentation-and-software) | El padre reportó recuperación de la página oficial: SP 800-22 rev.1a, abril 2010; recomendación espectral de **un millón de bits** y advertencia de carácter experimental. Fuente para límites/metodología de auditoría binaria; esta unidad no hizo nueva recuperación web. | No aplicar directamente pruebas binarias a sorteos incompatibles ni concluir aleatoriedad/ventaja por un p-valor. |
| Edward O. Thorp, [*The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market*](https://www.eecs.harvard.edu/cs286r/courses/fall12/papers/Thorpe_KellyCriterion2007.pdf), *Handbook of Asset and Liability Management*, vol. 1, ©2006, DOI:10.1016/S1872-0978(06)01009-X | El padre recuperó el PDF primario e inspeccionó §§2 y 7.3. §2 sustenta B07 **sólo** bajo ganancia neta binaria `b`/pérdida completa; §7.3 sustenta el ejemplo de medio Kelly y la cautela por estimación/sobreapostar en B08. Esta unidad no hizo nueva recuperación. | No prueba probabilidades de lotería, independencia, rentabilidad ni transferencia de esa fórmula a carteras de apuestas. |
| [PDF candidato previamente comunicado (Berkeley)](https://www.stat.berkeley.edu/~aldous/157/Papers/Good_Bad_Kelly.pdf) | Contenido **no verificado**; fuente distinta de Thorp inspeccionada. | No atribuirle fórmulas, autoría, conclusiones ni respaldo. |
| Otras familias externas | Sin fuentes, versión, fórmula, parámetros y evidencia validadas aún. | No agregar familias al inventario inicial aprobado sin ficha y aprobación nueva. |

**Límite de aplicación:** `b` en B07 es **ganancia neta** sobre la unidad jugada cuando se gana, no el multiplicador de **pago bruto total** P02. Una cuota que paga `M` en total por unidad y pierde toda la apuesta al fallar daría `b=M−1` sólo para ese evento binario aislado. Una cartera de varios números, posiciones y premios simultáneos/correlacionados tiene otros resultados y exposiciones; no aplicarle automáticamente `f*`, ni usar puntos de ranking como `p`.

**Ficha histórica para futuras incorporaciones ajenas al G1 inicial:** la referencia proponía registrar nombre/ID, clase, editor/URL/fecha/versión, fórmula y derivación para resultados modelados, parámetros/límites, procedencia/calibración de probabilidades, supuestos, compatibilidad, controles negativos, sensibilidad a error/exposición y riesgo de selección retrospectiva. La versión histórica registraba B06–B08 como aprobados para el catálogo, pero no implementados; esa aprobación no equivale a soporte en Corridas. Su eventual ejecución se condicionaba a contratos G2/G5 completos, implementación y evidencia de compatibilidad. La nota no autoriza nuevas familias, afirmaciones de rentabilidad ni Kelly binario sobre carteras correlacionadas.
