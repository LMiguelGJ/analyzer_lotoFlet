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

[U3] Interfaz y documentación en español, importes en DOP. Diseño con Impeccable, tomando https://pi.dev/ como referencia visual ya inspeccionada mediante capturas (ver [UX1] y la especificación UI/UX al final del documento); adaptado a una herramienta de trabajo, no una copia de su contenido o marca.

[U4] Prioridad al navegador de escritorio, con navegación por teclado, etiquetas claras y estados que no dependan exclusivamente del color.

## Operación y técnica

[NF1] Cola de experimentos: se calculan uno por uno, con estado y cancelación; podés seguir usando la web. Una comparación de hasta cinco configuraciones cuenta como un experimento.

[NF2] Los resultados son deterministas con los mismos datos, código y parámetros. Azar utiliza una semilla registrada.

[NF3] No se promete una duración de cálculo sin medirla. La implementación deberá comprobar respuesta de la interfaz, cancelación y consumo de recursos.

[T1] Se reutiliza el motor Python probado y se conservan los 14 ejecutables como referencias de regresión. No se copian sus cálculos financieros en el navegador.

[T2] Propuesta técnica para el MVP: backend Python, frontend web y almacenamiento local SQLite. La elección concreta del framework web queda definida en [T4]; no cambia el alcance funcional.

## Inicio y stack

[T3] Lanzador de Windows por doble clic, después de una preparación inicial. Inicia el servidor local y abre el navegador. Sin instalador autónomo en el MVP.

[T4] Stack elegido: FastAPI + React + TypeScript + Vite + Tailwind CSS + SQLite.

[T5] El servidor sirve el frontend compilado. Node se necesita para desarrollar o compilar, no para el uso cotidiano. Los cálculos financieros permanecen en Python.

[U5] El diseño usa Impeccable y toma pi.dev como referencia visual; no exige copiar su stack ni incorporar sus servicios externos.

## Cancelación

[F13] Al cancelar una comparación, se conservan los resultados de las configuraciones que ya terminaron.

[F14] La configuración interrumpida no se guarda como resultado completo; las restantes quedan identificadas como no ejecutadas por cancelación. La comparación se muestra como incompleta, no como una comparación finalizada normalmente.

[F15] La cancelación se atiende entre pasos de cálculo, sin esperar a que termine toda la sesión. No se permite reanudar el experimento cancelado.

## Azar reproducible

[F16] Semilla configurable y registrada, compartida entre las variantes de azar de una comparación.

[F17] Cada sorteo tiene una permutación reproducible de los 100 números. Una cobertura de 5 toma los primeros cinco; una de 10, los primeros diez.

[F18] La selección aleatoria depende de la semilla y del sorteo histórico, no del orden de ejecución ni de cuándo termina otra configuración.

## Almacenamiento y borrado

[D4] Se permite borrar experimentos y configuraciones mediante confirmación explícita. No hay limpieza automática.

[D5] Borrar una configuración no elimina sus experimentos anteriores: conservan la copia de parámetros con la que se ejecutaron.

[D6] Presupuesto inicial: 5 GB configurables para almacenamiento de experimentos. No incluye el JSON ni los rankings originales.

[D7] La web muestra espacio utilizado y advertencias. Al alcanzar el límite, bloquea nuevas ejecuciones hasta liberar espacio o ampliar el presupuesto; nunca borra resultados automáticamente.

[D8] Supuesto de protección: si una ejecución activa no puede continuar por falta de almacenamiento, se detiene con un estado explícito de error, conservando lo ya finalizado sin etiquetar resultados parciales como completos.

## Exportaciones

[U6] Sin exportación en el MVP. Los resultados se consultan dentro de la web; CSV, JSON e informes descargables quedan fuera de esta versión.

## Navegador y servidor

[NF5] Cerrar el navegador no detiene la cola mientras el servidor local siga abierto. Al volver a abrir la web, se recupera la vista del estado guardado.

[NF6] El lanzador permite detener la aplicación. No se instala un servicio de Windows.

[NF7] Al detenerse el servidor, la ejecución activa queda interrumpida y no se reanuda automáticamente. Los resultados de configuraciones ya terminadas permanecen disponibles.

