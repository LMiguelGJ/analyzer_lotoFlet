# Calibración prospectiva de cobertura E5 en controles sanos

Piloto separado: 20 corrientes SHA-256 independientes sobre el calendario original; selección entre 12 políticas E5 solo en el 60% inicial, evaluación en el 40% final. IC bootstrap 95% por días con 2.000 remuestreos por corriente y semilla fija 7. La cobertura incluye ambos límites del intervalo.

**Control sano E5 original: criterio INCUMPLIDO.** Política par/impar tras ≥3; IC 95% [0.823736, 0.848713] excluye 0,85. Este piloto no reemplaza ese fallo ni demuestra rentabilidad de estrategia alguna.

| Semilla | Política elegida | Retorno entrenamiento | Retorno prueba | IC 95% prueba | Contiene 0,85 |
|---|---|---:|---:|---:|---|
| E5-healthy-cal-v1-001 | par/impar tras ≥4 | 0.860595 | 0.843731 | [0.823694, 0.866348] | sí |
| E5-healthy-cal-v1-002 | bajo/alto tras ≥4 | 0.847183 | 0.846096 | [0.827510, 0.865601] | sí |
| E5-healthy-cal-v1-003 | par/impar tras ≥8 | 0.897959 | 0.895725 | [0.813645, 0.994188] | sí |
| E5-healthy-cal-v1-004 | par/impar tras ≥8 | 0.878427 | 0.805963 | [0.743229, 0.882185] | sí |
| E5-healthy-cal-v1-005 | par/impar tras ≥8 | 0.876941 | 0.873233 | [0.805618, 0.945519] | sí |
| E5-healthy-cal-v1-006 | bajo/alto tras ≥6 | 0.872236 | 0.858890 | [0.820512, 0.898337] | sí |
| E5-healthy-cal-v1-007 | par/impar tras ≥8 | 0.865817 | 0.889188 | [0.823697, 0.963078] | sí |
| E5-healthy-cal-v1-008 | bajo/alto tras ≥6 | 0.873501 | 0.861042 | [0.819391, 0.907174] | sí |
| E5-healthy-cal-v1-009 | bajo/alto tras ≥8 | 0.855890 | 0.804593 | [0.729035, 0.895260] | sí |
| E5-healthy-cal-v1-010 | par/impar tras ≥8 | 0.865579 | 0.871655 | [0.796269, 0.960214] | sí |
| E5-healthy-cal-v1-011 | bajo/alto tras ≥4 | 0.849630 | 0.856753 | [0.839699, 0.874457] | sí |
| E5-healthy-cal-v1-012 | bajo/alto tras ≥6 | 0.857060 | 0.837755 | [0.806749, 0.873209] | sí |
| E5-healthy-cal-v1-013 | par/impar tras ≥7 | 0.883646 | 0.817409 | [0.769025, 0.866530] | sí |
| E5-healthy-cal-v1-014 | bajo/alto tras ≥8 | 0.892707 | 0.790128 | [0.723090, 0.860618] | sí |
| E5-healthy-cal-v1-015 | par/impar tras ≥8 | 0.886098 | 0.805714 | [0.725179, 0.900579] | sí |
| E5-healthy-cal-v1-016 | par/impar tras ≥8 | 0.870424 | 0.827419 | [0.763976, 0.902422] | sí |
| E5-healthy-cal-v1-017 | par/impar tras ≥7 | 0.872900 | 0.909663 | [0.854936, 0.969629] | no |
| E5-healthy-cal-v1-018 | bajo/alto tras ≥8 | 0.895429 | 0.838152 | [0.769561, 0.921472] | sí |
| E5-healthy-cal-v1-019 | bajo/alto tras ≥8 | 0.869371 | 0.853477 | [0.781194, 0.936012] | sí |
| E5-healthy-cal-v1-020 | par/impar tras ≥8 | 0.885103 | 0.832807 | [0.767409, 0.911922] | sí |

**Criterio separado: PASA** — 19/20 intervalos contienen 0,85 (umbral ≥18/20).
Piloto de precisión limitada: no aprueba retroactivamente E5 original ni garantiza cobertura universal; retorno esperado 0,85 no es rentabilidad (>1).
Tiempo de ejecución: 10.52 s.
