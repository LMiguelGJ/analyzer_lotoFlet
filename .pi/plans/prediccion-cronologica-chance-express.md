# Plan: Predicción cronológica integral de Chance Express

## Summary

Construir un laboratorio reproducible de predicción sin dinero: viajar a un punto del historial, emitir rankings 00–99 usando únicamente el pasado, revelar resultados y medir si superan referencias de igual cobertura. Prioridad: **Top-25 del primer puesto en el siguiente sorteo consecutivo**; incluir todos los tamaños, horizontes, familias, controles y análisis secundarios descritos abajo, sin prometer resultados positivos ni prolongar la búsqueda hasta obtenerlos.

Estado: plan para aprobación; no se ejecutaron experimentos ni se crearon archivos de implementación. Interfaz elegida por el usuario: reporte y comando por fecha. Segunda fase supervisada incluida y acotada, independientemente de que los modelos simples mejoren o no.

## Current State Analysis

### Evidencia leída

- `chance_express_history.json`: esquema `metadata` + `sorteos_por_fecha`, filas con `hora`, cinco strings `numeros` y `source_url`. Zona `America/Santo_Domingo`; intervalo 2025-03-05–2026-09-25, 570 fechas solicitadas, 566 con datos y 105.426 sorteos. Cuatro fechas vacías; metadata dice 75 duplicados exactos omitidos durante descarga y **completitud histórica no verificada**. Eso no autoriza a inventar sorteos faltantes ni reconstruir los 75 registros.
- `rng_audit/run_audit.py::load_draws`: ordena fecha/hora y construye `Draws`, pero no valida exhaustivamente timestamps duplicados, continuidad ni procedencia. No usarlo como validación suficiente.
- `rng_audit/lottery_tests.py::Draws`: números `(N,5)`, ordinal del día, minutos del día, weekday y mes. Las pruebas existentes incluyen comparaciones y dependencias; no son un motor predictivo.
- `rng_audit/generators.py::sha256_drbg`: control sano reproducible sobre la misma cronología con rechazo para evitar sesgo módulo. Controles RNG existentes no sustituyen controles específicos de predicción.
- `strategy_tests/experiments.py`: precedentes para rachas, edades, subconjuntos y bootstrap diario. No reutilizar `money` como estadística de aciertos: crear métricas sin premios/apuestas.
- `repo_ref/Testing_Lottery_Predictability.ipynb`, inspeccionado por scout sin ejecutarlo: frecuencias históricas/recientes/atraso, combinación 45/45/10, validación cronológica, holdout y seguimiento. Quina es otro juego; resultados almacenados no prueban precisión en Chance Express. No ejecutar sus celdas de descargas/escrituras.
- No se encontró manifiesto científico raíz en la exploración. El código previo usa NumPy/SciPy y las pruebas anteriores funcionaron, pero se comprobarán versiones al iniciar implementación. `lagacy_loto/requirements.txt` no establece disponibilidad de scikit-learn. No instalar sin nueva autorización.

### Restricciones heredadas

Preservar historial y todos los informes anteriores, `rng_audit/`, `strategy_tests/`, `lagacy_loto/`, notebook original y eliminación ajena `lottery-predictability-monte-carlo`. Sin commits, push, PR, instalaciones ni descargas. Código/tests nuevos en inglés; plan, ODD e informes en español. No modificar criterios/semillas al ver un resultado desfavorable. STR-13 histórico no se resuelve con este estudio.

## Proposed Changes

Todos los archivos `chance_rank/` siguientes son **nuevos propuestos**, no rutas existentes. Reutilizar solo importaciones de estructuras/generación sanas, sin editar los módulos anteriores.

### 1 — `chance_rank/protocol.py`, `chance_rank/data.py`, `chance_rank/test_data.py`

**Qué:** protocolo versionado, carga validada y cronología canónica con procedencia conservada.

