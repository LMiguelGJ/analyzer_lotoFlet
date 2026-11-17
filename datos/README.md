# datos/

Históricos de sorteos en JSON (fuente de datos del proyecto):
- `chance_express_history.json`: Chance Express (Loteka). **La webapp lo necesita** y verifica su SHA-256 al iniciar; no lo modifiques a mano.
- `leidsa_quiniela_history.json`: Quiniela Leidsa. Lo genera `download_leidsa_quiniela.py`.
- `loteka_numbers.json`: números de Loteka. Lo usa `predictor_v2/`.

Se actualizan con `download_chance_express.py` y `download_leidsa_quiniela.py` (en la raíz).