[NF8] Supuesto para la cola pendiente: los experimentos que todavía no comenzaron permanecen guardados, pero al reiniciar requieren una acción explícita para volver a ejecutarlos. No se inicia trabajo automáticamente al abrir la aplicación.

## Precisiones técnicas propuestas

[T6] El presupuesto de almacenamiento se controla con margen para escrituras y metadatos; no se promete que SQLite ocupe exactamente el tamaño de los resultados visibles. Los umbrales y el comportamiento ante falta de disco se verificarán con pruebas.

[NF9] No se fijan tiempos de ejecución ni capacidad en cantidad de experimentos sin mediciones. La interfaz debe mantenerse utilizable mientras trabaja la cola.

## Evolución hacia el producto completo

[A4] Primera ampliación: juegos configurables —rango, cantidad de posiciones, repeticiones, premios, mínimos e incrementos de apuesta— e importación de JSON con vista previa, mapeo de campos y validación explícita.

[A5] Esa ampliación incluye calcular y guardar rankings compatibles con los datos importados. No reutilizar rankings actuales para otro historial como si fueran válidos.

[A6] Después: evaluaciones masivas, periodos separados para exploración y validación, y análisis de estabilidad.

[A7] Más adelante: acceso remoto y, eventualmente, cuentas multiusuario. No forman parte del MVP.

## Límites que quedarán visibles

[NF4] Los resultados actuales usan datos ya investigados: no son una validación independiente de rentabilidad. La web distinguirá resultados históricos de simulaciones artificiales y no presentará una sesión ganadora como una probabilidad de éxito.

[A8] Tu ejemplo de tres posiciones, pagos 60/10/5 y JSON propio pertenece a la primera ampliación. La mezcla transición 60% + fríos 40%, cobertura 10 y límite de 12 apuestas sí entra en el MVP, usando el juego Q80 existente.

## 🎨 Especificación de UI/UX — laboratorio web (MVP)

Esta sección documenta la propuesta visual y de interacción ya aceptada, en un mismo nivel de detalle que las decisiones anteriores. Es documentación pasiva que consolida una propuesta de interfaz aprobada; no implementa la interfaz ni fija código de aplicación.

### Estado de la referencia visual

[UX1] Se inspeccionaron cuatro capturas de https://pi.dev/ (portada, catálogo de paquetes, tabla de modelos, documentación). Las capturas fueron archivos temporales externos y no se copian ni se anexan a este documento. Se registra evidencia observada, sin extraer CSS ni fuentes exactas. Los valores de esta sección se dividen en dos categorías, distinguidas en cada punto:

- **Propuestos para la app**: definidos en este documento, nuevos, no tomados de pi.dev.
- **Observados en pi.dev**: descripción aproximada de lo visto en capturas, sin valores exactos ni garantía de reproducirlos con precisión.

No se copian logo, marca ni contenido editorial de pi.dev; solo se toma como referencia de estilo visual general.

| Observado en pi.dev (aproximado) | Descripción |
| --- | --- |
| Fondo | Azul-carbón oscuro |
| Textura de fondo | Grilla tenue tipo papel cuadriculado |
| Paneles | Planos, con bordes finos, esquinas casi rectas |
| Texto | Gris pálido, acentos azul apagado |
| Encabezados | Serif itálica, tono editorial |
| Navegación y tablas | Monoespaciada, compacta, mayúsculas en etiquetas cortas |
| Documentación | Navegación lateral izquierda y panel de contexto a la derecha |

### Paleta de color (tokens propuestos)

[UX2] Paleta oscura provisional para el MVP:

| Token | Valor | Uso |
| --- | --- | --- |
| Fondo | `#171e26` | Fondo general de la aplicación |
| Superficie | `#222830` | Paneles y secciones |
| Campo | `#242f3b` | Inputs, celdas editables |
| Texto principal | `#d0d4d8` | Texto de lectura y valores |
| Texto secundario | `#adb5bf` | Etiquetas, ayudas, metadatos |
| Acento | `#7eb3da` | Enlaces, foco, estados activos |
| Separador | `#3b4652` | Bordes finos entre paneles |

