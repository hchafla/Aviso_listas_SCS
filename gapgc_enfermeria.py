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
    # Reemplaza saltos de línea por un espacio limpio y quita espacios extra
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    return " | ".join(lineas)

def procesar_pdf():
    if not descargar_pdf():
        return

    with pdfplumber.open("temp_gapgc.pdf") as pdf:
        # El documento suele ser de una sola página, iteramos por si acaso
        for pagina in pdf.pages:
            tabla = pagina.extract_table()
            if not tabla:
                continue

            for fila in tabla:
                # Buscamos la fila de Enfermería (primera columna)
                if fila[0] and "ATS/DUE" in fila[0]:
                    # Mapeo estricto según orden físico de columnas detectado en image_c49b38.png
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

                    # Creamos la cadena de control para el histórico
                    cadena_control = "#".join([f"{k}:{v}" for k, v in datos.items()])

                    estado_anterior = ""
                    if os.path.exists(FICHERO_ESTADO):
                        with open(FICHERO_ESTADO, "r") as f:
                            estado_anterior = f.read().strip()

                    if cadena_control != estado_anterior:
                        ahora = datetime.now().strftime("%d/%m/%Y - %H:%M")
                        
                        # Construcción del reporte para Telegram
                        msg = (
                            f"🏥 *SCS: GAPGC (Atención Primaria GC)*\n"
                            f"📅 _Actualizado: {ahora}_\n"
                            f"📜 _Categoría: ATS/DUE (PDF Oficial)_\n\n"
                            f"📊 *Listas de Empleo SIGLE/SUPLE:*\n"
                            f"• Eventual Corta Ord: `{datos['Ev_Corta_Ord'] or 'Sin datos'}`\n"
                            f"• Eventual Corta Disc: `{datos['Ev_Corta_Disc'] or 'Sin datos'}`\n"
                            f"• Eventual Larga Ord: `{datos['Ev_Larga_Ord'] or 'Sin datos'}`\n"
                            f"• Eventual Larga Disc: `{datos['Ev_Larga_Disc'] or 'Sin datos'}`\n"
                            f"• Sustitución Corta Ord: `{datos['Sust_Corta_Ord'] or 'Sin datos'}`\n"
                            f"• Sustitución Corta Disc: `{datos['Sust_Corta_Disc'] or 'Sin datos'}`\n"
                            f"• Sustitución Larga Ord: `{datos['Sust_Larga_Ord'] or 'Sin datos'}`\n"
                            f"• Sustitución Larga Disc: `{datos['Sust_Larga_Disc'] or 'Sin datos'}`\n"
                            f"• Interinidad Ord: `{datos['Interinidad_Ord'] or 'Sin datos'}`\n"
                            f"• Interinidad Disc: `{datos['Interinidad_Disc'] or 'Sin datos'}`\n\n"
                            f"📋 *Listas de Contratación propias:*\n"
                            f"• Currículum GAPGC Ord: `{datos['Curriculum_Ord'] or 'Sin datos'}`\n\n"
                            f"🔗 [Descargar PDF Oficial]({URL_PDF})"
                        )
                        
                        enviar_telegram(msg)
                        
                        with open(FICHERO_ESTADO, "w") as f:
                            f.write(cadena_control)
                        print("✅ Cambios detectados y procesados para la GAPGC.")
                    else:
                        print("ℹ️ GAPGC sin cambios desde la última verificación.")
                    return

    # Limpieza del archivo temporal
    if os.path.exists("temp_gapgc.pdf"):
        os.remove("temp_gapgc.pdf")

if __name__ == "__main__":
    procesar_pdf()
