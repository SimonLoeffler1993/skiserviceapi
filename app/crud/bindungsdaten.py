from datetime import date
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.bindungsdaten import Bindungsdaten
from app.models.skiservice import Ski
from app.schemas.bindungsdaten import BindungsdatenBase


def setze_bindungsdaten(db: Session, ski: Ski, kunde_id: int, daten: Optional[BindungsdatenBase], vorlage_id: Optional[int] = None):
    """
    Legt die Bindungsdaten eines Ski an, ändert oder entfernt sie.
    Ohne Bindungscheck oder ohne Werte wird ein vorhandener Datensatz gelöscht.
    Eine übernommene Vorlage desselben Kunden wird archiviert, weil der neue Datensatz sie ersetzt.
    """
    if not ski.bindung_check or daten is None or daten.ist_leer():
        if ski.bindungsdaten is not None:
            db.delete(ski.bindungsdaten)
            ski.bindungsdaten = None
        return

    if ski.bindungsdaten is None:
        ski.bindungsdaten = Bindungsdaten(Kunde_ID=kunde_id, Erfasst_Am=date.today())
    for feld, wert in daten.model_dump().items():
        setattr(ski.bindungsdaten, feld, wert.strip() or None if isinstance(wert, str) else wert)

    if vorlage_id is not None:
        vorlage = db.get(Bindungsdaten, vorlage_id)
        if vorlage is not None and vorlage.Kunde_ID == kunde_id and vorlage is not ski.bindungsdaten:
            vorlage.Archiviert = True


def bindungsdaten_kunde(db: Session, kunde_id: int, mit_archiv: bool = False) -> list[dict]:
    """Alle Bindungsdaten eines Kunden, neueste zuerst, mit Angabe des Auftrags."""
    query = (
        db.query(Bindungsdaten)
        .filter(Bindungsdaten.Kunde_ID == kunde_id)
        .options(joinedload(Bindungsdaten.ski).joinedload(Ski.auftrag))
        .order_by(Bindungsdaten.Erfasst_Am.desc(), Bindungsdaten.ID.desc())
    )
    if not mit_archiv:
        query = query.filter(Bindungsdaten.Archiviert == False)  # noqa: E712

    ergebnis = []
    for eintrag in query.all():
        ski = eintrag.ski
        ergebnis.append({
            **{spalte.name: getattr(eintrag, spalte.name) for spalte in Bindungsdaten.__table__.columns},
            "Auftrag_ID": ski.auftrag_id if ski else None,
            "Auftrag_Name": ski.auftrag.name if ski and ski.auftrag else None,
            "Ski_Name": ski.name if ski else None,
            "Service": ski.service if ski else None,
        })
    return ergebnis


def setze_archiviert(db: Session, bindungsdaten_id: int, archiviert: bool) -> Optional[Bindungsdaten]:
    eintrag = db.get(Bindungsdaten, bindungsdaten_id)
    if eintrag is None:
        return None
    eintrag.Archiviert = archiviert
    db.commit()
    db.refresh(eintrag)
    return eintrag
