# Plan: claridad visual conservando la identidad de Pi

> Estado: APROBADO por el usuario para implementación con ODD e Impeccable en cada fase, incluida compatibilidad tablet. La puerta de Plan Mode quedó resuelta. Seguimiento: `odd/tasks/claridad-visual-inspirada-en-pi.md`. No implica autorización nueva de publicación.

## Summary

Reorganizar la interfaz del laboratorio para que preparar datos, configurar una simulación e interpretar su resultado sean tareas comprensibles sin interpretar detalles internos. No imponer un único orden transversal: la preparación de datos es independiente; el clásico conserva Condiciones → Estrategias → Revisar, y cada flujo con perfil conserva su secuencia real. Conservar íntegramente la identidad oscura, azul y tipográfica actual inspirada en https://pi.dev/; tomar del ejemplo Boomerang únicamente jerarquía, contención y claridad, no su paleta blanca ni su composición de marketing.

## Current State Analysis

Exploración de solo lectura por scout y spot-check del padre. No se ejecutaron pruebas ni se modificó código en esta planificación.

- Proyecto existente: React 18, TypeScript, React Router, Vite, Tailwind y Vitest; scripts `test`, `typecheck`, `build` en `webapp/frontend/package.json`. No requiere nuevas bibliotecas ni cambio de framework.
- `webapp/frontend/src/styles/tokens.css:21–40`: identidad y límites de contraste explícitos. `styles/index.css` contiene primitivas compartidas `.field`, `.control`, `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-destructive`, `.section-header`, `.data-list`, `.metric-grid` y tablas. Lectura adicional confirmó altura base de 42px, borde funcional, primario azul relleno, secundario transparente y destructivo con texto subrayado; deben unificarse y completar estados sin inventar otro sistema. El comentario de adopción puede estar desactualizado: hay páginas que ya utilizan estas clases.
- `webapp/frontend/src/App.tsx:14–98` y `components/Shell.tsx:22–27,111–135`: navegación, títulos y cola. Mantener rutas y acceso a funciones; no convertir la app en landing.
- `pages/data/index.tsx:232,358`: importación de historial y biblioteca; importación avanzada ya usa `<details>`. No presentar como funcionalidad nueva una separación existente: mejorar su jerarquía y acceso.
- `pages/new-experiment/index.tsx:458–538`: asistente clásico de tres pasos, Condiciones / Estrategias / Revisar, con resumen responsive.
- `pages/new-experiment/ProfileExperimentPage.tsx`: versiones 1–4, formulario continuo, no asistente por pasos.
- `pages/new-experiment/ProfileBatchPage.tsx:331`: cinco pasos existentes: Historial y perfil / Estrategias / Condiciones / Validación / Simulación. `batch-model.ts` conserva reglas y referencias congeladas.
- `pages/experiments/index.tsx:87`: filtros, orden, tabla y paginación; estados vacío y sin coincidencias diferenciados.
- `pages/experiments/DetailPage.tsx:255,295`: Resultado / Apuestas / Parámetros y datos; métricas financieras, trayectoria y reproducción. `ComparisonPage.tsx:116–124` conserva métricas por resultado y comparaciones.
- `pages/settings/index.tsx`: cuota lógica, diagnósticos de almacenamiento, identificadores desplegables y acceso para agentes. Hay separación semántica existente; el problema observado es su lenguaje y protagonismo visual.
- Auditoría anterior: siete capturas y navegación real por Experimentos, Estrategias, Datos y Ajustes. Asistentes, detalle y comparación no se comprobaron en vivo en esa auditoría. Detector sin hallazgos no demuestra buena UX ni accesibilidad completa.
- Git observado: rama `stage`, gitlink eliminado ajeno y `docs/Capturas/` no rastreado. No modificar esas superficies ni otros cambios ajenos.

## Proposed Changes

### Brief de diseño — Impeccable, modo Operate

