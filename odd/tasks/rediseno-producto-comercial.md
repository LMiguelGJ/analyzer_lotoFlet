# Rediseño comercial completo — seguimiento ODD

## Objetivo y autorización

Usuario aprobó `.pi/plans/rediseno-producto-comercial.md` completo (8 slices) y pidió ejecutarlo con ODD, modo YOLO y modo rápido: él hará las pruebas manuales al final; ir al grano. Inicio: rama `stage`, HEAD `d34d69e`. Un escritor por slice; tests focalizados + typecheck por slice; suite completa + build al cierre (RED-08). Commit convencional por slice en `stage`; push normal autorizado por YOLO; PR solo si se pide. Revisión nativa por commit de unidad según RDD; si bloquea, registrar y seguir sin bucle.

## Alcance y límites

Frontend `webapp/frontend/src` + tests afectados + este tracking. SIN backend, API, esquemas, payloads, claves internas, motores ni datos. Preservar `rng_audit/`, sesiones históricas, DB y el gitlink eliminado (sin staging). Identidad fijada: oscuro, paleta Pi (#171e26/#222830/#242f3b/#d0d4d8/#adb5bf/#7eb3da), cuerpo sans + títulos serif cursiva coherente, radio 0, `sm:640 / nav:800 / wide:1100`. Vocabulario: «simulación» como artefacto; «perfil de juego» para reglas; «historial» para datos; «estrategia» para métodos guardados. «Sesión» se retira del copy visible; «lote» solo en «Lote de simulaciones». Semilla: requerida por contrato → autogenerada, visible/editable solo en Avanzado, jamás sugerida con su máximo legal. Verdad financiera y caveats intactos (neto ≠ delta, null ≠ 0, versiones/códigos/hashes en «Detalles técnicos», HISTORICAL_CAVEAT). URLs existentes conservadas; solo títulos/copy cambian.

## Modo rápido + YOLO (decisión del usuario)

Sin verificador independiente por unidad ni checkpoints renderizados por unidad; escritor corre tests focalizados + typecheck y reporta; padre hace spot check y commit. Tests manuales: usuario al final. Test-first en conductas deterministas nuevas (CTA perfil visible, 3 grupos, Avanzado cerrado, orden del desenlace); CSS/copy pasivo sin RED inventado. Se retiran solo aserciones puramente de copy obsoleto, dejando constancia; salvaguardas funcionales (finanzas, payloads, admisión, duplicados, foco, borradores, secretos) siempre intactas.

## Tareas

- [ ] **RED-01 — Vocabulario y navegación por tareas.** `ui-labels.ts` (voz única, semilla como etiqueta de Avanzado), `Shell.tsx` (nav: Simulaciones · Perfiles de juego · Historiales · Estrategias · Administración + promesa «Simulaciones honestas con datos históricos.»), `App.tsx` (títulos coherentes: /experimentos «Simulaciones», /nuevo «Crear simulación», /nuevo/sesion «Lote de simulaciones», /nuevo/perfil «Simulación con perfil», /:id «Resultado de la simulación», /configuraciones «Estrategias», /datos «Datos del laboratorio», /ajustes «Administración del laboratorio»; fallback con enlace primario). Nav Perfiles→/datos#perfiles y Historiales→/datos#historiales (anclajes los agrega RED-03). Checks: tests App/Shell + typecheck.
- [ ] **RED-02 — «Crear simulación» en 3 grupos.** `new-experiment/index.tsx`: Reglas del sorteo / Selección / Límites con valores ejemplo; «Ajustes avanzados» cerrado (semilla autogenerada + Cambiar, liquidación, minutos, estrategias); un solo primario; errores por campo + foco. Checks: suite NewExperiment + typecheck; RED de «3 grupos + semilla oculta».
- [ ] **RED-03 — Perfiles de juego visibles.** `data/index.tsx` orden Perfiles → Historiales → Importar → Avanzadas con anclajes #perfiles/#historiales; CTA «Crear perfil de juego» visible sin desplegar; `ProfileEditor.tsx` plantilla Quiniela (00–99, 3 posiciones, 60/10/5, RD$1, «sin escala»), ID/revisión a «Detalles técnicos», verdad de multiplicadores intacta. Checks: suites Data/History/ProfileEditor + typecheck.
- [ ] **RED-04 — Perfil y lote con revelado progresivo.** `ProfileExperimentPage.tsx` («Simulación con perfil», resumen Reglas/Selección/Límites, requisitos con acción en contexto, técnicos a Avanzado) y `ProfileBatchPage.tsx` («Lote de simulaciones», selectores/definiciones/semilla plegados, caveat «la validación no reserva capacidad»). Checks: suites ProfileExperiment/ProfileBatch + typecheck; ≤4 decisiones visibles.
- [ ] **RED-05 — Resultados primero.** `DetailPage.tsx` (Desenlace: saldo, cambio, neto, motivo, clasificación; resto plegado con versiones/hash/categoría cruda) y `ComparisonPage.tsx` (saldo/neto/motivo lideran; tabla completa desplegable). Checks: suites Detail/Comparison/RunTrajectory + typecheck; neto ≠ delta.
- [ ] **RED-06 — Cola, Estrategias y Administración.** `QueueDrawer.tsx` («En curso / Esperando / Detenido», protocolo en Detalles), `configurations/index.tsx` (biblioteca opcional), `settings/index.tsx` (Administración: Capacidad → Límite → Diagnóstico plegado → Acceso agentes plegado, secreto oculto). Checks: suites QueueDrawer/Configurations/Settings + typecheck.
- [ ] **RED-07 — Jerarquía visual comercial.** `tokens.css`/`index.css`: escala tipográfica sobria (H1 32–40, razón 1.125–1.2), ritmo de espaciado, primaria dominante, superficies planas, foco 2px, radio 0, reduced-motion conservando estados; sin sombras/gradientes/animaciones nuevas. Checks: tokens.test + typecheck + diff-check.
- [ ] **RED-08 — Cierre: adapt + harden + audit.** Empty states que enseñan la siguiente acción; errores en lenguaje plano; tablet/coarse 44px; zoom 200%; orden de encabezados; suite completa --maxWorkers=1; typecheck; build; detect.mjs 0; Playwright solo lectura con fixtures (semilla fuera del flujo, CTA perfil visible, ≤4 decisiones/grupo, sin overflow). Commit final + push; aceptación manual del usuario.

## Evidencia y bloqueos

Documento creado antes de la primera escritura de fuente. Sin checks observados todavía. Última base verificada: entrega anterior `d34d69e` (485/485 tests, typecheck/build OK; crítica Impeccable 18/40 en `.impeccable/critique/2026-10-03T17-04-08Z__webapp-frontend-src.md`).

## Próximo paso

RED-01 delegado a un escritor único; al asentar: spot check + commit `feat(frontend): unify task navigation and simulation vocabulary`, actualizar este archivo, espejo Engram `odd/rediseno-producto-comercial/tasks` y todo, y continuar con RED-02. Actualizar tras cada transición.
