# Feature: Reestructura y unificación de la web

Origen: Judgment Day sobre la estructura completa (target `fdab1f3`), ledger en
`odd/reviews/judgment-day-estructura-web.md` (10 hallazgos confirmados C1-C10,
5 sospechosos S1-S5, veredicto ESCALATED por contradicciones de severidad en C5/C6).
Decisión del usuario (2026-10-05): ejecutar las 4 fases completas.

Pregunta del usuario que guía todo: «¿por qué los simuladores son cosas distintas a
los históricos?». Respuesta de diseño: son el mismo trabajo (probar una estrategia
sobre el historial); la diferencia es un parámetro de alcance (una sesión desde un
sorteo frente a todo el historial con sesiones repetidas).

## Estructura objetivo

1. **Simulaciones**: un listado y un asistente únicos (Estrategia → Reglas del juego
   → Alcance → Capital y meta → Revisar), un resultado común y «Repetir con cambios»
   para todos los tipos.
2. **Estrategias**: una sola biblioteca.
3. **Datos**: historiales e importación en un solo formulario.
4. **Ajustes**: «Reglas del juego» como única fuente.

Término único: **Simulación** (palabra del usuario). Rutas `/simulaciones/...` con
redirecciones desde `/experimentos/...` para no romper enlaces guardados.

## Reglas de la reestructura

- Los 14 escenarios dorados (`webapp/backend/tests/test_backtest_golden.py`) deben
  seguir exactos en cada unidad: protegen el motor.
- No se pierde capacidad: todo flujo actual sigue existiendo, aunque entre por otra
  puerta.
- Cambios de datos persistidos (F3) llevan migración y prueba de migración.
- Una unidad de trabajo = un commit + revisión nativa.

## Tasks

### F1 — Bugs y nombres

- [ ] T1. Título móvil (S1), enlace «Editar reglas» (C6), nombre único
  «Simulaciones» en menú, aria-label, títulos y rutas con redirecciones (C2), acción
  primaria declarada por ruta en vez de regex en el Shell (C4).

### F2 — Simulaciones unificadas

- [ ] T2. Listado único de simulaciones (clásicas, con perfil e históricas) con filtro
  por alcance; sin pestañas internas (C1, C3); «Repetir con cambios» en todos los
  tipos (C8).
- [ ] T3. Asistente único «Nueva simulación» con paso de Alcance; usa catálogo,
  `StrategyEditor` y biblioteca de estrategias también para historial completo
  (C7, C10). Los flujos con perfil quedan como una opción de datos dentro del mismo
  asistente.
- [ ] T4. Modelo de vista y componente de resultado comunes (C9).

### F3 — Una biblioteca y una fuente de reglas

- [ ] T5. Biblioteca única de estrategias (`/configurations` + `/strategies`, C5) con
  migración de datos.
- [ ] T6. Fuente única de reglas del juego (`settings/game` + perfiles de juego, C6)
  con migración de datos.

### F4 — Limpieza del backend

- [ ] T7. Versiones de perfil v1-v4 como adaptadores de lectura sobre v5 (S3).
- [ ] T8. API del agente sobre la misma API con autenticación propia, sin router
  espejo (S4).
- [ ] T9. Importación única (endpoint y formulario) con modo avanzado plegado (S5);
  borrado y orden en el listado de corridas (S2).

### Cierre

- [ ] T10. QA: suites completas, build, verificación visual móvil/escritorio,
  re-crítica Impeccable para medir contra el 22/40, push.

## Verification

Backend: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/ -q` (incluye los
14 dorados) y `ruff`. Frontend: `npm test -- --run`, `npm run typecheck`,
`npm run build`. Visual: capturas a 390 px y 1440 px.

## Evidencia (commits)

- T1-T10: pendiente
