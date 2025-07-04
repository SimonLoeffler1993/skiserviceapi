from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.kunde import SkiKunde
from app.schemas.kunde import SkiKundeSpeichern

def get_kunden(db: Session):
    return db.query(SkiKunde).all()

def get_kunde(db: Session, kunde_id: int):
    return db.query(SkiKunde).filter(SkiKunde.ID == kunde_id).first()

def search_kunde(db: Session, vorname: str, nachname: str):
    kunden = db.query(SkiKunde).filter(SkiKunde.Vorname.like(vorname + '%')).filter(SkiKunde.Nachname.like(nachname + '%')).all()
    # Falls Vor und Nachname vertauscht sind
    if not kunden:
        kunden = db.query(SkiKunde).filter(SkiKunde.Vorname.like(nachname + '%')).filter(SkiKunde.Nachname.like(vorname + '%')).all()
    return kunden

def erfassen_kunde(db: Session, kunde: SkiKundeSpeichern):
    try:

        # wen keine PLZ eingegebn wird NULL
        # BUG PLZ ind er DB auf String Plz kann auch mit 0 beginnen
        if kunde.Plz == "":
            tmpPlz = 0
        else:
            tmpPlz = kunde.Plz

        neuerKunde = SkiKunde(
            Vorname=kunde.Vorname,
            Nachname = kunde.Nachname,
            Strasse = kunde.Strasse,
            Plz = tmpPlz,
            Tel = kunde.Tel,
            Tel1 = kunde.Handy,
            Email = kunde.Email
        )      

        db.add(neuerKunde)
        db.commit()
        db.refresh(neuerKunde)
        db.close()
        return {
            "success": True,
            "id":neuerKunde.ID
            }
    except SQLAlchemyError as e:
        print(f"Fehler beim Kunde Speichern: {e}")
        return {
            "success": False,
            "id": None
            }
    
def update_kunde(db: Session, kunde_id: int, kunde: SkiKundeSpeichern):
    existing_kunde = db.query(SkiKunde).filter(SkiKunde.ID == kunde_id).first()
    existing_kunde.Vorname = kunde.Vorname
    existing_kunde.Nachname = kunde.Nachname
    existing_kunde.Strasse = kunde.Strasse
    existing_kunde.Plz = kunde.Plz
    existing_kunde.Tel = kunde.Tel
    existing_kunde.Tel1 = kunde.Handy
    existing_kunde.Email = kunde.Email
    db.commit()
    return {
        "success": True,
        "kunde":existing_kunde
    }

