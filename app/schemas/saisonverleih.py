from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.schemas.kunde import SkiKundeOut
from app.schemas.saison import SaisonRead

#  --- Material für Saisonverleih


# --- Saisonverleih ---
class SaisonVerleihBase(BaseModel):
    Kunde_ID: int 
    Ueberweisung: int | None = None
    Bezahlt: int | None = None
    Bezahlt_Am: date | None = None
    Zurueck: int | None = None
    Zurueck_Am: date | None = None
    Bemerkung: str | None = None
    Saison_ID: int 
    Abgerechnet: int | None = None
    Name: str 
    Start_Am: date 
    QuittungID: int | None = None

    class Config:
        from_attributes = True

class SaisonVerleihCreate(SaisonVerleihBase):
    pass

class SaisonVerleihUpdate(SaisonVerleihBase):
    pass

# -> Read mit verschachtelten Objekten
class SaisonVerleihRead(SaisonVerleihBase):
    ID: int | None = None
    Kunde: SkiKundeOut | None = None
    Saison: SaisonRead | None = None

    class Config:
        from_attributes = True