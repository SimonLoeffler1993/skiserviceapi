from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.v1.health import health_antwort
from app.schemas.scanner import ScanAntwort, ScannerGeraet, ScannerMeldung, ScannerRead
from app.services.scanner import scan_auswerten
from app.utils.scannerregister import scanner_register
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
    scanner_register.melden(ScannerMeldung(name=scanner_data.name, modus=scanner_data.trigger))
    return await scan_auswerten(db, scanner_data)


@router.post("/melden")
def melden(meldung: ScannerMeldung, db: Session = Depends(get_db)):
    """
    Health-Check des Scanners (alle 30 s): trägt ihn als verbunden ein und prüft wie /health die Datenbank.
    Bei nicht erreichbarer Datenbank 503.
    """
    scanner_register.melden(meldung)
    return health_antwort(db)


@router.get("/geraete", response_model=list[ScannerGeraet])
def geraete():
    """Alle Scanner, die sich in den letzten 24 h gemeldet haben, mit verbunden = Meldung in den letzten 75 s."""
    return scanner_register.liste()


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