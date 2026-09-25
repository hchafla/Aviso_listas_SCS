import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo  # <- Forzar zona horaria nativa

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

URL_BASE = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/index.xhtml"
URL_CAT = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/categorias.xhtml"

# Google Sheet exclusivo para TCAE
SPREADSHEET_ID = "14dbpOOpwYk2VkUa2tDY48AGk2W3OAfa-AFqaC3ri62"

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


def obtener_servicio_sheets():
    """Conecta con Google Sheets usando las credenciales del Secret."""
    try:
        if not GOOGLE_CREDENTIALS:
            print("⚠️ No existe GOOGLE_CREDENTIALS.")
            return None

        credenciales_dict = json.loads(GOOGLE_CREDENTIALS)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets"
        ]

        credentials = Credentials.from_service_account_info(
            credenciales_dict,
            scopes=scopes
        )

        service = build(
            "sheets",
            "v4",
            credentials=credentials
        )

        print("✅ Servicio de Google Sheets conectado correctamente.")
        return service

    except Exception as e:
        print(f"❌ Error conectando con Google Sheets: {e}")
        return None


def convertir_numero(valor):
    """Convierte un valor a número si es posible."""
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor


def registrar_en_sheets(
    sheets_service,
    fecha,
    gerencia,
    tipo_lista,
    contrato,
    numero_gerencia,
    numero_global
):
    """Añade una línea al histórico de Google Sheets."""
    if sheets_service is None:
        return

    try:
        valores = [[
            fecha,
            gerencia,
            tipo_lista,
            contrato,
            convertir_numero(numero_gerencia),
            convertir_numero(numero_global)
        ]]

        body = {
            "values": valores
        }

        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Histórico_Datos!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        print(
            f"📊 Registrado en Sheets: "
            f"{gerencia} | {tipo_lista} | {contrato}"
        )

    except Exception as e:
        # Un fallo de Sheets NO debe impedir que siga funcionando
        # el scraper ni Telegram.
        print(f"⚠️ Error registrando en Google Sheets: {e}")


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
            print(
                f"Error Telegram TCAE "
                f"(Hilo {thread_id}): {response.text}"
            )

    except Exception as e:
        print(f"Error sending to Telegram TCAE: {e}")


def extraer_view_state(html):
    soup = BeautifulSoup(html, "html.parser")
    input_vs = soup.find(
        "input",
        {"name": "javax.faces.ViewState"}
    )

    return input_vs.get("value") if input_vs else None


def procesar_gerencia(
    session,
    nombre,
    valor_gerencia,
    thread_id,
    sheets_service
):
    fichero_estado = f"estado_tcae_{valor_gerencia}.txt"

    try:
        r_home = session.get(
            URL_BASE,
            timeout=15
        )

        vs_1 = extraer_view_state(r_home.text)

        payload_g = {
            "j_idt43": "j_idt43",
            "j_idt43:gerenciaUNSOM_input": valor_gerencia,
            "j_idt43:j_idt46": "Seleccionar",
            "javax.faces.ViewState": vs_1
        }

        r_cat = session.post(
            URL_BASE,
            data=payload_g,
            timeout=15
        )

        vs_2 = extraer_view_state(r_cat.text)

        payload_c = {
            "j_idt13": "j_idt13",
            "j_idt13:categoriasSOM_input": CATEGORIA_TCAE,
            "j_idt13:j_idt16": "Seleccionar",
            "javax.faces.ViewState": vs_2
        }

        r_final = session.post(
            URL_CAT,
            data=payload_c,
            timeout=15
        )

        soup = BeautifulSoup(
            r_final.text,
            "html.parser"
        )

        filas = [
            f for f in soup.find_all("tr")
            if len(f.find_all("td")) >= 3
            and any(
                kw in f.get_text()
                for kw in ["Corta", "Larga", "Interinidad"]
            )
        ]

        print(
            f"[{nombre}] Filas TCAE detectadas: {len(filas)}"
        )

        if len(filas) == 0:
            return

        datos_actuales = ""
        lineas_ord = []
        lineas_disc = []

        estado_ant = ""

        if os.path.exists(fichero_estado):
            with open(
                fichero_estado,
                "r"
            ) as f:
                estado_ant = f.read().strip()

        for fila in filas:
            celdas = [
                c.get_text(strip=True)
                for c in fila.find_all("td")
            ]

            info_linea = (
                f"{celdas[0]}:"
                f"{celdas[1]}-"
                f"{celdas[2]}"
            )

            datos_actuales += info_linea + "|"

        if datos_actuales != estado_ant:

            # Forzamos explícitamente el huso horario de Canarias
            ahora_dt = datetime.now(
                ZoneInfo("Atlantic/Canary")
            )

            ahora = ahora_dt.strftime(
                "%d/%m/%Y - %H:%M"
            )

            # Fecha para Google Sheets
            fecha_sheets = ahora_dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            for idx, fila in enumerate(filas):

                celdas = [
                    c.get_text(strip=True)
                    for c in fila.find_all("td")
                ]

                info_linea = (
                    f"{celdas[0]}:"
                    f"{celdas[1]}-"
                    f"{celdas[2]}"
                )

                texto_linea = (
                    f"  • {celdas[0]} ➔ "
                    f"Gerencia: `{celdas[1]}` | "
                    f"Global: `{celdas[2]}`"
                )

                if estado_ant and (
                    info_linea not in estado_ant
                ):
                    texto_linea = (
                        f"⚠️ {texto_linea}"
                    )

                # Las tres primeras filas son Ordinarias
                if idx < 3:
                    tipo_lista = "Ordinaria"
                    lineas_ord.append(texto_linea)

                # El resto son Discapacidad
                else:
                    tipo_lista = "Discapacidad"
                    lineas_disc.append(texto_linea)

                # Solo registramos en Sheets:
                # - todas las líneas en la primera ejecución
                # - únicamente las líneas nuevas posteriormente
                if not estado_ant or (
                    info_linea not in estado_ant
                ):
                    registrar_en_sheets(
                        sheets_service,
                        fecha_sheets,
                        nombre,
                        tipo_lista,
                        celdas[0],
                        celdas[1],
                        celdas[2]
                    )

            with open(
                fichero_estado,
                "w"
            ) as f:
                f.write(datos_actuales)

            txt_ord = "\n".join(lineas_ord)
            txt_disc = "\n".join(lineas_disc)

            msg = (
                f"🔄 *SCS: {nombre}*\n"
                f"📅 _Actualizado: {ahora}_\n"
                f"🏥 *TCAE (Auxiliar de Enfermería)*\n\n"
                f"📋 *Ordinarios:*\n"
                f"{txt_ord}\n\n"
                f"♿ *Discapacidad:*\n"
                f"{txt_disc}\n\n"
                f"🔗 [Ver en la web]({URL_BASE})"
            )

            enviar_telegram(
                msg,
                thread_id
            )

    except Exception as e:
        print(
            f"Error procesando TCAE en {nombre}: {e}"
        )


def main():

    # Conectar una sola vez con Google Sheets
    sheets_service = obtener_servicio_sheets()

    session = requests.Session()

    session.headers.update({
        "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })

    for g in GERENCIAS_TCAE:

        procesar_gerencia(
            session,
            g["nombre"],
            g["valor"],
            g["thread_id"],
            sheets_service
        )


if __name__ == "__main__":
    main()
