from pydantic import BaseModel, Field
from typing import Optional

# --- Hersteller ---
class VerleihSchuhHerstellerBase(BaseModel):
    Name: str

class VerleihSchuhHerstellerRead(VerleihSchuhHerstellerBase):
    ID: int

    class Config:
        from_attributes = True


# --- Schuhmodell ---
class VerleihSchuhModellBase(BaseModel):
    Modell: str
    Jugend: bool
    Hersteller_ID: int

class VerleihSchuhModellRead(VerleihSchuhModellBase):
    ID: int
    Hersteller: Optional[VerleihSchuhHerstellerRead]

    class Config:
        from_attributes = True


# --- EigenSchuh ---
class EigenSchuhBase(BaseModel):
    Modell_ID: int
    # Eigene Nummer, z.B. Inventur-Aufkleber. Ohne Angabe wird die ID verwendet.
    SchuhNr: Optional[str] = Field(default=None, max_length=50)
    Groese: float
    # Sohlenlänge in mm, optional
    Sohle: Optional[int] = Field(default=None, ge=150, le=400)
    Saison: str
    VK: float
    EK: float

class EigenSchuhRead(EigenSchuhBase):
    ID: int
    SchuhNr: str
    Modell: Optional[VerleihSchuhModellRead]
    Ausgemustert: bool = False
    # Steckt der Schuh in einem Verleih (nur in Listen gesetzt)
    ImVerleih: bool = False

    class Config:
        from_attributes = True



# --- Bearbeiten (nur gesetzte Felder werden geändert) ---
class VerleihSchuhHerstellerUpdate(BaseModel):
    Name: Optional[str] = None

class VerleihSchuhModellUpdate(BaseModel):
    Modell: Optional[str] = None
    Jugend: Optional[bool] = None
    Hersteller_ID: Optional[int] = None

class EigenSchuhUpdate(BaseModel):
    Modell_ID: Optional[int] = None
    # Leer = zurück auf die interne ID
    SchuhNr: Optional[str] = Field(default=None, max_length=50)
    Groese: Optional[float] = None
    Sohle: Optional[int] = Field(default=None, ge=150, le=400)
    Saison: Optional[str] = None
    VK: Optional[float] = None
    EK: Optional[float] = None
