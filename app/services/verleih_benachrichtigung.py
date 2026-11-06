"""Abhol-Mail, sobald ein Verleih vorbereitet ist und bei jedem Material die Bindung geprüft ist."""
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.saisonverleih import SaisonVerleihRead
from app.utils.mail import sendeVerleihMail


def status_vor_aenderung(db: Session, saisonverleih_id: int) -> Optional[str]:
    """Status vor einer Änderung, um einen Verleih in Vorbereitung von einem Rücksetzen zu unterscheiden."""
    verleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    return verleih.Status if verleih else None


def abhol_mail_nach_wechsel(db: Session, verleih, status_vorher: Optional[str]):
    """
    Der Kunde bekommt die Abhol-Mail, sobald der Verleih "vorbereitet" ist und bei jedem Material die Bindung
    geprüft ist, sofern er noch nicht benachrichtigt wurde und eine E-Mail hinterlegt ist.
    Auch wenn der Status von Hand schon auf "vorbereitet" stand und die letzte Prüfung erst danach kommt.
    Ein Zurücksetzen von "unterwegs" oder "zurueck" löst keine Mail aus.
    """
    if (
        verleih is None
        or status_vorher not in ("vorbereitung", "vorbereitet")
        or verleih.Status != "vorbereitet"
        or verleih.Benachrichtigt != "nein"
        or not crud_saisonverleih.alle_bindungen_geprueft(verleih)
    ):
        return verleih
    if not sendeVerleihMail(SaisonVerleihRead.model_validate(verleih), "abholung"):
        return verleih
    return crud_saisonverleih.setze_benachrichtigt(db, verleih.ID, "abholung")
