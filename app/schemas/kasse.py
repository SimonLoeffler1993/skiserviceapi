from pydantic import BaseModel
from enum import Enum
from typing import Optional

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
    service: bool = False
    verleih: bool = False

class KasseHatBezahltSchema(BaseModel):
    quittung_id: int
    bezahldatum: Optional[str] = None
    # bezahlinfo: Optional[dict] = None
    success: bool 

class KasseBezahlenSchema(BaseModel):
    artikels: list[KassenArtikelSchema]
    ueberweisung: bool = False
    karte: bool = False
    bar: bool = False