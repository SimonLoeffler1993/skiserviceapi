from fastapi.templating import Jinja2Templates
from weasyprint import HTML

from app.schemas.saisonverleih import SaisonVerleihRead

templates = Jinja2Templates(directory="app/templates")

def generate_Saisonbericht(saionverleih: SaisonVerleihRead) -> bytes:
    """
    Erstellt den Vertrag für einen Saison- oder Tagesverleih als PDF.
    Das PDF wird wie die Quittung lokal mit WeasyPrint erzeugt, es wird kein externer Dienst benötigt.
    """

    # Gesamtpreis berechnen
    gesamtpreis = sum(item.Preis for item in saionverleih.Material)

    html = templates.get_template("saisonverleih.html").render(saisonverleih=saionverleih, gesamtpreis=gesamtpreis)

    pdf = HTML(string=html).write_pdf()
    if not pdf:
        raise ValueError("PDF konnte nicht erstellt werden")
    return pdf
