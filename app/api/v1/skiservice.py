from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from app.core.zugriff import pruefe_recht, recht
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Literal, Optional

from app.db.deps import get_db
from app.crud import skiservice as crud_skiservice
from app.crud import skiservicepreis as crud_skiservicepreis

from app.schemas.skiservice import AuftragSchema, AuftragSkiFertigSchema, AuftragCreateSchema, SkiBindungFertigSchema, AuftragUpdateSchema, AuftragAbgeholtSetzen, SkiCreateSchema, SkiUpdateSchema
from app.schemas.scanner import ScannerRead, TriggerStatus, ScannerWebSocketMessage
from app.schemas.mailstatus import MailStatus
from app.schemas.skiservicepreise import SkiServicePreiseBase, SkiServicePreiseSchema

from app.utils.skiscannerguimanager import scanner_gui_manager as scanner_manager
from app.utils.mail import sendeFertigMail, skizusammenfassen

from app.services import skiserviceauftrag
from app.services.bezahlstatus import auftrag_bezahlt_setzen
from app.schemas.quittung import BezahltSetzen

router = APIRouter(
    prefix="/skiservice",
    tags=["Skiservice"],
    responses={404: {"beschreibung": "Aufruf kann nicht gefunden wernde!"}},
)

@router.get("/", response_model=list[AuftragSchema])
async def skiauftragListe(
    saisonID: Optional[int] = Query(default=None, description="ID der Saison für die Filterung der Service-Einträge, keine ist die aktelle Saison"),
    limit: int = Query(default=15, le=100), 
    last_id: Optional[int] = Query(default=None, description="ID des letzten Eintrags der vorherigen Seite für die Pagination"),
    alle: bool = Query(default=False, description="Alle Einträge ohne Pagination zurückgeben"),
    sortierung: Literal["neueste", "aelteste"] = Query(default="neueste", description="Zuletzt oder zuerst erfasste oben"),
    suche: Optional[str] = Query(default=None, max_length=100, description="Teil von Vor- und/oder Nachname des Kunden"),
    status: Optional[Literal["bearbeitung", "fertig", "abgeholt"]] = Query(default=None, description="Nur Aufträge mit diesem Status"),
    bezahlt: Optional[Literal["ja", "nein"]] = Query(default=None, description="Nur bezahlte bzw. offene Aufträge"),
    benachrichtigt: Optional[Literal["ja", "nein"]] = Query(default=None, description="Nur benachrichtigte bzw. nicht benachrichtigte Aufträge"),
    erledigte: bool = Query(default=True, description="false blendet erledigte Aufträge aus (abgeholt und bezahlt)"),
    db: Session = Depends(get_db)
):
    """
    Listet alle Skiservice auf
    """
    return crud_skiservice.get_skiservice_liste(db, limit, last_id, saisonID, alle, sortierung, suche, status, bezahlt, benachrichtigt, erledigte)

@router.get("/test")
async def test():
    return {"message": "Skiservice API is working!"}

@router.get("/auftrag/{skiservice_auftrag_id}", response_model=AuftragSchema)
async def get_auftrag(skiservice_auftrag_id: int, db: Session = Depends(get_db)):
    """
    Gibt die Details eines Skiservice-Auftrags zurück.
    """
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, skiservice_auftrag_id)
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return auftrag


async def _fertig_mail(db: Session, auftrag, auftragSchema: AuftragSchema) -> tuple[MailStatus, str]:
    """
    Sendet die Fertig-Mail, wenn der Kunde noch nicht benachrichtigt wurde.
    Gibt den Mail-Status für den Hinweis auf der Scanner-Seite und einen Text für die Meldung zurück.
    """
    if (auftrag.benachrichtigt or "").lower() != "nein":
        return None, " Kunde wurde bereits benachrichtigt."
    if await run_in_threadpool(sendeFertigMail, auftragSchema):
        crud_skiservice.setzeBenachrichtigt(db, auftrag.id, benachrichtigt=True)
        return "gesendet", " und Kunde benachrichtigt."
    if auftragSchema.kunde and auftragSchema.kunde.Email:
        # Ohne Adresse ist nichts fehlgeschlagen, dafür hat das Center einen eigenen Hinweis
        return "fehlgeschlagen", " E-Mail an den Kunden konnte nicht gesendet werden."
    return None, ""


