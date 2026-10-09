# Plan: Aplicar el diseño BossFarmer al frontend

> Created by `plan-mode-trae` skill. Path: this file · Language: es · Created: 2026-10-09

## Summary

Reemplazar el mundo visual Material 3 del frontend por el sistema BossFarmer definido en `DESIGN.md`
(chapa oscura, placas con hairlines, Archivo Narrow/Archivo, esquina viva, cero sombras, cero iconos),
en siete tareas ODD secuenciales, sin tocar backend, contratos ni semántica financiera.

## Current State Analysis

- **Project**: `webapp/frontend`, Vite + React + TypeScript + Tailwind 3 (breakpoints `sm 640`, `nav 800`, `wide 1100`).
- **Tokens**: `src/styles/tokens.css` (277 líneas) define `--md-sys-*` (color, escala tipográfica, forma,
  elevación, movimiento) y alias de compatibilidad `--color-*` / `--chart-*`. Tiene `:root` claro,
  `[data-theme="dark"]` y `:root:not([data-theme="light"])` duplicados; `color-scheme: dark` ya está declarado.
- **Estilos**: `src/styles/index.css` (404 líneas, ~340 referencias `--md-sys-*` en el frontend). Contiene
  11 clases `.m3-*` y unas 90 clases de pantalla (`shell-*`, `backtest-*`, `ledger-*`, `experiment-*`, `comparison-*`).
  Hay reglas de elevación/radio/sombra en ~40 líneas.
- **Tailwind**: `tailwind.config.ts` mapea `bg/surface/field/text/accent/border` a `--color-*`, `borderRadius.control`, familias `heading/mono/body`.
- **Fuentes**: `index.html` carga Roboto Flex desde Google Fonts y `theme-color #f8faf7`. No existe `public/`; Archivo no está instalado.
- **Shell** (`src/components/Shell.tsx`, 101 líneas): iconos de carácter en el nav (`◫ ◇ ▤ ⚙`), botón de tema
  (`laboratorio-theme` en localStorage), botón de cola con `☷`, FAB `.m3-extended-fab` con `＋`, rail a ≥900 px.
- **Iconos reales**: SVG en `StatusLabel.tsx` (formas de estado), `BalanceChart.tsx`, `ComparisonChart.tsx`
  (estos dos ya distinguen series por trazo y marcador). Radios/sombras en TSX: solo `ConfirmDialog.tsx`.
- **Componentes base**: `components/ui/{Block,Controls,Data,Feedback,Signature}.tsx` + `ui.test.tsx` (171 líneas).
- **Tests que dependen de lo visual**: `App.test.tsx`, `Shell.test.tsx`, `ExperimentsPage.test.tsx`
  (tema, FAB, `m3-`, «Acceso rápido»).
- **Constraints**: backend/contratos/payloads de solo lectura; pruebas no se eliminan ni debilitan; la app
  funciona offline; toda la UI en español.

## Proposed Changes

Rama de trabajo: `feat/bossfarmer-design` desde `stage`. Un commit de trabajo por tarea (Conventional Commits).
Cada tarea cierra con build + pruebas focalizadas de sus archivos + revisión visual en 390 y 1440 px.

### T1 — Fundación: tokens, fuentes, Tailwind, tema único
- **Files**: `src/styles/tokens.css`, `src/styles/index.css` (solo base), `tailwind.config.ts`, `index.html`,
  nuevo `public/fonts/` (Archivo, Archivo Narrow), nuevo `src/styles/fonts.css`.
- **What**: crear `--bf-*` (chassis, chassis-rail, rule, legend, legend-dim, signal, alerta, field-sunken,
  field-placeholder, escala tipográfica, espaciado). Redefinir `--md-sys-*` y `--color-*` como **alias**
  de `--bf-*` (única definición, sin bloques claro/oscuro). Radios a 0 y sombras a `none` en tokens y en
  `tailwind.config.ts` (`borderRadius`/`boxShadow` fijos). Declarar `@font-face` con archivos locales
  (`font-display: swap`), quitar el link de Google Fonts y los `preconnect`, `theme-color #121415`.
  Selección `signal`/`chassis`, scrollbar `rule` sobre `chassis-rail`, foco `legend` 2px offset 3px.
