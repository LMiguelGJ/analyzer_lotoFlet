# Spec — Reglas configurables en UI + reescritura segura de pruebas

Fuente: elicitation spec-assistant (4 preguntas, ciclo cerrado).
Asunciones: [A1]–[A7]. Hechos: [F1]–[F4]. Véase `odd/tasks/rediseno-ledger-v2.md`.

## Objetivo

1. Las reglas del juego se editan desde la UI (hoy solo por env/CLI).
2. La suite se reescribe desde cero **sin perder conocimiento**: se extrae el
   contrato de comportamiento antes de borrar nada.
3. Se cierra el defecto cosmético de los chips repetidos.

## [A1] Editor de reglas del juego en Ajustes

- Ubicación: `/ajustes`, dentro del plegado «Avanzado».
- Campos: números posibles, posiciones por sorteo, premios por posición (lista de
  longitud = posiciones), repeticiones permitidas, apuesta mínima por número.
- Validación en vivo con las mismas reglas que `make_game()` (numbers>=2,
  positions>=1, positions<=numbers sin repeticiones, len(prizes)==positions,
  prize>=1, minimum_stake>=1).
- Aviso visible: cambiar las reglas del juego afecta las simulaciones futuras.
- [A6] Persistencia: store de ajustes del backend (`0003_settings.sql`), no
  variables de entorno. Las reglas sobreviven reinicios. `LABORATORIO_GAME_*`
  queda como valor inicial/fallback cuando no hay nada persistido.
- [A7] Las simulaciones guardadas conservan las reglas con las que se crearon.

## [A2] Reescritura segura de pruebas

Orden estricto por suite:

1. **Extraer el contrato**: documentar cada regla de negocio/comportamiento que
   las pruebas actuales verifican, en `docs/contrato-comportamiento-{backend,frontend}.md`.
2. **Escribir pruebas nuevas** contra ese contrato.
3. **Borrar las viejas** recién cuando la cobertura del contrato sea igual o mejor.

[A5] «Igual o mejor» se mide por **comportamientos cubiertos**, no por cantidad
de tests. El número final puede ser menor. Toda prueba retirada se registra en
`webapp/reports/verification/registro-pruebas-copy.md` con su motivo.

## [A3] Tres lanes en paralelo (worktrees aislados)

| Lane | Alcance | Superficie |
|---|---|---|
| A | Contrato + reescritura backend | `docs/contrato-comportamiento-backend.md`, `webapp/backend/tests/**` |
| B | Contrato + reescritura frontend + chips | `docs/contrato-comportamiento-frontend.md`, `webapp/frontend/src/**/*.test.*`, `pages/experiments/DetailPage.tsx` |
| C | Editor de reglas (backend + frontend) | `webapp/backend/laboratorio/**`, `webapp/frontend/src/pages/settings/**`, `api/types.ts` |

Cada slice cierra con revisión nativa y commit convencional.

## [A4] Cerrado acá vs aceptación manual

- **Se corrige acá**: chips de estado repetidos en las pestañas de resultado.
- **Aceptación manual del usuario** (no automatizable en este entorno):
  - zoom nativo real del navegador (el barrido usó viewport+deviceScaleFactor).
  - prueba del lanzador `iniciar-laboratorio.bat` en Windows real.

## Gates de verificación por slice

- Backend: `python -m pytest -q -p no:playwright` (reportar totales y delta contra
  la base), `python -m ruff check laboratorio tests`.
- Frontend: `npx vitest run --maxWorkers=1`, `npm run typecheck`, `npm run build`.
- Ambos: `node scripts/detect.mjs --json webapp/frontend/src` = `[]`.
- Revisión nativa por slice con lineage real, luego push a `origin/stage`.

## Fuera de alcance

- Backend/API/contratos de solo lectura en lo que no sea el editor de reglas
  (endpoints nuevos permitidos solo para settings de juego).
- Datos históricos y base de datos existente: sin migraciones destructivas.
- Identidad visual: fijada (Pi oscuro, sans + serif, radio 0).