- **Trabajo del usuario:** configurar y comprender simulaciones históricas. Priorizar a quien llega por primera vez sin penalizar a quien ya usa datos, estrategias o diagnósticos avanzados. Estas personas son supuestos de diseño, no una investigación de usuarios completada.
- **Tesis visual:** primero la decisión o desenlace, luego el contexto que lo explica, finalmente la auditoría. La identidad oscura/azul actual es la autoridad; Boomerang aporta contención, no un mundo visual nuevo.
- **Carga cognitiva:** una decisión principal por paso; separar grupos por significado, no convertir cada campo en tarjeta. Una pantalla puede tener cero o una acción dominante; no inventar un CTA en una vista de lectura ni repetir botones primarios por fila.
- **Densidad:** preservar tablas cuando ayudan a comparar; limitar párrafos de ayuda a una idea y medida aproximada de 65–75 caracteres por línea. Tipografía estable en rem, no títulos fluidos ni tamaños de marketing. Valores financieros con cifras tabulares y alineación consistente.
- **Primer momento de prueba:** al cerrar la unidad 1, revisar shell y controles reales de una pantalla representante con estados normal/foco/deshabilitado/carga. No propagar una base visual fallida al resto. Luego revisar cada unidad en navegador, no sólo al final.

### Composición decidida por superficie

| Superficie | Primera lectura | Información secundaria | Acción dominante máxima |
| --- | --- | --- | --- |
| Datos sin historiales | Cómo importar el primer historial y requisito de perfil | Biblioteca vacía breve; CSV/perfiles avanzados | Importar historial; durante confirmación, confirmar importación en lugar de otro primario paralelo |
| Datos con historiales | Biblioteca y contexto de los historiales | Importación y configuración avanzada como regiones diferenciadas | Importar historial; acciones de filas secundarias |
| Clásico / V5 | Decisión del paso actual con campos relacionados | Resumen compacto y opciones avanzadas | Continuar/Validar según paso; iniciar sólo cuando corresponde y es admisible |
| Perfil V1–V4 | Formulario agrupado por reglas, historial y condiciones | Opciones menos frecuentes y explicación técnica | Iniciar sesión cuando la validación vigente lo permita |
| Resultados / comparación | Resultado financiero disponible y advertencias de completitud | Evolución y apuestas; parámetros/auditoría al final | Puede no haber primario: explorar no debe competir con el desenlace |
| Estrategias vacías / pobladas | Cómo crear la primera / lista reutilizable | Editor sólo cuando se abre; búsqueda/paginación sólo si son útiles | Nueva estrategia guardada; al editar, Guardar sustituye al primario de creación |
| Experimentos | Identificar la ejecución guardada y su estado | Filtros agrupados, fechas y acciones en fila | Nuevo experimento |
| Ajustes | Capacidad lógica, avisos y setting editable | Diagnóstico y acceso de agentes separados | Guardar cambios cuando hay cambios; refrescar/consultar siguen secundarios |

**Responsive:** conservar breakpoints comprobados de shell: navegación a 800px y composición amplia a 1100px. Una columna cuando falta espacio; resumen lateral sólo en composición amplia, sin cambiar orden DOM/foco para fingir jerarquía. Tablas pueden desplazarse horizontalmente dentro de una región identificada; nunca hacer scroll horizontal de toda la página. Tamaño táctil se decide por capacidad de puntero, no por ancho.

**Estabilidad:** el orden biblioteca/importación depende de vacío o poblado tras resolver la carga; no saltar secciones durante búsqueda, polling ni cambios de página. No cambiar de posición un control enfocado. Loading conserva estructura con placeholder/skeleton discreto sin nuevos efectos; errores tienen causa/recuperación disponibles y no se disfrazan de biblioteca vacía.

### Unidad 1 — Base visual compartida, sin reemplazar identidad

**Archivos:** `webapp/frontend/src/styles/index.css`, `components/Shell.tsx`, `components/Shell.test.tsx`. `styles/tokens.css` se usa como autoridad, sin alterar paleta, familias tipográficas ni valores existentes.