**Cómo:**
- Protocolo `chance-rank-v1`; congelar su JSON canónico y hash antes de calcular métricas reales. Incluir toda grilla, semillas, folds, exclusiones, presupuesto y criterios. Si hay que cambiarlo, versionar y rotular resultados previos como tales, nunca sobrescribirlos.
- Validar raíz, fechas, horas, cinco valores enteros 0–99 y URLs cuando existan. Conservar representación `00` en reportes; no confundir repetidos dentro de un sorteo con registros duplicados.
- Duplicados del mismo timestamp y mismos cinco valores: conservar una fila canónica y registrar todas las procedencias. Conflicto de números para mismo timestamp: STOP antes del análisis; no elegir fuente por conveniencia. Filas inválidas: STOP con diagnóstico. Vacíos/huecos: informar, no rellenar ni eliminar días silenciosamente.
- SHA base requerido: `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`. Si difiere, STOP y registrar nuevo alcance antes de resultados.
- Orden canónico `(fecha,hora)`. ID estable basado en timestamp, procedencia y posición canónica, sin depender de números futuros para semillas. Mantener hora local sin convertir a UTC de forma implícita.
- **Elegibilidad principal:** target con predecesor observado exactamente 5 minutos antes y mismo día. Es una pregunta acotada a ese siguiente registro consecutivo, no a cualquier siguiente sorteo. Segmentos se cortan ante cambio de día o hueco. La procedencia de la fila objetivo se usa después para desglosar métricas, no para elegir si emitir pronóstico; no se presupone conocer la fuente del target antes de verlo. Fuera de esto, generar análisis secundario explícito de “siguiente registro disponible”, nunca llamarlo siguiente sorteo real. Horarios inusuales se reportan, no se deduce una agenda completa de la ausencia de filas.
- Frecuencias conservan memoria entre días; ventanas y edades cuentan registros observados. Edades son 'registros desde última aparición', no sorteos realmente transcurridos; indicador de censura si nunca se vio. Rachas/transiciones se reinician en límites de segmento. Al cambiar fuente, reporte separado y sensibilidad de reinicio de estado, sin mezclarla con el resultado principal.

### 2 — `chance_rank/features.py`, `chance_rank/models.py`, `chance_rank/test_models.py`

**Qué:** rankings deterministas y causales para todos los números, sin dinero.

**Contrato:** `predict(context_before_target) -> ranking[100], optional_probabilities[100]`; `update(revealed_draw)` solo después del registro de la predicción. Metadatos permitidos: timestamp objetivo conocido, pasada posición ordinal observada del día, fuente del último registro ya revelado (procedencia objetivo solo tras revelación, no predictor del modelo principal). Prohibido calcular información con números aún ocultos.

**Suavizado condicional exacto:** `P(y|c)=(n(c,y)+lambda*P0(y))/(n(c)+lambda)` con `P0` marginal Laplace pasada. Para transición/arrastre, c es el valor previo del puesto de origen e y el valor del target. Para dobles, cada candidato v usa c=indicador de v repetido en el sorteo previo, éxito y=target igual v y prior marginal P0(v); normalizar las 100 estimaciones para ranking. Categorías: c=(categoría previa,longitud agrupada de racha), y=categoría del target, prior marginal de categorías; probabilidad del valor dentro de categoría proporcional a su conteo pasado+1. Tiempo: c=hora/weekday/grupo de índice, y=valor del target. Ausencia de predecesor válido usa marginal, no contexto ficticio. Mezclas usan percentiles para seleccionar, no probabilidades calibradas.

**Normalización y desempates:** scores de frecuencia suavizados con Laplace 1 por número; para mezclas, transformar cada señal a rango percentil con empates por rango medio, entre 0 y 1. Mayor antigüedad favorece frío. Desempatar ranking por una permutación fija SHA-256 de `chance-rank-v1/tie`, común a todas las familias; no elegir valor por resultados. Desempatar candidatos por ID lexicográfico, declarado en protocolo.

