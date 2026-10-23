from pydantic import BaseModel

class SkiStockOut(BaseModel):
    ID: int
    Bezeichnung: str
    Ausgemustert: bool = False
    # Steckt der Stock in einem Verleih (nur in Listen gesetzt)
    ImVerleih: bool = False

    class Config:
        from_attributes = True

class SkiStockIn(BaseModel):
    Bezeichnung: str