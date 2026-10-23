from sqlalchemy.orm import Session
from app.models.saison import Saison
from app.schemas.saison import SaisonErstellen
from app.services import einstellungen

def get_AktuelleSaison(db: Session):
    return db.query(Saison).filter(Saison.Verwendet == 1).first()

def get_next_SaisonVerleihNummer(db: Session, art: str = "saison"):
    """
    Erhöht den Nummernzähler der aktuellen Saison und gibt die neue Verleihnummer zurück.
    Saison- und Tagesverleih haben getrennte Nummernkreise.
    Die Zeile wird gesperrt, damit parallele Anfragen keine doppelte Nummer erhalten.
    Es wird nicht committet, damit die Nummer zusammen mit dem Verleih gespeichert wird.
    """
    saisonData = (
        db.query(Saison)
        .filter(Saison.Verwendet == 1)
        .with_for_update()
        .first()
    )
    if saisonData is None:
        raise ValueError("Keine aktuelle Saison vorhanden.")

    # Nummer eins höher setzen
    if art == "tag":
        nexteNummer = (saisonData.TagesVerleihNummer or 0) + 1
        saisonData.TagesVerleihNummer = nexteNummer
        return saisonData.Name + einstellungen.hole("KUERZEL_TAGESVERLEIH") + str(nexteNummer)

    nexteNummer = (saisonData.SaisonVerleihNummer or 0) + 1
    saisonData.SaisonVerleihNummer = nexteNummer
    return saisonData.Name + einstellungen.hole("KUERZEL_SAISONVERLEIH") + str(nexteNummer)


def get_next_QuittungNummer(db: Session) -> str:
    """
    Nächste Quittungsnummer der aktuellen Saison, z.B. "26/27Q12".
    Wie beim Verleih gesperrt und ohne Commit, die Nummer wird mit der Quittung gespeichert.
    """
    saisonData = (
        db.query(Saison)
        .filter(Saison.Verwendet == 1)
        .with_for_update()
        .first()
    )
    if saisonData is None:
        raise ValueError("Keine aktuelle Saison vorhanden.")

    nexteNummer = (saisonData.QuittungNummer or 0) + 1
    saisonData.QuittungNummer = nexteNummer
    return saisonData.Name + einstellungen.hole("KUERZEL_QUITTUNG") + str(nexteNummer)


def get_all_saisons(db: Session):
    return db.query(Saison).all()


def erfasse_saison(db: Session, saison: SaisonErstellen):
    # Es darf nur eine aktuelle Saison geben
    if saison.Verwendet == 1:
        db.query(Saison).filter(Saison.Verwendet == 1).update({Saison.Verwendet: 0})

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
