# Registro de reescritura de pruebas frontend

Worktree: `wt-rw-fe` (`wt/rw-fe`). Especificación: `docs/contrato-comportamiento-frontend.md`.

## Decisión y registro de cambios

Se conserva cada caso de prueba preexistente: el contrato fue extraído de esas aserciones, por lo que no se eliminó ningún comportamiento cubierto ni se reemplazó un cuerpo de test por uno más débil. Se añadieron citas de IDs contractuales en los nombres de pruebas (donde la correspondencia es directa) o en comentarios de trazabilidad por archivo (cuando el mismo archivo contiene una familia de reglas). Se conservaron también los casos más estrictos que el contrato resumido y los casos adicionales fuera del contrato.

- Tests eliminados: **ninguno**.
- Tests reemplazados/eliminados sin sustituto: **ninguno**.
- Registro por archivo/casos trazados:
  - `src/lib/profile-display.test.ts`: F-UTIL-001–003, comportamiento conservado y citado en cada caso.
  - `src/lib/profile-input.test.ts`: F-UTIL-004–007, conservado/citado.
  - `src/pages/experiments/replay.test.ts`: F-UTIL-008, conservado/citado.
  - `src/pages/new-experiment/batch-model.test.ts`: F-UTIL-009–012, conservado/citado.
  - `src/pages/new-experiment/model.test.ts`: F-UTIL-013–019, conservado/citado.
  - `src/pages/new-experiment/profile-model.test.ts`: F-UTIL-020–026, conservado/citado.
  - `src/test/vite-dev-server.test.ts`: F-UTIL-027–028, conservado/citado.
  - `src/components/ui/ui.test.tsx`, `src/lib/tokens.test.ts`, `src/lib/contrast.test.ts`, `src/lib/format.test.ts`: F-UI-001–025, conservado/citado.
  - `src/App.test.tsx`, `src/components/Shell.test.tsx`, `src/lib/ui-labels.test.ts`: F-SHELL-001–015, conservado/citado.
  - `src/api/client.test.ts`, `src/api/types.contract.test.ts`: F-API-001–031, conservado/citado.
  - `src/pages/new-experiment/NewExperimentPage.test.tsx`, `ProfileExperimentPage.test.tsx`, `ProfileBatchPage.test.tsx`: F-CREATE-001–053, conservado/citado.
  - `src/pages/experiments/DetailPage.test.tsx`, `ComparisonPage.test.tsx`, `src/components/{BalanceChart,ComparisonChart,FinancialMetrics,RunTrajectory,StatusLabel}.test.tsx`: F-RESULT-001–040, conservado/citado.
  - `src/pages/experiments/ExperimentsPage.test.tsx`, `src/components/{DataTable,ConfirmDialog,StrategyEditor,QueueDrawer,QueueProvider}.test.tsx`, `src/pages/configurations/ConfigurationsPage.test.tsx`, `src/pages/data/{DataPage,DataPageHistory,ProfileEditor}.test.tsx`, `src/pages/settings/SettingsPage.test.tsx`: F-LIST-001–098, conservado/citado.

## Cobertura por contrato

| Área | IDs verificados | Total | No cubiertos |
| --- | ---: | ---: | --- |
| F-UTIL | 28 | 28 | Ninguno identificado |
| F-UI | 25 | 25 | Ninguno identificado |
| F-SHELL | 15 | 15 | Ninguno identificado |
| F-API | 31 | 31 | Ninguno identificado |
| F-CREATE | 53 | 53 | Ninguno identificado |
| F-RESULT | 40 | 40 | Ninguno identificado |
| F-LIST | 98 | 98 | Ninguno identificado |
| **Total** | **290** | **290** | **Ninguno identificado** |

## Brechas y comportamiento adicional preservado

- `SettingsPage.test.tsx` conserva pruebas adicionales del editor de reglas de juego (valores almacenados, agregar/quitar premios, validación, guardado y rechazo 422), fuera de los 98 IDs F-LIST del contrato. No se eliminaron; requieren IDs contractuales nuevos si se busca cobertura trazable completa de ese comportamiento.
- CodeGraph no estaba inicializado en el worktree (`codegraph status` indicó “Not initialized”). No se inicializó para evitar crear artefactos fuera de las superficies autorizadas; la exploración estructural se limitó a los archivos contractuales y de test indicados. El `node_modules` junctionado apunta físicamente al checkout base, según la disposición declarada; los comandos Vitest usaron dependencias a través de ese junction, sin escribir en el checkout base.

## Convenciones aplicadas

- IDs visibles en títulos de `it`/`it.each` para casos de correspondencia directa; comentarios `Contract coverage` en el encabezado de archivos con reglas agrupadas.
- Consultas de Testing Library y aserciones existentes se mantienen, priorizando roles, nombres accesibles, atributos ARIA, foco y payloads exactos cuando ya eran parte del comportamiento afirmado.
- Copy frágil en español, cifras exactas, restricciones de no reintento/no invención y aserciones más estrictas se conservaron sin debilitarlas.
- Sin cambios a fuentes de producción ni backend; sin eliminaciones.
