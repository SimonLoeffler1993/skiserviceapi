from sqlalchemy.orm import Session

from app.models.saisonverleih import SkiSaisonverleihPreise, SaisonVerleih

def get_saisonverleihpreise(db: Session,):
    # TODO mit Historie
    return db.query(SkiSaisonverleihPreise).all()

def get_saisonverleih(db: Session, saisonverleih_id: int):
    return db.query(SaisonVerleih).filter(SaisonVerleih.ID == saisonverleih_id).first()
    