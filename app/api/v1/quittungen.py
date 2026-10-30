import httpx
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.db.deps import get_db
from app.crud import quittung as crud_quittung
from app.crud import saisonverleih as crud_saisonverleih
from app.crud import skiservice as crud_skiservice
from app.schemas.quittung import QuittungListeEintrag, QuittungNurExtern, QuittungRead, QuittungOutSchema
from app.utils.lexware import LexwareAPI
from app.services import einstellungen
from app.services. quittung import QuittungsService, quittung_pdf, quittungen_liste
from app.schemas.kasse import QuittungMailAnfrage, QuittungMailErgebnis
from app.utils.mail import sendeQuittungMail
from app.crud import saison as crud_saison
from app.services.lexware_sync import SyncKonflikt, quittung_pdf_hochladen
from app.utils.lexware import LexwareFehler

router = APIRouter(
    prefix="/quittungen",
    tags=["quittungen"],
    responses={404: {"description": "Not found"}},
)

lexware_api = LexwareAPI()
logger = logging.getLogger(__name__)

@router.get("/lexware/belege")
async def get_lexware_belege(
        page: Optional[int] = Query(default=0, description="Seitenzahl für die Paginierung der Belege von Lexware, beginnend bei 0")
    ):
    """
    Holt die Belege von Lexoffice.
    """
    try:
        # Standardmäßig wird die erste Seite (page=0) abgerufen, wenn kein Wert angegeben ist.
        if page is None:
            page = 0

        belege_data = lexware_api.get_belege(page=page)
        return belege_data
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

@router.get("/lexware/{lex_quittung_id}")
async def get_lexware_quittung(lex_quittung_id: str):
    """
    Holt den Bezahlstatus einer Quittung von Lexoffice anhand der Quittungs-ID.
    """
    try:
        quittung_data = lexware_api.get_bezahlstatus(lex_quittung_id)
        return quittung_data
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    
@router.get("/liste", response_model=list[QuittungListeEintrag])
def liste_quittungen(saison: Optional[int] = None, db: Session = Depends(get_db)):
    """Alle Quittungen einer Saison (ohne Angabe die aktuelle), neueste zuerst, mit Artikeln."""
    if saison is None:
        aktuelle = crud_saison.get_AktuelleSaison(db)
        if aktuelle is None:
            raise HTTPException(status_code=404, detail="Keine aktuelle Saison gefunden")
        saison = aktuelle.ID
    return quittungen_liste(db, saison)

@router.get("/quittung/{quittung_id}", response_model=QuittungRead)
async def get_quittung(quittung_id: int, bezahlinfo: bool = False, db: Session = Depends(get_db)):
    """
    Holt eine Quittung anhand der ID.
    mir bezahlinfo = True werden die Bezahlinformationen von Lexware mit abgefragt und in die Antwort integriert.
    """
    quittung = crud_quittung.get_quittung(db, quittung_id)
    if not quittung:
        raise HTTPException(status_code=404, detail="Quittung not found")
    # Nur Quittungen, die in Lexware angelegt sind, haben dort einen Bezahlstatus
    if bezahlinfo and quittung.LexID and einstellungen.hole("LEXWARE_APIKEY"):
        try:
    
            # TODO Datum für Lex Sync in DB Speichern
            bezahlinfo_data = lexware_api.get_bezahlstatus(quittung.LexID)
            lexBez = False
            if bezahlinfo_data["voucherStatus"] == "paid":
                quittung.Bezahlt = True
                # Parse ISO 8601 datetime and convert to date
                if bezahlinfo_data["paidDate"]:
                    paid_date = datetime.fromisoformat(bezahlinfo_data["paidDate"].replace('Z', '+00:00'))
                    quittung.Bezahlt_Am = paid_date.date()
                else:
                    quittung.Bezahlt_Am = None
                db.commit()
                db.refresh(quittung)
                lexBez = True
            else:
                quittung.Bezahlt = False
                quittung.Bezahlt_Am = None
                db.commit()
                db.refresh(quittung)

           

            lexOffenerBetrag = -1
            lexOffenerBetrag = bezahlinfo_data.get("openAmount")

            lexBezahltAm = None
            if bezahlinfo_data.get("paidDate"):
                # Parse ISO 8601 datetime and convert to date for response
                paid_date = datetime.fromisoformat(bezahlinfo_data["paidDate"].replace('Z', '+00:00'))
                lexBezahltAm = paid_date.date()

            bezInfo = {
                "Bezahlt": lexBez,
                "Bezahlt_Am": lexBezahltAm,
                "Offener_Betrag": lexOffenerBetrag
            }

                # eigenes Response Model mit Bezahlinfo erstellen
            quittungResponse = {
                ** quittung.__dict__,
                "Nummer": quittung.Nummer,
                "ManuellZugewiesen": quittung.ManuellZugewiesen,
                "BezahlInfo": bezInfo
            }
            return quittungResponse

        except httpx.HTTPError:
            # Lexware nicht erreichbar oder Beleg dort unbekannt (z.B. falsch zugewiesen):
            # Quittung trotzdem ohne Bezahlinfo zurückgeben, damit die Zuweisung korrigiert werden kann
            logger.exception("Bezahlstatus von Lexware konnte nicht abgerufen werden")
    return quittung

