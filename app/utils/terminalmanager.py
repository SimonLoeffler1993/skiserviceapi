import asyncio


class KundenTerminalManager():
    def __init__(self):
        self.verbindungen: dict[str, asyncio.Queue] = {}

    async def connect(self, terminal:str) -> asyncio.Queue:
        # Teporäre Warteschlange für das Terminal
        q = asyncio.Queue()
        self.verbindungen[terminal] = q
        return q
    
    async def disconnect(self, terminal: str):
        self.verbindungen.pop(terminal, None)
        
    async def send_message(self, terminal: str, message: str):
        if terminal not in self.verbindungen:
            raise ValueError(f"Terminal {terminal} not connected.")
        
        # Nachricht an die Warteschlange des Terminals senden
        await self.verbindungen[terminal].put(message)