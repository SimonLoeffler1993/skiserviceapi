"""Abhol-Mail beim Wechsel eines Verleihs auf "vorbereitet" (alle Bindungen geprüft)."""
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.saisonverleih import SaisonVerleihRead
from app.utils.mail import sendeVerleihMail


def status_vor_aenderung(db: Session, saisonverleih_id: int) -> Optional[str]:
    """Status vor einer Änderung, um den Wechsel auf "vorbereitet" zu erkennen."""
    verleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    return verleih.Status if verleih else None


def abhol_mail_nach_wechsel(db: Session, verleih, status_vorher: Optional[str]):
    """
    Wechselt der Verleih von "vorbereitung" auf "vorbereitet", bekommt der Kunde die Abhol-Mail,
    sofern er noch nicht benachrichtigt wurde und eine E-Mail hinterlegt ist.
    """
    if verleih is None or status_vorher != "vorbereitung" or verleih.Status != "vorbereitet" or verleih.Benachrichtigt != "nein":
        return verleih
    if not sendeVerleihMail(SaisonVerleihRead.model_validate(verleih), "abholung"):
        return verleih
    return crud_saisonverleih.setze_benachrichtigt(db, verleih.ID, "abholung")
