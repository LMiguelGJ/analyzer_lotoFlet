# Quiniela Extraordinaria 80 sobre Chance Express: simulación contrafactual

**No son sorteos observados de Rapidita ni validación de sus reglas.** Pagos hipotéticos RD$80/8/4/2/1 por peso y número en posiciones 1.ª–5.ª. All suma coincidencias repetidas (principal); best paga solo la mejor (sensibilidad no confirmada por reglas oficiales). No palé ni tripleta.

Fuente `chance_express_history.json` SHA-256 `d1c0e9ec047dfa6ae61f870ef3d1b2ad21917dbd97aa3ca80d9f776d2b8f9711`; 105,426 sorteos, 566 días. Corte 60/40: hasta 2026-02-09 entrenamiento (339 días, 63,246 sorteos), desde 2026-02-10 prueba ciega (227 días, 42,180 sorteos). Bootstrap por día 2.000 repeticiones, semilla 7. E6: 20.000 sesiones MC por combinación, sesiones reales consecutivas no solapadas.

## Conclusiones y supuestos

- Prioridad: retorno de solo primera posición vs **0,80**; total quiniela all vs **0,95** y best vs **0,9474159401**. Son referencias de azar uniforme independiente; beneficio exige **retorno >1** con incertidumbre, no solo superar azar. Un retorno histórico >1 no garantiza ventaja futura.
- E2–E5: se elige candidato por retorno al 1.º solo en entrenamiento; el mismo candidato y las mismas apuestas se evalúan en las tres vistas de prueba ciega. La elección alternativa por total all es sensibilidad.
- p crudos de E1–E5 y E8 no dependen del premio; E6 sí cambia por pagos/objetivo y modo. Holm se recalcula sobre la familia completa, incluidas E6 all/best; sus p ajustados pueden variar aunque el p crudo de otras pruebas sea idéntico. α=0,01; N/A se conserva.

## Ocho ideas: pruebas de probabilidad

| Idea | Pregunta | Chance Express | Sano | Trampa |
|---|---|---|---|---|
| #1 Mitades tras racha | ¿Después de N iguales (par/impar, bajo/alto) sale más la otra mitad? | ✅ 0/40 pruebas válidas fallan | ✅ 0/40 pruebas válidas fallan | ❌ 3/40 pruebas válidas fallan, 2 sospechosas |
| #2 Números fríos | ¿Un número que lleva X sorteos sin salir 1º sale más? | ⚠️ 0/9 pruebas válidas fallan, 3 N/A | ⚠️ 0/9 pruebas válidas fallan, 3 N/A | ❌ 5/9 pruebas válidas fallan, 1 sospechosas, 3 N/A |
| #6 Arrastre | ¿Un número del sorteo anterior sube al 1º? | ✅ 0/6 pruebas válidas fallan | ✅ 0/6 pruebas válidas fallan | ❌ 6/6 pruebas válidas fallan |
| #12 Dobles | ¿Un número que salió doble vuelve pronto? | ✅ 0/6 pruebas válidas fallan | ✅ 0/6 pruebas válidas fallan | ❌ 6/6 pruebas válidas fallan |
| #21 Entrar tras N fallos | ¿Esperar N iguales y cubrir la otra mitad paga más? | ✅ 0/12 pruebas válidas fallan | ✅ 0/12 pruebas válidas fallan | ❌ 4/12 pruebas válidas fallan |
| #26 Audaz vs tímida | ¿Cómo se comparan sesiones reales no solapadas con MC uniforme del mismo pago/modo? | ✅ 0/8 pruebas válidas fallan | ✅ 0/8 pruebas válidas fallan | ✅ 0/8 pruebas válidas fallan |
| #29 Cambio de fuente | ¿premios.do y loteka.com.do se comportan igual? | ⚠️ 0/221 pruebas válidas fallan, 3 sospechosas, 17 N/A | ⚠️ 0/221 pruebas válidas fallan, 1 sospechosas, 17 N/A | ❌ 34/221 pruebas válidas fallan, 9 sospechosas, 17 N/A |
| #27 E7 Repetidos | retornos all / best; teórico 0.9500 / 0.9474 | 0.9500 / 0.9474 | 0.9500 / 0.9475 | 0.9500 / 0.9474 |

**Resultado económico principal en prueba ciega:** E2: 1.º 0.5839, all 0.7080, neto all RD$-40; E3: 1.º 0.8314, all 0.9755, neto all RD$-1,027; E4: 1.º 0.8020, all 0.9464, neto all RD$-4,148; E5: 1.º 0.7890, all 0.9418, neto all RD$-7,384. 4/4 selecciones planas pierden dinero en all; el IC de una muestra escasa puede ser especialmente inestable.

### Grilla E1 y E5: todos los N y variantes

| Prueba | Casos | Observado | Esperado | p | p Holm |
|---|---:|---:|---:|---:|---:|
| E1 par-g1 N=1 | 52,928 | 50.28% | 50.00% | 0.1997 | 1.0000 |
| E1 par-g1 N=2 | 26,180 | 49.80% | 50.00% | 0.5164 | 1.0000 |
| E1 par-g1 N=3 | 13,071 | 50.65% | 50.00% | 0.1370 | 1.0000 |
| E1 par-g1 N=4 | 6,418 | 50.56% | 50.00% | 0.3755 | 1.0000 |
| E1 par-g1 N=5 | 3,157 | 50.71% | 50.00% | 0.4336 | 1.0000 |
| E1 par-g1 N=6 | 1,551 | 49.97% | 50.00% | 1.0000 | 1.0000 |
| E1 par-g1 N=7 | 770 | 48.31% | 50.00% | 0.3676 | 1.0000 |
| E1 par-g1 N=8 | 397 | 48.11% | 50.00% | 0.4823 | 1.0000 |
| E1 par-g1 N=9 | 206 | 52.43% | 50.00% | 0.5307 | 1.0000 |
| E1 par-g1 N=10 | 96 | 46.88% | 50.00% | 0.6101 | 1.0000 |
| E1 par-5g N=1 | 263,766 | 49.96% | 50.00% | 0.6869 | 1.0000 |
| E1 par-5g N=2 | 131,288 | 50.08% | 50.00% | 0.5753 | 1.0000 |
| E1 par-5g N=3 | 65,201 | 50.14% | 50.00% | 0.4712 | 1.0000 |
| E1 par-5g N=4 | 32,336 | 50.23% | 50.00% | 0.4137 | 1.0000 |
| E1 par-5g N=5 | 16,017 | 50.46% | 50.00% | 0.2487 | 1.0000 |
| E1 par-5g N=6 | 7,896 | 50.23% | 50.00% | 0.6937 | 1.0000 |
| E1 par-5g N=7 | 3,904 | 49.41% | 50.00% | 0.4714 | 1.0000 |
| E1 par-5g N=8 | 1,966 | 49.34% | 50.00% | 0.5729 | 1.0000 |
| E1 par-5g N=9 | 990 | 50.91% | 50.00% | 0.5890 | 1.0000 |
| E1 par-5g N=10 | 482 | 50.00% | 50.00% | 1.0000 | 1.0000 |
| E1 alto-g1 N=1 | 52,704 | 49.77% | 50.00% | 0.3019 | 1.0000 |
| E1 alto-g1 N=2 | 26,327 | 50.25% | 50.00% | 0.4230 | 1.0000 |
| E1 alto-g1 N=3 | 13,015 | 50.46% | 50.00% | 0.3010 | 1.0000 |
| E1 alto-g1 N=4 | 6,418 | 50.02% | 50.00% | 0.9900 | 1.0000 |
| E1 alto-g1 N=5 | 3,188 | 50.50% | 50.00% | 0.5830 | 1.0000 |
| E1 alto-g1 N=6 | 1,569 | 49.14% | 50.00% | 0.5116 | 1.0000 |
| E1 alto-g1 N=7 | 795 | 48.43% | 50.00% | 0.3947 | 1.0000 |
| E1 alto-g1 N=8 | 405 | 43.70% | 50.00% | 0.0129 | 1.0000 |
| E1 alto-g1 N=9 | 225 | 52.44% | 50.00% | 0.5051 | 1.0000 |
| E1 alto-g1 N=10 | 106 | 48.11% | 50.00% | 0.7709 | 1.0000 |
| E1 alto-5g N=1 | 263,586 | 49.97% | 50.00% | 0.7274 | 1.0000 |
| E1 alto-5g N=2 | 131,198 | 50.20% | 50.00% | 0.1519 | 1.0000 |
| E1 alto-5g N=3 | 64,988 | 49.89% | 50.00% | 0.5695 | 1.0000 |
| E1 alto-5g N=4 | 32,408 | 50.06% | 50.00% | 0.8458 | 1.0000 |
| E1 alto-5g N=5 | 16,090 | 49.80% | 50.00% | 0.6194 | 1.0000 |
| E1 alto-5g N=6 | 8,041 | 49.96% | 50.00% | 0.9467 | 1.0000 |
| E1 alto-5g N=7 | 4,003 | 50.44% | 50.00% | 0.5910 | 1.0000 |
| E1 alto-5g N=8 | 1,976 | 48.48% | 50.00% | 0.1844 | 1.0000 |
| E1 alto-5g N=9 | 1,011 | 50.45% | 50.00% | 0.8014 | 1.0000 |
| E1 alto-5g N=10 | 495 | 47.68% | 50.00% | 0.3228 | 1.0000 |
| E5 par/impar N≥3 | 25,752 | 50.51% | 50.00% | 0.1012 | 1.0000 |
| E5 par/impar N≥4 | 12,681 | 50.37% | 50.00% | 0.4139 | 1.0000 |
| E5 par/impar N≥5 | 6,263 | 50.17% | 50.00% | 0.8005 | 1.0000 |
| E5 par/impar N≥6 | 3,106 | 49.61% | 50.00% | 0.6798 | 1.0000 |
| E5 par/impar N≥7 | 1,555 | 49.26% | 50.00% | 0.5769 | 1.0000 |
| E5 par/impar N≥8 | 785 | 50.19% | 50.00% | 0.9431 | 1.0000 |
| E5 bajo/alto N≥3 | 25,829 | 50.11% | 50.00% | 0.7275 | 1.0000 |
| E5 bajo/alto N≥4 | 12,814 | 49.76% | 50.00% | 0.5900 | 1.0000 |
| E5 bajo/alto N≥5 | 6,396 | 49.50% | 50.00% | 0.4308 | 1.0000 |
| E5 bajo/alto N≥6 | 3,208 | 48.50% | 50.00% | 0.0935 | 1.0000 |
| E5 bajo/alto N≥7 | 1,639 | 47.90% | 50.00% | 0.0930 | 1.0000 |
| E5 bajo/alto N≥8 | 844 | 47.39% | 50.00% | 0.1388 | 1.0000 |

