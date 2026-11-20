from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from app.core.zugriff import Zugriff, angemeldet, anmeldung_erzwungen, geraet_oder_angemeldet, nur_admin, zugriff_aus_ticket
from sqlalchemy.orm import Session

from app.api.v1.health import health_antwort
from app.schemas.scanner import ScanAntwort, ScannerGeraet, ScannerMeldung, ScannerRead
from app.services.scanner import scan_auswerten
from app.utils.scannerregister import ScannerUnbekannt, UpdateNichtMoeglich, scanner_register
from app.utils.skiscannerguimanager import scanner_gui_manager as scanner_manager
from app.db.deps import get_db

router = APIRouter(
    prefix="/scanner/skiscanner",
    tags=["Scanner"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test", dependencies=[Depends(angemeldet)])
async def test():
    return {"message": "Skiscanner API is working!"}

@router.post("/scan", response_model=ScanAntwort)
async def scan(scanner_data: ScannerRead, db: Session = Depends(get_db),
               zugriff: Zugriff = Depends(geraet_oder_angemeldet("scanner"))):
    """
    Wertet einen Scan vom Skiscanner aus, je nach Modus (trigger):
    1 = Fertigstellen (nur Service-Etiketten), 2 = Bindung geprüft (Service- und Verleih-Etiketten).
    """
    scanner_register.melden(ScannerMeldung(name=scanner_data.name, modus=scanner_data.trigger),
                            schluessel=zugriff.schluessel.name if zugriff.schluessel else None)
    return await scan_auswerten(db, scanner_data)


@router.post("/melden")
def melden(meldung: ScannerMeldung, db: Session = Depends(get_db),
           zugriff: Zugriff = Depends(geraet_oder_angemeldet("scanner"))):
    """
    Health-Check des Scanners (alle 30 s): trägt ihn als verbunden ein und prüft wie /health die Datenbank.
    Bei nicht erreichbarer Datenbank 503.
    Wurde im Center ein Firmware-Update angestoßen, steht einmalig "update": true in der Antwort:
    der Scanner prüft dann selbst auf eine neue Firmware und installiert sie.
    """
    antwort = health_antwort(db)
    # Bei einem Datenbankfehler (503) bleibt die Anforderung für die nächste Meldung stehen
    if scanner_register.melden(meldung, health_check=isinstance(antwort, dict),
                               schluessel=zugriff.schluessel.name if zugriff.schluessel else None):
        antwort["update"] = True
    return antwort


@router.get("/geraete", response_model=list[ScannerGeraet], dependencies=[Depends(angemeldet)])
def geraete():
    """Alle Scanner, die sich in den letzten 24 h gemeldet haben, mit verbunden = Meldung in den letzten 75 s."""
    return scanner_register.liste()


@router.post("/geraete/{name}/update", response_model=ScannerGeraet, dependencies=[Depends(nur_admin)])
def update_anstossen(name: str):
    """
    Stößt das Firmware-Update eines Scanners an. Er erfährt es bei seiner nächsten Meldung (spätestens nach 30 s).
    """
    try:
        return scanner_register.update_anfordern(name)
    except ScannerUnbekannt:
        raise HTTPException(status_code=404, detail="Scanner nicht gefunden.")
    except UpdateNichtMoeglich as fehler:
        raise HTTPException(status_code=409, detail=str(fehler))


@router.websocket("/data")
async def websocket_endpoint(websocket: WebSocket):
    # Kein Header möglich: angemeldet über ?ticket= (POST /auth/ticket), ohne Ticket nur im Übergang
    ticket = websocket.query_params.get("ticket")
    try:
        zugriff = zugriff_aus_ticket(ticket, websocket.url.path) if ticket else None
    except HTTPException:
        zugriff = None
    if (zugriff is None or zugriff.benutzer is None) and (ticket or anmeldung_erzwungen()):
        # Erst annehmen, dann schließen: so sieht der Browser den Code 4401 und holt ein neues Ticket
        await websocket.accept()
        await websocket.close(code=4401)
        return
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