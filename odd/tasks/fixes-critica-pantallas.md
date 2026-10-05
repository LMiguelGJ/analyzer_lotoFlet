# Feature: Fixes de la crítica de pantallas (2026-10-05)

Fuente: snapshot `.impeccable/critique/2026-10-05T15-20-36Z__webapp-frontend-src.md`
(22/40 Nielsen, dual-agent). Decisiones del usuario (2026-10-05):
- Corregir TODO (los 5 issues de la crítica, en una tanda).
- Tema OSCURO por defecto (cambia DESIGN.md: era claro por defecto).
- Fuera de alcance (no seleccionado): pulido menor (foco visible, aria de
  colección, nombres internos menores) — queda como seguimiento.

## Tasks

- [x] U1. Acciones únicas por pantalla (P1-1, /impeccable distill): suprimir el
  FAB donde la página define su propia acción primaria; un solo affordance por
  destino (nombre+botón de resultado → uno); un solo «Limpiar filtros».
  Superficies: webapp/frontend/src/components/Shell.tsx,
  webapp/frontend/src/pages/experiments/index.tsx, tests colocados.
- [x] U2. Layout de escritorio (P1-2, /impeccable layout): tabla sin scroll
  horizontal espurio, rail con labels legibles, contenido que aproveche el
  ancho. Superficies: webapp/frontend/src/styles/**,
  webapp/frontend/src/components/Shell.tsx, tests colocados.
- [x] U3. Tema oscuro por defecto: inversión del default (toggle conserva
  claro), tokens verificados en oscuro, DESIGN.md actualizado.
  Superficies: webapp/frontend/src/components/Shell.tsx,
  webapp/frontend/src/styles/**, tests colocados + DESIGN.md.
- [x] U4. Solapamientos móviles (P2-4, /impeccable harden): FAB/Nav no tapan
  input de archivo (Datos), gráfico (Detalle), disclosure (Comparación), campos
  (Ajustes); verificar ≤320px y zoom. Superficies: webapp/frontend/src/styles/**,
  webapp/frontend/src/components/Shell.tsx.
- [x] U5. Claridad del wizard + conclusión financiera primero (P1-3 + P2-5,
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
- [x] U6. QA del ciclo (build + capturas + suite final + verificación DOM): suite completa x3, typecheck, build, capturas móviles y
  escritorio de las 7 pantallas para verificación visual, commit final.

## Verification (por unidad)

Desde webapp/frontend: tests focales + typecheck; al cierre de cada unidad la
suite completa en verde (criterio: corridas consecutivas sin timeouts).
Aceptación visual: capturas 390px y 1440px de las 7 pantallas.

## [x] U7. Fixes de la verificación visual (hallados en las capturas de U6) — CERRADO

1. [P1] Listado móvil: el FAB tapa el botón de la card («Abrir resultado» a
   medias detrás del FAB) — reservar zona segura en el listado también.
2. [P2] Fila de escritorio: queda un link «Acciones» suelto debajo de «Abrir
   resultado» (affordance duplicado sobrante) — eliminarlo; una sola acción.
3. [P2] Card móvil del listado muestra el nombre interno `todo_o_nada` en los
   metadatos — moverlo detrás de detalles / usar etiqueta neutra.
4. [P3] El pill activo del rail tapa su propio icono (escritorio, listado y
   Ajustes) — arreglar el layout del ítem del rail.
5. [P3] Detalle: repetición de «5000 sorteos» (conclusión + Sorteos jugados +
   Duración), frase confusa («El saldo final no es lo mismo que la ganancia…») y
   título del app bar truncado («Resultado de la simula…») — simplificar y
   ajustar el título.
6. [P3] Datos: heading «Crear perfil de juego» + botón con el mismo texto;
   etiquetas de importación poco distintas — diferenciarlos.

## Evidencia (commits)

- U1+U2+U3+U4: 272793a (7 archivos, una unidad compartida por Shell/styles) ·
  revisión nativa review-0600b5a6f490a079 aprobada y quemada; suite 564/564 x2;
  hallazgo informativo R3-table-layout-coverage (styles/index.css:292-293)
- U5: 2d068d9 (8 archivos) · revisión nativa review-5f84e7affceacb3b
  aprobada y quemada; suite 566/566 x2; hallazgo informativo R3-ruin-balance
  (experiments/DetailPage.tsx:49)
- U6: suite 566/566, build ok, capturas de las 7 pantallas (móvil+escritorio);
  verificación visual realizada — orígenes de U7
- U7: 01f529b (11 archivos) · revisión nativa review-babc5b6d17d72695
  aprobada y quemada (hallazgo informativo R3-keyboard-result-access,
  experiments/index.tsx:122); suite 567/567 x2
- U7b (micro-fix): ff54f43 (6 archivos) · revisión nativa
  review-6a418678cd886f8f aprobada y quemada (hallazgo informativo
  R3-duration-proof, DetailPage.test.tsx:439-440); suite 567/567

## Cierre del ciclo (2026-10-05)

Los 5 issues de la crítica + los 6 defectos de la verificación visual + 3 nits
finales fueron corregidos, verificados por DOM/capturas y revisados nativamente.
Commits: 272793a (U1-U4), 2d068d9 (U5), 01f529b (U7), ff54f43 (U7b).
Revisiones quemadas: review-0600b5a6f490a079, review-5f84e7affceacb3b,
review-babc5b6d17d72695, review-6a418678cd886f8f. Tema oscuro por defecto
(design decision del usuario). Suite 567/567; build ok (chunk >500 kB, no
fatal). Pendiente de aceptación manual: probar en dispositivo real y zoom.

## Notas de alcance

- Backend/API de solo lectura; nada de lógica de dominio.
- Proteger lo que la crítica marcó como bueno: caveat «simula, no predice»,
  visibilidad de capital/meta/duración, validación y borradores del wizard.
- Los cambios NO deben reintroducir el mundo visual descartado (oscuro Pi,
  Georgia, radio 0): el tema oscuro pedido es el esquema M3 oscuro ya tokenizado.
