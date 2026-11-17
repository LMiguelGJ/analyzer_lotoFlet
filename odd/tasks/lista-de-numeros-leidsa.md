# Lista de números seleccionable (Loteka / Leidsa)

Permitir elegir en Ajustes con qué lista de sorteos trabaja la app, hacer que los laboratorios corran con la Quiniela Leidsa,
y dejar la pantalla de Ajustes limpia, sin tecnicismos. Loteka Chance Express debe seguir dando resultados idénticos.

## Specs

- S1 — Elegir la lista en Ajustes. Verbatim: "lo unico que ma hace falta es que en config me permita elejir con que lista de numeros voy a trabajar http://127.0.0.1:8765/ajustes" con las listas que producen `download_chance_express.py` y `download_leidsa_quiniela.py` (`datos/chance_express_history.json`, `datos/leidsa_quiniela_history.json`).
- S2 — Ajustes más limpio. Verbatim: "y tambien mejora esa interfaz para que se vea mas limpia sin tanto tecnisismos".
- S3 — Los laboratorios funcionan con Leidsa. Decisión del usuario: "Que los laboratorios funcionen con Leidsa".
- S4 — Premios configurables. Decisión del usuario: "Configurable en Ajustes" — la tabla de premios por posición de Leidsa se edita en Ajustes; valor inicial 60 / 8 / 4.
- S5 — Sistemas disponibles con Leidsa. Decisión del usuario: "Leidsa con los 5 sistemas posibles": Paridad, Fríos, Frecuencia histórica, Frecuencia reciente y Decaimiento. Los demás sistemas se muestran como "No disponible para esta lista". Loteka conserva sus 13 sistemas.
- S6 — Sin regresión en Loteka: mismo historial (SHA-256 fijado), mismo parseo y mismos resultados dorados/paridad de los 14 laboratorios de referencia.

## Tasks

- T1 — S1, S6: catálogo de listas + lista activa persistida (migración 0021) + `GET/PUT` de lista activa; parseo con N posiciones sin cambiar Loteka. Route: worker. Commit: pending.
- T2 — S3, S5, S6: laboratorios y corridas aceptan 3 posiciones; sistemas sin ranking para Leidsa (paridad, fríos, frecuencias, decaimiento); los que requieren ranking quedan bloqueados con mensaje claro; ventana derivada de la lista. Route: worker. Commit: pending.
- T3 — S4: premios por posición editables en Ajustes para la lista activa (defecto Leidsa 60/8/4, Loteka 80/8/4/2/1). Route: worker. Commit: pending.
- T4 — S1, S2, S4: rediseño de `/ajustes`: selector de lista, premios, textos simples; datos técnicos plegados en "Avanzado". Formularios de laboratorio con premios dinámicos. Route: worker. Commit: pending.
- T5 — S1–S6: verificación independiente (backend + frontend + golden) y arranque de la app. Route: verify. Commit: n/a.

## Log

- L1 — Pedido original: "lo unico que ma hace falta es que en config me permita elejir con que lista de numeros voy a trabajar http://127.0.0.1:8765/ajustes "C:/Users/luism/OneDrive/Escritorio/Proyecto Personal/analyzer_lotoFlet/download_chance_express.py" "C:/Users/luism/OneDrive/Escritorio/Proyecto Personal/analyzer_lotoFlet/download_leidsa_quiniela.py"  y tambien mejora esa interfaz para que se vea mas limpia sin tanto tecnisismos"
- L2 — Decisiones: motor genérico ("Que los laboratorios funcionen con Leidsa"); premios "Configurable en Ajustes"; "Leidsa con los 5 sistemas posibles".
- L4 — Entrega: "al final debe pasar todo a la rama master" — al cerrar T5 con todo verificado, merge de feat/lista-leidsa a master (sin push).
- L3 — Evidencia: el motor v1 está fijo en 5 posiciones (`engine/contracts.py:78`, `engine/adapter.py:105,170`, `domain/laboratories.py:104`); 9 de 13 sistemas dependen de `pos1.npz` (rankings de chance_rank, no recalculables con 1.381 sorteos); la capa v2 (`/api/v2/game-profiles`, `/history-sources`) es solo almacenamiento y no se reutiliza como motor. Test `test_v13_database_upgrades_in_place` ya fallaba en HEAD antes de este trabajo.
