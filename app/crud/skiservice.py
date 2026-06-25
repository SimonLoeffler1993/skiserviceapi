from datetime import datetime, date

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import update
from sqlalchemy.engine import CursorResult

from app.models.skiservice import Auftrag, Ski, AuftragNummer
from app.crud import saison as crud_saison
from app.schemas.skiservice import AuftragCreateSchema

def getSkiserviceAuftrag(db: Session, skiservice_auftrag_id: int, mitski: bool = True):
    if mitski:
        return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()

def setzeSkiFertig(db: Session, skiservice_auftrag_id: int, ski_ids: list[int]):
    auftrag = db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    if not auftrag:
        return None, False
    
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
    return auftrag, alleFertig

def setzeBenachrichtigt(db: Session, skiservice_auftrag_id: int, benachrichtigt: bool = True):
    auftrag = db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()
    if not auftrag:
        return False
    
    if benachrichtigt:
        auftrag.benachrichtigt = "Ja"
    else:
        auftrag.benachrichtigt = "Nein"

    db.commit()
    db.refresh(auftrag)
    return True

def neuAuftragNummer(db: Session):
    neu = AuftragNummer(
        Jahr=datetime.now().year
    )
    db.add(neu)
    db.commit()
    db.refresh(neu)
    return neu

def createSkiserviceAuftrag(db: Session, auftrag_data: AuftragCreateSchema):

    aktuelle_saison = crud_saison.get_AktuelleSaison(db)
    if aktuelle_saison is None:
        return None
    
    auftragNummer = neuAuftragNummer(db)
    name = aktuelle_saison.Name+ "S" + str(auftragNummer.NeuNr)

    new_auftrag = Auftrag(
        kunden_id=auftrag_data.kunden_id,
        abhol_date=auftrag_data.abhol_date,
        zu= str(aktuelle_saison.ID),
        name=name,
        skis=[Ski(
            name=f"{name}-{i+1}",
            service=ski.service,
            preis=ski.preis,
            komentar=ski.komentar,
            bindung_preis=ski.bindung_preis,
            bindung_check=ski.bindung_check
        ) for i, ski in enumerate(auftrag_data.skis)]
    )
    db.add(new_auftrag)
    db.commit()
    db.refresh(new_auftrag)
    return new_auftrag

def setzeBindungGeprueft(db: Session, ski_ids: list[int]) -> bool:
    skis = db.query(Ski).filter(Ski.id.in_(ski_ids)).all()
    
    if not skis:
        return False

    for ski in skis:
        ski.bindung_status = True
        ski.gepueft = date.today()

    db.commit()
    return True