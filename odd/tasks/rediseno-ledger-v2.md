# Rediseño v2 «Estado de cuenta» — seguimiento ODD

## Objetivo y autorización

Rehacer TODO el frontend desde cero con Impeccable hasta superar el rediseño v1
en diseño, interfaz y UX, con nivel de producto comercial serio. Plan
decision-complete: `.pi/plans/rediseno-ledger-v2.md`. Identidad fijada (Pi
oscuro, sans + serif, radio 0). Backend/API/contratos/datos/DB solo lectura.
Suite de 501 tests como salvaguarda. Usuario en modo YOLO delegado: ejecución
completa sin interrupciones; preguntas abiertas solo al final del informe.

## Dirección elegida

**«Estado de cuenta» (ledger financiero)** — ver justificación en el plan §2.
Contrato y sistema: `DESIGN.md` (raíz). Verdad de producto: `PRODUCT.md` (raíz).

## Tareas

- [x] S0 Fundación del sistema visual: tokens + primitivas `components/ui/*` + tests — commit `8defd01`; verificación independiente: 523/523 tests serial (36 archivos), typecheck limpio, contrato de primitivas sin violaciones
- [x] S1 Shell + glosario canónico (Shell, App, ui-labels, format) — en curso (writer en árbol principal)
- [x] S2 Creador simple de 3 grupos con «Resumen de la orden» (brief no negociable)
- [x] S3 Resultado con veredicto primero (DetailPage, FinancialMetrics, charts) — implementado y commiteado como `f51143b` en rama `wt/s3` (535/535 tests serial, typecheck limpio; mapeo veredicto solo desde hechos existentes: outcome goal→Meta alcanzada, ruin→Se agotó el capital, limit→Límite de sesión, history_exhausted→Historial agotado, running/pending/held→En curso, cancelado→Simulación cancelada); pendiente integrar a `stage`
- [x] S4 Comparación que responde «qué cambió» primero
- [x] S5 Listado como libro mayor con estados y vacíos que enseñan
- [x] S6 Datos y estrategias en lenguaje llano con lo técnico plegado
- [x] S7 Cola y ajustes con estados llanos y una acción por fila
- [ ] S8 Pulido: microinteracciones, estados, teclado, zoom, tablet, reduced-motion
- [ ] S9 QA + evidencia: suite completa, typecheck, build, detect 0, barrido
      navegador desktop+tablet, capturas, docs

## Reglas de ejecución

- Commits convencionales por unidad en rama `stage`; tests y docs con el código.
- Writers en worktrees aislados; máximo 2 en paralelo con archivos disjuntos.
- Política de tests: salvaguardas intactas; retiro solo de copy obsoleto con
  registro en `webapp/reports/verification/rediseno-v2/registro-pruebas-copy.md`.
- Revisión nativa por slice de commits (RDD activo); evidencia por cierre.
- Push final a `origin/stage` + informe con comandos, conteos y capturas.

## Evidencia y bloqueos

- Commits: `8defd01` (S0 fundación), `cb29454` (plan + seguimiento), `c9a4bae`
  (S1 shell + glosario; fallout conocido: 47 aserciones de copy en suites de
  otros slices, se reconcilian en el commit de integración), `66de27c` (S2
  creador, rama `wt/s2`, 524/524), `f51143b` (S3, `wt/s3`), `50202f1` (S4,
  `wt/s3`), `dcba4fe` (S6, `wt/s3`, 537/537).
- Verdad de motor verificada por S2: max_bets cuenta UNA apuesta por sorteo
  rankeado → «Duración máxima (sorteos)» = 12 es exacto; el juego clásico
  impone apuesta mínima RD$1 (fila legítima); reglas reales del juego activo:
  00–99, 5 posiciones, repeticiones permitidas, premios 80/8/4/2/1.
- Pendiente de pulido (S8): doble caveat adyacente en el Resumen de la orden
  (OrderSummary + caveat histórico).
- Lanes paralelos: árbol principal = S1; `wt-s2` = S2 (creador); `wt-s3` = S4 tras S3.
  Worktrees con node_modules por junction de Windows.
