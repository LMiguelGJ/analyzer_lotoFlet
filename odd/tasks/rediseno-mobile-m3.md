# Feature: Rediseño completo mobile-first Material 3

Solicitado por el usuario (2026-10-05): «sigue siendo muy técnico… visualmente es
horrible… rediseño completo… interfaz para móvil… https://m3.material.io/develop/web
en combinación con la skill de Impeccable».

Decisiones confirmadas por entrevista (2026-10-05):
- Tareas principales: analizar resultados, generar combinaciones, seguir
  experimentos, administrar datos (todas).
- Configuración: guía paso a paso (asistente), sin jerga.
- Audiencia: solo el usuario (herramienta personal).

Contrato de dirección (Material 3 web + Impeccable, mobile-first): ver `DESIGN.md`.
Anti-referencia: el mundo visual anterior (oscuro «Pi», Georgia, radio 0).

Modo de ejecución: YOLO nocturno (usuario ausente, «nunca pares»). Sin preguntas:
las decisiones de producto razonables se toman y se documentan acá. La calidad se
mide contra la especificación Material 3 + craft floor de Impeccable (el usuario
fijó el canon M3; no hay roll de conceptos).

## Alcance

Frontend `webapp/frontend` únicamente. Backend, API, contratos, datos históricos y
base de datos son de solo lectura: no se cambian endpoints ni payloads.

## Tasks

- [x] T1. Base M3: tokens (`--md-sys-*`), tipografía Roboto Flex, componentes
  compartidos M3 y Shell mobile-first (Navigation Bar inferior + FAB + top app bar).
  Superficies: webapp/frontend/src/styles/**, webapp/frontend/src/components/**
  (Shell, ui compartidos), tests colocados.
- [x] T2. Asistente de configuración: Ajustes como guía paso a paso (reglas del
  juego, cuota, avanzado plegado). Superficies: webapp/frontend/src/pages/settings/**
  y componentes compartidos que use, tests colocados.
- [ ] T3. Asistente de creación de simulaciones: flujo guiado por pasos
  (datos → selección → límites → revisión → ejecutar), variantes perfil/lote
  alcanzables. Superficies: webapp/frontend/src/pages/new-experiment/** y
  componentes compartidos que use, tests colocados.
- [ ] T4. Resultados: listado, detalle y comparación en lenguaje cotidiano, cards
  en móvil, verdad financiera siempre visible. Superficies:
  webapp/frontend/src/pages/experiments/** y presentación compartida que usen,
  tests colocados.
- [ ] T5. Estrategias y datos: configurations + data mobile-first con jerarquía
  clara. Superficies: webapp/frontend/src/pages/configurations/**,
  webapp/frontend/src/pages/data/** y presentación compartida que usen, tests
  colocados.
- [ ] T6. QA transversal: responsive, accesibilidad, reduced motion, tsc, suite
  completa frontend, build, detector Impeccable `[]`. Superficies: solo correcciones
  de presentación/estilos y tests de regresión que aparezcan.

## Verification (por tarea)

Desde `webapp/frontend`: `npm test -- --run <archivos focales>`, luego
`npm run typecheck`. Al cierre de T6: `npm test -- --run` completo + `npm run build`
+ detector `node C:\Users\luism\.pi\agent\skills\impeccable\scripts\detect.mjs --json`.
Aceptación manual del usuario: navegador en ancho de teléfono real + zoom.

## Evidencia (commits por unidad de trabajo)

- T1: 65f0af0 (8 archivos) · revisión nativa review-67641f41fa08db8d
  aprobada y quemada; 3 hallazgos informativos R3 (ver seguimientos)
- T2: 875e221 (3 archivos) · revisión nativa review-4fc2fc999cd38525
  aprobada y quemada; hallazgos informativos R3: R3-hidden-save-results
  (settings/index.tsx:412-413), R3-readonly-review-quota (settings/index.tsx:398),
  R3-rules-failure-blocks-settings (settings/index.tsx)
- T3: pendiente
- T4: pendiente
- T5: pendiente
- T6: pendiente

## Seguimientos de revisión (no bloqueantes)

- R3-hidden-save-results (pages/settings/index.tsx:412-413): el resultado del
  guardado queda poco visible tras la acción final.
- R3-readonly-review-quota (pages/settings/index.tsx:398): el resumen de cuota del
  paso final es de solo lectura.
- R3-rules-failure-blocks-settings (pages/settings/index.tsx): un fallo de reglas
  bloquea el resto de la configuración.

- R3-dark-token-coverage (src/lib/tokens.test.ts:10): ampliar cobertura de tokens
  del esquema oscuro.
- R3-storage-failure (src/components/Shell.tsx:25-28): manejar fallo de
  localStorage al persistir el tema.
- R3-theme-position (src/styles/index.css:70): posición del control de tema.

## Notas de alcance

- El producto afirma «simula, no predice»: ningún cambio de copy puede insinuar
  predicción ni rentabilidad.
- Estados parciales/faltantes de comparaciones y resultados se preservan literales.
- La cola de trabajos debe seguir accesible en móvil sin competir con la acción
  principal.
