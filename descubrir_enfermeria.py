import requests
from bs4 import BeautifulSoup

URL_BASE = "https://www3.gobiernodecanarias.org/sanidad/scs/ConsultaSIGLE/index.xhtml"

def descubrir():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    # 1. Entramos a la Home para sacar el ViewState
    print("Accediendo a la Home del SCS...")
    r_home = session.get(URL_BASE, timeout=15)
    soup_home = BeautifulSoup(r_home.text, "html.parser")
    
    input_vs = soup_home.find("input", {"name": "javax.faces.ViewState"})
    if not input_vs:
        print("No se localizó el ViewState inicial.")
        return
    vs_1 = input_vs.get("value")
    
    # 2. Seleccionamos una gerencia cualquiera (ej: Dr. Negrín, valor 21) para que nos mande a la página de categorías
    print("Simulando selección de Gerencia para cargar categorías...")
    payload_g = {
        "j_idt43": "j_idt43", 
        "j_idt43:gerenciaUNSOM_input": "21", 
        "j_idt43:j_idt46": "Seleccionar", 
        "javax.faces.ViewState": vs_1
    }
    r_cat = session.post(URL_BASE, data=payload_g, timeout=15)
    
    # 3. Analizamos el desplegable de categorías de la segunda página
    soup_cat = BeautifulSoup(r_cat.text, "html.parser")
    select_cat = soup_cat.find("select", {"id": "j_idt13:categoriasSOM_input"})
    
    if select_cat:
        print("\n--- ¡DESPLEGABLE DE CATEGORÍAS ENCONTRADO! ---")
        options = select_cat.find_all("option")
        for option in options:
            val = option.get("value")
            texto = option.text.strip()
            if val:
                print(f"ID: {val} | Nombre: {texto}")
    else:
        print("\n❌ Error: No se localizó el elemento selector 'j_idt13:categoriasSOM_input'.")
        # Imprimimos fragmento para auditar qué estructura devolvió en su lugar
        print("Estructura de inputs disponibles:")
        for inp in soup_cat.find_all("input"):
            print(f"Input encontrado -> Name: {inp.get('name')}, Type: {inp.get('type')}")

if __name__ == "__main__":
    discover()