- **Qué:** establecer lectura consistente: título, contexto imprescindible, acción principal, contenido, información secundaria. Adoptar las primitivas compartidas adecuadas y agrupar por proximidad antes de agregar paneles.
- **Por qué:** cambiar colores no resolvería jerarquía ni redundancias; la base actual ya tiene contraste documentado.
- **Cómo:** serif sólo para encabezados; cuerpo y controles en sans existente. Mantener estilos numéricos existentes con cifras tabulares, incluida mono en valores financieros cuando ya aporte lectura/alineación; reservar mono en prosa para identificadores/datos técnicos, sin prohibición global que contradiga `.metric-value` o `.data-list-numeric`. Limitar el énfasis azul a navegación activa, foco y acciones importantes. Mantener cola accesible, sin hacerla el centro de todas las pantallas. No cambiar su funcionamiento ni quitar su acceso. Preservar textura estática discreta existente; no agregar gradientes, video, glassmorphism, 3D, tarjetas anidadas o animación continua.
- **Resultado:** un patrón repetible de página y un sistema consistente de botones y controles, sin rediseño de marca ni dependencias externas.

#### Botones y controles — especificación transversal

**Superficies:** primitivas en `styles/index.css`, adopción en los archivos ya enumerados en las unidades 2–6 y en `components/Shell.tsx`. No crear una biblioteca nueva ni modificar comportamiento/API para resolver una apariencia. Probar interacción en los tests de cada consumidor; verificar geometría/contraste en navegador, no sólo por presencia de clases.

##### Jerarquía de botones

| Variante | Uso | Tratamiento |
| --- | --- | --- |
| Principal | Siguiente acción de la tarea: Importar historial, Continuar, Iniciar simulación, Guardar cambios | `.btn-primary`, azul actual relleno y texto oscuro; como máximo una acción dominante por pantalla o paso activo; acciones de fila nunca primarias |
| Secundaria | Atrás, Cancelar, Actualizar estado | `.btn-secondary`, fondo neutro/transparente y borde funcional existente |
| Terciaria | Ver parámetros, abrir detalles, ayuda contextual | Enlace o botón de texto según semántica; sin marco de botón grande; área de interacción suficiente |
| Destructiva | Eliminar estrategia o experimento | `.btn-destructive`, verbo y objeto explícitos, diferenciada por texto/peso además de color; nunca confundir con continuar ni introducir rojo decorativo. Preservar confirmación y consecuencias reales |

- Mantener radio 4px, cuerpo sans y escala tipográfica actual. Altura base 42px para controles comunes; con `(any-pointer: coarse)` aplicar variante `min-height: 2.75rem` (44px) y ancho mínimo equivalente en objetivos compactos, sin cambiar el token global. Esto incluye tablets anchas y equipos híbridos; una ventana angosta con mouse no prueba interacción táctil. Checkbox/radio conservan marca compacta, pero la etiqueta amplía el área táctil. Separar acciones para evitar toques accidentales; no superponer hit areas.
- Padding, alineación vertical y separación entre botones consistentes. Ancho según contenido en desktop; en móvil agrupar sin desbordar, dejando la acción principal en una fila clara y evitando una hilera de botones diminutos. Texto largo debe envolver sin recorte ni pérdida del nombre accesible.
- Navegación usa enlaces reales; ejecutar una acción usa botones. `type="button"` fuera del submit explícito. No convertir enlaces en botones que pierdan apertura en nueva pestaña o URL.
- Nombres específicos en español: evitar botones llamados sólo «Acciones», «OK» o iconos sin contexto. En filas, conservar nombre accesible que identifique el objeto. No agregar una dependencia de iconos; si se reutilizan iconos existentes, son complementarios al texto y no la única explicación.

##### Estados de interacción

