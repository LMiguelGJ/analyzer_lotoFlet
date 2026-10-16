---
name: Quiniela
description: Una libreta de papel cuadriculado para medir corridas históricas con claridad.
colors:
  paper: "#F7FBFC"
  paper-sheet: "#FCFEFF"
  grid: "#CDE5EA"
  ink: "#142C36"
  ink-muted: "#405B64"
  pencil-red: "#B42332"
  highlighter-yellow: "#FFE66D"
  control-fill: "#FFFFFF"
  line: "#A9C0C7"
typography:
  display:
    fontFamily: "Archivo Narrow, Archivo, ui-sans-serif, sans-serif"
    fontSize: "2.5rem"
    fontWeight: 600
    lineHeight: 1.1
  headline:
    fontFamily: "Archivo Narrow, Archivo, ui-sans-serif, sans-serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.1
  title:
    fontFamily: "Archivo Narrow, Archivo, ui-sans-serif, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.15
  body:
    fontFamily: "Archivo, ui-sans-serif, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo Narrow, Archivo, ui-sans-serif, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.08em"
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "16px"
  md: "24px"
  lg: "32px"
  xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "12px 24px"
    height: "48px"
  button-primary-hover:
    backgroundColor: "{colors.paper-sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  button-secondary:
    backgroundColor: "{colors.paper-sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 24px"
    height: "48px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 24px"
    height: "48px"
  navigation:
    rounded: "{rounded.none}"
    height: "48px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "4px 12px"
    height: "32px"
  card:
    backgroundColor: "{colors.paper-sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "24px"
  input:
    backgroundColor: "{colors.control-fill}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
    height: "48px"
---

# Design System: Quiniela

## Overview

**Creative North Star: "La libreta del apostador"**

La interfaz es una libreta de hojas claras y cuadriculadas: cada corrida es una hoja de trabajo y sus cifras descansan sobre una retícula precisa. El mundo sugiere apuntar, sumar y volver a probar; la interfaz hace las cuentas sin disfrazarse de una libreta física ni convertir la expresión en ruido.

Es una superficie de operación, no de promoción. La cuadrícula y la tinta ordenan la información; cifras legibles y palabras explícitas llevan el significado. Los destinos principales son **Laboratorios** (definir reglas fijas, ejecutar y leer resultados guardados) y **Ajustes** (cuota e historial). Corridas anteriores conserva sus rutas directas y su motor. Este documento no amplía estrategias, contratos ni promesas de verificación.

**Key Characteristics:**
- Papel blanco frío y cuadrícula cian tenue de 24 px.
- Tinta azul-negra, tinta secundaria AA y lápiz rojo para pérdidas, quiebras y errores.
- Marcador amarillo opcional, limitado a una aplicación por pantalla.
- Esquinas vivas, superficies planas y bordes precisos.
- Archivo local de Archivo y Archivo Narrow; las cifras usan numerales tabulares.

## Colors

Paleta restringida de papel, tinta y dos acentos funcionales. Los tokens del frontmatter son la fuente normativa; el rojo siempre acompaña una palabra o signo y nunca es el único indicador.

### Primary
- **Tinta azul-negra** (`colors.ink`): texto, cifras, foco y acciones principales.
- **Lápiz rojo** (`colors.pencil-red`): pérdidas, quiebra, errores y correcciones; no sustituye etiquetas ni signos.

### Neutral
- **Papel frío** (`colors.paper`): fondo general, sin crema ni sepia.
- **Hoja clara** (`colors.paper-sheet`): hojas, grupos y controles secundarios.
- **Cuadrícula cian** (`colors.grid`): textura tenue y alineación; nunca cuenta como límite de control.
- **Tinta secundaria** (`colors.ink-muted`): rótulos, ayudas y texto secundario con contraste AA.
- **Línea de hoja** (`colors.line`): divisiones y bordes de superficies.
- **Relleno de control** (`colors.control-fill`): campos sobre el papel.

### Tertiary
- **Marcador amarillo** (`colors.highlighter-yellow`): fondo opcional de la cifra clave; como máximo una vez por pantalla y con tinta encima.

