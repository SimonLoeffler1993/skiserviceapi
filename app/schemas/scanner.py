from pydantic import BaseModel
from enum import IntEnum

# TriggerStatus muss mit der ESP Firmware übereinstimmen, damit die Werte korrekt interpretiert werden können
class TriggerStatus(IntEnum):
    bearbeitung = 0
    fertig = 1

class ScannerRead(BaseModel):
    code: str
    name: str
    trigger: TriggerStatus