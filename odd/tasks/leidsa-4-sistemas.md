# Cuatro sistemas nuevos para Leidsa

Agregar Transición, Ciclo vencido, Terminaciones y decenas y Ensamble a la lista Quiniela Leidsa, y probarlos
con todos los sorteos disponibles (2010-07-19 → hoy).

## Specs

- S1 — "vamos crea un plan completo vamos para agregar estas 4 estrategias nuevas": Transición (qué número suele salir al día siguiente del de ayer), Ciclo vencido (el que superó su tiempo promedio sin salir), Terminaciones y decenas (los números cuya unidad y decena salen más), Ensamble (combina los sistemas de Leidsa en un solo ranking).
- S2 — "haz prueabas al final con todos los años de leisa con ellos desde el 2010 hasta ahora": correr los 9 sistemas sobre 2010-07-19 → hoy, año por año, y confirmar fuera de muestra.
- S3 — Loteka Chance Express no cambia: mismos sistemas, mismas etiquetas y mismos resultados.

## Tasks

- T1 — S3: `engine/causal_rankings.py` con las 4 familias nuevas (causales, fila 0 = orden TIE), `FAMILIES` intacto. Commit: pending.
- T2 — S1, S3: `domain/number_lists.py` (Leidsa con 9 sistemas y etiquetas propias), `run_data.py`, `run_service.py` y las dos APIs de opciones. Commit: pending.
- T3 — S1: frontend — ayuda por lista, etiquetas de los sistemas en la lista lateral y en el panel. Commit: pending.
- T4 — S1, S2: informe `odd/reports/leidsa-4-sistemas.md` con la tabla anual y la prueba fuera de muestra. Commit: ver `git log -- odd/reports`.
- T5 — S2: un laboratorio por sistema nuevo en la app, con todo el rango.

## Log

- L1 — Pedido literal: "vamos crea un plan completo vamos para agregar estas 4 estrategias nuevas dale y haz prueabas al final con todos los años de leisa con ellos desde el 2010 hasta ahora". Plan: `.pi/plans/estrategias-leidsa-4-sistemas.md`.
- L2 — Resultado: 0 de 48 configuraciones gana en 2019–2022 y 2023–2026; Transición muestra +181.032 total pero casi todo viene de 2011, año de datos no verificables (ver `investigacion-estrategias.md` §3).
