# Plan: Auditoría del generador aleatorio de Chance Express

> Creado con `plan-mode-trae` · Idioma: español · Fecha: 2026-09-26
> Aprobado por el usuario en el mismo pedido ("crea un plan ... ejecútalo con ODD").

## Summary

Construir una auditoría de solo lectura sobre `chance_express_history.json` que aplique NIST SP 800-22
y pruebas específicas para números 00–99. Se validan las pruebas con generadores de control (uno sano
y tres defectuosos a propósito) y se genera un reporte con las conclusiones.

## Current State Analysis

- **Proyecto**: Python en la raíz (`download_chance_express.py`), sin paquete ni tests formales.
  Hay Python 3.14 con numpy 2.4, scipy 1.17, pandas y matplotlib. No hay `gcc`, así que TestU01 no
  compila, y no se instalan dependencias.
- **Datos**: `chance_express_history.json` → `sorteos_por_fecha[YYYY-MM-DD] = [{hora "HH:MM",
  numeros [5 strings "00"-"99"], source_url}]`. 570 fechas, 105.426 sorteos, 4 días vacíos,
  ~187 sorteos/día entre 05:05 y 21:55 (cada 5 minutos).
- **Hallazgos previos (sesión)**: chi² por posición ≈ 99, independencia de globos (9,58% repetidos
  vs 9,66% teórico), correlación de frecuencias 60/40 = 0,03, Markov par/impar 50,28%.
- **ODD**: `odd/tasks/<slug>.md` con Objective / Scope / Constraints / Tasks `XXX-n` + Evidence /
  Acceptance criteria / Progress.
- **Restricciones**: el JSON y los archivos legacy no se modifican. No se instala nada. No hay commit.

## Proposed Changes

### 1 — `rng_audit/nist_sp800_22.py`
- **Qué**: las 15 pruebas de NIST SP 800-22 rev1a (frequency, block frequency, runs, longest run,
  binary matrix rank, DFT, non-overlapping template (148 plantillas m=9), overlapping template,
  Maurer universal, linear complexity (Berlekamp-Massey), serial, approximate entropy, cumulative
  sums, random excursions, random excursions variant).
- **Por qué**: es la batería estándar pedida y no se puede instalar la suite oficial.
- **Cómo**: funciones puras `test_x(bits: np.ndarray) -> list[float]` (p-values); numpy vectorizado;
  `scipy.special.gammaincc/erfc`. Las constantes π se toman de SP 800-22 rev1a.

### 2 — `rng_audit/test_nist_examples.py`
- **Qué**: fixtures escritas antes que el código, con los ejemplos numéricos del documento NIST
  (frequency 1011010101 → 0,527089; block frequency 0110011010, M=3 → 0,801252; runs 1001101011 →
  0,147232; cusum 1011010111 → 0,4116588; ApEn 0100110101, m=3 → 0,261961; serial 0011011101, m=3 →
  0,808792 / 0,670320).
- **Por qué**: demostrar que la implementación propia coincide con la referencia.

### 3 — `rng_audit/lottery_tests.py`
- **Qué**: pruebas específicas para 00–99:
  B1 sesgo de módulo (00–55 vs 56–99, fuente de 8 bits; 00–35 vs 36–99, fuente de 16 bits) ·
  B2 uniformidad por posición y global · B3 transición sorteo N→N+1 dentro del mismo día (100×100) ·
  B4 independencia entre globos (10 pares 100×100) · B5 decenas y unidades, y su independencia ·
  B6 gaps contra la distribución geométrica · B7 autocorrelación (valor y paridad) a lags 1–187 dentro
  del día, con Ljung-Box · B8 misma hora en días consecutivos (coincidencias de 1ª posición) ·
  B9 5-tuplas duplicadas y n-gramas repetidos de 1ª posición contra lo esperado · B10 relaciones
  lineales mod 100 (x' − a·x) para todo a, entre sorteos y entre globos · B11 efecto hora /
  día de la semana / mes.
- **Por qué**: detectan los errores reales de implementación de loterías digitales.

### 4 — `rng_audit/generators.py`
- **Qué**: datasets de control con la misma estructura (mismas fechas y horas):
  `crypto` (`secrets`, sano) · `lcg_low_bits` (LCG glibc `% 100`) · `modulo_bias_8bit`
  (`randbits(8) % 100`) · `seeded_by_time` (semilla = hora del día, días idénticos).
- **Por qué**: probar que las pruebas detectan fallas y ver cómo se ve un generador sano.

### 5 — `rng_audit/run_audit.py`
- **Qué**: carga el JSON (solo lectura), ordena por fecha y hora, arma dos flujos de bits
  (rechazo a 6 bits usando solo 00–63; paridad de la 1ª posición), corre NIST (20 secuencias de
  100.000 bits; Maurer y excursiones sobre 2 × 1.000.000) y las pruebas B1–B11 sobre los 5 datasets.
  Aplica Holm (α=0,01) y BH-FDR, y escribe `reports/rng_audit.md` y `reports/rng_audit.json`.
- **Criterio NIST**: proporción de secuencias con p ≥ 0,01 dentro de p̂ ± 3·sqrt(p̂(1−p̂)/m)
  (con 20 secuencias hacen falta ≥ 19 aprobadas).

### 6 — `odd/tasks/rng-audit.md`
- **Qué**: tarea ODD con RNG-1…RNG-6 y la evidencia de cada una.

## Assumptions & Decisions

- Dieharder no se corre: necesita cientos de MB y hay ~250 KB, así que reciclaría datos y daría
  falsos fallos.
- TestU01 no se corre: no hay compilador y no se instalan dependencias. Se reporta como limitación.
- Bits: solo los valores 00–63 → 6 bits (MSB primero), para no introducir sesgo propio.
- Las pruebas seriales no cruzan cortes de día (21:55 → 05:05 del día siguiente).
- Umbral: α = 0,01 con corrección de Holm para decidir "falla". BH-FDR se informa como apoyo.
- Semillas fijas en los controles para que sean reproducibles.
- Código en inglés; reporte y ODD en español (idioma del usuario).

## Verification

- [ ] `py -m pytest rng_audit/test_nist_examples.py -q` coincide con los valores de NIST.
- [ ] `py rng_audit/run_audit.py` termina y escribe `reports/rng_audit.md`/`.json`.
- [ ] Controles: `crypto` pasa. `lcg_low_bits`, `modulo_bias_8bit` y `seeded_by_time` fallan en
      las pruebas que les corresponden.
- [ ] El hash SHA-256 de `chance_express_history.json` no cambia.
- [ ] LSP/diagnósticos sin errores en `rng_audit/`.

## Out of Scope

- Instalar TestU01, Dieharder o paquetes nuevos.
- Predictores, laboratorio MCP y web.
- Commit, push y PR.
