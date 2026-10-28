from sqlalchemy.orm import Session
from datetime import datetime
from app.models.quittung import Quittung
from app.models.saisonverleih import SaisonVerleih
from app.models.skiservice import Auftrag
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

def create_NurExtern_quittung(db: Session, lexoffice_id: str, name: str = "EXTERNER BELEG", commit: bool = True):
    """
    Legt eine Quittung an, deren Beleg nur in Lexware existiert (für Saisonverleih oder Skiservice).
    Mit commit=False wird nur geflusht, z.B. beim Bezahlen an der Kasse in einer gemeinsamen Transaktion.
    """
    aktuelle_saison = crud_saison.get_AktuelleSaison(db)
    if aktuelle_saison is None:
        raise ValueError("Keine aktuelle Saison gefunden. Bitte erstelle eine Saison, bevor du eine Quittung erstellst.")
    
    db_quittung = Quittung(
        Saison_ID=aktuelle_saison.ID,
        LexID=lexoffice_id,
        NurExtern=True,
        BuchhaltungSync=True,
        Bezahlt=False,
        Name=name,
        Erstellt_Am = datetime.now().date()
    )
    db.add(db_quittung)
    if commit:
        db.commit()
        db.refresh(db_quittung)
    else:
        db.flush()

    return db_quittung


def quittung_verwendet(db: Session, quittung_id: int) -> bool:
    """Zeigt noch ein Saisonverleih oder Skiservice-Auftrag auf die Quittung?"""
    verleih = db.query(SaisonVerleih.ID).filter(SaisonVerleih.QuittungID == quittung_id).first()
    auftrag = db.query(Auftrag.id).filter(Auftrag.quittung_id == quittung_id).first()
    return verleih is not None or auftrag is not None
