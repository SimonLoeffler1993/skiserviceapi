from datetime import datetime, date
from typing import Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import update, desc
from sqlalchemy.engine import CursorResult

from app.models.skiservice import Auftrag, Ski, AuftragNummer
from app.crud import saison as crud_saison
from app.schemas.skiservice import AuftragCreateSchema, AuftragUpdateSchema, SkiCreateSchema, SkiUpdateSchema
from app.services import einstellungen
from app.crud.bindungsdaten import setze_bindungsdaten

def getSkiserviceAuftrag(db: Session, skiservice_auftrag_id: int, mitski: bool = True):
    if mitski:
        return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    return db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()

def setzeSkiFertig(db: Session, skiservice_auftrag_id: int, ski_ids: list[int]):
    auftrag = db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).options(selectinload(Auftrag.skis)).first()
    if not auftrag:
        return None, False
    
    alleFertig = True

    for ski in auftrag.skis:
        if ski.id in ski_ids:
            ski.status = 1  # Status auf "fertig" setzen
            ski.fertig_date = datetime.now().strftime("%d.%m.%Y")  # Fertigstellungsdatum setzen

        if ski.status != 1: # Wenn ein Ski nicht fertig ist, alleFertig auf False setzen
            alleFertig = False

    if alleFertig:
        auftrag.fertig_date = datetime.now().strftime("%d.%m.%Y")  # Auftragsfertigstellungsdatum setzen
        auftrag.wie = "1"  # Auftrag als fertig markieren
    

    db.commit()
    db.refresh(auftrag)
    return auftrag, alleFertig

def setzeBenachrichtigt(db: Session, skiservice_auftrag_id: int, benachrichtigt: bool = True):
    auftrag = db.query(Auftrag).filter(Auftrag.id == skiservice_auftrag_id).first()
    if not auftrag:
        return False
    
    if benachrichtigt:
        auftrag.benachrichtigt = "Ja"
    else:
        auftrag.benachrichtigt = "Nein"

    db.commit()
    db.refresh(auftrag)
    return True

def neuAuftragNummer(db: Session):
    neu = AuftragNummer(
        Jahr=datetime.now().year
    )
    db.add(neu)
    db.commit()
    db.refresh(neu)
    return neu

def createSkiserviceAuftrag(db: Session, auftrag_data: AuftragCreateSchema):

    aktuelle_saison = crud_saison.get_AktuelleSaison(db)
    if aktuelle_saison is None:
        return None
    
    auftragNummer = neuAuftragNummer(db)
    name = aktuelle_saison.Name + einstellungen.hole("KUERZEL_SKISERVICE") + str(auftragNummer.NeuNr)

    new_auftrag = Auftrag(
        kunden_id=auftrag_data.kunden_id,
        abhol_date=auftrag_data.abhol_date,
        zu= str(aktuelle_saison.ID),
        name=name,
        skis=[Ski(
            name=f"{name}-{i+1}",
            service=ski.service,
            preis=ski.preis,
            komentar=ski.komentar,
            bindung_preis=ski.bindung_preis,
            bindung_check=ski.bindung_check
        ) for i, ski in enumerate(auftrag_data.skis)]
    )
    for ski, ski_daten in zip(new_auftrag.skis, auftrag_data.skis):
        setze_bindungsdaten(db, ski, auftrag_data.kunden_id, ski_daten.bindungsdaten, ski_daten.vorlage_id)
    db.add(new_auftrag)
    db.commit()
    db.refresh(new_auftrag)
    return new_auftrag

def setzeBindungGeprueft(db: Session, ski_ids: list[int]) -> bool:
    skis = db.query(Ski).filter(Ski.id.in_(ski_ids)).all()
    
    if not skis:
        return False

    for ski in skis:
        ski.bindung_status = True
        ski.gepueft = date.today()

    db.commit()
    return True

def get_skiservice_liste(db: Session, limit: int = 15, last_id: Optional[int] = None, saisonID: Optional[int] = None, alle: Optional[bool] =False):
    # Falls keine Saison ID angegebn ist, wird die aktuelle Saison verwendet
    if saisonID is None:
        SkiSaison = crud_saison.get_AktuelleSaison(db)
        if SkiSaison is not None:
            saisonID = SkiSaison.ID

    query = db.query(Auftrag).filter(Auftrag.zu == saisonID)

    if alle:
        return query.order_by(Auftrag.id).all()
    
    # Pagination anwenden
    if last_id is not None:
        # Da absteigend sortiert wird, muss kleiner als gefiltert werden
        query = query.filter(Auftrag.id < last_id)

    return query.order_by(desc(Auftrag.id)).limit(limit).all()

def get_auftragid_from_skiid(db: Session, ski_id: int) -> Optional[int]:
    ski = db.query(Ski).filter(Ski.id == ski_id).first()
    if ski:
        return ski.auftrag_id
    return None

# --- Bearbeiten / Löschen ---

class AuftragGesperrt(Exception):
    """Bezahlte Aufträge dürfen nicht mehr geändert oder gelöscht werden."""


def _ist_bezahlt(auftrag: Auftrag) -> bool:
    return auftrag.bezahlt == "ja" or auftrag.quittung_id is not None


def _fertig_status_aktualisieren(auftrag: Auftrag):
    """Setzt den Auftrag auf fertig, wenn alle Ski fertig sind, sonst wieder auf offen."""
    if auftrag.skis and all(ski.status == 1 for ski in auftrag.skis):
        if auftrag.wie != "1":
            auftrag.wie = "1"
            auftrag.fertig_date = datetime.now().strftime("%d.%m.%Y")
    else:
        auftrag.wie = None
        auftrag.fertig_date = None


