"""
Bezahlt-Status von Quittung, Skiservice-Auftrag und Saisonverleih gemeinsam ändern:
von Hand in der Detailansicht oder beim Abgleich mit Lexware.
"""
import logging
from datetime import date, datetime

from sqlalchemy.orm import Session
from app.core.zugriff import aktueller_benutzer_id
from app.services import ereignisse

from app.crud import quittung as crud_quittung
from app.models.handware import Handware
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
    # Eine stornierte Quittung bleibt storniert, auch wenn der Beleg in Lexware bezahlt ist
    if quittung.Storniert or not lexware_bezahlt(lex_daten):
        return False
    datum = lexware_bezahlt_am(lex_daten) or date.today()
    if not quittung_bezahlt_setzen(db, quittung, True, datum):
        return False
    db.commit()
    db.refresh(quittung)
    logger.info("Quittung %s laut Lexware bezahlt, Status in der Datenbank angepasst", quittung.ID)
    return True


def quittung_stornieren(db: Session, quittung: Quittung) -> None:
    """
    Storniert die Quittung, ohne Commit: alle Aufträge und Verleihe darauf werden nicht bezahlt und von ihr gelöst
    (sie erscheinen wieder in der Kasse), verkaufte Handware geht zurück auf den Bestand.
    Die Artikel der Quittung bleiben stehen, damit sichtbar bleibt, was storniert wurde.
    Lexware wird nicht angefasst: ein Beleg dort wird von Hand storniert.
    """
    betroffen = 0
    for auftrag in db.query(Auftrag).filter(Auftrag.quittung_id == quittung.ID):
        # Je Auftrag bzw. Verleih ein Ereignis, damit das Storno auch in deren Verlauf steht
        ereignisse.erfasse(db, "quittung_storniert", quittung_id=quittung.ID, auftrag_id=auftrag.id,
                           kunde_id=auftrag.kunden_id, text=quittung.Nummer)
        betroffen += 1
        _auftrag_setzen(auftrag, False, None)
        auftrag.quittung_id = None
    for verleih in db.query(SaisonVerleih).filter(SaisonVerleih.QuittungID == quittung.ID):
        ereignisse.erfasse(db, "quittung_storniert", quittung_id=quittung.ID, verleih_id=verleih.ID,
                           kunde_id=verleih.Kunde_ID, text=quittung.Nummer)
        betroffen += 1
        _verleih_setzen(verleih, False, None)
        verleih.QuittungID = None
    if not betroffen:
        ereignisse.erfasse(db, "quittung_storniert", quittung_id=quittung.ID, text=quittung.Nummer)
    # Gegenstück zum Verkauf an der Kasse: Anzahl nur zur Orientierung, ohne Bestand bleibt sie leer
    for position in quittung.artikels:
        if position.Artikel_Kategorie != "Handware":
            continue
        handware = db.query(Handware).filter(Handware.ID == position.Artikel_ID).with_for_update().first()
        if handware is not None and handware.Anzahl is not None:
            handware.Anzahl += position.Menge or 0
    quittung.Storniert = True
    quittung.Storniert_Am = date.today()
    quittung.Storniert_Von = aktueller_benutzer_id()
    quittung.Bezahlt = False
    quittung.Bezahlt_Am = None
    logger.info("Quittung %s storniert", quittung.ID)


