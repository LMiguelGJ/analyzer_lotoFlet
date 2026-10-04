# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Persona común que quiere probar estrategias de Quiniela 80 sobre datos históricos
sin entender conceptos técnicos. Escenario real: usa la herramienta local en su
computadora, con poco tiempo, y quiere responder una sola pregunta — «¿esta
estrategia aguanta o se queda sin plata?» — antes de comprometer dinero real.
(Supuesto inferido del brief y del README; el usuario durmió durante la sesión de
diseño y no se le entrevistó.)

## Product Purpose

Laboratorio local de simulación financiera para estrategias de Quiniela 80 sobre un
historial congelado. Permite crear simulaciones con un formulario simple de tres
grupos (reglas del sorteo, selección, límites), ver si la estrategia alcanza la meta
de saldo antes de agotarse, y comparar resultados entre estrategias. Éxito: la
persona entiende el resultado financiero de un vistazo y decide con datos, no con
esperanza.

## Positioning

La única herramienta de simulación de lotería que trata la verdad financiera como
protagonista: capital, meta, duración y caveats siempre visibles, cero jerga interna
en pantalla, y una advertencia honesta e inamovible — esto SIMULA, no predice ni
garantiza rentabilidad. Un producto vecino no podría copiar esta disciplina de
«verdad financiera primero» sin renunciar a su propio lenguaje técnico.

## Operating Context

Herramienta local (Windows, `iniciar-laboratorio.bat`, `http://127.0.0.1:8765/`).
Historial de Quiniela 80 descargado y congelado en `chance_express_history.json`;
corre sobre Python (FastAPI) + frontend compilado. No hay apuestas reales, no hay
sorteos en vivo, no se publica en Internet. Sesión de trabajo típica: crear
simulación → leer resultado → comparar → ajustar estrategia. La cola de ejecución
procesa experimentos de a uno.

## Capabilities and Constraints

- Formulario simple de 3 grupos con estos valores de referencia (brief no negociable):
  REGLAS DEL SORTEO — números posibles 00–99, 3 posiciones por sorteo, repeticiones
  permitidas, premios por posición 60/10/5, apuesta mínima por número RD$1.
  SELECCIÓN — transición 60% + fríos 40%, cobertura 10 números. LÍMITES — capital
  RD$2.000, meta de saldo RD$2.800, duración máxima 12 sorteos.
- Cero jerga técnica visible: semillas, hashes, JSON, esquemas, enumeraciones,
  identificadores y números sin sentido van autogenerados y plegados en
  «Avanzado» / «Detalles técnicos». La información financiera clave nunca se oculta.
- Backend, API, contratos, datos históricos y base de datos son de SOLO LECTURA para
  cualquier trabajo de frontend: no se cambian endpoints ni payloads.
- Terminología de dominio en español dominicano/chileno neutro: sorteo, posición,
  premio, apuesta, capital, meta de saldo, duración, estrategia, historial.
- La UI no promete predicción ni rentabilidad; todo resultado muestra su caveat.

## Brand Commitments

Identidad fijada por el usuario (vinculante): paleta oscura Pi (azul-gris profundo,
fondo #171e26 y superficies cercanas), tipografía sans + serif (serif para
encabezados y momentos editoriales, sans para UI, mono/tabular para cifras), radio
de esquinas 0 en toda la interfaz. Textura sutil de papel milimetrado de fondo,
estática. Sin gamificación, sin hype, sin promesas de ganancia.

## Evidence on Hand

- Historial real congelado: `chance_express_history.json` (descargado por
  `download_chance_express.py`).
- Especificación funcional completa: `especificaciones-laboratorio-web.md`.
- Suite de 501 tests del frontend (35 archivos) como salvaguarda funcional.
- Evidencia de verificación previa: `webapp/reports/verification/` (lw15–lw18).
- No hay clientes, testimonios, benchmarks ni métricas de negocio reales: no se
  inventan. Las cifras de resultados en pantallas provienen del backend o de
  fixtures etiquetados como tales.

## Product Principles

1. La verdad financiera manda: capital, meta, duración y caveat visibles siempre.
2. Una decisión por pantalla; el resto se pliega o se pospone.
3. El lenguaje del usuario es el del juego (sorteo, apuesta, premio), jamás el del
   código (semilla, hash, payload).
4. Todo estado se explica y se recupera: vacíos que enseñan, errores que se
   resuelven, cargas que informan.
5. Sobriedad con carácter: serio como un estado de cuenta, no como un panel CRUD.

## Accessibility & Inclusion

Contraste AA verificado por tokens (medido en `src/lib/tokens.test.ts`), navegación
completa por teclado con foco visible, `prefers-reduced-motion` respetado, sin
overflow horizontal a 200% de zoom ni a 320px de ancho. Sin conformidad WCAG formal
declarada (no se afirma lo que no se verifica).
