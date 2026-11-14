"""
Auswertung je Materialstück: jede Verleihzeile einzeln und was der Ski bzw. Schuh erwirtschaftet hat.

Der Preis steht nur einmal je Verleihzeile (Ski, Schuh und Stock zusammen). Aufteilung:
- Ski und Schuh in der Zeile: der Ski bekommt VERLEIH_ANTEIL_SKI_PROZENT, der Schuh den Rest
- nur Ski bzw. nur Schuh: der ganze Preis
- Stöcke zählen nicht
Es zählen alle Verleihe, auch noch nicht bezahlte. Beim Ski werden die Services abgezogen.
"""
from datetime import date

from sqlalchemy.orm import Session, joinedload

from app.models.materialschuh import EigenSchuh
from app.models.materialski import EigenSki
from app.models.materialskiservice import VerleihSkiService
from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.schemas.materialdetails import SkiServiceCreate, SkiServiceUpdate
from app.services import einstellungen


def anteil_ski_prozent() -> int:
    return min(100, max(0, int(einstellungen.hole("VERLEIH_ANTEIL_SKI_PROZENT"))))


def service_abzug_standard() -> float:
    return max(0.0, float(einstellungen.hole("VERLEIH_SKI_SERVICE_ABZUG")))


def _positionen(db: Session, bedingung, fuer_ski: bool, ski_prozent: int) -> list[dict]:
    """Jede Verleihzeile einzeln (nicht je Verleih zusammengefasst), neueste zuerst."""
    zeilen = (
        db.query(SaisonVerleihMaterial)
        .filter(bedingung)
        .options(joinedload(SaisonVerleihMaterial.saisonverleih).joinedload(SaisonVerleih.Kunde))
        .all()
    )
    ergebnis = []
    for zeile in zeilen:
        verleih = zeile.saisonverleih
        if verleih is None:
            continue
        mit_ski = zeile.skinr is not None
        mit_schuh = zeile.schuhnr is not None
        if mit_ski and mit_schuh:
            prozent = ski_prozent if fuer_ski else 100 - ski_prozent
        else:
            prozent = 100
        preis = float(zeile.Preis or 0)
        kunde = verleih.Kunde
        ergebnis.append({
            "Verleih_ID": verleih.ID,
            "Material_ID": zeile.ID,
            "Name": verleih.Name,
            "Art": verleih.Art,
            "Saison_ID": verleih.Saison_ID,
            "Start_Am": verleih.Start_Am,
            "Ende_Am": verleih.Ende_Am,
            "Kunde": " ".join(t for t in ((kunde.Vorname if kunde else None), (kunde.Nachname if kunde else None)) if t) or "Unbekannt",
            "Fahrer": (zeile.SkiFahrerName or "").strip() or None,
            "Status": verleih.Status,
            "Bezahlt": bool(verleih.Bezahlt),
            "Preis": preis,
            "MitSki": mit_ski,
            "MitSchuh": mit_schuh,
            "AnteilProzent": prozent,
            "Anteil": round(preis * prozent / 100, 2),
        })
    return sorted(ergebnis, key=lambda e: (e["Verleih_ID"], e["Material_ID"]), reverse=True)


def _summen(positionen: list[dict], service_abzug: float = 0.0) -> dict:
    einnahmen = round(sum(p["Anteil"] for p in positionen), 2)
    return {
        "AnzahlVerleihe": len({p["Verleih_ID"] for p in positionen}),
        "Einnahmen": einnahmen,
        "ServiceAbzug": round(service_abzug, 2),
        "Ergebnis": round(einnahmen - service_abzug, 2),
    }


def services_von_ski(db: Session, ski_id: int) -> list[VerleihSkiService]:
    return (
        db.query(VerleihSkiService)
        .filter(VerleihSkiService.EigenSki_ID == ski_id)
        .order_by(VerleihSkiService.Datum.desc(), VerleihSkiService.ID.desc())
        .all()
    )


def ski_details(db: Session, ski: EigenSki) -> dict:
    prozent = anteil_ski_prozent()
    positionen = _positionen(db, SaisonVerleihMaterial.skinr == ski.SkiNr, True, prozent)
    services = services_von_ski(db, ski.ID)
    ski.ImVerleih = bool(positionen)
    return {
        "Ski": ski,
        "Verleihe": positionen,
        "Services": services,
        "Summen": _summen(positionen, sum(float(s.Abzug or 0) for s in services)),
        "AnteilSkiProzent": prozent,
        "ServiceAbzugStandard": service_abzug_standard(),
    }


def schuh_details(db: Session, schuh: EigenSchuh) -> dict:
    prozent = anteil_ski_prozent()
    positionen = _positionen(db, SaisonVerleihMaterial.schuhnr == schuh.ID, False, prozent)
    schuh.ImVerleih = bool(positionen)
    return {
        "Schuh": schuh,
        "Verleihe": positionen,
        "Summen": _summen(positionen),
        "AnteilSkiProzent": prozent,
    }


# --- Services am Leihski ---

def erstelle_service(db: Session, ski: EigenSki, daten: SkiServiceCreate) -> VerleihSkiService:
    service = VerleihSkiService(
        EigenSki_ID=ski.ID,
        Datum=daten.Datum or date.today(),
        Bezeichnung=daten.Bezeichnung.strip(),
        Abzug=round(daten.Abzug, 2) if daten.Abzug is not None else service_abzug_standard(),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


def aendere_service(db: Session, service: VerleihSkiService, daten: SkiServiceUpdate) -> VerleihSkiService:
    """Nur gesetzte Felder werden geändert."""
    for feld, wert in daten.model_dump(exclude_unset=True).items():
        if wert is None:
            continue
        if feld == "Bezeichnung":
            wert = wert.strip()
        elif feld == "Abzug":
            wert = round(wert, 2)
        setattr(service, feld, wert)
    db.commit()
    db.refresh(service)
    return service


def loesche_service(db: Session, service: VerleihSkiService):
    db.delete(service)
    db.commit()
