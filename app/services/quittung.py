
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from collections import Counter
from datetime import date
from decimal import Decimal
from weasyprint import HTML

from app.models.quittung import Quittung
from app.schemas.quittung import QuittungArtikelSchema, QuittungOutSchema, QuittungsTyp, QuittungGruppeArtikel
from app.crud import skiservice as crud_skiservice
from app.crud import saisonverleih as crud_saisonverleih

templates = Jinja2Templates(directory="app/templates")

def _datum(wert) -> str:
    """'2026-10-18' / date / datetime -> '18.10.2026'"""
    if not wert:
        return ""
    if isinstance(wert, str):
        wert = date.fromisoformat(wert[:10])
    return wert.strftime("%d.%m.%Y")

def _eur(wert) -> str:
    """1234.5 -> '1.234,50 €'"""
    text = f"{Decimal(str(wert or 0)):,.2f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".") + " €"

templates.env.filters["datum"] = _datum
templates.env.filters["eur"] = _eur

def _voller_name(vorname: str | None, nachname: str | None) -> str:
    """Fügt Vor- und Nachname zusammen, fehlende Teile werden übersprungen."""
    return " ".join(teil.strip() for teil in (vorname, nachname) if teil and teil.strip())

def _AuftragzuArtikel(auftrag_id: int, db: Session) -> QuittungGruppeArtikel:
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, auftrag_id)
    service_Counter: Counter[tuple[str, float]] = Counter()
    bindung_Counter: Counter[float] = Counter()

    if not auftrag:
        raise HTTPException(
                    status_code=404,
                    detail=f"Quittung verweist auf Auftrag {auftrag_id}, der nicht existiert",
                )
    
    for ski in auftrag.skis:
        # Wen Service und Preis identisch ist wird Hochgezählt
        service_Counter[(ski.service, ski.preis)] += 1
        if ski.bindung_check:
            bindung_Counter[ski.bindung_preis] += 1

    kunde = auftrag.kunde
    name = _voller_name(kunde.Vorname, kunde.Nachname) if kunde else ""
    bez = f"Skiservice - {auftrag.name} - {name}"
    artikelgruppe = QuittungGruppeArtikel(type=QuittungsTyp.Auftrag, toID=auftrag_id, bezeichnung=bez)
        
    for (service, preis), anzahl in service_Counter.items():
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung=service,
            preis=preis,
            anzahl=anzahl,
            toID=auftrag_id
        ))

    for bindung_preis, anzahl in bindung_Counter.items():
        # TODO #27 Bindungscheck bezeichnung aus DB in der Quittung
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung="Bindungscheck",
            preis=bindung_preis,
            anzahl=anzahl,
            toID=auftrag_id
        ))

    return artikelgruppe

def _VerleihzuArtikel(verleihID: int, db: Session) -> QuittungGruppeArtikel:
    # ertmal daten aus DB lesen
    verleih = crud_saisonverleih.get_saisonverleih(db, verleihID)
    # TODO #26 Verleih bezeichnung mit auf der Quittung
    verleih_counter: Counter[float] = Counter()

    #Wen nix gefunden wird auch nix zurück
    if not verleih:
        raise HTTPException(
            status_code=404,
            detail=f"Quittung verweist auf Verleih {verleihID}, der nicht existiert",
        )

    # artikel Init
    kunde = verleih.Kunde
    name = _voller_name(kunde.Vorname, kunde.Nachname) if kunde else ""
    bez = f"Verleih - {verleih.Name} - {name}"
    artikelgruppe = QuittungGruppeArtikel(type=QuittungsTyp.Verleih, toID=verleihID, bezeichnung=bez)

    for ski in verleih.Material:
        verleih_counter[ski.Preis] += 1

    for verleih_Preis, anzahl in verleih_counter.items():
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Verleih,
            bezeichnung="Saisonverleih",
            preis=verleih_Preis,
            anzahl=anzahl,
            toID=verleihID
        ))

    return artikelgruppe

class QuittungsService:
    def __init__(self, db: Session):
        self.db = db

    def get_quittung(self, quittung_id: int) -> QuittungOutSchema:
        quittung = self.db.query(Quittung).filter(Quittung.ID == quittung_id).first()

        # Wurde etwas geufnden?
        if not quittung:
            raise HTTPException(status_code=404, detail="Quittung not found")

        quittungOut = QuittungOutSchema(
            id=quittung.ID,
            name=quittung.Name,
            saison_ID=quittung.Saison_ID,
            bezahlt=quittung.Bezahlt,
            bezahlt_Am=quittung.Bezahlt_Am,
            ueberweisung=quittung.Ueberweisung,
            karte=quittung.Karte,
            bar=quittung.Bar,
            buchhaltungSync=quittung.BuchhaltungSync,
            lexID=quittung.LexID,
            nurExtern=quittung.NurExtern,
        )

        if quittung.NurExtern:
            pass #TODO Qittung direkt von Lexoffice holen und zurückgeben

           
        for artikel in quittung.artikels:
            if artikel.Auftrag_ID is not None:
                quittungOut.artikelgruppen.append(_AuftragzuArtikel(artikel.Auftrag_ID, self.db))

            if artikel.Verleih_ID is not None:
                quittungOut.artikelgruppen.append(_VerleihzuArtikel(artikel.Verleih_ID, self.db))
        
        return quittungOut

    def renderPDF(self, data: QuittungOutSchema) -> bytes:
        FIRMA = {
            "name": "Simons Skiservice",
            "strasse": "Am Anennberg 12",          # z. B. "Musterstraße 1"
            "ort": "Fronreute",     # z. B. "88273 Fronreute"
            "telefon": "07502/94 27 162",
            "email": "info@ms-skiservice.de",
            "mwst_satz": 19,      # z. B. 19 -> zeigt Netto/MwSt. an
            "kleinunternehmer": False,
        }

        html = templates.get_template("quittung.html").render(quittung=data, firma=FIRMA, heute=_datum(date.today()))
        pdf = HTML(string=html, base_url=str(templates)).write_pdf()

        if not pdf:
            raise HTTPException(status_code=404, detail="PDF konnte nicht erstellt werden")

        return pdf