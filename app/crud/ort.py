from sqlalchemy.orm import Session
from sqlalchemy import cast, String

from app.models.ort import Ort

def get_orte(db: Session, plz: str):
    return db.query(Ort).filter(cast(Ort.Postlz, String).startswith(plz)).all()