@router.post("/skifertig", dependencies=[Depends(recht("skiservice.status"))])
async def skifertig(AuftragSkiFertig: AuftragSkiFertigSchema, db: Session = Depends(get_db)):
    """
    Endpoint, der aufgerufen wird, wenn ein Ski fertig bearbeitet ist.
    """

    auftrag, alleSkiFertig = crud_skiservice.setzeSkiFertig(db, AuftragSkiFertig.id, AuftragSkiFertig.ski_ids)

    nachricht = "Es wurde nicht alles sauber übergeben"
    
    # Wen kein Auftrag gefunden wurde, wird eine 404-Fehlermeldung zurückgegeben
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    
    nachricht = "Ski fertig bearbeitet: Ski IDs {}".format(AuftragSkiFertig.ski_ids)

    auftragSchema = AuftragSchema.model_validate(auftrag)
    # Ergebnis der Fertig-Mail, für den Hinweis auf der Scanner-Seite
    mail: MailStatus = None

    if alleSkiFertig:
        nachricht = " Alle Ski sind fertig bearbeitet."
        if not AuftragSkiFertig.mail:
            nachricht = " Alle Ski sind fertig bearbeitet (ohne Mail)."
        elif not crud_skiservice.fertig_mail_faellig(auftrag):
            # Einstellung "Service + Bindung": die Mail geht erst nach der letzten Bindungsprüfung raus
            nachricht += " Fertig-Mail folgt nach der Bindungsprüfung."
        else:
            mail, text = await _fertig_mail(db, auftrag, auftragSchema)
            nachricht += text

    await scanner_manager.sende_data_broadcast(ScannerWebSocketMessage(
        message=nachricht,
        success=True,
        scannername=None,
        ski_id=None,
        service_id=AuftragSkiFertig.id,
        data=auftragSchema if auftrag else None,
        mail=mail,
    ))

    # Auftrag wie bisher, ergänzt um das Ergebnis der Mail
    return {**jsonable_encoder(auftrag), "mail": mail}

@router.post("/bindungfertig", dependencies=[Depends(recht("skiservice.status"))])
async def bindungfertig(SkisChecked: SkiBindungFertigSchema, db: Session = Depends(get_db)):
    """
    Endpunkt der eine Bindung auf geprüft setzt
    """
    auftrag_ids = crud_skiservice.setzeBindungGeprueft(db, SkisChecked.ski_ids)

    if not auftrag_ids:
        raise HTTPException(status_code=404, detail="Keine Skis gefunden")

    # Ergebnis der Fertig-Mail, für den Hinweis auf der Scanner-Seite (bei mehreren Aufträgen das erste)
    antwort_mail: MailStatus = None

    # Wie beim Fertigstellen: Statusmeldung ohne Scannername, damit andere Tablets
    # und das Werkstatt-Dashboard gleich neu laden
    for auftrag_id in auftrag_ids:
        nachricht = "Bindung geprüft"
        mail: MailStatus = None
        auftrag = crud_skiservice.getSkiserviceAuftrag(db, auftrag_id)
        # Bei Einstellung "Service + Bindung" geht die Fertig-Mail nach der letzten Bindungsprüfung raus,
        # sonst wurde sie schon beim Fertigstellen gesendet (benachrichtigt) und hier passiert nichts
        if auftrag is not None and crud_skiservice.fertig_mail_faellig(auftrag):
            mail, text = await _fertig_mail(db, auftrag, AuftragSchema.model_validate(auftrag))
            if mail is not None:
                nachricht += "." + text
        antwort_mail = antwort_mail or mail
        await scanner_manager.sende_data_broadcast(ScannerWebSocketMessage(
            message=nachricht,
            success=True,
            service_id=auftrag_id,
            mail=mail,
        ))

    return {"success": True, "mail": antwort_mail}

@router.get("/preise", response_model=list[SkiServicePreiseSchema])
async def get_preise(db: Session = Depends(get_db)):
    preise = crud_skiservicepreis.get_ski_service_preise(db)
    return preise

@router.post("/preise", response_model=SkiServicePreiseSchema, dependencies=[Depends(recht("preise.verwalten"))])
async def create_preis(preis: SkiServicePreiseBase, db: Session = Depends(get_db)):
    new_preis = crud_skiservicepreis.create_ski_service_preis(db, preis)
    return new_preis