[UX3] Objetivo de contraste WCAG AA: 4.5:1 para texto sobre fondo, 3:1 para componentes de interfaz (bordes de control, iconografía funcional). Se etiqueta como **prueba de contraste pendiente de verificación**; esta especificación no declara los valores anteriores como ya conformes, solo como punto de partida a medir en la implementación.

[UX4] Tema único oscuro para el MVP. No se agrega alternancia claro/oscuro; no fue solicitada.

### Tipografía

[UX5] Encabezados editoriales: familia serif itálica (aproximación con Georgia itálica disponible en sistema; no es la fuente exacta de pi.dev, que no fue extraída). Tamaño 32–40px en escritorio, 26–30px en pantallas chicas.

[UX6] Controles, tablas, cifras y navegación: familia monoespaciada de sistema (`ui-monospace`, Consolas como alternativa en Windows), 14–16px. Se evita texto largo en mayúsculas sostenidas; las mayúsculas se reservan para etiquetas cortas de navegación o encabezados de columna.

[UX7] Texto de lectura (descripciones, ayudas, mensajes de estado): tipografía de cuerpo estándar del sistema, 16px, sin itálica ni monoespaciado.

### Espaciado, bordes y ritmo visual

[UX8] Márgenes de página 24–32px; separación entre secciones 24px. El contenido se organiza en secciones simples, no en tarjetas anidadas superpuestas.

[UX9] Radio de borde 0–4px. Sin sombras pronunciadas ni efectos de resplandor ("glow"); los bordes finos son el único recurso para separar paneles.

[UX10] Controles interactivos (botones, campos, filas clicables) con altura 40–44px.

[UX11] Grilla tenue de fondo, estática, únicamente detrás del contenido y sin animarse. No se agregan gráficos decorativos ni visualizaciones ambientales ajenas a los datos reales del experimento.

### Layout global

[UX12] Barra lateral fija en escritorio, ancho 200–220px, con únicamente tres accesos: Experimentos, Configuraciones, Ajustes. Se conserva esta barra lateral ya aceptada; no se reemplaza por la navegación superior observada en pi.dev.

[UX13] Encabezado del área de contenido con el título de la pantalla actual y un indicador discreto del conteo de la cola de experimentos (texto simple, no una barra de progreso ni un panel de métricas).

[UX14] Ancho máximo del contenido principal ~1440px, centrado, con márgenes laterales fluidos en pantallas más anchas.

[UX15] En el asistente de nuevo experimento, el formulario principal convive con un panel de resumen fijo de ~300px de ancho.

[UX16] Puntos de quiebre: por debajo de ~1100px, el resumen del asistente pasa de estar al costado a apilarse debajo del formulario. Por debajo de ~800px, la barra lateral se colapsa detrás de un control explícito (no se oculta sin indicación visible).

[UX17] La interfaz debe seguir siendo utilizable con zoom de navegador hasta 200% y con navegación completa por teclado, sin recortar contenido ni dejar controles inalcanzables.

[UX18] Las tablas anchas (comparación de configuraciones, detalle de apuestas) se desplazan horizontalmente dentro de una región propia y con etiqueta, sin forzar el desplazamiento de toda la página.

### Movimiento

[UX19] Transiciones discretas de 120–180ms para foco, apertura de menús y cambios de estado. Se respeta la preferencia de reducción de movimiento del sistema, desactivando animaciones no esenciales.

### Pantalla 1 — Experimentos (listado)

[UX20] Vista por defecto: listado de experimentos, no un panel de indicadores ni una pantalla de presentación. Título "Experimentos" y acción primaria "Nuevo experimento".

[UX21] Se muestra la tarea activa (si existe) de forma discreta, sin métrica de ganancia global ni progreso/tiempo estimado inventados.

[UX22] Buscador por nombre o estado, con ordenamiento. Tabla con columnas: nombre, cantidad de configuraciones, fecha de creación, estado.

[UX23] Cada fila permite abrir el detalle y un menú de acciones: usar como base (precarga el asistente con esos parámetros), eliminar (con confirmación explícita).

[UX24] Estados a cubrir, cada uno con su propia presentación: vacío (sin experimentos), cargando, sin resultados de búsqueda, servidor desconectado, error genérico. No se combinan ni se sustituyen entre sí.

### Pantalla 2 — Nuevo experimento (asistente de 3 pasos)

