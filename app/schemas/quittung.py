from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BezahlInfoSchema(BaseModel):
    Bezahlt: bool
    Bezahlt_Am: date | None = None
    Offener_Betrag: float | None = None


class QuittungBase(BaseModel):
    Name: str
    AnzAuftrag: int
    AnzVerleih: int
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