def aus_quittung_entfernen(
        db: Session, quittung: Quittung, auftrag: Auftrag | None = None, verleih: SaisonVerleih | None = None,
    ) -> None:
    """
    Nimmt genau einen Auftrag oder Verleih von der Quittung, ohne Commit. Die übrigen Positionen bleiben bezahlt.
    War es die letzte Position, wird die Quittung storniert (ein von Hand zugewiesener Lexware-Beleg gelöscht).
    """
    manuell = quittung.ManuellZugewiesen
    ereignisse.erfasse(db, "aus_quittung_entfernt", quittung_id=quittung.ID,
                       auftrag_id=auftrag.id if auftrag is not None else None,
                       verleih_id=verleih.ID if verleih is not None else None,
                       kunde_id=(auftrag.kunden_id if auftrag is not None else verleih.Kunde_ID if verleih is not None else None),
                       text=quittung.Nummer)
    if auftrag is not None:
        auftrag.quittung_id = None
    if verleih is not None:
        verleih.QuittungID = None
    db.flush()
    if quittung.Storniert:
        return
    if manuell:
        # Wie beim Aufheben der Zuweisung: nur löschen, wenn nichts anderes mehr auf die Quittung zeigt
        if not crud_quittung.quittung_verwendet(db, quittung.ID):
            db.delete(quittung)
        return

    eigene = [
        p for p in quittung.artikels
        if (auftrag is not None and p.Auftrag_ID == auftrag.id) or (verleih is not None and p.Verleih_ID == verleih.ID)
    ]
    if len(eigene) == len(quittung.artikels) and not crud_quittung.quittung_verwendet(db, quittung.ID):
        # Letzte Position: ihre Zeile bleibt als Nachweis auf der stornierten Quittung
        quittung_stornieren(db, quittung)
        return
    for position in eigene:
        quittung.artikels.remove(position)
    if auftrag is not None:
        quittung.AnzAuftrag = max((quittung.AnzAuftrag or 0) - 1, 0)
    if verleih is not None:
        quittung.AnzVerleih = max((quittung.AnzVerleih or 0) - 1, 0)


def auftrag_bezahlt_setzen(
        db: Session, auftrag_id: int, bezahlt: bool, mit_quittung: bool, quittung_entfernen: bool = False,
    ) -> Auftrag | None:
    """
    Setzt einen Auftrag von Hand auf (nicht) bezahlt, auf Wunsch mit seiner Quittung und deren Positionen.
    Mit quittung_entfernen wird er bei "nicht bezahlt" stattdessen allein von der Quittung genommen.
    """
    auftrag = db.get(Auftrag, auftrag_id)
    if auftrag is None:
        return None
    heute = date.today()
    quittung = db.get(Quittung, auftrag.quittung_id) if auftrag.quittung_id else None
    if quittung_entfernen and not bezahlt:
        _auftrag_setzen(auftrag, False, heute)
        if quittung is not None:
            aus_quittung_entfernen(db, quittung, auftrag=auftrag)
        else:
            auftrag.quittung_id = None
    else:
        if mit_quittung and quittung is not None:
            quittung_bezahlt_setzen(db, quittung, bezahlt, heute)
        if _auftrag_setzen(auftrag, bezahlt, heute):
            ereignisse.erfasse(db, "bezahlt" if bezahlt else "unbezahlt", auftrag_id=auftrag.id,
                               kunde_id=auftrag.kunden_id, quittung_id=auftrag.quittung_id,
                               text="von Hand" + (" mit Quittung" if mit_quittung and quittung is not None else ""))
    db.commit()
    logger.info("Auftrag %s von Hand auf %s gesetzt", auftrag_id, "bezahlt" if bezahlt else "nicht bezahlt")
    return auftrag


def verleih_bezahlt_setzen(
        db: Session, verleih_id: int, bezahlt: bool, mit_quittung: bool, quittung_entfernen: bool = False,
    ) -> SaisonVerleih | None:
    """
    Setzt einen Verleih von Hand auf (nicht) bezahlt, auf Wunsch mit seiner Quittung und deren Positionen.
    Mit quittung_entfernen wird er bei "nicht bezahlt" stattdessen allein von der Quittung genommen.
    """
    verleih = db.get(SaisonVerleih, verleih_id)
    if verleih is None:
        return None
    heute = date.today()
    quittung = db.get(Quittung, verleih.QuittungID) if verleih.QuittungID else None
    if quittung_entfernen and not bezahlt:
        _verleih_setzen(verleih, False, heute)
        if quittung is not None:
            aus_quittung_entfernen(db, quittung, verleih=verleih)
        else:
            verleih.QuittungID = None
    else:
        if mit_quittung and quittung is not None:
            quittung_bezahlt_setzen(db, quittung, bezahlt, heute)
        if _verleih_setzen(verleih, bezahlt, heute):
            ereignisse.erfasse(db, "bezahlt" if bezahlt else "unbezahlt", verleih_id=verleih.ID,
                               kunde_id=verleih.Kunde_ID, quittung_id=verleih.QuittungID,
                               text="von Hand" + (" mit Quittung" if mit_quittung and quittung is not None else ""))
    db.commit()
    logger.info("Verleih %s von Hand auf %s gesetzt", verleih_id, "bezahlt" if bezahlt else "nicht bezahlt")
    return verleih
