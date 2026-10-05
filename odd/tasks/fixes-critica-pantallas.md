# Feature: Fixes de la crítica de pantallas (2026-10-05)

Fuente: snapshot `.impeccable/critique/2026-10-05T15-20-36Z__webapp-frontend-src.md`
(22/40 Nielsen, dual-agent). Decisiones del usuario (2026-10-05):
- Corregir TODO (los 5 issues de la crítica, en una tanda).
- Tema OSCURO por defecto (cambia DESIGN.md: era claro por defecto).
- Fuera de alcance (no seleccionado): pulido menor (foco visible, aria de
  colección, nombres internos menores) — queda como seguimiento.

## Tasks

- [ ] U1. Acciones únicas por pantalla (P1-1, /impeccable distill): suprimir el
  FAB donde la página define su propia acción primaria; un solo affordance por
  destino (nombre+botón de resultado → uno); un solo «Limpiar filtros».
  Superficies: webapp/frontend/src/components/Shell.tsx,
  webapp/frontend/src/pages/experiments/index.tsx, tests colocados.
- [ ] U2. Layout de escritorio (P1-2, /impeccable layout): tabla sin scroll
  horizontal espurio, rail con labels legibles, contenido que aproveche el
  ancho. Superficies: webapp/frontend/src/styles/**,
  webapp/frontend/src/components/Shell.tsx, tests colocados.
- [ ] U3. Tema oscuro por defecto: inversión del default (toggle conserva
  claro), tokens verificados en oscuro, DESIGN.md actualizado.
  Superficies: webapp/frontend/src/components/Shell.tsx,
  webapp/frontend/src/styles/**, tests colocados + DESIGN.md.
- [ ] U4. Solapamientos móviles (P2-4, /impeccable harden): FAB/Nav no tapan
  input de archivo (Datos), gráfico (Detalle), disclosure (Comparación), campos
  (Ajustes); verificar ≤320px y zoom. Superficies: webapp/frontend/src/styles/**,
  webapp/frontend/src/components/Shell.tsx.
- [ ] U5. Claridad del wizard + conclusión financiera primero (P1-3 + P2-5,
  clarify/distill): título + una decisión por paso en creación y Ajustes;
  «Guardar reglas» explícito; ruta perfil/estrategias guardadas demoradas;
  resultado/comparación: perder/meta/límite primero, nombres internos en
  «Detalles técnicos», comparación sin encuadre «ganador».
  Superficies: webapp/frontend/src/pages/new-experiment/**,
  webapp/frontend/src/pages/settings/**,
  webapp/frontend/src/pages/experiments/DetailPage.tsx,
  webapp/frontend/src/pages/experiments/ComparisonPage.tsx,
  webapp/frontend/src/pages/configurations/**,
  webapp/frontend/src/pages/data/**, tests colocados.
- [ ] U6. QA del ciclo: suite completa x3, typecheck, build, capturas móviles y
  escritorio de las 7 pantallas para verificación visual, commit final.

## Verification (por unidad)

Desde webapp/frontend: tests focales + typecheck; al cierre de cada unidad la
suite completa en verde (criterio: corridas consecutivas sin timeouts).
Aceptación visual: capturas 390px y 1440px de las 7 pantallas.

## Evidencia (commits)

- U1: pendiente
- U2: pendiente
- U3: pendiente
- U4: pendiente
- U5: pendiente
- U6: pendiente

## Notas de alcance

- Backend/API de solo lectura; nada de lógica de dominio.
- Proteger lo que la crítica marcó como bueno: caveat «simula, no predice»,
  visibilidad de capital/meta/duración, validación y borradores del wizard.
- Los cambios NO deben reintroducir el mundo visual descartado (oscuro Pi,
  Georgia, radio 0): el tema oscuro pedido es el esquema M3 oscuro ya tokenizado.
