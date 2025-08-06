from pydantic import BaseModel
from typing import Optional

# --- Basis-Schemas (für Read & Write gemeinsam) ---

class VerleihSkiHerstellerBase(BaseModel):
    Name: str

class SkiArtBase(BaseModel):
    Art: str

class VerleihSkiModellBase(BaseModel):
    Modell: str
    Art_ID: int
    Hersteller_ID: int

class EigenSkiBase(BaseModel):
    Modell_ID: int
    Laenge: int
    VK: float
    EK: float
    Saison: str
    SkiNr: str

# --- Read-Schemas (für GET-Anfragen) ---
class VerleihSkiHerstellerRead(VerleihSkiHerstellerBase):
    ID: int

    class Config:
        orm_mode = True

class SkiArtRead(SkiArtBase):
    ID: int

    class Config:
        orm_mode = True

class VerleihSkiModellRead(VerleihSkiModellBase):
    ID: int
    Art: Optional[SkiArtRead]
    Hersteller: Optional[VerleihSkiHerstellerRead]

    class Config:
        orm_mode = True

class EigenSkiRead(EigenSkiBase):
    ID: int
    Modell: Optional[VerleihSkiModellRead]

    class Config:
        orm_mode = True