[UX25] Resumen persistente visible en los tres pasos: sorteo inicial, capital, meta, límites y cantidad de configuraciones cargadas.

[UX26] Paso 1 — Condiciones: nombre del experimento, sorteo inicial (fecha/hora, solo opciones con ranking disponible), capital, meta (aclarando que representa saldo final, no ganancia adicional, ver [F6]), pagos acumulados o solo mejor premio, límites (máximo de apuestas, de tiempo histórico o ambos) y semilla de azar compartida entre variantes de la comparación (ver [F16]). Información del juego fija y de solo lectura; no hay editor de juego en el MVP.

[UX27] Paso 2 — Estrategias: hasta 5 configuraciones, cada una en un acordeón (una sola expandida a la vez). Tipos disponibles: individual (13 sistemas), azar, par/impar (cobertura fija 50) y mezcla personalizada con pesos 100→1 que deben sumar 100%. Azar y par/impar quedan fuera de la mezcla personalizada. Ante empate de pesos, se aplica la prioridad fija y reproducible de [F3]; no se consulta el resultado futuro.

[UX28] Selector de cobertura (1/5/10/20/25/30/40/50) y de tipo de apuesta (plana/escalera/audaz), con textos de ayuda breves por opción.

[UX29] Guardar/cargar configuración como plantilla reutilizable. Los errores de validación se muestran junto al campo correspondiente y bloquean el avance; no se permite un estado intermedio inválido guardado como válido.

[UX30] Paso 3 — Revisión: tabla de condiciones comunes con enlaces "editar" hacia el paso correspondiente, listado de configuraciones y acción "Agregar a la cola". Si el formulario fue modificado y el usuario intenta salir, se muestra una advertencia de pérdida de cambios; no se promete guardado automático de borradores. Cancelar la vista del asistente no cancela un cálculo que ya fue encolado.

### Pantalla 3 — Detalle de experimento

[UX31] Misma pantalla para los estados en ejecución y completado, sin cambiar de URL al finalizar. Cada configuración conserva su propio estado (en curso, completada, cancelada); cancelar una no altera el estado de las ya finalizadas, y ninguna configuración parcial se presenta como completa.

[UX32] Métricas de resultado en línea (saldo final, delta, apuestas realizadas, motivo de cierre) como texto o tabla simple, no como tarjetas de color tipo panel de indicadores.

[UX33] Gráfico de evolución de saldo con línea de referencia de la meta.

[UX34] Pestañas: "Resultado", "Apuestas", "Parámetros y datos".

[UX35] Reproducción histórica con anterior/reproducir/pausar/siguiente y control de velocidad; el sorteo mostrado durante la reproducción se distingue visualmente de las métricas finales del experimento, para no confundir un estado intermedio con el resultado definitivo.

[UX36] Tabla de apuestas paginada y expandible: fecha/hora, números elegidos (con formato consistente, dos dígitos), apuesta por número, gasto total, los cinco premios posibles, cobro y saldo resultante. Puede incluir una traza ilustrativa de una transición conocida, siempre marcada como ejemplo, nunca presentada como dato real fabricado.

[UX37] Se distingue visualmente el estado de ejecución (en curso/cancelado/completado/historial agotado) del resultado financiero (meta alcanzada/quiebre/sin definir); no se combinan en una sola etiqueta.

### Pantalla 4 — Comparación

[UX38] Hasta 5 configuraciones con las mismas condiciones comunes. Tabla final con saldo, delta, apuestas realizadas y motivo de cierre por configuración.

[UX39] Gráfico compartido con eje temporal real (fecha/hora histórica); cada serie termina en el punto donde finalizó su propia sesión, sin prolongarse artificialmente. Las series se distinguen por etiqueta y patrón de línea, no solo por color.

[UX40] Control para mostrar/ocultar series individuales. Enlace desde cada fila hacia el detalle de esa configuración.

[UX41] Si hay menos de 5 configuraciones completas, se muestra un aviso "N/5" explícito. Los valores faltantes se representan con guion, nunca con cero. No se calcula ni sugiere una "mejor estrategia" ni una probabilidad de éxito. Sin exportación en el MVP (ver [U6]).

### Pantalla 5 — Configuraciones (biblioteca)

