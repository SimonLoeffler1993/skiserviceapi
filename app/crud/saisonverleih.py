from sqlalchemy.orm import Session
import datetime
from typing import Optional

from app.models.saisonverleih import SkiSaisonverleihPreise, SaisonVerleih, SaisonVerleihMaterial
from app.schemas.saisonverleih import SaisonVerleihCreate
from app.crud import saison as crud_saison
from app.utils.skiEttiket import SkiEttiket
from app.core.config import EttikettierSettings


def get_saisonverleihpreise(db: Session,):
    # TODO mit Historie
    return db.query(SkiSaisonverleihPreise).all()

def get_saisonverleih(db: Session, saisonverleih_id: int):
    return db.query(SaisonVerleih).filter(SaisonVerleih.ID == saisonverleih_id).first()

def get_saisonverleih_liste(db: Session, saisonID: Optional[int] = None ):
    if saisonID is not None:
        return db.query(SaisonVerleih).filter(SaisonVerleih.Saison_ID == saisonID).all()
    SkiSaison = crud_saison.get_AktuelleSaison(db)
    return db.query(SaisonVerleih).filter(SaisonVerleih.Saison_ID == SkiSaison.ID).all()

def create_saisonverleih(db: Session, saisonverleih: SaisonVerleihCreate):

    # Namen in Array
    printNamen = []

    try:
        if saisonverleih.Saison_ID is not None:
            Saison_ID=saisonverleih.Saison_ID,
        else:
            SkiSaison=crud_saison.get_AktuelleSaison(db)
            Saison_ID=SkiSaison.ID,
        
        db_saisonverleih = SaisonVerleih(
            Kunde_ID=saisonverleih.Kunde_ID,
            Bezahlt = False,
            Ueberweisung=0,
            Bemerkung=saisonverleih.Bemerkung,
            Name=crud_saison.get_next_SaisonVerleihNummer(db),
            Saison_ID=Saison_ID,
            Abgerechnet=saisonverleih.Abgerechnet,
            Start_Am=datetime.date.today(),
            QuittungID=saisonverleih.QuittungID
        )

        for material in saisonverleih.Material:

            # Namen für Etikett
            if not material.SkiFahrerName or material.SkiFahrerName.strip() != "": 
                printNamen.append(material.SkiFahrerName)

            if material.stockbez_ID == -1:
                stockbez_ID=None,
            else:
                stockbez_ID=material.stockbez_ID,

            db_saisonverleih.Material.append(
                SaisonVerleihMaterial(
                    skinr=material.skinr,
                    schuhnr=material.schuhnr,
                    stockbez_ID=stockbez_ID,
                    stocklaenge=material.stocklaenge,
                    Preis=material.Preis,
                    SkiFahrerName=material.SkiFahrerName
                )
            )

        db.add(db_saisonverleih)
        db.commit()
        db.refresh(db_saisonverleih)

        # Etiketten drucken
        # Druck Job wird extra gemacht falls was schief geht
        if EttikettierSettings.printErstellung:
            label = SkiEttiket()
            for name in printNamen:
                label.saisonFahererName(name)

            label.drucken()


        return {
            "success": True,
            "data":db_saisonverleih
            }

    except Exception as e:
        print(f"Fehler beim Saisonverleih Speichern: {e}")
        return {
            "success": False,
            "data": None
            }
    