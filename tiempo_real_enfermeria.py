import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo  # <- Forzar zona horaria nativa

# Configuración de variables desde los Secrets de GitHub
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
URL_BASE = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/index.xhtml"
URL_CAT = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/categorias.xhtml"

# ID real verificado para ATS/DUE (Enfermero/a)
CATEGORIA_ENFERMERIA = "103"

# Mapeo de gerencias: asocia el código del SCS, el nombre y su hilo de Telegram
GERENCIAS_ENFERMERIA = [
    {"nombre": "Lanzarote", "valor": "22", "thread_id": 8},
    {"nombre": "Fuerteventura", "valor": "23", "thread_id": 9},
    {"nombre": "CHUIMI", "valor": "24", "thread_id": 6},
    {"nombre": "Candelaria", "valor": "25", "thread_id": 10},
    {"nombre": "La Palma", "valor": "26", "thread_id": 47},
    {"nombre": "La Gomera", "valor": "27", "thread_id": 12},
    {"nombre": "El Hierro", "valor": "28", "thread_id": 13},
    {"nombre": "Atención Primaria Tenerife", "valor": "30", "thread_id": 14},
    {"nombre": "Atención Primaria Gran Canaria", "valor": "20", "thread_id": 7},
    {"nombre": "Dr. Negrín", "valor": "21", "thread_id": 2}
]

def enviar_telegram(mensaje, thread_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "message_thread_id": thread_id
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200:
            print(f"Error Telegram (Hilo {thread_id}): {response.text}")
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def extraer_view_state(html):
    soup = BeautifulSoup(html, "html.parser")
    input_vs = soup.find("input", {"name": "javax.faces.ViewState"})
    return input_vs.get("value") if input_vs else None

def procesar_gerencia(session, nombre, valor_gerencia, thread_id):
    fichero_estado = f"estado_enf_{valor_gerencia}.txt"

    try:
        # 1. Petición a la Home y selección de Gerencia
        r_home = session.get(URL_BASE, timeout=15)
        vs_1 = extraer_view_state(r_home.text)
        
        payload_g = {
            "j_idt43": "j_idt43", 
            "j_idt43:gerenciaUNSOM_input": valor_gerencia, 
            "j_idt43:j_idt46": "Seleccionar", 
            "javax.faces.ViewState": vs_1
        }
        r_cat = session.post(URL_BASE, data=payload_g, timeout=15)
        
        # 2. Selección de la Categoría ATS/DUE (103)
        vs_2 = extraer_view_state(r_cat.text)
        payload_c = {
            "j_idt13": "j_idt13", 
            "j_idt13:categoriasSOM_input": CATEGORIA_ENFERMERIA, 
            "j_idt13:j_idt16": "Seleccionar", 
            "javax.faces.ViewState": vs_2
        }
        r_final = session.post(URL_CAT, data=payload_c, timeout=15)
        
        # 3. Procesamiento de la tabla de resultados
        soup = BeautifulSoup(r_final.text, "html.parser")
        filas = [f for f in soup.find_all("tr") if len(f.find_all("td")) >= 3 and any(kw in f.get_text() for kw in ["Corta", "Larga", "Interinidad"])]
        
        print(f"[{nombre}] Filas válidas detectadas en la tabla: {len(filas)}")
        
        if len(filas) == 0:
            return

        datos_actuales = ""
        lineas_ord, lineas_disc = [], []
        
        estado_ant = ""
        if os.path.exists(fichero_estado):
            with open(fichero_estado, "r") as f: 
                estado_ant = f.read().strip()

        for fila in filas:
            celdas = [c.get_text(strip=True) for c in fila.find_all("td")]
            info_linea = f"{celdas[0]}:{celdas[1]}-{celdas[2]}"
            datos_actuales += info_linea + "|"

        # Si el estado de la gerencia ha cambiado o es la primera ejecución
        if datos_actuales != estado_ant:
            # Forzamos el uso de la hora de Canarias explícitamente
            ahora = datetime.now(ZoneInfo("Atlantic/Canary"))
            fecha_telegram = ahora.strftime("%d/%m/%Y - %H:%M")

            for idx, fila in enumerate(filas):
                celdas = [c.get_text(strip=True) for c in fila.find_all("td")]
                info_linea = f"{celdas[0]}:{celdas[1]}-{celdas[2]}"
                texto_linea = f"  • {celdas[0]} ➔ Gerencia: `{celdas[1]}` | Global: `{celdas[2]}`"
                
                if estado_ant and (info_linea not in estado_ant):
                    texto_linea = f"⚠️ {texto_linea}"
                
                if idx < 3: 
                    lineas_ord.append(texto_linea)
                else: 
                    lineas_disc.append(texto_linea)

            with open(fichero_estado, "w") as f: 
                f.write(datos_actuales)
            print(f"✅ Archivo {fichero_estado} actualizado en disco.")
            
            txt_ord = "\n".join(lineas_ord)
            txt_disc = "\n".join(lineas_disc)
            
            msg = (
                f"🔄 *SCS: {nombre}*\n"
                f"📅 _Actualizado: {fecha_telegram}_\n"
                f"🏥 _Enfermero/a (ATS/DUE)_\n\n"
                f"📋 *Ordinarios:*\n{txt_ord}\n\n"
                f"♿ *Discapacidad:*\n{txt_disc}\n\n"
                f"🔗 [Ver en la web]({URL_BASE})"
            )
            enviar_telegram(msg, thread_id)
            
    except Exception as e:
        print(f"Error procesando la gerencia de {nombre}: {e}")

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    for g in GERENCIAS_ENFERMERIA:
        procesar_gerencia(session, g['nombre'], g['valor'], g['thread_id'])

if __name__ == "__main__":
    main()
    