- Definir default / hover / pressed / focus-visible / disabled / busy de forma consistente. Hover/pressed mediante las superficies, bordes y acento existentes, sin sombras llamativas ni cambio de dimensiones; usar transiciones explícitas de color/borde de 150ms, no `transition-all`, escalado, rebote ni movimiento de la interfaz.
- Preservar anillo de foco azul de 2px con offset de 2px. No quitarlo con `outline-none`; no depender del hover para descubrir una acción. Enlaces/controles seleccionados deben tener señal de estado además de color.
- Disabled usa semántica nativa y tratamiento moderado, no una opacidad aplicada a todo el formulario que vuelva ilegible su contenido. La razón para no poder continuar se muestra cerca cuando no sea evidente. No mostrar un botón de continuar activo si la validación actual exige bloqueo.
- Busy conserva ancho y etiqueta comprensible («Guardando…», «Validando…»), bloquea envíos duplicados según la lógica actual y comunica estado con `aria-busy`/status cuando corresponda. No inventar porcentajes ni indicar éxito antes de respuesta confirmada. Mantener manejo de resultados inciertos y reintento idempotente.

##### Campos y selectores

- Inputs, selects, textarea y búsqueda deben compartir fondo de campo, borde funcional, tipografía, espaciado de label/ayuda/error y foco. Textarea usa altura acorde al contenido, no el `height` fijo de `.control`; no aplicar la regla de inputs a todos los elementos indiscriminadamente.
- Etiqueta persistente arriba; ayuda opcional corta y error junto al campo, enlazados con `aria-describedby`; `aria-invalid` cuando corresponda. Error identifica qué corregir sin borrar lo escrito ni depender del rojo.
- Separar visualmente sufijo/unidad («RD$», «números», «sorteos») del valor editable sin cambiar serialización, parsing monetario, precision, límites, type o semántica vigente. Usar `inputmode` sólo si es compatible con el parser actual; no añadir formateo de miles dentro del valor ni truncar con `Number` importes exactos.
- Conservar selects/checkbox/radio nativos y su comportamiento de teclado; no reemplazarlos por dropdowns custom ni convertir selección exclusiva en multiselección. Mostrar etiqueta de la opción, no IDs técnicos, cuando ya hay información adecuada.
- Tabs, disclosures, navegación, paginación y menú de acciones deben mostrar activo/abierto/seleccionado, con ARIA y teclado acordes a la semántica existente. Reutilizar `<details>/<summary>` donde ya corresponda. Si falla validación en un disclosure cerrado, abrirlo, preservar valores, mostrar el error vinculado y llevar foco al primer campo inválido dentro del flujo de validación existente; no robar foco ante polling o actualizaciones de fondo. Advertencias que impidan o condicionen una decisión siguen visibles fuera del panel. Menús/diálogos no deben quedar recortados por contenedores con overflow; conservar mecanismos existentes de foco, Escape y restauración.
- Probar que estas variantes no hereden en SVG, gráficos o canvas; mantener reglas por clase, no estilos globales que alteren todas las etiquetas `button`, `input` o elementos gráficos sin control.

**Orden de implementación:** establecer variantes/estados en la unidad 1; adoptar y probar por pantalla en las unidades siguientes, sin una edición masiva de todas las clases que impida revisar regresiones.

### Unidad 2 — Datos: elegir, importar y configurar sin mezclar tareas

**Archivos:** `webapp/frontend/src/pages/data/index.tsx`, `DataPage.test.tsx`, `DataPageHistory.test.tsx`, `ProfileEditor.tsx`, `ProfileEditor.test.tsx`.

- **Qué:** separar Biblioteca de historiales / Importar historial / Opciones avanzadas.
- **Cómo:** con biblioteca poblada, mostrar historiales y sus acciones primero; vacía, destacar importar el primero. Acción primaria «Importar historial». Mostrar formato soportado y validación junto al archivo; no ocultar confirmaciones necesarias. Mantener CSV/mapeo/perfiles dentro de secciones secundarias explícitas, reutilizando el disclosure existente. La selección de perfil necesaria para validar no desaparece ni se vuelve implícita.
- **Copy:** conservar que importar no ejecuta una simulación ni calcula pagos. Si no hay continuación ejecutable, explicar por qué, sin enlaces que prometan un flujo inexistente.
- **No cambiar:** bytes importados, confirmación/promoción, versiones, monedas, premios, cuotas, validaciones ni datos reales.

### Unidad 3 — Asistentes: reducir decisiones simultáneas

