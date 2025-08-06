from sqlalchemy.orm import Session

from app.models.saisonverleih import SkiSaisonverleihPreise

def get_saisonverleihpreise(db: Session,):
    # TODO mit Historie
    return db.query(SkiSaisonverleihPreise).all()