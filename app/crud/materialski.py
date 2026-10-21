from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import materialverwendung as verwendung
from app.crud.materialverwendung import MaterialKonflikt, MaterialUngueltig
from app.models.materialski import EigenSki, VerleihSkiHersteller, SkiArt, VerleihSkiModell
from app.models.saisonverleih import SaisonVerleihMaterial, SkiSaisonverleihPreise
from app.schemas.materialski import EigenSkiUpdate, SkiArtUpdate, VerleihSkiHerstellerUpdate, VerleihSkiModellUpdate


def ski_text(ski: EigenSki) -> str:
    """Kurzbeschreibung für Meldungen, z.B. "Atomic Redster S9, 165 cm"."""
    modell = ski.Modell
    teile = [t for t in ((modell.Hersteller.Name if modell and modell.Hersteller else None), (modell.Modell if modell else None)) if t]
    return f"{' '.join(teile) or 'Ski'}, {ski.Laenge} cm" if ski.Laenge else (" ".join(teile) or "Ski")


def _benutzte_skinr(db: Session) -> set:
    return {nr for (nr,) in db.query(SaisonVerleihMaterial.skinr).filter(SaisonVerleihMaterial.skinr.isnot(None)).distinct()}


def get_eigen_ski(db: Session, eigen_ski_nr: str, mit_ausgemustert: bool = True):
    """Ski, deren Nummer mit eigen_ski_nr beginnt. Mit leerem Text alle."""
    query = db.query(EigenSki).filter(EigenSki.SkiNr.startswith(eigen_ski_nr))
    if not mit_ausgemustert:
        query = query.filter(EigenSki.Ausgemustert == False)  # noqa: E712
    skis = query.order_by(EigenSki.SkiNr).all()
    return verwendung.setze_im_verleih(skis, _benutzte_skinr(db), lambda ski: ski.SkiNr)


def get_eigen_ski_by_id(db: Session, ski_id: int):
    return db.get(EigenSki, ski_id)


def create_eigen_ski(db: Session, ski):
    skinr = verwendung.pruefe_nummer(db, EigenSki, EigenSki.SkiNr, ski.SkiNr, None, ski_text)
    db_ski = EigenSki(
        SkiNr=skinr,
        Modell_ID=ski.Modell_ID,
        VK=ski.VK,
        EK=ski.EK,
        Laenge=ski.Laenge,
        Saison=ski.Saison
    )
    db.add(db_ski)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MaterialKonflikt(f"Ski-Nr. {skinr} ist bereits vergeben.")
    db.refresh(db_ski)
    return db_ski


def aendere_eigen_ski(db: Session, ski_id: int, daten: EigenSkiUpdate):
    """
    Ändert einen Ski. Eine neue Ski-Nr. muss eindeutig sein.
    Bestehende Verleihe ziehen über den Fremdschlüssel (ON UPDATE CASCADE) automatisch mit.
    Gibt den Ski und die Anzahl umgestellter Verleihe zurück.
    """
    ski = db.get(EigenSki, ski_id)
    if ski is None:
        return None, 0
    aenderungen = daten.model_dump(exclude_unset=True)
    umgestellt = 0

    if "SkiNr" in aenderungen:
        neue_nr = verwendung.pruefe_nummer(db, EigenSki, EigenSki.SkiNr, aenderungen.pop("SkiNr"), ski.ID, ski_text)
        if neue_nr != ski.SkiNr:
            umgestellt = verwendung.anzahl_verleihe(db, SaisonVerleihMaterial.skinr == ski.SkiNr)
            ski.SkiNr = neue_nr

    for feld, wert in aenderungen.items():
        if wert is None:
            raise MaterialUngueltig(f"{feld} darf nicht leer sein.")
        setattr(ski, feld, wert)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise MaterialKonflikt("Die Ski-Nr. ist bereits vergeben.")
    db.refresh(ski)
    ski.ImVerleih = ski.SkiNr in _benutzte_skinr(db)
    return ski, umgestellt


def verwendung_eigen_ski(db: Session, ski: EigenSki) -> list[dict]:
    return verwendung.verwendung(db, SaisonVerleihMaterial.skinr == ski.SkiNr)


def loesche_eigen_ski(db: Session, ski: EigenSki):
    verwendung.loesche(db, ski, SaisonVerleihMaterial.skinr == ski.SkiNr, f"Ski {ski.SkiNr}")


# --- Hersteller ---

def get_hersteller(db: Session):
    return db.query(VerleihSkiHersteller).order_by(VerleihSkiHersteller.Name).all()

def create_hersteller(db: Session, hersteller: str):
    db_hersteller = VerleihSkiHersteller(Name=hersteller)
    db.add(db_hersteller)
    db.commit()
    db.refresh(db_hersteller)
    return db_hersteller

