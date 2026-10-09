---
name: BossFarmer
description: Taller que fabrica bots; la web pública es su placa de identificación.
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
    fontSize: "3.4rem / 5rem (sm) / 6rem (lg)"
    fontWeight: 600
    lineHeight: 0.88
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
    fontSize: "3.4rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  body:
    fontFamily: "Archivo, ui-sans-serif, sans-serif"
    fontSize: "0.95rem – 1.2rem"
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
  section: "56px – 96px"
  container: "72rem"
components:
  button-primary:
    backgroundColor: "{colors.legend}"
    textColor: "{colors.chassis}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
  button-primary-hover:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.chassis}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.legend}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "12px 16px"
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
  plan-plate-chosen:
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

# Design System: BossFarmer

## Overview

**Creative North Star: "La placa de identificación del taller"**

La web pública es chapa industrial serigrafiada: fondo mate oscuro, leyendas condensadas en
versalitas espaciadas, raíles finos arriba y abajo, y placas de máquina ruladas con hairlines de 1px.
Cada proyecto es una placa; cada dato es una fila término/valor. El verde de marca entra solo como
campo sólido estampado: el sello «En producción», la banda de cierre, la placa de plan elegida.

La densidad es de ficha técnica, no de folleto: pocos elementos, grandes diferencias de tamaño,
hechos en vez de cifras. No hay capturas, métricas, gradientes, brillo ni sombras; la profundidad
es tonal (chasis sobre raíl) y la estructura la ponen las hairlines. Portada con scroll corto:
primera vista, Proyectos, A medida (encargos: texto, pasos numerados y botón a Telegram) y
cierre verde; `/planes` con placas de plan, orden de compra y dos listas ruladas.

**Key Characteristics:**
- Chapa mate `chassis` con raíles y placas en `chassis-rail`, unidas por hairlines `rule`.
- Una sola voz display: Archivo Narrow 600 en versalitas; el tamaño hace toda la jerarquía.
- Verde `signal` exclusivamente como campo sólido con texto `chassis` encima.
- Esquina viva en todo; cero sombras.
- Filas término/valor (leyenda pequeña a la izquierda, texto corrido a la derecha) como unidad de información.
- Todo en español.

## Colors

Neutros cálidos casi negros con una sola tinta de serigrafía clara y un verde que solo existe como campo.

### Primary
- **Verde de estampado** (`signal`): fondo del sello «En producción», de la banda de cierre, de la
  placa de plan elegida, de la opción activa del selector de plan, de la cabecera de la orden recibida,
  de la selección de texto y del hover/foco de los botones primarios. Siempre con texto `chassis`.

### Secondary
- **Ámbar de aviso** (`alerta`): solo errores de formulario, como borde de 1px y texto sobre chasis.
  Nunca decorativo, nunca en marca.

### Neutral
- **Chapa mate** (`chassis`): fondo de página y texto sobre campos verdes o claros.
- **Raíl** (`chassis-rail`): raíles superior e inferior, placas, pista de scrollbar.
- **Hairline** (`rule`): toda línea de 1px (bordes de placa, divisores de fila, borde de botón
  secundario, pulgar de scrollbar).
- **Serigrafía** (`legend`): texto principal, fondo de botón primario, anillo de foco.
- **Serigrafía gastada** (`legend-dim`): texto secundario, leyendas de término, nav inactivo.
- **Chapa hundida** (`field-sunken`) y **marcador** (`field-placeholder`): solo interior y
  placeholder de campos de formulario.

### Named Rules
**The Green Field Rule.** `signal` es un campo, no un acento: fondo sólido con texto `chassis`.
Nunca como texto sobre oscuro, nunca como borde, nunca como brillo.

**The Amber Is For Errors Rule.** `alerta` aparece solo cuando algo falló y el usuario debe corregirlo.

## Typography

**Display Font:** Archivo Narrow (con ui-sans-serif), clase `.legend`: versalitas, `0.16em`, peso 600, interlineado 1.
**Body Font:** Archivo (con ui-sans-serif), peso por defecto.

Ambas autoalojadas con `next/font/google` en `layout.tsx`.

**Character:** una leyenda de chapa estampada, condensada y espaciada, frente a un texto corrido
grotesco y neutro que explica sin adornar.

### Hierarchy
- **Display** (600, 3.4rem → 5rem → 6rem; en `/planes` 3rem → 4.5rem; interlineado 0.88–0.9, tracking `0.01em`):
  el nombre «Boss/Farmer» y el título de página. Uno por página.
