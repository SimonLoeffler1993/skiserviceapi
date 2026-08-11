from pydantic import BaseModel
from enum import Enum

class KasseArtikelKategorie(str, Enum):
    auftrag = "Auftrag"
    verleih = "Verleih"
    handware = "Handware"

class KasseEinzelArtikelSchema(BaseModel):
    id: int
    bezeichnung: str
    preis: float

class KassenArtikelSchema(BaseModel):
    id: int
    kundenname: str
    artikelname: str
    gesamtpreis: float
    artikel: list[KasseEinzelArtikelSchema]
