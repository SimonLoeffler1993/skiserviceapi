from sqlalchemy.orm import Session
from app.models.quittung import Quittung

def get_quittung(db: Session, quittung_id: int):
    db_quittung = db.query(Quittung).filter(Quittung.ID == quittung_id).first()
    if db_quittung is None:
        return None
    return db_quittung