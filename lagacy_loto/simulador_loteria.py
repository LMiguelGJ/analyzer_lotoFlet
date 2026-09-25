#!/usr/bin/env python3
"""
Simulador de Juego de Lotería
Basado en las reglas especificadas con apuestas PAR/IMPAR y progresión de apuestas
"""

# Tabla de progresión de apuestas
PROGRESION_APUESTAS = {
    1: {"apuesta_por_numero": 1, "apuesta_total": 50},
    2: {"apuesta_por_numero": 3, "apuesta_total": 150},
    3: {"apuesta_por_numero": 10, "apuesta_total": 500},
    4: {"apuesta_por_numero": 35, "apuesta_total": 1750},
    5: {"apuesta_por_numero": 123, "apuesta_total": 6150},
    6: {"apuesta_por_numero": 430, "apuesta_total": 21500},
    7: {"apuesta_por_numero": 1505, "apuesta_total": 75250},
    8: {"apuesta_por_numero": 5268, "apuesta_total": 263400},
    9: {"apuesta_por_numero": 18438, "apuesta_total": 921900},
    10: {"apuesta_por_numero": 64533, "apuesta_total": 3226650}
}

# Constantes del juego
PAGO_PRIMERA_CHANCE = 70  # pesos por cada peso apostado
NUMEROS_PARES = list(range(0, 100, 2))  # [0, 2, 4, ..., 98]
NUMEROS_IMPARES = list(range(1, 100, 2))  # [1, 3, 5, ..., 99]


def obtener_eleccion_sorteo():
    """Pregunta al usuario si quiere jugar PAR o IMPAR en cada sorteo"""
    while True:
        print("\n¿Quieres jugar PAR o IMPAR?")
        print("Presiona 1 para IMPAR")
        print("Presiona 2 para PAR")
        
        try:
            opcion = int(input("Tu elección (1 o 2): ").strip())
            if opcion == 1:
                return "IMPAR"
            elif opcion == 2:
                return "PAR"
            else:
                print("Por favor, presiona 1 o 2")
        except ValueError:
            print("Por favor, ingresa un número válido (1 o 2)")


def obtener_capital_inicial():
    """Pregunta al usuario su capital inicial"""
    while True:
        try:
            capital = int(input("¿Cuál es tu capital inicial? "))
            if capital > 0:
                return capital
            print("El capital debe ser mayor que 0")
        except ValueError:
            print("Por favor, ingresa un número válido")


def obtener_numeros_ganadores():
    """Recibe la lista de números ganadores del usuario"""
    print("\nIngresa los números ganadores de cada sorteo (00-99).")
    print("Separa los números con espacios o comas. Ejemplo: 12 45 67 89")
    
    while True:
        entrada = input("Números ganadores: ").strip()
        try:
            # Reemplazar comas por espacios y separar
            numeros_str = entrada.replace(',', ' ').split()
            numeros = []
            
            for num_str in numeros_str:
                num = int(num_str)
                if 0 <= num <= 99:
                    numeros.append(num)
                else:
                    print(f"El número {num} está fuera del rango 00-99")
                    continue
            
            if len(numeros) > 0:
                return numeros
            else:
                print("Debes ingresar al menos un número válido")
                
        except ValueError:
            print("Por favor, ingresa números válidos separados por espacios o comas")


def determinar_ganador(numero_sorteo, eleccion_usuario):
    """
    Determina si el usuario ganó o perdió
    Retorna True si ganó, False si perdió
    """
    es_par = numero_sorteo % 2 == 0
    
    if eleccion_usuario == 'PAR':
        return es_par
    else:  # IMPAR
        return not es_par


def calcular_pago(apuesta_por_numero, ronda):
    """Calcula el pago si se gana"""
    return PAGO_PRIMERA_CHANCE * apuesta_por_numero


def simular_ronda(numero_sorteo, eleccion_usuario, ronda_actual, capital, total_invertido):
    """
    Simula una ronda del juego
    Retorna: (gano, nuevo_capital, nuevo_total_invertido, pago)
    """
    # Obtener datos de la apuesta según la ronda
    datos_apuesta = PROGRESION_APUESTAS[ronda_actual]
    apuesta_total = datos_apuesta["apuesta_total"]
    apuesta_por_numero = datos_apuesta["apuesta_por_numero"]
    
    # Verificar si hay suficiente capital
    if capital < apuesta_total:
        return False, capital, total_invertido, 0, "Bancarrota"
    
    # Realizar la apuesta
    capital -= apuesta_total
    total_invertido += apuesta_total
    
    # Determinar si ganó o perdió
    gano = determinar_ganador(numero_sorteo, eleccion_usuario)
    
    if gano:
        pago = calcular_pago(apuesta_por_numero, ronda_actual)
        capital += pago
        ganancia_neta = pago - total_invertido
        return True, capital, 0, pago, ganancia_neta  # Reiniciar total_invertido al ganar
    else:
        return False, capital, total_invertido, 0, -apuesta_total


