import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo  # <- Forzar zona horaria nativa

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Variables desde los Secrets de GitHub
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_CREDENTIALS = os.environ.get("GOOGLE_CREDENTIALS")

URL_BASE = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/index.xhtml"
URL_CAT = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/categorias.xhtml"

# ID real verificado para ATS/DUE (Enfermero/a)
CATEGORIA_ENFERMERIA = "103"

# Google Sheet de Enfermería
SPREADSHEET_ID = "12ADV_6QhR02uh6o3OJfZIelDZFSr1yI-sTN877-MPtI"


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


# ============================================================
# TELEGRAM
# ============================================================

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


# ============================================================
# GOOGLE SHEETS
# ============================================================

def obtener_servicio_sheets():
    """
    Crea el servicio de Google Sheets utilizando las credenciales
    almacenadas en el Secret GOOGLE_CREDENTIALS de GitHub.
    """

    if not GOOGLE_CREDENTIALS:
        print("⚠️ GOOGLE_CREDENTIALS no está configurado.")
        return None

    try:
        credenciales_dict = json.loads(GOOGLE_CREDENTIALS)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets"
        ]

        credenciales = Credentials.from_service_account_info(
            credenciales_dict,
            scopes=scopes
        )

        servicio = build(
            "sheets",
            "v4",
            credentials=credenciales
        )

        print("✅ Servicio de Google Sheets conectado correctamente.")
        return servicio

    except Exception as e:
        print(f"⚠️ Error conectando con Google Sheets: {e}")
        return None


def convertir_numero(valor):
    """
    Intenta convertir un valor a entero.
    Si no es posible, devuelve el valor original.
    """

    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor


def registrar_en_sheets(
    sheets_service,
    fecha,
    nombre_gerencia,
    tipo_lista,
    contrato,
    num_g,
    num_gl
):
    """
    Añade una fila al histórico de Google Sheets.

    Columnas:
    Fecha | Gerencia | Tipo de lista | Contrato | Nº Gerencia | Nº Global
    """

    if sheets_service is None:
        return

    try:
        valores = [[
            fecha,
            nombre_gerencia,
            tipo_lista,
            contrato,
            convertir_numero(num_g),
            convertir_numero(num_gl)
        ]]

        cuerpo = {
            "values": valores
        }

        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="Histórico_Datos!A:F",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=cuerpo
        ).execute()

        print(
            f"📊 Registrado en Sheets: "
            f"{nombre_gerencia} | {tipo_lista} | {contrato}"
        )

    except Exception as e:
        # Un fallo de Sheets no debe impedir que continúe Telegram
        print(f"⚠️ Error registrando en Google Sheets: {e}")


# ============================================================
# VIEW STATE
# ============================================================

def extraer_view_state(html):
    soup = BeautifulSoup(html, "html.parser")
    input_vs = soup.find(
        "input",
        {"name": "javax.faces.ViewState"}
    )

    return input_vs.get("value") if input_vs else None


# ============================================================
# PROCESAMIENTO DE CADA GERENCIA
# ============================================================

