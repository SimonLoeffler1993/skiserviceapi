import logging
from app.schemas.skiservice import AuftragSchema
from app.utils.skiEttiket import SkiEttiket
from app.core.config import AnwendungSettings

logger = logging.getLogger(__name__) 

# Falls am Schluss ein "/" ist wird dieser entfernt, damit es beim zusammensetzten keine Probleme gibt
appHost = AnwendungSettings.appHost.rstrip("/")

def skiServiceEttiketDrucken(skiserviceAuftrag: AuftragSchema):
    serviceEttiket = SkiEttiket()

    # Kunde aus Vor und Nachname, falls kein Vorname oder Nachname werden leerzeichen entfernt
    kundeName = f"{skiserviceAuftrag.kunde.Vorname} {skiserviceAuftrag.kunde.Nachname}"
    kundeName = kundeName.strip()

    bisDatum = skiserviceAuftrag.abhol_date

    for ski in skiserviceAuftrag.skis:
        logger.info(f"Ski Ettiket wird erstellt {ski.name}")

        skiName = ski.name or "Ski"

        skiUrl = f"{appHost}/skiservice/anzeigen/{skiserviceAuftrag.id}?ski={ski.id}"
        
        # Ettiket für Service
        serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,ski.service,ski.bindung_check,bisDatum)

        if ski.bindung_check:
            # Bei Bindung
            # zusätzlich ein Ettiket für den Schuh
            serviceEttiket.skiAuftragEttiket(kundeName, skiName,skiUrl,"SCHUH",False,bisDatum)


    logger.info("Alle Ettiketen erstellt, jetzt kommt der Druck")
    serviceEttiket.drucken()