from sqlalchemy.orm import Session
from app.models.materialschuh import EigenSchuh, VerleihSchuhHersteller, VerleihSchuhModell
from app.schemas.materialschuh import VerleihSchuhHerstellerBase, VerleihSchuhModellBase, EigenSchuhBase

def get_eigen_schuhe(db: Session, eigen_schuh_nr: str):
    db_eigen_schuhe = db.query(EigenSchuh).filter(EigenSchuh.ID == eigen_schuh_nr).first()
    if db_eigen_schuhe is None:
        return None
    return db_eigen_schuhe

def get_eigen_schuhe_liste(db: Session):
    return db.query(EigenSchuh).all()

def create_hersteller(db: Session, schuh: VerleihSchuhHerstellerBase):
    db_schuh = VerleihSchuhHersteller(**schuh.model_dump())
    db.add(db_schuh)
    db.commit()
    db.refresh(db_schuh)
    return db_schuh

def get_hersteller(db: Session):
    return db.query(VerleihSchuhHersteller).all()

def create_modell(db: Session, modell: VerleihSchuhModellBase):
    db_modell = VerleihSchuhModell(**modell.model_dump())
    db.add(db_modell)
    db.commit()
    db.refresh(db_modell)
    return db_modell

def get_modelle(db: Session):
    return db.query(VerleihSchuhModell).all()

def create_eigen_schuhe(db: Session, schuh: EigenSchuhBase):
    db_schuh = EigenSchuh(**schuh.model_dump())
    db.add(db_schuh)
    db.commit()
    db.refresh(db_schuh)
    return db_schuh