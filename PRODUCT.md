# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Persona común que quiere probar estrategias de Quiniela 80 sobre datos históricos
sin entender conceptos técnicos. Confirmado por el usuario (2026-10-05): es el único
usuario, conoce el dominio de la lotería pero tiene dificultades reales para
configurar la herramienta; la navegación y la configuración actuales le resultan
confusas y visualmente desagradables. Escenario real: usa la herramienta en su
celular la mayor parte del tiempo (también en computadora), con poco tiempo, y
quiere responder «¿esta estrategia aguanta o se queda sin plata?» antes de
comprometer dinero real.

## Product Purpose

Laboratorio local de simulación financiera para estrategias de Quiniela 80 sobre un
historial congelado. Permite configurar las reglas del juego, crear simulaciones,
analizar resultados históricos, generar y evaluar combinaciones, seguir
experimentos y administrar datos. Éxito: la persona completa cada tarea desde el
celular, sin jerga, guiada paso a paso, y entiende el resultado financiero de un
vistazo para decidir con datos, no con esperanza.

## Positioning

La única herramienta de simulación de lotería que trata la verdad financiera como
protagonista y, al mismo tiempo, se usa como una app moderna de celular: guía paso
a paso, lenguaje cotidiano, cero jerga interna en pantalla, y la advertencia honesta
e inamovible — esto SIMULA, no predice ni garantiza rentabilidad.

## Operating Context

Herramienta local (Windows, `iniciar-laboratorio.bat`, `http://127.0.0.1:8765/`),
usada primariamente desde el navegador del celular y también en escritorio.
Historial de Quiniela 80 descargado y congelado en `chance_express_history.json`;
corre sobre Python (FastAPI) + frontend compilado. No hay apuestas reales, no hay
sorteos en vivo, no se publica en Internet. Sesión típica: configurar reglas →
crear simulación guiada → leer resultado → comparar → ajustar. La cola de ejecución
procesa experimentos de a uno.

## Capabilities and Constraints

- Configuración por guía paso a paso (decisión confirmada del usuario): toda tarea
  de configuración se conduce como asistente pregunta-por-pregunta con lenguaje
  cotidiano; lo avanzado queda plegado detrás de «Avanzado» / «Detalles técnicos».
- Tareas del producto (confirmadas por el usuario, todas importantes): analizar
  resultados, generar combinaciones, seguir experimentos y administrar datos.
- Interfaz mobile-first para todo: ninguna tarea requiere escritorio.
- Reglas del juego configurables de punta a punta (números, posiciones, premios,
  repeticiones, apuesta mínima); nada hardcodeado en la interfaz.
- La información financiera clave (capital, meta de saldo, duración, caveats) nunca
  se oculta ni se aplaza.
- Backend, API, contratos, datos históricos y base de datos son de SOLO LECTURA
  para el trabajo de frontend: no se cambian endpoints ni payloads.
- Terminología de dominio en español: sorteo, posición, premio, apuesta, capital,
  meta de saldo, duración, estrategia, historial.
- La UI no promete predicción ni rentabilidad; todo resultado muestra su caveat.

## Brand Commitments

Mundo visual fijado por el usuario (vinculante, 2026-10-05): **Material 3 para web**
(https://m3.material.io/develop/web) combinado con la disciplina de la skill
Impeccable. Mobile-first. La identidad previa (paleta oscura «Pi», Georgia serif,
radio 0, papel milimetrado) queda descartada por decisión explícita del usuario.
Se conservan los compromisos conductuales: sin gamificación, sin hype, sin promesas
de ganancia.

## Evidence on Hand

- Historial real congelado: `chance_express_history.json` (descargado por
  `download_chance_express.py`).
- Especificación funcional: `especificaciones-laboratorio-web.md`.
- Contratos de comportamiento: `docs/contrato-comportamiento-backend.md` (497
  ítems) y `docs/contrato-comportamiento-frontend.md` (290 ítems).
- Suite de tests: backend 856, frontend 565 (verdad al 2026-10-05, `2b2e82f`).
- No hay clientes, testimonios, benchmarks ni métricas de negocio reales: no se
  inventan. Las cifras de pantallas provienen del backend o de fixtures etiquetados.

## Product Principles

1. La verdad financiera primero: capital, meta, duración y caveats siempre visibles.
2. Guía antes que panel: cada configuración se conduce paso a paso, sin jerga.
3. El celular manda: si una tarea no funciona en un teléfono, no está terminada.
4. Lo avanzado existe, pero estorba menos: plegado, secundario, jamás eliminado.
5. Simula y dilo: cero promesas de predicción o ganancia en toda la interfaz.

## Accessibility & Inclusion

El usuario declara dificultad real con interfaces técnicas: la claridad visual y el
lenguaje cotidiano son requisito de producto, no lujo. Contraste suficiente,
objetivos táctiles cómodos, teclado y zoom del navegador sin romper el diseño,
respeto de `prefers-reduced-motion`.