**Archivos:** `webapp/frontend/src/pages/new-experiment/index.tsx`, `NewExperimentPage.test.tsx`, `ProfileExperimentPage.tsx`, `ProfileExperimentPage.test.tsx`, `ProfileBatchPage.tsx`, `ProfileBatchPage.test.tsx`.

- **Qué:** reorganizar dentro de los pasos existentes; no inventar un único asistente que confunda capacidades distintas.
- **Clásico:** conservar tres pasos y orden probado. Agrupar Condiciones por significado y resumir sólo lo necesario; mantener mezcla compatible 60/40 donde ya existe.
- **V5:** conservar cinco pasos, validación servidor y referencias congeladas. Cada paso tiene una decisión dominante; opciones avanzadas bajo acceso explícito. Mantener borrador, reintento e identidad de envío.
- **V1–V4:** conservar formulario continuo, dividido visualmente en Reglas del sorteo / Historial / Selección / Condiciones de la sesión. No convertirlo en otro wizard ni añadir capacidad de mezcla.
- **Resumen:** desktop compacto, no un segundo formulario paralelo; móvil en bloque desplegable antes de acciones. En revisión mostrar configuración completa y legible. Etiquetas persistentes, ayuda corta junto al campo; «Continuar» principal y «Atrás» secundaria donde corresponda.
- **Modelo de lectura:** distinguir reglas del juego, cómo se seleccionan números y cuándo termina la sesión. No cambiar valores predeterminados, límites, parsing monetario o payloads por razones estéticas.

### Unidad 4 — Resultados y comparación: interpretar antes de auditar

**Archivos:** `webapp/frontend/src/pages/experiments/DetailPage.tsx`, `DetailPage.test.tsx`, `ComparisonPage.tsx`, `ComparisonPage.test.tsx`, `webapp/frontend/src/components/FinancialMetrics.tsx`, `RunTrajectory.tsx`, `RunTrajectory.test.tsx`, `ComparisonChart.tsx`, `ComparisonChart.test.tsx`.

- **Qué:** orden Resultado económico → saldo/capital/contexto → motivo de cierre → evolución → apuestas/reproducción → parámetros/procedencia.
- **Cómo:** mantener tabs existentes y enlaces. Dar protagonismo al neto, saldo final, capital inicial y apuestas, con etiquetas y cifras próximas. Estado de ejecución distinto del desenlace económico. Evitar repetir nombre/estado tres veces; conservar contexto al cambiar estrategia.
- **Métricas:** presentar cada concepto una vez donde sea equivalente, sin asumir que delta de saldo y neto son iguales para todos los contratos. Mantener desglose financiero completo en sección secundaria. Usar los valores del backend, moneda y precisión actuales. Nunca fabricar agregados entre resultados incompatibles ni recategorizar cierre.
- **Mapa de verdad financiera:** `api/types.ts` y `components/FinancialMetrics.tsx` son autoridades de proyección existentes: `result.final_balance` → Saldo final; `result.delta` → Cambio respecto del inicio; `result.net` → Neto; `result.wagered` → Total apostado; `result.paid` → Total pagado; `result.return_per_wagered` → Retorno por peso apostado; `result.roi` → ROI neto; `result.max_drawdown` → Máximo drawdown absoluto. Apuestas/capital/moneda se obtienen de los campos específicos del contrato vigente, usando formatters actuales, sin fórmula alternativa. Si `net` falta, mostrar N/A con contexto y el delta disponible por separado; no llamar neto al delta. No convertir ratios a porcentajes en este cambio visual. Valores ausentes/null no se vuelven cero.
- **Resultado parcial o ausente:** mostrar `status`, `complete/completion` y `stop_category/stop_reason` de V5 según corresponda; advertencia de incompleto/no disponible en la primera lectura. El cierre se presenta con el mapper existente, no inferido de texto ni equiparando ventana operativa a fin de historial. Si `result` es null, comunicar el estado y no renderizar métricas ficticias ni un gráfico de saldo cero.
- **Comparación:** misma jerarquía financiera por estrategia; conservar diferencias, gráficos y límites de compatibilidad existentes. No tocar mapeo de ordinals ni lógica gráfica por decoración.
- **Detalles técnicos:** IDs, hashes, revisiones y metodología accesibles pero secundarios. Aviso de simulación histórica visible y sin reiteración innecesaria; no sustituirlo por promesas de predicción o rentabilidad.

