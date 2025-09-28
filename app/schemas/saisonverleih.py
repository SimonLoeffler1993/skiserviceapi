from pydantic import BaseModel
from typing import Optional, List
from datetime import date

from app.schemas.kunde import SkiKundeOut
from app.schemas.saison import SaisonRead
from app.schemas.materialski import EigenSkiRead
from app.schemas.materialschuh import EigenSchuhRead
from app.schemas.materialstock import SkiStockOut



# --- Saisonverleih-Material ---
class SaisonVerleihMaterialBase(BaseModel):
    skinr: Optional[str] = None
    schuhnr: Optional[int] = None
    stockbez_ID: Optional[int] = None
    stocklaenge: Optional[int] = None
    Preis: float
    SkiFahrerName: Optional[str] = None # Name der Person, die das Material fährt (kann vom Kunden abweichen)

    class Config:
        from_attributes = True


class SaisonVerleihMaterialCreate(SaisonVerleihMaterialBase):
    SaisonVerlei_ID: int


class SaisonVerleihMaterialUpdate(SaisonVerleihMaterialBase):
    pass


class SaisonVerleihMaterialRead(SaisonVerleihMaterialBase):
    ID: int
    Ski: EigenSkiRead | None = None
    Schuh: EigenSchuhRead | None = None
    Stock: SkiStockOut | None = None
    # Optional: verschachtelte Infos aus den Relationen (falls du eigene Out-Schemas hast)
    # Ski: Optional[EigenSkiRead] = None
    # Schuh: Optional[EigenSchuhRead] = None

    class Config:
        from_attributes = True


# --- Saisonverleih ---
class SaisonVerleihBase(BaseModel):
    Kunde_ID: int 
    Ueberweisung: int | None = None
    Bezahlt: int | None = None
    Bezahlt_Am: date | None = None
    Zurueck: bool | None = None
    Zurueck_Am: date | None = None
    Bemerkung: str | None = None
    Saison_ID: int | None = None
    Abgerechnet: int | None = None
    Start_Am: date | None = None
    QuittungID: int | None = None

    class Config:
        from_attributes = True

class SaisonVerleihCreate(SaisonVerleihBase):
    Material: List[SaisonVerleihMaterialBase] = []

class SaisonVerleihUpdate(SaisonVerleihBase):
    pass

# -> Read mit verschachtelten Objekten
class SaisonVerleihRead(SaisonVerleihBase):
    ID: int
    Name: str 
    Kunde: SkiKundeOut | None = None
    Saison: SaisonRead | None = None
    Material: List[SaisonVerleihMaterialRead] = [] 

    class Config:
        from_attributes = True