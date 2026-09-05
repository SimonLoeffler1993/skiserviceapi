# app/services/kasse_service.py

from sqlalchemy.orm import Session

from app.models.skiservice import Auftrag, Ski
from app.schemas.kasse import KassenArtikelSchema, KasseEinzelArtikelSchema


class KasseService:
    def __init__(self, db: Session):
        self.db = db

    def get_offene_auftraege(self) -> list[KassenArtikelSchema]:
        auftraege = (
            self.db.query(Auftrag)
            .filter(Auftrag.bezahlt == "nein")
            .all()
        )
        return [self._auftrag_zu_kassenartikel(a) for a in auftraege]

    def _auftrag_zu_kassenartikel(self, auftrag: Auftrag) -> KassenArtikelSchema:
        artikel = [self._ski_zu_artikel(ski) for ski in auftrag.skis]
        artikel = [item for sublist in artikel for item in sublist]  # flatten

        gesamtpreis = sum(a.preis for a in artikel)

        return KassenArtikelSchema(
            id=auftrag.id,
            kundenname=f"{auftrag.kunde.Vorname} {auftrag.kunde.Nachname}",
            artikelname=auftrag.name,
            gesamtpreis=gesamtpreis,
            artikel=artikel,
        )

    def _ski_zu_artikel(self, ski: Ski) -> list[KasseEinzelArtikelSchema]:
        positionen = [
            KasseEinzelArtikelSchema(
                id=ski.id,
                bezeichnung=ski.service,
                preis=float(ski.preis),
            )
        ]
        if ski.bindung_check and ski.bindung_preis:
            positionen.append(
                KasseEinzelArtikelSchema(
                    id=ski.id * -1,
                    bezeichnung="Bindung montieren",
                    preis=float(ski.bindung_preis),
                )
            )
        return positionen