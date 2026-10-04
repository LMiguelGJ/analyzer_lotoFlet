# Plan — Rediseño v2 «Estado de cuenta» (frontend completo)

Autor: el Gentleman (dirección de diseño + orquestación ODD).
Estado: **aprobado por delegación explícita del usuario** («no preguntes nada,
ejecutá todo… modo YOLO»). Preguntas abiertas al final del informe final.
Restricciones duras: backend/API/contratos/datos/DB **solo lectura**; identidad
fijada (paleta oscura Pi, sans + serif, radio 0); verdad financiera y caveats
intactos; suite actual de 501 tests sin perder salvaguardas funcionales.

## 1. Evidencia de partida (crítica Impeccable, doble evaluación)

- **Evaluación A (fuente/diseño, agente independiente): 26/40 — Aceptable.**
  P1: (a) recorridos de perfil/lote exponen demasiadas decisiones fuera del
  brief (`ProfileExperimentPage.tsx:171-216`, `ProfileBatchPage.tsx:322-323`);
  (b) comparación con métricas y jerga técnica sin respuesta dominante
  (`ComparisonPage.tsx:89-103,124-149`); (c) vocabulario mixto
  experimento/simulación/estrategia/perfil (`Shell.tsx:22-27`, `App.tsx:21-85`).
  P2: bytes crudos y diagnóstico en Ajustes (`settings/index.tsx:267-317`);
  filas de cola sobrecargadas (`QueueDrawer.tsx:99-145`). P3: estados vacíos
  escuetos (`ExperimentsPage.tsx:205`, `configurations/index.tsx:190`).
  Fortalezas a preservar: honestidad financiera, recuperación robusta de
  errores, base de identidad/accesibilidad.
- **Evaluación B (navegador real + detector):** se ejecuta con verificador
  autorizado; sus hallazgos se incorporan al detalle de cada slice antes de
  implementar. Detector determinista sobre `webapp/frontend/src`: **0 hallazgos**
  (`detect.mjs --json` → `[]`).
- Crítica previa (pre-rediseño v1) y evidencia: `.impeccable/critique/…`,
  `webapp/reports/verification/`.

## 2. Dos direcciones visuales y decisión

### Dirección 1 — «Estado de cuenta» (ledger financiero)
La interfaz se lee como un extracto financiero impreso: reglas hairline, cifras
tabulares mono alineadas, títulos serif sobrios, chips de estado discretos,
una acción primaria única. Cada pantalla es un documento que rinde cuentas:
lista = libro mayor; resultado = extracto con veredicto; creación = orden con
resumen vivo; ajustes = notas al pie del extracto.

### Dirección 2 — «Expediente» (dossier editorial)
Cada simulación es un caso con portada-veredicto, folios numerados y anexos
plegados; serif display dramático. Fuerte en resultados, débil en las tareas
operativas diarias (cola, ajustes, datos), donde el expediente es un disfraz.

### Decisión de dirección de diseño: **Dirección 1**
1. **La credibilidad que pide el brief es financiera, no narrativa.** El
   producto maneja capital, meta y riesgo: el lenguaje del extracto es el que
   un producto comercial serio usa para hablar de dinero; el dossier aporta
   drama, no autoridad contable.
2. **Escala a las 9 superficies sin romperse.** El expediente se quiebra en
   cola/ajustes/datos; el ledger mantiene una sola gramática de punta a punta
   (que es exactamente lo que hoy falla: «se siente ensamblado desde módulos»).
3. **La identidad fijada vive nativa en el ledger** (recto, hairline, serif +
   sans + mono): menos disfraz, más precisión — la línea que separa lo
   comercial serio de lo amateur.
4. **Carga cognitiva:** el ledger ordena por columnas y jerarquía de cifras
   (decisión por bloque, ≤4); el expediente invita a leer prosa, que el brief
   prohíbe como recurso de jerarquía.

