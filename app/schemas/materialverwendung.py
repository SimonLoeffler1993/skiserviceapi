from datetime import date
from typing import Optional

from pydantic import BaseModel


class VerleihVerwendung(BaseModel):
    """Ein Verleih, in dem ein Ski, Schuh oder Stock steckt."""
    ID: int
    Name: str
    Art: str
    Start_Am: Optional[date] = None
    Ende_Am: Optional[date] = None
    Kunde: str
    Fahrer: Optional[str] = None
    Zurueck: bool
    # vorbereitung, unterwegs oder zurueck
    Status: str = "unterwegs"


class StammdatenVerwendung(BaseModel):
    """Wie oft ein Hersteller oder Modell noch verwendet wird."""
    Anzahl: int
    # Erste Bezeichnungen, z.B. Modellnamen oder Ski-Nr.
    Beispiele: list[str]


class Ausmustern(BaseModel):
    Ausgemustert: bool


class LoeschErgebnis(BaseModel):
    success: bool