**Grilla cerrada interpretable:**

| Familia | Candidatos exactos | Mecanismo |
|---|---|---|
| Frecuencia histórica | expansión y últimos 20.000 registros | Conteo del puesto objetivo; variante global suma cinco posiciones con su denominador correcto. |
| Frecuencia reciente/caliente | ventanas 20,100,500,2.000 | Ranking de conteos; 'caliente' no se cuenta como modelo independiente si es idéntico. |
| Memoria decreciente | semivida 20,100,500,2.000 registros | Conteos exponenciales actualizados tras observar. |
| Fríos | atraso del puesto objetivo y atraso en cualquiera de los cinco | Censura explícita; sin inferir que el atraso obliga a salir. |
| Mezcla notebook | pesos (.45,.45,.10), ventana reciente 20,100,500,2.000 | Histórica/reciente/atraso normalizados. |
| Mezclas alternativas | pesos múltiplos de .25, no negativos, suma1; mismas cuatro ventanas | 15 triples, incluyendo extremos; deduplicar scores/configuraciones equivalentes antes de ejecución. |
| Transición exacta | lag1 intrasegmento, fuerza de suavizado 100 o1.000 | P(destino\|último valor), con prior de frecuencia marginal pasada. No tabla 100×100 sin suavizar. |
| Arrastre de puestos | origen j=1..5 del sorteo anterior, fuerza100 o1.000 | Para cada target posicional, aprender transición desde origen j. |
| Dobles | condición 'valor duplicado en sorteo previo', suavizado100 o1.000 | Estimar aparición del candidato en puesto objetivo frente a contexto sin doble, regularizando contra marginal. |
| Categorías/rachas | paridad, bajo/alto, decena, terminación; longitud de racha agrupada1,2,3,4,≥5 | Aprender distribución de categoría siguiente; repartir su masa dentro de cada categoría según frecuencia pasada suavizada. |
| Tiempo | hora; día semanal; índice observado del día agrupado0–49,50–99,100–149,≥150 | Distribución por contexto suavizada a marginal, fuerza100 o1.000. Contexto usa solo valores disponibles antes del target. |
| Ensemble | Borda uniforme de histórica, reciente500, fría, transición suavizado1.000, hora suavizado1.000; voto Top25 de esos mismos cinco | Ranking por media de percentiles o votos, desempate por Borda y permutación fija; no pesos aprendidos de test. |

Entrenar versiones posicionales1..5. Para objetivo 'cualquier puesto', usar promedio de percentiles de los cinco rankings posicionales correspondientes, rotulado como sexto objetivo. No asumir cinco valores distintos. Las probabilidades solo se emiten por modelos que realmente las definen; scores/rangos no se convierten en probabilidades mediante una etiqueta.

**Ablaciones predeclaradas:** mezcla notebook sin cada una de sus tres señales, renormalizando pesos restantes; ensemble sin cada miembro (incluido hora); modelo supervisado sin atraso, reciente y tiempo por separado. Ejecutarlas como secundarios aunque la combinación no sea positiva, para no condicionar el conjunto de tests al resultado. Reportar Jaccard Top25 y correlación de indicadores de acierto entre modelos; no sumar sus aciertos como si fueran independientes.

### 3 — `chance_rank/supervised.py`, `chance_rank/test_supervised.py`

**Qué:** segunda fase incluida, regularizada y finita; no búsqueda automática ilimitada.

