"""
Auswertung der Scans vom Hardware-Skiscanner.
Die Art des Etiketts steht in der URL im QR-Code:
- Service: <HOST>/skiservice/anzeigen/<auftrag>?ski=<ski>
- Verleih: <HOST>/saisonverleih/anzeigen/<verleih>?material=<material>
"""
import logging
from dataclasses import dataclass
from typing import Literal, Optional
from urllib.parse import parse_qs, urlparse

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.crud import saisonverleih as crud_saisonverleih
from app.crud import skiservice as crud_skiservice
from app.models.skiservice import Ski
from app.schemas.scanner import ScanAntwort, ScannerRead, ScannerWebSocketMessage, TriggerStatus
from app.schemas.skiservice import AuftragSchema
from app.services.verleih_benachrichtigung import abhol_mail_nach_wechsel, status_vor_aenderung
from app.utils.skiscannerguimanager import scanner_gui_manager

logger = logging.getLogger(__name__)


@dataclass
class Etikett:
    art: Literal["service", "verleih"]
    # Auftrag bzw. Verleih
    id: int
    # Ski bzw. Materialzeile, fehlt bei alten Etiketten
    position_id: Optional[int]


def _zahl(wert: Optional[str]) -> Optional[int]:
    return int(wert) if wert and wert.isdigit() else None


def etikett_lesen(code: str) -> Optional[Etikett]:
    """Erkennt Service- und Verleih-Etiketten am Pfad der URL, der Host spielt keine Rolle."""
    url = urlparse(code.strip())
    teile = [teil for teil in url.path.split("/") if teil]
    if len(teile) < 3 or teile[-2] != "anzeigen" or _zahl(teile[-1]) is None:
        return None
    query = parse_qs(url.query)
    if teile[-3] == "skiservice":
        return Etikett("service", int(teile[-1]), _zahl(query.get("ski", [None])[0]))
    if teile[-3] == "saisonverleih":
        return Etikett("verleih", int(teile[-1]), _zahl(query.get("material", [None])[0]))
    return None


def _antwort(success: bool, message: str, art=None) -> ScanAntwort:
    (logger.info if success else logger.warning)("Scan: %s", message)
    return ScanAntwort(success=success, message=message, art=art)


async def _fertigstellen(db: Session, scan: ScannerRead, etikett: Etikett) -> ScanAntwort:
    if etikett.art != "service":
        return _antwort(False, "Kein Service-Etikett", etikett.art)
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, etikett.id)
    if auftrag is None:
        return _antwort(False, f"Auftrag {etikett.id} nicht gefunden", "service")
    # Mit Scannername: das Center wählt den Ski aus und stellt ihn nach dem Countdown fertig
    await scanner_gui_manager.sende_data_broadcast(ScannerWebSocketMessage(
        message="Scan abgeschlossen",
        success=True,
        scannername=scan.name,
        ski_id=etikett.position_id,
        service_id=auftrag.id,
        data=AuftragSchema.model_validate(auftrag),
    ))
    return _antwort(True, f"Auftrag {auftrag.name or auftrag.id} an das Center gesendet", "service")


async def _bindung_service(db: Session, etikett: Etikett) -> ScanAntwort:
    if etikett.position_id is None:
        return _antwort(False, "Etikett ohne Ski", "service")
    ski = db.get(Ski, etikett.position_id)
    if ski is None or ski.auftrag_id != etikett.id:
        return _antwort(False, f"Ski {etikett.position_id} nicht im Auftrag {etikett.id} gefunden", "service")
    if not ski.bindung_check:
        return _antwort(False, "Kein Bindungscheck beauftragt", "service")
    if ski.bindung_status:
        return _antwort(True, "Bindung war bereits geprüft", "service")
    crud_skiservice.setzeBindungGeprueft(db, [ski.id])
    # Ohne Scannername: das Center lädt den Auftrag nur neu, kein Fertig-Countdown
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, etikett.id)
    await scanner_gui_manager.sende_data_broadcast(ScannerWebSocketMessage(
        message="Bindung geprüft",
        success=True,
        ski_id=ski.id,
        service_id=etikett.id,
        data=AuftragSchema.model_validate(auftrag) if auftrag else None,
    ))
    return _antwort(True, f"Bindung von Ski {ski.id} geprüft", "service")


def _bindung_verleih(db: Session, etikett: Etikett) -> ScanAntwort:
    if etikett.position_id is None:
        return _antwort(False, "Etikett ohne Materialzeile", "verleih")
    verleih = crud_saisonverleih.get_saisonverleih(db, etikett.id)
    material = next((m for m in verleih.Material if m.ID == etikett.position_id), None) if verleih else None
    if material is None:
        return _antwort(False, f"Material {etikett.position_id} nicht im Verleih {etikett.id} gefunden", "verleih")
    if not material.skinr:
        return _antwort(False, "Keine Bindung an diesem Material", "verleih")
    if material.BindungGeprueft:
        return _antwort(True, "Bindung war bereits geprüft", "verleih")
    status_vorher = status_vor_aenderung(db, verleih.ID)
    verleih = crud_saisonverleih.pruefe_bindungen(db, verleih.ID, [material.ID])
    abhol_mail_nach_wechsel(db, verleih, status_vorher)
    return _antwort(True, f"Bindung von Ski {material.skinr} im Verleih {verleih.Name} geprüft", "verleih")


async def scan_auswerten(db: Session, scan: ScannerRead) -> ScanAntwort:
    if scan.trigger == TriggerStatus.bearbeitung:
        # Noch ohne Funktion
        return ScanAntwort(success=True, message="Scan empfangen")
    etikett = etikett_lesen(scan.code)
    if etikett is None:
        return _antwort(False, f"Unbekanntes Etikett: {scan.code}")
    if scan.trigger == TriggerStatus.fertig:
        return await _fertigstellen(db, scan, etikett)
    if etikett.art == "service":
        return await _bindung_service(db, etikett)
    # Kann die Abhol-Mail senden (SMTP blockiert), daher nicht im Event-Loop
    return await run_in_threadpool(_bindung_verleih, db, etikett)
