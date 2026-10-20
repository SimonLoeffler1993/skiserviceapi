from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload
import datetime
import logging
from typing import Optional

from app.models.saisonverleih import SkiSaisonverleihPreise, SaisonVerleih, SaisonVerleihMaterial
from app.schemas.saisonverleih import SaisonVerleihCreate, SaisonVerleihPreisBase, SaisonVerleihUpdate, SaisonVerleihMaterialBase, SaisonVerleihMaterialUpdate
from app.crud import saison as crud_saison
from app.utils.skiEttiket import SkiEttiket
from app.services import einstellungen

logger = logging.getLogger(__name__)


def get_saisonverleihpreise(db: Session,):
    # TODO mit Historie
    return db.query(SkiSaisonverleihPreise).all()

def create_saisonverleihpreis(db: Session, preis_data: SaisonVerleihPreisBase):
    new_preis = SkiSaisonverleihPreise(
        Bezeichnung=preis_data.Bezeichnung,
        Preis=preis_data.Preis,
        vonL=preis_data.vonL,
        bisL=preis_data.bisL,
        SkiArt_ID=preis_data.SkiArt_ID,
        inaktiv=0
    )
    db.add(new_preis)
    db.commit()
    db.refresh(new_preis)
    return new_preis

def get_saisonverleih(db: Session, saisonverleih_id: int):
    return db.query(SaisonVerleih).filter(SaisonVerleih.ID == saisonverleih_id).first()

def get_saisonverleih_liste(db: Session, limit: int = 15, last_id: Optional[int] = None, saisonID: Optional[int] = None, alle: Optional[bool] = False, art: Optional[str] = None):
    # Wenn keine Saison ID angegeben ist, nehme die aktuelle Saison
    if saisonID is None:
        SkiSaison = crud_saison.get_AktuelleSaison(db)
        if SkiSaison is not None:
            saisonID = SkiSaison.ID

    query = db.query(SaisonVerleih).filter(SaisonVerleih.Saison_ID == saisonID)
    if art is not None:
        query = query.filter(SaisonVerleih.Art == art)

    # Wenn "alle" True ist, gebe alle Einträge zurück, andernfalls wende Pagination an
    if alle:
        return query.order_by(SaisonVerleih.ID).all()
    
    # Pagination anwenden
    if last_id is not None:
        query = query.filter(SaisonVerleih.ID > last_id)

    return query.order_by(SaisonVerleih.ID).limit(limit).all()

def finde_belegungen(
        db: Session,
        von: datetime.date,
        bis: datetime.date,
        skinr: Optional[str] = None,
        schuhnr: Optional[int] = None,
        ausser_id: Optional[int] = None,
    ) -> list[dict]:
    """
    Sucht Verleihe, in denen der Ski bzw. Schuh im Zeitraum von-bis bereits verliehen ist.
    - Tagesverleih: Zeiträume überschneiden sich
    - Saisonverleih: gestartet vor dem Ende des Zeitraums und nicht vor dessen Beginn zurückgegeben
    """
    if not skinr and not schuhnr:
        return []

    material_filter = []
    if skinr:
        material_filter.append(SaisonVerleihMaterial.skinr == skinr)
    if schuhnr:
        material_filter.append(SaisonVerleihMaterial.schuhnr == schuhnr)

    gestartet = or_(SaisonVerleih.Start_Am.is_(None), SaisonVerleih.Start_Am <= bis)
    nicht_zurueck = or_(
        SaisonVerleih.Zurueck.is_(None),
        SaisonVerleih.Zurueck == 0,
        SaisonVerleih.Zurueck_Am.is_(None),
        SaisonVerleih.Zurueck_Am >= von,
    )
    zeitraum_filter = or_(
        and_(SaisonVerleih.Art == "tag", gestartet, SaisonVerleih.Ende_Am >= von),
        and_(SaisonVerleih.Art != "tag", gestartet, nicht_zurueck),
    )

    query = (
        db.query(SaisonVerleih)
        .join(SaisonVerleih.Material)
        .filter(or_(*material_filter), zeitraum_filter)
        .options(selectinload(SaisonVerleih.Material), selectinload(SaisonVerleih.Kunde))
        .distinct()
    )
    if ausser_id is not None:
        query = query.filter(SaisonVerleih.ID != ausser_id)

    belegungen = []
    for verleih in query.all():
        for material in verleih.Material:
            treffer = []
            if skinr and material.skinr == skinr:
                treffer.append("Ski")
            if schuhnr and material.schuhnr == schuhnr:
                treffer.append("Schuh")
            for art in treffer:
                kunde = verleih.Kunde
                belegungen.append({
                    "ID": verleih.ID,
                    "Name": verleih.Name,
                    "Art": verleih.Art,
                    "Start_Am": verleih.Start_Am,
                    "Ende_Am": verleih.Ende_Am,
                    "Kunde": f"{kunde.Vorname or ''} {kunde.Nachname or ''}".strip() if kunde else "Unbekannt",
                    "Material": art,
                })
    return belegungen


