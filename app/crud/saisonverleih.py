from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload
import datetime
import logging
from typing import Optional

from app.models.saisonverleih import SkiSaisonverleihPreise, SaisonVerleih, SaisonVerleihMaterial
from app.models.materialski import EigenSki
from app.models.materialschuh import EigenSchuh
from app.models.materialstock import Skistock
from app.schemas.saisonverleih import SaisonVerleihCreate, SaisonVerleihPreisBase, SaisonVerleihUpdate, SaisonVerleihMaterialBase, SaisonVerleihMaterialUpdate
from app.crud import saison as crud_saison
from app.utils.skiEttiket import SkiEttiket
from app.services import einstellungen
from app.crud.bindungsdaten import bindung_werte, setze_bindungsdaten

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
    # Pro Verleih und Teil nur ein Eintrag, auch wenn das Teil (trotz Belegung) mehrfach drinsteckt
    gesehen: set[tuple[int, str]] = set()
    for verleih in query.all():
        for material in verleih.Material:
            treffer = []
            if skinr and material.skinr == skinr:
                treffer.append("Ski")
            if schuhnr and material.schuhnr == schuhnr:
                treffer.append("Schuh")
            for art in treffer:
                if (verleih.ID, art) in gesehen:
                    continue
                gesehen.add((verleih.ID, art))
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


def belegung_fehler(
        db: Session,
        art: str,
        start: Optional[datetime.date],
        ende: Optional[datetime.date],
        skinr: Optional[str],
        schuhnr: Optional[int],
        ausser_id: Optional[int] = None,
    ) -> Optional[str]:
    """
    Meldung, wenn Ski oder Schuh schon verliehen sind, sonst None.
    Tagesverleih: im Zeitraum Start-Ende. Saisonverleih: heute in einem nicht zurückgegebenen Verleih.
    """
    if art == "tag":
        von, bis = start, ende
    else:
        von = bis = datetime.date.today()
    if von is None or bis is None:
        return None
    belegungen = finde_belegungen(db, von, bis, skinr=skinr, schuhnr=schuhnr, ausser_id=ausser_id)
    return belegung_text(belegungen[0]) if belegungen else None


