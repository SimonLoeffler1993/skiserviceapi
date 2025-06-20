from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio

from app.utils.terminalmanager import KundenTerminalManager


router = APIRouter(
    prefix="/event",
    tags=["events"],
    responses={404: {"description": "Not found"}},
)

# Initialize the terminal manager
terminal_manager = KundenTerminalManager()

@router.get("/test")
async def test(request: Request):
    async def event_stream():
        for i in range(10):
            yield f"data: Event {i}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@router.post("/send/{terminal}")
async def send_message(request: Request, terminal: str):
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
                
    