def belegung_text(belegung: dict) -> str:
    if belegung["Art"] == "tag":
        zeitraum = f"{belegung['Start_Am']:%d.%m.}–{belegung['Ende_Am']:%d.%m.%Y}"
    else:
        zeitraum = "Saisonverleih"
    return f"{belegung['Material']} ist bereits verliehen: {belegung['Name']} ({zeitraum}, {belegung['Kunde']})"


def create_saisonverleih(db: Session, saisonverleih: SaisonVerleihCreate):

    # Namen in Array
    printNamen = []

    try:
        if saisonverleih.Saison_ID is not None:
            Saison_ID = saisonverleih.Saison_ID
        else:
            SkiSaison = crud_saison.get_AktuelleSaison(db)
            if SkiSaison is None:
                return {"success": False, "data": None, "error": "Keine aktuelle Saison vorhanden."}
            Saison_ID = SkiSaison.ID

        db_saisonverleih = SaisonVerleih(
            Kunde_ID=saisonverleih.Kunde_ID,
            Bezahlt = False,
            Ueberweisung=0,
            Bemerkung=saisonverleih.Bemerkung,
            Name=crud_saison.get_next_SaisonVerleihNummer(db, saisonverleih.Art),
            Saison_ID=Saison_ID,
            Abgerechnet=saisonverleih.Abgerechnet,
            Art=saisonverleih.Art,
            Start_Am=saisonverleih.Start_Am or datetime.date.today(),
            Ende_Am=saisonverleih.Ende_Am if saisonverleih.Art == "tag" else None,
            QuittungID=saisonverleih.QuittungID
        )

        # Beim Tagesverleih prüfen, ob Ski oder Schuh im Zeitraum schon verliehen sind
        if saisonverleih.Art == "tag":
            for material in saisonverleih.Material:
                belegungen = finde_belegungen(
                    db, saisonverleih.Start_Am, saisonverleih.Ende_Am,
                    skinr=material.skinr or None, schuhnr=material.schuhnr or None,
                )
                if belegungen:
                    return {"success": False, "data": None, "error": belegung_text(belegungen[0])}

        for material in saisonverleih.Material:

            # Namen für Etikett
            if material.SkiFahrerName and material.SkiFahrerName.strip() != "":
                printNamen.append(material.SkiFahrerName.strip())

            # -1 / 0 = kein Stock ausgewählt
            stockbez_ID = material.stockbez_ID if material.stockbez_ID and material.stockbez_ID > 0 else None
            skinr = material.skinr or None
            schuhnr = material.schuhnr or None

            db_saisonverleih.Material.append(
                SaisonVerleihMaterial(
                    skinr=skinr,
                    schuhnr=schuhnr,
                    stockbez_ID=stockbez_ID,
                    stocklaenge=material.stocklaenge,
                    Preis=material.Preis,
                    SkiFahrerName=material.SkiFahrerName
                )
            )

        db.add(db_saisonverleih)
        db.commit()
        db.refresh(db_saisonverleih)

    except Exception as e:
        db.rollback()
        logger.exception("Fehler beim Saisonverleih Speichern")
        return {
            "success": False,
            "data": None,
            "error": str(e)
            }

    # Etiketten drucken
    # Druck Job wird extra gemacht, damit ein Druckfehler den gespeicherten Verleih nicht als Fehler meldet
    if einstellungen.hole("PRINTSAISONVERLEIHCREATION") and printNamen:
        try:
            label = SkiEttiket()
            for name in printNamen:
                label.saisonFahererName(name)
            label.drucken()
        except Exception:
            logger.exception("Fehler beim Drucken der Saisonverleih Etiketten")

    return {
        "success": True,
        "data":db_saisonverleih
        }

