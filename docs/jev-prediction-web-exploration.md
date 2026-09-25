# Exploración y propuesta de arquitectura: Web JEV/System One para predicción de lotería

> Documento de exploración y arquitectura. No es implementación final: las preguntas exactas, la UI
> definitiva y el comportamiento final quedan pendientes de definición por el usuario.

## 1. Resumen de lo que se entendió que se quiere construir

Una web nueva e independiente (no dentro de `flet_app.py`) donde:

- Se carga o pega una lista de números de lotería (00–99).
- Esa lista se convierte en un estado/contexto estructurado.
- Ese estado se envía a JEV/System One Models como una cadena secuencial de preguntas (no una sola
  llamada monolítica): cada respuesta de JEV se incorpora al estado que alimenta la siguiente
  pregunta.
- El resultado final es una predicción explicada paso a paso (par/impar, bloque, decena, última cifra,
  candidatos, etc.), no una caja negra.
- La cadena de Markov (`MarkovPY.py`) no es el motor principal de esta nueva vía; puede quedar como
  fuente de features auxiliares o como comparación, pero JEV es el "cerebro" que se va a explorar.
- Como todavía no se conoce el contrato real de la API de JEV, se necesita una interfaz/adaptador
  simulado (mock) para poder diseñar y probar el flujo de preguntas sin bloquear el trabajo por falta
  de documentación.

Esto es exploración y arquitectura, no implementación final: el usuario cerrará preguntas exactas, UI
definitiva y comportamiento después.

## 2. Análisis del repositorio actual

| Archivo | Qué hace | Reutilizable | Acoplado a Flet |
|---|---|---|---|
| `flet_app.py` | UI de escritorio/web con Flet: botones que lanzan subprocesos (`scrapy.py`, `main_runner.py`) y muestran stdout en un log. No hay lógica de negocio propia. | Prácticamente nada del código, pero sí la idea (leer últimos N números, borrar último, mostrar log). | Totalmente. Usa `subprocess.Popen` + polling de stdout, controles Flet, threads. Este patrón no aplica a una web JEV. |
| `MarkovPY.py` | Clase `MarkovPredictor`: modela paridad (par/impar) como cadena de Markov de orden `k`, con backoff y 3 métodos de combinación (weighted/conservative/aggressive). Es standalone (`if __name__ == "__main__"` lee el JSON directo). | Alto. La lógica de conteo de rachas y transiciones es reutilizable como feature extractor (no como motor de decisión). | Ninguno. Es puro Python, sin flet. |
| `main_runner.py` | Orquesta `MarkovPY.py` para múltiples órdenes (1–9) reescribiendo el archivo con regex y ejecutándolo por subprocess, parseando el stdout con regex para extraer resultados. | Bajo. El patrón (modificar código fuente + subprocess + regex sobre print) es fragil y no aplica a un backend serio. La intención (barrer varios órdenes y consolidar) sí es reutilizable si se reescribe como función. | Ninguno directo, pero es un antipatrón que no se quiere repetir. |
| `scrapy.py` | Scraper de `loteka.com.do` con reintentos, detección de overlap con últimos 10 números para no duplicar, actualiza `.env` con `LAST_PROCESSED_DATE`. | Alto como fuente de datos, sin cambios. Es independiente de Flet. | Ninguno. |
| `loteka_numbers.json` | ~409.639 números. Hallazgo importante: mezcla tipos — 365.806 son `int` (ej. `32`) y 43.833 son `string` con padding (ej. `"08"`). Esto hay que normalizar antes de construir cualquier estado, porque `32 == "32"` es `False` en la mayoría de comparaciones y el padding se pierde en `int`. | El dato en sí sí, pero necesita una capa de normalización/validación antes de usarse en la web nueva. | Ninguno. |
| `requirements.txt` | `requests`, `beautifulsoup4`, `python-dotenv`, `flet==0.24.1`, `urllib3`, `pytz`. | Se reutiliza `requests`/`dotenv`/`pytz` si el scraper se reutiliza; `flet` no aplica a la nueva web si se elige otro framework. | — |
| `Dockerfile` / `start.sh` | Empaquetan y arrancan `flet_app.py` en el puerto 8080, healthcheck sobre `/`. Verifican existencia de `flet_app.py`, `scrapy.py`, `MarkovPY.py`, `main_runner.py`. | Patrón reutilizable (imagen slim, usuario no-root, healthcheck), pero apunta al proceso Flet, habría que crear un Dockerfile/start.sh propios para el nuevo servicio. | Alto (hardcodea el arranque de Flet). |
| `simulador_loteria.py` | Simulador de apuestas PAR/IMPAR con progresión de apuestas (no mencionado originalmente pero está en el repo). No tiene relación directa con JEV; es un módulo aparte de simulación económica. | Aparte, no interfiere. | Ninguno. |