def aendereAuftrag(db: Session, auftrag_id: int, daten: AuftragUpdateSchema):
    auftrag = getSkiserviceAuftrag(db, auftrag_id)
    if auftrag is None:
        return None
    aenderungen = daten.model_dump(exclude_unset=True)
    if "kunden_id" in aenderungen and aenderungen["kunden_id"] is not None:
        auftrag.kunden_id = aenderungen["kunden_id"]
        # Bindungsdaten gehören zum Kunden des Auftrags
        for ski in auftrag.skis:
            if ski.bindungsdaten is not None:
                ski.bindungsdaten.Kunde_ID = auftrag.kunden_id
    if "abhol_date" in aenderungen:
        auftrag.abhol_date = aenderungen["abhol_date"] or None
    # Gleiche Werte wie setzeBenachrichtigt, jederzeit änderbar (auch nach dem Bezahlen)
    if aenderungen.get("benachrichtigt") is not None:
        auftrag.benachrichtigt = "Ja" if aenderungen["benachrichtigt"] else "Nein"
    db.commit()
    db.refresh(auftrag)
    return auftrag


def fuegeSkiHinzu(db: Session, auftrag_id: int, ski_daten: SkiCreateSchema):
    auftrag = getSkiserviceAuftrag(db, auftrag_id)
    if auftrag is None:
        return None
    if _ist_bezahlt(auftrag):
        raise AuftragGesperrt("Der Auftrag ist bezahlt und kann nicht mehr erweitert werden.")

    # Laufende Nummer aus den vorhandenen Ski-Namen ermitteln (z.B. 25/26S12-3)
    nummern = [int(s.name.rsplit("-", 1)[1]) for s in auftrag.skis if s.name and s.name.rsplit("-", 1)[-1].isdigit()]
    naechste = max(nummern, default=0) + 1

    neuer_ski = Ski(
        name=f"{auftrag.name}-{naechste}",
        service=ski_daten.service,
        preis=ski_daten.preis,
        komentar=ski_daten.komentar,
        bindung_preis=ski_daten.bindung_preis,
        bindung_check=ski_daten.bindung_check,
    )
    auftrag.skis.append(neuer_ski)
    setze_bindungsdaten(db, neuer_ski, auftrag.kunden_id, ski_daten.bindungsdaten, ski_daten.vorlage_id)
    _fertig_status_aktualisieren(auftrag)
    db.commit()
    db.refresh(auftrag)
    return auftrag


def aendereSki(db: Session, auftrag_id: int, ski_id: int, daten: SkiUpdateSchema):
    auftrag = getSkiserviceAuftrag(db, auftrag_id)
    if auftrag is None:
        return None
    ski = next((s for s in auftrag.skis if s.id == ski_id), None)
    if ski is None:
        return None

    aenderungen = daten.model_dump(exclude_unset=True)
    # Bindungsdaten werden getrennt behandelt
    bindung_geaendert = "bindungsdaten" in aenderungen or aenderungen.get("bindung_check") is False
    aenderungen.pop("bindungsdaten", None)
    aenderungen.pop("vorlage_id", None)
    preisrelevant = {"service", "preis", "bindung_check", "bindung_preis"} & aenderungen.keys()
    if preisrelevant and _ist_bezahlt(auftrag):
        raise AuftragGesperrt("Der Auftrag ist bezahlt, Service und Preise können nicht mehr geändert werden.")

    for feld, wert in aenderungen.items():
        if wert is None and feld not in ("komentar",):
            continue
        setattr(ski, feld, wert)

    if "status" in aenderungen:
        ski.fertig_date = datetime.now().strftime("%d.%m.%Y") if ski.status == 1 else None
        _fertig_status_aktualisieren(auftrag)

    # Bindungsdaten sind auch nach dem Bezahlen änderbar, sie betreffen keinen Preis
    if bindung_geaendert:
        setze_bindungsdaten(db, ski, auftrag.kunden_id, daten.bindungsdaten, daten.vorlage_id)

    db.commit()
    db.refresh(auftrag)
    return auftrag


def entferneSki(db: Session, auftrag_id: int, ski_id: int):
    auftrag = getSkiserviceAuftrag(db, auftrag_id)
    if auftrag is None:
        return None
    if _ist_bezahlt(auftrag):
        raise AuftragGesperrt("Der Auftrag ist bezahlt, es können keine Ski entfernt werden.")
    ski = next((s for s in auftrag.skis if s.id == ski_id), None)
    if ski is None:
        return None
    if len(auftrag.skis) == 1:
        raise AuftragGesperrt("Der letzte Ski kann nicht entfernt werden. Bitte stattdessen den Auftrag löschen.")

    auftrag.skis.remove(ski)
    _fertig_status_aktualisieren(auftrag)
    db.commit()
    db.refresh(auftrag)
    return auftrag


def loescheAuftrag(db: Session, auftrag_id: int) -> bool:
    auftrag = getSkiserviceAuftrag(db, auftrag_id)
    if auftrag is None:
        return False
    if _ist_bezahlt(auftrag):
        raise AuftragGesperrt("Der Auftrag ist bezahlt und kann nicht gelöscht werden.")
    db.delete(auftrag)
    db.commit()
    return True
