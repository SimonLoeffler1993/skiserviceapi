from sqlalchemy.orm import Session
from app.models.materialstock import Skistock

def get_alle_skistocke(db: Session):
    return db.query(Skistock).all()

def create_skistock(db: Session, bezeichnung: str):
    db_skistock = Skistock(Bezeichnung=bezeichnung)
    db.add(db_skistock)
    db.commit()
    db.refresh(db_skistock)
    return db_skistock