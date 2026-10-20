from typing import Any, Optional
from pydantic import BaseModel, Field


class EinstellungRead(BaseModel):
    schluessel: str
    gruppe: str
    gruppe_bezeichnung: str
    bezeichnung: str
    beschreibung: str
    typ: str
    optionen: list[str]
    # Bei Passwörtern immer None
    wert: Any = None
    # Ob ein Wert in der Datenbank gespeichert ist
    gesetzt: bool


class EinstellungenSpeichern(BaseModel):
    # Schlüssel -> Wert. Leere Passwörter bleiben unverändert.
    werte: dict[str, Any]


class TestMail(BaseModel):
    empfaenger: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TestErgebnis(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
