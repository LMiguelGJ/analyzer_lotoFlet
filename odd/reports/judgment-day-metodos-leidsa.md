# Judgment Day: métodos de laboratorio para Leidsa

Fecha: 2026-11-25. Objetivo: commit `cf7b1b6` (árbol limpio), archivos
`engine/causal_rankings.py`, `engine/stake_styles.py`, `engine/reference_labs.py`,
`domain/laboratories.py`. Dos jueces ciegos (A y B), sin refutadores.

**Resultado: JUDGMENT: APPROVED.** Ningún hallazgo BLOCKER ni CRITICAL; 0 rondas de corrección.
Verificación final: 183 tests pasan (`test_causal_rankings`, `test_leidsa_new_systems`,
`test_stake_styles`, `test_max_stake`, `test_reference_parity`).

## Hallazgos informativos (WARNING / SUGGESTION), agrupados

| Tema | IDs | Qué pasa | Mejora propuesta |
|---|---|---|---|
| Sin ventaja sobre el azar | A-001, B-005 | Los 8 sistemas devuelven 0,70–0,78 por peso (teórico 0,72); el acierto del 1.º es c/100 | Ninguna configuración crea ventaja; mostrarlo en la app |
| Parámetros fijos de Chance | A-002, B-005 | Ventanas/half-life de 500 vienen de Chance (≈2,7 días allí, ≈16 meses en Leidsa) y no se pueden cambiar | Hacer configurables ventana y half-life por laboratorio |
| Solo se mira el 1.er lugar | A-002 | `scope=position` ignora 2.º y 3.º, que aportan 12/72 del valor | Opción de contar las 3 posiciones |
| Selección congelada | A-004, B-006 | freq_hist juega el 36/28 desde 2012; decay 500 casi fijo | Ventana obligatoria o más corta en freq_hist |
| Empates por orden fijo | A-005 | 82 % de empates en el puesto 10 con freq_recent; los decide `TIE` | Desempate por otro criterio o aleatorio con semilla |
| Escalera defectuosa | A-007, B-001, B-002, B-003 | Objetivo fijo +10, se reinicia tras 10 fallos perdiendo lo invertido, cuenta "quiebra" con saldo de sobra (541 de 701), con tope sigue avanzando | Escalera ligada a la meta, sin reinicio silencioso, apuesta acotada al saldo |
| Progresiones con premios parciales | A-006, B-004 | Un 2.º o 3.er premio cuenta como "ganar" y reinicia sin recuperar | Reiniciar solo cuando se recupera lo perdido en el ciclo |
| Validación incompleta | B-009 | Martingala/Paroli/D'Alembert/Fibonacci aceptan prizes[0] ≤ cobertura (solo pueden quebrar) | Exigir prizes[0] > cobertura a todas |
| Ensamble sin señal | A-003, A-008, B-007, B-008 | Mezcla votos opuestos y duplicados (cold–overdue 0,96); ignora parámetros | Quitar componentes redundantes o pesos; pasar parámetros |
| Sin calentamiento | A-009 | La ventana arranca en el primer sorteo con rankings vacíos | Empezar la ventana por defecto después de N sorteos |
| Sin desglose anual | B-010 | Los totales no se reparten por año | Mostrar resultado por año en la app |

## Variaciones de parámetros (mismo día)

1.104 combinaciones 2019–2026 (simulador validado contra la app: +1.737 en 2026, +4.248 en 2019–2026).
Única con los 8 años > +10 %: **Decaimiento half-life 300 · 1 número · Audaz · 10.000 → 10.500**
(+16 a +31 % por año, 0 quiebras, 10.000 → 26.959). Pasa la prueba 2019–2022 → 2023–2026 y 50
arranques distintos, pero sus vecinos (100, 200, 500) quiebran 3–4 veces, falla en 2010–2018 y no se
separa del azar. Resumen completo en `.tmp/leidsa-busquedas/variaciones/resumen.md`.