Sobre "JEV/System One": no existe ninguna mención, cliente, SDK, URL ni credencial de JEV en el
repositorio ni en el historial de commits — la única referencia es el nombre de la rama
`feature/jev-prediction-web`. Se confirma explícitamente: no se conoce el contrato real de esa API y no
se va a inventar.

## 3. Flujo recomendado de la cadena de preguntas a JEV

Idea central: cada etapa es una llamada (o un lote pequeño de llamadas) que recibe el estado acumulado
+ su pregunta específica, y devuelve una respuesta que se fusiona al estado antes de pasar a la etapa
siguiente. Esto da trazabilidad completa: se puede ver exactamente qué sabía JEV en cada paso.

```
[Números crudos]
   → (1) Ingest & Validate            → estado.raw_valid
   → (2) Estado actual de la lista     → estado.current_state
   → (3) Secuencias y rachas           → estado.streaks
   → (4) Comparación de ventanas       → estado.window_comparison
   → (5) Frecuencias                   → estado.frequencies
   → (6) Transiciones                  → estado.transitions
   → (7) Paridad                       → estado.parity_signal
   → (8) Rangos (00-24/25-49/50-74/75-99) → estado.range_signal
   → (9) Decenas (00-09..90-99)        → estado.decade_signal
   → (10) Última cifra                 → estado.last_digit_signal
   → (11) Similaridad con anterior     → estado.similarity_signal
   → (12) Detección de contradicciones → estado.conflicts
   → (13) Generación de candidatos     → estado.candidates
   → (14) Combinación de señales       → estado.combined_signal
   → (15) Resultado final de JEV       → estado.final_prediction
```

Notas de diseño de la cadena:

- Etapas 1–6 son analíticas locales, no necesitan llamar a JEV — son cómputo determinístico (Python
  puro) que enriquece el estado antes de empezar a preguntarle a JEV. Esto reduce llamadas y le da a
  JEV contexto ya masticado en vez de números crudos.
- Etapas 7–11 son las preguntas "consultivas" a JEV, una por una o agrupadas (ver sección 8 sobre
  redundancia).
- Etapa 12 (contradicciones) puede ser una función local determinística (comparar respuestas 7–11
  entre sí) antes de gastar otra llamada a JEV, y solo escalarle a JEV si hay conflicto real que
  requiera su criterio.
- Etapas 13–15 son donde JEV consolida: generación de candidatos compatibles con las señales,
  combinación ponderada, y salida final con nivel de confianza (o abstención).
- Cada etapa debe ser idempotente y versionada: si se repite la etapa 7 con el mismo estado, debería
  dar la misma respuesta (mismo contexto = misma pregunta).

## 4. Ejemplo de estado acumulado entre llamadas

