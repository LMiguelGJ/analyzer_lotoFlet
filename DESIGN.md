---
name: Laboratorio Quiniela 80 — Interfaz de simulación financiera
description: Extracto financiero oscuro: cifras tabulares, reglas finas, veredicto primero y cero jerga.
colors:
  bg: "#171e26"
  surface: "#222830"
  field: "#242f3b"
  text: "#d0d4d8"
  text-secondary: "#adb5bf"
  accent: "#7eb3da"
  border: "#3b4652"
  border-control: "#6c7f92"
typography:
  display:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontWeight: 400
    lineHeight: 1.1
  title:
    fontFamily: "Georgia, 'Times New Roman', serif"
    fontWeight: 400
    lineHeight: 1.2
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.5
  figure:
    fontFamily: "ui-monospace, Consolas, 'SFMono-Regular', Menlo, monospace"
    fontFeature: "tnum"
    lineHeight: 1.2
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "0.8125rem"
    letterSpacing: "0.08em"
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "16px"
  md: "24px"
  lg: "40px"
  xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#10161c"
    rounded: "{rounded.none}"
    height: "42px"
    padding: "0 20px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.none}"
    height: "42px"
    padding: "0 20px"
  field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text}"
    rounded: "{rounded.none}"
    height: "42px"
  figure-hero:
    typography: "{typography.figure}"
    textColor: "{colors.text}"
---

# Design System: Laboratorio Quiniela 80

