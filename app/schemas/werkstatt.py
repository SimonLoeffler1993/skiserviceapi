from datetime import date
from typing import Optional

from pydantic import BaseModel


class WerkstattSaison(BaseModel):
    ID: int
    Name: str


class WerkstattSki(BaseModel):
    """Ski aus einem Skiservice-Auftrag, an dem noch etwas zu tun ist."""
    ski_id: int
    ski_name: Optional[str] = None
    auftrag_id: int
    auftrag_name: Optional[str] = None
    kunde_name: str
    service: str
    komentar: Optional[str] = None
    # Leistung noch nicht fertig
    service_offen: bool
    # Bindungscheck beauftragt, aber noch nicht geprüft
    bindung_offen: bool
    # Fertig-bis-Datum wie gespeichert ("TT.MM.JJJJ")
    abhol_date: Optional[str] = None


class WerkstattVerleih(BaseModel):
    """Verleih in Vorbereitung: Bindungen müssen noch geprüft werden."""
    ID: int
    Name: str
    Art: str
    kunde_name: str
    Start_Am: Optional[date] = None
    Ende_Am: Optional[date] = None
    material_gesamt: int
    material_geprueft: int


class Zeitraum(BaseModel):
    heute: int = 0
    # Letzte 7 Tage einschließlich heute
    woche: int = 0
    saison: int = 0


class WerkstattAuswertung(BaseModel):
    # Bindungen eingestellt und geprüft
    eingestellt_service: Zeitraum
    eingestellt_verleih: Zeitraum
    # Ski mit fertiger Leistung
    service_fertig: Zeitraum
    # Alle Ski der Saison im Skiservice
    ski_gesamt: int
    # Davon mit Bindungscheck
    bindung_gesamt: int
    service_offen: int
    bindung_offen: int
    # Materialzeilen im Verleih: gesamt und noch nicht geprüft (nur Verleihe in Vorbereitung)
    verleih_material_gesamt: int
    verleih_bindung_offen: int


class VerleihStatusZahlen(BaseModel):
    vorbereitung: int = 0
    vorbereitet: int = 0
    unterwegs: int = 0
    zurueck: int = 0
    gesamt: int = 0
    unbezahlt: int = 0
    # Nur Tagesverleih: unterwegs und letzter Verleihtag erreicht oder vorbei
    rueckgabe_faellig: int = 0


class WerkstattVerleihZahlen(BaseModel):
    saison: VerleihStatusZahlen
    tag: VerleihStatusZahlen


class WerkstattUebersicht(BaseModel):
    saison: WerkstattSaison
    ski_offen: list[WerkstattSki]
    verleih_offen: list[WerkstattVerleih]
    auswertung: WerkstattAuswertung
    verleih: WerkstattVerleihZahlen