def set_Saisonverleih_Zurueck(db: Session, saisonverleih_id: int, zurueck: bool = True):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        return False
    saisonverleih.Zurueck_Am = datetime.date.today() if zurueck else None
    saisonverleih.Zurueck = zurueck
    db.commit()
    db.refresh(saisonverleih)
    return True

def set_Saisonverleih_Quittung(db: Session, saisonverleih_id: int, quittung_id: int):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        return False
    saisonverleih.QuittungID = quittung_id
    db.commit()
    db.refresh(saisonverleih)
    return True

# --- Bearbeiten / Löschen ---

class VerleihGesperrt(Exception):
    """Bezahlte Verleihe dürfen nicht mehr geändert oder gelöscht werden."""


def _pruefe_nicht_bezahlt(saisonverleih: SaisonVerleih):
    if saisonverleih.Bezahlt or saisonverleih.QuittungID is not None:
        raise VerleihGesperrt("Der Verleih ist bezahlt und kann nicht mehr geändert werden.")


def aendere_saisonverleih(db: Session, saisonverleih_id: int, daten: SaisonVerleihUpdate):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return None
    aenderungen = daten.model_dump(exclude_unset=True)

    # Kunde und Art/Zeitraum beeinflussen die Abrechnung
    if {"Kunde_ID", "Art", "Start_Am", "Ende_Am"} & aenderungen.keys():
        _pruefe_nicht_bezahlt(saisonverleih)

    for feld, wert in aenderungen.items():
        if wert is None and feld != "Bemerkung" and feld != "Ende_Am":
            continue
        setattr(saisonverleih, feld, wert)

    if saisonverleih.Art == "tag":
        if saisonverleih.Start_Am is None or saisonverleih.Ende_Am is None:
            raise ValueError("Beim Tagesverleih sind Start- und Enddatum Pflicht.")
        if saisonverleih.Ende_Am < saisonverleih.Start_Am:
            raise ValueError("Das Enddatum darf nicht vor dem Startdatum liegen.")
    else:
        saisonverleih.Ende_Am = None

    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih


def _material_werte(material) -> dict:
    """Bereinigt leere Werte wie beim Anlegen."""
    werte = material.model_dump(exclude_unset=True)
    if "stockbez_ID" in werte:
        werte["stockbez_ID"] = werte["stockbez_ID"] if werte["stockbez_ID"] and werte["stockbez_ID"] > 0 else None
    for feld in ("skinr", "schuhnr"):
        if feld in werte:
            werte[feld] = werte[feld] or None
    return werte


def fuege_material_hinzu(db: Session, saisonverleih_id: int, material: SaisonVerleihMaterialBase):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return None
    _pruefe_nicht_bezahlt(saisonverleih)
    werte = _material_werte(material)
    if saisonverleih.Art == "tag":
        belegungen = finde_belegungen(
            db, saisonverleih.Start_Am, saisonverleih.Ende_Am,
            skinr=werte.get("skinr"), schuhnr=werte.get("schuhnr"), ausser_id=saisonverleih.ID,
        )
        if belegungen:
            raise VerleihGesperrt(belegung_text(belegungen[0]))
    saisonverleih.Material.append(SaisonVerleihMaterial(**werte))
    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih


def aendere_material(db: Session, saisonverleih_id: int, material_id: int, daten: SaisonVerleihMaterialUpdate):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return None
    material = next((m for m in saisonverleih.Material if m.ID == material_id), None)
    if material is None:
        return None

    werte = _material_werte(daten)
    # Nur der Fahrername darf nach dem Bezahlen noch geändert werden
    if set(werte.keys()) - {"SkiFahrerName"}:
        _pruefe_nicht_bezahlt(saisonverleih)

    for feld, wert in werte.items():
        setattr(material, feld, wert)
    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih


def entferne_material(db: Session, saisonverleih_id: int, material_id: int):
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return None
    _pruefe_nicht_bezahlt(saisonverleih)
    material = next((m for m in saisonverleih.Material if m.ID == material_id), None)
    if material is None:
        return None
    if len(saisonverleih.Material) == 1:
        raise VerleihGesperrt("Das letzte Material kann nicht entfernt werden. Bitte stattdessen den Verleih löschen.")
    saisonverleih.Material.remove(material)
    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih


def loesche_saisonverleih(db: Session, saisonverleih_id: int) -> bool:
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return False
    _pruefe_nicht_bezahlt(saisonverleih)
    db.delete(saisonverleih)
    db.commit()
    return True