- Dependencia prevista scikit-learn; comprobar import/version solo tras aprobación del plan. Si falta: dejar fase bloqueada sin instalar ni omitir silenciosamente; una instalación requeriría autorización explícita posterior que levante esa restricción. No implementar librerías caseras para simular equivalencia.
- Regresión logística multinomial L2: C=.01,.1,1; solver lbfgs, max_iter500, tol1e-4. Árbol de clasificación: max_depth3,5; min_samples_leaf200,1.000; random_state derivado del protocolo. No redes ni AutoML.
- Ventanas de entrenamiento10.000 y30.000 targets previos elegibles. Features: frecuencias relativas100,500,2.000 del puesto, EWMA500, edades del puesto y globales con censura, indicadores one-hot de cinco puestos previos, duplicados previos, categorías/rachas, hora y weekday cíclicos. Normalización entrenada solo dentro de cada fit para logística; árbol sin scaler. Clases ausentes conservan su lugar en el vector100; no invertir orden por etiquetas faltantes. Clip1e-12 y renormalizar solo para métricas log-loss.
- Reentrenar al inicio del bloque externo y cada siete días **observados** dentro de él, según agenda fija. Features se actualizan después de cada sorteo. Ajustar parámetros solo en validación interna. Registrar toda convergencia fallida; no aumentar iteraciones post hoc solo para modelos con buen score.
- No forzar probabilidades confiables: reportar Brier multiclase y log-loss contra uniforme/marginal, además de calibración Top25 con diez bins fijos de0 a1, tamaños por bin y sin calibración sobre test. Clasificadores/árboles no implican precisión por sí mismos.

### 4 — `chance_rank/walkforward.py`, `chance_rank/replay.py`, `chance_rank/test_replay.py`

**Qué:** evaluación cronológica anidada y replay auditable.

**Folds externos exactos (índices de días con registros):** días0–179 iniciales; test `[180+28j, min(180+28(j+1),D))` hasta agotar D=566. Quedan13 bloques completos28 días y uno final22 días si la validación mantiene566 fechas. Entrenamiento expansivo anterior al inicio externo. No confundir días observados con días calendario. Fechas concretas quedan en manifiesto antes de observar métricas. Último bloque corto se muestra como tal.

**Selección interna:** para un origen externo d, tres tests consecutivos `[d-84,d-56)`, `[d-56,d-28)`, `[d-28,d)`, cada uno entrenado/estado inicializado exclusivamente con el prefijo anterior. Elegir por promedio Top25 agregado por oportunidades elegibles, no por mejor fold. Primer ajuste de cada fold interno usa solo targets anteriores. Los tres validadores reproducen las mismas actualizaciones causales que la ejecución externa.

**Sistemas comparados:** una variante interna ganadora por familia, más dos selectores automáticos: ganador entre familias interpretables y ganador entre todas las familias incluidas (supervisadas cuando estén disponibles). Se eligen antes de cada bloque; no seleccionar ganador final por el test y llamarlo predicción previa. Fases y manifiesto registran todos los intentos. Para secundarios elegir parámetros por la misma métrica del target posicional correspondiente; K y horizonte no se optimizan sobre resultados externos.

**Horizontes/listas:** K=(1,5,10,20,25,30,40,50); H=(1,5,10,20). Siguiente sorteo actualizado en todos los targets elegibles. Para comparaciones de horizontes, particionar cada segmento contiguo dentro del fold en bloques completos de20 targets con un predecesor disponible: origen antes del primero; puntuar prefijos H del mismo bloque. Descartar remanente menor20 solo de la evaluación multihorizonte, no de H1 principal; reportar cuántos y cómo cambia la población. Rankings congelados en origen o actualizados con cada revelación; mismos targets en ambos modos. No cruzar fold/día/hueco; fuente se desglosa retrospectivamente y no filtra por procedencia futura. H1 actualizado y congelado en mismo origen debe coincidir.

**Warmup/fallback:** 2.000 registros iniciales antes de evaluar candidatos; contexto específico escaso vuelve a marginal suavizada, sin excluir fallos de evaluación. Si falta entrenamiento suficiente de un supervisado, fallback marginal y contarlo. Ningún denominador depende de si el modelo acertó. Fuera de folds externos, comando inspección marca `demostración/no evaluado` y usa mezcla notebook reciente500; no busca parámetros con datos posteriores.

