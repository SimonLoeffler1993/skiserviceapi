from sqlalchemy.orm import Session
from app.models.materialski import EigenSki



def get_eigen_ski(db: Session, eigen_ski_nr: int):
    db_eigen_ski = db.query(EigenSki).filter(EigenSki.SkiNr.startswith(eigen_ski_nr)).all()
    if db_eigen_ski is None:
        return None
    return db_eigen_ski