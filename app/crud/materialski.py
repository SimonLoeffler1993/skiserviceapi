from sqlalchemy.orm import Session
from app.models.materialski import EigenSki, VerleihSkiHersteller



def get_eigen_ski(db: Session, eigen_ski_nr: int):
    db_eigen_ski = db.query(EigenSki).filter(EigenSki.SkiNr.startswith(eigen_ski_nr)).all()
    if db_eigen_ski is None:
        return None
    return db_eigen_ski

def get_hersteller(db: Session):
    return db.query(VerleihSkiHersteller).all()

def create_hersteller(db: Session, hersteller: str):
    db_hersteller = VerleihSkiHersteller(Name=hersteller)
    db.add(db_hersteller)
    db.commit()
    db.refresh(db_hersteller)
    return db_hersteller