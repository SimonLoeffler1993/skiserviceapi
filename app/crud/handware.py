from sqlalchemy.orm import Session

from app.models.handware import Handware
from app.schemas.handware import HandwareCreate, HandwareUpdate


def _bereinigt(werte: dict) -> dict:
    """Leere Texte als NULL speichern, Name ohne Leerzeichen am Rand."""
    for feld in ("Name", "Beschreibung", "Kategorie"):
        if feld in werte and isinstance(werte[feld], str):
            werte[feld] = werte[feld].strip() or None
    return werte


def get_handware_liste(db: Session) -> list[Handware]:
    return db.query(Handware).order_by(Handware.Kategorie, Handware.Name).all()


def get_handware(db: Session, handware_id: int) -> Handware | None:
    return db.get(Handware, handware_id)


def lege_handware_an(db: Session, daten: HandwareCreate) -> Handware:
    handware = Handware(**_bereinigt(daten.model_dump()))
    db.add(handware)
    db.commit()
    db.refresh(handware)
    return handware


def aendere_handware(db: Session, handware_id: int, daten: HandwareUpdate) -> Handware | None:
    handware = get_handware(db, handware_id)
    if handware is None:
        return None
    werte = _bereinigt(daten.model_dump(exclude_unset=True))
    # Name und Preis sind Pflicht und können nicht geleert werden
    for feld in ("Name", "Preis"):
        if feld in werte and werte[feld] is None:
            del werte[feld]
    for feld, wert in werte.items():
        setattr(handware, feld, wert)
    db.commit()
    db.refresh(handware)
    return handware


def loesche_handware(db: Session, handware_id: int) -> bool:
    """Auch nach Verkäufen möglich, die Quittung hat eine Kopie von Name, Preis und Menge."""
    handware = get_handware(db, handware_id)
    if handware is None:
        return False
    db.delete(handware)
    db.commit()
    return True
