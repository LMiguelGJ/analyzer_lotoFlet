# Registro de pruebas retiradas o reescritas por copy obsoleto (rediseño ledger v2)

Política: ninguna salvaguarda funcional se retira. Solo se reescribe o retira
una prueba cuando verifica un elemento o cadena que el rediseño elimina por
diseño. Cada caso queda aquí con su motivo y reemplazo.

## Retiradas (parte eliminada por diseño)

| Archivo | Prueba | Motivo | Reemplazo |
|---|---|---|---|
| `src/components/QueueDrawer.test.tsx` | `keeps mobile navigation closed when Escape dismisses only the drawer` | S1 eliminó el botón «Abrir navegación» (la navegación es siempre visible: rail en escritorio, barra en tablet). La parte del toggle ya no existe. | Misma prueba reescrita como `dismisses only the drawer on Escape and returns focus to the queue control`: conserva la salvaguarda real (Escape cierra solo el drawer y devuelve el foco al control de cola). |

## Reescritas por glosario (sin cambio de comportamiento)

- «Administración» → «Ajustes» (enlace y encabezado de ruta): NewExperimentPage, QueueDrawer, SettingsPage.
- Botón «Cola» → «Abrir cola de cálculo» (nombre accesible nuevo del control): QueueDrawer, QueueProvider.
- Copy llano en Datos/Estrategias/Listado/Resultado/Comparación/Cola/Ajustes: expectativas actualizadas al texto real renderizado; todas las aserciones de comportamiento (payloads, validación, paginación, borrado con confirmación, flujo de importación, sondeo único, reenvío manual, foco) se conservan.

## Conteo

- Línea base previa al rediseño v2: 501 pruebas (35 archivos).
- Tras integrar S0–S7: 551 pruebas (37 archivos), 0 fallos, 0 omitidas.
