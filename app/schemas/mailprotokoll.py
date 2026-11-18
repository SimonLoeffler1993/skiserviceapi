from datetime import datetime

from pydantic import BaseModel

from app.schemas.quittung import QuittungBezug


class MailProtokollRead(BaseModel):
    """Eine versendete Kundenmail. Bei einer Quittungs-Mail verweist Quittung_ID auf den Anhang."""
    ID: int
    Gesendet_Am: datetime
    Vorlage: str
    Empfaenger: str
    Betreff: str
    Inhalt: str
    Erfolgreich: bool
    Fehler: str | None = None
    Kunde_ID: int | None = None
    Auftrag_ID: int | None = None
    Verleih_ID: int | None = None
    Quittung_ID: int | None = None
    Quittung_Nummer: str | None = None
    # Auftrag bzw. Verleih der Mail, bei einer Quittungs-Mail alle auf der Quittung
    Bezuege: list[QuittungBezug] = []
