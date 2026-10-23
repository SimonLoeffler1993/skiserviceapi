from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import materialverwendung as verwendung
from app.crud.materialverwendung import MaterialKonflikt, MaterialUngueltig
from app.models.materialschuh import EigenSchuh, VerleihSchuhHersteller, VerleihSchuhModell
from app.models.saisonverleih import SaisonVerleihMaterial
from app.schemas.materialschuh import (
    VerleihSchuhHerstellerBase, VerleihSchuhModellBase, EigenSchuhBase,
    EigenSchuhUpdate, VerleihSchuhHerstellerUpdate, VerleihSchuhModellUpdate,
)


def schuh_text(schuh: EigenSchuh) -> str:
    """Kurzbeschreibung für Meldungen, z.B. "Atomic Hawx Prime 100, Größe 27.5"."""
    modell = schuh.Modell
    teile = [t for t in ((modell.Hersteller.Name if modell and modell.Hersteller else None), (modell.Modell if modell else None)) if t]
    return f"{' '.join(teile) or 'Schuh'}, Größe {schuh.Groese}"


def _benutzte_schuhe(db: Session) -> set:
    return {nr for (nr,) in db.query(SaisonVerleihMaterial.schuhnr).filter(SaisonVerleihMaterial.schuhnr.isnot(None)).distinct()}


def get_eigen_schuhe(db: Session, eigen_schuh_nr: str):
    """Schuh anhand der Schuh-Nr., Groß-/Kleinschreibung zählt nicht."""
    nummer = (eigen_schuh_nr or "").strip()
    if not nummer:
        return None
    return db.query(EigenSchuh).filter(func.lower(EigenSchuh.SchuhNr) == nummer.lower()).first()


def get_eigen_schuh_by_id(db: Session, schuh_id: int):
    return db.get(EigenSchuh, schuh_id)


def get_eigen_schuhe_liste(db: Session, mit_ausgemustert: bool = True):
    query = db.query(EigenSchuh)
    if not mit_ausgemustert:
        query = query.filter(EigenSchuh.Ausgemustert == False)  # noqa: E712
    schuhe = query.order_by(EigenSchuh.ID).all()
    return verwendung.setze_im_verleih(schuhe, _benutzte_schuhe(db), lambda schuh: schuh.ID)


def _standard_nummer(db: Session, schuh: EigenSchuh) -> str:
    """Die ID als Nummer. Hat jemand diese Zahl schon selbst vergeben, wird S{ID} genommen."""
    for kandidat in (str(schuh.ID), f"S{schuh.ID}"):
        vorhanden = (
            db.query(EigenSchuh)
            .filter(func.lower(EigenSchuh.SchuhNr) == kandidat.lower(), EigenSchuh.ID != schuh.ID)
            .first()
        )
        if vorhanden is None:
            return kandidat
    return f"S{schuh.ID}-{schuh.ID}"


def create_eigen_schuhe(db: Session, schuh: EigenSchuhBase):
    daten = schuh.model_dump()
    eigene_nummer = (daten.pop("SchuhNr") or "").strip()
    if eigene_nummer:
        eigene_nummer = verwendung.pruefe_nummer(db, EigenSchuh, EigenSchuh.SchuhNr, eigene_nummer, None, schuh_text)

    # Vorläufige Nummer, die ID gibt es erst nach dem Flush
    db_schuh = EigenSchuh(**daten, SchuhNr=eigene_nummer or "__neu__")
    db.add(db_schuh)
    try:
        db.flush()
        if not eigene_nummer:
            db_schuh.SchuhNr = _standard_nummer(db, db_schuh)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MaterialKonflikt(f"Schuh-Nr. {eigene_nummer} ist bereits vergeben.")
    db.refresh(db_schuh)
    return db_schuh


def aendere_eigen_schuh(db: Session, schuh_id: int, daten: EigenSchuhUpdate):
    """Ändert einen Schuh. Verleihe verweisen auf die ID, eine neue Nummer ändert dort nichts."""
    schuh = db.get(EigenSchuh, schuh_id)
    if schuh is None:
        return None
    aenderungen = daten.model_dump(exclude_unset=True)

    if "SchuhNr" in aenderungen:
        nummer = (aenderungen.pop("SchuhNr") or "").strip()
        schuh.SchuhNr = (
            verwendung.pruefe_nummer(db, EigenSchuh, EigenSchuh.SchuhNr, nummer, schuh.ID, schuh_text)
            if nummer else _standard_nummer(db, schuh)
        )

    for feld, wert in aenderungen.items():
        # Nur die Sohlenlänge darf leer sein
        if wert is None and feld != "Sohle":
            raise MaterialUngueltig(f"{feld} darf nicht leer sein.")
        setattr(schuh, feld, wert)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MaterialKonflikt("Die Schuh-Nr. ist bereits vergeben.")
    db.refresh(schuh)
    schuh.ImVerleih = schuh.ID in _benutzte_schuhe(db)
    return schuh


