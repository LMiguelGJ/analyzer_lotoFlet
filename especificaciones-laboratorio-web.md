# 📋 Resumen de decisiones y supuestos para la especificación

## MVP: laboratorio web local

[A1] Web para explorar estrategias históricas con el motor existente. No realiza apuestas ni predice sorteos en vivo.

[A2] El MVP mantiene el juego actual: números 00–99, cinco posiciones, repeticiones permitidas y premios 80/8/4/2/1. Permite pagos acumulados o solo el mejor premio por número.

[A3] Usa el JSON y los rankings actuales, sin modificarlos. Juegos configurables, otros JSON y nuevos cálculos de rankings quedan para la evolución posterior.

[P1] Uso personal en tu computadora, desde el navegador, sin cuentas. El servicio escucha únicamente en la computadora local, no queda publicado en Internet.

## Configuración y selección

[F1] Podés elegir un método individual, azar, tu par/impar o una mezcla personalizada.

[F2] Las mezclas combinan rankings mediante pesos que suman 100%: 100 puntos al primero, 99 al segundo… 1 al último. Los puntos no son probabilidades.

[F3] La mezcla usa los 13 sistemas de ranking disponibles. Azar y par/impar quedan como alternativas separadas. Ante empate, se conserva una prioridad fija y reproducible, sin consultar el resultado futuro.

[F4] Coberturas disponibles: 1, 5, 10, 20, 25, 30, 40 y 50. Tu par/impar original conserva su cobertura de 50; no inventamos cómo seleccionar subconjuntos.

[F5] Apuestas plana, escalera y audaz, con las reglas actuales adaptadas a cada cobertura. Mínimo RD$1 por número y sin gastar más que el saldo; los importes son pesos enteros.

[F6] Capital inicial y meta configurables. La meta representa saldo final, no ganancia adicional: capital 2.000 y meta 2.800 equivale a buscar +800. Se rechazan configuraciones incompatibles antes de ejecutar.

## Sesiones y comparación

[F7] Una sesión detallada o comparación de hasta cinco configuraciones, con la misma fecha inicial, capital, meta y límites.

[F8] Elegís un sorteo inicial con ranking disponible. Los huecos posteriores no generan apuestas, pero consumen tiempo histórico.

[F9] Podés fijar máximo de apuestas, máximo de minutos históricos o ambos. Con ambos, se detiene al alcanzar el primero.

[F10] Estados finales separados: meta alcanzada, quiebre, límite de sesión o historial agotado. Quiebre significa no poder financiar la próxima apuesta prescrita; no siempre implica saldo cero.

[F11] Propuesta de regla temporal: el reloj comienza en el sorteo inicial; no se apuesta en un sorteo cuya hora alcance o supere el límite de minutos. Una apuesta ya realizada se liquida antes de evaluar su desenlace.

[F12] Reproducción visual con avanzar, reproducir y pausar, además de ejecución completa. No espera cinco minutos reales entre sorteos. Pausar la visualización no cambia el cálculo.

## Resultados y persistencia

[D1] Se guardan configuraciones y experimentos terminados: parámetros, identificación de datos y código, semillas cuando correspondan, resultados y detalle de apuestas.

[D2] Un experimento terminado se consulta sin recalcular. Modificar una configuración y volver a ejecutarla crea otro experimento; no altera el anterior.

[D3] No se recuperan ejecuciones interrumpidas tras cerrar la aplicación. Al reiniciar, se identifican como interrumpidas, sin presentar resultados parciales como completos.

[U1] Espacio de experimentos con listado, detalle y vista propia de comparación.

[U2] Cada detalle muestra números elegidos, apuesta por número, gasto total, resultados reales, cobro, saldo, fecha y hora; incluye gráfico del saldo y motivos de terminación.

[U3] Interfaz y documentación en español, importes en DOP. Diseño con Impeccable, tomando https://pi.dev/ como referencia visual, pendiente de inspección; adaptado a una herramienta de trabajo, no una copia de su contenido o marca.

[U4] Prioridad al navegador de escritorio, con navegación por teclado, etiquetas claras y estados que no dependan exclusivamente del color.

## Operación y técnica

[NF1] Cola de experimentos: se calculan uno por uno, con estado y cancelación; podés seguir usando la web. Una comparación de hasta cinco configuraciones cuenta como un experimento.

[NF2] Los resultados son deterministas con los mismos datos, código y parámetros. Azar utiliza una semilla registrada.

[NF3] No se promete una duración de cálculo sin medirla. La implementación deberá comprobar respuesta de la interfaz, cancelación y consumo de recursos.

[T1] Se reutiliza el motor Python probado y se conservan los 14 ejecutables como referencias de regresión. No se copian sus cálculos financieros en el navegador.

[T2] Propuesta técnica para el MVP: backend Python, frontend web y almacenamiento local SQLite. La elección concreta del framework web se fundamentará en la fase técnica; no cambia el alcance funcional.

## Evolución hacia el producto completo

[A4] Primera ampliación: juegos configurables —rango, cantidad de posiciones, repeticiones, premios, mínimos e incrementos de apuesta— e importación de JSON con vista previa, mapeo de campos y validación explícita.

[A5] Esa ampliación incluye calcular y guardar rankings compatibles con los datos importados. No reutilizar rankings actuales para otro historial como si fueran válidos.

[A6] Después: evaluaciones masivas, periodos separados para exploración y validación, y análisis de estabilidad.

[A7] Más adelante: acceso remoto y, eventualmente, cuentas multiusuario. No forman parte del MVP.

## Límites que quedarán visibles

[NF4] Los resultados actuales usan datos ya investigados: no son una validación independiente de rentabilidad. La web distinguirá resultados históricos de simulaciones artificiales y no presentará una sesión ganadora como una probabilidad de éxito.

[A8] Tu ejemplo de tres posiciones, pagos 60/10/5 y JSON propio pertenece a la primera ampliación. La mezcla transición 60% + fríos 40%, cobertura 10 y límite de 12 apuestas sí entra en el MVP, usando el juego Q80 existente.
