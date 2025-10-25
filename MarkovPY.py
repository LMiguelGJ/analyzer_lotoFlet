#!c:/Users/LMiguelGJ/Desktop/LotePy/.venv/Scripts/python.exe
from collections import deque, defaultdict
import json

class MarkovPredictor:
    def __init__(self, order=1):
        self.order = order  # Longitud del patrón consecutivo (1, 2, 3, 6, etc.)
        self.history = deque(maxlen=order)  # Últimas 'order' paridades
        self.counts_runs = {'Par': 0, 'Impar': 0}  # Conteo de patrones consecutivos (solo longitud 'order')
        # Transiciones por clave exacta de longitud k (1..order): clave -> siguiente estado
        self.transitions_by_key = {k: defaultdict(lambda: {'Par': 0, 'Impar': 0}) for k in range(1, order + 1)}
        # Qué viene después de un patrón consecutivo de longitud order
        self.after_runs = {
            'Par': {'Par': 0, 'Impar': 0},
            'Impar': {'Par': 0, 'Impar': 0}
        }

    def _state(self, number):
        return 'Par' if number % 2 == 0 else 'Impar'

    def update(self, number):
        """Agrega un nuevo número, contabiliza transiciones por clave y patrones consecutivos."""
        current_state = self._state(number)

        # 1) Contar transiciones desde la clave previa hacia el estado actual
        #    Para cada k, la clave es el último k estados ANTES de agregar el actual
        for k in range(1, self.order + 1):
            if len(self.history) >= k:
                key = tuple(list(self.history)[-k:])
                self.transitions_by_key[k][key][current_state] += 1

        # Detectar si la ventana anterior tenía order estados iguales (antes de agregar current_state)
        if len(self.history) == self.order and all(s == self.history[0] for s in self.history):
            run_state = self.history[0]
            self.after_runs[run_state][current_state] += 1

        # 2) Agregar el estado actual a la ventana
        self.history.append(current_state)

        # 3) Si la ventana completa (order) es un patrón consecutivo, contar aparición
        if len(self.history) == self.order and all(s == self.history[0] for s in self.history):
            run_state = self.history[0]
            self.counts_runs[run_state] += 1

    def predict_global(self):
        """Predice globalmente usando la frecuencia de patrones consecutivos de longitud 'order'."""
        total = sum(self.counts_runs.values())
        if total == 0:
            probs = {'Par': 0.5, 'Impar': 0.5}
        else:
            probs = {state: self.counts_runs[state] / total for state in ['Par', 'Impar']}
        predicted_state = max(probs, key=probs.get)
        return predicted_state, probs

    def predict_with_context(self):
        """Predice siempre con contexto usando back-off de clave exacta de longitud k (order..1)."""
        # Tomar las últimas k paridades como clave y buscar transiciones registradas
        hist_list = list(self.history)
        for k in range(self.order, 0, -1):
            if len(hist_list) >= k:
                key = tuple(hist_list[-k:])
                counts = self.transitions_by_key[k].get(key)
                if counts:
                    total = counts['Par'] + counts['Impar']
                    if total > 0:
                        probs = {
                            'Par': counts['Par'] / total,
                            'Impar': counts['Impar'] / total
                        }
                        predicted_state = max(probs, key=probs.get)
                        return k, key, predicted_state, probs
        # Si no hay contexto con datos, caer a la global
        pred_global, probs_global = self.predict_global()
        return 0, tuple(), pred_global, probs_global

    def predict_combined(self, method='weighted', weight_context=0.7):
        """
        Combina la predicción global y la de contexto para una decisión más asertiva.
        
        Métodos disponibles:
        - 'weighted': Promedio ponderado (weight_context = peso del contexto)
        - 'conservative': Toma la predicción con mayor confianza
        - 'aggressive': Toma la predicción que maximice la probabilidad mínima
        """
        pred_global, probs_global = self.predict_global()
        k_used, key_used, pred_ctx, probs_ctx = self.predict_with_context()
        
        if method == 'weighted':
            # Promedio ponderado de las probabilidades
            combined_probs = {
                'Par': weight_context * probs_ctx['Par'] + (1 - weight_context) * probs_global['Par'],
                'Impar': weight_context * probs_ctx['Impar'] + (1 - weight_context) * probs_global['Impar']
            }
            predicted_state = max(combined_probs, key=combined_probs.get)
            return predicted_state, combined_probs, 'ponderada'
            
        elif method == 'conservative':
            # Toma la predicción con mayor confianza (máxima probabilidad)
            max_global = max(probs_global.values())
            max_context = max(probs_ctx.values())
            
            if max_context >= max_global:
                return pred_ctx, probs_ctx, 'contexto (mayor confianza)'
            else:
                return pred_global, probs_global, 'global (mayor confianza)'
                
        elif method == 'aggressive':
            # Toma la predicción que maximice la probabilidad mínima (más segura)
            min_global = min(probs_global.values())
            min_context = min(probs_ctx.values())
            
            if min_context >= min_global:
                return pred_ctx, probs_ctx, 'contexto (más segura)'
            else:
                return pred_global, probs_global, 'global (más segura)'
        
        else:
            # Por defecto, usa el contexto si está disponible
            if k_used > 0:
                return pred_ctx, probs_ctx, 'contexto (por defecto)'
            else:
                return pred_global, probs_global, 'global (por defecto)'

