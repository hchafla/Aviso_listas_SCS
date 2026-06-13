import os
import requests
import pdfplumber
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
THREAD_ID = 7  # Hilo asignado a Atención Primaria Gran Canaria
URL_PDF = "https://www3.gobiernodecanarias.org/sanidad/scs/content/f91bab10-92f7-11ec-9494-c360bb7ead96/Ultimos-llamamientos-LC-GranCanaria.pdf"
FICHERO_ESTADO = "estado_gapgc.txt"

def descargar_pdf():
    try:
        response = requests.get(URL_PDF, timeout=30)
        if response.status_code == 200:
            with open("temp_gapgc.pdf", "wb") as f:
                f.write(response.content)
            return True
        print(f"Error al descargar PDF: Estado {response.status_code}")
    except Exception as e:
        print(f"Error en la descarga del PDF: {e}")
    return False

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "message_thread_id": THREAD_ID
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code != 200:
            print(f"Error Telegram GAPGC: {response.text}")
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

def limpiar_celda(texto):
    if not texto:
        return ""
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    return " | ".join(lineas)

def procesar_pdf():
    if not descargar_pdf():
        return

    with pdfplumber.open("temp_gapgc.pdf") as pdf:
        for pagina in pdf.pages:
            tabla = pagina.extract_table()
            if not tabla:
                continue

            for fila in tabla:
                if fila[0] and "ATS/DUE" in fila[0]:
                    datos = {
                        "Ev_Corta_Ord": limpiar_celda(fila[1]),
                        "Ev_Corta_Disc": limpiar_celda(fila[2]),
                        "Ev_Larga_Ord": limpiar_celda(fila[3]),
                        "Ev_Larga_Disc": limpiar_celda(fila[4]),
                        "Sust_Corta_Ord": limpiar_celda(fila[5]),
                        "Sust_Corta_Disc": limpiar_celda(fila[6]),
                        "Sust_Larga_Ord": limpiar_celda(fila[7]),
                        "Sust_Larga_Disc": limpiar_celda(fila[8]),
                        "Interinidad_Ord": limpiar_celda(fila[9]),
                        "Interinidad_Disc": limpiar_celda(fila[10]),
                        "Curriculum_Ord": limpiar_celda(fila[13]) if len(fila) > 13 else ""
                    }

                    # Cadena de control del estado actual
                    cadena_control = "#".join([f"{k}:{v}" for k, v in datos.items()])

                    estado_anterior = ""
                    if os.path.exists(FICHERO_ESTADO):
                        with open(FICHERO_ESTADO, "r") as f:
                            estado_anterior = f.read().strip()

                    if cadena_control != estado_anterior:
                        ahora = datetime.now().strftime("%d/%m/%Y - %H:%M")
                        
                        # Diccionario para almacenar las líneas finales formateadas
                        lineas_msg = {}

                        # Evaluamos cada campo individualmente contra el historial
                        for clave, valor in datos.items():
                            texto_mostrar = valor or "Sin datos"
                            marcador = ""
                            
                            # Si existía un estado anterior, verificamos si este campo específico ha mutado
                            if estado_anterior:
                                patron_campo = f"{clave}:{valor}"
                                if patron_campo not in estado_anterior:
                                    marcador = "⚠️ "
                            
                            lineas_msg[clave] = f"{marcador}`{texto_mostrar}`"

                        # Construcción del reporte dinámico para Telegram
                        msg = (
                            f"🏥 *SCS: GAPGC (Atención Primaria GC)*\n"
                            f"📅 _Actualizado: {ahora}_\n"
                            f"📜 _Categoría: ATS/DUE (PDF Oficial)_\n\n"
                            f"📊 *Listas de Empleo SIGLE/SUPLE:*\n"
                            f"• Eventual Corta Ord: {lineas_msg['Ev_Corta_Ord']}\n"
                            f"• Eventual Corta Disc: {lineas_msg['Ev_Corta_Disc']}\n"
                            f"• Eventual Larga Ord: {lineas_msg['Ev_Larga_Ord']}\n"
                            f"• Eventual Larga Disc: {lineas_msg['Ev_Larga_Disc']}\n"
                            f"• Sustitución Corta Ord: {lineas_msg['Sust_Corta_Ord']}\n"
                            f"• Sustitución Corta Disc: {lineas_msg['Sust_Corta_Disc']}\n"
                            f"• Sustitución Larga Ord: {lineas_msg['Sust_Larga_Ord']}\n"
                            f"• Sustitución Larga Disc: {lineas_msg['Sust_Larga_Disc']}\n"
                            f"• Interinidad Ord: {lineas_msg['Interinidad_Ord']}\n"
                            f"• Interinidad Disc: {lineas_msg['Interinidad_Disc']}\n\n"
                            f"📋 *Listas de Contratación propias:*\n"
                            f"• Currículum GAPGC Ord: {lineas_msg['Curriculum_Ord']}\n\n"
                            f"🔗 [Descargar PDF Oficial]({URL_PDF})"
                        )
                        
                        enviar_telegram(msg)
                        
                        with open(FICHERO_ESTADO, "w") as f:
                            f.write(cadena_control)
                        print("✅ Cambios detectados y procesados para la GAPGC con marcas de alerta.")
                    else:
                        print("ℹ️ GAPGC sin cambios desde la última verificación.")
                    return

    if os.path.exists("temp_gapgc.pdf"):
        os.remove("temp_gapgc.pdf")

if __name__ == "__main__":
    procesar_pdf()