def verwendung_eigen_schuh(db: Session, schuh: EigenSchuh) -> list[dict]:
    return verwendung.verwendung(db, SaisonVerleihMaterial.schuhnr == schuh.ID)


def loesche_eigen_schuh(db: Session, schuh: EigenSchuh):
    verwendung.loesche(db, schuh, SaisonVerleihMaterial.schuhnr == schuh.ID, f"Schuh {schuh.SchuhNr}")


# --- Hersteller ---

def create_hersteller(db: Session, schuh: VerleihSchuhHerstellerBase):
    db_schuh = VerleihSchuhHersteller(**schuh.model_dump())
    db.add(db_schuh)
    db.commit()
    db.refresh(db_schuh)
    return db_schuh

def get_hersteller(db: Session):
    return db.query(VerleihSchuhHersteller).order_by(VerleihSchuhHersteller.Name).all()

def aendere_hersteller(db: Session, hersteller_id: int, daten: VerleihSchuhHerstellerUpdate):
    hersteller = db.get(VerleihSchuhHersteller, hersteller_id)
    if hersteller is None:
        return None
    if daten.Name is not None:
        if not daten.Name.strip():
            raise MaterialUngueltig("Der Name darf nicht leer sein.")
        hersteller.Name = daten.Name.strip()
    db.commit()
    db.refresh(hersteller)
    return hersteller

def verwendung_hersteller(db: Session, hersteller_id: int) -> dict:
    modelle = db.query(VerleihSchuhModell).filter(VerleihSchuhModell.Hersteller_ID == hersteller_id).order_by(VerleihSchuhModell.Modell).all()
    return {"Anzahl": len(modelle), "Beispiele": [m.Modell or "?" for m in modelle[:5]]}

def loesche_hersteller(db: Session, hersteller: VerleihSchuhHersteller):
    benutzt = verwendung_hersteller(db, hersteller.ID)
    if benutzt["Anzahl"]:
        raise MaterialKonflikt(f"Wird noch von {benutzt['Anzahl']} {'Modell' if benutzt['Anzahl'] == 1 else 'Modellen'} verwendet und kann nicht gelöscht werden.")
    db.delete(hersteller)
    db.commit()


# --- Modelle ---

def create_modell(db: Session, modell: VerleihSchuhModellBase):
    db_modell = VerleihSchuhModell(**modell.model_dump())
    db.add(db_modell)
    db.commit()
    db.refresh(db_modell)
    return db_modell

def get_modelle(db: Session):
    return db.query(VerleihSchuhModell).all()

def aendere_modell(db: Session, modell_id: int, daten: VerleihSchuhModellUpdate):
    modell = db.get(VerleihSchuhModell, modell_id)
    if modell is None:
        return None
    for feld, wert in daten.model_dump(exclude_unset=True).items():
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            raise MaterialUngueltig(f"{feld} darf nicht leer sein.")
        setattr(modell, feld, wert.strip() if isinstance(wert, str) else wert)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MaterialUngueltig("Der Hersteller existiert nicht.")
    db.refresh(modell)
    return modell

def verwendung_modell(db: Session, modell_id: int) -> dict:
    schuhe = db.query(EigenSchuh).filter(EigenSchuh.Modell_ID == modell_id).order_by(EigenSchuh.ID).all()
    return {"Anzahl": len(schuhe), "Beispiele": [s.SchuhNr for s in schuhe[:5]]}

def loesche_modell(db: Session, modell: VerleihSchuhModell):
    benutzt = verwendung_modell(db, modell.ID)
    if benutzt["Anzahl"]:
        raise MaterialKonflikt(f"Wird noch von {benutzt['Anzahl']} {'Schuh' if benutzt['Anzahl'] == 1 else 'Schuhen'} verwendet und kann nicht gelöscht werden.")
    db.delete(modell)
    db.commit()
