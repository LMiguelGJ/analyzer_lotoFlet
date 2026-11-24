# datos/

Históricos de sorteos en JSON (fuente de datos del proyecto):
- `chance_express_history.json`: Chance Express (Loteka). **La webapp lo necesita** y verifica su SHA-256 al iniciar; no lo modifiques a mano.
- `leidsa_quiniela_history.json`: Quiniela Leidsa, de 2010-07-19 en adelante. Lo genera `download_leidsa_quiniela.py`. Desde 2023-01-04 los datos vienen de premios.do (fuente de verdad, con hora de cierre); antes de esa fecha vienen de miresultadoloteria.com (`--backfill`), con la hora inferida del día de la semana (15:50 domingo, 20:50 resto) y validados contra premios.do en las fechas compartidas. Ver `metadata.fuentes`.
- `loteka_numbers.json`: números de Loteka. Lo usa `predictor_v2/`.

Se actualizan con `download_chance_express.py` y `download_leidsa_quiniela.py` (en la raíz).
