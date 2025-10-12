from pydantic import BaseModel
from datetime import date
from typing import Optional

class SaisonRead(BaseModel):
    ID: int
    Start: date
    Ende: date
    Name: str
    Verwendet: int

    class Config:
        from_attributes = True  # ab Pydantic v2 (für SQLAlchemy-Kompatibilität)

class SaisonsNamen(BaseModel):
    Name: str
    ID: int
    Verwendet: int
    class Config:
        from_attributes = True  # ab Pydantic v2 (für SQLAlchemy-Kompatibilität)