**Reinicio por fuente:** análisis secundario para primera posición y Top25 del selector interpretable, reiniciando estado después de revelar la primera fila de fuente nueva y declarando warmup/N/A; nunca anticipar el cambio usando la fuente del target oculto. Reportar todas las fuentes/períodos sin interpretar como efecto causal de la fuente.

### 5 — `chance_rank/metrics.py`, `chance_rank/inference.py`, `chance_rank/test_metrics.py`

**Referencias:**
- Uniforme analítica K/100 para primer puesto y cada puesto.
- 100 rankings aleatorios uniformes por target/origen, semillas `chance-rank-v1/random/000..099`. Mantener un ranking por realización/origen durante una lista congelada. Mismos rankings usados para todos los K anidados.
- Lista fija: prefijo de permutación SHA-256 `chance-rank-v1/fixed`, independiente de datos.
- Frecuencia del entrenamiento externo congelada todo el bloque.
- Frecuencia reciente500 actualizada causalmente.
- Nulo de orden temporal: permutar **filas completas** dentro de día/fuente, preservando distribución y repetidos dentro de cada sorteo. No usar esos valores para entrenar el modelo real. Diagnóstico de sensibilidad a orden, no p confirmatorio bajo dependencia arbitraria; cualquier p de permutación se etiqueta condicional a intercambiabilidad, sin mezclarlo con inferencia principal.

**Métricas:** aciertoTopK, diferencia absoluta en puntos porcentuales, lift relativo, rango del ganador, MRR, aciertos por horizonte y al menos uno, número de puestos acertados, valores distintos acertados, rachas de fallos y tiempo hasta acierto con censura al terminar segmentos (no descartar esperas inconclusas). Mostrar medianas/percentiles solo si estimables y número censurado; tabla de supervivencia empírica. Para cualquier posición mostrar por separado los tres indicadores; 1-(1-K/100)^5 solo como referencia bajo independencia/uniformidad, no regla exacta del historial.

**Inferencia principal predeclarada:** primera posición, K25,H1 actualizado, targets consecutivos. Comparar cada sistema de familia/selector contra (a) referencia uniforme y (b) frecuencia500 actualizada, emparejados en idénticos targets. Familia primaria = todos los sistemas × ambos baselines conjuntamente, fijados en manifiesto antes de resultados, incluidos supervisados y selectores; Holm unilateral α=.01. Hipótesis 'mejora', no 'cualquier diferencia'. Los contrastes indisponibles mantienen su casilla y contribuyen p=1 al ajuste conservador, pero se publican N/A, no aprobados. No reducir la familia por dependencia ausente; si supervisados están bloqueados, selector 'todas' queda N/A y el trabajo no se declara completo.

- Estimador: suma diferencias de acierto / número targets. Para baseline uniforme usar hit-.25. Bootstrap circular por bloques contiguos de7 días observados **dentro de cada fold/fuente**, conservando todos los targets de días remuestreados y cociente ponderado por oportunidades. 10.000 réplicas, seed `chance-rank-v1/inference`. p bajo nulo calculado con distribución bootstrap centrada, `(1 + # delta_boot-delta_observada >= delta_observada)/(B+1)`; es aproximación dependiente de supuestos de bloques, no exactitud universal. IC percentil99% y95% descriptivo, todos rotulados marginales/no simultáneos.
- Sensibilidad bloques1 y14 días para contrastes primarios, sin seleccionar el ancho que produce significancia. Si signos/evidencia cambian, clasificar inestable. Estrato <28 días: no p propio; sumar descriptivos al agregado si elegible. Si bootstrap degenerado o sin oportunidades: N/A.
- Criterio práctico fijado: mejora≥1 punto porcentual frente a uniforme y reciente500, Holm<.01 en ambos; diferencia positiva en≥70% de folds externos con≥500 targets. Este umbral es decisión operativa, no promesa de detectabilidad. Registrar también señales menores sin declararlas éxito del criterio.
- Reportes secundarios de todos los K, horizontes, puestos, any, ablaciones: tamaños/IC y rankings descriptivos, **sin afirmaciones confirmatorias ni p miles de veces**. Si se desea convertir uno en objetivo principal, nuevo protocolo/datos; no ascenderlo por tener el mejor resultado.
- Detectabilidad: antes de resultados reales, estimar y reportar magnitud detectable para Top25 con N elegible y α corregida mediante aproximación binomial declarada optimista; complementar con controles que miden potencia empírica bajo calendario/dependencia. No interpretar no rechazo como equivalencia.

