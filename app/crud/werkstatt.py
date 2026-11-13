"""
Abfragen für das Werkstatt-Dashboard: offene Arbeit, kleine Auswertung und Verleih-Zahlen.
Die Datumsfelder im Skiservice sind teils Text ("TT.MM.JJJJ"), deshalb wird in Python gezählt.
"""
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.models.skiservice import Auftrag, Ski

VERLEIH_STATUS = ("vorbereitung", "vorbereitet", "unterwegs", "zurueck")


def _text_datum(text: Optional[str]) -> Optional[date]:
    """ "TT.MM.JJJJ" als Datum, None bei leerem oder ungültigem Text."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def _kunde_name(kunde) -> str:
    if kunde is None:
        return "Ohne Kunde"
    return ", ".join(t for t in (kunde.Nachname, kunde.Vorname) if t) or "Ohne Kunde"


def _zaehle(zeitraum: dict, am: Optional[date], heute: date) -> None:
    """Ein erledigtes Teil in heute / woche / saison einsortieren."""
    zeitraum["saison"] += 1
    if am is None:
        return
    if am == heute:
        zeitraum["heute"] += 1
    if heute - timedelta(days=6) <= am <= heute:
        zeitraum["woche"] += 1


def _neuer_zeitraum() -> dict:
    return {"heute": 0, "woche": 0, "saison": 0}


def offene_ski(db: Session, saison_id: int) -> list[dict]:
    """Ski der Saison, deren Leistung oder Bindungscheck noch offen ist. Dringendste zuerst."""
    service_offen = or_(Ski.status.is_(None), Ski.status != 1)
    bindung_offen = and_(Ski.bindung_check.is_(True), or_(Ski.bindung_status.is_(None), Ski.bindung_status.is_(False)))
    skis = (
        db.query(Ski)
        .join(Ski.auftrag)
        .filter(Auftrag.zu == str(saison_id))
        # Abgeholte Aufträge sind erledigt
        .filter(or_(Auftrag.wie.is_(None), Auftrag.wie != "2"))
        .filter(or_(service_offen, bindung_offen))
        .options(joinedload(Ski.auftrag).joinedload(Auftrag.kunde))
        .all()
    )

    ergebnis = []
    for ski in skis:
        auftrag = ski.auftrag
        ergebnis.append({
            "ski_id": ski.id,
            "ski_name": ski.name,
            "auftrag_id": auftrag.id,
            "auftrag_name": auftrag.name,
            "kunde_name": _kunde_name(auftrag.kunde),
            "service": ski.service,
            "komentar": ski.komentar,
            "service_offen": ski.status != 1,
            "bindung_offen": bool(ski.bindung_check) and not ski.bindung_status,
            "abhol_date": auftrag.abhol_date,
        })

    # Nach Fertig-bis-Datum, ohne Datum ans Ende, dann nach Auftrag und Ski
    ergebnis.sort(key=lambda e: (_text_datum(e["abhol_date"]) or date.max, e["auftrag_id"], e["ski_id"]))
    return ergebnis


def offene_verleihe(db: Session, saison_id: int) -> list[dict]:
    """Verleihe in Vorbereitung (Bindungen noch nicht alle geprüft), früheste zuerst."""
    verleihe = (
        db.query(SaisonVerleih)
        .filter(SaisonVerleih.Saison_ID == saison_id, SaisonVerleih.Status == "vorbereitung")
        .options(selectinload(SaisonVerleih.Material), joinedload(SaisonVerleih.Kunde))
        .order_by(SaisonVerleih.Start_Am, SaisonVerleih.ID)
        .all()
    )
    return [
        {
            "ID": verleih.ID,
            "Name": verleih.Name,
            "Art": verleih.Art,
            "kunde_name": _kunde_name(verleih.Kunde),
            "Start_Am": verleih.Start_Am,
            "Ende_Am": verleih.Ende_Am,
            "material_gesamt": len(verleih.Material),
            "material_geprueft": sum(1 for m in verleih.Material if m.BindungGeprueft),
        }
        for verleih in verleihe
    ]


def auswertung(db: Session, saison_id: int) -> dict:
    """Wie viele Ski eingestellt wurden und wie viele einen Service bekommen haben."""
    heute = date.today()

    eingestellt_service = _neuer_zeitraum()
    service_fertig = _neuer_zeitraum()
    ski_gesamt = bindung_gesamt = service_offen = bindung_offen = 0

    zeilen = (
        db.query(Ski.status, Ski.fertig_date, Ski.bindung_check, Ski.bindung_status, Ski.gepueft, Auftrag.wie)
        .join(Ski.auftrag)
        .filter(Auftrag.zu == str(saison_id))
        .all()
    )
    for status, fertig_date, bindung_check, bindung_status, gepueft, wie in zeilen:
        ski_gesamt += 1
        abgeholt = wie == "2"
        if status == 1:
            _zaehle(service_fertig, _text_datum(fertig_date), heute)
        elif not abgeholt:
            service_offen += 1
        if bindung_check:
            bindung_gesamt += 1
            if bindung_status:
                _zaehle(eingestellt_service, gepueft, heute)
            elif not abgeholt:
                bindung_offen += 1

    eingestellt_verleih = _neuer_zeitraum()
    verleih_material_gesamt = verleih_bindung_offen = 0
    material = (
        db.query(SaisonVerleihMaterial.BindungGeprueft, SaisonVerleihMaterial.BindungGeprueft_Am, SaisonVerleih.Status)
        .join(SaisonVerleihMaterial.saisonverleih)
        .filter(SaisonVerleih.Saison_ID == saison_id)
        .all()
    )
    for geprueft, geprueft_am, status in material:
        verleih_material_gesamt += 1
        if geprueft:
            _zaehle(eingestellt_verleih, geprueft_am, heute)
        elif status == "vorbereitung":
            verleih_bindung_offen += 1

    return {
        "eingestellt_service": eingestellt_service,
        "eingestellt_verleih": eingestellt_verleih,
        "service_fertig": service_fertig,
        "ski_gesamt": ski_gesamt,
        "bindung_gesamt": bindung_gesamt,
        "service_offen": service_offen,
        "bindung_offen": bindung_offen,
        "verleih_material_gesamt": verleih_material_gesamt,
        "verleih_bindung_offen": verleih_bindung_offen,
    }


def verleih_zahlen(db: Session, saison_id: int) -> dict:
    """Anzahl der Verleihe je Art und Status, dazu unbezahlte und fällige Rückgaben."""
    def leer() -> dict:
        return {**{status: 0 for status in VERLEIH_STATUS}, "gesamt": 0, "unbezahlt": 0, "rueckgabe_faellig": 0}

    zahlen = {"saison": leer(), "tag": leer()}

    je_status = (
        db.query(SaisonVerleih.Art, SaisonVerleih.Status, func.count(SaisonVerleih.ID))
        .filter(SaisonVerleih.Saison_ID == saison_id)
        .group_by(SaisonVerleih.Art, SaisonVerleih.Status)
        .all()
    )
    for art, status, anzahl in je_status:
        if art not in zahlen:
            continue
        zahlen[art]["gesamt"] += anzahl
        if status in VERLEIH_STATUS:
            zahlen[art][status] += anzahl

    unbezahlt = (
        db.query(SaisonVerleih.Art, func.count(SaisonVerleih.ID))
        .filter(SaisonVerleih.Saison_ID == saison_id)
        .filter(or_(SaisonVerleih.Bezahlt.is_(None), SaisonVerleih.Bezahlt.is_(False)))
        .group_by(SaisonVerleih.Art)
        .all()
    )
    for art, anzahl in unbezahlt:
        if art in zahlen:
            zahlen[art]["unbezahlt"] = anzahl

    zahlen["tag"]["rueckgabe_faellig"] = (
        db.query(func.count(SaisonVerleih.ID))
        .filter(
            SaisonVerleih.Saison_ID == saison_id,
            SaisonVerleih.Art == "tag",
            SaisonVerleih.Status == "unterwegs",
            SaisonVerleih.Ende_Am <= date.today(),
        )
        .scalar()
    ) or 0

    return zahlen