def mostrar_resultado_ronda(ronda, numero_sorteo, eleccion, apuesta, resultado, 
                           pago, ganancia_neta, capital, volver_ronda1=False):
    """Muestra el resultado de la ronda formateado"""
    print(f"\n=== Ronda {ronda} ===")
    print(f"Número sorteado: {numero_sorteo:02d}")
    print(f"Apuesta: {apuesta}")
    print(f"Elección: {eleccion}")
    print(f"Resultado: {'GANASTE' if resultado else 'PERDISTE'}")
    
    if resultado:
        print(f"Pago recibido: {pago}")
        print(f"Ganancia neta: {'+' if ganancia_neta >= 0 else ''}{ganancia_neta}")
    else:
        print(f"Pérdida: {abs(ganancia_neta)}")
    
    print(f"Capital actual: {capital}")
    
    if volver_ronda1:
        print("Volviendo a ronda 1...")


def jugar_loteria():
    """Función principal del juego"""
    print("=== SIMULADOR DE LOTERÍA ===\n")
    
    # Obtener datos iniciales del usuario
    capital_inicial = obtener_capital_inicial()
    numeros_ganadores = obtener_numeros_ganadores()
    
    print(f"\nCapital inicial: {capital_inicial}")
    print(f"Números ganadores: {[f'{num:02d}' for num in numeros_ganadores]}")
    print(f"Número de sorteos: {len(numeros_ganadores)}")
    
    # Iniciar el juego
    capital = capital_inicial
    ronda_actual = 1
    total_invertido = 0
    sorteo_actual = 0
    
    print("\n--- INICIANDO SIMULACIÓN ---")
    
    while sorteo_actual < len(numeros_ganadores) and capital > 0:
        numero_sorteo = numeros_ganadores[sorteo_actual]
        
        # Preguntar al usuario su elección para este sorteo
        print(f"\n--- Sorteo {sorteo_actual + 1} ---")
        eleccion = obtener_eleccion_sorteo()
        
        # Simular la ronda
        gano, nuevo_capital, nuevo_total_invertido, pago, ganancia_neta = simular_ronda(
            numero_sorteo, eleccion, ronda_actual, capital, total_invertido
        )
        
        # Actualizar estado
        capital = nuevo_capital
        total_invertido = nuevo_total_invertido
        
        # Mostrar resultado
        if capital < 0:
            mostrar_resultado_ronda(ronda_actual, numero_sorteo, eleccion, 
                                   PROGRESION_APUESTAS[ronda_actual]["apuesta_total"], 
                                   False, 0, ganancia_neta, 0)
            print("\n=== BANCARROTA ===")
            print("Te has quedado sin fondos.")
            break
        
        mostrar_resultado_ronda(ronda_actual, numero_sorteo, eleccion, 
                               PROGRESION_APUESTAS[ronda_actual]["apuesta_total"], 
                               gano, pago, ganancia_neta, capital, gano)
        
        # Actualizar ronda para el próximo sorteo
        if gano:
            ronda_actual = 1  # Volver a ronda 1 al ganar
        else:
            ronda_actual += 1  # Avanzar a la siguiente ronda
            if ronda_actual > 10:
                print("\n=== LÍMITE DE RONDAS ALCANZADO ===")
                print("Has alcanzado la ronda máxima (10).")
                break
        
        sorteo_actual += 1
        
        # Pequeña pausa para mejor legibilidad
        if sorteo_actual < len(numeros_ganadores):
            input("\nPresiona Enter para continuar con el siguiente sorteo...")
    
    # Resumen final
    print(f"\n=== RESUMEN FINAL ===")
    print(f"Sorteos jugados: {sorteo_actual}")
    print(f"Capital inicial: {capital_inicial}")
    print(f"Capital final: {capital}")
    print(f"Ganancia/Pérdida total: {'+' if capital - capital_inicial >= 0 else ''}{capital - capital_inicial}")


if __name__ == "__main__":
    jugar_loteria()