### Unidad 5 — Biblioteca de estrategias y lista de experimentos

**Archivos:** `webapp/frontend/src/pages/configurations/index.tsx`, `ConfigurationsPage.test.tsx`, `webapp/frontend/src/pages/experiments/index.tsx`, `ExperimentsPage.test.tsx`. Ruta `/configuraciones` resuelta desde `App.tsx`; cuerpo real `ConfigurationsPage:29–198` leído. Búsqueda actual filtra sólo la página cargada; paginación actual corresponde al total remoto, no a una búsqueda global. Preservar y explicitar esa semántica, sin ampliar API.

- **Estrategias:** en vacío real, explicación breve y acción de creación ya soportada; sin búsqueda/paginación inútiles. Si hay elementos pero el filtro no encuentra coincidencias, mantener búsqueda y ofrecer limpiar filtro. No confundir ambos estados.
- **Terminología:** usar «Estrategia guardada» en navegación, búsqueda, estados y confirmaciones. El modelo distingue `configuration.name` y `configuration.strategy.name`: mantener ambos, rotularlos «Nombre guardado» y «Nombre de la estrategia» en el editor con ayuda breve; no fusionar ni sobrescribir campos. No renombrar contratos ni IDs internos.
- **Experimentos:** acción principal «Nuevo experimento»; filtros agrupados y acciones en su fila. Mejorar jerarquía del nombre/contexto/estado con datos ya disponibles. No añadir llamadas por cada fila ni crear columnas financieras que el listado actual no suministra; el resultado económico permanece en detalle si no está disponible en el contrato.

### Unidad 6 — Ajustes: necesidad del usuario antes del diagnóstico

**Archivos:** `webapp/frontend/src/pages/settings/index.tsx`, `SettingsPage.test.tsx`.

- **Qué:** lectura Capacidad de la aplicación / Cambiar límite / Diagnóstico técnico / Acceso para agentes.
- **Cómo:** comenzar por capacidad lógica usada/restante con unidades legibles; valores exactos en detalles. Etiquetar explícitamente que la cuota de admisión no es espacio físico libre. Mantener advertencias que condicionan una operación; no esconderlas en diagnósticos.
- **Alcance del input:** conservar el campo exacto y su parsing actual para evitar nueva conversión/roundtrip; mejorar etiqueta y ejemplo, separando su explicación técnica. No introducir selector GB ni conversión de unidades en esta unidad visual.
- **Diagnóstico:** SQLite/WAL/SHM, bytes y hashes desplegables agrupados; preservar datos, errores y actualización real.
- **Seguridad:** acceso de agentes separado, secreto oculto por defecto, sin lectura automática, cambios de credencial ni degradación de no-store/foco/confirmaciones.

## Assumptions & Decisions

### Identidad visual fijada

| Rol | Token actual preservado |
| --- | --- |
| Fondo | `#171e26` |
| Superficie | `#222830` |
| Campo | `#242f3b` |
| Texto | `#d0d4d8` |
| Texto secundario | `#adb5bf` |
| Acento azul | `#7eb3da` |
| Separador decorativo | `#3b4652` |
| Borde funcional | `#6c7f92` |

Conservar Georgia/Times para títulos, system-ui para cuerpo y mono existente para diagnóstico; espaciado base y controles actuales (`28px`, `24px`, `4px`, `42px`, `150ms`). Nunca sustituir el borde funcional por el decorativo: sus requisitos de contraste son distintos. La autoridad cromática son estos tokens del proyecto, no colores inferidos del HTML de pi.dev.

### Ejemplo aportado por el usuario

Usarlo en el plan como ejemplo de agrupación y lectura, NO como sesión nueva ni configuración ejecutable prometida:

#### Reglas del sorteo

- Números posibles: 00–99.
- Posiciones por sorteo: 3; repeticiones permitidas.
- Premios por posición: 60 / 10 / 5.
- Apuesta mínima por número: RD$1.