```json
{
  "session_id": "uuid-v4",
  "created_at": "2025-01-15T10:00:00Z",
  "input": {
    "raw_numbers": ["32", "47", "61", "08", "89"],
    "source": "manual_paste",
    "count": 5
  },
  "normalized": {
    "numbers": [32, 47, 61, 8, 89],
    "padded": ["32", "47", "61", "08", "89"],
    "invalid_entries": [],
    "validation_notes": "5 valid numbers in range 00-99"
  },
  "stages": {
    "current_state": {
      "last_number": 89,
      "position_in_history": 5
    },
    "streaks": {
      "current_parity_streak": {"state": "Impar", "length": 2},
      "longest_streak_seen": {"state": "Par", "length": 4}
    },
    "window_comparison": {
      "window_10": {"even_pct": 0.4, "odd_pct": 0.6},
      "window_50": {"even_pct": 0.52, "odd_pct": 0.48},
      "divergence": "window_10 skews odd vs window_50"
    },
    "frequencies": {
      "by_number": {"32": 3, "47": 5, "61": 2},
      "by_decade": {"30": 12, "40": 15, "60": 9},
      "hot": [47, 32],
      "cold": [61]
    },
    "transitions": {
      "after_89": {"even_count": 6, "odd_count": 9}
    },
    "parity_signal": {
      "question": "will_next_be_even_or_odd",
      "jev_answer": "odd",
      "confidence": 0.62,
      "reasoning": "..."
    },
    "range_signal": { "question": "block_00_49_or_50_99", "jev_answer": "00-49", "confidence": 0.55 },
    "decade_signal": { "question": "which_decade", "jev_answer": "30-39", "confidence": 0.4 },
    "last_digit_signal": { "question": "last_digit", "jev_answer": "7", "confidence": 0.3 },
    "similarity_signal": { "question": "shares_traits_with_previous", "jev_answer": false },
    "conflicts": [
      {"between": ["parity_signal", "decade_signal"], "type": "soft_conflict", "detail": "odd + 30-39 has only 2 odd numbers in that decade historically"}
    ],
    "candidates": [37, 39, 47],
    "combined_signal": { "weights": {"parity": 0.3, "range": 0.2, "decade": 0.2, "last_digit": 0.15, "similarity": 0.15} },
    "final_prediction": {
      "top_candidates": [37, 47],
      "confidence": 0.41,
      "abstain": false,
      "explanation_chain": ["parity_signal", "range_signal", "decade_signal"]
    }
  },
  "call_log": [
    {"stage": "parity_signal", "prompt_version": "v1", "latency_ms": 320, "raw_response_ref": "s3://.../resp1.json"}
  ]
}
```

Esto es un ejemplo ilustrativo, no el formato final — el usuario decidirá nombres exactos de campos.

## 5. Propuesta de arquitectura (independiente de Flet)

```
jev-web/
├── backend/
│   ├── app.py                     # entrypoint del servidor web (API)
│   ├── data/
│   │   ├── loader.py              # lee/normaliza loteka_numbers.json (o input manual)
│   │   └── validator.py           # valida rango 00-99, tipos, duplicados
│   ├── analysis/                  # cómputo local, SIN llamar a JEV (etapas 1-6, 12)
│   │   ├── state.py               # construye estado base
│   │   ├── streaks.py
│   │   ├── windows.py
│   │   ├── frequencies.py
│   │   ├── transitions.py
│   │   └── conflicts.py
│   ├── jev/
│   │   ├── client.py              # interfaz abstracta JEVClient (ABC)
│   │   ├── mock_client.py         # implementación simulada para desarrollo
│   │   ├── real_client.py         # placeholder, NO implementado hasta tener API real
│   │   ├── questions.py           # catálogo de preguntas + templates
│   │   └── chain.py               # orquesta la cadena, etapa por etapa
│   ├── storage/
│   │   └── predictions_log.py     # guarda cada predicción para comparar con el resultado real
│   └── api/
│       └── routes.py              # endpoints HTTP (subir números, ejecutar cadena, ver historial)
├── frontend/                      # web sencilla: form de carga + vista de resultado paso a paso
├── shared/
│   └── schemas/                   # JSON Schema de estado, preguntas, respuestas
└── legacy_bridge/ (opcional)
    ├── scrapy_adapter.py          # reutiliza scrapy.py sin tocarlo
    └── markov_features.py         # reutiliza MarkovPY.py como proveedor de features, no como decisor
```

Principios clave:

