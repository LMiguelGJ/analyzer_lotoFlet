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
  `on-primary`, `surface-container-high`, `outline-variant`, …). Valores exactos
  provisionales hasta que el build los asiente; se actualizan aquí.

## Tipografía

- Familia: **Roboto Flex** (gramática nativa M3), fallback `system-ui`.
  Cifras con `font-variant-numeric: tabular-nums` (dinero, tablas, resultados).
- Escala tipográfica M3 completa: display (large/medium/small), headline (1–5),
  title (1–3), body (1–2), label (1–3). Ningún heading serif.
- Texto de interfaz en español cotidiano; sin jerga en los flujos principales.

## Forma, elevación, movimiento

- Shape scale M3: xs 4, sm 8, md 12, lg 16, xl 28. Controles redondeados (radio 0
  eliminado por completo).
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

## Componentes M3 previstos

App bars, Navigation Bar/Rail, FAB extendido, botones filled/tonal/outlined/text,
segmented buttons, chips (filter/assist), text fields (outlined/filled), lists,
cards, dialogs, bottom sheets, snackbars, menus, switches, sliders, linear
progress, tabs, tooltips. Todos con state layer, foco visible y objetivo táctil ≥ 48 px.