### 6 — `chance_rank/controls.py`, `chance_rank/test_controls.py`

**Controles sanos:** 20 streams SHA-256 `chance-rank-v1/healthy/001..020`, mismo calendario validado; ejecutar pipeline completo de selección/evaluación principal, no solo el ganador de datos reales. Registrar resultados todos. Comprobación diagnóstica predeclarada: como máximo2/20 streams con algún rechazo primario Holm; si excede, STOP de interpretación y auditoría, no resembrar. Incluso0 rechazos no prueba calibración universal.

**Señales aisladas:** cinco tipos × intensidades q=.02,.10 × semillas `chance-rank-v1/signal/{tipo}/{q}/001..003`. Generar cinco puestos uniformes inicialmente; aplicar a primero solamente y sin superponer tipos:
1. Repetición: con probq copiar primero anterior del mismo segmento.
2. Arrastre: con probq copiar segundo anterior del mismo segmento.
3. Hora: con probq elegir uniforme en decena `hora%10`.
4. Cambio de distribución: a partir del día índice283 con probq elegir00–09; antes elegir90–99 bajo esa misma intervención.
5. Racha: tras≥3 primeros de misma paridad, con probq reemplazar primero por valor uniforme de paridad contraria.

Registrar tasa efectiva de intervención y oportunidades. Todos los modelos y mismos criterios, sin modificar código para cada realización. Intensidad .10: al menos2/3 streams deben mostrar mejora contra uniforme en Top25 por familia relevante (transición, arrastre, hora, EWMA/reciente, categoría), Holm de la familia de cinco tests de control dentro de cada stream a .01. Esto evalúa sensibilidad específica; no exige superar reciente500 para un simple cambio de marginal. Intensidad .02 sirve como curva de potencia informada sin gate. Si falla gate fuerte, reportar limitación/defecto y no prometer que el modelo detectaría señales reales de ese tipo; no aumentar q post hoc.

**Nulo de orden:** 20 permutaciones fijas de filas dentro de día/fuente sobre historia real, fase interpretable primaria completa y sin seleccionar permutaciones convenientes. Reportar cuánto persiste del resultado por marginal frente a dependencia de orden; no suponer que toda señal debe desaparecer (hora/día/frecuencia pueden persistir).

**Fixtures pequeñas obligatorias:** futuro alterado no cambia predicción pasada; prohibir current-target features; secuencia manual de ranking; empate determinista; cold-start; TopK anidado/sin duplicados; targets/métricas posicionales/any con repetidos; H actualizado vs congelado; huecos/días/fuentes; scaler entrenado solo en pasado; inner/outer/purge; cache sin contaminación de fold; conteo de todos intentos; control patrón determinista recuperable; cambio deliberado de resultado no modifica logs previos. RED/GREEN observado antes de funciones correspondientes.

### 7 — `chance_rank/artifacts.py`, `chance_rank/report.py`, `chance_rank/cli.py`, `chance_rank/__main__.py`, tests asociados