@router.post("/quittung/{quittung_id}/lexware", response_model=QuittungRead)
def quittung_nach_lexware(quittung_id: int, db: Session = Depends(get_db)):
    """
    Lädt eine eigene Quittung als Beleg mit PDF nach Lexware hoch (z.B. wenn der automatische Upload fehlgeschlagen ist).
    """
    try:
        quittung = quittung_pdf_hochladen(db, quittung_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SyncKonflikt as e:
        raise HTTPException(status_code=409, detail=str(e))
    except LexwareFehler as e:
        raise HTTPException(status_code=502, detail=str(e))
    return crud_quittung.get_quittung(db, quittung.ID)

@router.get("/quittung/{quittung_id}/pdf")
def get_quittung_pdf(quittung_id: int, db: Session = Depends(get_db)):
    """
    Holt das PDF einer Quittung anhand der ID.
    """
    quittung = crud_quittung.get_quittung(db, quittung_id)
    if quittung is None:
        raise HTTPException(status_code=404, detail="Quittung nicht gefunden")

    pdf, dateiname = _quittung_pdf_oder_fehler(db, quittung)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{dateiname}"'},
    )


def _quittung_pdf_oder_fehler(db: Session, quittung) -> tuple[bytes, str]:
    try:
        return quittung_pdf(db, quittung)
    except LexwareFehler as e:
        # Externe Quittung: das Original liegt in Lexware
        raise HTTPException(status_code=502, detail=f"PDF konnte nicht aus Lexware geladen werden: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))


@router.post("/quittung/{quittung_id}/mail", response_model=QuittungMailErgebnis)
def sende_quittung_mail(quittung_id: int, anfrage: QuittungMailAnfrage, db: Session = Depends(get_db)):
    """
    Versendet die Quittung als PDF an eine oder mehrere Adressen, an jede eine eigene Mail.
    """
    quittung = crud_quittung.get_quittung(db, quittung_id)
    if quittung is None:
        raise HTTPException(status_code=404, detail="Quittung nicht gefunden")

    pdf, dateiname = _quittung_pdf_oder_fehler(db, quittung)
    ergebnis = QuittungMailErgebnis(gesendet=[], fehlgeschlagen=[])
    # Doppelte Adressen nur einmal senden
    emails: dict[str, str] = {}
    for e in anfrage.emails:
        emails.setdefault(e.lower(), e)
    for email in emails.values():
        if sendeQuittungMail(email, quittung.Nummer, pdf, dateiname):
            ergebnis.gesendet.append(email)
        else:
            ergebnis.fehlgeschlagen.append(email)

    if not ergebnis.gesendet:
        raise HTTPException(status_code=502, detail="Die E-Mail konnte nicht versendet werden.")
    return ergebnis
    
@router.get("/quittung/{quittung_id}/json", response_model=QuittungOutSchema)
async def get_quittung_json(quittung_id: int, db: Session = Depends(get_db)):
    """
    Holt das JSON einer Quittung anhand der ID.
    """
    try:
        return QuittungsService(db).get_quittung(quittung_id)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

@router.post("/quittung/nurextern")
def create_quittung_nur_extern(quittung_data: QuittungNurExtern, db: Session = Depends(get_db)):
    """
    Weist einem Saisonverleih oder einem Skiservice-Auftrag einen externen Lexware-Beleg als Quittung zu.
    Mit ersetzen wird ein bereits von Hand zugewiesener Beleg geändert (Kassen-Quittungen nicht).
    """
    ziel, bisher_id = _quittung_ziel(db, quittung_data.SaisonverleihID, quittung_data.AuftragID)
    if bisher_id is not None:
        if not quittung_data.ersetzen:
            raise HTTPException(status_code=409, detail="Es ist bereits eine Quittung zugewiesen")
        # Falsch gewählten Beleg korrigieren: gleiche Quittung, neuer Lexware-Beleg
        bisher = _manuelle_quittung(db, bisher_id)
        bisher.LexID = quittung_data.LexOfficeID
        db.commit()
        return {"erfolgreich": True, "quittung_id": bisher.ID}

    try:
        neuExQuittung = crud_quittung.create_NurExtern_quittung(db, lexoffice_id=quittung_data.LexOfficeID)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Mit der Quittung verknüpfen
    if quittung_data.SaisonverleihID is not None:
        ziel.QuittungID = neuExQuittung.ID
    else:
        ziel.quittung_id = neuExQuittung.ID
    db.commit()

    return {"erfolgreich": True, "quittung_id": neuExQuittung.ID}


def _quittung_ziel(db: Session, saisonverleih_id: Optional[int], auftrag_id: Optional[int]):
    """Saisonverleih oder Auftrag laden (404), dazu die ID der bisher zugewiesenen Quittung."""
    if (saisonverleih_id is None) == (auftrag_id is None):
        raise HTTPException(status_code=422, detail="Bitte genau eines angeben: SaisonverleihID oder AuftragID.")
    if saisonverleih_id is not None:
        ziel = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id=saisonverleih_id)
        if ziel is None:
            raise HTTPException(status_code=404, detail="Saisonverleih nicht gefunden")
        return ziel, ziel.QuittungID
    ziel = crud_skiservice.getSkiserviceAuftrag(db, auftrag_id, mitski=False)
    if ziel is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return ziel, ziel.quittung_id


