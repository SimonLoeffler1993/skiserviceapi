"""
Ereignisprotokoll: wer hat wann was getan.

erfasse()        hängt das Ereignis an die Session des Aufrufers an, ohne Commit: es wird zusammen
                 mit der eigentlichen Änderung gespeichert oder gar nicht.
erfasse_sofort() eigene Session, wirft nie (z.B. für fehlgeschlagene Anmeldungen).

Benutzer und Gerät kommen aus dem aktuellen Zugriff (app/core/zugriff.py).
"""
import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.zugriff import aktueller_zugriff
from app.db.session import SessionLocal
from app.models.ereignis import Ereignis

logger = logging.getLogger(__name__)

# Art -> Bezeichnung für die Anzeige im Verlauf
ARTEN = {
    "auftrag_angelegt": "Auftrag angelegt",
    "auftrag_geloescht": "Auftrag gelöscht",
    "auftrag_abgeholt": "Abgeholt",
    "auftrag_abgeholt_zurueck": "Abholung zurückgenommen",
    "ski_fertig": "Ski fertig",
    "ski_fertig_zurueck": "Ski wieder in Arbeit",
    "bindung_geprueft": "Bindung geprüft",
    "verleih_angelegt": "Verleih angelegt",
    "verleih_geloescht": "Verleih gelöscht",
    "verleih_status": "Status geändert",
    "verleih_bindung_geprueft": "Bindung geprüft",
    "verleih_zurueckgegeben": "Zurückgegeben",
    "bezahlt": "Bezahlt",
    "unbezahlt": "Als unbezahlt markiert",
    "quittung_storniert": "Quittung storniert",
    "aus_quittung_entfernt": "Aus Quittung entfernt",
    "einstellung_geaendert": "Einstellung geändert",
    "vorlage_geaendert": "Mail-Vorlage geändert",
    "benutzer_angelegt": "Benutzer angelegt",
    "benutzer_geaendert": "Benutzer geändert",
    "benutzer_freigegeben": "Benutzer freigegeben",
    "benutzer_geloescht": "Benutzer gelöscht",
    "rolle_geaendert": "Rolle geändert",
    "gruppe_geaendert": "Gruppe geändert",
    "geraeteschluessel_erzeugt": "Geräteschlüssel erzeugt",
    "geraeteschluessel_geaendert": "Geräteschlüssel geändert",
    "geraeteschluessel_geloescht": "Geräteschlüssel gelöscht",
    "geraet_angemeldet": "Gerät angemeldet",
    "geraet_abgemeldet": "Gerät abgemeldet",
    "anmeldung": "Angemeldet",
    "anmeldung_fehlgeschlagen": "Anmeldung fehlgeschlagen",
    "benutzer_gesperrt": "Benutzer gesperrt (Fehlversuche)",
}


def _neues_ereignis(art: str, *, benutzer_id: int | None, benutzer_name: str | None, kunde_id: int | None,
                    auftrag_id: int | None, verleih_id: int | None, quittung_id: int | None,
                    text: str, daten: Any) -> Ereignis:
    zugriff = aktueller_zugriff.get()
    if benutzer_id is None and zugriff.benutzer is not None:
        benutzer_id = zugriff.benutzer.id
        benutzer_name = benutzer_name or zugriff.benutzer.anzeigename
    return Ereignis(
        Zeitpunkt=datetime.now(),
        Art=art,
        Benutzer_ID=benutzer_id,
        Benutzer_Name=(benutzer_name or None) and benutzer_name[:100],
        Geraet=(zugriff.geraet_name or None) and zugriff.geraet_name[:100],
        Kunde_ID=kunde_id,
        Auftrag_ID=auftrag_id,
        Verleih_ID=verleih_id,
        Quittung_ID=quittung_id,
        Text=(text or "")[:500],
        Daten=json.dumps(daten, ensure_ascii=False, default=str) if daten is not None else None,
    )


def erfasse(db: Session, art: str, *, kunde_id: int | None = None, auftrag_id: int | None = None,
            verleih_id: int | None = None, quittung_id: int | None = None, text: str = "",
            daten: Any = None, benutzer_id: int | None = None, benutzer_name: str | None = None) -> None:
    """Ereignis in der Transaktion des Aufrufers. Der Aufrufer committet."""
    db.add(_neues_ereignis(art, benutzer_id=benutzer_id, benutzer_name=benutzer_name, kunde_id=kunde_id,
                           auftrag_id=auftrag_id, verleih_id=verleih_id, quittung_id=quittung_id,
                           text=text, daten=daten))


def erfasse_sofort(art: str, **werte: Any) -> None:
    """Ereignis mit eigener Session. Fehler werden nur geloggt."""
    try:
        with SessionLocal() as db:
            erfasse(db, art, **werte)
            db.commit()
    except Exception:
        logger.exception("Ereignis %s konnte nicht gespeichert werden", art)
