"""
Übertragung bezahlter Quittungen an Lexware Office. Zwei Modi (Einstellung LEXWARE_MODUS):
- pdf:      eigene Quittung als Buchhaltungsbeleg (Voucher) anlegen und das Quittungs-PDF anhängen
- rechnung: Rechnung direkt in Lexware anlegen, in der Anwendung gibt es nur eine externe Quittung
Der Status in Lexware ist immer "open", die Zahlung wird in Lexware zugeordnet.
"""
import logging
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.kunde import SkiKunde
from app.models.quittung import Quittung
from app.schemas.quittung import QuittungGruppeArtikel, QuittungKundeSchema
from app.services import einstellungen
from app.services.quittung import (
    QuittungsService, _AuftragzuArtikel, _VerleihzuArtikel, _quittung_kunde, quittung_dateiname, quittung_nummer,
)
from app.utils.lexware import LexwareAPI, LexwareFehler

logger = logging.getLogger(__name__)

# Buchungskategorien laut Lexware Doku (Vouchers Endpoint, "List of CategoryIds")
KATEGORIE_EINNAHMEN = "8f8664a1-fd86-11e1-a21f-0800200c9a66"
KATEGORIE_EINNAHMEN_KLEINUNTERNEHMER = "f5c7fee8-f184-4e7a-ab04-8f7e7ad6c207"

# Pause zwischen zwei Lexware Aufrufen (höchstens 2 Anfragen pro Sekunde)
PAUSE = 0.6


class SyncKonflikt(Exception):
    """Quittung kann nicht (mehr) übertragen werden, z.B. weil sie schon in Lexware liegt."""


def lexware_modus() -> str | None:
    """'pdf' oder 'rechnung', None wenn die Übertragung aus ist oder kein API Key hinterlegt ist."""
    if not einstellungen.hole("LEXWARE_SYNC") or not einstellungen.hole("LEXWARE_APIKEY"):
        return None
    return einstellungen.hole("LEXWARE_MODUS") or "pdf"


def _steuer() -> tuple[float, bool]:
    """Steuersatz in % und ob Kleinunternehmer (dann immer 0 %)."""
    kleinunternehmer = bool(einstellungen.hole("FIRMA_KLEINUNTERNEHMER"))
    satz = 0.0 if kleinunternehmer else float(einstellungen.hole("FIRMA_MWST_SATZ") or 0)
    return satz, kleinunternehmer


def _summe(gruppen: list[QuittungGruppeArtikel]) -> float:
    return round(sum(a.preis * a.anzahl for g in gruppen for a in g.artikels), 2)


def _bemerkung(gruppen: list[QuittungGruppeArtikel], kunde: QuittungKundeSchema | None) -> str:
    teile = [g.bezeichnung for g in gruppen]
    if kunde:
        teile.insert(0, f"Kunde: {kunde.name}")
    return " · ".join(teile)


# --- Modus pdf: eigene Quittung als Beleg mit PDF ---

def _beleg_daten(quittung: Quittung, gruppen: list[QuittungGruppeArtikel], kunde: QuittungKundeSchema | None) -> dict:
    satz, kleinunternehmer = _steuer()
    brutto = _summe(gruppen)
    steuer = round(brutto - brutto / (1 + satz / 100), 2)
    datum = quittung.Bezahlt_Am or quittung.Erstellt_Am or date.today()
    return {
        "type": "salesinvoice",
        "voucherStatus": "open",
        "voucherNumber": quittung_nummer(quittung),
        "voucherDate": datum.isoformat(),
        "totalGrossAmount": brutto,
        "totalTaxAmount": steuer,
        "taxType": "gross",
        "useCollectiveContact": True,
        "remark": f"Quittung {quittung_nummer(quittung)} · {_bemerkung(gruppen, kunde)}"[:1000],
        "voucherItems": [{
            "amount": brutto,
            "taxAmount": steuer,
            "taxRatePercent": satz,
            "categoryId": KATEGORIE_EINNAHMEN_KLEINUNTERNEHMER if kleinunternehmer else KATEGORIE_EINNAHMEN,
        }],
    }


def quittung_pdf_hochladen(db: Session, quittung_id: int) -> Quittung:
    """
    Legt für eine eigene Quittung einen Beleg in Lexware an und hängt das Quittungs-PDF an.
    Die Lexware ID wird sofort gespeichert: schlägt nur der Upload fehl, lädt der nächste Versuch
    nur noch die Datei hoch, ohne einen zweiten Beleg anzulegen.
    """
    quittung = db.get(Quittung, quittung_id)
    if quittung is None:
        raise LookupError(f"Quittung {quittung_id} nicht gefunden.")
    if quittung.NurExtern:
        raise SyncKonflikt("Externe Quittungen liegen bereits in Lexware.")
    if quittung.BuchhaltungSync:
        raise SyncKonflikt("Die Quittung wurde bereits an Lexware übertragen.")

    service = QuittungsService(db)
    daten = service.get_quittung(quittung_id)
    api = LexwareAPI()

    if not quittung.LexID:
        antwort = api.erstelle_beleg(_beleg_daten(quittung, daten.artikelgruppen, daten.kunde))
        quittung.LexID = antwort["id"]
        db.commit()
        logger.info("Quittung %s als Lexware Beleg %s angelegt", quittung_id, quittung.LexID)
        time.sleep(PAUSE)

    pdf = service.renderPDF(daten)
    api.lade_beleg_datei_hoch(quittung.LexID, pdf, quittung_dateiname(quittung))
    quittung.BuchhaltungSync = True
    db.commit()
    db.refresh(quittung)
    logger.info("PDF der Quittung %s an Lexware Beleg %s angehängt", quittung_id, quittung.LexID)
    return quittung