## Retornos y apuestas — Chance Express

Cada celda: retorno [IC 95%]; RD$ apostado / cobrado / neto; aciertos crudos al 1.º; sorteos con apuesta; unidades-número apostadas; capital mínimo; caída máxima. Los aciertos crudos NO son tasas ponderadas por stake. Una apuesta a 50 números tiene cobertura 50%, no 1%; referencia de 1% es por número-unidad. El retorno de primera posición tiene referencia 0,80; total all 0,95; best 0,9474159401. Rentabilidad neta requiere retorno >1.

| Selección por retorno 1.º en entrenamiento | Solo 1.º | Total all | Total best |
|---|---|---|---|
| E2 frío en cualquier ≥200 (entrenamiento 1.º 1.3973799126637554) | 0.5839 [0.000–4.140]; RD$137 / 80 / -57; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 137; caída 136 | 0.7080 [0.062–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 | 0.7080 [0.055–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 |
| E3 jugar el 2º anterior (entrenamiento 1.º 0.8240736325051267) | 0.8314 [0.756–0.912]; RD$41,953 / 34,880 / -7,073; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 7,243; caída 7,327 | 0.9755 [0.895–1.053]; RD$41,953 / 40,926 / -1,027; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,617; caída 2,226 | 0.9722 [0.892–1.054]; RD$41,953 / 40,787 / -1,166; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,739; caída 2,308 |
| E4 jugar el doble 20 sorteos (entrenamiento 1.º 0.8403375862754076) | 0.8020 [0.744–0.858]; RD$77,405 / 62,080 / -15,325; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 15,462; caída 15,459 | 0.9464 [0.891–1.001]; RD$77,405 / 73,257 / -4,148; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,665; caída 5,270 | 0.9435 [0.888–0.999]; RD$77,405 / 73,029 / -4,376; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,875; caída 5,427 |
| E5 par/impar tras ≥5 (entrenamiento 1.º 0.8120236178207193) | 0.7890 [0.757–0.823]; RD$126,850 / 100,080 / -26,770; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 26,850; caída 26,830 | 0.9418 [0.908–0.976]; RD$126,850 / 119,466 / -7,384; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,469; caída 7,666 | 0.9387 [0.908–0.972]; RD$126,850 / 119,079 / -7,771; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,856; caída 8,050 |

### Grilla monetaria completa (sin escoger por prueba ciega)

| Idea y candidato | Solo 1.º: prueba ciega | All: prueba ciega | Best: prueba ciega |
|---|---|---|---|
| E2 frío en 1º ≥100 (train 1.º 0.7996170423031974, train total 0.9504910609633854) | 0.8138 [0.804–0.823]; RD$1,545,897 / 1,258,000 / -287,897; 15,725 aciertos 1.º; 42,180 sorteos; 1,545,897 unidades; capital 287,985; caída 288,076 | 0.9640 [0.955–0.974]; RD$1,545,897 / 1,490,278 / -55,619; 15,725 aciertos 1.º; 42,180 sorteos; 1,545,897 unidades; capital 55,963; caída 56,152 | 0.9613 [0.951–0.971]; RD$1,545,897 / 1,486,139 / -59,758; 15,725 aciertos 1.º; 42,180 sorteos; 1,545,897 unidades; capital 60,094; caída 60,279 |
| E2 frío en 1º ≥150 (train 1.º 0.8008394293074211, train total 0.9510124514873656) | 0.8093 [0.795–0.825]; RD$927,362 / 750,560 / -176,802; 9,382 aciertos 1.º; 42,180 sorteos; 927,362 unidades; capital 176,916; caída 176,978 | 0.9586 [0.943–0.974]; RD$927,362 / 888,994 / -38,368; 9,382 aciertos 1.º; 42,180 sorteos; 927,362 unidades; capital 38,570; caída 39,334 | 0.9560 [0.942–0.970]; RD$927,362 / 886,577 / -40,785; 9,382 aciertos 1.º; 42,180 sorteos; 927,362 unidades; capital 40,972; caída 41,722 |
| E2 frío en 1º ≥200 (train 1.º 0.8008249042060003, train total 0.9503658337281884) | 0.8142 [0.796–0.833]; RD$556,835 / 453,360 / -103,475; 5,667 aciertos 1.º; 42,180 sorteos; 556,835 unidades; capital 103,615; caída 103,886 | 0.9629 [0.944–0.984]; RD$556,835 / 536,197 / -20,638; 5,667 aciertos 1.º; 42,180 sorteos; 556,835 unidades; capital 20,799; caída 22,055 | 0.9604 [0.940–0.979]; RD$556,835 / 534,773 / -22,062; 5,667 aciertos 1.º; 42,180 sorteos; 556,835 unidades; capital 22,221; caída 23,425 |
| E2 frío en 1º ≥300 (train 1.º 0.7927638293529292, train total 0.9419237344355991) | 0.8178 [0.784–0.852]; RD$200,543 / 164,000 / -36,543; 2,050 aciertos 1.º; 41,965 sorteos; 200,543 unidades; capital 36,950; caída 37,247 | 0.9654 [0.933–0.999]; RD$200,543 / 193,610 / -6,933; 2,050 aciertos 1.º; 41,965 sorteos; 200,543 unidades; capital 8,055; caída 8,950 | 0.9629 [0.927–0.998]; RD$200,543 / 193,105 / -7,438; 2,050 aciertos 1.º; 41,965 sorteos; 200,543 unidades; capital 8,349; caída 9,229 |
| E2 frío en 1º ≥400 (train 1.º 0.793752619469178, train total 0.9460624566985707) | 0.8385 [0.782–0.897]; RD$71,651 / 60,080 / -11,571; 751 aciertos 1.º; 35,168 sorteos; 71,651 unidades; capital 11,693; caída 12,237 | 0.9904 [0.937–1.049]; RD$71,651 / 70,964 / -687; 751 aciertos 1.º; 35,168 sorteos; 71,651 unidades; capital 1,346; caída 3,062 | 0.9875 [0.933–1.048]; RD$71,651 / 70,754 / -897; 751 aciertos 1.º; 35,168 sorteos; 71,651 unidades; capital 1,470; caída 3,157 |
| E2 frío en 1º ≥500 (train 1.º 0.8000747733433031, train total 0.9553462940461726) | 0.7987 [0.702–0.900]; RD$24,840 / 19,840 / -5,000; 248 aciertos 1.º; 18,697 sorteos; 24,840 unidades; capital 5,000; caída 5,423 | 0.9507 [0.853–1.054]; RD$24,840 / 23,616 / -1,224; 248 aciertos 1.º; 18,697 sorteos; 24,840 unidades; capital 2,156; caída 2,890 | 0.9481 [0.852–1.050]; RD$24,840 / 23,551 / -1,289; 248 aciertos 1.º; 18,697 sorteos; 24,840 unidades; capital 2,185; caída 2,902 |
| E2 frío en cualquier ≥100 (train 1.º 0.8561145935124056, train total 1.011011273446624) | 0.8735 [0.785–0.970]; RD$28,116 / 24,560 / -3,556; 307 aciertos 1.º; 20,760 sorteos; 28,116 unidades; capital 3,864; caída 4,109 | 1.0314 [0.941–1.125]; RD$28,116 / 28,998 / +882; 307 aciertos 1.º; 20,760 sorteos; 28,116 unidades; capital 456; caída 1,494 | 1.0282 [0.941–1.117]; RD$28,116 / 28,910 / +794; 307 aciertos 1.º; 20,760 sorteos; 28,116 unidades; capital 504; caída 1,517 |
| E2 frío en cualquier ≥150 (train 1.º 0.8210742387957578, train total 0.9784468012316113) | 0.9091 [0.561–1.358]; RD$1,848 / 1,680 / -168; 21 aciertos 1.º; 1,833 sorteos; 1,848 unidades; capital 270; caída 443 | 1.1023 [0.733–1.521]; RD$1,848 / 2,037 / +189; 21 aciertos 1.º; 1,833 sorteos; 1,848 unidades; capital 70; caída 287 | 1.1012 [0.744–1.547]; RD$1,848 / 2,035 / +187; 21 aciertos 1.º; 1,833 sorteos; 1,848 unidades; capital 71; caída 288 |
| E2 frío en cualquier ≥200 (train 1.º 1.3973799126637554, train total 1.5458515283842795) | 0.5839 [0.000–4.140]; RD$137 / 80 / -57; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 137; caída 136 | 0.7080 [0.062–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 | 0.7080 [0.055–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 |
| E2 frío en cualquier ≥300 (train 1.º None, train total None) | N/A (sin apuestas) | N/A (sin apuestas) | N/A (sin apuestas) |
| E2 frío en cualquier ≥400 (train 1.º None, train total None) | N/A (sin apuestas) | N/A (sin apuestas) | N/A (sin apuestas) |
| E2 frío en cualquier ≥500 (train 1.º None, train total None) | N/A (sin apuestas) | N/A (sin apuestas) | N/A (sin apuestas) |
| E3 jugar el 1º anterior (train 1.º 0.7655745783458121, train total 0.9164004005913491) | 0.7742 [0.700–0.852]; RD$41,953 / 32,480 / -9,473; 406 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 10,750; caída 11,113 | 0.9173 [0.842–0.992]; RD$41,953 / 38,484 / -3,469; 406 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 5,437; caída 5,927 | 0.9154 [0.838–0.989]; RD$41,953 / 38,404 / -3,549; 406 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 5,493; caída 5,981 |
| E3 jugar el 2º anterior (train 1.º 0.8240736325051267, train total 0.9729600839334255) | 0.8314 [0.756–0.912]; RD$41,953 / 34,880 / -7,073; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 7,243; caída 7,327 | 0.9755 [0.895–1.053]; RD$41,953 / 40,926 / -1,027; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,617; caída 2,226 | 0.9722 [0.892–1.054]; RD$41,953 / 40,787 / -1,166; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,739; caída 2,308 |
| E3 jugar el 3º anterior (train 1.º 0.8126281653869999, train total 0.9625001987060263) | 0.8295 [0.750–0.904]; RD$41,953 / 34,800 / -7,153; 435 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 7,722; caída 7,721 | 0.9712 [0.891–1.049]; RD$41,953 / 40,745 / -1,208; 435 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 2,264; caída 2,263 | 0.9684 [0.891–1.044]; RD$41,953 / 40,626 / -1,327; 435 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 2,371; caída 2,370 |
| E3 jugar el 4º anterior (train 1.º 0.7973675425628308, train total 0.9519926240323017) | 0.7456 [0.680–0.810]; RD$41,953 / 31,280 / -10,673; 391 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 10,673; caída 10,792 | 0.8943 [0.830–0.963]; RD$41,953 / 37,517 / -4,436; 391 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 4,441; caída 4,593 | 0.8917 [0.826–0.958]; RD$41,953 / 37,408 / -4,545; 391 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 4,550; caída 4,698 |
| E3 jugar el 5º anterior (train 1.º 0.7617594226397698, train total 0.9168137091261703) | 0.8123 [0.740–0.890]; RD$41,953 / 34,080 / -7,873; 426 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 7,873; caída 7,873 | 0.9646 [0.895–1.039]; RD$41,953 / 40,466 / -1,487; 426 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,748; caída 2,123 | 0.9621 [0.886–1.036]; RD$41,953 / 40,361 / -1,592; 426 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,805; caída 2,147 |
| E3 jugar los 5 anteriores (train 1.º 0.7928395382021014, train total 0.944691269944221) | 0.8030 [0.767–0.836]; RD$205,634 / 165,120 / -40,514; 2,064 aciertos 1.º; 41,953 sorteos; 205,634 unidades; capital 40,884; caída 40,879 | 0.9490 [0.914–0.985]; RD$205,634 / 195,153 / -10,481; 2,064 aciertos 1.º; 41,953 sorteos; 205,634 unidades; capital 12,105; caída 12,161 | 0.9463 [0.911–0.982]; RD$205,634 / 194,601 / -11,033; 2,064 aciertos 1.º; 41,953 sorteos; 205,634 unidades; capital 12,583; caída 12,635 |
| E4 jugar el doble 1 sorteos (train 1.º 0.7718724448078496, train total 0.9224856909239575) | 0.5869 [0.397–0.805]; RD$4,089 / 2,400 / -1,689; 30 aciertos 1.º; 4,021 sorteos; 4,089 unidades; capital 1,700; caída 1,768 | 0.7271 [0.537–0.938]; RD$4,089 / 2,973 / -1,116; 30 aciertos 1.º; 4,021 sorteos; 4,089 unidades; capital 1,128; caída 1,262 | 0.7271 [0.532–0.943]; RD$4,089 / 2,973 / -1,116; 30 aciertos 1.º; 4,021 sorteos; 4,089 unidades; capital 1,128; caída 1,262 |
| E4 jugar el doble 5 sorteos (train 1.º 0.8045254556882464, train total 0.9507095835125211) | 0.7883 [0.685–0.897]; RD$20,196 / 15,920 / -4,276; 199 aciertos 1.º; 16,437 sorteos; 20,196 unidades; capital 4,355; caída 4,354 | 0.9325 [0.828–1.045]; RD$20,196 / 18,832 / -1,364; 199 aciertos 1.º; 16,437 sorteos; 20,196 unidades; capital 1,530; caída 1,597 | 0.9307 [0.821–1.042]; RD$20,196 / 18,796 / -1,400; 199 aciertos 1.º; 16,437 sorteos; 20,196 unidades; capital 1,566; caída 1,632 |
| E4 jugar el doble 20 sorteos (train 1.º 0.8403375862754076, train total 0.9889429264963762) | 0.8020 [0.744–0.858]; RD$77,405 / 62,080 / -15,325; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 15,462; caída 15,459 | 0.9464 [0.891–1.001]; RD$77,405 / 73,257 / -4,148; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,665; caída 5,270 | 0.9435 [0.888–0.999]; RD$77,405 / 73,029 / -4,376; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,875; caída 5,427 |
| E5 par/impar tras ≥3 (train 1.º 0.8105658422892659, train total 0.9598342612974233) | 0.8047 [0.788–0.822]; RD$515,300 / 414,640 / -100,660; 5,183 aciertos 1.º; 10,306 sorteos; 515,300 unidades; capital 100,790; caída 100,770 | 0.9541 [0.938–0.971]; RD$515,300 / 491,634 / -23,666; 5,183 aciertos 1.º; 10,306 sorteos; 515,300 unidades; capital 23,850; caída 23,830 | 0.9515 [0.935–0.968]; RD$515,300 / 490,331 / -24,969; 5,183 aciertos 1.º; 10,306 sorteos; 515,300 unidades; capital 25,149; caída 25,129 |
| E5 par/impar tras ≥4 (train 1.º 0.8097097625329815, train total 0.9581583113456464) | 0.8002 [0.779–0.822]; RD$255,050 / 204,080 / -50,970; 2,551 aciertos 1.º; 5,101 sorteos; 255,050 unidades; capital 51,110; caída 51,060 | 0.9515 [0.930–0.974]; RD$255,050 / 242,677 / -12,373; 2,551 aciertos 1.º; 5,101 sorteos; 255,050 unidades; capital 12,531; caída 12,560 | 0.9487 [0.928–0.971]; RD$255,050 / 241,954 / -13,096; 2,551 aciertos 1.º; 5,101 sorteos; 255,050 unidades; capital 13,254; caída 13,275 |
| E5 par/impar tras ≥5 (train 1.º 0.8120236178207193, train total 0.9603864734299516) | 0.7890 [0.757–0.823]; RD$126,850 / 100,080 / -26,770; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 26,850; caída 26,830 | 0.9418 [0.908–0.976]; RD$126,850 / 119,466 / -7,384; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,469; caída 7,666 | 0.9387 [0.908–0.972]; RD$126,850 / 119,079 / -7,771; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,856; caída 8,050 |
| E5 par/impar tras ≥6 (train 1.º 0.8061403508771929, train total 0.9560416666666667) | 0.7763 [0.736–0.821]; RD$64,100 / 49,760 / -14,340; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 14,420; caída 14,510 | 0.9238 [0.885–0.969]; RD$64,100 / 59,213 / -4,887; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 4,972; caída 5,155 | 0.9204 [0.880–0.964]; RD$64,100 / 58,996 / -5,104; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 5,189; caída 5,369 |
| E5 par/impar tras ≥7 (train 1.º 0.7705685618729097, train total 0.9212931995540691) | 0.8122 [0.756–0.877]; RD$32,900 / 26,720 / -6,180; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 6,260; caída 6,210 | 0.9588 [0.902–1.022]; RD$32,900 / 31,546 / -1,354; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 1,457; caída 1,407 | 0.9558 [0.896–1.024]; RD$32,900 / 31,447 / -1,453; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 1,553; caída 1,503 |
| E5 par/impar tras ≥8 (train 1.º 0.8034632034632034, train total 0.9511688311688312) | 0.8025 [0.723–0.892]; RD$16,150 / 12,960 / -3,190; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 3,270; caída 3,260 | 0.9498 [0.873–1.039]; RD$16,150 / 15,339 / -811; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 975; caída 1,003 | 0.9471 [0.871–1.032]; RD$16,150 / 15,296 / -854; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 1,017; caída 1,037 |
| E5 bajo/alto tras ≥3 (train 1.º 0.7981455247907276, train total 0.9474900193174501) | 0.8072 [0.792–0.822]; RD$514,950 / 415,680 / -99,270; 5,196 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 99,410; caída 99,420 | 0.9557 [0.940–0.970]; RD$514,950 / 492,117 / -22,833; 5,196 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 22,992; caída 23,076 | 0.9533 [0.938–0.969]; RD$514,950 / 490,898 / -24,052; 5,196 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 24,211; caída 24,287 |
| E5 bajo/alto tras ≥4 (train 1.º 0.7971036979570727, train total 0.9467287302818722) | 0.7946 [0.773–0.817]; RD$254,000 / 201,840 / -52,160; 2,523 aciertos 1.º; 5,080 sorteos; 254,000 unidades; capital 52,240; caída 52,500 | 0.9445 [0.922–0.967]; RD$254,000 / 239,914 / -14,086; 2,523 aciertos 1.º; 5,080 sorteos; 254,000 unidades; capital 14,169; caída 14,677 | 0.9422 [0.920–0.966]; RD$254,000 / 239,330 / -14,670; 2,523 aciertos 1.º; 5,080 sorteos; 254,000 unidades; capital 14,753; caída 15,255 |
| E5 bajo/alto tras ≥5 (train 1.º 0.7873345445107708, train total 0.9363145600830521) | 0.7991 [0.769–0.832]; RD$127,150 / 101,600 / -25,550; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 25,630; caída 25,620 | 0.9474 [0.914–0.982]; RD$127,150 / 120,465 / -6,685; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 6,785; caída 7,169 | 0.9451 [0.913–0.978]; RD$127,150 / 120,174 / -6,976; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 7,076; caída 7,434 |
| E5 bajo/alto tras ≥6 (train 1.º 0.759280205655527, train total 0.9084318766066838) | 0.8019 [0.759–0.848]; RD$63,150 / 50,640 / -12,510; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 12,590; caída 12,600 | 0.9483 [0.904–0.995]; RD$63,150 / 59,885 / -3,265; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 3,348; caída 3,409 | 0.9461 [0.904–0.994]; RD$63,150 / 59,744 / -3,406; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 3,489; caída 3,545 |
| E5 bajo/alto tras ≥7 (train 1.º 0.757396449704142, train total 0.9095463510848126) | 0.7808 [0.730–0.836]; RD$31,250 / 24,400 / -6,850; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 6,970; caída 6,950 | 0.9271 [0.872–0.988]; RD$31,250 / 28,971 / -2,279; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 2,498; caída 2,490 | 0.9253 [0.872–0.982]; RD$31,250 / 28,916 / -2,334; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 2,542; caída 2,534 |
| E5 bajo/alto tras ≥8 (train 1.º 0.7228733459357278, train total 0.8742911153119093) | 0.8178 [0.744–0.898]; RD$15,750 / 12,880 / -2,870; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 2,990; caída 2,980 | 0.9659 [0.893–1.056]; RD$15,750 / 15,213 / -537; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 700; caída 797 | 0.9640 [0.892–1.049]; RD$15,750 / 15,183 / -567; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 730; caída 826 |

La selección alternativa por retorno total all en entrenamiento es solo sensibilidad, no segunda prueba confirmatoria:

| Idea | Elección alternativa | Solo 1.º: prueba ciega | Total all: prueba ciega | Total best: prueba ciega |
|---|---|---|---|---|
| E2: frío en cualquier ≥200 (train all 1.5458515283842795) | 0.5839 [0.000–4.140]; RD$137 / 80 / -57; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 137; caída 136 | 0.7080 [0.062–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 | 0.7080 [0.055–3.905]; RD$137 / 97 / -40; 1 aciertos 1.º; 137 sorteos; 137 unidades; capital 124; caída 123 |
| E3: jugar el 2º anterior (train all 0.9729600839334255) | 0.8314 [0.756–0.912]; RD$41,953 / 34,880 / -7,073; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 7,243; caída 7,327 | 0.9755 [0.895–1.053]; RD$41,953 / 40,926 / -1,027; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,617; caída 2,226 | 0.9722 [0.892–1.054]; RD$41,953 / 40,787 / -1,166; 436 aciertos 1.º; 41,953 sorteos; 41,953 unidades; capital 1,739; caída 2,308 |
| E4: jugar el doble 20 sorteos (train all 0.9889429264963762) | 0.8020 [0.744–0.858]; RD$77,405 / 62,080 / -15,325; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 15,462; caída 15,459 | 0.9464 [0.891–1.001]; RD$77,405 / 73,257 / -4,148; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,665; caída 5,270 | 0.9435 [0.888–0.999]; RD$77,405 / 73,029 / -4,376; 776 aciertos 1.º; 35,334 sorteos; 77,405 unidades; capital 4,875; caída 5,427 |
| E5: par/impar tras ≥5 (train all 0.9603864734299516) | 0.7890 [0.757–0.823]; RD$126,850 / 100,080 / -26,770; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 26,850; caída 26,830 | 0.9418 [0.908–0.976]; RD$126,850 / 119,466 / -7,384; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,469; caída 7,666 | 0.9387 [0.908–0.972]; RD$126,850 / 119,079 / -7,771; 1,251 aciertos 1.º; 2,537 sorteos; 126,850 unidades; capital 7,856; caída 8,050 |

### E5: ambas escaleras, mismo N seleccionado por apuesta plana al 1.º

La escalera original de premio 70 NO fue optimizada para 80. La nueva se calculó antes de ver resultados: mínimo entero por número para recuperar lo invertido más RD$10 con un único acierto 1.º. Los 50 números cuestan 50 × apuesta por ronda. Pérdida completa = fallo al 1.º en la décima apuesta; puede haber pagos menores sin evitar ese evento. El costo de diez rondas perdidas es determinista. Ausencia de pérdidas raras en prueba ciega NO permite al bootstrap inventar colas no observadas.

**original70_unchanged**: secuencia [1, 3, 10, 35, 123, 430, 1505, 5268, 18438, 64533]; diez fallos: RD$4,517,300; inversión acumulada y neto al acertar 1.º por ronda: [[50, 30], [200, 40], [700, 100], [2450, 350], [8600, 1240], [30100, 4300], [105350, 15050], [368750, 52690], [1290650, 184390], [4517300, 645340]].

| N y variante | Pérdidas completas (todos / prueba) | Solo 1.º prueba | All prueba | Best prueba |
|---|---:|---|---|---|
| par/impar tras ≥3 | 9 / 3 | 0.9317 [0.727–1.142]; RD$73,580,950 / 68,554,640 / -5,026,310; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 14,281,420; caída 13,198,690 | 1.0883 [0.878–1.302]; RD$73,580,950 / 80,081,396 / +6,500,446; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 8,258,512; caída 9,578,523 | 1.0854 [0.862–1.300]; RD$73,580,950 / 79,861,264 / +6,280,314; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 8,472,795; caída 9,724,105 |
| par/impar tras ≥4 | 4 / 3 | 0.6377 [0.362–1.143]; RD$30,654,500 / 19,547,680 / -11,106,820; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 13,754,850; caída 13,447,020 | 0.8017 [0.535–1.297]; RD$30,654,500 / 24,576,408 / -6,078,092; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 10,296,380; caída 10,673,392 | 0.7997 [0.536–1.301]; RD$30,654,500 / 24,513,613 / -6,140,887; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 10,357,531; caída 10,714,950 |
| par/impar tras ≥5 | 2 / 1 | 0.8629 [0.363–1.145]; RD$18,414,450 / 15,890,560 / -2,523,890; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 8,772,500; caída 5,722,520 | 1.0109 [0.558–1.306]; RD$18,414,450 / 18,614,487 / +200,037; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 7,560,355; caída 4,680,023 | 1.0099 [0.548–1.308]; RD$18,414,450 / 18,596,602 / +182,152; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 7,576,013; caída 4,690,907 |
| par/impar tras ≥6 | 0 / 0 | 1.1436 [1.143–1.148]; RD$8,476,450 / 9,693,280 / +1,216,830; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 4,466,410; caída 1,290,650 | 1.3265 [1.275–1.354]; RD$8,476,450 / 11,244,046 / +2,767,596; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 4,207,863; caída 1,080,146 | 1.3259 [1.273–1.353]; RD$8,476,450 / 11,238,960 / +2,762,510; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 4,212,235; caída 1,083,156 |
| par/impar tras ≥7 | 0 / 0 | 1.1446 [1.143–1.154]; RD$2,416,350 / 2,765,760 / +349,410; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 1,275,710; caída 368,750 | 1.3276 [1.276–1.356]; RD$2,416,350 / 3,208,020 / +791,670; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 1,202,013; caída 308,609 | 1.3270 [1.275–1.355]; RD$2,416,350 / 3,206,591 / +790,241; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 1,203,256; caída 309,469 |
| par/impar tras ≥8 | 0 / 0 | 1.1460 [1.144–1.163]; RD$687,250 / 787,600 / +100,350; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 364,390; caída 105,350 | 1.3292 [1.280–1.357]; RD$687,250 / 913,504 / +226,254; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 343,420; caída 88,167 | 1.3286 [1.278–1.357]; RD$687,250 / 913,107 / +225,857; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 343,775; caída 88,413 |
| bajo/alto tras ≥3 | 10 / 5 | 0.7344 [0.504–1.025]; RD$63,135,800 / 46,364,880 / -16,770,920; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 18,007,730; caída 17,790,910 | 0.8758 [0.655–1.144]; RD$63,135,800 / 55,292,614 / -7,843,186; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 10,797,052; caída 10,189,764 | 0.8730 [0.649–1.149]; RD$63,135,800 / 55,120,371 / -8,015,429; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 10,960,977; caída 10,264,480 |
| bajo/alto tras ≥4 | 4 / 2 | 0.8409 [0.505–1.144]; RD$34,123,450 / 28,694,480 / -5,428,970; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 5,465,620; caída 8,653,300 | 0.9646 [0.617–1.290]; RD$34,123,450 / 32,916,099 / -1,207,351; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 3,759,758; caída 7,533,074 | 0.9632 [0.630–1.289]; RD$34,123,450 / 32,867,007 / -1,256,443; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 3,760,531; caída 7,535,610 |
| bajo/alto tras ≥5 | 2 / 0 | 1.1438 [1.143–1.146]; RD$16,179,700 / 18,505,840 / +2,326,140; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 3,596,470; caída 1,290,650 | 1.3258 [1.271–1.349]; RD$16,179,700 / 21,450,879 / +5,271,179; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 2,577,960; caída 1,194,948 | 1.3249 [1.267–1.348]; RD$16,179,700 / 21,436,902 / +5,257,202; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 2,591,224; caída 1,194,958 |
| bajo/alto tras ≥6 | 2 / 0 | 1.1447 [1.144–1.149]; RD$4,610,800 / 5,277,760 / +666,960; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 1,025,950; caída 368,750 | 1.3267 [1.272–1.350]; RD$4,610,800 / 6,117,358 / +1,506,558; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 736,309; caída 341,408 | 1.3259 [1.270–1.351]; RD$4,610,800 / 6,113,394 / +1,502,594; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 740,083; caída 341,411 |
| bajo/alto tras ≥7 | 1 / 0 | 1.1458 [1.144–1.152]; RD$1,311,450 / 1,502,720 / +191,270; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 292,800; caída 105,350 | 1.3281 [1.275–1.352]; RD$1,311,450 / 1,741,740 / +430,290; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 210,646; caída 97,536 | 1.3273 [1.274–1.351]; RD$1,311,450 / 1,740,627 / +429,177; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 211,708; caída 97,537 |
| bajo/alto tras ≥8 | 1 / 0 | 1.1490 [1.146–1.164]; RD$372,000 / 427,440 / +55,440; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 82,990; caída 30,100 | 1.3316 [1.282–1.355]; RD$372,000 / 495,359 / +123,359; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 59,766; caída 27,868 | 1.3308 [1.281–1.353]; RD$372,000 / 495,044 / +123,044; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 60,067; caída 27,868 |

Candidato seleccionado: métricas de **todos los datos** (NO de prueba ciega):

| Variante | Solo 1.º: todos | All: todos | Best: todos |
|---|---|---|---|
| par/impar tras ≥5 | 0.8501 [0.547–1.144]; RD$35,298,750 / 30,006,560 / -5,292,190; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 11,540,800; caída 9,915,640 | 0.9809 [0.673–1.284]; RD$35,298,750 / 34,624,605 / -674,145; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 8,434,537; caída 8,204,611 | 0.9800 [0.683–1.283]; RD$35,298,750 / 34,591,020 / -707,730; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 8,465,895; caída 8,221,251 |

**precomputed80**: secuencia [1, 2, 6, 16, 42, 112, 299, 797, 2126, 5669]; diez fallos: RD$453,500; inversión acumulada y neto al acertar 1.º por ronda: [[50, 30], [150, 10], [450, 30], [1250, 30], [3350, 10], [8950, 10], [23900, 20], [63750, 10], [170050, 30], [453500, 20]].

| N y variante | Pérdidas completas (todos / prueba) | Solo 1.º prueba | All prueba | Best prueba |
|---|---:|---|---|---|
| par/impar tras ≥3 | 9 / 3 | 0.8814 [0.751–1.010]; RD$10,668,400 / 9,403,600 / -1,264,800; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 1,758,020; caída 1,498,730 | 1.0346 [0.900–1.164]; RD$10,668,400 / 11,037,193 / +368,793; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 809,849; caída 891,550 | 1.0316 [0.888–1.162]; RD$10,668,400 / 11,006,031 / +337,631; 5,180 aciertos 1.º; 10,299 sorteos; 514,950 unidades; capital 838,825; caída 907,027 |
| par/impar tras ≥4 | 4 / 3 | 0.7256 [0.514–1.014]; RD$4,773,450 / 3,463,760 / -1,309,690; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 1,500,400; caída 1,405,670 | 0.8836 [0.678–1.172]; RD$4,773,450 / 4,217,868 / -555,582; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 999,590; caída 1,030,168 | 0.8812 [0.673–1.167]; RD$4,773,450 / 4,206,344 / -567,106; 2,548 aciertos 1.º; 5,097 sorteos; 254,850 unidades; capital 1,010,340; caída 1,035,914 |
| par/impar tras ≥5 | 2 / 1 | 0.8360 [0.538–1.022]; RD$2,602,050 / 2,175,200 / -426,850; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 891,110; caída 614,140 | 0.9861 [0.701–1.180]; RD$2,602,050 / 2,565,766 / -36,284; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 712,693; caída 480,140 | 0.9844 [0.686–1.180]; RD$2,602,050 / 2,561,554 / -40,496; 1,250 aciertos 1.º; 2,536 sorteos; 126,800 unidades; capital 716,001; caída 481,963 |
| par/impar tras ≥6 | 0 / 0 | 1.0107 [1.005–1.029]; RD$1,240,250 / 1,253,520 / +13,270; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 450,420; caída 170,050 | 1.1812 [1.150–1.205]; RD$1,240,250 / 1,464,973 / +224,723; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 406,111; caída 141,745 | 1.1800 [1.149–1.203]; RD$1,240,250 / 1,463,439 / +223,189; 622 aciertos 1.º; 1,282 sorteos; 64,100 unidades; capital 407,261; caída 142,343 |
| par/impar tras ≥7 | 0 / 0 | 1.0166 [1.008–1.049]; RD$455,950 / 463,520 / +7,570; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 168,290; caída 63,750 | 1.1875 [1.157–1.215]; RD$455,950 / 541,446 / +85,496; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 151,944; caída 53,137 | 1.1863 [1.156–1.214]; RD$455,950 / 540,904 / +84,954; 334 aciertos 1.º; 658 sorteos; 32,900 unidades; capital 152,365; caída 53,361 |
| par/impar tras ≥8 | 0 / 0 | 1.0220 [1.011–1.066]; RD$165,950 / 169,600 / +3,650; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 62,840; caída 23,900 | 1.1936 [1.164–1.226]; RD$165,950 / 198,082 / +32,132; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 56,873; caída 19,921 | 1.1925 [1.162–1.226]; RD$165,950 / 197,897 / +31,947; 162 aciertos 1.º; 323 sorteos; 16,150 unidades; capital 57,029; caída 20,005 |
| bajo/alto tras ≥3 | 10 / 5 | 0.7730 [0.623–0.955]; RD$9,524,150 / 7,362,000 / -2,162,150; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 2,186,610; caída 2,195,690 | 0.9153 [0.766–1.094]; RD$9,524,150 / 8,717,117 / -807,033; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 1,060,697; caída 1,070,708 | 0.9129 [0.760–1.088]; RD$9,524,150 / 8,694,419 / -829,731; 5,191 aciertos 1.º; 10,292 sorteos; 514,600 unidades; capital 1,081,119; caída 1,085,477 |
| bajo/alto tras ≥4 | 4 / 2 | 0.8260 [0.603–1.016]; RD$4,910,050 / 4,055,840 / -854,210; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 863,390; caída 898,320 | 0.9572 [0.746–1.158]; RD$4,910,050 / 4,699,897 / -210,153; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 337,063; caída 730,600 | 0.9555 [0.734–1.158]; RD$4,910,050 / 4,691,583 / -218,467; 2,521 aciertos 1.º; 5,078 sorteos; 253,900 unidades; capital 337,493; caída 731,491 |
| bajo/alto tras ≥5 | 2 / 0 | 1.0116 [1.007–1.023]; RD$2,370,450 / 2,397,840 / +27,390; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 432,880; caída 170,050 | 1.1756 [1.150–1.192]; RD$2,370,450 / 2,786,731 / +416,281; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 240,475; caída 154,944 | 1.1743 [1.149–1.192]; RD$2,370,450 / 2,783,705 / +413,255; 1,270 aciertos 1.º; 2,543 sorteos; 127,150 unidades; capital 243,185; caída 154,950 |
| bajo/alto tras ≥6 | 2 / 0 | 1.0170 [1.010–1.036]; RD$870,050 / 884,800 / +14,750; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 159,050; caída 63,750 | 1.1813 [1.158–1.198]; RD$870,050 / 1,027,808 / +157,758; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 88,966; caída 58,088 | 1.1801 [1.156–1.198]; RD$870,050 / 1,026,710 / +156,660; 633 aciertos 1.º; 1,263 sorteos; 63,150 unidades; capital 89,963; caída 58,090 |
| bajo/alto tras ≥7 | 1 / 0 | 1.0228 [1.014–1.048]; RD$316,550 / 323,760 / +7,210; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 58,540; caída 23,900 | 1.1876 [1.165–1.205]; RD$316,550 / 375,935 / +59,385; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 33,287; caída 21,774 | 1.1864 [1.164–1.204]; RD$316,550 / 375,552 / +59,002; 305 aciertos 1.º; 625 sorteos; 31,250 unidades; capital 33,637; caída 21,775 |
| bajo/alto tras ≥8 | 1 / 0 | 1.0313 [1.019–1.070]; RD$113,950 / 117,520 / +3,570; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 21,200; caída 8,950 | 1.1969 [1.177–1.220]; RD$113,950 / 136,391 / +22,441; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 12,227; caída 8,158 | 1.1958 [1.174–1.219]; RD$113,950 / 136,258 / +22,308; 161 aciertos 1.º; 315 sorteos; 15,750 unidades; capital 12,350; caída 8,158 |

Candidato seleccionado: métricas de **todos los datos** (NO de prueba ciega):

| Variante | Solo 1.º: todos | All: todos | Best: todos |
|---|---|---|---|
| par/impar tras ≥5 | 0.8458 [0.652–1.016]; RD$5,506,600 / 4,657,440 / -849,160; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 1,313,420; caída 1,058,480 | 0.9819 [0.786–1.158]; RD$5,506,600 / 5,407,045 / -99,555; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 775,964; caída 815,063 | 0.9803 [0.794–1.158]; RD$5,506,600 / 5,398,318 / -108,282; 3,140 aciertos 1.º; 6,261 sorteos; 313,050 unidades; capital 783,787; caída 818,678 |

## E6: alcanzar meta (NO pronóstico)

El límite banco/meta solo corresponde al caso hipotético de juego justo; con pagos 80/8/4/2/1 hay margen. MC uniforme usa el mismo perfil y modo all/best que la serie real. IC Wilson 95%.

| Modo | Capital → meta | Estilo | Real [IC], sesiones | MC [IC], mediana sorteos | Cota justa |
|---|---|---|---|---|---:|
| all | 1,000 → 2,000 | audaz | 48.20% [46.12%–50.28%], n=2218 | 47.28% [46.59%–47.98%], mediana 55 | 50.00% |
| all | 1,000 → 2,000 | tímida (10 por sorteo) | 42.78% [38.82%–46.84%], n=582 | 40.17% [39.50%–40.86%], mediana 133 | 50.00% |
| all | 5,000 → 10,000 | audaz | 49.18% [47.09%–51.27%], n=2198 | 47.63% [46.94%–48.32%], mediana 56 | 50.00% |
| all | 5,000 → 10,000 | tímida (10 por sorteo) | 40.00% [24.59%–57.68%], n=30 | 30.22% [29.59%–30.86%], mediana 2845 | 50.00% |
| best | 1,000 → 2,000 | audaz | 48.04% [45.97%–50.12%], n=2219 | 47.27% [46.57%–47.96%], mediana 55 | 50.00% |
| best | 1,000 → 2,000 | tímida (10 por sorteo) | 42.43% [38.43%–46.53%], n=568 | 39.94% [39.26%–40.62%], mediana 133 | 50.00% |
| best | 5,000 → 10,000 | audaz | 49.14% [47.05%–51.23%], n=2200 | 47.57% [46.87%–48.26%], mediana 56 | 50.00% |
| best | 5,000 → 10,000 | tímida (10 por sorteo) | 38.46% [22.43%–57.47%], n=26 | 29.48% [28.86%–30.12%], mediana 2842 | 50.00% |

## E7 y E8

| Repetidos | Teórico | Observado |
|---|---:|---:|
| All | 0.9500000000 | 0.9500 |
| Best | 0.9474159401 | 0.9474 |
| Sorteos con repetidos | 9.65% | 9.58% |

- E8 `loteka.com.do`: 28,530 sorteos, 2026-04-25 a 2026-09-25 (períodos disjuntos).
- E8 `premios.do`: 76,896 sorteos, 2025-03-05 a 2026-04-24 (períodos disjuntos).
E8: 238 filas, 17 N/A (celdas dispersas o sin casos); no detectar diferencia NO prueba equivalencia. Comparación directa de globos y repetidos:

| ID | Pregunta | Observado | Esperado | Casos | p | p Holm | Veredicto |
|---|---|---:|---:|---:|---:|---:|---|
| E8 globo 1 | Misma distribución por fuente, globo 1 | — | — | 105,426 | 0.5381 | 1.0000 | ✅ PASA |
| E8 globo 2 | Misma distribución por fuente, globo 2 | — | — | 105,426 | 0.6039 | 1.0000 | ✅ PASA |
| E8 globo 3 | Misma distribución por fuente, globo 3 | — | — | 105,426 | 0.9741 | 1.0000 | ✅ PASA |
| E8 globo 4 | Misma distribución por fuente, globo 4 | — | — | 105,426 | 0.8804 | 1.0000 | ✅ PASA |
| E8 globo 5 | Misma distribución por fuente, globo 5 | — | — | 105,426 | 0.0926 | 1.0000 | ✅ PASA |
| E8 repetidos | Misma tasa de sorteos con repetidos por fuente | — | — | 105,426 | 0.5755 | 1.0000 | ✅ PASA |

- E8 loteka.com.do B3a: N/A — chi²=9830 (gl=9801), 28376 pares; N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.12: N/A — chi²=9925 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.13: N/A — chi²=9706 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.14: N/A — chi²=9698 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.15: N/A — chi²=9887 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.23: N/A — chi²=9922 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.24: N/A — chi²=9952 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.25: N/A — chi²=9830 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.34: N/A — chi²=9917 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.35: N/A — chi²=9911 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do B4.45: N/A — chi²=9657 (gl=9801); N/A: 100×100 expected count <5/cell; exploratory
- E8 loteka.com.do E2 cualquier X=300: N/A — sin casos
- E8 loteka.com.do E2 cualquier X=400: N/A — sin casos
- E8 loteka.com.do E2 cualquier X=500: N/A — sin casos
- E8 premios.do E2 cualquier X=300: N/A — sin casos
- E8 premios.do E2 cualquier X=400: N/A — sin casos
- E8 premios.do E2 cualquier X=500: N/A — sin casos

## Controles y límites

**sano (SHA-256)**: ✅ 0/40 pruebas válidas fallan; ⚠️ 0/9 pruebas válidas fallan, 3 N/A; ✅ 0/6 pruebas válidas fallan; ✅ 0/6 pruebas válidas fallan; ✅ 0/12 pruebas válidas fallan; ✅ 0/8 pruebas válidas fallan; ⚠️ 0/221 pruebas válidas fallan, 1 sospechosas, 17 N/A
- E2 first frío en cualquier ≥200: IC [0.000000, 2.442815] cubre 0.8000000000; 160 sorteos, 160 unidades, 3 aciertos 1.º.
- E2 all frío en cualquier ≥200: IC [0.333333, 2.569705] cubre 0.9500000000; 160 sorteos, 160 unidades, 3 aciertos 1.º.
- E2 best frío en cualquier ≥200: IC [0.319111, 2.520256] cubre 0.9474159401; 160 sorteos, 160 unidades, 3 aciertos 1.º.
- E3 first jugar el 3º anterior: IC [0.733138, 0.888545] cubre 0.8000000000; 41953 sorteos, 41,953 unidades, 426 aciertos 1.º.
- E3 all jugar el 3º anterior: IC [0.892365, 1.045173] cubre 0.9500000000; 41953 sorteos, 41,953 unidades, 426 aciertos 1.º.
- E3 best jugar el 3º anterior: IC [0.888879, 1.043058] cubre 0.9474159401; 41953 sorteos, 41,953 unidades, 426 aciertos 1.º.
- E4 first jugar el doble 1 sorteos: IC [0.665179, 1.205473] cubre 0.8000000000; 4034 sorteos, 4,107 unidades, 48 aciertos 1.º.
- E4 all jugar el doble 1 sorteos: IC [0.829710, 1.355938] cubre 0.9500000000; 4034 sorteos, 4,107 unidades, 48 aciertos 1.º.
- E4 best jugar el doble 1 sorteos: IC [0.819089, 1.349365] cubre 0.9474159401; 4034 sorteos, 4,107 unidades, 48 aciertos 1.º.
- E5 first par/impar tras ≥3: IC [0.771403, 0.801289] cubre 0.8000000000; 10651 sorteos, 532,550 unidades, 5230 aciertos 1.º.
- E5 all par/impar tras ≥3: IC [0.920200, 0.949524] NO cubre 0.9500000000; 10651 sorteos, 532,550 unidades, 5230 aciertos 1.º.
- E5 best par/impar tras ≥3: IC [0.917215, 0.946451] NO cubre 0.9474159401; 10651 sorteos, 532,550 unidades, 5230 aciertos 1.º.

**trampa (4 patrones sembrados)**: ❌ 3/40 pruebas válidas fallan, 2 sospechosas; ❌ 5/9 pruebas válidas fallan, 1 sospechosas, 3 N/A; ❌ 6/6 pruebas válidas fallan; ❌ 6/6 pruebas válidas fallan; ❌ 4/12 pruebas válidas fallan; ✅ 0/8 pruebas válidas fallan; ❌ 34/221 pruebas válidas fallan, 9 sospechosas, 17 N/A
- E2 first frío en 1º ≥400: IC [1.885685, 2.661814] NO cubre 0.8000000000; 4512 sorteos, 4,727 unidades, 132 aciertos 1.º.
- E2 all frío en 1º ≥400: IC [2.012758, 2.808763] NO cubre 0.9500000000; 4512 sorteos, 4,727 unidades, 132 aciertos 1.º.
- E2 best frío en 1º ≥400: IC [2.002439, 2.825493] NO cubre 0.9474159401; 4512 sorteos, 4,727 unidades, 132 aciertos 1.º.
- E3 first jugar el 2º anterior: IC [4.804369, 5.195754] NO cubre 0.8000000000; 41953 sorteos, 41,953 unidades, 2622 aciertos 1.º.
- E3 all jugar el 2º anterior: IC [4.971409, 5.339681] NO cubre 0.9500000000; 41953 sorteos, 41,953 unidades, 2622 aciertos 1.º.
- E3 best jugar el 2º anterior: IC [4.938325, 5.332819] NO cubre 0.9474159401; 41953 sorteos, 41,953 unidades, 2622 aciertos 1.º.
- E4 first jugar el doble 1 sorteos: IC [5.614647, 6.795948] NO cubre 0.8000000000; 4055 sorteos, 4,121 unidades, 319 aciertos 1.º.
- E4 all jugar el doble 1 sorteos: IC [5.765336, 6.980828] NO cubre 0.9500000000; 4055 sorteos, 4,121 unidades, 319 aciertos 1.º.
- E4 best jugar el doble 1 sorteos: IC [5.753043, 6.960489] NO cubre 0.9474159401; 4055 sorteos, 4,121 unidades, 319 aciertos 1.º.
- E5 first par/impar tras ≥5: IC [0.874955, 0.944409] NO cubre 0.8000000000; 2345 sorteos, 117,250 unidades, 1332 aciertos 1.º.
- E5 all par/impar tras ≥5: IC [1.022238, 1.092955] NO cubre 0.9500000000; 2345 sorteos, 117,250 unidades, 1332 aciertos 1.º.
- E5 best par/impar tras ≥5: IC [1.018830, 1.087984] NO cubre 0.9474159401; 2345 sorteos, 117,250 unidades, 1332 aciertos 1.º.


## 4. Controles: sensibilidad a patrones sembrados (no validación universal)

| Patrón sembrado en *trampa* | Prueba | Chance Express | sano (SHA-256) | trampa (4 patrones sembrados) |
|---|---|---|---|---|
| Tras ≥5 impares en el 1º, par 65% | E1 par-g1 N=5 | ✅ obs 0.5071 (esp 0.5000), Holm 1.0000 | ✅ obs 0.4928 (esp 0.5000), Holm 1.0000 | ❌ obs 0.5927 (esp 0.5000), Holm 2.11e-24 |
| Tras ≥5 impares en el 1º, par 65% | E5 par/impar N≥5 | ✅ obs 0.5017 (esp 0.5000), Holm 1.0000 | ✅ obs 0.4921 (esp 0.5000), Holm 1.0000 | ❌ obs 0.5771 (esp 0.5000), Holm 2.63e-29 |
| El 2º pasa al 1º del siguiente (5%) | E3 2º→1º | ✅ obs 0.0103 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0099 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0620 (esp 0.0100), Holm <1e-300 |
| Un doble sale 1º en el siguiente (5%) | E4 1º w=1 | ✅ obs 0.0087 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0109 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0787 (esp 0.0100), Holm 7.75e-156 |
| Frío ≥300 sorteos sale 1º con 3% | E2 1º X=300 | ✅ obs 0.0100 (esp 0.0100), Holm 1.0000 | ✅ obs 0.0100 (esp 0.0100), Holm 1.0000 | ❌ obs 0.0283 (esp 0.0100), Holm <1e-300 |
Los cuatro defectos sembrados (racha, arrastre, doble, frío) sirven para sensibilidad, no certifican ausencia de otros defectos. El criterio sano E5 original quedó **NO APROBADO**; el piloto 19/20 sobre 0,85 y STR-13 siguen históricos, NO se trasladan al premio 80. No se ajustaron semillas para hacer cubrir IC.

E4 usa ventanas solapadas e inferencia agrupada por día; Holm no elimina dependencia intradía. E8 compara fuentes de épocas distintas, con tablas 100×100 dispersas N/A. IC bootstrap por día asume días independientes, no ajusta simultáneamente grillas y puede ser poco informativo para apuestas escasas. La selección post hoc de cualquier fila no confirma predicción; cambios futuros y pérdidas raras no observadas quedan fuera del bootstrap.

## E9: transición descriptiva tras X (00–99)

Solo pares consecutivos del mismo día en Chance Express; matriz 100×100 íntegra en JSON. No hay elección ni p por X, ni predicción.

| X | Casos | Repeticiones | Tasa |
|---|---:|---:|---:|
| 00 | 1,081 | 10 | 0.93% |
| 01 | 1,048 | 7 | 0.67% |
| 02 | 1,097 | 11 | 1.00% |
| 03 | 1,046 | 5 | 0.48% |
| 04 | 1,049 | 10 | 0.95% |
| 05 | 1,038 | 11 | 1.06% |
| 06 | 1,033 | 8 | 0.77% |
| 07 | 1,023 | 10 | 0.98% |
| 08 | 974 | 4 | 0.41% |
| 09 | 1,006 | 11 | 1.09% |
| 10 | 1,109 | 11 | 0.99% |
| 11 | 992 | 7 | 0.71% |
| 12 | 1,020 | 10 | 0.98% |
| 13 | 1,090 | 10 | 0.92% |
| 14 | 1,082 | 9 | 0.83% |
| 15 | 1,088 | 13 | 1.19% |
| 16 | 1,076 | 7 | 0.65% |
| 17 | 1,071 | 9 | 0.84% |
| 18 | 1,056 | 8 | 0.76% |
| 19 | 1,065 | 11 | 1.03% |
| 20 | 1,015 | 11 | 1.08% |
| 21 | 1,063 | 6 | 0.56% |
| 22 | 1,076 | 10 | 0.93% |
| 23 | 1,058 | 9 | 0.85% |
| 24 | 1,036 | 7 | 0.68% |
| 25 | 1,095 | 19 | 1.74% |
| 26 | 1,032 | 7 | 0.68% |
| 27 | 1,005 | 11 | 1.09% |
| 28 | 984 | 9 | 0.91% |
| 29 | 1,015 | 11 | 1.08% |
| 30 | 1,121 | 14 | 1.25% |
| 31 | 1,036 | 11 | 1.06% |
| 32 | 1,052 | 7 | 0.67% |
| 33 | 1,058 | 13 | 1.23% |
| 34 | 1,059 | 10 | 0.94% |
| 35 | 1,106 | 20 | 1.81% |
| 36 | 1,036 | 14 | 1.35% |
| 37 | 1,046 | 7 | 0.67% |
| 38 | 1,018 | 9 | 0.88% |
| 39 | 1,000 | 9 | 0.90% |
| 40 | 1,049 | 11 | 1.05% |
| 41 | 1,053 | 15 | 1.42% |
| 42 | 1,033 | 15 | 1.45% |
| 43 | 1,063 | 8 | 0.75% |
| 44 | 1,020 | 10 | 0.98% |
| 45 | 1,023 | 9 | 0.88% |
| 46 | 1,074 | 5 | 0.47% |
| 47 | 1,044 | 13 | 1.25% |
| 48 | 1,011 | 8 | 0.79% |
| 49 | 1,002 | 9 | 0.90% |
| 50 | 1,057 | 15 | 1.42% |
| 51 | 1,089 | 7 | 0.64% |
| 52 | 992 | 9 | 0.91% |
| 53 | 1,052 | 10 | 0.95% |
| 54 | 999 | 15 | 1.50% |
| 55 | 1,050 | 9 | 0.86% |
| 56 | 1,066 | 9 | 0.84% |
| 57 | 1,084 | 9 | 0.83% |
| 58 | 1,030 | 12 | 1.17% |
| 59 | 1,079 | 9 | 0.83% |
| 60 | 1,004 | 16 | 1.59% |
| 61 | 1,026 | 12 | 1.17% |
| 62 | 1,089 | 15 | 1.38% |
| 63 | 994 | 5 | 0.50% |
| 64 | 1,040 | 8 | 0.77% |
| 65 | 1,093 | 8 | 0.73% |
| 66 | 1,022 | 10 | 0.98% |
| 67 | 1,036 | 12 | 1.16% |
| 68 | 1,050 | 3 | 0.29% |
| 69 | 1,105 | 11 | 1.00% |
| 70 | 1,066 | 16 | 1.50% |
| 71 | 1,083 | 8 | 0.74% |
| 72 | 1,017 | 9 | 0.88% |
| 73 | 1,034 | 4 | 0.39% |
| 74 | 1,057 | 9 | 0.85% |
| 75 | 995 | 10 | 1.01% |
| 76 | 1,008 | 14 | 1.39% |
| 77 | 1,104 | 9 | 0.82% |
| 78 | 1,066 | 12 | 1.13% |
| 79 | 1,050 | 10 | 0.95% |
| 80 | 1,072 | 15 | 1.40% |
| 81 | 1,089 | 13 | 1.19% |
| 82 | 998 | 8 | 0.80% |
| 83 | 1,082 | 11 | 1.02% |
| 84 | 1,043 | 5 | 0.48% |
| 85 | 1,048 | 12 | 1.15% |
| 86 | 1,035 | 14 | 1.35% |
| 87 | 1,096 | 19 | 1.73% |
| 88 | 1,081 | 8 | 0.74% |
| 89 | 1,017 | 11 | 1.08% |
| 90 | 1,066 | 5 | 0.47% |
| 91 | 1,036 | 15 | 1.45% |
| 92 | 1,021 | 6 | 0.59% |
| 93 | 1,063 | 11 | 1.03% |
| 94 | 1,027 | 5 | 0.49% |
| 95 | 1,051 | 8 | 0.76% |
| 96 | 1,060 | 7 | 0.66% |
| 97 | 1,109 | 15 | 1.35% |
| 98 | 1,067 | 8 | 0.75% |
| 99 | 1,035 | 8 | 0.77% |
