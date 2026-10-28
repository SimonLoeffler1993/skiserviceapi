from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated
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
    # Angezeigte Nummer, z.B. "26/27Q12" oder die Lexware Rechnungsnummer
    quittung_nummer: Optional[str] = None
    # E-Mail Adressen der Kunden als Vorschlag für den Mailversand der Quittung
    emails: list[str] = []

class KasseBezahlenSchema(BaseModel):
    artikels: list[KassenArtikelSchema]
    ueberweisung: bool = False
    karte: bool = False
    bar: bool = False

# Einfache Prüfung, email-validator ist nicht installiert
EmailAdresse = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=100)]

class QuittungMailAnfrage(BaseModel):
    emails: list[EmailAdresse] = Field(min_length=1)

class QuittungMailErgebnis(BaseModel):
    gesendet: list[str]
    fehlgeschlagen: list[str]
