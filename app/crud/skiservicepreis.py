from sqlalchemy.orm import Session

from app.models.skiservicepreise import SkiServicePreise
from app.schemas.skiservicepreise import SkiServicePreiseBase

def get_ski_service_preise(db: Session):
    return db.query(SkiServicePreise).all()

def create_ski_service_preis(db: Session, preis_data: SkiServicePreiseBase):
    # db_service_preis = SkiServicePreiseBase(**preis_data.model_dump())
    new_preis = SkiServicePreise(
        Service=preis_data.service,
        Preis=str(preis_data.preis),
        Bindung=preis_data.bindung
    )
    db.add(new_preis)
    db.commit()
    db.refresh(new_preis)
    return new_preis