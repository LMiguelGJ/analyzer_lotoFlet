---
name: Laboratorio Quiniela 80
description: Taller de simulación financiera; cada corrida es una placa de datos sobre chapa mate.
system: BossFarmer (adaptado a app operativa mobile-first)
platform: web, mobile-first
colors:
  chassis: "#17191a"
  chassis-rail: "#121415"
  rule: "#2e3233"
  legend: "#e6e4de"
  legend-dim: "#9aa097"
  signal: "#1db954"
  alerta: "#e8b12c"
  field-sunken: "#0e1010"
  field-placeholder: "#80857d"
typography:
  display:
    fontFamily: "Archivo Narrow, ui-sans-serif, sans-serif"
    fontSize: "2.6rem / 3.4rem (sm) / 4rem (lg)"
    fontWeight: 600
    lineHeight: 0.9
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Archivo Narrow, ui-sans-serif, sans-serif"
    fontSize: "1.6rem / 2rem (sm)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.16em"
  title:
    fontFamily: "Archivo Narrow, ui-sans-serif, sans-serif"
    fontSize: "1.05rem – 1.3rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.16em"
  numeral:
    fontFamily: "Archivo, ui-sans-serif, sans-serif"
    fontSize: "2.4rem / 3.4rem (sm)"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  body:
    fontFamily: "Archivo, ui-sans-serif, sans-serif"
    fontSize: "0.95rem – 1.1rem"
    fontWeight: 400
    lineHeight: 1.625
  label:
    fontFamily: "Archivo Narrow, ui-sans-serif, sans-serif"
    fontSize: "0.6rem – 0.7rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.16em"
rounded:
  none: "0px"
spacing:
  gutter: "20px / 32px (sm)"
  row: "16px 20px"
  section: "40px – 72px"
  container: "72rem"
  touch: "48px mínimo"
components:
  button-primary:
    backgroundColor: "{colors.legend}"
    textColor: "{colors.chassis}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "14px 16px"
  button-primary-hover:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.chassis}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "14px 16px"
  button-on-signal:
    backgroundColor: "{colors.chassis}"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "14px 20px"
  stamp:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.chassis}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
  plate:
    backgroundColor: "{colors.chassis-rail}"
    textColor: "{colors.legend}"
    rounded: "{rounded.none}"
    padding: "16px 20px"
  plate-chosen:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.chassis}"
    rounded: "{rounded.none}"
    padding: "28px 24px"
  input:
    backgroundColor: "{colors.field-sunken}"
    textColor: "{colors.legend}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "12px 13.6px"
  nav-rail:
    backgroundColor: "{colors.chassis-rail}"
    textColor: "{colors.legend-dim}"
    typography: "{typography.label}"
    padding: "12px 20px"
---

# Design System: Laboratorio Quiniela 80

## Overview

**Creative North Star: "La placa de ensayo del taller"**

Este sistema es el de BossFarmer, conservado tal cual: chapa industrial serigrafiada, fondo mate oscuro,
leyendas condensadas en versalitas espaciadas, raíles finos arriba y abajo y placas rueladas con hairlines
de 1px. Aquí cada simulación es una placa de ensayo; cada dato es una fila término/valor. El verde de marca
entra solo como campo sólido estampado: el sello de meta alcanzada, el paso elegido del asistente, la placa
de la opción escogida, la banda de cierre.

La densidad es de ficha técnica, no de panel de control: pocos elementos, grandes diferencias de tamaño,
hechos en vez de decoración. No hay gradientes, brillo ni sombras; la profundidad es tonal (chasis sobre
raíl) y la estructura la ponen las hairlines. Mundo oscuro único: no hay esquema claro ni selector de tema.

**Mode:** Operate. La persona completa una tarea, así que legibilidad, consistencia y uso con el pulgar
mandan sobre la expresión; la identidad vive en los detalles exactos.

