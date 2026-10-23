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
        from_attributes = True

class SkiArtRead(SkiArtBase):
    ID: int

    class Config:
        from_attributes = True

class VerleihSkiModellRead(VerleihSkiModellBase):
    ID: int
    Art: Optional[SkiArtRead]
    Hersteller: Optional[VerleihSkiHerstellerRead]

    class Config:
        from_attributes = True

class EigenSkiRead(EigenSkiBase):
    ID: int
    Modell: Optional[VerleihSkiModellRead]
    Ausgemustert: bool = False
    # Steckt der Ski in einem Verleih (nur in Listen gesetzt)
    ImVerleih: bool = False

    class Config:
        from_attributes = True


# --- Bearbeiten (nur gesetzte Felder werden geändert) ---
class VerleihSkiHerstellerUpdate(BaseModel):
    Name: Optional[str] = None

class SkiArtUpdate(BaseModel):
    Art: Optional[str] = None

class VerleihSkiModellUpdate(BaseModel):
    Modell: Optional[str] = None
    Art_ID: Optional[int] = None
    Hersteller_ID: Optional[int] = None

class EigenSkiUpdate(BaseModel):
    Modell_ID: Optional[int] = None
    Laenge: Optional[int] = None
    VK: Optional[float] = None
    EK: Optional[float] = None
    Saison: Optional[str] = None
    SkiNr: Optional[str] = None

class EigenSkiAenderung(EigenSkiRead):
    # Anzahl Verleihe, die auf die neue Ski-Nr. umgestellt wurden
    UmgestellteVerleihe: int = 0
