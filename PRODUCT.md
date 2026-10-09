# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Una sola persona usuaria, confirmada (2026-10-05): conoce el dominio de la lotería, quiere probar
estrategias de Quiniela 80 sobre datos históricos y tiene dificultades reales con interfaces técnicas.
Escenario real: usa la herramienta sobre todo en el celular (también en computadora), con poco tiempo, y
quiere responder «¿esta estrategia aguanta o se queda sin plata?» antes de comprometer dinero real.

## Product Purpose

Laboratorio local de simulación financiera para estrategias de Quiniela 80 sobre un historial congelado.
Permite configurar las reglas del juego, crear simulaciones (individuales, por lote, de perfiles y
backtests históricos), analizar resultados, comparar corridas, seguir la cola de experimentos y
administrar datos. Éxito: la persona completa cada tarea desde el celular, sin jerga, guiada paso a paso,
y entiende el resultado financiero de un vistazo para decidir con datos, no con esperanza.

## Positioning

La única herramienta de simulación de lotería que trata la verdad financiera como protagonista, se usa
cómoda en el celular y dice siempre lo mismo: esto SIMULA, no predice ni garantiza rentabilidad.

Lo que no se puede copiar honestamente:

- **Verdad financiera visible** — capital, meta de saldo, duración y caveats nunca se esconden ni se aplazan.
- **Trazabilidad de cada corrida** — versiones, huellas, fuente de datos y, en corridas históricas nuevas,
  sesiones y apuestas consultables. Lo que no se guardó se declara («Detalle no almacenado»); nunca se reconstruye.
- **Guía paso a paso** — cinco pasos, una decisión por vez, lenguaje cotidiano; lo avanzado queda plegado, no eliminado.

## Operating Context

Herramienta local (Windows, `iniciar-laboratorio.bat`, `http://127.0.0.1:8765/`), usada desde el navegador
del celular y también en escritorio. Historial de Quiniela 80 descargado y congelado en
`chance_express_history.json`; corre sobre Python (FastAPI) + frontend compilado (Vite, React, TypeScript,
Tailwind). No hay apuestas reales, no hay sorteos en vivo, no se publica en Internet y funciona sin red:
ningún recurso (fuentes incluidas) puede depender de servicios externos. Sesión típica: configurar reglas →
crear simulación guiada → leer resultado → comparar → ajustar. La cola procesa experimentos de a uno.

## Capabilities and Constraints

- Asistente de cinco pasos común a los cuatro creadores: Estrategia → Reglas → Alcance → Capital y meta → Revisión.
  Una decisión por paso, resumen antes de confirmar; lo avanzado plegado («Avanzado» / «Detalles técnicos»).
- Tareas confirmadas, todas importantes: analizar resultados, generar combinaciones, seguir experimentos y administrar datos.
- Mobile-first en todo: ninguna tarea requiere escritorio.
- Reglas del juego configurables de punta a punta (números, posiciones, premios, repeticiones, apuesta mínima);
  nada hardcodeado en la interfaz.
- La información financiera clave (capital, meta de saldo, duración, caveats) nunca se oculta ni se aplaza.
- Backend, API, contratos, datos históricos y base de datos son de SOLO LECTURA para el trabajo de diseño:
  no se cambian endpoints, payloads, identidades, huellas ni semántica financiera nativa.
- Terminología de dominio en español: sorteo, posición, premio, apuesta, capital, meta de saldo, duración,
  estrategia, historial, sesión.
- La UI no promete predicción ni rentabilidad; todo resultado muestra su caveat.
- Toda la interfaz se escribe **en español**.
- Sin conexión: las fuentes y cualquier activo se entregan con la aplicación (autoalojados).

Explícitamente fuera de alcance: sesiones consecutivas, mallas, Monte Carlo y estabilidad (plan 80/20).

## Brand Commitments

Mundo visual vinculante (decisión del usuario, 2026-10-09): **el sistema de diseño de BossFarmer, tal cual**
(taller industrial: chapa mate oscura, placas con hairlines, leyendas condensadas en versalitas, esquina
viva, cero sombras), adaptado solo donde la naturaleza de este producto lo exige. Reemplaza al mundo
Material 3 (decisión del 2026-10-05), que queda como anti-referencia. Los originales de BossFarmer se
conservan en `docs/referencia-bossfarmer/`.

Se conservan los compromisos conductuales: sin gamificación, sin hype, sin promesas de ganancia.
No hay logo definitivo: hoy se usa la marca tipográfica «Laboratorio Quiniela 80». El monograma BF
pertenece a BossFarmer y no se reutiliza.

## Evidence on Hand

- Historial real congelado: `chance_express_history.json` (descargado por `download_chance_express.py`).
- Especificaciones: `docs/especificaciones-laboratorio-integral.md`; contratos de comportamiento en
  `docs/contrato-comportamiento-backend.md` y `docs/contrato-comportamiento-frontend.md`.
- Suites de tests de backend y frontend; el estado vigente se verifica ejecutándolas, no se cita de memoria.
- No hay clientes, testimonios, benchmarks ni métricas de negocio: no se inventan. Las cifras de pantalla
  provienen del backend o de fixtures etiquetados.

## Product Principles

1. La verdad financiera primero: capital, meta, duración y caveats siempre visibles.
2. Guía antes que panel: cada configuración se conduce paso a paso, sin jerga.
3. El celular manda: si una tarea no funciona en un teléfono, no está terminada.
4. Lo avanzado existe, pero estorba menos: plegado, secundario, jamás eliminado.
5. Simula y dilo: cero promesas de predicción o ganancia en toda la interfaz.
6. Lo que no se guardó se dice, no se inventa.

## Accessibility & Inclusion

El usuario declara dificultad real con interfaces técnicas: claridad visual y lenguaje cotidiano son
requisito de producto. Contraste suficiente (texto `legend` sobre `chassis` y `chassis` sobre `signal`),
objetivos táctiles de al menos 48 px, teclado completo, foco visible, zoom del navegador sin romper el
diseño y respeto de `prefers-reduced-motion`. Cuando el color no basta, el estado se dice con texto
(«Meta alcanzada», «Sin capital»), nunca solo con tono.
