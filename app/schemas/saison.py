from pydantic import BaseModel
from datetime import date

class SaisonRead(BaseModel):
    ID: int
    Start: date
    Ende: date
    Name: str
    Verwendet: int

    class Config:
        from_attributes = True  # ab Pydantic v2 (für SQLAlchemy-Kompatibilität)