def procesar_gerencia(
    session,
    sheets_service,
    nombre,
    valor_gerencia,
    thread_id
):

    fichero_estado = f"estado_enf_{valor_gerencia}.txt"

    try:

        # ----------------------------------------------------
        # 1. Petición a la Home y selección de Gerencia
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # 2. Selección de la Categoría ATS/DUE (103)
        # ----------------------------------------------------

        vs_2 = extraer_view_state(r_cat.text)

        payload_c = {
            "j_idt13": "j_idt13",
            "j_idt13:categoriasSOM_input": CATEGORIA_ENFERMERIA,
            "j_idt13:j_idt16": "Seleccionar",
            "javax.faces.ViewState": vs_2
        }

        r_final = session.post(
            URL_CAT,
            data=payload_c,
            timeout=15
        )

        # ----------------------------------------------------
        # 3. Procesamiento de la tabla de resultados
        # ----------------------------------------------------

        soup = BeautifulSoup(
            r_final.text,
            "html.parser"
        )

        filas = [
            f
            for f in soup.find_all("tr")
            if len(f.find_all("td")) >= 3
            and any(
                kw in f.get_text()
                for kw in ["Corta", "Larga", "Interinidad"]
            )
        ]

        print(
            f"[{nombre}] Filas válidas detectadas en la tabla: "
            f"{len(filas)}"
        )

        if len(filas) == 0:
            return

        datos_actuales = ""

        lineas_ord = []
        lineas_disc = []

        # ----------------------------------------------------
        # Estado anterior
        # ----------------------------------------------------

        estado_ant = ""

        if os.path.exists(fichero_estado):
            with open(
                fichero_estado,
                "r"
            ) as f:
                estado_ant = f.read().strip()

        # ----------------------------------------------------
        # Construcción del estado actual
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Si el estado ha cambiado o es la primera ejecución
        # ----------------------------------------------------

        if datos_actuales != estado_ant:

            # Hora de Canarias
            ahora = datetime.now(
                ZoneInfo("Atlantic/Canary")
            )

            fecha_telegram = ahora.strftime(
                "%d/%m/%Y - %H:%M"
            )

            fecha_sheets = ahora.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            # ------------------------------------------------
            # Procesar filas
            # ------------------------------------------------

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

                # --------------------------------------------
                # Determinar si la línea es nueva/modificada
                # --------------------------------------------

                linea_nueva = (
                    estado_ant
                    and info_linea not in estado_ant
                )

                if linea_nueva:
                    texto_linea = f"⚠️ {texto_linea}"

                # --------------------------------------------
                # Tipo de lista
                # --------------------------------------------

                if idx < 3:
                    tipo_lista = "Ordinaria"
                    lineas_ord.append(texto_linea)
                else:
                    tipo_lista = "Discapacidad"
                    lineas_disc.append(texto_linea)

                # --------------------------------------------
                # Google Sheets
                #
                # Primera ejecución:
                #   registra todas las filas.
                #
                # Ejecuciones posteriores:
                #   registra solamente las líneas nuevas.
                # --------------------------------------------

                if not estado_ant or linea_nueva:

                    registrar_en_sheets(
                        sheets_service=sheets_service,
                        fecha=fecha_sheets,
                        nombre_gerencia=nombre,
                        tipo_lista=tipo_lista,
                        contrato=celdas[0],
                        num_g=celdas[1],
                        num_gl=celdas[2]
                    )

            # ------------------------------------------------
            # Actualizar archivo de estado
            # ------------------------------------------------

            with open(
                fichero_estado,
                "w"
            ) as f:
                f.write(datos_actuales)

            print(
                f"✅ Archivo {fichero_estado} "
                f"actualizado en disco."
            )

            # ------------------------------------------------
            # Telegram
            # ------------------------------------------------

            txt_ord = "\n".join(lineas_ord)
            txt_disc = "\n".join(lineas_disc)

            msg = (
                f"🔄 *SCS: {nombre}*\n"
                f"📅 _Actualizado: {fecha_telegram}_\n"
                f"🏥 _Enfermero/a (ATS/DUE)_\n\n"
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
            f"Error procesando la gerencia de "
            f"{nombre}: {e}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Conexión con Google Sheets
    # --------------------------------------------------------

    sheets_service = obtener_servicio_sheets()

    # --------------------------------------------------------
    # Sesión HTTP
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update({
        "User-Agent":
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64)"
    })

    # --------------------------------------------------------
    # Procesar todas las gerencias
    # --------------------------------------------------------

    for g in GERENCIAS_ENFERMERIA:

        procesar_gerencia(
            session,
            sheets_service,
            g["nombre"],
            g["valor"],
            g["thread_id"]
        )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()
