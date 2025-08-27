from pydantic import BaseModel
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
    Jugend: int
    Hersteller_ID: int

class VerleihSchuhModellRead(VerleihSchuhModellBase):
    ID: int
    Hersteller: Optional[VerleihSchuhHerstellerRead]

    class Config:
        from_attributes = True


# --- EigenSchuh ---
class EigenSchuhBase(BaseModel):
    Modell_ID: int
    Groese: float
    Saison: str
    VK: float
    EK: float

class EigenSchuhRead(EigenSchuhBase):
    ID: int
    Modell: Optional[VerleihSchuhModellRead]

    class Config:
        from_attributes = True

