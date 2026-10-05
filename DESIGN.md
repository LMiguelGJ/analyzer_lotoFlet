---
name: Laboratorio Quiniela 80 — Interfaz Material 3 mobile-first
description: App operativa Material 3: guía paso a paso, lenguaje cotidiano, verdad financiera visible, mobile-first.
system: Material 3 (web realization)
platform: web, mobile-first
---

# DESIGN — Mundo visual Material 3

Decisión vinculante del usuario (2026-10-05): rediseño completo con
https://m3.material.io/develop/web + Impeccable. El mundo visual anterior
(extracto financiero oscuro, Georgia serif, radio 0, papel milimetrado) queda
descartado y sirve solo como anti-referencia.

## Implementación (regla de sistema)

- Material Web Components oficial está en modo mantenimiento (verificado en
  m3.material.io/develop/web): NO se agrega como dependencia. La fidelidad M3 se
  logra con los **design tokens oficiales de Material 3** (`--md-sys-*`) como CSS
  custom properties + componentes React propios con la gramática M3 nativa
  (state layers, elevation, shape scale, type scale, motion emphasized).
- Si la gramática M3 y una convención del proyecto entran en conflicto, M3 gana
  en todo lo visual; la semántica y la accesibilidad del producto ganan siempre.

## Color (M3 tonal palettes)

- Seed: teal profundo (hue ≈ 172) → roles `primary/secondary` fríos y confiables
  (verdad financiera). Terciario: ámbar cálido (hue ≈ 45) para cifras de dinero,
  números del juego y momentos de resultado (evita el cliché violeta/oro de las
  apps de lotería).
- Esquema claro por defecto + esquema oscuro completo, siguiendo
  `prefers-color-scheme` con toggle manual (comportamiento nativo M3).
- Estrategia: Restrained sobre la gramática M3 (neutrales + primary + accent de
  resultado); superficies tonales M3 (surface, surface-container), nunca gris puro.
- Los roles M3 se nombran con el vocabulario oficial (`--md-sys-color-primary`,
  `on-primary`, `surface-container-high`, `outline-variant`, …).

### Tokens asentados por el build (2026-10-05)

- Color: seed primario claro `#006a60` (teal profundo, hue ≈ 172°); secondary
  `#4a635e`; tertiary/acento de resultado `#805600` (ámbar, hue ≈ 42°). Roles
  tonales completos light y dark en `webapp/frontend/src/styles/tokens.css`.
- Tipografía: `"Roboto Flex", system-ui, -apple-system, "Segoe UI", sans-serif`
  para cuerpo y encabezados; cifras tabulares. Roboto Flex se entrega por el link
  de Google Fonts en `index.html` (verificado en el build) con fallback de sistema
  para uso offline.
- Forma: xs 4px, sm 8px, md 12px, lg 16px, xl 28px, full 9999px; controles 8px;
  cards 12px.
- Elevación M3 niveles 0–5: nivel 1 botones primarios, 2 wizard sticky, 3
  FAB/dialog/snackbar, 4 hover de FAB.
- Motion: cortos 50/100/150 ms; medios 200/300 ms; largo 400 ms.
  Easing estándar `cubic-bezier(0.2, 0, 0, 1)`, emphasized
  `cubic-bezier(0.2, 0, 0, 0.2)`. El progreso del wizard anima con `transform`
  (nunca propiedades de layout). `prefers-reduced-motion` reduce todo a 0.01 ms.
- Navegación: Navigation Bar inferior (Experimentos · Estrategias · Datos ·
  Ajustes) + FAB extendido «Nueva simulación»; top app bar pequeña con cola y tema
  (acciones en flujo normal, sin reserva fija de gutter). A ≥900 px la navegación
  se vuelve rail lateral. El FAB se oculta durante los flujos guiados (Ajustes y
  creación) para no competir con las acciones fijas del wizard.

## Tipografía

- Familia: **Roboto Flex** (gramática nativa M3), fallback `system-ui`.
  Cifras con `font-variant-numeric: tabular-nums` (dinero, tablas, resultados).
- Escala tipográfica M3 completa: display (large/medium/small), headline (1–5),
  title (1–3), body (1–2), label (1–3). Ningún heading serif.
- Texto de interfaz en español cotidiano; sin jerga en los flujos principales.

## Forma, elevación, movimiento

- Valores exactos asentados en la sección «Tokens asentados por el build» arriba;
  esta sección fija las reglas. Controles redondeados (radio 0 eliminado).
- Elevation M3 con surface tint; sombras solo donde M3 las define (FAB, dialogs,
  bottom sheets).
- Motion M3 emphasized (desaceleración 200–350 ms) en transiciones de estado;
  `prefers-reduced-motion` respetado en todo.

## Navegación y patrones

- Mobile-first absoluto: **Navigation Bar inferior** (Experimentos · Estrategias ·
  Datos · Ajustes) + **FAB extendido** «Nueva simulación» accesible con el pulgar.
  En pantallas anchas, la barra puede volverse navigation rail; nunca al revés.
- Top app bar pequeña con título de pantalla y acciones puntuales (cola de
  trabajos, tema).
- Configuración = **asistente paso a paso**: una decisión por pantalla/paso, resumen
  antes de confirmar, progreso visible, «Avanzado» plegado al final.
- Datos densos: en móvil, cards M3 (filled/outlined) con jerarquía; las tablas
  densas son solo la mejora de escritorio del mismo contenido.
- Estados: empty/loading/error/offline con el mismo vocabulario M3 (illustration
  mínima + explicación en lenguaje humano + acción concreta).

## Reglas duras del producto (anti-regresión)

- Capital, meta de saldo, duración y caveats de «simula, no predice» siempre
  visibles; nunca tras un disclosure.
- Lo avanzado (semillas, hashes, JSON, ids) se pliega; jamás se elimina.
- Sin gamificación, sin hype, sin promesas de ganancia.
- Nada hardcodeado: las reglas del juego vienen de configuración, no de constantes
  de UI.

## Pendientes conocidos (no bloqueantes, seguimiento futuro)

- Hallazgos informativos de revisión nativa sin abrir corrección: R3-001
  (pages/settings/index.tsx:380) y los anteriores ya cerrados.
- Ceiling check de Material 3 (revisión de cierre): state layers más consistentes
  en selección/press, jerarquía por elevación/superficie tonal en vez de bordes,
  y uso más sistemático de los roles tipográficos M3 por pantalla.
- Verificación manual pendiente del usuario: dispositivo físico, zoom del
  navegador y ancho ≤320 px.

## Componentes M3 previstos

App bars, Navigation Bar/Rail, FAB extendido, botones filled/tonal/outlined/text,
segmented buttons, chips (filter/assist), text fields (outlined/filled), lists,
cards, dialogs, bottom sheets, snackbars, menus, switches, sliders, linear
progress, tabs, tooltips. Todos con state layer, foco visible y objetivo táctil ≥ 48 px.
