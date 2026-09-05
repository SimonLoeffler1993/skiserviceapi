from sqlalchemy.orm import Session
from app.models.saison import Saison
from app.schemas.saison import SaisonErstellen

def get_AktuelleSaison(db: Session):
    return db.query(Saison).filter(Saison.Verwendet == 1).first()

def get_next_SaisonVerleihNummer(db: Session):
    # TODO: #15 Saisonnummer erstllen überarbeiten, auch in DB wegen Sicherung
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


def erfasse_saison(db: Session, saison: SaisonErstellen):
    db_saison = Saison(
        Start=saison.Start,
        Ende=saison.Ende,
        Name=saison.Name,
        Verwendet=saison.Verwendet
    )
    db.add(db_saison)
    db.commit()
    db.refresh(db_saison)
    return db_saison
