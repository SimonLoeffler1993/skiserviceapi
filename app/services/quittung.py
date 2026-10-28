
from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from weasyprint import HTML

from app.models.quittung import Quittung
from app.services import einstellungen
from app.utils.lexware import LexwareAPI
from app.utils.girocode import girocode_png_data_uri, iban_formatiert
from app.schemas.quittung import QuittungArtikelSchema, QuittungBezug, QuittungKundeSchema, QuittungListeEintrag, QuittungOutSchema, QuittungsTyp, QuittungGruppeArtikel
from app.models.kunde import SkiKunde
from app.models.saisonverleih import SaisonVerleih
from app.models.skiservice import Auftrag
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

def quittung_nummer(quittung: Quittung) -> str:
    return quittung.Nummer

def quittung_dateiname(quittung: Quittung) -> str:
    """z.B. quittung-26-27Q12.pdf"""
    return f"quittung-{quittung_nummer(quittung).replace('/', '-')}.pdf"

def _quittung_kunde(kunden: dict[int, SkiKunde]) -> QuittungKundeSchema | None:
    """Ein Kunde mit Anschrift, bei unterschiedlichen Kunden (anhand der ID) ein Sammelkunde."""
    if not kunden:
        return None
    if len(kunden) > 1:
        return QuittungKundeSchema(sammel=True, name="Sammelkunde")
    kunde = next(iter(kunden.values()))
    return QuittungKundeSchema(
        id=kunde.ID,
        name=_voller_name(kunde.Vorname, kunde.Nachname),
        strasse=(kunde.Strasse or "").strip() or None,
        plz=kunde.Ort.Postlz if kunde.Ort else kunde.Plz,
        ort=kunde.Ort.Ort if kunde.Ort else None,
    )

def auftrag_gruppe(auftrag: Auftrag) -> QuittungGruppeArtikel:
    """Artikelgruppe eines geladenen Auftrags: gleiche Services mit gleichem Preis werden zusammengezählt."""
    service_Counter: Counter[tuple[str, float]] = Counter()
    bindung_Counter: Counter[float] = Counter()

    for ski in auftrag.skis:
        # Wen Service und Preis identisch ist wird Hochgezählt
        service_Counter[(ski.service, ski.preis)] += 1
        if ski.bindung_check:
            bindung_Counter[ski.bindung_preis] += 1

    kunde = auftrag.kunde
    name = _voller_name(kunde.Vorname, kunde.Nachname) if kunde else ""
    bez = f"Skiservice - {auftrag.name} - {name}"
    artikelgruppe = QuittungGruppeArtikel(type=QuittungsTyp.Auftrag, toID=auftrag.id, bezeichnung=bez)
        
    for (service, preis), anzahl in service_Counter.items():
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung=service,
            preis=preis,
            anzahl=anzahl,
            toID=auftrag.id
        ))

    for bindung_preis, anzahl in bindung_Counter.items():
        # TODO #27 Bindungscheck bezeichnung aus DB in der Quittung
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung="Bindungscheck",
            preis=bindung_preis,
            anzahl=anzahl,
            toID=auftrag.id
        ))

    return artikelgruppe

def verleih_gruppe(verleih: SaisonVerleih) -> QuittungGruppeArtikel:
    """Artikelgruppe eines geladenen Verleihs: Material mit gleichem Preis wird zusammengezählt."""
    # TODO #26 Verleih bezeichnung mit auf der Quittung
    verleih_counter: Counter[float] = Counter()

    # artikel Init
    kunde = verleih.Kunde
    name = _voller_name(kunde.Vorname, kunde.Nachname) if kunde else ""
    bez = f"Verleih - {verleih.Name} - {name}"
    artikelgruppe = QuittungGruppeArtikel(type=QuittungsTyp.Verleih, toID=verleih.ID, bezeichnung=bez)

    for ski in verleih.Material:
        verleih_counter[ski.Preis] += 1

    for verleih_Preis, anzahl in verleih_counter.items():
        artikelgruppe.artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Verleih,
            bezeichnung=verleih.Bezeichnung,
            preis=verleih_Preis,
            anzahl=anzahl,
            toID=verleih.ID
        ))

    return artikelgruppe

