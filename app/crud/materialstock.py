from sqlalchemy.orm import Session
from app.models.materialstock import Skistock

def get_alle_skistocke(db: Session):
    return db.query(Skistock).all()