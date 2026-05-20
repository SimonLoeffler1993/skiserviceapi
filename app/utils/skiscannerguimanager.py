from fastapi import WebSocket, WebSocketDisconnect

class SkiScannerGUIManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def verbinden(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)

    async def trennen(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)

    async def sende_nachricht_broadcast(self, message: str):
        for websocket in list(self.active):
            try:
                await websocket.send_text(message)
            except WebSocketDisconnect:
                await self.trennen(websocket)