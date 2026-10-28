from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from enum import Enum 
from typing import Optional


class BezahlInfoSchema(BaseModel):
    Bezahlt: bool
    Bezahlt_Am: date | None = None
    Offener_Betrag: float | None = None


class QuittungBase(BaseModel):
    Name: str
    AnzAuftrag: int | None = None
    AnzVerleih: int | None = None
    Saison_ID: int
    Bezahlt_Am: date | None = None
    Erstellt_Am: date | None = None
    Ueberweisung: bool
    Bezahlt: bool
    BuchhaltungSync: bool
    LexID: str | None = None
    BezahlInfo: BezahlInfoSchema | None = None


class QuittungCreate(QuittungBase):
    pass


class QuittungUpdate(BaseModel):
    Name: str | None = None
    AnzAuftrag: int | None = None
    AnzVerleih: int | None = None
    Saison_ID: int | None = None
    Bezahlt_Am: date | None = None
    Erstellt_Am: date | None = None
    Ueberweisung: bool | None = None
    Bezahlt: bool | None = None
    BuchhaltungSync: bool | None = None
    LexID: str | None = None


def _lexware_modus() -> str | None:
    # Spät importieren, damit das Schema ohne Einstellungen/DB geladen werden kann
    from app.services.lexware_sync import lexware_modus
    return lexware_modus()

class QuittungRead(QuittungBase):
    ID: int
    Nummer: str | None = None
    NurExtern: bool | None = None
    # Lexware-Beleg von Hand zugewiesen, kann geändert oder aufgehoben werden
    ManuellZugewiesen: bool = False
    # Aktuelle Lexware Übertragung ("pdf" / "rechnung"), None wenn aus
    LexwareModus: str | None = Field(default_factory=_lexware_modus)

    model_config = {
        "from_attributes": True
    }

class QuittungNurExtern(BaseModel):
    # Genau eines von beiden: Saisonverleih oder Skiservice-Auftrag
    SaisonverleihID: Optional[int] = None
    AuftragID: Optional[int] = None
    LexOfficeID: str
    # Bestehende, von Hand zugewiesene Quittung durch diesen Beleg ersetzen
    ersetzen: bool = False

    @model_validator(mode="after")
    def pruefe_ziel(self):
        if (self.SaisonverleihID is None) == (self.AuftragID is None):
            raise ValueError("Bitte genau eines angeben: SaisonverleihID oder AuftragID.")
        return self

    model_config = {
        "from_attributes": True
    }

# Outputschema für einheitliche Antwort
class QuittungsTyp(str, Enum):
    Auftrag = "Auftrag"
    Verleih = "Verleih"
    Handware = "Handware"

class QuittungKundeSchema(BaseModel):
    # Bei Artikeln unterschiedlicher Kunden: "Sammelkunde" ohne Anschrift
    sammel: bool = False
    id: int | None = None
    name: str
    strasse: str | None = None
    plz: int | None = None
    ort: str | None = None

class QuittungOutSchema(BaseModel):
    id: int
    name: str
    # Angezeigte Quittungsnummer, z.B. "26/27Q12" (Altbestand: die ID)
    nummer: str = ""
    saison_ID: int
    bezahlt: bool 
    bezahlt_Am: date | None = None
    erstellt_Am: date | None = None
    ueberweisung: bool
    karte: bool
    bar: bool
    buchhaltungSync: bool
    lexID: str | None = None
    artikelgruppen: list[QuittungGruppeArtikel] = []
    nurExtern: bool = False
    kunde: QuittungKundeSchema | None = None

class QuittungGruppeArtikel(BaseModel):
    type: QuittungsTyp
    toID: int
    bezeichnung: str
    artikels: list[QuittungArtikelSchema] = []

class QuittungArtikelSchema(BaseModel):
    type: QuittungsTyp
    bezeichnung: str
    preis: float
    anzahl: int
    toID: int

class QuittungBezug(BaseModel):
    art: Literal["auftrag", "verleih"]
    id: int
    name: str | None = None

class QuittungListeEintrag(BaseModel):
    """Zeile der Quittungsliste im Center, mit Artikeln zum Aufklappen."""
    ID: int
    # Angezeigte Quittungsnummer, z.B. "26/27Q12"
    Nummer: str
    Name: str | None = None
    Erstellt_Am: date | None = None
    Bezahlt_Am: date | None = None
    Bezahlt: bool
    # z.B. "Bar" oder "EC, Überweisung"
    Zahlart: str
    Betrag: float
    # Kundenname bzw. "Sammelkunde"
    Kunde: str | None = None
    Bezuege: list[QuittungBezug] = []
    NurExtern: bool
    LexID: str | None = None
    BuchhaltungSync: bool
    artikelgruppen: list[QuittungGruppeArtikel] = []