def _AuftragzuArtikel(auftrag_id: int, db: Session) -> QuittungGruppeArtikel:
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, auftrag_id)
    if not auftrag:
        raise HTTPException(
                    status_code=404,
                    detail=f"Quittung verweist auf Auftrag {auftrag_id}, der nicht existiert",
                )
    return auftrag_gruppe(auftrag)

def _VerleihzuArtikel(verleihID: int, db: Session) -> QuittungGruppeArtikel:
    verleih = crud_saisonverleih.get_saisonverleih(db, verleihID)
    #Wen nix gefunden wird auch nix zurück
    if not verleih:
        raise HTTPException(
            status_code=404,
            detail=f"Quittung verweist auf Verleih {verleihID}, der nicht existiert",
        )
    return verleih_gruppe(verleih)

def zahlart_text(bar: bool | None, karte: bool | None, ueberweisung: bool | None) -> str:
    """z.B. "Bar" oder "EC, Überweisung", leer wenn nichts angegeben"""
    return ", ".join(name for name, aktiv in (("Bar", bar), ("EC", karte), ("Überweisung", ueberweisung)) if aktiv)

def quittungen_liste(db: Session, saison_id: int) -> list[QuittungListeEintrag]:
    """
    Alle Quittungen einer Saison mit Artikeln, Betrag, Kunde und Bezügen.
    Aufträge und Verleihe werden gesammelt geladen (je eine Abfrage), nicht pro Quittung.
    """
    quittungen = (
        db.query(Quittung)
        .filter(Quittung.Saison_ID == saison_id)
        .order_by(Quittung.ID.desc())
        .all()
    )
    ids = [q.ID for q in quittungen]
    if not ids:
        return []

    auftraege = (
        db.query(Auftrag)
        .filter(Auftrag.quittung_id.in_(ids))
        .options(selectinload(Auftrag.skis), selectinload(Auftrag.kunde).selectinload(SkiKunde.Ort))
        .order_by(Auftrag.id)
        .all()
    )
    verleihe = (
        db.query(SaisonVerleih)
        .filter(SaisonVerleih.QuittungID.in_(ids))
        .options(selectinload(SaisonVerleih.Material), selectinload(SaisonVerleih.Kunde).selectinload(SkiKunde.Ort))
        .order_by(SaisonVerleih.ID)
        .all()
    )
    nach_quittung_a: dict[int, list[Auftrag]] = defaultdict(list)
    for a in auftraege:
        nach_quittung_a[a.quittung_id].append(a)
    nach_quittung_v: dict[int, list[SaisonVerleih]] = defaultdict(list)
    for v in verleihe:
        nach_quittung_v[v.QuittungID].append(v)

    liste = []
    for q in quittungen:
        q_auftraege = nach_quittung_a.get(q.ID, [])
        q_verleihe = nach_quittung_v.get(q.ID, [])
        gruppen = [auftrag_gruppe(a) for a in q_auftraege] + [verleih_gruppe(v) for v in q_verleihe]
        kunden = {k.ID: k for k in [a.kunde for a in q_auftraege] + [v.Kunde for v in q_verleihe] if k is not None}
        kunde = _quittung_kunde(kunden)
        liste.append(QuittungListeEintrag(
            ID=q.ID,
            Nummer=quittung_nummer(q),
            Name=q.Name,
            Erstellt_Am=q.Erstellt_Am,
            Bezahlt_Am=q.Bezahlt_Am,
            Bezahlt=bool(q.Bezahlt),
            Zahlart=zahlart_text(q.Bar, q.Karte, q.Ueberweisung),
            Betrag=round(sum(a.preis * a.anzahl for g in gruppen for a in g.artikels), 2),
            Kunde=kunde.name if kunde else None,
            Bezuege=[QuittungBezug(art="auftrag", id=a.id, name=a.name) for a in q_auftraege]
                    + [QuittungBezug(art="verleih", id=v.ID, name=v.Name) for v in q_verleihe],
            NurExtern=bool(q.NurExtern),
            LexID=q.LexID or None,
            BuchhaltungSync=bool(q.BuchhaltungSync),
            artikelgruppen=gruppen,
        ))
    return liste

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
            nummer=quittung_nummer(quittung),
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

           
        # Kunden der Aufträge und Verleihe, nach ID
        kunden: dict[int, SkiKunde] = {}
        for artikel in quittung.artikels:
            if artikel.Auftrag_ID is not None:
                quittungOut.artikelgruppen.append(_AuftragzuArtikel(artikel.Auftrag_ID, self.db))
                # Bereits geladen, db.get liest aus der Session
                auftrag = self.db.get(Auftrag, artikel.Auftrag_ID)
                if auftrag and auftrag.kunde:
                    kunden[auftrag.kunde.ID] = auftrag.kunde

            if artikel.Verleih_ID is not None:
                quittungOut.artikelgruppen.append(_VerleihzuArtikel(artikel.Verleih_ID, self.db))
                verleih = self.db.get(SaisonVerleih, artikel.Verleih_ID)
                if verleih and verleih.Kunde:
                    kunden[verleih.Kunde.ID] = verleih.Kunde

        quittungOut.kunde = _quittung_kunde(kunden)
        
        return quittungOut

    def renderPDF(self, data: QuittungOutSchema) -> bytes:
        FIRMA = {
            "name": einstellungen.hole("FIRMA_NAME"),
            "strasse": einstellungen.hole("FIRMA_STRASSE"),
            "ort": einstellungen.hole("FIRMA_ORT"),
            "telefon": einstellungen.hole("FIRMA_TELEFON"),
            "email": einstellungen.hole("FIRMA_EMAIL"),
            "mwst_satz": einstellungen.hole("FIRMA_MWST_SATZ"),      # z. B. 19 -> zeigt Netto/MwSt. an
            "kleinunternehmer": einstellungen.hole("FIRMA_KLEINUNTERNEHMER"),
        }

        summe = round(sum(a.preis * a.anzahl for g in data.artikelgruppen for a in g.artikels), 2)

        # Bankverbindung immer, GiroCode nur bei Überweisung
        bank = None
        girocode = None
        verwendungszweck = None
        iban = einstellungen.hole("BANK_IBAN")
        if iban:
            inhaber = (einstellungen.hole("BANK_KONTOINHABER") or "").strip() or FIRMA["name"]
            bic = einstellungen.hole("BANK_BIC") or None
            bank = {"inhaber": inhaber, "iban": iban_formatiert(iban), "bic": bic, "name": einstellungen.hole("BANK_NAME")}
            if data.ueberweisung and summe > 0:
                # z.B. "Quittung 12 · 26/27S5, 26/27SV7"
                nummern = [g.bezeichnung.split(" - ")[1] for g in data.artikelgruppen if g.bezeichnung.count(" - ") >= 1]
                verwendungszweck = data.nummer + (f" - {', '.join(nummern)}" if nummern else "")
                girocode = girocode_png_data_uri(inhaber, iban, bic, summe, verwendungszweck)

        html = templates.get_template("quittung.html").render(
            quittung=data, firma=FIRMA, heute=_datum(date.today()),
            summe=summe, bank=bank, girocode=girocode, verwendungszweck=verwendungszweck,
        )
        pdf = HTML(string=html, base_url=str(templates)).write_pdf()

        if not pdf:
            raise HTTPException(status_code=404, detail="PDF konnte nicht erstellt werden")

        return pdf


def quittung_pdf(db: Session, quittung: Quittung) -> tuple[bytes, str]:
    """
    PDF und Dateiname einer Quittung. Externe Quittung: das Original kommt aus Lexware (kann LexwareFehler werfen).
    """
    if quittung.NurExtern and quittung.LexID:
        pdf, dateiname = LexwareAPI().hole_rechnung_pdf(quittung.LexID)
        return pdf, dateiname or quittung_dateiname(quittung)
    service = QuittungsService(db)
    return service.renderPDF(service.get_quittung(quittung.ID)), quittung_dateiname(quittung)
