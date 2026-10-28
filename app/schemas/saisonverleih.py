from pydantic import BaseModel, model_validator
from typing import Literal, Optional, List
from datetime import date

from app.schemas.kunde import SkiKundeOut
from app.schemas.saison import SaisonRead
from app.schemas.materialski import EigenSkiRead
from app.schemas.materialschuh import EigenSchuhRead
from app.schemas.materialstock import SkiStockOut
from app.schemas.bindungsdaten import BindungsdatenBase, BindungsdatenRead



# --- Saisonverleih-Material ---
class SaisonVerleihMaterialBase(BaseModel):
    skinr: Optional[str] = None
    schuhnr: Optional[int] = None
    stockbez_ID: Optional[int] = None
    stocklaenge: Optional[int] = None
    Preis: float
    SkiFahrerName: Optional[str] = None # Name der Person, die das Material fährt (kann vom Kunden abweichen)
    # Optional, leer bzw. null entfernt die Bindungsdaten
    bindungsdaten: Optional[BindungsdatenBase] = None
    # Aus "Letzte Daten abfragen" übernommener Datensatz, wird beim Speichern archiviert
    vorlage_id: Optional[int] = None
    # Ski bzw. Schuh bewusst übernehmen, obwohl sie schon verliehen sind (wird nicht gespeichert)
    trotz_belegung: bool = False

    model_config = {
        "from_attributes": True
    }
    # class Config:
    #     from_attributes = True


class SaisonVerleihMaterialCreate(SaisonVerleihMaterialBase):
    SaisonVerlei_ID: int


class SaisonVerleihMaterialUpdate(BaseModel):
    # Nur gesetzte Felder werden geändert. bindungsdaten: null entfernt sie
    bindungsdaten: Optional[BindungsdatenBase] = None
    vorlage_id: Optional[int] = None
    skinr: Optional[str] = None
    schuhnr: Optional[int] = None
    stockbez_ID: Optional[int] = None
    stocklaenge: Optional[int] = None
    Preis: Optional[float] = None
    SkiFahrerName: Optional[str] = None
    # Ski bzw. Schuh bewusst übernehmen, obwohl sie schon verliehen sind
    trotz_belegung: bool = False


class SaisonVerleihMaterialRead(SaisonVerleihMaterialBase):
    ID: int
    BindungGeprueft: bool = False
    BindungGeprueft_Am: date | None = None
    Ski: EigenSkiRead | None = None
    Schuh: EigenSchuhRead | None = None
    Stock: SkiStockOut | None = None
    bindungsdaten: BindungsdatenRead | None = None
    # Optional: verschachtelte Infos aus den Relationen (falls du eigene Out-Schemas hast)
    # Ski: Optional[EigenSkiRead] = None
    # Schuh: Optional[EigenSchuhRead] = None

    model_config = {
        "from_attributes": True
    }
    # class Config:
    #     from_attributes = True


# --- Saisonverleih ---
class SaisonVerleihBase(BaseModel):
    Kunde_ID: int 
    Ueberweisung: int | None = None
    Bezahlt: int | None = None
    Bezahlt_Am: date | None = None
    Zurueck: bool | None = None
    Zurueck_Am: date | None = None
    Bemerkung: str | None = None
    Saison_ID: int | None = None
    Abgerechnet: int | None = None
    Start_Am: date | None = None
    # Nur beim Tagesverleih
    Ende_Am: date | None = None
    Art: Literal["saison", "tag"] = "saison"
    QuittungID: int | None = None

    model_config = {
        "from_attributes": True
    }

class SaisonVerleihCreate(SaisonVerleihBase):
    Material: List[SaisonVerleihMaterialBase] = []

    @model_validator(mode="after")
    def pruefe_zeitraum(self):
        if self.Art == "tag":
            if self.Start_Am is None or self.Ende_Am is None:
                raise ValueError("Beim Tagesverleih sind Start- und Enddatum Pflicht.")
            if self.Ende_Am < self.Start_Am:
                raise ValueError("Das Enddatum darf nicht vor dem Startdatum liegen.")
        return self

class SaisonVerleihUpdate(BaseModel):
    # Nur gesetzte Felder werden geändert
    Kunde_ID: int | None = None
    Bemerkung: str | None = None
    Art: Literal["saison", "tag"] | None = None
    Start_Am: date | None = None
    Ende_Am: date | None = None

# -> Read mit verschachtelten Objekten
VerleihStatus = Literal["vorbereitung", "vorbereitet", "unterwegs", "zurueck"]


class VerleihStatusAenderung(BaseModel):
    Status: VerleihStatus


# nein, abholung (Ski abholbereit) oder rueckgabe (Erinnerung an die Rückgabe)
VerleihBenachrichtigung = Literal["nein", "abholung", "rueckgabe"]


class VerleihBenachrichtigtAenderung(BaseModel):
    # Von Hand setzen, ohne Mail (z.B. Kunde angerufen)
    Benachrichtigt: VerleihBenachrichtigung


class VerleihBenachrichtigenAnfrage(BaseModel):
    # Welche Mail versendet wird
    art: Literal["abholung", "rueckgabe"]


class BindungGeprueftAnfrage(BaseModel):
    # Ohne Angabe alle Materialzeilen mit Ski
    material_ids: Optional[List[int]] = None


class SaisonVerleihRead(SaisonVerleihBase):
    ID: int
    Status: VerleihStatus = "unterwegs"
    Abgeholt_Am: date | None = None
    Benachrichtigt: VerleihBenachrichtigung = "nein"
    Benachrichtigt_Am: date | None = None
    Name: str 
    Tage: int | None = None
    Bezeichnung: str = "Saisonverleih"
    Kunde: SkiKundeOut | None = None
    Saison: SaisonRead | None = None
    Material: List[SaisonVerleihMaterialRead] = [] 

    model_config = {
        "from_attributes": True
    }
    # class Config:
    #     from_attributes = True


# --- Saisonverleih-Preis ---
class SaisonVerleihPreisBase(BaseModel):
    Bezeichnung: str
    Preis: float
    vonL: int | None = None
    bisL: int | None = None
    SkiArt_ID: int | None = None
    inaktiv: bool | None = None

    model_config = {
        "from_attributes": True
    }

class SaisonVerleihPreisRead(SaisonVerleihPreisBase):
    ID: int

    model_config = {
        "from_attributes": True
    }

class SaisonVerleihPreiseListe(BaseModel):
    preise: List[SaisonVerleihPreisRead]

    model_config = {
        "from_attributes": True
    }

# --- Belegung (Prüfung beim Tagesverleih) ---
class VerleihBelegung(BaseModel):
    ID: int
    Name: str
    Art: str
    Start_Am: date | None = None
    Ende_Am: date | None = None
    Kunde: str
    # "Ski" oder "Schuh"
    Material: str
