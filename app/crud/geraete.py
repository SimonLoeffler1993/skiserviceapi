"""Geräteschlüssel (Scanner, Kundenterminal) und angemeldete Geräte für Admins."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import sicherheit
from app.models.benutzer import Bedienersitzung, Benutzer, Geraeteschluessel, Geraetesitzung
from app.schemas.benutzer import GeraeteschluesselAendern, GeraeteschluesselAnlegen, GeraetesitzungAendern
from app.services import ereignisse


def schluessel_read(eintrag: Geraeteschluessel) -> dict:
    return {
        "id": eintrag.ID,
        "name": eintrag.Name,
        "bereich": eintrag.Bereich,
        "praefix": eintrag.Praefix,
        "aktiv": bool(eintrag.Aktiv),
        "erstellt_am": eintrag.Erstellt_Am,
        "zuletzt_benutzt": eintrag.Zuletzt_Benutzt,
    }


def schluessel_liste(db: Session) -> list[Geraeteschluessel]:
    return db.query(Geraeteschluessel).order_by(Geraeteschluessel.Bereich, Geraeteschluessel.Name).all()


def _schluessel(db: Session, schluessel_id: int) -> Geraeteschluessel:
    eintrag = db.get(Geraeteschluessel, schluessel_id)
    if eintrag is None:
        raise LookupError("Geräteschlüssel nicht gefunden")
    return eintrag


def _name_frei(db: Session, name: str, ausser_id: int | None = None) -> None:
    abfrage = db.query(Geraeteschluessel.ID).filter(Geraeteschluessel.Name == name)
    if ausser_id is not None:
        abfrage = abfrage.filter(Geraeteschluessel.ID != ausser_id)
    if abfrage.first():
        raise ValueError(f"Es gibt schon einen Geräteschlüssel „{name}“.")


def schluessel_anlegen(db: Session, daten: GeraeteschluesselAnlegen, erstellt_von: int | None) -> dict:
    """Gibt den Schlüssel einmalig im Klartext zurück; gespeichert wird nur sein Hash."""
    name = daten.name.strip()
    _name_frei(db, name)
    schluessel = sicherheit.token_erzeugen(sicherheit.PRAEFIX_SCHLUESSEL)
    eintrag = Geraeteschluessel(
        Name=name,
        Bereich=daten.bereich,
        Schluessel_Hash=sicherheit.token_hash(schluessel),
        Praefix=schluessel[:7],
        Aktiv=True,
        Erstellt_Am=datetime.now(),
        Erstellt_Von=erstellt_von,
    )
    db.add(eintrag)
    db.flush()
    ereignisse.erfasse(db, "geraeteschluessel_erzeugt", text=f"{name} ({daten.bereich})")
    db.commit()
    return {**schluessel_read(eintrag), "schluessel": schluessel}


def schluessel_aendern(db: Session, schluessel_id: int, daten: GeraeteschluesselAendern) -> Geraeteschluessel:
    eintrag = _schluessel(db, schluessel_id)
    if daten.name:
        _name_frei(db, daten.name.strip(), eintrag.ID)
        eintrag.Name = daten.name.strip()
    if daten.aktiv is not None:
        eintrag.Aktiv = daten.aktiv
        ereignisse.erfasse(db, "geraeteschluessel_geaendert",
                           text=f"{eintrag.Name}: {'aktiviert' if daten.aktiv else 'gesperrt'}")
    db.commit()
    return eintrag


def schluessel_loeschen(db: Session, schluessel_id: int) -> None:
    eintrag = _schluessel(db, schluessel_id)
    ereignisse.erfasse(db, "geraeteschluessel_geloescht", text=eintrag.Name)
    db.delete(eintrag)
    db.commit()


def sitzungen(db: Session) -> list[dict]:
    geraete = db.query(Geraetesitzung).order_by(Geraetesitzung.Zuletzt_Gesehen.desc()).all()
    namen = {b.ID: b.Anzeigename for b in db.query(Benutzer.ID, Benutzer.Anzeigename).all()}
    bediener = {s.Geraetesitzung_ID: namen.get(s.Benutzer_ID)
                for s in db.query(Bedienersitzung.Geraetesitzung_ID, Bedienersitzung.Benutzer_ID).all()}
    return [{
        "id": g.ID,
        "name": g.Name,
        "art": g.Art,
        "angemeldet_von": namen.get(g.Angemeldet_Von),
        "bediener": bediener.get(g.ID),
        "erstellt_am": g.Erstellt_Am,
        "zuletzt_gesehen": g.Zuletzt_Gesehen,
        "laeuft_ab": g.Laeuft_Ab,
        "bediener_timeout_minuten": g.Bediener_Timeout_Minuten,
        "dauerhaft": bool(g.Dauerhaft),
    } for g in geraete]


def _sitzung(db: Session, sitzung_id: int) -> Geraetesitzung:
    geraet = db.get(Geraetesitzung, sitzung_id)
    if geraet is None:
        raise LookupError("Gerät nicht gefunden")
    return geraet


def sitzung_aendern(db: Session, sitzung_id: int, daten: GeraetesitzungAendern) -> None:
    geraet = _sitzung(db, sitzung_id)
    if daten.name:
        geraet.Name = daten.name.strip()
    if "bediener_timeout_minuten" in daten.model_fields_set:
        geraet.Bediener_Timeout_Minuten = daten.bediener_timeout_minuten
    db.commit()


def sitzung_abmelden(db: Session, sitzung_id: int) -> None:
    geraet = _sitzung(db, sitzung_id)
    db.query(Bedienersitzung).filter(Bedienersitzung.Geraetesitzung_ID == geraet.ID).delete()
    ereignisse.erfasse(db, "geraet_abgemeldet", text=f"{geraet.Name} (durch Admin)")
    db.delete(geraet)
    db.commit()
