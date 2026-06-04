import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from urllib.parse import urlparse, parse_qs
from sqlalchemy.orm import Session

from app.schemas.scanner import ScannerRead, TriggerStatus, ScannerWebSocketMessage
from app.schemas.skiservice import AuftragSchema
from app.utils.skiscannerguimanager import scanner_gui_manager as scanner_manager
from app.crud import skiservice as crud_skiservice
from app.db.deps import get_db

router = APIRouter(
    prefix="/scanner/skiscanner",
    tags=["Scanner"],
    responses={404: {"description": "Not found"}},
)

def codeURL2SaisonID(codeURL: str):
    parsed_url = urlparse(codeURL)
    service_id = parsed_url.path.strip("/").split("/")[-1] or None
    ski_id = parse_qs(parsed_url.query).get("ski", [None])[0] 

    return service_id, ski_id

@router.get("/test")
async def test():
    return {"message": "Skiscanner API is working!"}

@router.post("/scan")
async def scan(scanner_data: ScannerRead, db: Session = Depends(get_db)):
    """
    Wertet die gesendeten Daten vom Skiscanner aus.
    """
    
    if scanner_data.trigger == TriggerStatus.fertig:
        service_id, ski_id = codeURL2SaisonID(scanner_data.code)
        print(f"Scan abgeschlossen. ServiceID: {service_id}, Ski-ID: {ski_id}")

        # ServiceID in Integer umwandeln, falls möglich
        intServiceID = int(service_id) if service_id and service_id.isdigit() else None
        if intServiceID is None:
            print(f"Ungültige ServiceID: {service_id}")
            return {"message": "Ungültige ServiceID im CodeURL", "success": False}
        
        # Datenbankabfrage, um die Auftragsdaten zu erhalten
        skiservicedata = crud_skiservice.getSkiserviceAuftrag(db, intServiceID)

        # Nachricht an alle verbundenen WebSocket-Clients senden
        await scanner_manager.sende_data_broadcast(
            ScannerWebSocketMessage(
                message="Scan abgeschlossen",
                success=True,
                scannername=scanner_data.name,
                ski_id=int(ski_id) if ski_id and ski_id.isdigit() else None,
                service_id=intServiceID,
                data=AuftragSchema.model_validate(skiservicedata) if skiservicedata else None
            )
        )

    return {"message": "Scanning abgeschlossen", "success": True}



@router.websocket("/data")
async def websocket_endpoint(websocket: WebSocket):
    await scanner_manager.verbinden(websocket)
    try:
        while True:
            # Warte auf eine Nachricht von der GUI
            data = await websocket.receive_text()
            await scanner_manager.sende_nachricht_broadcast("Nachricht von GUI:")
            print(f"Nachricht von GUI erhalten: {data}")
    except WebSocketDisconnect:
        await scanner_manager.trennen(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        await scanner_manager.trennen(websocket)