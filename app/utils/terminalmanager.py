import asyncio


class KundenTerminalManager():
    def __init__(self):
        """Initialisiert den Terminal Manager."""
        self.verbindungen: dict[str, asyncio.Queue] = {}
        # Terminals, die ohne Geräteschlüssel verbunden sind (Übergang)
        self.ohne_schluessel: set[str] = set()

    def list_terminale(self) -> list[str]:
        """Gibt eine Liste der verbundenen Terminals zurück."""
        return list(self.verbindungen.keys())

    async def connect(self, terminal: str, mit_schluessel: bool = False) -> asyncio.Queue:
        # Teporäre Warteschlange für das Terminal
        q = asyncio.Queue()
        self.verbindungen[terminal] = q
        if mit_schluessel:
            self.ohne_schluessel.discard(terminal)
        else:
            self.ohne_schluessel.add(terminal)
        return q
    
    async def disconnect(self, terminal: str, queue: asyncio.Queue):
        # Nur die eigene Verbindung entfernen: hat sich das Terminal inzwischen neu verbunden,
        # gehört der Eintrag schon der neuen Verbindung
        if self.verbindungen.get(terminal) is queue:
            del self.verbindungen[terminal]
            self.ohne_schluessel.discard(terminal)
        
    async def send_message(self, terminal: str, message: str):
        if terminal not in self.verbindungen:
            raise ValueError(f"Terminal {terminal} not connected.")
        
        # Nachricht an die Warteschlange des Terminals senden
        await self.verbindungen[terminal].put(message)