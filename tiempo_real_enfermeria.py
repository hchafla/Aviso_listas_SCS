import os
import requests
from bs4 import BeautifulSoup
import json

# Configuración de variables desde los Secrets de GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Código interno del SCS para la categoría de Enfermero/a
CATEGORIA_ENFERMERIA = "1"

# Diccionario que asocia el nombre exacto de la gerencia que devuelve la web con su ID de hilo de Telegram
MAPEO_HILOS = {
    "Dr. Negrín": 2,
    "CHUIMI": 6,
    "Atención Primaria Gran Canaria": 7,
    "Lanzarote": 8,
    "Fuerteventura": 9,
    "Candelaria": 10,
    "La Palma": 11,
    "La Gomera": 12,
    "El Hierro": 13,
    "Atención Primaria Tenerife": 14
}

FILE_ESTADO = "estado_enfermeria.json"

def cargar_estado_anterior():
    if os.path.exists(FILE_ESTADO):
        with open(FILE_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_estado_actual(estado):
    with open(FILE_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=4)

def enviar_telegram(mensaje, thread_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "message_thread_id": thread_id
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Error enviando a Telegram (Hilo {thread_id}): {response.text}")
    except Exception as e:
        print(f"Excepción al enviar a Telegram: {e}")

def raspar_enfermeria():
    url = "https://www3.gobiernodecanarias.org/sanidad/scs/organica/gestion/index.jsp" # URL ficticia de la consulta del SCS
    # Simulamos los datos del formulario necesarios para la petición POST
    payload = {
        "j_idt13:categoriasSOM_input": CATEGORIA_ENFERMERIA,
        "j_idt13:enviar": "Consultar"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    estado_actual = {}
    
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Error al acceder a la web del SCS: Código {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, "html.parser")
        # Asumimos la estructura estándar de la tabla de resultados analizada previamente
        tabla = soup.find("table", {"id": "tablaCortes"}) 
        
        if not tabla:
            print("No se encontró la tabla de cortes en la página.")
            return None
            
        filas = tabla.find_all("tr")[1:] # Saltamos la cabecera
        for fila in filas:
            columnas = fila.find_all("td")
            if len(columnas) >= 3:
                gerencia = columnas[0].text.strip()
                corte_gerencia = columnas[1].text.strip()
                corte_global = columnas[2].text.strip()
                
                estado_actual[gerencia] = {
                    "gerencia": corte_gerencia,
                    "global": corte_global
                }
        return estado_actual
    except Exception as e:
        print(f"Error durante el raspado de datos: {e}")
        return None

def procesar_alertas():
    estado_anterior = cargar_estado_anterior()
    estado_actual = raspar_enfermeria()
    
    if not estado_actual:
        print("Proceso abortado por errores en el raspado.")
        return

    # Si es la primera ejecución del script, guardamos el estado y no enviamos alertas masivas
    if not estado_anterior:
        print("Primer registro de datos de Enfermería completado.")
        guardar_estado_actual(estado_actual)
        return

    for gerencia, datos in estado_actual.items():
        thread_id = MAPEO_HILOS.get(gerencia)
        if not thread_id:
            # Si la web devuelve una gerencia que no tenemos mapeada, saltamos para evitar fallos
            continue
            
        datos_antiguos = estado_anterior.get(gerencia)
        
        if not datos_antiguos:
            # Nueva gerencia detectada que antes no estaba en la tabla
            mensaje = (
                f"🚨 *NUEVA GERENCIA DETECTADA: {gerencia}*\n\n"
                f"📈 *Corte Gerencia:* {datos['gerencia']}\n"
                f"🌍 *Corte Global:* {datos['global']}"
            )
            enviar_telegram(mensaje, thread_id)
        else:
            cambio_gerencia = datos['gerencia'] != datos_antiguos['gerencia']
            cambio_global = datos['global'] != datos_antiguos['global']
            
            if cambio_gerencia or cambio_global:
                mensaje = f"🔄 *¡ACTUALIZACIÓN EN {gerencia.upper()}!*\n\n"
                
                if cambio_gerencia:
                    mensaje += f"📉 *Corte Gerencia:* {datos_antiguos['gerencia']} ➔ `{datos['gerencia']}`\n"
                else:
                    mensaje += f"📉 *Corte Gerencia:* Mantienen `{datos['gerencia']}`\n"
                    
                if cambio_global:
                    mensaje += f"🌍 *Corte Global:* {datos_antiguos['global']} ➔ `{datos['global']}`\n"
                else:
                    mensaje += f"🌍 *Corte Global:* Mantienen `{datos['global']}`\n"
                
                enviar_telegram(mensaje, thread_id)

    guardar_estado_actual(estado_actual)

if __name__ == "__main__":
    procesar_alertas()
