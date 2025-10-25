#!c:/Users/LMiguelGJ/Desktop/LotePy/.venv/Scripts/python.exe
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime, timedelta
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def scrape_loteka(fecha):
    # Configure retry strategy
    retry_strategy = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LotekaScraper/1.0"
    })
    
    fecha_codificada = quote(fecha)
    url = f'https://loteka.com.do/wp-content/themes/loteka/getChanceExpress.php?fechaSeleccionada={fecha_codificada}'
    
    try:
        # Add timeout parameter (12 seconds)
        response = session.get(url, timeout=12)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {fecha}: {str(e)}")
        return []
    
    # Analizar el contenido HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Encontrar todos los elementos <li>
    li_elements = soup.find_all('li')
    
    # Lista para almacenar los primeros números
    numbers = []
    
    # Iterar sobre cada <li> y obtener solo el primer <span class="numero">
    for li in li_elements:
        first_number_span = li.find('span', class_='numero')
        if first_number_span:
            numbers.append(first_number_span.text.strip())
    
    # Invertir la lista de números
    numbers.reverse()
    return numbers

# Fecha inicial en formato DD/MM/YYYY
# fecha = '05/03/2025'

def get_existing_numbers():
    try:
        with open('loteka_numbers.json', 'r') as f:
            existing_numbers = json.load(f)
            # Get the last 10 numbers as reference (from the end of the list)
            return existing_numbers if len(existing_numbers) < 10 else existing_numbers[-10:]
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def main():
    # Get existing numbers
    reference_numbers = get_existing_numbers()
    all_existing_numbers = []

    try:
        with open('loteka_numbers.json', 'r') as f:
            all_existing_numbers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_existing_numbers = []

    # Get the last processed date from .env or use default
    last_date = os.getenv('LAST_PROCESSED_DATE', '15/10/2019')
    fecha = last_date
    print(f"Iniciando desde {last_date}")

    # Convertir la fecha inicial a objeto datetime
    fecha_actual = datetime.strptime(fecha, '%d/%m/%Y')
    fecha_hoy = datetime.now()

    # Lista para almacenar los nuevos resultados
    nuevos_resultados = []

    # Bucle mientras la fecha sea menor a hoy
    while fecha_actual <= fecha_hoy:
        fecha_formateada = fecha_actual.strftime('%d/%m/%Y')
        print(f"\nResultados para {fecha_formateada}:")
        resultados = scrape_loteka(fecha_formateada)
        if resultados:
            print("Numeros:", ", ".join(resultados))
        else:
            print("Sin numeros encontrados")
        
        # Check if we found our reference numbers (checking from the end)
        found_overlap = False
        for i in range(len(resultados)):
            if resultados[i:i+len(reference_numbers)] == reference_numbers:
                # We found the overlap point, add only numbers that come after
                nuevos_resultados.extend(resultados[i+len(reference_numbers):])
                found_overlap = True
                break
        
        if not found_overlap:
            # No overlap found, add all numbers
            nuevos_resultados.extend(resultados)
        
        fecha_actual += timedelta(days=1)

    # Combine existing numbers with new ones
    todos_resultados = all_existing_numbers + nuevos_resultados

    # Update the last processed date in .env
    with open('.env', 'w') as env_file:
        env_file.write(f'LAST_PROCESSED_DATE={fecha_hoy.strftime("%d/%m/%Y")}')

    # Guardar resultados en archivo JSON
    with open('loteka_numbers.json', 'w') as f:
        json.dump(todos_resultados, f, indent=4)

    print(f"\nResultados guardados. {len(nuevos_resultados)} nuevos numeros agregado.")
    return nuevos_resultados

if __name__ == "__main__":
    main()
