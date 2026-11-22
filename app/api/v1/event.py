from fastapi import APIRouter, Request, Depends
from app.core.zugriff import Zugriff, angemeldet, geraet_oder_angemeldet, recht
from fastapi.responses import StreamingResponse
import asyncio
import json

from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.utils.terminalmanager import KundenTerminalManager
from app.schemas.kunde import SkiKundeZuTerminal, SkiKundeTerminal
from app.crud import kunde as crud_kunde


router = APIRouter(
    prefix="/event",
    tags=["events"],
    responses={404: {"description": "Not found"}},
)

# Server Event https://www.youtube.com/watch?v=M4glLwqDEBw&t=842s

# Initialize the terminal manager
terminal_manager = KundenTerminalManager()

# Abstand der Heartbeats an die Terminals
HEARTBEAT_SEKUNDEN = 15

@router.get("/test", dependencies=[Depends(angemeldet)])
async def test(request: Request):
    async def event_stream():
        for i in range(10):
            yield f"data: Event {i}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.get("/terminals", dependencies=[Depends(angemeldet)])
async def list_terminals(request: Request):
    terminals = terminal_manager.list_terminale()
    ohne = sorted(t for t in terminals if t in terminal_manager.ohne_schluessel)
    return {"terminals": terminals, "ohne_schluessel": ohne}

@router.post("/zeigekunde", dependencies=[Depends(recht("kunden.bearbeiten"))])
async def zeige_kunde(daten: SkiKundeZuTerminal, request: Request, db: Session = Depends(get_db)):
    if daten.terminal not in terminal_manager.verbindungen:
        return {"status": "Terminal not connected", "terminal": daten.terminal}
    
    # Kunde abfragen
    kunde = crud_kunde.get_kunde(db, daten.kunde_id)
    if not kunde:
        return {"status": "Kunde not found", "kunde_id": daten.kunde_id}

    # Nachricht an die Warteschlange des Terminals senden
    payload = {
        "command": "zeige_kunde",
        "kunde": SkiKundeTerminal.model_validate(kunde).model_dump()
    }

    await terminal_manager.send_message(daten.terminal,json.dumps(payload))
      
    return {"status": "zeige_kunde command sent"}

@router.post("/send/{terminal}", dependencies=[Depends(angemeldet)])
async def send_message(request: Request, terminal: str):
    if terminal not in terminal_manager.verbindungen:
        return {"status": "Terminal not connected", "terminal": terminal}
    
    await terminal_manager.send_message(terminal, "Hello from the server!")
    return {"status": "Message sent", "terminal": terminal}


@router.get("/connect/{terminal}")
async def connect_terminal(request: Request, terminal: str,
                           zugriff: Zugriff = Depends(geraet_oder_angemeldet("terminal"))):
    """SSE für das Kundenterminal. EventSource kann keine Header senden: Schlüssel bzw. Anmeldung kommen als ?ticket=."""

    async def event_stream(terminal: str):
        queue = await terminal_manager.connect(terminal, mit_schluessel=zugriff.schluessel is not None)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SEKUNDEN)
                except asyncio.TimeoutError:
                    # Heartbeat: eine abgerissene Verbindung fällt beim Schreiben auf,
                    # das Terminal erkennt daran, dass die Verbindung noch lebt
                    yield "event: ping\ndata: \n\n"
                    continue
                yield f"data: {message}\n\n"
        finally:
            await terminal_manager.disconnect(terminal, queue)

    return StreamingResponse(
        event_stream(terminal),
        media_type="text/event-stream",
        # Kein Puffern durch Proxy (z.B. nginx), sonst kommt der Heartbeat nicht an
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


                
    