#### Selección

- Transición 60% + fríos 40%.
- Cobertura: 10 números.

#### Condiciones de la sesión

- Capital: RD$2.000.
- Meta de saldo: RD$2.800.
- Duración máxima: 12 sorteos.

**Compatibilidad:** el perfil permite universo/posiciones/repeticiones/premios personalizados, pero V1–V4 y el editor V5 no admiten esa mezcla ponderada. El clásico admite 60/40, pero usa reglas fijas de cinco posiciones y premios 80/8/4/2/1. Por tanto la combinación exacta NO es ejecutable en un solo flujo actual. No sustituir silenciosamente premios, selector, posiciones o estrategia. El plan visual no incorpora ese motor; si se necesita ejecutar la combinación, requiere alcance funcional separado y aprobación. No mostrar el ejemplo como preset seleccionable ni como resultado existente.

### Límites de ejecución futura

- Sin cambios de backend, contratos, motores, estrategias, cuotas, referencias/oráculo o sesiones históricas.
- Preservar todas las rutas; `/experimentos/nuevo/sesion` debe seguir abriendo y refrescando sin 404.
- UI española y términos consistentes; no textos Boomerang ni claims comerciales nuevos.
- Sin nuevas librerías, fuentes remotas obligatorias, logos, video o canvas.
- No modificar `rng_audit/`, gitlink eliminado, `docs/Capturas/`, tareas/reviews históricos ni otros cambios ajenos.
- No crear tareas de implementación ODD ni ejecutar cambios hasta aprobar el plan. Después de aprobación, relectura del plan, tareas/mirror y un escritor a la vez.
- Trabajo multiárea probablemente supera 400 líneas: separar seis unidades revisables; recomendar PRs encadenadas si se autoriza publicación, no un único diff gigante. Commits/push de esta nueva fase requieren la autorización aplicable; la entrega pasada no los autoriza automáticamente.

## Verification

Todas las verificaciones siguientes son PROPUESTAS y no ejecutadas en esta fase.

### Automatizada por unidad

Desde `webapp/frontend`:

- Base: `npm run test -- --run src/components/Shell.test.tsx src/lib/tokens.test.ts`.
- Datos: `npm run test -- --run src/pages/data/DataPage.test.tsx src/pages/data/DataPageHistory.test.tsx src/pages/data/ProfileEditor.test.tsx`.
- Asistentes: `npm run test -- --run src/pages/new-experiment/NewExperimentPage.test.tsx src/pages/new-experiment/ProfileExperimentPage.test.tsx src/pages/new-experiment/ProfileBatchPage.test.tsx`.
- Resultados: `npm run test -- --run src/pages/experiments/DetailPage.test.tsx src/pages/experiments/ComparisonPage.test.tsx src/components/RunTrajectory.test.tsx src/components/ComparisonChart.test.tsx`.
- Biblioteca/listado: `npm run test -- --run src/pages/configurations/ConfigurationsPage.test.tsx src/pages/experiments/ExperimentsPage.test.tsx`.
- Ajustes: `npm run test -- --run src/pages/settings/SettingsPage.test.tsx`.
- `npm run typecheck` tras cada unidad con cambios TS; `npm run build` al integrar. No instalar dependencias si falta un runner: reportar bloqueo.
- Cuando hay conducta comprobable modificada, observar RED → cambio → GREEN (ej.: ocultar paginación sólo en vacío real; disclosure/foco). Reordenado puramente visual: screenshots y regresiones relevantes; no inventar RED para CSS pasivo.
- Detector Impeccable una vez sobre las superficies finales cambiadas; no usar resultado vacío como aceptación visual.

### Navegador y criterios observables