def quittung_pdf_hochladen_hintergrund(quittung_id: int):
    """Für BackgroundTasks nach dem Bezahlen: eigene DB Session, Fehler nur ins Log."""
    db = SessionLocal()
    try:
        quittung_pdf_hochladen(db, quittung_id)
    except Exception:
        logger.exception("Quittung %s konnte nicht an Lexware übertragen werden", quittung_id)
    finally:
        db.close()


# --- Modus rechnung: Rechnung direkt in Lexware ---

def _jetzt_lexware() -> str:
    """Datum im Lexware Format, z.B. 2026-10-23T14:05:00.000+02:00"""
    return datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="milliseconds")


def _adresse(kunde: QuittungKundeSchema | None) -> dict:
    """Einmalige Adresse (legt keinen Kontakt in Lexware an), bei mehreren Kunden "Sammelkunde"."""
    if kunde is None:
        return {"name": "Sammelkunde", "countryCode": "DE"}
    adresse = {"name": kunde.name or "Kunde", "countryCode": "DE"}
    if not kunde.sammel:
        if kunde.strasse:
            adresse["street"] = kunde.strasse
        if kunde.plz:
            adresse["zip"] = str(kunde.plz)
        if kunde.ort:
            adresse["city"] = kunde.ort
    return adresse


def _zahlungsarten(bar: bool, karte: bool, ueberweisung: bool) -> str:
    arten = [name for name, aktiv in (("Bar", bar), ("Karte", karte), ("Überweisung", ueberweisung)) if aktiv]
    return ", ".join(arten)


def rechnung_anlegen(db: Session, auftrag_ids: list[int], verleih_ids: list[int], kunden: dict[int, SkiKunde],
                     bar: bool = False, karte: bool = False, ueberweisung: bool = False) -> tuple[str, str]:
    """
    Legt für die Aufträge und Verleihe eine finalisierte Rechnung in Lexware an.
    Gibt die Lexware ID und die Rechnungsnummer zurück.
    """
    gruppen = [_AuftragzuArtikel(i, db) for i in auftrag_ids] + [_VerleihzuArtikel(i, db) for i in verleih_ids]
    satz, kleinunternehmer = _steuer()
    jetzt = _jetzt_lexware()

    positionen = []
    for gruppe in gruppen:
        for artikel in gruppe.artikels:
            preis = round(float(artikel.preis), 2)
            positionen.append({
                "type": "custom",
                "name": artikel.bezeichnung,
                "description": gruppe.bezeichnung,
                "quantity": artikel.anzahl,
                "unitName": "Stück",
                # Kleinunternehmer: steuerfrei, Netto = Brutto
                "unitPrice": {"currency": "EUR", "taxRatePercentage": satz,
                              **({"netAmount": preis} if kleinunternehmer else {"grossAmount": preis})},
            })
    if not positionen:
        raise LexwareFehler("Keine Positionen für die Rechnung vorhanden.")

    zahlung = _zahlungsarten(bar, karte, ueberweisung)
    daten = {
        "voucherDate": jetzt,
        "address": _adresse(_quittung_kunde(kunden)),
        "lineItems": positionen,
        "totalPrice": {"currency": "EUR"},
        "taxConditions": {"taxType": "vatfree" if kleinunternehmer else "gross"},
        "shippingConditions": {"shippingType": "service", "shippingDate": jetzt},
        "title": "Rechnung",
        "remark": f"Bezahlt{f' ({zahlung})' if zahlung else ''}. Vielen Dank!",
    }

    api = LexwareAPI()
    antwort = api.erstelle_rechnung(daten)
    lex_id = antwort["id"]
    time.sleep(PAUSE)
    try:
        nummer = api.hole_rechnung(lex_id).get("voucherNumber") or f"Lexware {lex_id[:8]}"
    except LexwareFehler:
        # Rechnung ist angelegt, nur die Nummer fehlt: nicht abbrechen
        logger.exception("Rechnungsnummer für Lexware Rechnung %s konnte nicht abgerufen werden", lex_id)
        nummer = f"Lexware {lex_id[:8]}"
    logger.info("Lexware Rechnung %s (%s) angelegt", nummer, lex_id)
    return lex_id, nummer
