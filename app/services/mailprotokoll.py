"""
Protokoll der an Kunden versendeten Mails: was ging an wen, und hat es geklappt.
Geschrieben wird aus app/utils/mail.py bei jedem Sendeversuch.
"""
import logging
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.mailprotokoll import MailProtokoll
from app.models.quittung import Quittung
from app.models.saisonverleih import SaisonVerleih
from app.models.skiservice import Auftrag

logger = logging.getLogger(__name__)

FEHLER_MAX = 500


def fehler_text(fehler: BaseException) -> str:
    """Kurzer Fehlertext für das Protokoll, z.B. "SMTPAuthenticationError: (535, ...)"."""
    return f"{type(fehler).__name__}: {fehler}"[:FEHLER_MAX]


def protokolliere(
    vorlage: str,
    empfaenger: str,
    betreff: str,
    inhalt: str,
    fehler: str | None = None,
    kunde_id: int | None = None,
    auftrag_id: int | None = None,
    verleih_id: int | None = None,
    quittung_id: int | None = None,
) -> None:
    """
    Speichert einen Sendeversuch, fehler=None heißt gesendet.
    Eigene Session: der Eintrag bleibt auch stehen, wenn die Anfrage danach zurückgerollt wird.
    Wirft nie, ein Fehler beim Protokollieren darf den Versand nicht stören.
    """
    try:
        with SessionLocal() as db:
            db.add(MailProtokoll(
                Gesendet_Am=datetime.now().replace(microsecond=0),
                Vorlage=vorlage,
                Empfaenger=(empfaenger or "")[:255],
                Betreff=(betreff or "")[:255],
                Inhalt=inhalt or "",
                Erfolgreich=fehler is None,
                Fehler=fehler[:FEHLER_MAX] if fehler else None,
                Kunde_ID=kunde_id,
                Auftrag_ID=auftrag_id,
                Verleih_ID=verleih_id,
                Quittung_ID=quittung_id,
            ))
            db.commit()
    except Exception:
        logger.exception("Mail an %s konnte nicht protokolliert werden", empfaenger)


def _fuer_anzeige(db: Session, mails: list[MailProtokoll]) -> list[dict]:
    """
    Ergänzt die angezeigte Quittungsnummer und die Bezüge: der Auftrag bzw. Verleih der Mail,
    bei einer Quittungs-Mail alle Aufträge und Verleihe, die auf die Quittung zeigen.
    Geladen wird gesammelt (je eine Abfrage), nicht pro Mail.
    """
    ids = {m.Quittung_ID for m in mails if m.Quittung_ID}
    nummern = {q.ID: q.Nummer for q in db.query(Quittung).filter(Quittung.ID.in_(ids))} if ids else {}

    auftrag_ids = {m.Auftrag_ID for m in mails if m.Auftrag_ID}
    verleih_ids = {m.Verleih_ID for m in mails if m.Verleih_ID}
    auftraege = (
        db.query(Auftrag.id, Auftrag.name, Auftrag.quittung_id)
        .filter(or_(Auftrag.id.in_(auftrag_ids), Auftrag.quittung_id.in_(ids)))
        .order_by(Auftrag.id)
        .all()
    ) if auftrag_ids or ids else []
    verleihe = (
        db.query(SaisonVerleih.ID, SaisonVerleih.Name, SaisonVerleih.QuittungID)
        .filter(or_(SaisonVerleih.ID.in_(verleih_ids), SaisonVerleih.QuittungID.in_(ids)))
        .order_by(SaisonVerleih.ID)
        .all()
    ) if verleih_ids or ids else []

    def bezuege(m: MailProtokoll) -> list[dict]:
        liste = [
            {"art": "auftrag", "id": a.id, "name": a.name}
            for a in auftraege
            if a.id == m.Auftrag_ID or (m.Quittung_ID and a.quittung_id == m.Quittung_ID)
        ]
        liste += [
            {"art": "verleih", "id": v.ID, "name": v.Name}
            for v in verleihe
            if v.ID == m.Verleih_ID or (m.Quittung_ID and v.QuittungID == m.Quittung_ID)
        ]
        return liste

    return [
        {
            "ID": m.ID,
            "Gesendet_Am": m.Gesendet_Am,
            "Vorlage": m.Vorlage,
            "Empfaenger": m.Empfaenger,
            "Betreff": m.Betreff,
            "Inhalt": m.Inhalt,
            "Erfolgreich": m.Erfolgreich,
            "Fehler": m.Fehler,
            "Kunde_ID": m.Kunde_ID,
            "Auftrag_ID": m.Auftrag_ID,
            "Verleih_ID": m.Verleih_ID,
            "Quittung_ID": m.Quittung_ID,
            "Quittung_Nummer": nummern.get(m.Quittung_ID),
            "Bezuege": bezuege(m),
        }
        for m in mails
    ]


def _suche(db: Session, eigene, quittung_ids: set[int]) -> list[dict]:
    """
    Mails, die direkt verknüpft sind, und die Quittungs-Mails der übergebenen Quittungen.
    Quittungs-Mails haben keinen Kunden, sie hängen wie die Quittung selbst am Auftrag bzw. Verleih.
    """
    bedingung = eigene
    if quittung_ids:
        bedingung = or_(eigene, MailProtokoll.Quittung_ID.in_(quittung_ids))
    mails = (
        db.query(MailProtokoll)
        .filter(bedingung)
        .order_by(MailProtokoll.Gesendet_Am.desc(), MailProtokoll.ID.desc())
        .all()
    )
    return _fuer_anzeige(db, mails)


def mails_auftrag(db: Session, auftrag_id: int) -> list[dict]:
    quittung_id = db.query(Auftrag.quittung_id).filter(Auftrag.id == auftrag_id).scalar()
    return _suche(db, MailProtokoll.Auftrag_ID == auftrag_id, {quittung_id} if quittung_id else set())


def mails_verleih(db: Session, verleih_id: int) -> list[dict]:
    quittung_id = db.query(SaisonVerleih.QuittungID).filter(SaisonVerleih.ID == verleih_id).scalar()
    return _suche(db, MailProtokoll.Verleih_ID == verleih_id, {quittung_id} if quittung_id else set())


def mails_kunde(db: Session, kunde_id: int) -> list[dict]:
    auftrag_quittungen = db.query(Auftrag.quittung_id).filter(Auftrag.kunden_id == kunde_id, Auftrag.quittung_id.isnot(None))
    verleih_quittungen = db.query(SaisonVerleih.QuittungID).filter(SaisonVerleih.Kunde_ID == kunde_id, SaisonVerleih.QuittungID.isnot(None))
    quittung_ids = {zeile[0] for zeile in auftrag_quittungen} | {zeile[0] for zeile in verleih_quittungen}
    return _suche(db, MailProtokoll.Kunde_ID == kunde_id, quittung_ids)
