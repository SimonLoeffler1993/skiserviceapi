import requests
from fastapi.templating import Jinja2Templates
from app.schemas.saisonverleih import SaisonVerleihRead
from app.services import einstellungen
import os

templates = Jinja2Templates(directory="app/templates")

# TODO #20 auf Loakel generieren umstellen
def generate_Saisonbericht(saionverleih: SaisonVerleihRead):

    # Gesamtpreis berechnen
    gesamtpreis = sum(item.Preis for item in saionverleih.Material)

    html  = templates.get_template("saisonverleih.html").render(saisonverleih=saionverleih, gesamtpreis=gesamtpreis)

    # PDF generieren via API
    stirlingUrl = einstellungen.hole("STIRLING_URL").rstrip("/")
    respose = requests.post(f"{stirlingUrl}/api/v1/convert/html/pdf",
                            files={"fileInput": ("saisonverleih.html", html, "text/html")},
                            data={"zoom":1},
                            timeout=60)
    if respose.status_code != 200:
        raise Exception("Fehler bei der PDF Generierung")

    return respose.content