### Named Rules
**The One Highlighter Rule.** El amarillo es raro por diseño: una sola aplicación por pantalla como máximo.
**The Sign Always Rule.** Los resultados monetarios y retornos conservan signo (+ o −); el dinero mantiene unidad RD$ y el color solo refuerza el significado. Excepción local: los nuevos importes absolutos Aportado de tu bolsillo y Patrimonio al final no llevan `+`. No cambiar los formatos históricos ni los formateadores compartidos.
**The Not Cream Rule.** El papel permanece frío y claro; no usar crema, sepia ni terracota.

## Typography

**Display Font:** Archivo Narrow (con Archivo y sans-serif de sistema como fallback).
**Body Font:** Archivo (con sans-serif de sistema como fallback).
**Label/Mono Font:** Archivo Narrow para rótulos; la pila monoespaciada del sistema queda reservada para contenido técnico.

**Character:** Imprenta nítida, sobria y funcional. Los pesos y tamaños fijos construyen jerarquía; los datos financieros usan cifras tabulares, no una fuente de exhibición.

### Hierarchy
- **Display** (600, 2.5rem, 1.1): cifra principal cuando una página la requiera.
- **Headline** (600, 2rem, 1.1): encabezado de página.
- **Title** (600, 1.5rem, 1.15): título de hoja o sección.
- **Body** (400, 1rem, 1.5): texto general; mantener los párrafos de lectura en una medida cómoda, aproximadamente 65–75ch.
- **Label** (600, 0.75rem, 0.08em): rótulos concisos; caja normal por defecto, sin convertir cada encabezado en un eyebrow.

### Named Rules
**The Tabular Rule.** Las columnas numéricas alinean cifras tabulares; dinero lleva RD$ y resultados/retorno llevan signo. Los dos importes absolutos de billetera siguen la excepción local anterior.
**The Local Font Rule.** Usa los archivos Archivo y Archivo Narrow ya empaquetados; no dependas de fuentes remotas.

## Layout

Una cuadrícula de 24 px sostiene la composición; filas, grupos y pausas principales siguen ese ritmo. Los espacios reutilizables son 8, 16, 24, 32 y 48 px. Los campos y controles interactivos miden al menos 48 px de alto.

La navegación principal tiene dos destinos: Laboratorios y Ajustes. En móvil se fija abajo con el área segura inferior; desde 900 px se integra en la barra superior adhesiva. Conserva el enlace para saltar al contenido y el foco de teclado. El contenido se centra en una columna de hasta 1440 px. Laboratorios usa lista lateral y panel; a 860 px o menos, un panel seleccionado precede a la lista en el DOM. Sin selección, la lista va primero. Las instancias estables conservan borrador, selección y página al redimensionar. Las tablas se desplazan horizontalmente sin ampliar la página; Ajustes conserva su presentación.

### Resultado y corrección en Laboratorios

- «Tu dinero · Simulación» primero: Aportado de tu bolsillo, Patrimonio al final y Ganancia / pérdida. La última reutiliza el neto, sin tarjeta duplicada. Los dos importes nuevos son absolutos y sin `+`; el neto conserva signo. Mantener RD$, cifras tabulares, dinero sin cortes y columnas monetarias alineadas a la derecha.
- «Movimiento de apuestas» conserva volumen apostado, premios recibidos y retorno sobre apostado, con los mismos valores. Los cuatro contadores siguen presentes; «Media neta de cerradas» pasa a «Detalle de sesiones», cerrado inicialmente. La ayuda nativa «ⓘ Cómo se calcula» también empieza cerrada; no cambiar las ayudas de opciones ni añadir otro ROI.
- La jerarquía se adapta al contenedor del panel, no a cuatro columnas fijas según el viewport. Los ajustes quedan limitados a Laboratorios, sin modificar rutas históricas ni tokens.
- «Datos de la reproducción» es un desplegable nativo con ventana y huellas completas. No restaurar los seis párrafos explicativos retirados ni inventar trazas por apuesta.
- El formulario inválido anuncia un resumen enlazado a sus campos y enfoca el primero. La navegación iniciada desde un enlace enfoca el panel, sin robar foco en carga inicial ni al consultar resultados.

Estos comportamientos están implementados; la aceptación visual, móvil, de teclado e independiente sigue pendiente. El chequeo focalizado no acredita conformidad global WCAG. Ver [guía de QA manual](quiniela-ui-manual-qa.md).

## Elevation & Depth