**Key Characteristics:**
- Chapa mate `chassis` con raíles y placas en `chassis-rail`, unidas por hairlines `rule`.
- Una sola voz display: Archivo Narrow 600 en versalitas; el tamaño hace toda la jerarquía.
- Verde `signal` exclusivamente como campo sólido con texto `chassis` encima.
- Esquina viva en todo; cero sombras.
- Filas término/valor (leyenda pequeña a la izquierda, texto corrido a la derecha) como unidad de información.
- Todo en español. Mobile-first.

## Adaptaciones al producto (lo único que cambia respecto de BossFarmer)

Todo lo demás de este documento es BossFarmer sin modificar. Estas son las únicas decisiones nuevas, cada
una con su motivo:

1. **Sin portada pública.** No hay landing ni planes. El Overview de BossFarmer se aplica a las pantallas de
   la app; los tamaños display se reducen (ver tipografía) porque el contenido manda sobre la presentación.
2. **Sin iconos, incluido el nav.** La regla «no iconos» se mantiene entera: navegación, pasos, estados y
   acciones se dicen con leyendas. No existe la flecha de «Acceder» porque no hay acceso.
3. **Marca.** Sin monograma (el BF no se reutiliza): marca tipográfica «LABORATORIO / QUINIELA 80» en
   leyenda, hasta que exista un logo definitivo.
4. **Resultados adversos.** Un resultado que acabó en quiebra («Sin capital») o una corrida fallida usa
   `alerta` como hairline y texto, igual que un error: es el único uso nuevo de ámbar. Nunca decorativo.
5. **Gráficos.** Sin color de datos adicional. Series en `legend` y `legend-dim`, rejilla en `rule`, línea de
   meta discontinua en `legend-dim`, etiquetas directas en leyenda; las series se distinguen por trazo
   (continuo, discontinuo, punteado) y etiqueta, no por tono. El punto final se rotula con texto.
6. **Dinero y signo.** Ganancia y pérdida se distinguen con signo («+» / «−») y texto, en `legend`;
   nunca con verde ni rojo. Cifras siempre tabulares.
7. **Fuentes locales.** Archivo y Archivo Narrow se entregan con la aplicación (archivos propios en
   `public/fonts`, `font-display: swap`); la app funciona sin red y no puede cargar Google Fonts.
8. **Tabla densa.** Tablas con hairlines `rule` entre filas, sin cebra ni radios. En móvil el mismo contenido
   se apila como placas de filas término/valor; la tabla es la mejora de escritorio.
9. **Objetivos táctiles.** Todo control interactivo mide al menos 48 px de alto en móvil (los botones pasan
   a 14px de padding vertical).

## Colors

Neutros cálidos casi negros con una sola tinta de serigrafía clara y un verde que solo existe como campo.

### Primary
- **Verde de estampado** (`signal`): fondo del sello «Meta alcanzada», de la banda de cierre, del paso
  elegido del asistente, de la placa u opción elegida, de la selección de texto y del hover/foco de los
  botones primarios. Siempre con texto `chassis`.

### Secondary
- **Ámbar de aviso** (`alerta`): errores de formulario y resultados adversos (quiebra, corrida fallida),
  como borde de 1px y texto sobre chasis. Nunca decorativo, nunca en marca.

### Neutral
- **Chapa mate** (`chassis`): fondo de página y texto sobre campos verdes o claros.
- **Raíl** (`chassis-rail`): raíles superior e inferior, placas, pista de scrollbar.
- **Hairline** (`rule`): líneas decorativas de 1px (bordes de placa, divisores de fila, borde de botón secundario,
  pulgar de scrollbar, rejilla de gráficos). Excepción de accesibilidad: los límites necesarios de campos
  interactivos habilitados usan `legend-dim` para alcanzar 3:1; los controles activos sobre `signal` usan
  `chassis` en su borde para alcanzar 3:1. Los controles deshabilitados y los errores conservan sus reglas
  existentes. Sin cambios de paleta.