- [ ] Conservar colores/tipos actuales; comparación visual antes/después, sin nueva identidad blanca.
- [ ] En cinco segundos se reconoce propósito, dato principal y siguiente acción de cada pantalla.
- [ ] Botones principal/secundario/terciario/destructivo distinguibles; máximo una acción dominante por pantalla/paso, ninguna en filas; vistas de lectura no obligadas a tener CTA. Etiqueta explícita y consistencia entre pantallas.
- [ ] Controles nativos operables con Tab/Shift+Tab, Enter/Espacio y flechas según corresponda; foco visible, etiquetas vinculadas y estados accesibles sin depender de color/hover.
- [ ] Default/hover/pressed/focus/disabled/busy/error revisados en navegador; carga sin saltos de ancho ni envíos duplicados, errores preservan valores, disabled con motivo cuando necesario.
- [ ] Objetivos táctiles de al menos 44×44px con puntero coarse, también en tablets anchas/híbridos; reflow se verifica por ancho independientemente del puntero. Acciones separadas, textos largos y zoom 200% sin clipping; controles nativos siguen usables.
- [ ] Contraste de texto al menos 4.5:1 (3:1 para texto grande aplicable) y bordes/foco funcionales al menos 3:1 donde corresponde, incluidos nuevos estados; colores actuales preservados. No asumir que el contraste del estado default prueba hover/pressed.
- [ ] Parsing de importe/cuota/pesos, límites, exclusividad de selectores, payloads y comportamiento de submit intactos; valores exactos no se cambian por formateo visual.
- [ ] Biblioteca vacía vs búsqueda sin resultados claramente diferenciadas.
- [ ] Importación exige la validación/confirmación actual y no dispara ejecuciones.
- [ ] Classic mantiene tres pasos; V5 cinco; V1–V4 formulario por secciones. Borrador, retry y envío intactos.
- [ ] Resultado económico prominente, ejecución/cierre separados; valores idénticos al registro guardado.
- [ ] Técnicos accesibles sin inundar la vista inicial; advertencias necesarias y completitud visibles. Error de validación dentro de panel cerrado abre el panel, conserva valores, enfoca el campo inválido y anuncia el error; actualización de fondo no roba foco.
- [ ] Loading/error/vacío no se confunden; orden de regiones estable durante polling/búsqueda, overlays no recortados y ningún control enfocado cambia de lugar.
- [ ] Neto ausente, resultado null e incompleto cubiertos con fixtures; ningún importe ausente se convierte en cero ni delta en neto. Cierre/formatters financieros actuales preservados.
- [ ] Abrir/refrescar rutas incluyendo sesión, detalle y comparación. Sólo lectura sobre sesiones reales; pruebas de creación/importación en fixtures/entorno temporal, nunca DB del usuario.
- [ ] Viewports 390, 768, 800, 1100 y 1440 px, incluyendo lados de cada breakpoint; combinar ancho angosto/amplio con punteros fine/coarse. Zoom 200%, teclado, foco, Escape cuando corresponde y reduced motion. Orden DOM/foco coherente con lectura visual; sin overflow global.
- [ ] Poblado/vacío/loading/error, nombres largos, moneda y cifras extremas sin clipping.
- [ ] No abrir/copiar credenciales reales ni tocar configuración para una prueba visual.
- [ ] Reportar todos los fallos, omisiones y checks pendientes. Aceptación manual sólo con evidencia del usuario; revisión anterior escalada no se transforma en aprobación.

## Out of Scope

Rediseño de marca, landing comercial, incorporar Boomerang, soporte nuevo de mezcla ponderada para perfiles personalizados, simulaciones nuevas reales, cambios históricos, eliminación de tests vigentes, migraciones/contratos, autenticación nueva, cambios de modelos/agentes/configuración, instalaciones, commit/push automático o repetir revisiones anteriores para inventar aprobación.

## Próximo paso — implementación autorizada

Usuario aprobó aplicar el plan, preservar la paleta y cubrir tablets. No hay preguntas de producto pendientes para este alcance visual; el ejemplo incompatible permanece ilustrativo. Exploración, aclaración y planificación completadas; puerta de aprobación resuelta. Ejecutar por unidades con tracking ODD e Impeccable, comprobando la base antes de propagarla. Estado y evidencia reales en `odd/tasks/claridad-visual-inspirada-en-pi.md`; no interpretar los checks propuestos de este plan como resultados ya observados.