@router.post("/neu", response_model=AuftragSchema, dependencies=[Depends(recht("skiservice.anlegen"))])
async def erstelle_auftrag(auftrag: AuftragCreateSchema, hintergrundProzess: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Skiservice-Auftrag.
    """
    new_auftrag = crud_skiservice.createSkiserviceAuftrag(db, auftrag)
    if not new_auftrag:
        raise HTTPException(status_code=400, detail="Auftrag konnte nicht angelegt werden.")

    # SQLAlchemy zu Pydantic
    skiauftrag = AuftragSchema.model_validate(new_auftrag)

    # Drucken im Hintergrund
    hintergrundProzess.add_task(skiserviceauftrag.skiServiceEttiketDrucken, skiauftrag)

    return skiauftrag

@router.post("/bindungsservice", response_model=SkiServicePreiseSchema, dependencies=[Depends(recht("preise.verwalten"))])
async def set_bindungsservice(bindungsserviceid: int, db: Session = Depends(get_db)):
    """
    Setzt den Bindungsservice für einen Skiservice-Auftrag.
    """
    updated_preis = crud_skiservicepreis.setze_bindungsservice(db, bindungsserviceid)
    if not updated_preis:
        raise HTTPException(status_code=404, detail="Bindungsservice nicht gefunden")
    return updated_preis

# --- Bearbeiten / Löschen ---

def _auftrag_oder_404(auftrag):
    if auftrag is None:
        raise HTTPException(status_code=404, detail="Auftrag oder Ski nicht gefunden")
    return auftrag


@router.patch("/auftrag/{skiservice_auftrag_id}", response_model=AuftragSchema)
def aendere_auftrag(skiservice_auftrag_id: int, daten: AuftragUpdateSchema, db: Session = Depends(get_db)):
    """
    Ändert Kunde, Abholdatum oder den Benachrichtigt-Status eines Auftrags
    (z.B. wenn der Kunde angerufen statt per Mail informiert wurde).
    """
    return _auftrag_oder_404(crud_skiservice.aendereAuftrag(db, skiservice_auftrag_id, daten))


@router.patch("/auftrag/{skiservice_auftrag_id}/bezahlt", response_model=AuftragSchema)
def setze_auftrag_bezahlt(skiservice_auftrag_id: int, daten: BezahltSetzen, db: Session = Depends(get_db)):
    """
    Setzt den Auftrag von Hand auf bezahlt oder nicht bezahlt.
    Mit mit_quittung werden die Quittung und alle Positionen darauf ebenfalls geändert.
    Mit quittung_entfernen wird bei "nicht bezahlt" nur dieser Auftrag von der Quittung genommen.
    """
    if daten.quittung_entfernen:
        pruefe_recht("quittungen.verwalten")
    if auftrag_bezahlt_setzen(db, skiservice_auftrag_id, daten.bezahlt, daten.mit_quittung, daten.quittung_entfernen) is None:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return crud_skiservice.getSkiserviceAuftrag(db, skiservice_auftrag_id)

@router.patch("/auftrag/{skiservice_auftrag_id}/abgeholt", response_model=AuftragSchema, dependencies=[Depends(recht("skiservice.status"))])
def setze_auftrag_abgeholt(skiservice_auftrag_id: int, daten: AuftragAbgeholtSetzen, db: Session = Depends(get_db)):
    """
    Setzt den Auftrag auf abgeholt (mit Datum) oder nimmt die Abholung zurück, auch bei bezahlten Aufträgen.
    """
    return _auftrag_oder_404(crud_skiservice.setzeAbgeholt(db, skiservice_auftrag_id, daten.abgeholt))


@router.post("/auftrag/{skiservice_auftrag_id}/benachrichtigen", response_model=AuftragSchema, dependencies=[Depends(recht("skiservice.status"))])
def benachrichtige_kunde(skiservice_auftrag_id: int, db: Session = Depends(get_db)):
    """
    Versendet die Fertig-Mail von Hand (auch erneut) und setzt den Auftrag auf benachrichtigt.
    """
    auftrag = _auftrag_oder_404(crud_skiservice.getSkiserviceAuftrag(db, skiservice_auftrag_id))
    if not auftrag.kunde or not auftrag.kunde.Email:
        raise HTTPException(status_code=400, detail="Beim Kunden ist keine E-Mail Adresse hinterlegt.")
    if not sendeFertigMail(AuftragSchema.model_validate(auftrag)):
        raise HTTPException(status_code=502, detail="Die E-Mail konnte nicht versendet werden.")
    crud_skiservice.setzeBenachrichtigt(db, skiservice_auftrag_id, benachrichtigt=True)
    return crud_skiservice.getSkiserviceAuftrag(db, skiservice_auftrag_id)


@router.delete("/auftrag/{skiservice_auftrag_id}", dependencies=[Depends(recht("skiservice.loeschen"))])
def loesche_auftrag(skiservice_auftrag_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Auftrag mit allen Ski. Bezahlte Aufträge können nicht gelöscht werden.
    """
    try:
        if not crud_skiservice.loescheAuftrag(db, skiservice_auftrag_id):
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    except crud_skiservice.AuftragGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"success": True}


@router.post("/auftrag/{skiservice_auftrag_id}/ski", response_model=AuftragSchema)
def fuege_ski_hinzu(skiservice_auftrag_id: int, ski: SkiCreateSchema, db: Session = Depends(get_db)):
    try:
        return _auftrag_oder_404(crud_skiservice.fuegeSkiHinzu(db, skiservice_auftrag_id, ski))
    except crud_skiservice.AuftragGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/auftrag/{skiservice_auftrag_id}/ski/{ski_id}", response_model=AuftragSchema)
def aendere_ski(skiservice_auftrag_id: int, ski_id: int, daten: SkiUpdateSchema, db: Session = Depends(get_db)):
    """
    Ändert Service, Preis, Kommentar, Bindung oder den Fertig-Status eines Ski.
    Bei bezahlten Aufträgen können nur Kommentar und Status geändert werden.
    """
    try:
        return _auftrag_oder_404(crud_skiservice.aendereSki(db, skiservice_auftrag_id, ski_id, daten))
    except crud_skiservice.AuftragGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/auftrag/{skiservice_auftrag_id}/ski/{ski_id}", response_model=AuftragSchema)
def entferne_ski(skiservice_auftrag_id: int, ski_id: int, db: Session = Depends(get_db)):
    try:
        return _auftrag_oder_404(crud_skiservice.entferneSki(db, skiservice_auftrag_id, ski_id))
    except crud_skiservice.AuftragGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))