- Verdad de motor detectada (decisión de dirección): el juego embebido Q80 es
  100 números / 5 posiciones / premios 80-8-4-2-1 (contracts.py:36), mientras el
  brief pide 3 posiciones y premios 60/10/5 (juego de perfil, "primera
  ampliación" según especificaciones-laboratorio-web.md [A8]). Decisión: el
  panel de Reglas muestra SIEMPRE los valores reales del juego en uso (verdad
  financiera intacta = límite 6 del brief); los valores del brief se prefiltran
  donde el contrato real existe (blend transición 60 + fríos 40, cobertura 10,
  capital 2000, meta 2800, duración 12 sorteos vía max_bets si una apuesta es
  una ronda de sorteo — verificado por S2). Discrepancia 3/60-10-5 lista para
  decisión del usuario en el informe final.
- Canal de preguntas de subagentes NO funciona (expira siempre): los writers
  reciben autorización y criterio embebidos y prohibición de preguntar.

- Crítica de partida (Evaluación A): 26/40; P1 perfil/lote, comparación técnica,
  vocabulario mixto. Detector: 0 hallazgos.
- Evaluación B (navegador real, 46 capturas en
  `webapp/reports/verification/rediseno-v2/critica-b/`): identidad ya no parece
  plantilla genérica; sigue «herramienta interna» por recuperación insuficiente,
  estados contradictorios (cola «Sin conexión» + «Actualizando…»), resumen roto
  del creador («Un sistema de selección (), cobertura 1»), números de
  implementación en Avanzado (9.007.199.254.740.991), cabecera 320px fragmentada
  (título con 101px, palabras partidas) y «Continuar» habilitado sin datos en el
  lote. Sin overflow horizontal a 320px/200%; foco 2px correcto; reduced-motion
  respetado; contraste 9,12:1 en inputs. Detector fuente `[]`; URL no válido
  (falta puppeteer). API caída (502): solo estados sin conexión evaluados.
- Preview de verificación quedó activo en :4173 (gestionado por el padre).
- Preexistente ajeno a este trabajo: gitlink eliminado
  `lottery-predictability-monte-carlo` sin stagear; se excluye de todo commit.
- Primer intento de Evaluación B bloqueado por canal de autorización expirado
  (relanzado con autorización embebida; sin pérdida de evidencia).

## Integración y revisión nativa (evidencia real)

- `stage` integra todo: S0 `8defd01`, S1 `c9a4bae`, S5 `603ff84`, merge S2 `8552cec`
  (S2 = `66de27c`), fix de integración `f55c417`, merge S3/S4/S6/S7 `390bc1f`
  (S3 `f51143b`, S4 `50202f1`, S6 `dcba4fe`, S7 `26fc266`) y reconciliación de
  suites `711bb24`. Suite serial integrada: **551/551**, typecheck limpio.
- Revisión nativa por slice (RDD activo; base `4afe0f8`; el rango completo excedió
  el presupuesto de contexto → `lens_context_budget_exceeded`, se partió en
  cadena y se verificó que el árbol de la cadena es idéntico a `stage@711bb24`):
  - R1 S0+S1 — lineage `review-19b9c053f317da0f`: approved, ack quemado
  - R2 S2+S5 — lineage `review-e6be18c715098705`: approved, ack quemado
  - R3a S3+S4 — lineage `review-412d072b93cb8ea4`: approved, ack quemado
  - R3b S6 — lineage `review-eb3406633418e22b`: approved, ack quemado
  - R3c S7+reconciliación — lineage `review-5315f527ee084785`: approved, ack quemado
  Lente `review-reliability` (riesgo medio). Advisories no bloqueantes (se tratan
  como trabajo posterior, no reabren la revisión): doble caveat adyacente,
  `Shell.tsx:53-59` nombre de cola, `Feedback.tsx:35` claim incondicional,
  `Signature.tsx:6/19` Verdict solo dinero y h1 duplicado, `new-experiment/index.tsx:459`
  regex muerta, `DetailPage.tsx:227/359`, `BalanceChart.tsx:16`, entre otros.
- Pendiente: S8 pulido guiado por barrido de navegador, S9 QA final, push.

## S8 pulido y QA mecánica (evidencia real)

- S8a `deffb8b`: advisories de revisión aplicados (Verdict h2 + cifras de conteo,
  un solo caveat vía prop de OrderSummary, ErrorBanner con `preserved` explícito,
  estado de la cola vía aria-describedby sin cambiar el nombre accesible, regex
  muerta fuera). 554/554.
- S8b `c21100b`: Resumen de la orden como grilla etiqueta/valor sin desbordes,
  enlace «Volver a simulaciones» en el creador, «Cancelar» de la cola pasa a
  secundario, volver de la comparación en ghost. 555/555.
- `93b85f1`: título del cajón «Cola de cálculo» (glosario). 555/555.
- Detector Impeccable `detect.mjs --json webapp/frontend/src`: `[]` (exit 0).
  Build de producción: ok. Typecheck: limpio.
- Barrido etapa 1 (API simulada, 18 capturas en `webapp/reports/verification/
  rediseno-v2/barrido/`): 0 `border-radius` distinto de 0, 0 `box-shadow`, 0
  jerga fuera de plegables, 1 acción primaria por ruta (3 en cajón de cola antes
  de S8b). Lectura visual de capturas encontró defectos que ningún detector ve
  (resumen de la orden pegado, tres primarias en la cola) y se corrigieron.
- Pendiente: barrido etapa 2 (320px, zoom 200%, teclado, vacío/error,
  reduced-motion), retoque menor de chips repetidos en pestañas de resultado,
  revisión nativa de S8 y push.
- Incidentes de proceso: caída de Pi y de un writer sin reporte (S8b); el estado
  se recuperó verificando el árbol (typecheck + suite) antes de commitear.

## S9 cierre: barrido etapa 2 y correcciones (en curso)

- Barrido etapa 2 (`webapp/reports/verification/rediseno-v2/barrido/etapa2.md`,
  API simulada, datos sintéticos): overflow solo en `/detalle` a 320px (2 spans
  "N/D", 3px); teclado con indicador visible en los stops reales y foco atrapado
  y devuelto en la cola; reduced-motion respetado en las 10 vistas; creador con
  capital 2.000 / meta 2.800 / duración 12, resumen sin palabras pegadas y un
  solo caveat; vacíos que enseñan en `/experimentos` y `/configuraciones`.
- Hallazgos corregidos (5): separador de miles a es-ES ("RD$2.800", ya no la
  coma que imponía es-DO y contradecía la ayuda del brief); overflow de "N/D" en
  FinancialMetrics (`min-w-0`); `/datos` con acción primaria única y "Reintentar
  perfiles" real (estado `profilesRetry`; antes el fetch corría una sola vez con
  `[]`); `/configuraciones` nombra su reintento y deshabilita "Nueva estrategia
  guardada" sin catálogo.
