from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json

from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.utils.terminalmanager import KundenTerminalManager
from app.schemas.kunde import SkiKundeZuTerminal
from app.crud import kunde as crud_kunde


router = APIRouter(
    prefix="/event",
    tags=["events"],
    responses={404: {"description": "Not found"}},
)

# Server Event https://www.youtube.com/watch?v=M4glLwqDEBw&t=842s

# Initialize the terminal manager
terminal_manager = KundenTerminalManager()

@router.get("/test")
async def test(request: Request):
    async def event_stream():
        for i in range(10):
            yield f"data: Event {i}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.get("/terminals")
async def list_terminals(request: Request):
    terminals = terminal_manager.list_terminale()
    return {"terminals": terminals}

@router.post("/zeigekunde")
async def zeige_kunde(daten: SkiKundeZuTerminal, request: Request, db: Session = Depends(get_db)):
    if daten.terminal not in terminal_manager.verbindungen:
        return {"status": "Terminal not connected", "terminal": daten.terminal}
    # Kunde abfragen
    kunde = crud_kunde.get_kunde(db, daten.kunde_id)
    if not kunde:
        return {"status": "Kunde not found", "kunde_id": daten.kunde_id}

    # Nachricht an die Warteschlange des Terminals senden
    await terminal_manager.send_message(daten.terminal,json.dumps({
        "command": "zeige_kunde",
        "kunde": {
            "id": kunde.ID,
            "nachname": kunde.Nachname,
            "vorname": kunde.Vorname,
            "strasse": kunde.Strasse,
            "plz": kunde.Plz,
            "tel": kunde.Tel,
            "email": kunde.Email,
        }
    }))
    return {"status": "zeige_kunde command sent"}

@router.post("/send/{terminal}")
async def send_message(request: Request, terminal: str):
    if terminal not in terminal_manager.verbindungen:
        return {"status": "Terminal not connected", "terminal": terminal}
    
    await terminal_manager.send_message(terminal, "Hello from the server!")
    return {"status": "Message sent", "terminal": terminal}


@router.get("/connect/{terminal}")
async def connect_terminal(request: Request, terminal: str):

    async def event_stream(terminal: str):
        queue = await terminal_manager.connect(terminal)
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await queue.get()
                yield f"data: {message}\n\n"
        finally:
            await terminal_manager.disconnect(terminal)

    return StreamingResponse(event_stream(terminal), media_type="text/event-stream")


                
    