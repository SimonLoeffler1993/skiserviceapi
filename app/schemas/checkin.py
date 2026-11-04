from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.kunde import SkiKundeOut, SkiKundeSpeichern


class CheckinKunde(SkiKundeSpeichern):
    """Kundendaten aus dem Check-in, Regeln wie beim Erfassen. Die PLZ bleibt Text, sonst gehen führende Nullen verloren."""
    Plz: str | None = Field(None, pattern=r"^\d{4,5}$")
    Ort: str | None = Field(None, max_length=100)


class CheckinInhalt(BaseModel):
    """Entschlüsselter Inhalt eines Datensatzes, ungeprüfte Eingabe aus dem Internet."""
    schemaVersion: int
    erfasstAm: str = Field(max_length=40)
    kunde: CheckinKunde


class CheckinRead(BaseModel):
    id: str
    erstellt_am: datetime
    lesbar: bool
    # Warum der Datensatz nicht lesbar ist
    grund: str | None = None
    kunde: CheckinKunde | None = None


class CheckinUebernommen(BaseModel):
    kunde: SkiKundeOut
    # Z.B. unbekannte PLZ, der Kunde ist trotzdem angelegt
    warnung: str | None = None


class CheckinStatus(BaseModel):
    eingerichtet: bool
    erreichbar: bool
    offen: int = 0
    # Datensätze, zu denen der API der private Schlüssel fehlt
    ohne_schluessel: int = 0


class CheckinSchluesselRead(BaseModel):
    """Bewusst ohne privaten Schlüssel."""
    schluessel_id: str
    public_key: str
    erstellt_am: datetime