- Defecto de enrutamiento (ODD): el primer intento de arreglar las 21 pruebas se
  hizo inline en el padre cuando ya eran 7 archivos; se corrigió delegando a un
  writer acotado (S9) con superficie explícita.

## Cierre S9 y entrega (evidencia final)

- S9 `cf34dd4` (hallazgos del barrido etapa 2: separador de miles es-ES
  "RD$2.800", overflow 320px corregido, `/datos` con acción primaria única y
  "Reintentar perfiles" real, `/configuraciones` con reintento nombrado y crear
  deshabilitado sin catálogo). Revisión nativa S9: lineage
  `review-d2c1a59fe65b909d` **approved, ack quemado** (advisories R3-001/002 no
  bloqueantes).
- Gates finales: 557/557 tests seriales, `tsc --noEmit` limpio, `vite build` ok
  (3.06s), detector Impeccable `[]` exit 0.
- Push `origin/stage`: `871a69e..cf34dd4`, adelantados/atrasados 0/0.
- Revisiones nativas del proyecto: R1 `review-19b9c053f317da0f`, R2
  `review-e6be18c715098705`, R3a `review-412d072b93cb8ea4`, R3b
  `review-eb3406633418e22b`, R3c `review-5315f527ee084785`, R4
  `review-07275744209932dd`, R5 `review-d2c1a59fe65b909d` — todas approved y
  quemadas con su ack exacto.
- PENDIENTE DE ACEPTACIÓN MANUAL: (a) los valores del brief "3 posiciones,
  premios 60/10/5" vs el motor Q80 (5 posiciones, 80/8/4/2/1): la UI muestra
  siempre la verdad del juego activo; (b) chips repetidos en pestañas de
  resultado (cosmético menor, detectado en captura, no corregido); (c) prueba
  de lanzador Windows y zoom nativo real, no cubiertos por el barrido.

## Configuración de reglas de juego (solicitud del usuario: nada hardcodeado)

Diagnóstico (explorado, no asumido): `Game.prizes` era `tuple[int,int,int,int,int]`
de longitud fija 5 y `GAME = Game("Quiniela 80", 100, 5, (80,8,4,2,1), True)` era
constante en `contracts.py:36` → atrapaba posiciones y premios. `session.py` ya
itera `zip(GAME.prizes, results, strict=True)` (genérico). El frontend ya
renderiza `catalog.game.{numbers,positions,allows_repeats,prizes}` dinámicamente
solo que "Apuesta mínima por número" estaba fija en `RD$1`.

Diseño (decision-complete):
- `Game.prizes` → `tuple[int, ...]`; `make_game(...)` valida (numbers>=2,
  positions>=1, positions<=numbers sin repeticiones, len(prizes)==positions,
  prize>=1, minimum_stake>=1) y `configure_game()` reemplaza el global `GAME`.
- `Settings` agrega `game_name/numbers/positions/prizes/allows_repeats/
  minimum_stake` (defaults = Q80 actual) y `from_environment` lee
  `LABORATORIO_GAME_{NAME,NUMBERS,POSITIONS,PRIZES,REPEATS,MINIMUM_STAKE}`;
  `__post_init__` aplica `configure_game` (cualquier Settings configura el juego).
- `api/catalog.py` expone el juego configurado, incluido `minimum_stake`.
- Frontend: `Game.minimum_stake: number` en tipos y el `dd` lee
  `formatDOP(catalog.game.minimum_stake)`; fixtures y tests actualizados.
- Salvaguarda: `test_game_is_the_fixed_quiniela_80_profile` pasa a afirmar el
  DEFAULT Q80 (no se retira, se refuerza con casos 3 posiciones 60/10/5).

Estado: dos writers en paralelo, superficies disjuntas (backend vs frontend).
