# Aplicar el diseño BossFarmer

Plan aprobado: `.pi/plans/aplicar-diseno-bossfarmer.md`. Rama `feat/bossfarmer-design` desde `stage`.
Autorizado por el usuario: ejecutar el plan tal cual con ODD; instalar `@fontsource/archivo` y
`@fontsource/archivo-narrow` (instalados, solo subconjunto latin, sin otras dependencias).
Fuera de alcance: backend, contratos, push, PR y merge (decisión del usuario).

## Tareas

- [x] T1 — Fundación: tokens `--bf-*`, fuentes locales, Tailwind sin radios/sombras, tema único. Commit `b475da3`.
- [x] T2 — Navegación y estructura (Shell). Commit en rama; ver evidencia.
- [x] T3 — Componentes base y estados.
- [x] T4 — Asistente de cinco pasos (+ navegación directa entre pasos). Commits 1b81d62, 143bb89, c701eb6, df24205.
- [ ] T5 — Resultados, gráficos y ledger.
- [ ] T6 — Pantallas (+ advertencia de Comparación y neto móvil).
- [ ] T7 — Limpieza y cierre.

## Evidencia

T1: typecheck PASS, build PASS (aviso chunk 631,48 kB), `tokens.test.ts` migrado 3/3 PASS, navegador sintético 390/1440 PASS (fondo rgb(23,25,26), fuentes locales, radio 0, sin sombras, 0 peticiones externas, sin overflow). Foco de campos y opacidad disabled 0,6 corregidos.

Hallazgo: suite completa de frontend = 73 fallos previos a T1 (`tokens.test.ts` 4, ya corregidos; resto: NewExperimentPage 32, ProfileExperimentPage 19, ProfileBatchPage 16, DetailPage 2). Son tests escritos para el layout previo al asistente de cinco pasos; CSS no influye en jsdom. La entrega anterior no había ejecutado la suite completa. Se reparan en T4 (asistente) y T6 (DetailPage) actualizando expectativas a la navegación nueva, sin debilitar contratos.

T2: verificador independiente en navegador 390/1440 PASS (rail inferior 4 celdas, acción primaria rectangular, radio 0/sin sombras, sin iconos, foco 2px, drawer con retorno de foco, 0 peticiones externas); suite 710 pass / 69 fallos previos idénticos al baseline (ninguno fuera). Hallazgos corregidos: orden de tab alineado con el visual; contador `pending.total` en la cola. No ejercitados: límite exacto 900 px y contador con trabajo activo en navegador.

T3: verificador independiente (typecheck/build PASS; suite 710/69 idéntica al baseline; navegador 390/1440 con datos sintéticos: radio 0, sin sombras ni gradientes, 48px, foco, 0 peticiones externas). Defectos corregidos: borde verde en `.ledger-chip-success`, scrim con chassis al 80%, variante `.btn-on-signal`, cursor `wait` en busy. Tras la corrección solo se re-ejecutaron tests focalizados (39), typecheck, build y grep de `--bf-signal` (solo fondos); no hubo segunda verificación de navegador. Variantes switch/segmentado/on-signal verificadas por sondas CSS, no integración React.

T4: asistente con marco de cinco celdas, salto directo a pasos alcanzados (`onSelectStep`/`maxReachableStep`), acciones después del contenido (grupo «Navegación del asistente», sticky en móvil) y Revisión en filas término/valor. Se repararon 67 tests obsoletos (NewExperimentPage 58, ProfileExperimentPage 39, ProfileBatchPage 29) sin reducir el número de casos (49/15/17 `it` igual que 8b413c5). Contratos reemplazados explícitamente: enlace «¿Necesitás algo más?» → selector «Tipo de simulación» (solo visible en Alcance); «Avanzado» de Estrategia abierto por diseño; edición durante recuperación pendiente bloqueada (F-CREATE-048, con las aserciones de recuperación intactas). Falso positivo descartado: F-CREATE-052 era «accepts… after an unrelated condition edit», no una regresión. Verificación final: suite 781/783 (solo DetailPage 692 y 728, alcance T6), typecheck y build PASS, navegador 390/1440 PASS, 0 peticiones externas. Límite: API sintética, sin dispositivo físico; fondo/borde de las acciones solo en móvil.

Cada cierre registra comandos y resultados observados, commit y límites.
