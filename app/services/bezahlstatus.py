"""
Bezahlt-Status von Quittung, Skiservice-Auftrag und Saisonverleih gemeinsam ändern:
von Hand in der Detailansicht oder beim Abgleich mit Lexware.
"""
import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.quittung import Quittung
from app.models.saisonverleih import SaisonVerleih
from app.models.skiservice import Auftrag

logger = logging.getLogger(__name__)

# Lexware voucherStatus, die als bezahlt gelten ("paidoff" = ausgeglichen)
LEXWARE_BEZAHLT = ("paid", "paidoff")


def _auftrag_setzen(auftrag: Auftrag, bezahlt: bool, datum: date | None) -> bool:
    soll = "ja" if bezahlt else "nein"
    neues_datum = (auftrag.bezahlt_am or datum) if bezahlt else None
    if auftrag.bezahlt == soll and auftrag.bezahlt_am == neues_datum:
        return False
    auftrag.bezahlt = soll
    auftrag.bezahlt_am = neues_datum
    return True


def _verleih_setzen(verleih: SaisonVerleih, bezahlt: bool, datum: date | None) -> bool:
    neues_datum = (verleih.Bezahlt_Am or datum) if bezahlt else None
    if bool(verleih.Bezahlt) == bezahlt and verleih.Bezahlt_Am == neues_datum:
        return False
    verleih.Bezahlt = bezahlt
    verleih.Bezahlt_Am = neues_datum
    return True


def quittung_bezahlt_setzen(db: Session, quittung: Quittung, bezahlt: bool, datum: date) -> bool:
    """
    Setzt die Quittung und alle Aufträge und Verleihe darauf auf (nicht) bezahlt, ohne Commit.
    Ein schon vorhandenes Bezahldatum bleibt stehen (z.B. das der Kasse), "nicht bezahlt" löscht es.
    Gibt zurück, ob sich etwas geändert hat.
    """
    geaendert = False
    neues_datum = (quittung.Bezahlt_Am or datum) if bezahlt else None
    if bool(quittung.Bezahlt) != bezahlt or quittung.Bezahlt_Am != neues_datum:
        quittung.Bezahlt = bezahlt
        quittung.Bezahlt_Am = neues_datum
        geaendert = True
    for auftrag in db.query(Auftrag).filter(Auftrag.quittung_id == quittung.ID):
        geaendert |= _auftrag_setzen(auftrag, bezahlt, datum)
    for verleih in db.query(SaisonVerleih).filter(SaisonVerleih.QuittungID == quittung.ID):
        geaendert |= _verleih_setzen(verleih, bezahlt, datum)
    return geaendert


def lexware_bezahlt(lex_daten: dict) -> bool:
    return lex_daten.get("voucherStatus") in LEXWARE_BEZAHLT


def lexware_bezahlt_am(lex_daten: dict) -> date | None:
    if not lex_daten.get("paidDate"):
        return None
    return datetime.fromisoformat(lex_daten["paidDate"].replace("Z", "+00:00")).date()


def lexware_abgleichen(db: Session, quittung: Quittung, lex_daten: dict) -> bool:
    """
    Übernimmt "bezahlt" aus Lexware in Quittung, Aufträge und Verleihe.
    "Offen" in Lexware setzt nichts zurück: Kassen-Quittungen stehen dort offen, bis die Zahlung zugeordnet ist.
    Committet nur, wenn sich etwas geändert hat, und gibt das zurück.
    """
    if not lexware_bezahlt(lex_daten):
        return False
    datum = lexware_bezahlt_am(lex_daten) or date.today()
    if not quittung_bezahlt_setzen(db, quittung, True, datum):
        return False
    db.commit()
    db.refresh(quittung)
    logger.info("Quittung %s laut Lexware bezahlt, Status in der Datenbank angepasst", quittung.ID)
    return True


def auftrag_bezahlt_setzen(db: Session, auftrag_id: int, bezahlt: bool, mit_quittung: bool) -> Auftrag | None:
    """Setzt einen Auftrag von Hand auf (nicht) bezahlt, auf Wunsch mit seiner Quittung und deren Positionen."""
    auftrag = db.get(Auftrag, auftrag_id)
    if auftrag is None:
        return None
    heute = date.today()
    if mit_quittung and auftrag.quittung_id and (quittung := db.get(Quittung, auftrag.quittung_id)):
        quittung_bezahlt_setzen(db, quittung, bezahlt, heute)
    _auftrag_setzen(auftrag, bezahlt, heute)
    db.commit()
    logger.info("Auftrag %s von Hand auf %s gesetzt", auftrag_id, "bezahlt" if bezahlt else "nicht bezahlt")
    return auftrag


def verleih_bezahlt_setzen(db: Session, verleih_id: int, bezahlt: bool, mit_quittung: bool) -> SaisonVerleih | None:
    """Setzt einen Verleih von Hand auf (nicht) bezahlt, auf Wunsch mit seiner Quittung und deren Positionen."""
    verleih = db.get(SaisonVerleih, verleih_id)
    if verleih is None:
        return None
    heute = date.today()
    if mit_quittung and verleih.QuittungID and (quittung := db.get(Quittung, verleih.QuittungID)):
        quittung_bezahlt_setzen(db, quittung, bezahlt, heute)
    _verleih_setzen(verleih, bezahlt, heute)
    db.commit()
    logger.info("Verleih %s von Hand auf %s gesetzt", verleih_id, "bezahlt" if bezahlt else "nicht bezahlt")
    return verleih
