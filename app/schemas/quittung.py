from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from enum import Enum 


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


class QuittungRead(QuittungBase):
    ID: int

    model_config = {
        "from_attributes": True
    }

class QuittungNurExtern(BaseModel):
    SaisonverleihID: int
    LexOfficeID: str

    model_config = {
        "from_attributes": True
    }

# Outputschema für einheitliche Antwort
class QuittungsTyp(str, Enum):
    Auftrag = "Auftrag"
    Verleih = "Verleih"
    Handware = "Handware"

class QuittungOutSchema(BaseModel):
    id: int
    name: str
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