1. Separación en 3 capas independientes: análisis local (determinístico, testeable sin red), cliente
   JEV (adaptador con interfaz fija), interfaz web (solo presenta y dispara).
2. `JEVClient` como interfaz abstracta con un método por etapa consultiva (`ask_parity(state) ->
   Answer`, `ask_range(state) -> Answer`, etc.), para que `mock_client.py` y el futuro `real_client.py`
   sean intercambiables sin tocar el resto del sistema.
3. El mock no debe "hacer trampa" simulando lógica real de predicción — debe devolver respuestas
   estructuradas plausibles (aunque sean aleatorias o basadas en reglas simples) solo para validar el
   pipeline, no para validar la calidad predictiva.
4. El archivo `loteka_numbers.json` no se toca: se lee mediante `data/loader.py`, que hace la
   normalización de tipos (int vs string con padding) como primer paso obligatorio.
5. `scrapy.py` y `MarkovPY.py` se reutilizan por importación, no por subprocess+regex como hoy.

## 6. Posibles tecnologías para la web

Para una primera versión sencilla, sin acoplarse a Flet:

| Opción | Cuándo tiene sentido |
|---|---|
| FastAPI + HTML/HTMX (o Jinja2) mínimo | Recomendado para explorar rápido: backend Python (reutiliza el stack actual), tipado con Pydantic para el estado/schema, fácil de testear cada etapa como función. HTMX da interactividad sin escribir un SPA. |
| Flask + plantilla simple | Si se prefiere algo aún más mínimo y ya conocido, sin async. Menos "batteries" para validación de esquemas que FastAPI+Pydantic. |
| FastAPI (backend) + React/Vue (frontend separado) | Si más adelante se quiere una UI rica (progreso visual etapa por etapa, gráficos de frecuencia). Más esfuerzo inicial. |
| Streamlit | Muy rápido para prototipo interno (subir lista, ver resultado), pero mezcla presentación y lógica más de lo ideal para algo que después va a crecer; menos control fino de la cadena de preguntas paso a paso. |

Recomendación para la primera versión exploratoria: FastAPI + Pydantic (para los esquemas de
estado/pregunta/respuesta) + HTML simple. Da tipado fuerte del estado (importante porque la cadena
depende de la forma exacta del JSON), separación limpia backend/frontend, y no hereda nada de Flet.

## 7. Preguntas recomendadas, ordenadas por etapas

**Etapa A — Señales atómicas (una pregunta = una dimensión):**
1. ¿El siguiente número será par o impar?
2. ¿Estará entre 00–49 o 50–99?
3. ¿En qué bloque de 25 estará? (00-24 / 25-49 / 50-74 / 75-99)
4. ¿En qué decena estará?
5. ¿Cuál será su última cifra?

**Etapa B — Señales derivadas/condicionales:**
6. ¿Continuará o romperá la racha actual (de paridad, de decena, de bloque)?
7. ¿Cambiará de decena respecto al número anterior?
8. ¿Cambiará de bloque respecto al número anterior?
9. ¿Se repetirá el número anterior exactamente?
10. ¿Compartirá alguna característica con el número anterior? (paridad, decena, terminación)

**Etapa C — Meta-análisis (sobre las respuestas anteriores, no sobre los números crudos):**
11. ¿Qué candidatos concretos son compatibles con el conjunto de señales dadas?
12. ¿Las señales combinadas son fuertes, débiles o contradictorias?
13. ¿JEV debería abstenerse de predecir (baja confianza / señales contradictorias)?

Preguntas que se dejarían fuera de la cadena, salvo que se pidan explícitamente:
- "¿Múltiplo de 5 o termina en 5?" y "¿Múltiplo de 10?" — ver punto 8, son subconjuntos de la última
  cifra.

## 8. Preguntas redundantes o que deberían combinarse

Esto es matemáticamente importante para no gastar llamadas ni confundir a JEV con preguntas que ya se
derivan de otras:

- "¿Múltiplo de 10?" es un caso particular de "última cifra = 0". No hace falta preguntarlo aparte: se
  deriva 100% de la respuesta a "última cifra".