- **Serigrafía** (`legend`): texto principal, fondo de botón primario, anillo de foco, series principales.
- **Serigrafía gastada** (`legend-dim`): texto secundario, leyendas de término, nav inactivo, series secundarias.
- **Chapa hundida** (`field-sunken`) y **marcador** (`field-placeholder`): solo interior y placeholder de campos.

### Named Rules
**The Green Field Rule.** `signal` es un campo, no un acento: fondo sólido con texto `chassis`.
Nunca como texto sobre oscuro, nunca como borde, nunca como línea de gráfico, nunca como brillo.

**The Amber Is For Failure Rule.** `alerta` aparece solo cuando algo falló o terminó mal y la persona debe
enterarse: errores de formulario, quiebra, corrida fallida.

## Typography

**Display Font:** Archivo Narrow (con ui-sans-serif), clase `.legend`: versalitas, `0.16em`, peso 600, interlineado 1.
**Body Font:** Archivo (con ui-sans-serif), peso por defecto.

Ambas autoalojadas (ver Adaptaciones, punto 7).

**Character:** una leyenda de chapa estampada, condensada y espaciada, frente a un texto corrido grotesco y
neutro que explica sin adornar.

### Hierarchy
- **Display** (600, 2.6rem → 3.4rem → 4rem; interlineado 0.9, tracking `0.01em`): el título de pantalla.
  Uno por página.
- **Headline** (600, 1.6rem → 2rem): títulos de sección y de paso del asistente.
- **Title** (600, 1.05rem–1.3rem): nombre de estrategia o de placa, subtítulos de lista.
- **Numeral** (Archivo 400, 2.4rem → 3.4rem, tracking `-0.02em`, cifras tabulares): capital, saldo final,
  neto, meta. La cifra clave de cada resultado.
- **Body** (Archivo, 0.95rem–1.1rem, interlineado relajado): descripciones de 38–48ch.
- **Label** (600, 0.6rem–0.7rem, versalitas `0.16em`): términos de placa, nav, botones, sello, etiquetas de campo.

### Named Rules
**The One Hierarchy Rule.** El tamaño manda; los pesos no cambian para dar énfasis. Toda leyenda es 600,
todo texto corrido es el peso base.

**The Wordmark Tracking Rule.** El nombre de la marca baja el tracking a `0.02em`; los títulos display a `0.01em`.

## Layout

Contenedor centrado de 72rem con márgenes laterales de 20px (32px desde `sm`). Las secciones se separan con
una hairline superior a sangre completa y un ritmo vertical de 40–72px. En móvil todo se apila en una
columna; desde `lg`, el resultado de una corrida se ordena en rejilla asimétrica (`1.1fr / 1fr`): cifras y
gráfico a la izquierda, placa de datos a la derecha.

Las filas término/valor usan una columna de término fija (8.5–9rem) desde `sm`; en móvil el término va
encima del valor. Las placas relacionadas (reglas, métricas, ventana de la corrida) van unidas en un solo
marco. El raíl superior es `sticky` y los anclajes compensan su altura (`scroll-mt-20`). El scroll es suave
salvo con movimiento reducido.

## Elevation & Depth

Sistema plano. No hay sombras en ningún elemento: ni siquiera diálogos, menús o cajones. La profundidad es
tonal: el raíl y las placas (`chassis-rail`) son un escalón más oscuros que la chapa (`chassis`), y los
campos (`field-sunken`) un escalón más, como chapa hundida. Un diálogo o el cajón de cola se distingue por
fondo `chassis-rail`, hairline `rule` y un velo `chassis` al 80% sobre la página; nada flota.

### Named Rules
**The Stamped Not Lifted Rule.** Nada flota. Un elemento se distingue por tono, hairline o campo verde,
nunca por sombra, bisel o brillo.

## Shapes

Esquina viva en todo (0px): botones, placas, campos, sello, etiquetas, chips, barras de progreso, diálogos.
Las formas son rectángulos con borde de 1px `rule` o campos sólidos sin borde. Los grupos relacionados
(pasos del asistente, selector segmentado, filas de datos) comparten marco y se dividen por hairlines
internas en vez de separarse en piezas sueltas.