**Entradas propuestas exactas:**
- `py -B -m chance_rank validate --input chance_express_history.json`
- `py -B -m chance_rank smoke --protocol chance-rank-v1` (fixtures/sintéticos pequeños, no revisar scores reales)
- `py -B -m chance_rank run --input chance_express_history.json --protocol chance-rank-v1 --stage interpretable`
- `py -B -m chance_rank run --input chance_express_history.json --protocol chance-rank-v1 --stage supervised`
- `py -B -m chance_rank report --run reports/chance_rank_v1`
- `py -B -m chance_rank inspect --run reports/chance_rank_v1 --at "AAAA-MM-DD HH:MM" --model notebook --k 25 --horizon 5` : target indicado, cutoff estrictamente anterior. Primero imprimir lista/cutoff, resultado oculto por defecto; `--reveal` revela resultados y aciertos. Timestamp ausente falla con vecinos sugeridos, no avanza silenciosamente. Para modelo ganador, reutilizar selección congelada de su fold. No usar pesos del final del historial.

**Artefactos nuevos bajo `reports/chance_rank_v1/`:** protocolo congelado y hash, validación de datos, manifiesto/versiones/semillas/folds, inventario de candidatos (incluye intentos fallidos), métricas JSON, resumen Markdown, predicciones y resultados separados comprimidos por fold/familia/target. Rankings uint8 o JSONL gzip con esquema documentado; no guardar un tensor redundante K×H. Cada predicción: ID, target y último observado, modelo/config/hashes, ranking100, probabilidades si existen, fold, modo, horizonte, origen, source y flags. Resultados revelados en archivo enlazado porID; scores de candidatos internos conservados como selección, no como evidencia externa. Rankings de candidatos derrotados en inner no necesitan export completo; ganadores/familias externas y baselines sí.

**Reproducibilidad:** cache por hash de entrada/protocolo/código/fit-cutoff/modelo/seed; checkpoints atómicos, reanudar verifica hashes y no omite intentos negativos. `inspect` reproduce ranking exactamente. No sobrescribir resultados de otra versión. Manifest con estado completo/parcial y motivo por módulo; test no pasado nunca rotulado hecho. Comandos de reporte no recalculan predicciones.

**Informe:** resumen principal primero, familias completas aunque pierdan, tablas K/cobertura, aciertos cortos actualizados/congelados, fuentes/meses, estabilidad, matriz ablation/ensemble, controles, fallos de ejecución, volumen y limitaciones. Distinguir mayor cobertura de mejor selección, diferencia de frecuencia de predictibilidad temporal y clasificación retrospectiva de confirmación prospectiva.

### 8 — Coste, secuencia ODD y revisión

Tras aprobación crear `odd/tasks/chance-rank.md` y espejo; no ahora. Un escritor por vez; revisores de solo lectura pueden operar en paralelo. Unidades:
1. Protocolo/calidad y fixtures.
2. Features/modelos interpretables.
3. Replay/validación anidada y barreras antifuga.
4. Métricas/inferencia/controles.
5. Artefactos/CLI/reporte.
6. Fase interpretable y verificación independiente.
7. Modelos supervisados, disponibilidad, ejecución y revisión.
8. Síntesis final de los14 bloques y registro de siguientes datos necesarios.

Superará400 líneas: dividir revisión por unidades, no una entrega monolítica. Sin commits/PR según restricción vigente; si luego se piden PR, recomendar encadenados.

Antes de cálculo total, inventariar número exacto de candidatos deduplicados y estimar coste con smoke sintético de5.000 filas, sin mirar resultados reales para decidir alcance. Features incrementales, estado/cache por prefijo y evaluación de todos K desde mismo ranking. Máximo2 procesos, un fit supervisado a la vez, presupuesto orientativo máximo4GB de memoria y10GB de artefactos; comprobar espacio antes. Bloque de ejecución máximo2 horas con checkpoint y STOP si no completa, no descartar familias/control para acelerar ni cambiar criterios. Informar estimación total (puede ser extensa por controles y nested fitting), permitir reanudar mismo protocolo. Si presupuesto insuficiente: pedir decisión antes de nueva reducción de alcance. Nunca anunciar duración estimada como tiempo observado.

## Assumptions & Decisions

