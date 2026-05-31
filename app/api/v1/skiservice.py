from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud import skiservice as crud_skiservice
from app.schemas.skiservice import AuftragSchema, AuftragSkiFertigSchema

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

    auftrag = crud_skiservice.setzeSkiFertig(db, AuftragSkiFertig.id, AuftragSkiFertig.ski_ids)
    if not auftrag:
        raise HTTPException(status_code=404, detail="Auftrag nicht gefunden")
    return auftrag