from datetime import datetime

from sqlalchemy.orm import Session, selectinload

from app.models.skiservice import Auftrag

def getSkiserviceAuftrag(db: Session, skiservice_auftrag_id: int, mitski: bool = True):
    if mitski:
        return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()

def setzeSkiFertig(db: Session, skiservice_auftrag_id: int, ski_ids: list[int]):
    auftrag = db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    if not auftrag:
        return None
    
    alleFertig = True

    for ski in auftrag.skis:
        if ski.id in ski_ids:
            ski.status = 1  # Status auf "fertig" setzen
            ski.fertig_date = datetime.now().strftime("%d.%m.%Y")  # Fertigstellungsdatum setzen

        if ski.status != 1: # Wenn ein Ski nicht fertig ist, alleFertig auf False setzen
            alleFertig = False

    if alleFertig:
        auftrag.fertig_date = datetime.now().strftime("%d.%m.%Y")  # Auftragsfertigstellungsdatum setzen
        auftrag.wie = "1"  # Auftrag als fertig markieren
    

    db.commit()
    db.refresh(auftrag)
    return auftrag