- "¿Múltiplo de 5 o termina en 5?" también se deriva de "última cifra" (última cifra ∈ {0, 5}). Es
  redundante como pregunta separada a JEV; se calcula localmente a partir de la respuesta de última
  cifra.
- "¿Par o impar?" y "última cifra" están correlacionadas pero no son 100% redundantes para JEV como
  modelo consultivo: la paridad depende solo de si la última cifra es par, así que en rigor si ya se
  preguntó última cifra, la paridad se deriva localmente sin nueva llamada. Si se prefiere preguntarlas
  en el orden inverso (paridad primero, como filtro grueso, y última cifra después como refinamiento
  dentro de esa paridad), entonces sí tiene sentido mantenerlas como dos etapas separadas — pero nunca
  las dos como preguntas independientes sin relación jerárquica.
- "¿Bloque de 25?" y "¿00-49 o 50-99?" no son independientes: el bloque de 25 ya determina la mitad
  (00-24 y 25-49 → 00-49; 50-74 y 75-99 → 50-99). Preguntar "¿bloque de 25?" primero y derivar la mitad
  localmente evita una llamada.
- "¿Decena?" y "¿bloque de 25?" tampoco son independientes: la decena determina el bloque de 25 (ej.
  decena 30-39 → bloque 25-49). Conviene preguntar la señal más fina (decena) y derivar la más gruesa
  (bloque) localmente, o viceversa si se prefiere ir de grueso a fino — pero no ambas como preguntas
  separadas a JEV.
- "¿Cambiará de decena?" y "¿cambiará de bloque?" son parcialmente redundantes: si cambia de decena
  dentro del mismo bloque de 25, cambia de decena pero no de bloque. Son preguntas distintas pero con
  dependencia lógica (cambiar de bloque implica cambiar de decena, no al revés). Podrían combinarse en
  una sola etapa que responda "nivel de cambio: mismo bloque / mismo bloque distinta decena / distinto
  bloque".
- Combinación sugerida en una sola etapa a JEV: preguntas 3+4+5 (bloque, decena, última cifra) podrían
  resolverse en una sola llamada estructurada que pida un objeto `{block, decade, last_digit}` en vez
  de 3 llamadas separadas, ya que son jerárquicamente anidadas (decena implica bloque, última cifra
  completa el número exacto dentro de la decena). Esto reduce latencia y costo, y evita que JEV dé
  respuestas inconsistentes entre sí (ej. decena 30-39 pero bloque 50-74).

## 9. Riesgos técnicos y estadísticos

**Técnicos:**
- Datos mixtos en `loteka_numbers.json` (int vs string con padding) — si no se normaliza antes de
  construir el estado, van a existir bugs silenciosos (ej. comparar `8 == "08"` da `False`).
- Dependencia de una API externa no documentada (JEV): sin conocer límites de rate, formato de error,
  autenticación, timeouts — cualquier cliente real debe construirse con reintentos, timeouts
  explícitos y manejo de fallos parciales de la cadena (si la etapa 9 falla, ¿se continúa con lo que
  hay o se aborta?).
- Estado que crece etapa a etapa: si no se acota, el payload que viaja a JEV en la etapa 15 puede
  volverse grande; conviene decidir qué "resumen" del estado se manda en cada etapa vs. qué se guarda
  solo localmente.
- Trazabilidad y reproducibilidad: si JEV no es determinístico, la misma cadena puede dar resultados
  distintos en dos corridas; hay que decidir si se fija una semilla/versión de prompt y se loguea.

**Estadísticos / de dominio:**
- Una lotería de números 00-99 con extracción aleatoria uniforme no tiene, en teoría, dependencia real
  entre extracciones (si el sorteo es justo). Cualquier "racha", "sesgo de decena" o "transición" que
  se detecte en el histórico es, salvo evidencia fuerte de sesgo físico del sorteo, ruido estadístico.
  Esto no invalida el ejercicio de explorar JEV como motor de razonamiento estructurado, pero es
  importante que la interfaz no comunique falsas garantías de "predicción" — mostrar confianza
  calibrada y permitir abstención (pregunta 13) es la forma correcta de manejarlo.