- **Headline** (600, 1.6rem → 2rem; banda de cierre 2rem → 2.8rem con tracking `0.04em`): títulos de sección.
- **Title** (600, 1.05rem–1.3rem): nombre de proyecto en la placa, nombre de plan, subtítulos de lista.
- **Numeral** (Archivo 400, 3.4rem, tracking `-0.02em`, cifras tabulares): cupo mensual del plan.
- **Body** (Archivo, 0.95rem–1.2rem, interlineado relajado): frases de 38ch en la primera vista,
  46–48ch en descripciones.
- **Label** (600, 0.6rem–0.7rem, versalitas `0.16em`): términos de placa, nav, botones, sello, etiquetas de campo.

### Named Rules
**The One Hierarchy Rule.** El tamaño manda; los pesos no cambian para dar énfasis. Toda leyenda es 600, todo texto corrido es el peso base.

**The Wordmark Tracking Rule.** El nombre escrito junto al monograma baja el tracking a `0.02em`; los títulos display a `0.01em`.

## Layout

Contenedor centrado de 72rem con márgenes laterales de 20px (32px desde `sm`). Las secciones se
separan con una hairline superior a sangre completa y un ritmo vertical de 56–96px. La primera vista
de la portada es una rejilla asimétrica (`1.1fr / 1fr` desde `lg`) alineada abajo: nombre, frase y dos
acciones a la izquierda; placa de datos a la derecha. En móvil todo se apila en una columna.

Las filas término/valor usan una columna de término fija (8.5–9rem) desde `sm`; en móvil el término
va encima del valor. Las placas de plan son tres columnas unidas desde `md` y una pila en móvil,
siempre dentro de un solo marco. El raíl superior es `sticky` y los anclajes compensan su altura
(`scroll-mt-20`). El scroll es suave salvo con movimiento reducido.

## Elevation & Depth

Sistema plano. No hay sombras en ningún elemento. La profundidad es tonal: el raíl y las placas
(`chassis-rail`) son un escalón más oscuros que la chapa (`chassis`), y los campos de formulario
(`field-sunken`) un escalón más, como chapa hundida. La separación la hacen hairlines de 1px.

### Named Rules
**The Stamped Not Lifted Rule.** Nada flota. Un elemento se distingue por tono, hairline o campo verde, nunca por sombra, bisel o brillo.

## Shapes

Esquina viva en todo (0px): botones, placas, campos, sello, etiqueta «Pronto». Las formas son
rectángulos con borde de 1px `rule` o campos sólidos sin borde. Los grupos relacionados
(placas de plan, selector segmentado, filas de datos) comparten marco y se dividen por hairlines
internas en vez de separarse en piezas sueltas.

**Monograma BF.** Nueve rectángulos en rejilla de trazo 76 sobre lienzo 1100×660 (5:3). Componente
`logo.tsx` en web y panel; `<symbol id="marca-bf">` en `apps/api/templates/base.html`. Se pinta con
`currentColor`, siempre `legend` sobre chasis o raíl, dimensionado por la altura (`h-5 w-auto` en el
raíl). Junto al nombre escrito va con `decorativo` para no leerse dos veces. Favicons e imagen para
compartir: marca `legend` sobre campo `chassis`, sin radios.

**Icono.** La única figura dibujada además del monograma es la flecha de entrada del botón «Acceder»
(13px, trazo 2, remates cuadrados e ingletes vivos, `currentColor`), heredada de la landing original.

## Components

### Buttons
Rectángulos estampados, sin radio, texto en leyenda.
- **Shape:** esquina viva (0px).
- **Primary:** fondo `legend`, texto `chassis`, 12px 16px (variantes de 10px a 14px vertical según contexto).
- **Hover / Focus:** el fondo pasa a `signal` con transición de color; foco con anillo `legend` de 2px a 3px de separación.
- **Secondary:** transparente con hairline `rule` y texto `legend`; en hover el borde pasa a `legend-dim`.
- **Sobre campo verde:** fondo `chassis`, texto `legend`; hover a `chassis-rail`.
- **Disabled / enviando:** opacidad 60% y cursor de espera.

### Chips
- **Sello «En producción»:** campo `signal` con leyenda `chassis`, 6px 10px. Al cargar, con
  `prefers-reduced-motion: no-preference`, una franja `legend` lo recorre una vez de izquierda a
  derecha (animación «rodillo», 900ms, `cubic-bezier(0.16, 1, 0.3, 1)`, 300ms de retardo). Sin
  movimiento reducido no hay animación; el sello es visible desde el principio.
