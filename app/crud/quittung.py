from sqlalchemy.orm import Session
from datetime import datetime
from app.models.quittung import Quittung
from app.crud import saison as crud_saison


def get_quittung(db: Session, quittung_id: int):
    db_quittung = db.query(Quittung).filter(Quittung.ID == quittung_id).first()
    if db_quittung is None:
        return None
    
    # NULL-Werte normalisieren
    db_quittung.AnzAuftrag = db_quittung.AnzAuftrag or 0
    db_quittung.AnzVerleih = db_quittung.AnzVerleih or 0
    db_quittung.Ueberweisung = db_quittung.Ueberweisung or False
    db_quittung.Bezahlt = db_quittung.Bezahlt or False
    db_quittung.BuchhaltungSync = db_quittung.BuchhaltungSync or False
    db_quittung.NurExtern = db_quittung.NurExtern or False

    return db_quittung

def create_NurExtern_quittung(db: Session, lexoffice_id: str):
    """Legt eine Quittung an, deren Beleg nur in Lexware existiert (für Saisonverleih oder Skiservice)."""
    aktuelle_saison = crud_saison.get_AktuelleSaison(db)
    if aktuelle_saison is None:
        raise ValueError("Keine aktuelle Saison gefunden. Bitte erstelle eine Saison, bevor du eine Quittung erstellst.")
    
    # TODO: #5 Externe Beleggname bei Name eintragen beim erstellen eines nur externen Beleg

    db_quittung = Quittung(
        Saison_ID=aktuelle_saison.ID,
        LexID=lexoffice_id,
        NurExtern=True,
        BuchhaltungSync=True,
        Bezahlt=False,
        Name = "EXTERNER BELEG",
        Erstellt_Am = datetime.now().date()
    )
    db.add(db_quittung)
    db.commit()
    db.refresh(db_quittung)

    return db_quittung