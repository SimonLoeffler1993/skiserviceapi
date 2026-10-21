import logging
from app.schemas.skiservice import AuftragSchema, SkiSchema
from app.utils.skiEttiket import SkiEttiket
from app.services import einstellungen

logger = logging.getLogger(__name__) 

def appHost() -> str:
    # Falls am Schluss ein "/" ist wird dieser entfernt, damit es beim zusammensetzten keine Probleme gibt
    return einstellungen.hole("HOST").rstrip("/")

def kunden_name(vorname: str | None, nachname: str | None) -> str:
    return " ".join(teil.strip() for teil in (vorname, nachname) if teil and teil.strip())

def _zahl(wert: float, stellen: int) -> str:
    # Deutsches Dezimalkomma, ohne unnötige Nachkommastellen bei ganzen Zahlen
    if float(wert).is_integer() and stellen < 2:
        return str(int(wert))
    return f"{float(wert):.{stellen}f}".replace(".", ",")

def bindungsdaten_text(ski: SkiSchema) -> str | None:
    """Kurze Zeile fürs Etikett, z.B. "Lena · 305mm · 75kg · 1,80m · Typ 2 · 34J". Fehlende Werte fallen weg."""
    daten = ski.bindungsdaten
    if not ski.bindung_check or daten is None:
        return None
    teile = []
    if daten.Fahrer:
        teile.append(daten.Fahrer)
    if daten.Sohle is not None:
        teile.append(f"{daten.Sohle}mm")
    if daten.Gewicht is not None:
        teile.append(f"{_zahl(daten.Gewicht, 1)}kg")
    if daten.Groesse is not None:
        # Gespeichert in cm, angezeigt in m
        teile.append(f"{_zahl(daten.Groesse / 100, 2)}m")
    if daten.Fahrkoennen is not None:
        teile.append(f"Typ {daten.Fahrkoennen}")
    if daten.Alter is not None:
        teile.append(f"{daten.Alter}J")
    return " · ".join(teile) or None

def skiServiceEttiketDrucken(skiserviceAuftrag: AuftragSchema):
    serviceEttiket = SkiEttiket()

    # Kunde aus Vor und Nachname, fehlende Teile werden weggelassen (sonst steht "None" auf dem Etikett)
    kundeName = kunden_name(skiserviceAuftrag.kunde.Vorname, skiserviceAuftrag.kunde.Nachname)

    bisDatum = skiserviceAuftrag.abhol_date

    for ski in skiserviceAuftrag.skis:
        logger.info(f"Ski Ettiket wird erstellt {ski.name}")

        skiName = ski.name or "Ski"

        skiUrl = f"{appHost()}/skiservice/anzeigen/{skiserviceAuftrag.id}?ski={ski.id}"
        
        # Ettiket für Service
        serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,ski.service,ski.bindung_check,bisDatum, bindungsdaten_text(ski))

        if ski.bindung_check:
            # Bei Bindung
            # zusätzlich ein Ettiket für den Schuh
            serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,"SCHUH",False,bisDatum)


    logger.info("Alle Ettiketen erstellt, jetzt kommt der Druck")
    serviceEttiket.drucken()

def skiServiceEttiketEinzelnDrucken(skiserviceAuftrag: AuftragSchema, skiIds: list[int]):
    serviceEttiket = SkiEttiket()

    # Kunde aus Vor und Nachname, fehlende Teile werden weggelassen (sonst steht "None" auf dem Etikett)
    kundeName = kunden_name(skiserviceAuftrag.kunde.Vorname, skiserviceAuftrag.kunde.Nachname)

    bisDatum = skiserviceAuftrag.abhol_date

    for ski in skiserviceAuftrag.skis:
        if ski.id not in skiIds:
            continue

        logger.info(f"Ski Ettiket wird erstellt {ski.name}")

        skiName = ski.name or "Ski"

        skiUrl = f"{appHost()}/skiservice/anzeigen/{skiserviceAuftrag.id}?ski={ski.id}"
        
        # Ettiket für Service
        serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,ski.service,ski.bindung_check,bisDatum, bindungsdaten_text(ski))

        if ski.bindung_check:
            # Bei Bindung
            # zusätzlich ein Ettiket für den Schuh
            serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,"SCHUH",False,bisDatum)


    logger.info("Alle Ettiketen erstellt, jetzt kommt der Druck")
    serviceEttiket.drucken()