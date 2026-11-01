from pydantic import BaseModel
from enum import IntEnum
from typing import Literal

from app.schemas.skiservice import AuftragSchema

# TriggerStatus muss mit der ESP Firmware übereinstimmen, damit die Werte korrekt interpretiert werden können
class TriggerStatus(IntEnum):
    bearbeitung = 0
    # Nur Service-Etiketten, der Ski wird im Center fertig gestellt
    fertig = 1
    # Service- und Verleih-Etiketten, die Bindung wird auf geprüft gesetzt
    bindung = 2

class ScannerRead(BaseModel):
    code: str
    name: str
    trigger: TriggerStatus

class ScanAntwort(BaseModel):
    """Antwort an den Scanner, success entscheidet über die LED (grün / rot)."""
    success: bool
    message: str
    # Erkanntes Etikett: "service" oder "verleih"
    art: Literal["service", "verleih"] | None = None

class ScannerWebSocketMessage(BaseModel):
    message: str
    success: bool
    scannername: str | None = None
    ski_id: int | None = None
    service_id: int | None = None
    data: AuftragSchema | None = None