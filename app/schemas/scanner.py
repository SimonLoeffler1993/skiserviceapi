from datetime import datetime

from pydantic import BaseModel
from enum import IntEnum
from typing import Literal

from app.schemas.mailstatus import MailStatus
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
    # Automatische Kundenmail durch diesen Scan (Abhol-Mail vom Verleih)
    mail: MailStatus = None

class ScannerWebSocketMessage(BaseModel):
    message: str
    success: bool
    scannername: str | None = None
    ski_id: int | None = None
    service_id: int | None = None
    data: AuftragSchema | None = None
    # "verleih": Bindungsscan eines Verleih-Etiketts, ohne data. Sonst Skiservice
    art: Literal["service", "verleih"] | None = None
    verleih_id: int | None = None
    # Anzeigename des Verleihs und Kunde, für den Hinweis im Center
    verleih_name: str | None = None
    kunde: str | None = None
    # Automatische Kundenmail: "gesendet" oder "fehlgeschlagen"
    mail: MailStatus = None

class ScannerMeldung(BaseModel):
    """Regelmäßige Meldung des Scanners (Health-Check), zeigt im Center, dass er verbunden ist."""
    name: str
    modus: TriggerStatus
    firmware: str | None = None
    ip: str | None = None
    # USB-Barcodescanner am ESP32 angeschlossen
    usb_scanner: bool = True
    # Firmware kann sich selbst aktualisieren (ältere Firmware schickt das Feld nicht)
    update_faehig: bool = False
    # Stand des Selbst-Updates: "" / "pruefe" / "laedt" / "aktuell" / "fehlgeschlagen"
    update_status: str | None = None
    update_fehler: str | None = None

class ScannerGeraet(ScannerMeldung):
    zuletzt: datetime
    verbunden: bool
    # Im Center angestoßenes Update, auf das der Scanner noch nicht reagiert hat
    update_angefordert: datetime | None = None