**Sin iconografía.** No hay iconos de ningún tipo; el significado lo lleva el texto.

## Components

### Buttons
Rectángulos estampados, sin radio, texto en leyenda, alto táctil mínimo de 48 px.
- **Primary:** fondo `legend`, texto `chassis`. Hover y foco: fondo `signal`, con transición de color;
  foco con anillo `legend` de 2px a 3px de separación.
- **Secondary:** transparente con hairline `rule` y texto `legend`; en hover el borde pasa a `legend-dim`.
- **Sobre campo verde:** fondo `chassis`, texto `legend`; hover a `chassis-rail`.
- **Disabled / ejecutando:** opacidad 60% y cursor de espera.
- **Acción principal «Nueva simulación»:** botón primario rectangular fijo sobre el raíl inferior en móvil
  (ancho completo, se oculta durante los asistentes) y en el raíl superior desde `md`. Reemplaza al FAB.

### Chips y sellos
- **Sello de estado:** campo `signal` con leyenda `chassis`, 6px 10px («Meta alcanzada», «Completada»).
  Con `prefers-reduced-motion: no-preference`, una franja `legend` lo recorre una vez al aparecer
  (animación «rodillo», 900ms, `cubic-bezier(0.16, 1, 0.3, 1)`); sin movimiento reducido no hay animación.
- **Etiqueta de estado neutro:** hairline `rule`, leyenda a 0.5rem, sin relleno («En cola», «Pronto»).
- **Etiqueta adversa:** hairline y texto `alerta` («Sin capital», «Fallida»).

### Cards / Containers
Placas de máquina, no tarjetas.
- **Corner Style:** esquina viva (0px). **Background:** `chassis-rail` sobre `chassis`.
- **Shadow Strategy:** ninguna. **Border:** hairline `rule` de 1px; divisores internos igual.
- **Internal Padding:** filas 16px 20px; cuerpo de placa 32–40px vertical, 20–28px lateral.
- **Placa de simulación:** fila de título con sello a la derecha, cuerpo con cifra clave (numeral) y lista
  de datos término/valor, fila de acciones abajo, todo separado por hairlines.

### Inputs / Fields
- **Style:** chapa hundida `field-sunken`, hairline `rule`, texto `legend` en Archivo 1rem, esquina viva.
  Etiqueta en leyenda de 0.6rem `legend-dim` encima.
- **Focus:** el borde pasa a `legend-dim` (3:1 mínimo frente a las superficies adyacentes); con teclado,
  anillo `legend` de 2px a 2px de separación.
- **Error:** un único aviso bajo el campo o formulario, hairline y texto `alerta`, `role="alert"`.
- **Selector segmentado:** opciones en un marco `rule` divididas por hairlines; la elegida se vuelve campo
  `signal` con texto `chassis`; las demás `legend-dim`. Sirve también para pestañas y rangos.
- **Interruptor y casilla:** rectángulos con límite `legend-dim` (o `chassis` al estar activos sobre `signal`);
  activo = campo `signal` con marca de texto. Los demás hairlines decorativos siguen en `rule`.

### Navigation
Móvil: raíl superior `sticky` en `chassis-rail` con la marca tipográfica y, a la derecha, la cola de
trabajos como leyenda con contador; raíl inferior fijo con cuatro leyendas (Experimentos · Estrategias ·
Datos · Ajustes) separadas por hairlines, la actual en `legend` con subrayado de 1px a 6px y el resto en
`legend-dim`. Desde `lg`, las cuatro destinos suben al raíl superior y el raíl inferior se retira.
Sin iconos, sin menú hamburguesa.

### Asistente de cinco pasos (signature)
Cinco celdas en un solo marco unidas por hairlines (Estrategia · Reglas · Alcance · Capital y meta ·
Revisión): el paso actual es campo `signal` con texto `chassis`, los completados `legend`, los pendientes
`legend-dim`. Cada paso es una placa con una decisión; las acciones Atrás / Siguiente van en una fila de
dos botones de 48 px de alto sobre el raíl inferior. La revisión final lista capital, meta, duración y
caveat como filas término/valor antes de confirmar. «Avanzado» es una fila plegable de la misma placa.