<!-- CONTRATO DE DIRECCIÓN (new-work, 5 bloques) -->
<!--
THESIS: La interfaz se lee como un estado de cuenta financiero: la verdad del
dinero ES la composición. Rechaza el panel CRUD genérico de admin.
OWN-WORLD: Oscuro Pi (#171e26), reglas hairline, cifras tabulares mono
alineadas, títulos serif sobrios, esquinas rectas, etiquetas sans tracked.
STORY: La persona crea una orden de simulación, lee su veredicto y decide.
FIRST VIEWPORT: Encabezado de extracto (título serif + 3 cifras grandes) y
debajo el libro de filas; la acción primaria única arriba a la derecha.
FORM: «Estado de cuenta» (ledger), dirección 1 de 2 candidatas, elegida por
decisión delegada del usuario en sesión sin interacción (sin tiro de dados).
-->

## Overview

**Creative North Star: "El extracto de la casa"**

Sistema visual inspirado en los extractos financieros impresos y los libros
mayores de auditoría: reglas finas que gobiernan el espacio, cifras tabulares
que se alinean como columnas contables, títulos serif con autoridad editorial y
una sobriedad que comunica seriedad comercial sin una sola decoración gratuita.
La interfaz no «muestra datos»: rinde cuentas. Cada pantalla es un documento que
responde primero la pregunta del dinero y recién después explica los mecanismos.

Es un sistema de modo Operate: la expresión nunca estorba la tarea. El carácter
vive en la disciplina tipográfica, en el ritmo de las reglas y en el peso visual
de las cifras, no en adornos. Rechazo confirmado: el panel administrativo CRUD
con tarjetas redondeadas, el dashboard de gráficos decorativos y el párrafo
explicativo como recurso de jerarquía.

**Key Characteristics:**
- Veredicto primero: toda pantalla de resultado abre con la respuesta.
- Cifras protagonistas: mono tabular, alineadas, con semántica de dinero.
- Reglas finas (1px, #3b4652) como único recurso de separación; sin sombras.
- Etiquetas sans en versalitas tracked para estructura; serif solo para títulos.
- Máximo 4 decisiones visibles por bloque; lo avanzado se pliega sin esconder
  la verdad financiera.

## Colors

Paleta azul-gris profunda y fría, sobria como papel de trabajo bajo luz de
escritorio; un solo acento y semántica de estado muy contenida.

### Primary
- **Azul Pi** (#7eb3da): único acento. Acción primaria, foco, enlaces, selección
  activa. Nunca como relleno decorativo de superficies grandes.

### Neutral
- **Fondo pizarra** (#171e26): fondo de página con textura sutil de papel
  milimetrado estático.
- **Superficie documento** (#222830): paneles y bloques de contenido.
- **Superficie campo** (#242f3b): controles editables y celdas destacadas.
- **Texto principal** (#d0d4d8): 11.27:1 sobre fondo.
- **Texto secundario** (#adb5bf): metadatos, hints, notas al pie.
- **Regla decorativa** (#3b4652): separadores hairline.
- **Regla de control** (#6c7f92): bordes funcionales de inputs/botones (≥3:1).

### Named Rules
**The Money Rule.** El color semántico positivo/negativo solo toca cifras de
dinero, chips de estado y sus indicadores. Nunca superficies, nunca fondos.
**The One Accent Rule.** El acento Pi ocupa ≤10% de cualquier pantalla: su
escasez es lo que señala la acción correcta.
**The Hairline Rule.** Toda separación se resuelve con reglas de 1px. Las
sombras están prohibidas: la profundidad se comunica con capas tonales.

## Typography

**Display Font:** Georgia ("Times New Roman", serif de sistema)
**Body Font:** system-ui / Segoe UI / Roboto (sans de sistema)
**Figure/Mono Font:** ui-monospace / Consolas / Menlo, con `font-variant-numeric: tabular-nums`

**Character:** El serif presta autoridad de documento financiero a títulos y
veredictos; el sans desaparece en los controles; el mono convierte cada cifra en
un dato contable alineado. Ninguna cursiva decorativa: el peso lo da el tamaño
y el espacio.

### Hierarchy
- **Display** (Georgia 400, 1.75–2rem, lh 1.1): veredicto y H1 de página.
- **Title** (Georgia 400, 1.27–1.5rem, lh 1.2): títulos de sección, numerados
  (01, 02, 03) en los formularios.
- **Body** (sans 400, 1rem, lh 1.5): párrafos breves de ayuda, máximo 65–75ch.
- **Figure** (mono 400–500, 1–1.5rem, tnum): todo importe, saldo, porcentaje,
  cantidad y fecha numérica. Alineación a la derecha en tablas.
- **Label** (sans 600, 0.8125rem, tracking 0.08em, mayúsculas): encabezados de
  columna, etiquetas de campo y de grupo.

### Named Rules
**The Figures Rule.** Si representa dinero, conteo o probabilidad, va en mono
tabular. Sin excepciones.
**The No-Paragraph Hierarchy Rule.** La jerarquía se comunica con estructura,
escala y reglas; los párrafos explicativos largos son un defecto de diseño.

## Layout

Grid de trabajo con margen de página 28px y ritmo de 8px (escalones 8/16/24/40/64).
Shell: rail izquierdo delgado (navegación + estado de cola) + columna de
contenido con ancho de lectura acotado para textos y ancho completo para tablas.
Cada pantalla abre con un «encabezado de extracto»: título serif, una línea de
contexto y una banda de 2–4 cifras clave (Stat). Los bloques de decisión se
separan con reglas finas y aire; más espacio arriba del título que debajo.
Responsive: a ≤900px el rail pasa a barra superior compacta, las bandas de
cifras se apilan en 2 columnas y las tablas densas se convierten en filas
definidas; sin overflow horizontal nunca. A 200% de zoom la estructura se
degrada al layout de tablet sin romper la lectura.

## Elevation & Depth

Sin sombras. Profundidad por capas tonales (bg → surface → field) y por reglas
hairline. Prohibido `box-shadow` salvo el anillo de foco accesible.

## Shapes

Radio 0 en toda la interfaz: botones, campos, paneles, diálogos y chips son
rectangulares. La silueta recurrente es el rectángulo dividido por reglas:
formularios como bloques de orden, tablas como libros contables. Iconos en
gramática de línea fina, sin tiles redondeados.

## Components

### Buttons
- **Shape:** radio 0, alto 42px, padding 0 20px.
- **Primary:** fondo azul Pi (#7eb3da), texto #10161c, sans 600. Máximo UNO por
  pantalla (acción primaria).
- **Secondary:** superficie #222830, borde #6c7f92, texto principal.
- **Ghost:** sin borde, texto secundario → principal al hover; acciones terciarias
  y plegados.
- **Hover / Focus:** hover aclara el fondo (transición 150ms ease-out); foco
  visible con anillo #7eb3da de 2px + offset.

### Chips
- **Estado (Meta alcanzada / Sin meta / En curso / Cancelado):** rectangulares,
  label tracked, borde hairline; color semántico SOLO en el texto y el borde.

### Cards / Containers (Bloques)
- **Corner Style:** 0. Fondo superficie. Sin sombra. Borde superior hairline o
  contorno completo hairline. Padding 16–24px. Encabezado de bloque con label
  tracked o título serif según jerarquía.

### Inputs / Fields
- **Style:** fondo #242f3b, borde #6c7f92, radio 0, alto 42px; etiqueta encima
  (label tracked), hint breve debajo, error con texto + icono.
- **Focus:** borde + anillo azul Pi. **Error:** borde semántico negativo y
  mensaje accionable. **Disabled:** texto secundario, sin misterios.

### Navigation
- Rail izquierdo delgado, sans, items con regla activa de 2px en azul Pi;
  estado de cola visible siempre. En tablet: barra superior compacta.

### Signature Component — «Resumen de la orden»
Panel vivo del formulario de creación: banda de cifras tabulares (capital, meta,
duración, cobertura) que se actualiza con cada decisión y cierra con el caveat
inamovible. Es la memoria externa del usuario: todo lo que configuró, en el
lenguaje del dinero.

### Signature Component — «Veredicto»
Bloque de apertura de todo resultado: una frase serif grande (Meta alcanzada /
Se agotó el capital / En curso) + 3 cifras clave + motivo de cierre. Nunca
decorativo: siempre responde «¿qué pasó con la plata?».

## Do's and Don'ts

### Do:
- **Do** abrir cada pantalla con la respuesta (veredicto o cifras clave) antes
  que con controles.
- **Do** mantener una sola acción primaria visible por pantalla y ≤4 decisiones
  visibles por bloque.
- **Do** plegar lo técnico en «Avanzado» / «Detalles técnicos», sin ocultar
  jamás capital, meta, duración, saldo ni caveat.
- **Do** usar reglas hairline y aire para agrupar; el espacio es el agrupador.
- **Do** escribir estados vacíos que enseñen el siguiente paso y errores que
  ofrezcan recuperación concreta.

### Don't:
- **Don't** mostrar jerga técnica (semilla, hash, JSON, esquema, enumeración,
  ids crudos, números sin sentido) fuera de «Detalles técnicos».
- **Don't** usar sombras, radios, gradientes decorativos ni glassmorphism.
- **Don't** usar el verde/rojo fuera del dinero y el estado.
- **Don't** comunicar jerarquía con párrafos largos ni con más de una acción
  primaria por bloque.
- **Don't** prometer predicción ni rentabilidad: el caveat «esto SIMULA» vive en
  toda superficie de resultados.