1. Usuario eligió CLI por fecha/reporte, no UI ni notebook nuevo; supervisados incluidos en fase2 aunque simples no den positivos. Instalación nueva no autorizada.
2. La historia ya fue consultada. Todo resultado actual se rotula retrospectivo/exploratorio fuera de muestra algorítmica, **no confirmación humana ciega**. Próxima confirmación requiere snapshots/predicciones selladas antes de conocer nuevos sorteos y protocolo nuevo con tamaño/horizonte fijados.
3. No garantiza precisión >azar. Éxito del software = pipeline correcto/reproducible/completo y controles evaluados; éxito de hipótesis = criterios estadísticos/prácticos, posiblemente incumplidos. No crear un TODO perpetuo de 'encontrar positivo' ni cambiar semillas para cerrar tareas.
4. No se ejecutan todos los modelos imaginables: la grilla finita de este documento cubre las familias solicitadas y limita el sobreajuste. Cualquier modelo añadido tras ver resultados se registra en nuevo estudio, nunca como predeclarado.
5. Resultados 'sin mejora', 'inconcluso', 'señal exploratoria', 'consistencia histórica' y 'confirmación prospectiva' se distinguen. Esta última no se puede otorgar al JSON actual.
6. Referencia fija/global temporal no debe seleccionarse por rendimiento en test. Score no es probabilidad y más aciertos por seleccionar50 en vez de25 no es superioridad predictiva.

## Verification

- [ ] Fuente SHA y todos los artefactos anteriores conservados; inventario `git status --short` sin cambios ajenos.
- [ ] RED/GREEN y fixtures causales de cada unidad, incluyendo cambiar futuro/target y observar mismas predicciones previas.
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 py -B -m pytest chance_rank strategy_tests rng_audit -q -p no:cacheprovider`.
- [ ] `py -B -m ruff check chance_rank`; diagnósticos LSP de archivos nuevos. Hallazgos previos fuera de alcance reportados, no arreglados silenciosamente.
- [ ] Independiente recalcula métricas desde logs sin llamar al motor; cardinalidadK, nesting, timestamps, ranking100, targets compartidos, denominadores, censura, folds y artefactos coherentes.
- [ ] Exactitud determinista en reanudación e inspección de fechas prefijadas: primer target de primer fold, último target del primer fold, primer target tras cambio de fuente y último target evaluable; prueba antes/después de hueco en fixture.
- [ ] Controles completos o explícitamente pendientes, incluyendo pipeline de selección, no solo un modelo favorable.
- [ ] Tabla final de trazabilidad14/14: pregunta/reglas; replay; calidad; targets; K; baselines; familias; ablaciones; cronología; fixtures; controles; métricas; logs; conclusiones. Cada celda dice implementado/verificado/bloqueado y enlaza archivo/test/resultado; no afirmar 'todo' si supervisados o cualquier familia están bloqueados.
- [ ] Revisión independiente de fuga temporal y estadística antes de interpretar. Revisión nativa según switch/consentimiento y autoridad disponible; no sustituir recibo ausente con aprobación inventada.
- [ ] Conclusión positiva solo con criterio cumplido y limitaciones; no evidencia negativa escondida y no costos/ganancias incluidos.

## Out of Scope

Dinero, martingalas, recomendaciones de apuesta, nuevas descargas o historia de Rapidita, ejecución del notebook de referencia, redes neuronales/AutoML/grillas ilimitadas, aplicación gráfica y nuevos endpoints. Confirmación prospectiva real es trabajo futuro con nuevos datos, no una etiqueta para este backtest.

## Estado de las fases de planificación

1. Exploración: completada con lecturas y scout de solo lectura.
2. Aclaración: completada; CLI/reporte y fase supervisada incluidos según respuestas del usuario.
3. Plan: escrito en este archivo.
4. Notificación: presentar para aprobación; **ejecución pendiente de permiso explícito**. Ninguna fase de planificación omitida.
