# app/services/kasse_service.py

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.skiservice import Auftrag, Ski
from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.schemas.kasse import KasseBezahlenSchema, KasseHatBezahltSchema, KassenArtikelSchema, KasseEinzelArtikelSchema
from app.models.kunde import SkiKunde
from app.models.quittung import Quittung, QuittungArtikel
from app.crud import saison as crud_saison

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
            service=True,
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
            .filter(or_(SaisonVerleih.Bezahlt.is_(None), SaisonVerleih.Bezahlt == False))
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
            verleih=True,
        )

    def _material_zu_artikel(self, material: SaisonVerleihMaterial) -> list[KasseEinzelArtikelSchema]:
        positionen = []
  
        positionen.append(
            # TODO: bezeichnung das Material als String
            KasseEinzelArtikelSchema(
                id=material.ID,
                bezeichnung=material.saisonverleih.Bezeichnung if material.saisonverleih else "Saisonverleih",
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

    def bezahlen(self, zuBezahlen: KasseBezahlenSchema) -> KasseHatBezahltSchema:
        """
        Es wird eine Quittung erstellt und die angegebenen Artikels als bezahlt markiert.
        Alles passiert in einer Transaktion: entweder wird alles gespeichert oder nichts.
        Bereits bezahlte Artikel werden abgelehnt.
        """
        if not zuBezahlen.artikels:
            raise ValueError("Keine Artikel zum Bezahlen übergeben.")

        aktuelle_Saison = crud_saison.get_AktuelleSaison(self.db)
        if aktuelle_Saison is None:
            raise ValueError("Keine aktuelle Saison gefunden.")

        try:
            quittung = Quittung(
                Name="Quittung",
                AnzAuftrag=0,
                AnzVerleih=0,
                Saison_ID=aktuelle_Saison.ID,
                Bezahlt_Am=date.today(),
                Erstellt_Am=date.today(),
                Ueberweisung=zuBezahlen.ueberweisung,
                Karte=zuBezahlen.karte,
                Bar=zuBezahlen.bar,
                Bezahlt=True,
                BuchhaltungSync=False,
                LexID="",
                NurExtern=False
            )
            self.db.add(quittung)
            # ID der Quittung holen, ohne zu committen
            self.db.flush()

            for artikel in zuBezahlen.artikels:
                if artikel.service:
                    auftrag = (
                        self.db.query(Auftrag)
                        .filter(Auftrag.id == artikel.id)
                        .with_for_update()
                        .first()
                    )
                    if auftrag is None:
                        raise ValueError(f"Auftrag {artikel.id} nicht gefunden.")
                    if auftrag.bezahlt == "ja":
                        raise ValueError(f"Auftrag {auftrag.name} ist bereits bezahlt.")

                    # Markiere den Auftrag als bezahlt und aktualisiere die Quittung_ID
                    auftrag.bezahlt = "ja"
                    auftrag.bezahlt_am = date.today()
                    auftrag.quittung_id = quittung.ID
                    quittung.AnzAuftrag += 1

                    # Skiservice Auftrag als Quittungsartikel hinzufügen
                    self.db.add(QuittungArtikel(
                        Quittung_ID=quittung.ID,
                        Artikel_ID=auftrag.id,
                        Artikel_Kategorie="Skiservice",
                        Auftrag_ID=auftrag.id,
                        Verleih_ID=None
                    ))

                elif artikel.verleih:
                    verleih = (
                        self.db.query(SaisonVerleih)
                        .filter(SaisonVerleih.ID == artikel.id)
                        .with_for_update()
                        .first()
                    )
                    if verleih is None:
                        raise ValueError(f"Verleih {artikel.id} nicht gefunden.")
                    if verleih.Bezahlt:
                        raise ValueError(f"Verleih {verleih.Name} ist bereits bezahlt.")

                    # Markiere den Verleih als bezahlt und aktualisiere die Quittung_ID
                    verleih.Bezahlt = True
                    verleih.Bezahlt_Am = date.today()
                    verleih.QuittungID = quittung.ID
                    quittung.AnzVerleih += 1

                    # Verleih als Quittungsartikel hinzufügen
                    self.db.add(QuittungArtikel(
                        Quittung_ID=quittung.ID,
                        Artikel_ID=verleih.ID,
                        Artikel_Kategorie="Verleih",
                        Auftrag_ID=None,
                        Verleih_ID=verleih.ID
                    ))

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(quittung)

        return KasseHatBezahltSchema(
            quittung_id=quittung.ID,
            bezahldatum=str(quittung.Bezahlt_Am),
            success=True
        )