[UX42] Listado con búsqueda/filtro y acciones "nueva", "usar", "editar", "eliminar" (con confirmación explícita). Reutiliza el mismo editor de estrategias del paso 2 del asistente.

[UX43] Eliminar una configuración no elimina los resultados de experimentos ya ejecutados con ella (ver [D5]). "Usar" abre el asistente precargado con esos parámetros.

### Pantalla 6 — Ajustes

[UX44] Almacenamiento: espacio utilizado sobre el presupuesto configurable (5 GB por defecto, ver [D6]/[D7]), con advertencias explícitas al acercarse al límite. Se distingue visualmente espacio en disco, presupuesto configurado y espacio recuperable al compactar SQLite; no hay borrado automático, solo acciones manuales explícitas.

[UX45] Datos de origen (universo/fuente, período, hashes, versión de código) en una sección de solo lectura, expandible para ver detalle. Sin opción de importar datos ni agregar juegos en el MVP.

[UX46] Información de conexión local (estado del servidor, versión) y guía para detener la aplicación desde el lanzador (ver [T3]/[NF6]); no se presenta como un servicio administrable.

### Cola global de experimentos

[UX47] Se presenta como un cajón (drawer) que se abre bajo demanda, no como un panel permanente en pantalla.

[UX48] Muestra el experimento activo y los pendientes en orden serial, con opción de inspeccionar o cancelar cada uno; no hay reordenamiento por arrastre.

[UX49] Un experimento pendiente que quedó sin ejecutar tras un reinicio requiere una acción explícita para iniciarse (ver [NF8]); no se reinicia automáticamente ni se ofrece "reanudar" un cálculo interrumpido.

[UX50] Pérdida de conexión con el servidor: aviso persistente pero discreto, sin afirmar que el cálculo se detuvo si eso no fue confirmado. Al reconectar o recargar, la vista se actualiza con el estado autoritativo del servidor.

[UX51] Las acciones destructivas (eliminar experimento/configuración, cancelar) usan un diálogo de confirmación con foco atrapado dentro del diálogo, cierre con Escape y devolución de foco al control de origen al cerrarlo.

[UX52] Las confirmaciones exitosas se muestran como aviso breve y transitorio; los errores persistentes se muestran en línea, junto al control afectado, no solo como notificación flotante. No se usan modales para la edición ordinaria de campos.

### Checklist de aceptación (verificación visual pendiente en navegador)

Esta sección es una especificación de diseño, no una interfaz terminada. Cada punto queda pendiente de comprobación en la implementación real:

- [ ] Paleta y contraste ([UX2]–[UX4]) medidos con una herramienta de contraste real, no solo declarados.
- [ ] Tipografías ([UX5]–[UX7]) legibles en encabezados, controles y cuerpo, sin depender de reproducir la fuente exacta de pi.dev.
- [ ] Layout responsivo ([UX12]–[UX18]) probado en escritorio, en los puntos de quiebre declarados y con zoom 200%.
- [ ] Pantalla de Experimentos ([UX20]–[UX24]): estados vacío, cargando, sin resultados, desconectado y error se ven y se distinguen entre sí.
- [ ] Asistente de nuevo experimento ([UX25]–[UX30]): validaciones bloquean el avance, la advertencia de pérdida de cambios funciona, el resumen se mantiene visible.
- [ ] Detalle de experimento ([UX31]–[UX37]): estado de ejecución y resultado financiero no se confunden; la reproducción histórica no se muestra como resultado final.
- [ ] Comparación ([UX38]–[UX41]): aviso "N/5" visible cuando corresponde, valores faltantes con guion, sin exportación.
- [ ] Configuraciones ([UX42]–[UX43]): eliminar una configuración no borra resultados de experimentos anteriores.
- [ ] Ajustes ([UX44]–[UX46]): estado de almacenamiento, advertencias y guía de detención visibles y correctos.
- [ ] Cola global ([UX47]–[UX52]): cancelación, reinicio explícito, aviso de desconexión y confirmaciones destructivas funcionan con foco y teclado correctos.
- [ ] Accesibilidad transversal: navegación completa por teclado, foco visible, estados no dependientes exclusivamente del color (ver [U4]).
