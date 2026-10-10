# app/services/kasse_service.py

from sqlalchemy.orm import Session

from app.models.skiservice import Auftrag, Ski
from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.schemas.kasse import KassenArtikelSchema, KasseEinzelArtikelSchema
from app.models.kunde import SkiKunde

def get_kundenname(kunde: SkiKunde | None) -> str:
    if kunde is not None:
        return f"{kunde.Vorname or ''} {kunde.Nachname or ''}".strip() or "Unbekannt"
    return "Unbekannt"


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
            kundenname=get_kundenname(auftrag.kunde),
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

    def get_offene_verleih(self) -> list[KassenArtikelSchema]:
        verleih = (
            self.db.query(SaisonVerleih)
            .filter(SaisonVerleih.Bezahlt != True)
            .all()
        )
        return [self._verleih_zu_kassenartikel(a) for a in verleih]

    def _verleih_zu_kassenartikel(self, verleih: SaisonVerleih) -> KassenArtikelSchema:
        artikel = [self._material_zu_artikel(m) for m in verleih.Material]
        artikel = [item for sublist in artikel for item in sublist]  # flatten

        gesamtpreis = sum(a.preis for a in artikel)

        kundenname = get_kundenname(verleih.Kunde)

        return KassenArtikelSchema(
            id=verleih.ID,
            kundenname=kundenname,
            artikelname=verleih.Name,
            gesamtpreis=gesamtpreis,
            artikel=artikel,
        )

    def _material_zu_artikel(self, material: SaisonVerleihMaterial) -> list[KasseEinzelArtikelSchema]:
        positionen = []
  
        positionen.append(
            # TODO: bezeichnung das Material als String
            KasseEinzelArtikelSchema(
                id=material.ID,
                bezeichnung=f"Saisonverleih",
                preis=float(material.Preis),
            )
        )
        # if material.Schuh:
        #     positionen.append(
        #         KasseEinzelArtikelSchema(
        #             id=material.ID,
        #             bezeichnung=f"Schuh {material.Schuh.ID}",
        #             preis=float(material.Preis),
        #         )
        #     )
        # if material.Stock:
        #     positionen.append(
        #         KasseEinzelArtikelSchema(
        #             id=material.ID,
        #             bezeichnung=f"Stock {material.Stock.stockbez_ID}",
        #             preis=float(material.Preis),
        #         )
        #     )
        return positionen