- **Etiqueta «Pronto»:** hairline `rule`, leyenda a 0.5rem, sin relleno de color. Marca una sección aún no disponible.

### Cards / Containers
Placas de máquina, no tarjetas.
- **Corner Style:** esquina viva (0px).
- **Background:** `chassis-rail` sobre `chassis`.
- **Shadow Strategy:** ninguna (ver Elevation & Depth).
- **Border:** hairline `rule` de 1px; divisores internos igual.
- **Internal Padding:** filas 16px 20px; cuerpo de placa de proyecto 32–40px vertical, 20–28px lateral.
- **Estructura de placa de proyecto:** fila de título con sello a la derecha, cuerpo con descripción y
  lista de datos término/valor, fila de acciones abajo, todo separado por hairlines.

### Inputs / Fields
- **Style:** chapa hundida `field-sunken`, hairline `rule`, texto `legend` en Archivo 1rem, esquina viva.
  Etiqueta en leyenda de 0.6rem `legend-dim` encima.
- **Focus:** el borde pasa a `legend-dim`; con teclado, anillo `legend` de 2px a 2px de separación.
- **Error:** un único aviso bajo el formulario, hairline y texto `alerta`, `role="alert"`.
- **Selector segmentado:** opciones en un marco `rule` divididas por hairlines; la elegida se vuelve campo `signal` con texto `chassis`; las demás `legend-dim`.

### Navigation
Raíl superior `sticky` en `chassis-rail` con hairline inferior: monograma y nombre a la izquierda;
enlaces en leyenda de 0.62rem `legend-dim` que pasan a `legend` en hover. La página actual va en
`legend` con subrayado de 1px a 6px. Las secciones futuras se muestran deshabilitadas con la etiqueta
«Pronto». Cierra con el botón primario «Acceder». En móvil el nombre escrito se oculta y queda el
monograma. Raíl inferior igual de sobrio, con enlaces en leyenda de 0.6rem.

### Placa de plan (signature)
Tres columnas en un solo marco unidas por hairlines: nombre del plan (title), cupo mensual (numeral),
«cuentas al mes» (label), precio, descripción, filas término/valor de beneficios (A la vez,
Comunidad, Soporte, Nuestros proxies…) y botón «Elegir este plan». Los beneficios vienen
escritos de la API (`BENEFICIOS` en `shared/suscripciones.py`): uno nuevo aparece solo en cada placa.
Al pedir, la columna entera se enciende como campo `signal` con texto `chassis` (transición de
fondo y color de 260ms, `cubic-bezier(0.16, 1, 0.3, 1)`, sin transición con movimiento reducido),
el botón pasa a fondo `chassis` con «Elegido» y el plan queda marcado en el selector del formulario.
Los precios salen de la API (`/api/planes`); la web nunca los escribe a mano.

### Orden recibida
Marco `rule` con cabecera de campo `signal` («Orden #N recibida» en leyenda `chassis`), cuerpo con
texto corrido y botón primario «Continuar en Telegram».

## Do's and Don'ts

### Do:
- **Do** usar `signal` solo como fondo sólido con texto `chassis` encima.
- **Do** separar y agrupar con hairlines `rule` de 1px y placas `chassis-rail`, con esquina viva.
- **Do** jerarquizar solo por tamaño: leyendas a 600, texto corrido al peso base.
- **Do** presentar información como filas término/valor en leyenda + texto corrido.
- **Do** tematizar las superficies del navegador desde la paleta: selección `signal`/`chassis`,
  scrollbar `rule` sobre `chassis-rail`, anillo de foco `legend`.
- **Do** mostrar solo hechos verificables; un precio o dato sin definir se escribe «Por definir».
- **Do** respetar `prefers-reduced-motion`: sin rodillo, sin transición de placa, scroll instantáneo.
- **Do** escribir toda la interfaz en español.

### Don't:
- **Don't** usar `signal` como texto, borde, contorno, brillo o degradado.
- **Don't** usar radios, sombras, biseles, cromo, gradientes ni glow.
- **Don't** cambiar pesos para dar énfasis (nada de negritas dentro del texto corrido).
- **Don't** poner antetítulos o kickers sobre los títulos.
- **Don't** inventar precios, métricas, contadores ni testimonios.
- **Don't** usar el glifo ni el logotipo de Spotify ni sus marcas en la web pública; se nombra el proyecto en texto, sin implicar afiliación.
- **Don't** añadir iconos: las únicas figuras son el monograma BF y la flecha de «Acceder».
- **Don't** convertir las placas en rejillas de tarjetas sueltas de features con capturas.