Plano, sin sombras ni desenfoques. Una hoja se separa del fondo mediante un cambio de papel y una línea fina; los controles tienen un borde de tinta de 2 px y el foco se marca con un contorno visible. El grid es textura, no una sombra ni un borde de control.

### Named Rules
**The Flat Sheet Rule.** Nada flota: contenedores y diálogos son hojas planas con límites claros.

## Shapes

Esquinas vivas en controles, hojas y grupos (0 px). Las superficies pueden tener divisores de 1 px; los límites de campos, botones y controles son de 2 px, con contraste mínimo 3:1. No anides tarjetas: organiza el contenido en hojas planas y grupos sin cajas repetidas.

## Components

Los componentes compartidos y las dos pantallas de la aplicación están implementados. La descripción de abajo documenta patrones visuales presentes en los estilos actuales, no una promesa de métricas o capacidades adicionales.

### Buttons
- **Shape:** esquinas vivas (0 px), borde de tinta de 2 px, alto mínimo de 48 px.
- **Primary:** bloque de tinta con texto de papel; padding vertical 12 px y horizontal 24 px.
- **Hover / Focus:** el primario invierte a hoja clara y tinta; las transiciones actuales duran 120 ms. El foco visible usa contorno de tinta de 3 px con separación.
- **Secondary / Ghost:** fondo de hoja o transparente, borde de tinta; hover usa cuadrícula tenue en el secundario y active puede usar amarillo de marcador.
- **Disabled / Loading:** deshabilitado conserva texto legible sobre hoja clara, sin opacidad; loading comunica `aria-busy` y deshabilita el envío repetido.

### Chips
- Etiqueta compacta de texto, sin fondo de acento ni significado transmitido solo por color; altura mínima de 32 px.

### Cards / Containers
- **Corner Style:** cuadrado (0 px).
- **Background:** hoja clara sobre papel frío.
- **Shadow Strategy:** ninguna; la separación usa borde de 1 px.
- **Internal Padding:** 24 px como base, reducido en pantallas estrechas.
- Usa secciones planas; no construyas una jerarquía de tarjetas anidadas.

### Inputs / Fields
- **Style:** campo blanco, tinta azul-negra, borde de 2 px y esquinas vivas; cada campo tiene etiqueta asociada.
- **Focus:** contorno de teclado de 3 px, desplazado 2 px en campos y 3 px en botones.
- **Error / Disabled:** error en lápiz rojo y asociado al campo; disabled conserva texto legible sobre hoja clara, sin opacidad, y no finge interactividad.
- **Choice Fields:** checkbox y radio conservan un glifo de 24 px dentro de una etiqueta clicable de al menos 48 × 48 px.
- **Loading:** usa un estado anunciado y filas skeleton; no un spinner decorativo central. Los esqueletos acompañan cargas de pantallas y listados.

### Navigation
- Barra superior en escritorio y barra inferior fija en móvil; enlaces de texto de al menos 48 px de alto. El destino actual se indica con tinta y subrayado, además del estado semántico del enlace.

### Flat Status Sheets
Estados vacíos, de error y carga usan hojas planas con texto claro. Los esqueletos son decorativos para lectores de pantalla y el estado de carga se anuncia como `status`.

## Do's and Don'ts

### Do:
- **Do** usar los tokens normativos y la retícula de 24 px para nuevas superficies.
- **Do** conservar Archivo y Archivo Narrow, cifras tabulares, signo y RD$.
- **Do** dar al texto contraste mínimo 4.5:1 y a los límites de controles al menos 3:1.
- **Do** mantener foco visible, navegación por teclado y `prefers-reduced-motion`.
- **Do** tratar el grid como textura y ofrecer palabras/signos además de color.
- **Do** preservar esta dirección en Laboratorios y mantener intactas las rutas históricas y Ajustes; este documento no amplía sus capacidades funcionales.

### Don't:
- **Don't** reintroducir la identidad, los tokens `--bf-*` ni el tema de BossFarmer.
- **Don't** añadir sombras, esquinas redondeadas, vidrio, gráficos o iconos decorativos.
- **Don't** apilar tarjetas anidadas ni usar el amarillo más de una vez por pantalla.
- **Don't** usar el rojo como único portador de pérdida, error o quiebra.
- **Don't** inventar datos, resultados, afirmaciones de producto o páginas no implementadas.
