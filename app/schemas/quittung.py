from __future__ import annotations

from datetime import date

from pydantic import BaseModel, model_validator
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


class QuittungRead(QuittungBase):
    ID: int

    model_config = {
        "from_attributes": True
    }

class QuittungNurExtern(BaseModel):
    # Genau eines von beiden: Saisonverleih oder Skiservice-Auftrag
    SaisonverleihID: Optional[int] = None
    AuftragID: Optional[int] = None
    LexOfficeID: str

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

