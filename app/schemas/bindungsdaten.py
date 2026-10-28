from datetime import date
from typing import Literal, Optional, get_args

from pydantic import BaseModel, Field, field_validator

# Fahrertyp mit Zwischenstufen, von 1- (sehr vorsichtig) bis 3+ (sehr sportlich)
Fahrertyp = Literal["1-", "1", "1+", "2-", "2", "2+", "3-", "3", "3+"]
FAHRERTYPEN: tuple[str, ...] = get_args(Fahrertyp)


class BindungsdatenBase(BaseModel):
    Fahrer: Optional[str] = Field(default=None, max_length=100)
    # Sohlenlänge in mm
    Sohle: Optional[int] = Field(default=None, ge=150, le=400)
    # Gewicht in kg
    Gewicht: Optional[float] = Field(default=None, ge=10, le=200)
    # Größe in cm (1,80 m = 180)
    Groesse: Optional[int] = Field(default=None, ge=80, le=230)
    # Typ 1- bis 3+ (1 vorsichtig, 2 normal, 3 sportlich, mit Zwischenstufen)
    Fahrkoennen: Optional[Fahrertyp] = None
    Alter: Optional[int] = Field(default=None, ge=2, le=100)
    # Nur Eingabe: Kunde hat die Angaben geprüft und bestätigt (gespeichert wird das Datum)
    bestaetigt: bool = False

    model_config = {"from_attributes": True}

    @field_validator("Fahrkoennen", mode="before")
    @classmethod
    def fahrertyp_als_text(cls, wert):
        # Alte Werte bzw. Clients liefern 1, 2, 3 als Zahl
        return str(wert) if isinstance(wert, int) and not isinstance(wert, bool) else wert

    def werte(self) -> dict:
        """Die Bindungswerte ohne die Bestätigung."""
        return self.model_dump(exclude={"bestaetigt"})

    def ist_leer(self) -> bool:
        return all(wert in (None, "") for wert in self.werte().values())


class BindungsdatenRead(BindungsdatenBase):
    ID: int
    Kunde_ID: int
    Ski_ID: Optional[int] = None
    Material_ID: Optional[int] = None
    Erfasst_Am: date
    Archiviert: bool
    # Datum der Bestätigung durch den Kunden, None wenn (noch) nicht bestätigt
    Bestaetigt_Am: Optional[date] = None


class BindungsdatenListeEintrag(BindungsdatenRead):
    # Woher der Eintrag stammt
    Auftrag_ID: Optional[int] = None
    Auftrag_Name: Optional[str] = None
    Ski_Name: Optional[str] = None
    Service: Optional[str] = None
    Verleih_ID: Optional[int] = None
    Verleih_Name: Optional[str] = None


class BindungsdatenArchivieren(BaseModel):
    Archiviert: bool
