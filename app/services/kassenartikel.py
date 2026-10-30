# app/services/kasse_service.py

import logging
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.skiservice import Auftrag, Ski
from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.schemas.kasse import KasseBezahlenSchema, KasseHatBezahltSchema, KassenArtikelSchema, KasseEinzelArtikelSchema
from app.models.kunde import SkiKunde
from app.models.quittung import Quittung, QuittungArtikel
from app.models.handware import Handware
from app.crud import saison as crud_saison
from app.crud import quittung as crud_quittung
from app.services.lexware_sync import lexware_modus, rechnung_anlegen
from app.services.quittung import material_bezeichnung, handware_gruppe

logger = logging.getLogger(__name__)

def _kunden_emails(kunden: list[SkiKunde | None]) -> list[str]:
    """Verschiedene E-Mail Adressen der Kunden in der Reihenfolge der Artikel."""
    emails: dict[str, str] = {}
    for kunde in kunden:
        email = (kunde.Email or "").strip() if kunde else ""
        if email:
            emails.setdefault(email.lower(), email)
    return list(emails.values())

def _ohne_quittung(spalte):
    """Noch keine Quittung zugeordnet, alte Daten haben teils 0 statt NULL."""
    return or_(spalte.is_(None), spalte == 0)

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
            .filter(Auftrag.bezahlt == "nein", _ohne_quittung(Auftrag.quittung_id))
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

    def get_handware(self) -> list[KassenArtikelSchema]:
        return [
            KassenArtikelSchema(
                id=h.ID,
                kundenname=h.Kategorie or "",
                artikelname=h.Name,
                gesamtpreis=h.Preis,
                artikel=[KasseEinzelArtikelSchema(id=h.ID, bezeichnung=h.Name, preis=h.Preis)],
                handware=True,
                bestand=h.Anzahl,
            )
            for h in self.db.query(Handware).order_by(Handware.Kategorie, Handware.Name).all()
        ]

    def get_offene_verleih(self) -> list[KassenArtikelSchema]:
        verleih = (
            self.db.query(SaisonVerleih)
            .filter(or_(SaisonVerleih.Bezahlt.is_(None), SaisonVerleih.Bezahlt == False), _ohne_quittung(SaisonVerleih.QuittungID))
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
            KasseEinzelArtikelSchema(
                id=material.ID,
                bezeichnung=material_bezeichnung(material),
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
        Im Lexware Modus "rechnung" wird statt der eigenen Quittung eine Rechnung in Lexware angelegt
        und in der Anwendung nur eine externe Quittung hinterlegt.
        """
        if not zuBezahlen.artikels:
            raise ValueError("Keine Artikel zum Bezahlen übergeben.")

        aktuelle_Saison = crud_saison.get_AktuelleSaison(self.db)
        if aktuelle_Saison is None:
            raise ValueError("Keine aktuelle Saison gefunden.")

        lex_id = None
        try:
            # Erst alles sperren und prüfen, damit Lexware nur bei gültigen Artikeln angefragt wird
            auftraege: list[Auftrag] = []
            verleihe: list[SaisonVerleih] = []
            # Handware mit verkaufter Menge, gleicher Artikel mehrfach wird zusammengezählt
            handware: dict[int, tuple[Handware, int]] = {}
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
                    if auftrag.quittung_id:
                        raise ValueError(f"Auftrag {auftrag.name} hat bereits eine Quittung.")
                    auftraege.append(auftrag)

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
                    if verleih.QuittungID:
                        raise ValueError(f"Verleih {verleih.Name} hat bereits eine Quittung.")
                    verleihe.append(verleih)

                elif artikel.handware:
                    if artikel.id in handware:
                        h, menge = handware[artikel.id]
                        handware[artikel.id] = (h, menge + artikel.menge)
                        continue
                    h = (
                        self.db.query(Handware)
                        .filter(Handware.ID == artikel.id)
                        .with_for_update()
                        .first()
                    )
                    if h is None:
                        raise ValueError(f"Artikel {artikel.artikelname} nicht gefunden.")
                    handware[artikel.id] = (h, artikel.menge)

            # Positionen mit Preis aus der DB, nicht vom Client
            handware_artikel = [
                QuittungArtikel(
                    Artikel_ID=h.ID,
                    Artikel_Kategorie="Handware",
                    Auftrag_ID=None,
                    Verleih_ID=None,
                    Bezeichnung=h.Name,
                    Preis=h.Preis,
                    Menge=menge,
                )
                for h, menge in handware.values()
            ]

            if lexware_modus() == "rechnung":
                kunden = {k.ID: k for k in [a.kunde for a in auftraege] + [v.Kunde for v in verleihe] if k is not None}
                gruppe = handware_gruppe(handware_artikel)
                lex_id, nummer = rechnung_anlegen(
                    self.db, [a.id for a in auftraege], [v.ID for v in verleihe], kunden,
                    bar=zuBezahlen.bar, karte=zuBezahlen.karte, ueberweisung=zuBezahlen.ueberweisung,
                    zusatz_gruppen=[gruppe] if gruppe else [],
                )
                quittung = crud_quittung.create_NurExtern_quittung(self.db, lex_id, name=nummer, commit=False)
                quittung.Bezahlt_Am = date.today()
                quittung.Ueberweisung = zuBezahlen.ueberweisung
                quittung.Karte = zuBezahlen.karte
                quittung.Bar = zuBezahlen.bar
                quittung.AnzAuftrag = 0
                quittung.AnzVerleih = 0
            else:
                quittung = Quittung(
                    Name=crud_saison.get_next_QuittungNummer(self.db),
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

            for auftrag in auftraege:
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

            for verleih in verleihe:
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

            for position in handware_artikel:
                position.Quittung_ID = quittung.ID
                self.db.add(position)
            # Anzahl nur zur Orientierung: abziehen, auch ins Minus
            for h, menge in handware.values():
                if h.Anzahl is not None:
                    h.Anzahl -= menge

            self.db.commit()
        except Exception:
            self.db.rollback()
            if lex_id:
                logger.error("Lexware Rechnung %s wurde angelegt, die Zahlung konnte aber nicht gespeichert werden. "
                             "Bitte die Rechnung in Lexware prüfen bzw. stornieren.", lex_id)
            raise

        self.db.refresh(quittung)

        return KasseHatBezahltSchema(
            quittung_id=quittung.ID,
            bezahldatum=str(quittung.Bezahlt_Am),
            success=True,
            quittung_nummer=quittung.Nummer,
            emails=_kunden_emails([a.kunde for a in auftraege] + [v.Kunde for v in verleihe]),
        )
