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
- [x] T5 — Resultados, gráficos y ledger. Commits f2d2c93, cdeddf5, a4c3803.
- [x] T6 — Pantallas (+ advertencia de Comparación y neto móvil). Commits 040f7b6, 95ec752, 6abdc5b.
- [x] T7 — Limpieza y cierre. Implementación `3a5a7d7`; corrección de accesibilidad y pruebas `ac987be`. Verificación independiente final completada.

## Evidencia

T1: typecheck PASS, build PASS (aviso chunk 631,48 kB), `tokens.test.ts` migrado 3/3 PASS, navegador sintético 390/1440 PASS (fondo rgb(23,25,26), fuentes locales, radio 0, sin sombras, 0 peticiones externas, sin overflow). Foco de campos y opacidad disabled 0,6 corregidos.

Hallazgo: suite completa de frontend = 73 fallos previos a T1 (`tokens.test.ts` 4, ya corregidos; resto: NewExperimentPage 32, ProfileExperimentPage 19, ProfileBatchPage 16, DetailPage 2). Son tests escritos para el layout previo al asistente de cinco pasos; CSS no influye en jsdom. La entrega anterior no había ejecutado la suite completa. Se reparan en T4 (asistente) y T6 (DetailPage) actualizando expectativas a la navegación nueva, sin debilitar contratos.

T2: verificador independiente en navegador 390/1440 PASS (rail inferior 4 celdas, acción primaria rectangular, radio 0/sin sombras, sin iconos, foco 2px, drawer con retorno de foco, 0 peticiones externas); suite 710 pass / 69 fallos previos idénticos al baseline (ninguno fuera). Hallazgos corregidos: orden de tab alineado con el visual; contador `pending.total` en la cola. No ejercitados: límite exacto 900 px y contador con trabajo activo en navegador.

T3: verificador independiente (typecheck/build PASS; suite 710/69 idéntica al baseline; navegador 390/1440 con datos sintéticos: radio 0, sin sombras ni gradientes, 48px, foco, 0 peticiones externas). Defectos corregidos: borde verde en `.ledger-chip-success`, scrim con chassis al 80%, variante `.btn-on-signal`, cursor `wait` en busy. Tras la corrección solo se re-ejecutaron tests focalizados (39), typecheck, build y grep de `--bf-signal` (solo fondos); no hubo segunda verificación de navegador. Variantes switch/segmentado/on-signal verificadas por sondas CSS, no integración React.

T4: asistente con marco de cinco celdas, salto directo a pasos alcanzados (`onSelectStep`/`maxReachableStep`), acciones después del contenido (grupo «Navegación del asistente», sticky en móvil) y Revisión en filas término/valor. Se repararon 67 tests obsoletos (NewExperimentPage 58, ProfileExperimentPage 39, ProfileBatchPage 29) sin reducir el número de casos (49/15/17 `it` igual que 8b413c5). Contratos reemplazados explícitamente: enlace «¿Necesitás algo más?» → selector «Tipo de simulación» (solo visible en Alcance); «Avanzado» de Estrategia abierto por diseño; edición durante recuperación pendiente bloqueada (F-CREATE-048, con las aserciones de recuperación intactas). Falso positivo descartado: F-CREATE-052 era «accepts… after an unrelated condition edit», no una regresión. Verificación final: suite 781/783 (solo DetailPage 692 y 728, alcance T6), typecheck y build PASS, navegador 390/1440 PASS, 0 peticiones externas. Límite: API sintética, sin dispositivo físico; fondo/borde de las acciones solo en móvil.

T5: placa de resultado (sello, numeral 38,4/54,4 px, filas término/valor, aviso fijo), gráficos neutros (legend/legend-dim, rejilla rule, trazo y marcador distinguen series), ledger en placas. Defectos reales hallados por el navegador y corregidos: quiebra (lote y perfil) con cabecera de éxito; saldo final sin jerarquía de numeral; proveniencia incompleta; aviso histórico con tinta incorrecta; y en lotes, hash de 64 caracteres y código crudo `insufficient_capital` visibles. Decisión de producto registrada en DESIGN.md: la proveniencia visible es en lenguaje cotidiano (versión y fuente); huella, archivo, JSON y semilla quedan plegados en «Cómo se hizo» (pestaña Parámetros y datos). Cambio de expectativa deliberado: un test de DetailPage que exigía ver `history.json` ahora exige que no se vea. Suite completa 788/788 (incluye los 2 casos de DetailPage antes fallidos), typecheck y build PASS; navegador 390/1440 PASS, 0 peticiones externas. Límites: API sintética; solo dos anchos, no el umbral exacto de 640 px; RunTrajectory/ComparisonChart se evaluaron por pruebas y estáticamente.

T6: Experimentos/Comparación (placas; advertencia «no constituyen validación independiente de rentabilidad» y «Cambio neto» móvil recuperados), Estrategias, Datos (selector de importación segmentado único), Ajustes y chrome del creador histórico. Hallazgos corregidos: prueba de CSS demasiado amplia, selector de importación incompleto, tipografía de etiquetas, doble h1 en Comparación, tinta de la barra de progreso. Suite 789/789, typecheck y build PASS; navegador 390/1440 PASS en 6 rutas, 0 errores de consola, 0 peticiones externas. Límites: API sintética; creador histórico solo primer paso en navegador; sin importación real.

T7 completed: Material compatibility aliases and `m3-*` runtime names retired in `3a5a7d7`; variable references resolve and no new skipped tests were added. The initial independent suite timed out at 120 seconds, then passed 790/790 on its exact retry. Integrity review exposed missing non-text contrast and DataTable hover/tracking guards. Required control borders measured only 1.47:1; the user approved using existing `legend-dim` for necessary boundaries while preserving decorative `rule` hairlines and the palette. Correction `ac987be` includes the documented exception and restored regression coverage. Observed RED on the original border, then GREEN 14/14 focused tests. Corrected contrast: 7.13:1 against the field, 6.59:1 against chassis; active chassis/signal boundary 6.82:1.

Final independent checks after the correction: focused tests 14/14; full suite 792/792 across 50 files in 157.14 seconds; typecheck and build PASS, all exit 0. Backend diff against `17bb8ab` remains empty. Fresh browser harness exited 0: 14 result checks with no failures plus 28 screen samples at 390/1440, no external requests. Real built-CSS probes with reduced motion enabled verified enabled, checked, focused, disabled and invalid control boundaries. Owned strict-port 5187 preview and probe browsers were cleaned up; port 5173 was untouched.

Limits and follow-ups: two console 404s originate from the missing synthetic `/api/v1/execution-policy` fixture, so batch-creator and complete creator submission journeys remain partially verified. Reduced motion was enabled for boundary probes, not a complete motion/gesture acceptance suite. The pre-existing generic text-input selector outranks the invalid `.control` selector, leaving its invalid border at `rule` rather than `alerta`; not introduced by this correction and retained as follow-up, not reported as fixed. The JavaScript chunk remains above 500 kB. Earlier verifier process failures produced no application verdict; their successful command evidence was recovered without rerunning. No push, PR, merge or deployment performed. Unrelated deleted docs and untracked `odd/qa/` preserved.

Cada cierre registra comandos y resultados observados, commit y límites.
