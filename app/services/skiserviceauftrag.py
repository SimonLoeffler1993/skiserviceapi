import logging
from app.schemas.skiservice import AuftragSchema
from app.utils.skiEttiket import SkiEttiket
from app.services import einstellungen

logger = logging.getLogger(__name__) 

def appHost() -> str:
    # Falls am Schluss ein "/" ist wird dieser entfernt, damit es beim zusammensetzten keine Probleme gibt
    return einstellungen.hole("HOST").rstrip("/")

def kunden_name(vorname: str | None, nachname: str | None) -> str:
    return " ".join(teil.strip() for teil in (vorname, nachname) if teil and teil.strip())

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
        serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,ski.service,ski.bindung_check,bisDatum)

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
        serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,ski.service,ski.bindung_check,bisDatum)

        if ski.bindung_check:
            # Bei Bindung
            # zusätzlich ein Ettiket für den Schuh
            serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,"SCHUH",False,bisDatum)


    logger.info("Alle Ettiketen erstellt, jetzt kommt der Druck")
    serviceEttiket.drucken()