- **Why**: `DESIGN.md` §Colors/Typography/Elevation e «Implementación»; los alias evitan romper pantallas intermedias.
- **How**: los archivos de fuente se obtienen de una fuente local ya disponible o se pide al usuario; **no se
  descargan ni instalan dependencias sin autorización explícita**. Si no se pueden autoalojar, se deja la
  pila `ui-sans-serif` con fallback condensado y se registra como pendiente.

### T2 — Navegación y estructura (`Shell`)
- **Files**: `src/components/Shell.tsx`, `src/components/Shell.test.tsx`, `src/App.test.tsx`,
  `src/pages/experiments/ExperimentsPage.test.tsx`, sección `shell-*`/`.m3-*` de `index.css`.
- **What**: raíl superior (marca tipográfica «LABORATORIO / QUINIELA 80», cola con contador en texto);
  raíl inferior fijo con 4 leyendas separadas por hairlines (móvil); a ≥ `lg` los destinos suben al raíl
  superior. Eliminar iconos del nav y del botón de cola, eliminar el botón y estado de tema (y la clave
  `laboratorio-theme`, con limpieza de la clave heredada). Reemplazar `.m3-extended-fab` por botón primario
  rectangular de ancho completo sobre el raíl inferior (móvil) y en el raíl superior (≥ `md`), oculto en
  los asistentes como hoy.
- **Why**: `DESIGN.md` §Navigation y adaptaciones 2, 3 y 9.
- **How**: mantener roles, `aria-*`, skip link, orden de foco y nombres accesibles; las pruebas se actualizan
  a los nuevos textos/roles conservando cada afirmación de comportamiento.

### T3 — Componentes base y estados
- **Files**: `src/components/ui/{Block,Controls,Data,Feedback,Signature}.tsx`, `ui.test.tsx`,
  `StatusLabel.tsx` (+test), `ConfirmDialog.tsx`, `QueueDrawer.tsx`, `DataTable.tsx` (+tests), clases base de `index.css`.
- **What**: botones primario/secundario/sobre-verde, campos hundidos, selector segmentado, interruptor y
  casilla de hairline, sellos, etiquetas neutra/adversa, placas, filas término/valor, estados
  vacío/cargando/error. `StatusLabel` pasa de SVG a texto con etiqueta (sin figura). Diálogo y cajón:
  `chassis-rail` + hairline + velo sin sombra. Tabla densa con hairlines y sin cebra.
- **Why**: `DESIGN.md` §Components y adaptaciones 4, 6 y 8.

### T4 — Asistente de cinco pasos
- **Files**: `FiveStepWizard.tsx` (+test), `WizardScopeSelector.tsx`, clases `backtest-stepper`/`backtest-step*`,
  páginas de creación solo en clases (`new-experiment/*`, `backtests/index.tsx`).
- **What**: celdas unidas en un marco, paso actual en campo `signal`, completados `legend`, pendientes
  `legend-dim`; fila Atrás/Siguiente de 48 px; revisión en filas término/valor; «Avanzado» como fila plegable.
- **Why**: `DESIGN.md` §Asistente de cinco pasos. Se mantienen los guardias de admisión, bloqueos de
  incertidumbre y navegación nativa existentes. Se restaura aquí la **navegación directa entre pasos** del
  lote perdida en `8b413c5` (celdas clicables solo hacia pasos ya alcanzados).

### T5 — Resultados, gráficos y ledger
- **Files**: `SimulationResultFrame.tsx`, `BacktestReport.tsx`, `BacktestSessions.tsx`, `FinancialMetrics.tsx`,
  `BalanceChart.tsx`, `ComparisonChart.tsx`, `RunTrajectory.tsx`, `GameRulesSummary.tsx`, tests asociados, `--chart-*`.