- Contradicción entre señales (etapa 12) es esperable y frecuente precisamente porque el proceso
  subyacente es aleatorio; el diseño de "detectar contradicciones" es bueno, pero no hay que esperar
  que se resuelvan de forma consistente entre corridas.
- Sobreajuste narrativo: con 15 etapas y explicaciones encadenadas, es fácil que el sistema "suene" muy
  convincente sin que la predicción sea mejor que el azar. Vale la pena, en algún momento, medir el
  desempeño real contra el número siguiente (por eso la pregunta de cómo guardar predicciones para
  comparar después — buena decisión).

## 10. Plan de implementación por fases

**Fase 0 — Preparación (sin tocar el repo actual):**
- Confirmar decisiones abiertas (sección 11).
- Definir el schema JSON del estado y de pregunta/respuesta (JSON Schema o Pydantic models).

**Fase 1 — Núcleo de análisis local (sin JEV):**
- Normalizador/validador de `loteka_numbers.json` (maneja int/string mixto).
- Módulos de etapas 1–6 y 12 (estado, rachas, ventanas, frecuencias, transiciones, contradicciones)
  como funciones puras, testeadas con datos reales del JSON.

**Fase 2 — Cliente JEV simulado + orquestador de cadena:**
- `JEVClient` abstracto + `MockJEVClient`.
- `chain.py` que recorre las etapas 7–15, pasando estado acumulado.
- Logging de cada llamada (`call_log`).

**Fase 3 — API + web mínima:**
- Endpoint para cargar/pegar números.
- Endpoint para ejecutar la cadena completa (o etapa por etapa, para debug).
- Vista simple que muestre el estado final y el camino de decisión (qué respondió cada etapa).

**Fase 4 — Persistencia de predicciones para comparación posterior:**
- Guardar cada predicción final junto con snapshot del estado, timestamp, y (más adelante) el número
  real cuando salga, para poder medir aciertos.

**Fase 5 — Integración real con JEV (bloqueada hasta tener documentación/credenciales):**
- Reemplazar `MockJEVClient` por `RealJEVClient` una vez se tenga el contrato de API real. No se hace
  antes.

**Fase 6 (opcional) — Reincorporar `MarkovPY.py` como feature adicional**, si se quiere
comparar/enriquecer el estado con sus probabilidades, sin que sea el motor de decisión.

## 11. Dudas o decisiones que deberían definirse más adelante

1. ¿JEV es una API HTTP externa, un modelo local, o algo tipo "System One" (razonamiento
   simbólico/reglas) que corre en el propio proceso? Esto cambia completamente el diseño del
   `client.py`.
2. ¿Cada etapa consultiva es una llamada de red separada o se prefiere agrupar varias preguntas en un
   solo prompt/payload (como se sugiere en el punto 8)? Afecta latencia, costo y consistencia.
3. ¿Qué pasa si una etapa intermedia falla o da timeout? ¿Aborta toda la cadena, sigue con valores por
   defecto, o reintenta?
4. ¿El estado se persiste completo en cada sesión (para auditoría) o solo se guarda el resumen final +
   la predicción?
5. ¿Se va a querer comparar contra `MarkovPY.py` en paralelo desde el día 1, o eso queda totalmente
   pospuesto?
6. ¿La carga de números será manual (pegar lista), por archivo, o reutilizando directamente
   `loteka_numbers.json` vía el scraper existente?
7. ¿Qué nivel de confianza mínimo debería disparar la abstención (pregunta 13)? ¿Lo define JEV o una
   regla sobre sus respuestas?
8. ¿Se necesita autenticación/usuarios en esta web, o es de uso personal/local por ahora?

---

No se tocó ningún archivo funcional del repo aparte de este documento. Cuando se quiera avanzar a
implementación, se recomienda empezar por la Fase 1, porque es la que ya se puede construir y testear
hoy sin depender de JEV.