El dispositivo más fuerte de la Dirección 2 —«veredicto primero»— se absorbe
como bloque de apertura de resultados (todo extracto abre con su resultado),
sin mezclar gramáticas. Sin tiro de dados: el usuario delegó la decisión de
dirección en la dirección de diseño y la sesión es sin interacción.

Contrato de dirección (5 bloques) y sistema duradero: **`DESIGN.md`** (raíz).
Verdad de producto: **`PRODUCT.md`** (raíz). El «Resumen de la orden» y el
«Veredicto» son los componentes firma.

## 3. Glosario canónico (vocabulario único en toda la UI)

| Visible en UI | Nunca visible | Notas |
|---|---|---|
| simulación | experimento, sesión | sustantivo principal del producto |
| estrategia | selector, sistema, componente | biblioteca reutilizable |
| sorteo · posición · premio · apuesta | draw, bet, settlement | lenguaje del juego |
| capital · meta de saldo · duración | max_bets, goal, límite técnico | verdad financiera siempre visible |
| historial / datos del historial | perfil de datos, JSON, CSV | lo técnico va en «Avanzado» |
| código de repetición (Avanzado) | semilla, seed, 9.007.199.254.740.991 | autogenerado; el número absurdo jamás en pantalla |
| cola de cálculo | cola de trabajos, payload | estados en lenguaje llano |
| Detalles técnicos / Avanzado | hash, esquema, enumeración, id crudo | único hogar legal de lo técnico |

## 4. Reglas de composición (no negociables)

- Una acción primaria por pantalla; ≤4 decisiones visibles por bloque.
- Veredicto/cifras primero, controles después; jerarquía por estructura, nunca
  por párrafos.
- Vacíos que enseñan (explican + ofrecen el siguiente paso como única acción),
  errores que recuperan (causa + acción concreta + datos preservados), cargas
  que informan (estructura estable, sin saltos).
- Jerga técnica solo en «Avanzado» / «Detalles técnicos»; información
  financiera clave (capital, meta, duración, saldo, caveat) nunca oculta.
- Caveat en toda superficie de resultados: esto SIMULA, no predice ni garantiza
  rentabilidad.
- Radio 0, sin sombras, sin gradientes decorativos; color semántico solo en
  dinero/estado; acento ≤10% de la pantalla.

## 5. Alcance por slices (commits convencionales por unidad)

| Slice | Archivos principales | Commit | Notas |
|---|---|---|---|
| **S0 Fundación** | `styles/tokens.css`, `styles/index.css`, nuevo `components/ui/*` (Block, SectionHeader, Figure/Stat, Money, Chip, Button, Field, Disclosure, EmptyState, ErrorBanner, Loading, Verdict, OrderSummary) + tests | `feat(frontend): establish ledger design system primitives` | un writer; base de todo lo demás |
| **S1 Shell + vocabulario** | `components/Shell.tsx`, `App.tsx`, `lib/ui-labels.ts`, `lib/format.ts` | `feat(frontend): unify product vocabulary and rebuild app shell` | glosario §3; nav Simulaciones · Estrategias · Datos · Ajustes |
| **S2 Creador (brief)** | `pages/new-experiment/index.tsx`, `model.ts`, tests | `feat(frontend): rebuild creation form as a three-block order` | 01 Reglas / 02 Selección / 03 Límites con defaults del brief; semilla autogenerada plegada; «Resumen de la orden» vivo; payload y validaciones intactos |
| **S3 Resultado** | `pages/experiments/DetailPage.tsx`, `components/FinancialMetrics.tsx`, `BalanceChart.tsx`, `RunTrajectory.tsx`, `StatusLabel.tsx` | `feat(frontend): lead results with the verdict and key figures` | veredicto + 3 cifras + motivo de cierre + caveat |
| **S4 Comparación** | `pages/experiments/ComparisonPage.tsx`, `components/ComparisonChart.tsx` | `feat(frontend): make comparison answer what changed first` | 3–4 métricas legibles; ratios/técnicos plegados; sin «ROI/drawdown/N/A» crudos |
| **S5 Listado** | `pages/experiments/index.tsx`, `components/DataTable.tsx` | `feat(frontend): present the simulation list as a ledger` | chips de estado, filtros compactos, vacío que enseña |
| **S6 Datos y estrategias** | `pages/data/index.tsx`, `ProfileEditor.tsx`, `pages/configurations/index.tsx`, `StrategyEditor.tsx` | `feat(frontend): simplify data and strategy management language` | creación visible; importación/CSV/JSON plegada; una acción primaria |
| **S7 Cola y ajustes** | `components/QueueDrawer.tsx`, `pages/settings/index.tsx` | `feat(frontend): clarify queue and settings around plain-language states` | una acción por fila; bytes/diagnóstico en Avanzado |
| **S8 Pulido** | transversal (microinteracciones, estados, teclado, zoom, tablet) | `polish(frontend): harden states, motion and responsive polish` | pass de `polish` + `harden` + `adapt` |
| **S9 QA + evidencia** | `webapp/reports/verification/rediseno-v2/*`, docs | `docs(frontend): record redesign evidence and verification` | suite, typecheck, build, detect 0, barrido navegador, capturas |