### Resultado de una corrida
Una placa con el sello de estado, el numeral del saldo final, las filas de capital inicial, meta, duración,
neto y proveniencia legible (versión del cálculo y fuente en lenguaje cotidiano), y el gráfico de trayectoria en su propia placa. Los identificadores técnicos (huella, nombre de archivo, JSON, semilla) quedan plegados bajo «Detalles técnicos»: se pliegan, nunca se eliminan. La
advertencia fija «Simula, no predice ni garantiza rentabilidad» ocupa una fila `legend-dim` visible en la
misma placa, sin disclosure.

### Ledger de sesiones y apuestas
Tabla de filas separadas por hairlines con la columna de cifras tabulares; contenida en una región con
desplazamiento horizontal y foco de teclado en móvil. «Detalle no almacenado» es una fila de texto neutro,
sin ámbar.

### Estados
Vacío, cargando, error y sin conexión comparten la misma placa: titular en leyenda, una frase en lenguaje
humano y una acción concreta. Error en `alerta`; el resto neutro. Sin ilustraciones.

## Do's and Don'ts

### Do:
- **Do** usar `signal` solo como fondo sólido con texto `chassis` encima.
- **Do** separar y agrupar con hairlines `rule` de 1px y placas `chassis-rail`, con esquina viva.
- **Do** jerarquizar solo por tamaño: leyendas a 600, texto corrido al peso base.
- **Do** presentar información como filas término/valor en leyenda + texto corrido.
- **Do** mantener capital, meta, duración y el caveat «simula, no predice» siempre visibles.
- **Do** decir el estado con texto además de tono.
- **Do** tematizar las superficies del navegador desde la paleta: selección `signal`/`chassis`, scrollbar
  `rule` sobre `chassis-rail`, anillo de foco `legend`, `color-scheme: dark`, `theme-color` `#121415`.
- **Do** mostrar solo hechos verificables; un dato sin definir se escribe «Por definir».
- **Do** respetar `prefers-reduced-motion`: sin rodillo, sin transiciones de color, scroll instantáneo.
- **Do** escribir toda la interfaz en español y entregar fuentes y activos sin depender de la red.

### Don't:
- **Don't** usar `signal` como texto, borde, contorno, línea de gráfico, brillo o degradado.
- **Don't** usar radios, sombras, biseles, cromo, gradientes ni glow, ni siquiera en diálogos o menús.
- **Don't** cambiar pesos para dar énfasis (nada de negritas dentro del texto corrido).
- **Don't** poner antetítulos o kickers sobre los títulos.
- **Don't** inventar precios, métricas, contadores ni testimonios.
- **Don't** añadir iconos de ningún tipo ni reutilizar el monograma BF de BossFarmer.
- **Don't** usar verde o rojo para ganancia o pérdida; usar signo y texto.
- **Don't** ofrecer esquema claro ni selector de tema.
- **Don't** convertir las placas en rejillas de tarjetas sueltas con capturas ni mover lo avanzado fuera
  de la guía: se pliega, nunca se elimina.
- **Don't** tocar backend, contratos, payloads ni semántica financiera por motivos visuales.

## Implementación (regla de sistema)

- Tokens nuevos `--bf-*` con los valores de este documento; los `--md-sys-*` actuales se conservan solo
  como alias temporales que apuntan a ellos, mientras se migra pantalla por pantalla, y desaparecen al terminar.
- Tailwind se configura con la paleta y las dos familias; los radios se fijan en 0 y las sombras se eliminan
  en la configuración, de modo que ningún componente pueda reintroducirlos.
- La migración conserva comportamiento, accesibilidad, rutas, contratos y pruebas existentes; el cambio es
  visual y de estructura de presentación, no funcional.
