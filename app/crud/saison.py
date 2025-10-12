from sqlalchemy.orm import Session
from app.models.saison import Saison

def get_AktuelleSaison(db: Session):
    return db.query(Saison).filter(Saison.Verwendet == 1).first()

def get_next_SaisonVerleihNummer(db: Session):
    
    saisonData = db.query(Saison).filter(Saison.Verwendet == 1).first()

    # Nummer eins höher setzen
    nexteNummer = saisonData.SaisonVerleihNummer + 1

    # in der Saison speichern
    saisonData.SaisonVerleihNummer = nexteNummer
    db.commit()
    db.refresh(saisonData)

    # TODO Kürzel in Einstellungen frei Devinierbar machen   
    return saisonData.Name + "SV" + str(nexteNummer)


def get_all_saisons(db: Session):
    return db.query(Saison).all()