Ejecución: ODD con `odd/tasks/rediseno-ledger-v2.md` + mirror Engram; writers en
worktrees aislados, máximo 2 en paralelo y solo con archivos disjuntos (S0 y S2
secuenciales; pares S3/S4, S5/S6, S7/S8 en paralelo). TODO visible siempre
actualizado. Commits de trabajo en la rama `stage`.

## 6. Política de tests

- **501 tests actuales = salvaguardas funcionales.** Ninguna se retira por
  comodidad. Los tests de comportamiento (payload, validación, formato,
  accesibilidad, rutas) se mantienen y se ajustan solo donde cambia el texto
  visible.
- **Copy obsoleto:** solo se retira una prueba si verifica un elemento/cadena
  que el rediseño elimina por diseño (p. ej. semilla visible con el número
  9.007.199.254.740.991). Cada retiro se registra en
  `webapp/reports/verification/rediseno-v2/registro-pruebas-copy.md` (archivo,
  prueba, motivo, reemplazo). Todo lo demás se actualiza al nuevo glosario.
- Tests nuevos para primitivas de UI, estados y glosario.

## 7. Verificación (gates por slice y final)

Por slice: tests enfocados verdes + `tsc --noEmit` verde + suite completa verde
al cerrar el commit. Final: `vitest run` completo (conteo ≥ 501, sin pérdidas no
registradas), `tsc --noEmit`, `vite build`, `detect.mjs --json` sobre targets
cambiados = 0, barrido de navegador con fixtures desktop 1440×900 y tablet
834×1112 (todas las rutas + QueueDrawer), foco/teclado, zoom 200% y 320px sin
overflow horizontal, `prefers-reduced-motion`, screenshots como evidencia en
`webapp/reports/verification/rediseno-v2/`.

## 8. Revisión nativa y entrega

- RDD activo: **revisión nativa por slice de commits** vía `gentle_review`
  (inspect → start → capture → acknowledge), agrupando unidades adyacentes por
  transacción como se hizo en el rediseño v1. Sin aprobaciones ni cierres
  inventados: cada cierre deja su lineage y evidencia en `odd/tasks/…`.
- Entrega: commits convencionales en `stage` + **push a `origin/stage`** +
  informe final con comandos, conteos y capturas reales; pendientes de
  aceptación manual y limitaciones, explícitos.

## 9. Riesgos y límites declarados

- Cambios de copy rompen aserciones de texto: se actualizan con el glosario y se
  documentan retiros (§6).
- El backend puede estar caído en el barrido de navegador: los estados de
  error/vacío son parte de la evaluación, no un impedimento.
- No se afirma conformidad WCAG formal ni pruebas de lanzador Windows nuevas:
  solo lo verificado entra en el informe.
- No hay generación de imágenes en el flujo de dirección (superficie Operate,
  presupuesto de ejecución nocturna): se documenta como desviación conocida.