def aendere_hersteller(db: Session, hersteller_id: int, daten: VerleihSkiHerstellerUpdate):
    hersteller = db.get(VerleihSkiHersteller, hersteller_id)
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
    modelle = db.query(VerleihSkiModell).filter(VerleihSkiModell.Hersteller_ID == hersteller_id).order_by(VerleihSkiModell.Modell).all()
    return {"Anzahl": len(modelle), "Beispiele": [m.Modell or "?" for m in modelle[:5]]}

def loesche_hersteller(db: Session, hersteller: VerleihSkiHersteller):
    benutzt = verwendung_hersteller(db, hersteller.ID)
    if benutzt["Anzahl"]:
        raise MaterialKonflikt(f"Wird noch von {benutzt['Anzahl']} {'Modell' if benutzt['Anzahl'] == 1 else 'Modellen'} verwendet und kann nicht gelöscht werden.")
    db.delete(hersteller)
    db.commit()


# --- Skiart ---

def get_skiart(db: Session):
    return db.query(SkiArt).order_by(SkiArt.Art).all()

def _pruefe_skiart_name(db: Session, name: str | None, eigene_id: int | None) -> str:
    """Name darf nicht leer und nicht doppelt sein (ohne Groß-/Kleinschreibung)."""
    name = (name or "").strip()
    if not name:
        raise MaterialUngueltig("Die Bezeichnung darf nicht leer sein.")
    query = db.query(SkiArt).filter(func.lower(SkiArt.Art) == name.lower())
    if eigene_id is not None:
        query = query.filter(SkiArt.ID != eigene_id)
    if query.first() is not None:
        raise MaterialKonflikt(f"Die Skiart {name} gibt es bereits.")
    return name

def create_skiart(db: Session, art: str):
    db_art = SkiArt(Art=_pruefe_skiart_name(db, art, None))
    db.add(db_art)
    db.commit()
    db.refresh(db_art)
    return db_art

def aendere_skiart(db: Session, art_id: int, daten: SkiArtUpdate):
    art = db.get(SkiArt, art_id)
    if art is None:
        return None
    if daten.Art is not None:
        art.Art = _pruefe_skiart_name(db, daten.Art, art.ID)
    db.commit()
    db.refresh(art)
    return art

def verwendung_skiart(db: Session, art_id: int) -> dict:
    """Modelle und Saisonverleih-Preise (ohne Fremdschlüssel), die auf die Skiart verweisen."""
    modelle = db.query(VerleihSkiModell).filter(VerleihSkiModell.Art_ID == art_id).order_by(VerleihSkiModell.Modell).all()
    preise = db.query(SkiSaisonverleihPreise).filter(SkiSaisonverleihPreise.SkiArt_ID == art_id).all()
    beispiele = [m.Modell or "?" for m in modelle] + [f"Preis {p.Bezeichnung}" for p in preise]
    return {"Anzahl": len(modelle) + len(preise), "Beispiele": beispiele[:5]}

def loesche_skiart(db: Session, art: SkiArt):
    modelle = db.query(VerleihSkiModell).filter(VerleihSkiModell.Art_ID == art.ID).count()
    preise = db.query(SkiSaisonverleihPreise).filter(SkiSaisonverleihPreise.SkiArt_ID == art.ID).count()
    if modelle or preise:
        teile = []
        if modelle:
            teile.append(f"{modelle} {'Modell' if modelle == 1 else 'Modellen'}")
        if preise:
            teile.append(f"{preise} {'Saisonverleih-Preis' if preise == 1 else 'Saisonverleih-Preisen'}")
        raise MaterialKonflikt(f"Wird noch von {' und '.join(teile)} verwendet und kann nicht gelöscht werden.")
    db.delete(art)
    db.commit()


# --- Modelle ---

def create_ski_modell(db: Session, modell):
    db_modell = VerleihSkiModell(
        Modell=modell.Modell,
        Art_ID=modell.Art_ID,
        Hersteller_ID=modell.Hersteller_ID
    )
    db.add(db_modell)
    db.commit()
    db.refresh(db_modell)
    return db_modell

def get_ski_modell(db: Session):
    return db.query(VerleihSkiModell).all()

def aendere_ski_modell(db: Session, modell_id: int, daten: VerleihSkiModellUpdate):
    modell = db.get(VerleihSkiModell, modell_id)
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
        raise MaterialUngueltig("Hersteller oder Art existiert nicht.")
    db.refresh(modell)
    return modell

def verwendung_ski_modell(db: Session, modell_id: int) -> dict:
    skis = db.query(EigenSki).filter(EigenSki.Modell_ID == modell_id).order_by(EigenSki.SkiNr).all()
    return {"Anzahl": len(skis), "Beispiele": [s.SkiNr or "?" for s in skis[:5]]}

def loesche_ski_modell(db: Session, modell: VerleihSkiModell):
    benutzt = verwendung_ski_modell(db, modell.ID)
    if benutzt["Anzahl"]:
        raise MaterialKonflikt(f"Wird noch von {benutzt['Anzahl']} Ski verwendet und kann nicht gelöscht werden.")
    db.delete(modell)
    db.commit()
