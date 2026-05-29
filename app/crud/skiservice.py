from sqlalchemy.orm import Session, selectinload

from app.models.skiservice import Auftrag

def getSkiserviceAuftrag(db: Session, skiservice_auftrag_id: int, mitski: bool = True):
    if mitski:
        return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()