# ------------------------------
# Ejemplo de uso
# ------------------------------
if __name__ == "__main__":
    # Variable para limitar cuántos números hacia atrás considerar
    NUMEROS_A_ANALIZAR = 0
    NUMERO_ORDER = 3
    
    with open("loteka_numbers.json", "r", encoding="utf-8") as f:
        raw = json.load(f)
    historial = []
    for x in raw:
        try:
            historial.append(int(x))
        except (ValueError, TypeError):
            pass
    
    # Limitar el historial a los últimos N números si se especifica
    if NUMEROS_A_ANALIZAR > 0 and len(historial) > NUMEROS_A_ANALIZAR:
        historial = historial[-NUMEROS_A_ANALIZAR:]
        print(f"Analizando los últimos {NUMEROS_A_ANALIZAR} números del historial")
    else:
        print(f"Analizando todos los {len(historial)} números del historial")
    
    predictor = MarkovPredictor(order=NUMERO_ORDER)

    # Inicializamos el modelo con el historial
    for numero in historial:
        predictor.update(numero)
    
    # Mostrar información sobre el rango analizado
    print(f"\n=== INFORMACIÓN DEL ANÁLISIS ===")
    if NUMEROS_A_ANALIZAR > 0 and len(historial) > 0:
        print(f"Rango: Desde el número {len(raw) - len(historial) + 1} hasta el {len(raw)}")
    
    print(f"Últimos {NUMERO_ORDER} números analizados: {historial[-NUMERO_ORDER:]}")

    # Mostrar la última ventana del deque (contexto actual)
    last_window = list(predictor.history)
    if len(last_window) == predictor.order and all(s == last_window[0] for s in last_window):
        print(f"Contexto actual es patrón consecutivo: {' '.join(last_window)}")
    else:
        print(f"Contexto actual NO es patrón consecutivo de longitud {predictor.order}")

    # Predicción global y predicción con contexto + back-off
    pred_global, probs_global = predictor.predict_global()
    k_used, key_used, pred_ctx, probs_ctx = predictor.predict_with_context()
    
    # === SALIDA MEJORADA Y MÁS DESCRIPTIVA ===
    print(f"\n{'='*60}")
    print(f"📊 ANÁLISIS MARKOV - ORDEN {predictor.order}")
    print(f"{'='*60}")
    
    # Contexto actual
    last_window = list(predictor.history)
    context_str = ' '.join(last_window) if last_window else "Sin contexto"
    print(f"🎯 Contexto Actual: {context_str}")
    
    # Estadísticas de patrones
    print(f"\n📈 PATRONES ENCONTRADOS:")
    pattern_par = 'Par' * predictor.order
    pattern_impar = 'Impar' * predictor.order
    print(f"   • {pattern_par}: {predictor.counts_runs['Par']} veces")
    print(f"   • {pattern_impar}: {predictor.counts_runs['Impar']} veces")
    
    # Predicciones individuales
    print(f"\n🔮 PREDICCIONES INDIVIDUALES:")
    print(f"   📋 Global: {pred_global} (Par: {probs_global['Par']:.1%}, Impar: {probs_global['Impar']:.1%})")
    if k_used > 0:
        print(f"   📋 Contexto: {pred_ctx} (Par: {probs_ctx['Par']:.1%}, Impar: {probs_ctx['Impar']:.1%})")
    else:
        print(f"   📋 Contexto: Usando predicción global (sin datos de contexto)")
    
    # Predicciones combinadas
    print(f"\n🎲 PREDICCIONES COMBINADAS:")
    pred_weighted, probs_weighted, _ = predictor.predict_combined('weighted', 0.7)
    pred_conservative, probs_conservative, _ = predictor.predict_combined('conservative')
    pred_aggressive, probs_aggressive, _ = predictor.predict_combined('aggressive')
    
    print(f"   ⚖️  Ponderada (70% contexto): {pred_weighted} (Par: {probs_weighted['Par']:.1%}, Impar: {probs_weighted['Impar']:.1%})")
    print(f"   🛡️  Conservadora: {pred_conservative} (Par: {probs_conservative['Par']:.1%}, Impar: {probs_conservative['Impar']:.1%})")
    print(f"   ⚡ Agresiva: {pred_aggressive} (Par: {probs_aggressive['Par']:.1%}, Impar: {probs_aggressive['Impar']:.1%})")
    
    # Recomendación final
    predictions = [pred_weighted, pred_conservative, pred_aggressive]
    par_count = predictions.count('Par')
    impar_count = predictions.count('Impar')
    
    print(f"\n{'='*60}")
    print(f"🏆 RECOMENDACIONES FINALES")
    print(f"{'='*60}")
    print(f"📊 CONSENSO DE MÉTODOS:")
    print(f"   • Par: {par_count}/3 métodos")
    print(f"   • Impar: {impar_count}/3 métodos")
    
    print(f"\n🎯 RECOMENDACIONES:")
    print(f"   🌍 Global: {pred_global}")
    print(f"   🔍 Contexto: {pred_ctx}")
    
    if par_count > impar_count:
        print(f"   🏆 Combinada: PAR (consenso {par_count}/3)")
    elif impar_count > par_count:
        print(f"   🏆 Combinada: IMPAR (consenso {impar_count}/3)")
    else:
        # Empate - usar promedio de probabilidades
        avg_par = (probs_weighted['Par'] + probs_conservative['Par'] + probs_aggressive['Par']) / 3
        avg_impar = (probs_weighted['Impar'] + probs_conservative['Impar'] + probs_aggressive['Impar']) / 3
        if avg_par > avg_impar:
            print(f"   🏆 Combinada: PAR (desempate por probabilidad: {avg_par:.1%})")
        else:
            print(f"   🏆 Combinada: IMPAR (desempate por probabilidad: {avg_impar:.1%})")
    
    print(f"{'='*60}")

