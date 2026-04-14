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

def get_saisonverleih_liste(db: Session, limit: int = 15, last_id: Optional[int] = None, saisonID: Optional[int] = None, alle: Optional[bool] = False):
    # Wenn keine Saison ID angegeben ist, nehme die aktuelle Saison
    if saisonID is None:
        SkiSaison = crud_saison.get_AktuelleSaison(db)
        if SkiSaison is not None:
            saisonID = SkiSaison.ID

    query = db.query(SaisonVerleih).filter(SaisonVerleih.Saison_ID == saisonID)

    # Wenn "alle" True ist, gebe alle Einträge zurück, andernfalls wende Pagination an
    if alle:
        return query.order_by(SaisonVerleih.ID).all()
    
    # Pagination anwenden
    if last_id is not None:
        query = query.filter(SaisonVerleih.ID > last_id)

    return query.order_by(SaisonVerleih.ID).limit(limit).all()

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

            if material.skinr == "":
                material.skinr=None,
            if material.schuhnr == "":
                material.schuhnr=None,

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
    
def set_Saisonverleih_Zurueck(db: Session, saisonverleih_id: int, zurueck: bool = True):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        return False
    saisonverleih.Zurueck_Am = datetime.date.today()
    saisonverleih.Zurueck = zurueck
    db.commit()
    db.refresh(saisonverleih)
    return True