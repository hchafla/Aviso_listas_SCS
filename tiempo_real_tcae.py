import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
URL_BASE = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/index.xhtml"
URL_CAT = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/categorias.xhtml"

# ID oficial para Auxiliar de Enfermería (TCAE)
CATEGORIA_TCAE = "98"

GERENCIAS_TCAE = [
    {"nombre": "Lanzarote", "valor": "22", "thread_id": 2},
    {"nombre": "Fuerteventura", "valor": "23", "thread_id": 3},
    {"nombre": "CHUIMI", "valor": "24", "thread_id": 4},
    {"nombre": "Candelaria", "valor": "25", "thread_id": 5},
    {"nombre": "La Palma", "valor": "26", "thread_id": 6},
    {"nombre": "La Gomera", "valor": "27", "thread_id": 7},
    {"nombre": "El Hierro", "valor": "28", "thread_id": 8},
    {"nombre": "Atención Primaria Tenerife", "valor": "30", "thread_id": 9},
    {"nombre": "Atención Primaria Gran Canaria", "valor": "20", "thread_id": 10},
    {"nombre": "Dr. Negrín", "valor": "21", "thread_id": 11}
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
            print(f"Error Telegram TCAE (Hilo {thread_id}): {response.text}")
    except Exception as e:
        print(f"Error enviando a Telegram TCAE: {e}")

def extraer_view_state(html):
    soup = BeautifulSoup(html, "html.parser")
    input_vs = soup.find("input", {"name": "javax.faces.ViewState"})
    return input_vs.get("value") if input_vs else None

def procesar_gerencia(session, nombre, valor_gerencia, thread_id):
    fichero_estado = f"estado_tcae_{valor_gerencia}.txt"

    try:
        r_home = session.get(URL_BASE, timeout=15)
        vs_1 = extraer_view_state(r_home.text)
        
        payload_g = {
            "j_idt43": "j_idt43", 
            "j_idt43:gerenciaUNSOM_input": valor_gerencia, 
            "j_idt43:j_idt46": "Seleccionar", 
            "javax.faces.ViewState": vs_1
        }
        r_cat = session.post(URL_BASE, data=payload_g, timeout=15)
        
        vs_2 = extraer_view_state(r_cat.text)
        payload_c = {
            "j_idt13": "j_idt13", 
            "j_idt13:categoriasSOM_input": CATEGORIA_TCAE, 
            "j_idt13:j_idt16": "Seleccionar", 
            "javax.faces.ViewState": vs_2
        }
        r_final = session.post(URL_CAT, data=payload_c, timeout=15)
        
        soup = BeautifulSoup(r_final.text, "html.parser")
        filas = [f for f in soup.find_all("tr") if len(f.find_all("td")) >= 3 and any(kw in f.get_text() for kw in ["Corta", "Larga", "Interinidad"])]
        
        print(f"[{nombre}] Filas TCAE detectadas: {len(filas)}")
        
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

        if datos_actuales != estado_ant:
            ahora = datetime.now().strftime("%d/%m/%Y - %H:%M")

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
            
            txt_ord = "\n".join(lineas_ord)
            txt_disc = "\n".join(lineas_disc)
            
            msg = (
                f"🔄 *SCS: {nombre}*\n"
                f"📅 _Actualizado: {ahora}_\n"
                f"🏥 *TCAE (Auxiliar de Enfermería)*\n\n"
                f"📋 *Ordinarios:*\n{txt_ord}\n\n"
                f"♿ *Discapacidad:*\n{txt_disc}\n\n"
                f"🔗 [Ver en la web]({URL_BASE})"
            )
            enviar_telegram(msg, thread_id)
            
    except Exception as e:
        print(f"Error procesando TCAE en {nombre}: {e}")

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    for g in GERENCIAS_TCAE:
        procesar_gerencia(session, g['nombre'], g['valor'], g['thread_id'])

if __name__ == "__main__":
    main()
