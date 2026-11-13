from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PlatzhalterRead(BaseModel):
    schluessel: str
    bezeichnung: str
    beispiel: str


class BausteinRead(BaseModel):
    schluessel: str
    bezeichnung: str
    beschreibung: str


class MailVorlageRead(BaseModel):
    schluessel: str
    bezeichnung: str
    beschreibung: str
    betreff: str
    inhalt: str
    # Unveränderlicher Originaltext, darauf wird zurückgesetzt
    original_betreff: str
    original_inhalt: str
    # Weicht vom Original ab
    geaendert: bool
    geaendert_am: Optional[datetime] = None
    platzhalter: list[PlatzhalterRead]
    bausteine: list[BausteinRead]


class MailVorlageSpeichern(BaseModel):
    betreff: str
    inhalt: str


class MailVorlageVorschau(BaseModel):
    betreff: str
    html: str
