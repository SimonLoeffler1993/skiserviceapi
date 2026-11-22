"""
Setzt bei jedem Flush automatisch, wer einen Auftrag bzw. Verleih angelegt und zuletzt geändert hat.
Eine geänderte Ski- bzw. Materialzeile zählt als Änderung am Auftrag bzw. Verleih.
Der Benutzer kommt aus dem aktuellen Zugriff (app/core/zugriff.py); ohne Anmeldung bleibt alles, wie es ist.
"""
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.zugriff import aktueller_benutzer_id
from app.models.saisonverleih import SaisonVerleih, SaisonVerleihMaterial
from app.models.skiservice import Auftrag, Ski

_registriert = False


def _auftrag_markieren(auftrag: Auftrag, benutzer_id: int, jetzt: datetime, neu: bool) -> None:
    if neu and auftrag.angelegt_von is None:
        auftrag.angelegt_von = benutzer_id
    auftrag.geaendert_von = benutzer_id
    auftrag.geaendert_am = jetzt


def _verleih_markieren(verleih: SaisonVerleih, benutzer_id: int, jetzt: datetime, neu: bool) -> None:
    if neu and verleih.Angelegt_Von is None:
        verleih.Angelegt_Von = benutzer_id
    verleih.Geaendert_Von = benutzer_id
    verleih.Geaendert_Am = jetzt


def _vor_dem_flush(session: Session, _flush_context, _instances) -> None:
    benutzer_id = aktueller_benutzer_id()
    if benutzer_id is None:
        return
    jetzt = datetime.now()
    # Kein Autoflush beim Nachladen der Eltern-Objekte (sonst Flush im Flush)
    with session.no_autoflush:
        for objekt in session.new:
            if isinstance(objekt, Auftrag):
                _auftrag_markieren(objekt, benutzer_id, jetzt, neu=True)
            elif isinstance(objekt, SaisonVerleih):
                _verleih_markieren(objekt, benutzer_id, jetzt, neu=True)
            elif isinstance(objekt, Ski) and objekt.auftrag is not None and objekt.auftrag not in session.new:
                _auftrag_markieren(objekt.auftrag, benutzer_id, jetzt, neu=False)
            elif isinstance(objekt, SaisonVerleihMaterial) and objekt.saisonverleih is not None \
                    and objekt.saisonverleih not in session.new:
                _verleih_markieren(objekt.saisonverleih, benutzer_id, jetzt, neu=False)

        for objekt in list(session.dirty):
            if not session.is_modified(objekt, include_collections=False):
                continue
            if isinstance(objekt, Auftrag):
                _auftrag_markieren(objekt, benutzer_id, jetzt, neu=False)
            elif isinstance(objekt, SaisonVerleih):
                _verleih_markieren(objekt, benutzer_id, jetzt, neu=False)
            elif isinstance(objekt, Ski) and objekt.auftrag is not None:
                _auftrag_markieren(objekt.auftrag, benutzer_id, jetzt, neu=False)
            elif isinstance(objekt, SaisonVerleihMaterial) and objekt.saisonverleih is not None:
                _verleih_markieren(objekt.saisonverleih, benutzer_id, jetzt, neu=False)


def registrieren() -> None:
    """Einmal beim Import von app.db.session; gilt für alle Sessions."""
    global _registriert
    if not _registriert:
        event.listen(Session, "before_flush", _vor_dem_flush)
        _registriert = True
