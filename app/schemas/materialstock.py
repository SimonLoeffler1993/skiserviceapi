from pydantic import BaseModel

class SkiStockOut(BaseModel):
    ID: int
    Bezeichnung: str

    class Config:
        from_attributes = True