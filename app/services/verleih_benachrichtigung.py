"""Abhol-Mail, sobald ein Verleih vorbereitet ist und bei jedem Material die Bindung geprüft ist."""
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.mailstatus import MailStatus
from app.schemas.saisonverleih import SaisonVerleihRead
from app.utils.mail import sendeVerleihMail


def status_vor_aenderung(db: Session, saisonverleih_id: int) -> Optional[str]:
    """Status vor einer Änderung, um einen Verleih in Vorbereitung von einem Rücksetzen zu unterscheiden."""
    verleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    return verleih.Status if verleih else None


def abhol_mail_mit_status(db: Session, verleih, status_vorher: Optional[str]) -> tuple[object, MailStatus]:
    """
    Der Kunde bekommt die Abhol-Mail, sobald der Verleih "vorbereitet" ist und bei jedem Material die Bindung
    geprüft ist, sofern er noch nicht benachrichtigt wurde und eine E-Mail hinterlegt ist.
    Auch wenn der Status von Hand schon auf "vorbereitet" stand und die letzte Prüfung erst danach kommt.
    Ein Zurücksetzen von "unterwegs" oder "zurueck" löst keine Mail aus.
    Gibt den Verleih und das Ergebnis der Mail zurück (None: keine Mail fällig oder keine Adresse).
    """
    if (
        verleih is None
        or status_vorher not in ("vorbereitung", "vorbereitet")
        or verleih.Status != "vorbereitet"
        or verleih.Benachrichtigt != "nein"
        or not crud_saisonverleih.alle_bindungen_geprueft(verleih)
    ):
        return verleih, None
    # Ohne Adresse ist nichts fehlgeschlagen, das Center zeigt dafür einen eigenen Hinweis
    if not verleih.Kunde or not verleih.Kunde.Email:
        return verleih, None
    if not sendeVerleihMail(SaisonVerleihRead.model_validate(verleih), "abholung"):
        return verleih, "fehlgeschlagen"
    return crud_saisonverleih.setze_benachrichtigt(db, verleih.ID, "abholung"), "gesendet"


def abhol_mail_nach_wechsel(db: Session, verleih, status_vorher: Optional[str]):
    """Wie abhol_mail_mit_status, gibt nur den Verleih zurück."""
    return abhol_mail_mit_status(db, verleih, status_vorher)[0]