def material_nicht_verfuegbar(db: Session, skinr: Optional[str], schuhnr: Optional[int], stockbez_ID: Optional[int]) -> Optional[str]:
    """Prüft, ob Ski, Schuh und Stock existieren und nicht ausgemustert sind. Gibt sonst eine Meldung zurück."""
    if skinr:
        ski = db.query(EigenSki).filter(EigenSki.SkiNr == skinr).first()
        if ski is None:
            return f"Ski {skinr} existiert nicht."
        if ski.Ausgemustert:
            return f"Ski {skinr} ist ausgemustert."
    if schuhnr:
        schuh = db.get(EigenSchuh, schuhnr)
        if schuh is None:
            return "Der Schuh existiert nicht."
        if schuh.Ausgemustert:
            return f"Schuh {schuh.SchuhNr} ist ausgemustert."
    if stockbez_ID and stockbez_ID > 0:
        stock = db.get(Skistock, stockbez_ID)
        if stock is None:
            return "Der Stock existiert nicht."
        if stock.Ausgemustert:
            return f"Stock {stock.Bezeichnung} ist ausgemustert."
    return None


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

        # Startstatus aus den Einstellungen, je Art getrennt: direkt unterwegs gilt als heute abgeholt
        schluessel = "VERLEIH_STARTSTATUS_TAG" if saisonverleih.Art == "tag" else "VERLEIH_STARTSTATUS_SAISON"
        startstatus = einstellungen.hole(schluessel) or "vorbereitung"
        db_saisonverleih = SaisonVerleih(
            Kunde_ID=saisonverleih.Kunde_ID,
            Status=startstatus,
            Zurueck=False,
            Abgeholt_Am=datetime.date.today() if startstatus == "unterwegs" else None,
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

        # Ausgemustertes Material darf nicht mehr verliehen werden
        for material in saisonverleih.Material:
            fehler = material_nicht_verfuegbar(db, material.skinr or None, material.schuhnr or None, material.stockbez_ID)
            if fehler:
                return {"success": False, "data": None, "error": fehler}

        # Prüfen, ob Ski oder Schuh schon verliehen sind, außer bewusst übernommen
        for material in saisonverleih.Material:
            if material.trotz_belegung:
                continue
            fehler = belegung_fehler(
                db, saisonverleih.Art, saisonverleih.Start_Am, saisonverleih.Ende_Am,
                material.skinr or None, material.schuhnr or None,
            )
            if fehler:
                return {"success": False, "data": None, "error": fehler}

        for material in saisonverleih.Material:

            # Namen für Etikett
            if material.SkiFahrerName and material.SkiFahrerName.strip() != "":
                printNamen.append(material.SkiFahrerName.strip())

            # -1 / 0 = kein Stock ausgewählt
            stockbez_ID = material.stockbez_ID if material.stockbez_ID and material.stockbez_ID > 0 else None
            skinr = material.skinr or None
            schuhnr = material.schuhnr or None

            neues_material = SaisonVerleihMaterial(
                skinr=skinr,
                schuhnr=schuhnr,
                stockbez_ID=stockbez_ID,
                stocklaenge=material.stocklaenge,
                Preis=material.Preis,
                SkiFahrerName=material.SkiFahrerName
            )
            db_saisonverleih.Material.append(neues_material)
            setze_bindungsdaten(db, neues_material, saisonverleih.Kunde_ID, material.bindungsdaten, material.vorlage_id)

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

def setze_status(db: Session, saisonverleih_id: int, status: str):
    """
    Setzt den Status (vorbereitung, vorbereitet, unterwegs, zurueck), auch rückwärts zum Korrigieren.
    Abgeholt_Am, Zurueck und Zurueck_Am werden passend mitgeführt.
    """
    if status not in ("vorbereitung", "vorbereitet", "unterwegs", "zurueck"):
        raise ValueError(f"Unbekannter Status: {status}")
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        return None
    heute = datetime.date.today()
    saisonverleih.Status = status
    if status in ("vorbereitung", "vorbereitet"):
        saisonverleih.Abgeholt_Am = None
    elif saisonverleih.Abgeholt_Am is None:
        saisonverleih.Abgeholt_Am = heute
    saisonverleih.Zurueck = status == "zurueck"
    saisonverleih.Zurueck_Am = (saisonverleih.Zurueck_Am or heute) if status == "zurueck" else None
    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih

def set_Saisonverleih_Zurueck(db: Session, saisonverleih_id: int, zurueck: bool = True):
    return setze_status(db, saisonverleih_id, "zurueck" if zurueck else "unterwegs") is not None

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

    # Bindungsdaten gehören zum Kunden des Verleihs
    if aenderungen.get("Kunde_ID") is not None:
        for material in saisonverleih.Material:
            if material.bindungsdaten is not None:
                material.bindungsdaten.Kunde_ID = saisonverleih.Kunde_ID

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
    """Bereinigt leere Werte wie beim Anlegen. Bindungsdaten werden getrennt gespeichert."""
    werte = material.model_dump(exclude_unset=True, exclude={"bindungsdaten", "vorlage_id", "trotz_belegung"})
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
    fehler = material_nicht_verfuegbar(db, werte.get("skinr"), werte.get("schuhnr"), werte.get("stockbez_ID"))
    if fehler:
        raise VerleihGesperrt(fehler)
    if not material.trotz_belegung:
        fehler = belegung_fehler(
            db, saisonverleih.Art, saisonverleih.Start_Am, saisonverleih.Ende_Am,
            werte.get("skinr"), werte.get("schuhnr"), ausser_id=saisonverleih.ID,
        )
        if fehler:
            raise VerleihGesperrt(fehler)
    neues_material = SaisonVerleihMaterial(**werte)
    saisonverleih.Material.append(neues_material)
    setze_bindungsdaten(db, neues_material, saisonverleih.Kunde_ID, material.bindungsdaten, material.vorlage_id)
    # Neuer, ungeprüfter Ski: Verleih ist nicht mehr vorbereitet
    _status_nach_pruefung(saisonverleih)
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
    # Nach dem Bezahlen ist nur der Preis gesperrt, Material darf getauscht werden
    if "Preis" in werte and werte["Preis"] != material.Preis:
        _pruefe_nicht_bezahlt(saisonverleih)

    # Nur getauschte Teile prüfen, das bisherige Material bleibt gültig
    neue_skinr = werte.get("skinr") if "skinr" in werte and werte["skinr"] != material.skinr else None
    neue_schuhnr = werte.get("schuhnr") if "schuhnr" in werte and werte["schuhnr"] != material.schuhnr else None
    neuer_stock = werte.get("stockbez_ID") if "stockbez_ID" in werte and werte["stockbez_ID"] != material.stockbez_ID else None
    fehler = material_nicht_verfuegbar(db, neue_skinr, neue_schuhnr, neuer_stock)
    if not fehler and not daten.trotz_belegung:
        fehler = belegung_fehler(
            db, saisonverleih.Art, saisonverleih.Start_Am, saisonverleih.Ende_Am,
            neue_skinr, neue_schuhnr, ausser_id=saisonverleih.ID,
        )
    if fehler:
        raise VerleihGesperrt(fehler)

    ski_vorher = material.skinr
    bindung_vorher = _bindung_werte(material)
    for feld, wert in werte.items():
        setattr(material, feld, wert)
    if "bindungsdaten" in daten.model_fields_set:
        setze_bindungsdaten(db, material, saisonverleih.Kunde_ID, daten.bindungsdaten, daten.vorlage_id)
    # Anderer Ski oder geänderte Bindungsdaten: Bindung muss neu geprüft werden
    if material.skinr != ski_vorher or _bindung_werte(material) != bindung_vorher:
        material.BindungGeprueft = False
        material.BindungGeprueft_Am = None
    _status_nach_pruefung(saisonverleih)
    db.commit()
    db.refresh(saisonverleih)
    return saisonverleih


def _bindung_werte(material: SaisonVerleihMaterial) -> Optional[dict]:
    """Bindungsdaten als vergleichbare Werte, None ohne Daten."""
    if material.bindungsdaten is None:
        return None
    return bindung_werte(material.bindungsdaten)


def _status_nach_pruefung(saisonverleih: SaisonVerleih):
    """
    In Vorbereitung -> Vorbereitet, sobald alle Materialzeilen mit Ski geprüft sind.
    Vorbereitet -> In Vorbereitung, wenn eine Prüfung fehlt (z.B. Ski getauscht).
    Spätere Status (unterwegs, zurueck) bleiben unverändert.
    """
    mit_ski = [m for m in saisonverleih.Material if m.skinr]
    alle_geprueft = bool(mit_ski) and all(m.BindungGeprueft for m in mit_ski)
    if saisonverleih.Status == "vorbereitung" and alle_geprueft:
        saisonverleih.Status = "vorbereitet"
    elif saisonverleih.Status == "vorbereitet" and not alle_geprueft:
        saisonverleih.Status = "vorbereitung"


def pruefe_bindungen(db: Session, saisonverleih_id: int, material_ids: Optional[list[int]] = None):
    """
    Markiert die Bindung der Materialzeilen mit Ski als geprüft, ohne Angabe alle.
    Auch nach dem Bezahlen erlaubt. Sind danach alle geprüft, wird der Verleih "vorbereitet".
    """
    saisonverleih = get_saisonverleih(db, saisonverleih_id)
    if saisonverleih is None:
        return None
    heute = datetime.date.today()
    for material in saisonverleih.Material:
        if not material.skinr or material.BindungGeprueft:
            continue
        if material_ids is None or material.ID in material_ids:
            material.BindungGeprueft = True
            material.BindungGeprueft_Am = heute
    _status_nach_pruefung(saisonverleih)
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
    _status_nach_pruefung(saisonverleih)
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
