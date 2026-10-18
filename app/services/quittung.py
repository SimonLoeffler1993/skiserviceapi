
from fastapi import HTTPException
from sqlalchemy.orm import Session
from collections import Counter

from app.models.quittung import Quittung
from app.schemas.quittung import QuittungArtikelSchema, QuittungOutSchema, QuittungsTyp
from app.crud import skiservice as crud_skiservice
from app.crud import saisonverleih as crud_saisonverleih


def _AuftragzuArtikel(auftrag_id: int, db: Session) -> list[QuittungArtikelSchema]:
    auftrag = crud_skiservice.getSkiserviceAuftrag(db, auftrag_id)
    service_Counter: Counter[tuple[str, float]] = Counter()
    bindung_Counter: Counter[float] = Counter()

    if not auftrag:
        return []
    
    for ski in auftrag.skis:
        # Wen Service und Preis identisch ist wird Hochgezählt
        service_Counter[(ski.service, ski.preis)] += 1
        if ski.bindung_check:
            bindung_Counter[ski.bindung_preis] += 1

    artikels: list[QuittungArtikelSchema] = []
        
    for (service, preis), anzahl in service_Counter.items():
        artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung=service,
            preis=preis,
            anzahl=anzahl,
            toID=auftrag_id
        ))

    for bindung_preis, anzahl in bindung_Counter.items():
        # TODO #27 Bindungscheck bezeichnung aus DB in der Quittung
        artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Auftrag,
            bezeichnung="Bindungscheck",
            preis=bindung_preis,
            anzahl=anzahl,
            toID=auftrag_id
        ))

    return artikels

def _VerleihzuArtikel(verleihID: int, db: Session) -> list[QuittungArtikelSchema]:
    # ertmal daten aus DB lesen
    verleih = crud_saisonverleih.get_saisonverleih(db, verleihID)
    # TODO #26 Verleih bezeichnung mit auf der Quittung
    verleih_counter: Counter[float] = Counter()

    #Wen nix gefunden wird auch nix zurück
    if not verleih:
        return []

    # artikel Init
    artikels: list[QuittungArtikelSchema] = []

    for ski in verleih.Material:
        verleih_counter[ski.Preis] += 1

    for verleih_Preis, anzahl in verleih_counter.items():
        artikels.append(QuittungArtikelSchema(
            type=QuittungsTyp.Verleih,
            bezeichnung="Saisonverleih",
            preis=verleih_Preis,
            anzahl=anzahl,
            toID=verleihID
        ))

    return artikels

class QuittungsService:
    def __init__(self, db: Session):
        self.db = db

    def get_quittung(self, quittung_id: int) -> QuittungOutSchema:
        quittung = self.db.query(Quittung).filter(Quittung.ID == quittung_id).first()

        # Wurde etwas geufnden?
        if not quittung:
            raise HTTPException(status_code=404, detail="Quittung not found")

        quittungOut = QuittungOutSchema(
            id=quittung.ID,
            name=quittung.Name,
            saison_ID=quittung.Saison_ID,
            bezahlt=quittung.Bezahlt,
            bezahlt_Am=quittung.Bezahlt_Am,
            ueberweisung=quittung.Ueberweisung,
            karte=quittung.Karte,
            bar=quittung.Bar,
            buchhaltungSync=quittung.BuchhaltungSync,
            lexID=quittung.LexID,
            nurExtern=quittung.NurExtern,
        )

        if quittung.NurExtern:
            pass #TODO Qittung direkt von Lexoffice holen und zurückgeben

           
        for artikel in quittung.artikels:
            if artikel.Auftrag_ID is not None:
                # mit extend anhängen
                quittungOut.artikels.extend(_AuftragzuArtikel(artikel.Auftrag_ID, self.db))

            if artikel.Verleih_ID is not None:
                quittungOut.artikels.extend(_VerleihzuArtikel(artikel.Verleih_ID, self.db))
        
        return quittungOut