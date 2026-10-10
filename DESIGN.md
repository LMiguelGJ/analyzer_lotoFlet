---
name: Laboratorio Quiniela 80
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

# Design System: Laboratorio Quiniela 80

## Overview

**Creative North Star: "La libreta del apostador"**

La interfaz es una libreta de hojas claras y cuadriculadas: cada corrida es una hoja de trabajo y sus cifras descansan sobre una retícula precisa. El mundo sugiere apuntar, sumar y volver a probar; la interfaz hace las cuentas sin disfrazarse de una libreta física ni convertir la expresión en ruido.

Es una superficie de operación, no de promoción. La cuadrícula y la tinta ordenan la información; cifras legibles y palabras explícitas llevan el significado. El sistema visual y la navegación están implementados como base; las páginas de Corridas y Ajustes siguen pendientes y no se deben inferir como pantallas ya resueltas.

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
**The Sign Always Rule.** Cada cantidad monetaria se presenta con signo (+ o −) y unidad RD$; el color solo refuerza el significado.
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
**The Tabular Rule.** Las columnas numéricas alinean cifras tabulares; dinero y retorno muestran signo y unidad.
**The Local Font Rule.** Usa los archivos Archivo y Archivo Narrow ya empaquetados; no dependas de fuentes remotas.

## Layout

Una cuadrícula de 24 px sostiene la composición; filas, grupos y pausas principales siguen ese ritmo. Los espacios reutilizables son 8, 16, 24, 32 y 48 px. Los campos y controles interactivos miden al menos 48 px de alto.

La navegación tiene dos destinos: Corridas y Ajustes. En móvil se fija abajo; desde 900 px se integra en la barra superior. Conserva el enlace para saltar al contenido, el foco de teclado y el área segura inferior del dispositivo. El contenido se centra en una columna de hasta 1440 px; las páginas aún no están implementadas.

## Elevation & Depth

Plano, sin sombras ni desenfoques. Una hoja se separa del fondo mediante un cambio de papel y una línea fina; los controles tienen un borde de tinta de 2 px y el foco se marca con un contorno visible. El grid es textura, no una sombra ni un borde de control.

### Named Rules
**The Flat Sheet Rule.** Nada flota: contenedores y diálogos son hojas planas con límites claros.

## Shapes

Esquinas vivas en controles, hojas y grupos (0 px). Las superficies pueden tener divisores de 1 px; los límites de campos, botones y controles son de 2 px, con contraste mínimo 3:1. No anides tarjetas: organiza el contenido en hojas planas y grupos sin cajas repetidas.

## Components

Los componentes compartidos están implementados; son una base, no una especificación de páginas de negocio.

### Buttons
- **Shape:** esquinas vivas (0 px), borde de tinta de 2 px, alto mínimo de 48 px.
- **Primary:** bloque de tinta con texto de papel; padding vertical 12 px y horizontal 24 px.
- **Hover / Focus:** el primario invierte a hoja clara y tinta; el foco visible usa contorno de tinta de 3 px con separación.
- **Secondary / Ghost:** fondo de hoja o transparente, borde de tinta; estados hover y active permanecen sobrios.
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
- **Focus:** contorno de teclado de 3 px, desplazado del borde.
- **Error / Disabled:** error en lápiz rojo y asociado al campo; disabled conserva texto legible sobre hoja clara, sin opacidad, y no finge interactividad.
- **Choice Fields:** checkbox y radio conservan un glifo de 24 px dentro de una etiqueta clicable de al menos 48 × 48 px.
- **Loading:** usa un estado anunciado y filas skeleton; no un spinner decorativo central.

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
- **Do** reconocer que las pantallas Corridas y Ajustes aún están pendientes; este documento solo fija la base.

### Don't:
- **Don't** reintroducir la identidad, los tokens `--bf-*` ni el tema de BossFarmer.
- **Don't** añadir sombras, esquinas redondeadas, vidrio, gráficos o iconos decorativos.
- **Don't** apilar tarjetas anidadas ni usar el amarillo más de una vez por pantalla.
- **Don't** usar el rojo como único portador de pérdida, error o quiebra.
- **Don't** inventar datos, resultados, afirmaciones de producto o páginas no implementadas.
