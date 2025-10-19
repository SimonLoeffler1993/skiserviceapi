from sqlalchemy.orm import Session
from app.models.materialski import EigenSki, VerleihSkiHersteller, SkiArt, VerleihSkiModell



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

def get_skiart(db: Session):
    return db.query(SkiArt).all()

def create_ski_modell(db: Session, modell):
    db_modell = VerleihSkiModell(
        Modell=modell.Modell,
        Art_ID=modell.Art_ID,
        Hersteller_ID=modell.Hersteller_ID
    )
    db.add(db_modell)
    db.commit()
    db.refresh(db_modell)
    return db_modell

def get_ski_modell(db: Session):
    return db.query(VerleihSkiModell).all() 