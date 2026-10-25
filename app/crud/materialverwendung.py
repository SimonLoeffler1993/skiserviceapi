"""
Gemeinsame Logik für Ski, Schuh und Stock: Verwendung in Verleihen, Ausmustern, Löschen
und eindeutige Nummern. So verhalten sich alle drei Materialarten gleich.
"""
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial


class MaterialKonflikt(Exception):
    """Aktion ist wegen bestehender Daten nicht möglich (HTTP 409)."""


class MaterialUngueltig(Exception):
    """Ungültige Eingabe (HTTP 400)."""


def verwendung(db: Session, bedingung) -> list[dict]:
    """
    Verleihe, in denen das Material steckt, neueste zuerst.
    bedingung: Filter auf SaisonVerleihMaterial, z.B. SaisonVerleihMaterial.schuhnr == 5
    """
    eintraege = (
        db.query(SaisonVerleihMaterial)
        .filter(bedingung)
        .options(joinedload(SaisonVerleihMaterial.saisonverleih).joinedload(SaisonVerleih.Kunde))
        .all()
    )
    # Ein Eintrag pro Verleih, auch wenn das Material mehrfach darin steckt
    # (z.B. derselbe Stocktyp für zwei Kinder). Die Fahrer werden zusammengefasst.
    ergebnis: dict[int, dict] = {}
    for material in eintraege:
        verleih = material.saisonverleih
        if verleih is None:
            continue
        eintrag = ergebnis.get(verleih.ID)
        if eintrag is None:
            kunde = verleih.Kunde
            eintrag = ergebnis[verleih.ID] = {
                "ID": verleih.ID,
                "Name": verleih.Name,
                "Art": verleih.Art,
                "Start_Am": verleih.Start_Am,
                "Ende_Am": verleih.Ende_Am,
                "Kunde": " ".join(t for t in ((kunde.Vorname if kunde else None), (kunde.Nachname if kunde else None)) if t) or "Unbekannt",
                "Fahrer": [],
                "Zurueck": bool(verleih.Zurueck),
                "Status": verleih.Status,
            }
        fahrer = (material.SkiFahrerName or "").strip()
        if fahrer and fahrer not in eintrag["Fahrer"]:
            eintrag["Fahrer"].append(fahrer)
    for eintrag in ergebnis.values():
        eintrag["Fahrer"] = ", ".join(eintrag["Fahrer"]) or None
    return sorted(ergebnis.values(), key=lambda e: e["ID"], reverse=True)


def anzahl_verleihe(db: Session, bedingung) -> int:
    return (
        db.query(func.count(func.distinct(SaisonVerleihMaterial.SaisonVerlei_ID)))
        .filter(bedingung)
        .scalar()
    ) or 0


def setze_ausgemustert(db: Session, objekt: Any, ausgemustert: bool):
    """Ausmustern oder wiederherstellen, geht immer."""
    objekt.Ausgemustert = ausgemustert
    db.commit()
    db.refresh(objekt)
    return objekt


def loesche(db: Session, objekt: Any, bedingung, bezeichnung: str):
    """Endgültig löschen, nur wenn das Material in keinem Verleih steckt."""
    anzahl = anzahl_verleihe(db, bedingung)
    if anzahl:
        raise MaterialKonflikt(
            f"{bezeichnung} steckt in {anzahl} {'Verleih' if anzahl == 1 else 'Verleihen'} und kann nicht gelöscht werden. Bitte ausmustern."
        )
    db.delete(objekt)
    db.commit()


def setze_im_verleih(objekte: list, benutzte: set, schluessel) -> list:
    """Hängt an jedes Objekt das Attribut ImVerleih für die Antwort an."""
    for objekt in objekte:
        objekt.ImVerleih = schluessel(objekt) in benutzte
    return objekte


def pruefe_nummer(db: Session, model, spalte, nummer: str | None, eigene_id: int | None, beschreibung) -> str:
    """
    Prüft eine Ski- bzw. Schuh-Nr. auf Eindeutigkeit.
    Leerzeichen am Rand werden entfernt, Groß-/Kleinschreibung zählt nicht.
    beschreibung(objekt) liefert den Text für die Fehlermeldung.
    """
    nummer = (nummer or "").strip()
    if not nummer:
        raise MaterialUngueltig("Die Nummer darf nicht leer sein.")
    query = db.query(model).filter(func.lower(spalte) == nummer.lower())
    if eigene_id is not None:
        query = query.filter(model.ID != eigene_id)
    vorhanden = query.first()
    if vorhanden is not None:
        raise MaterialKonflikt(f"Nummer {nummer} ist bereits vergeben ({beschreibung(vorhanden)}).")
    return nummer
