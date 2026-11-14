from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.materialschuh import EigenSchuhRead
from app.schemas.materialski import EigenSkiRead


class MaterialVerleihPosition(BaseModel):
    """Eine Verleihzeile, in der der Ski bzw. Schuh steckt, mit seinem Anteil am Zeilenpreis."""
    Verleih_ID: int
    Material_ID: int
    Name: str
    Art: str
    Saison_ID: Optional[int] = None
    Start_Am: Optional[date] = None
    Ende_Am: Optional[date] = None
    Kunde: str
    Fahrer: Optional[str] = None
    # vorbereitung, vorbereitet, unterwegs oder zurueck
    Status: str = "unterwegs"
    Bezahlt: bool = False
    # Preis der ganzen Zeile (Ski, Schuh und Stock zusammen)
    Preis: float
    MitSki: bool
    MitSchuh: bool
    # Anteil dieses Materialstücks am Zeilenpreis
    AnteilProzent: int
    Anteil: float


class ErloesSummen(BaseModel):
    AnzahlVerleihe: int
    Einnahmen: float
    # Summe der Abzüge aller Services, bei Schuhen immer 0
    ServiceAbzug: float = 0
    # Einnahmen abzüglich Services
    Ergebnis: float


class SkiServiceCreate(BaseModel):
    Datum: Optional[date] = None  # leer = heute
    Bezeichnung: str = Field(min_length=1, max_length=200)
    # leer = Betrag aus den Einstellungen
    Abzug: Optional[float] = Field(default=None, ge=0)


class SkiServiceUpdate(BaseModel):
    Datum: Optional[date] = None
    Bezeichnung: Optional[str] = Field(default=None, min_length=1, max_length=200)
    Abzug: Optional[float] = Field(default=None, ge=0)


class SkiServiceRead(BaseModel):
    ID: int
    EigenSki_ID: int
    Datum: date
    Bezeichnung: str
    Abzug: float

    class Config:
        from_attributes = True


class SkiDetails(BaseModel):
    Ski: EigenSkiRead
    Verleihe: list[MaterialVerleihPosition]
    Services: list[SkiServiceRead]
    Summen: ErloesSummen
    # Einstellungen, mit denen gerechnet wurde bzw. die der Dialog vorschlägt
    AnteilSkiProzent: int
    ServiceAbzugStandard: float


class SchuhDetails(BaseModel):
    Schuh: EigenSchuhRead
    Verleihe: list[MaterialVerleihPosition]
    Summen: ErloesSummen
    AnteilSkiProzent: int
