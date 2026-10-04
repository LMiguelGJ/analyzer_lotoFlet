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
- [ ] S1 Shell + glosario canónico (Shell, App, ui-labels, format) — en curso (writer en árbol principal)
- [ ] S2 Creador simple de 3 grupos con «Resumen de la orden» (brief no negociable)
- [ ] S3 Resultado con veredicto primero (DetailPage, FinancialMetrics, charts) — en curso (writer en worktree aislado `wt-s3`, rama `wt/s3`, node_modules por junction)
- [ ] S4 Comparación que responde «qué cambió» primero
- [ ] S5 Listado como libro mayor con estados y vacíos que enseñan
- [ ] S6 Datos y estrategias en lenguaje llano con lo técnico plegado
- [ ] S7 Cola y ajustes con estados llanos y una acción por fila
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
