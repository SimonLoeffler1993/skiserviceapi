from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.schemas.scanner import ScanAntwort, ScannerRead
from app.services.scanner import scan_auswerten
from app.utils.skiscannerguimanager import scanner_gui_manager as scanner_manager
from app.db.deps import get_db

router = APIRouter(
    prefix="/scanner/skiscanner",
    tags=["Scanner"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Skiscanner API is working!"}

@router.post("/scan", response_model=ScanAntwort)
async def scan(scanner_data: ScannerRead, db: Session = Depends(get_db)):
    """
    Wertet einen Scan vom Skiscanner aus, je nach Modus (trigger):
    1 = Fertigstellen (nur Service-Etiketten), 2 = Bindung geprüft (Service- und Verleih-Etiketten).
    """
    return await scan_auswerten(db, scanner_data)


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