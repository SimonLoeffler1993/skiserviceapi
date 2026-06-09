from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import cast

from app.db.deps import get_db
from app.crud import skiservice as crud_skiservice
from app.crud import skiservicepreis as crud_skiservicepreis

from app.schemas.skiservice import AuftragSchema, AuftragSkiFertigSchema, SkiSchema
from app.schemas.scanner import ScannerRead, TriggerStatus, ScannerWebSocketMessage
from app.schemas.skiservicepreise import SkiServicePreiseSchema

from app.utils.skiscannerguimanager import scanner_gui_manager as scanner_manager
from app.utils.mail import sendeFertigMail, skizusammenfassen

router = APIRouter(
    prefix="/skiservice",
    tags=["Skiservice"],
    responses={404: {"description": "Not found"}},
)

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


@router.post("/skifertig")
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

    if alleSkiFertig:
        nachricht = " Alle Ski sind fertig bearbeitet."
        if auftrag.benachrichtigt.lower() == "nein":
            mailSend = sendeFertigMail(auftragSchema)
            if mailSend:
                crud_skiservice.setzeBenachrichtigt(db, AuftragSkiFertig.id, benachrichtigt=True)
                nachricht += " und Kunde benachrichtigt."
        else:
            nachricht += " Kunde wurde bereits benachrichtigt."

    await scanner_manager.sende_data_broadcast(ScannerWebSocketMessage(
        message=nachricht,
        success=True,
        scannername=None,
        ski_id=None,
        service_id=AuftragSkiFertig.id,
        data=auftragSchema if auftrag else None
    ))

    return auftrag

@router.get("/preise", response_model=list[SkiServicePreiseSchema])
async def get_preise(db: Session = Depends(get_db)):
    preise = crud_skiservicepreis.get_ski_service_preise(db)
    return preise