- **What**: placa de resultado con sello, numeral de saldo, filas de capital/meta/duración/neto/proveniencia y
  caveat fijo. Gráficos con `legend`/`legend-dim`, rejilla `rule`, meta discontinua, etiquetas directas,
  sin color de datos. Ledger como placas en móvil y tabla de hairlines en escritorio, conservando la clase
  dedicada y la región con teclado de `BacktestSessions`. Quiebra y corrida fallida con `alerta` + texto.
- **Why**: `DESIGN.md` adaptaciones 4–6 y §Resultado de una corrida.
- **How**: cifras monetarias, strings enteros nativos y formateadores no se tocan.

### T6 — Pantallas
- **Files**: `pages/experiments/*` (lista, detalle, comparación), `pages/configurations/*`, `pages/data/*`,
  `pages/settings/*` y sus tests; clases de pantalla restantes de `index.css`.
- **What**: aplicar placas, filas término/valor, segmentados y estados a cada pantalla; **restaurar** en
  Comparación la advertencia «no constituyen validación independiente de rentabilidad» (y «ni una
  probabilidad de éxito» para perfiles) y el neto por ejecución en las placas móviles (`result.net`).
- **Why**: auditoría Git del 2026-10-09 (`547625a`, `e64747f`); recuperación acordada como parte del rediseño.

### T7 — Limpieza y cierre
- **Files**: `tokens.css`, `index.css`, `tailwind.config.ts`, tests.
- **What**: retirar los alias `--md-sys-*`/`.m3-*` sin uso, bloques de tema claro, código muerto y la clave de
  tema; verificar que `rg "md-sys|m3-|shadow|rounded|<svg"` solo deje usos documentados (gráficos). Actualizar
  `odd/tasks`, `docs/` y registrar evidencia.

## Assumptions & Decisions

- Solo mundo oscuro; sin selector de tema (aceptado por el usuario al elegir BossFarmer «tal cual»).
- Sin iconos en ninguna parte; los gráficos son figuras de datos, no iconografía.
- Orden de destinos del nav: se mantiene el actual (Simulaciones · Estrategias · Datos · Ajustes).
- `--md-sys-*`/`--color-*` sobreviven como alias hasta T7 para que cada tarea cierre en verde.
- Breakpoints actuales de Tailwind se conservan; el cambio de nav ocurre en el mismo umbral que hoy (900 px del Shell).
- Alcance visual únicamente: rutas, contratos, `api/`, lógica de modelos y semántica financiera intactos.
- Sin nuevas dependencias npm. Las fuentes se autoalojan desde archivos; si faltan, se detiene T1 y se pregunta.
- Avance por commits de tarea en rama propia; **push, PR y merge solo si el usuario lo pide**.

## Verification

- [ ] Por tarea: `npm.cmd run test -- --run <archivos de la tarea>` y `npm.cmd run typecheck`.
- [ ] Por tarea: `npm.cmd run build` y revisión en navegador sobre preview propio (sin puerto 5173 ajeno), API sintética, 390 y 1440 px, sin desbordamiento horizontal de página.
- [ ] Al cierre (T7): suite completa de frontend, typecheck, build, recorrido de las 4 rutas de creación, detalle con ledger, comparación, estrategias, datos y ajustes.
- [ ] Revisión independiente por tarea (verificador distinto del escritor).
- [ ] Criterios observables: sin `box-shadow`/`border-radius` computados distintos de 0/none; `signal` solo como `background-color`; cero iconos en nav/estado; fuentes sin peticiones externas; caveat y capital/meta/duración visibles; contraste AA.

## Out of Scope

- Cambios de backend, API, esquema o semántica financiera.
- Logo definitivo y monograma.
- Tema claro y selector de tema.
- Sesiones consecutivas, mallas, Monte Carlo, estabilidad.
- Migraciones físicas T5b/T6b (retiradas).
- Despliegue, push, PR y merge.
