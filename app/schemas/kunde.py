from pydantic import BaseModel
from app.schemas.ort import OrtOut


class SkiKundeOut(BaseModel):
    ID: int
    Nachname: str 
    Vorname: str
    Strasse: str
    Ort: OrtOut
    Tel: str
    Email: str

    class Config:
        orm_mode = True

class SkiKundeSpeichern(BaseModel):
    Nachname: str 
    Vorname: str
    Strasse: str
    Plz: str
    Ort: str
    Tel: str
    Handy: str
    Email: str

    class Config:
        orm_mode = True