def _manuelle_quittung(db: Session, quittung_id: int):
    """Nur von Hand zugewiesene Lexware-Belege dürfen geändert oder aufgehoben werden, keine Kassen-Quittungen."""
    quittung = crud_quittung.get_quittung(db, quittung_id)
    if quittung is None:
        raise HTTPException(status_code=404, detail="Quittung nicht gefunden")
    if not quittung.ManuellZugewiesen:
        raise HTTPException(status_code=409, detail="An der Kasse bezahlte Quittungen können nicht geändert werden")
    return quittung


@router.delete("/quittung/zuweisung")
def hebe_zuweisung_auf(
        SaisonverleihID: Optional[int] = Query(default=None),
        AuftragID: Optional[int] = Query(default=None),
        db: Session = Depends(get_db),
    ):
    """
    Hebt die Zuweisung eines von Hand zugewiesenen Lexware-Belegs auf, z.B. nach einem Vertipper.
    Der Beleg in Lexware bleibt unverändert, die Quittung in der App wird gelöscht.
    """
    ziel, quittung_id = _quittung_ziel(db, SaisonverleihID, AuftragID)
    if quittung_id is None:
        raise HTTPException(status_code=404, detail="Es ist keine Quittung zugewiesen")
    quittung = _manuelle_quittung(db, quittung_id)

    if SaisonverleihID is not None:
        ziel.QuittungID = None
    else:
        ziel.quittung_id = None
    db.flush()
    # Nur löschen, wenn nichts anderes mehr auf die Quittung zeigt
    if not crud_quittung.quittung_verwendet(db, quittung.ID):
        db.delete(quittung)
    db.commit()
    return {"erfolgreich": True}

@router.get("/test")
async def test():
    return {"test": "hier sind die quittungen"}

