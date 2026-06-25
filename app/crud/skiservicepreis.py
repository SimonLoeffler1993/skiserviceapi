from sqlalchemy.orm import Session

from app.models.skiservicepreise import SkiServicePreise

def get_ski_service_preise(db: Session):
    return db.query(SkiServicePreise).all()