from pydantic import BaseModel
from enum import IntEnum
from datetime import datetime

from app.schemas.skiservice import AuftragSchema

# TriggerStatus muss mit der ESP Firmware übereinstimmen, damit die Werte korrekt interpretiert werden können
class TriggerStatus(IntEnum):
    bearbeitung = 0
    fertig = 1

class ScannerRead(BaseModel):
    code: str
    name: str
    trigger: TriggerStatus

class ScannerWebSocketMessage(BaseModel):
    message: str
    success: bool
    scannername: str | None = None
    ski_id: int | None = None
    service_id: int | None = None
    data: AuftragSchema | None = None