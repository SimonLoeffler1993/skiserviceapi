from sqlalchemy.orm import Session
from app.models.materialschuh import EigenSchuh

def get_eigen_schuhe(db: Session, eigen_schuh_nr: str):
    db_eigen_schuhe = db.query(EigenSchuh).filter(EigenSchuh.ID == eigen_schuh_nr).first()

    # print(f"Debug: Retrieved EigenSchuh: {db_eigen_schuhe}")

    if db_eigen_schuhe is None:
        return None
    return db_eigen_schuhe

def get_eigen_schuhe_liste(db: Session):
    return db.query(EigenSchuh).all()