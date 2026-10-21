from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class BindungsdatenBase(BaseModel):
    Fahrer: Optional[str] = Field(default=None, max_length=100)
    # Sohlenlänge in mm
    Sohle: Optional[int] = Field(default=None, ge=150, le=400)
    # Gewicht in kg
    Gewicht: Optional[float] = Field(default=None, ge=10, le=200)
    # Größe in cm (1,80 m = 180)
    Groesse: Optional[int] = Field(default=None, ge=80, le=230)
    # Typ 1 (vorsichtig), 2 (normal), 3 (sportlich)
    Fahrkoennen: Optional[int] = Field(default=None, ge=1, le=3)
    Alter: Optional[int] = Field(default=None, ge=2, le=100)

    model_config = {"from_attributes": True}

    def ist_leer(self) -> bool:
        return all(wert in (None, "") for wert in self.model_dump().values())


class BindungsdatenRead(BindungsdatenBase):
    ID: int
    Kunde_ID: int
    Ski_ID: Optional[int] = None
    Erfasst_Am: date
    Archiviert: bool


class BindungsdatenListeEintrag(BindungsdatenRead):
    # Woher der Eintrag stammt
    Auftrag_ID: Optional[int] = None
    Auftrag_Name: Optional[str] = None
    Ski_Name: Optional[str] = None
    Service: Optional[str] = None


class BindungsdatenArchivieren(BaseModel):
    Archiviert: bool
