"""
Anmeldung: Passwort (Standard), freiwillige PIN, OIDC-Einmalcode; Geräte- und Bedienersitzungen; Tickets.

Ein Gerät (Center-Tablet, Kasse) wird einmal angemeldet und bekommt eine lange Gerätesitzung.
Darauf meldet sich jeweils ein Bediener an (Bedienersitzung). Pro Gerät gibt es höchstens einen Bediener.
"""
import logging
import os
import re
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import sicherheit
from app.core.zugriff import (Zugriff, anmeldung_erzwungen, bediener_timeout, ticket_ausstellen, darf_anonym, darf_anonym_lesen)
from app.models.benutzer import Bedienersitzung, Benutzer, Geraetesitzung
from app.services import einstellungen, ereignisse, oidc

logger = logging.getLogger(__name__)

# Pfade, für die ein Ticket ausgestellt wird (Zugriffe ohne Header aus dem Browser)
_TICKET_PFADE = [
    re.compile(r"^/scanner/skiscanner/data$"),
    re.compile(r"^/event/connect/[^/]{1,100}$"),
    re.compile(r"^/quittungen/quittung/\d+/pdf$"),
    re.compile(r"^/saisonverleih/pdf/\d+$"),
]
_TICKET_PFADE_TERMINAL = [re.compile(r"^/event/connect/[^/]{1,100}$")]

# Ohne Passwort darf ein OIDC-Benutzer seine PIN so lange nach der OIDC-Anmeldung setzen
_OIDC_FRISCH = timedelta(minutes=15)


class AnmeldeFehler(Exception):
    def __init__(self, status: int, detail: str, **zusatz):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.zusatz = zusatz


# --- Regeln --------------------------------------------------------------------

def passwort_regeln(passwort: str) -> None:
    minimum = int(einstellungen.hole("PASSWORT_MIN_LAENGE"))
    if len(passwort) < minimum:
        raise ValueError(f"Das Passwort muss mindestens {minimum} Zeichen lang sein.")


def pin_regeln(pin: str) -> None:
    minimum = int(einstellungen.hole("PIN_MIN_STELLEN"))
    if not pin.isdigit() or not minimum <= len(pin) <= 8:
        raise ValueError(f"Die PIN muss aus {minimum} bis 8 Ziffern bestehen.")
    if len(set(pin)) == 1 or pin in "0123456789" or pin in "9876543210":
        raise ValueError("Die PIN ist zu einfach (gleiche Ziffern oder Zahlenfolge).")


# --- Darstellung ---------------------------------------------------------------

def oidc_veraltet(benutzer: Benutzer) -> bool:
    return bool(benutzer.Oidc_Issuer) and benutzer.Oidc_Issuer != oidc.issuer_oder_none()


def ich_benutzer(db: Session, benutzer: Benutzer) -> dict:
    from app.crud import rechte as crud_rechte  # spät: crud.rechte -> services.ereignisse

    return {
        "id": benutzer.ID,
        "benutzername": benutzer.Benutzername,
        "anzeigename": benutzer.Anzeigename,
        "email": benutzer.Email,
        "rechte": crud_rechte.rechte_liste(crud_rechte.rechte_von(db, benutzer.ID)),
        "gruppen": crud_rechte.gruppen_von(benutzer, db),
        "hat_passwort": bool(benutzer.Passwort_Hash),
        "hat_pin": bool(benutzer.Pin_Hash),
        "passwort_aendern": bool(benutzer.Passwort_Aendern),
        "oidc_verknuepft": bool(benutzer.Oidc_Issuer),
        "oidc_veraltet": oidc_veraltet(benutzer),
    }


def ich_geraet(geraet: Geraetesitzung) -> dict:
    return {"id": geraet.ID, "name": geraet.Name, "art": geraet.Art,
            "bediener_timeout_minuten": bediener_timeout(geraet)}


def status(db: Session) -> dict:
    return {
        "einrichtung_noetig": einrichtung_noetig(db),
        "anmeldung_erzwungen": anmeldung_erzwungen(),
        "geraeteschluessel_erzwungen": bool(einstellungen.hole("GERAETESCHLUESSEL_ERZWINGEN")),
        "pin_erlaubt": bool(einstellungen.hole("PIN_ANMELDUNG_ERLAUBT")),
        "oidc": {"aktiv": oidc.aktiv(), "anbieter": oidc.anbieter_schluessel(), "button_text": oidc.button_text()},
        "ohne_anmeldung": _ohne_anmeldung(),
    }


def _crud_rechte():
    from app.crud import rechte  # spät: crud.rechte -> services.ereignisse -> core.zugriff

    return rechte


def _ohne_anmeldung() -> dict:
    """Was ohne Anmeldung erlaubt ist: im Übergang alles, sonst die Gruppe "Ohne Anmeldung"."""
    if not anmeldung_erzwungen():
        return {"lesen": True, "rechte": ["*"]}
    lesen, rechte = _crud_rechte().gast_zugriff()
    return {"lesen": lesen, "rechte": sorted(rechte)}


def einrichtung_noetig(db: Session) -> bool:
    return db.query(func.count(Benutzer.ID)).scalar() == 0


# --- Sperre --------------------------------------------------------------------

def _sperre_pruefen(benutzer: Benutzer, jetzt: datetime) -> None:
    if benutzer.Gesperrt_Bis and benutzer.Gesperrt_Bis > jetzt:
        raise AnmeldeFehler(423, "gesperrt_bis", gesperrt_bis=benutzer.Gesperrt_Bis.isoformat())


def _fehlversuch(db: Session, benutzer: Benutzer, art: str, jetzt: datetime) -> None:
    benutzer.Fehlversuche = (benutzer.Fehlversuche or 0) + 1
    gesperrt = benutzer.Fehlversuche >= int(einstellungen.hole("MAX_FEHLVERSUCHE"))
    if gesperrt:
        benutzer.Gesperrt_Bis = jetzt + timedelta(minutes=int(einstellungen.hole("SPERRE_MINUTEN")))
        benutzer.Fehlversuche = 0
    ereignisse.erfasse(db, "benutzer_gesperrt" if gesperrt else "anmeldung_fehlgeschlagen",
                       benutzer_id=benutzer.ID, benutzer_name=benutzer.Anzeigename, text=art)
    db.commit()


def _erfolg(benutzer: Benutzer, jetzt: datetime) -> None:
    benutzer.Fehlversuche = 0
    benutzer.Gesperrt_Bis = None
    benutzer.Letzte_Anmeldung = jetzt


def _darf_anmelden(benutzer: Benutzer) -> None:
    if benutzer.Freigabe_Ausstehend:
        raise AnmeldeFehler(403, "freigabe_ausstehend")
    if not benutzer.Aktiv:
        raise AnmeldeFehler(403, "gesperrt")


# --- Sitzungen -----------------------------------------------------------------

def _sitzungen_anlegen(db: Session, benutzer: Benutzer, methode: str, zugriff: Zugriff,
                       geraet_name: str | None, geraet_art: str) -> dict:
    jetzt = datetime.now()
    geraet_token = None
    geraet = db.get(Geraetesitzung, zugriff.geraet.id) if zugriff.geraet else None
    if geraet is None:
        geraet_token = sicherheit.token_erzeugen(sicherheit.PRAEFIX_GERAET)
        name = (geraet_name or "").strip() or f"{'Kasse' if geraet_art == 'kasse' else 'Center'} ({benutzer.Anzeigename})"
        geraet = Geraetesitzung(
            Token_Hash=sicherheit.token_hash(geraet_token),
            Name=name[:100],
            Art=geraet_art,
            Angemeldet_Von=benutzer.ID,
            Erstellt_Am=jetzt,
            Zuletzt_Gesehen=jetzt,
            Laeuft_Ab=jetzt + timedelta(days=int(einstellungen.hole("GERAETESITZUNG_TAGE"))),
        )
        db.add(geraet)
        db.flush()
        ereignisse.erfasse(db, "geraet_angemeldet", benutzer_id=benutzer.ID, benutzer_name=benutzer.Anzeigename,
                           text=geraet.Name)
    else:
        # Ein Bediener je Gerät: der vorherige wird abgemeldet
        db.query(Bedienersitzung).filter(Bedienersitzung.Geraetesitzung_ID == geraet.ID).delete()

    bediener_token = sicherheit.token_erzeugen(sicherheit.PRAEFIX_BEDIENER)
    db.add(Bedienersitzung(
        Token_Hash=sicherheit.token_hash(bediener_token),
        Geraetesitzung_ID=geraet.ID,
        Benutzer_ID=benutzer.ID,
        Methode=methode,
        Erstellt_Am=jetzt,
        Letzte_Aktivitaet=jetzt,
    ))
    ereignisse.erfasse(db, "anmeldung", benutzer_id=benutzer.ID, benutzer_name=benutzer.Anzeigename,
                       text=f"{methode} · {geraet.Name}")
    db.commit()
    return {
        "geraet_token": geraet_token,
        "bediener_token": bediener_token,
        "benutzer": ich_benutzer(db, benutzer),
        "geraet": ich_geraet(geraet),
    }


def _benutzer_nach_name(db: Session, benutzername: str) -> Benutzer | None:
    return db.query(Benutzer).filter(Benutzer.Benutzername == benutzername.strip()).one_or_none()


def anmelden(db: Session, benutzername: str, passwort: str, zugriff: Zugriff,
             geraet_name: str | None, geraet_art: str) -> dict:
    jetzt = datetime.now()
    benutzer = _benutzer_nach_name(db, benutzername)
    if benutzer is not None:
        _sperre_pruefen(benutzer, jetzt)
    if not sicherheit.passwort_pruefen(benutzer.Passwort_Hash if benutzer else None, passwort):
        if benutzer is not None:
            _fehlversuch(db, benutzer, "Passwort", jetzt)
        raise AnmeldeFehler(401, "falsche_anmeldedaten")
    _darf_anmelden(benutzer)
    if sicherheit.braucht_neuen_hash(benutzer.Passwort_Hash):
        benutzer.Passwort_Hash = sicherheit.passwort_hash(passwort)
    _erfolg(benutzer, jetzt)
    return _sitzungen_anlegen(db, benutzer, "passwort", zugriff, geraet_name, geraet_art)


def pin_anmelden(db: Session, benutzer_id: int, pin: str, zugriff: Zugriff) -> dict:
    if not einstellungen.hole("PIN_ANMELDUNG_ERLAUBT"):
        raise AnmeldeFehler(403, "pin_aus")
    jetzt = datetime.now()
    benutzer = db.get(Benutzer, benutzer_id)
    if benutzer is None or not benutzer.Pin_Hash or not benutzer.darf_anmelden:
        sicherheit.passwort_pruefen(None, pin)
        raise AnmeldeFehler(401, "falsche_anmeldedaten")
    _sperre_pruefen(benutzer, jetzt)
    if not sicherheit.passwort_pruefen(benutzer.Pin_Hash, pin):
        _fehlversuch(db, benutzer, f"PIN · {zugriff.geraet_name or ''}", jetzt)
        raise AnmeldeFehler(401, "falsche_anmeldedaten")
    _erfolg(benutzer, jetzt)
    return _sitzungen_anlegen(db, benutzer, "pin", zugriff, None, zugriff.geraet.art if zugriff.geraet else "center")


def oidc_einloesen(db: Session, code: str, zugriff: Zugriff, geraet_name: str | None, geraet_art: str) -> dict:
    eintrag = sicherheit.oidc_einmalcodes.entnehmen(code)
    if eintrag is None:
        raise AnmeldeFehler(401, "code_ungueltig")
    benutzer = db.get(Benutzer, eintrag["benutzer_id"])
    if benutzer is None:
        raise AnmeldeFehler(401, "code_ungueltig")
    _darf_anmelden(benutzer)
    _erfolg(benutzer, datetime.now())
    return _sitzungen_anlegen(db, benutzer, "oidc", zugriff, geraet_name, geraet_art)


def einrichten(db: Session, benutzername: str, anzeigename: str, passwort: str, email: str | None,
               geraet_name: str | None, geraet_art: str) -> dict:
    """Legt den ersten Admin an. Nur solange es noch keinen Benutzer gibt."""
    if not einrichtung_noetig(db):
        raise AnmeldeFehler(409, "bereits_eingerichtet")
    passwort_regeln(passwort)
    jetzt = datetime.now()
    benutzer = Benutzer(Benutzername=benutzername.strip(), Anzeigename=anzeigename.strip(), Email=email or None,
                        Aktiv=True, Passwort_Hash=sicherheit.passwort_hash(passwort),
                        Angelegt_Am=jetzt, Letzte_Anmeldung=jetzt)
    db.add(benutzer)
    db.flush()
    _crud_rechte().zur_admin_gruppe(db, benutzer)
    ereignisse.erfasse(db, "benutzer_angelegt", benutzer_id=benutzer.ID, benutzer_name=benutzer.Anzeigename,
                       text="Erster Admin (Einrichtung)")
    return _sitzungen_anlegen(db, benutzer, "passwort", Zugriff(), geraet_name, geraet_art)


def bediener_abmelden(db: Session, zugriff: Zugriff) -> None:
    if zugriff.bedienersitzung_id:
        db.query(Bedienersitzung).filter(Bedienersitzung.ID == zugriff.bedienersitzung_id).delete()
        db.commit()


def geraet_abmelden(db: Session, zugriff: Zugriff) -> None:
    if zugriff.geraet:
        geraet = db.get(Geraetesitzung, zugriff.geraet.id)
        if geraet is not None:
            db.query(Bedienersitzung).filter(Bedienersitzung.Geraetesitzung_ID == geraet.ID).delete()
            ereignisse.erfasse(db, "geraet_abgemeldet", text=geraet.Name)
            db.delete(geraet)
            db.commit()


def ich(db: Session, zugriff: Zugriff) -> dict:
    benutzer = db.get(Benutzer, zugriff.benutzer.id) if zugriff.benutzer else None
    geraet = db.get(Geraetesitzung, zugriff.geraet.id) if zugriff.geraet else None
    return {
        "benutzer": ich_benutzer(db, benutzer) if benutzer else None,
        "geraet": ich_geraet(geraet) if geraet else None,
        "methode": zugriff.methode,
    }


def kacheln(db: Session) -> list[dict]:
    """Benutzer mit selbst gesetzter PIN für die Schnellwahl."""
    if not einstellungen.hole("PIN_ANMELDUNG_ERLAUBT"):
        return []
    benutzer = (db.query(Benutzer)
                .filter(Benutzer.Pin_Hash.is_not(None), Benutzer.Aktiv.is_(True),
                        Benutzer.Freigabe_Ausstehend.is_(False))
                .order_by(Benutzer.Anzeigename)
                .all())
    return [{"id": b.ID, "anzeigename": b.Anzeigename} for b in benutzer]


# --- Mein Konto ----------------------------------------------------------------

def _eigener_benutzer(db: Session, zugriff: Zugriff) -> Benutzer:
    benutzer = db.get(Benutzer, zugriff.benutzer.id)
    if benutzer is None:
        raise AnmeldeFehler(401, "anmeldung_noetig")
    return benutzer


def _bestaetigen(db: Session, benutzer: Benutzer, passwort: str | None, zugriff: Zugriff) -> None:
    """Bestätigung mit dem Passwort; ohne Passwort (reiner OIDC-Benutzer) kurz nach der OIDC-Anmeldung."""
    jetzt = datetime.now()
    if benutzer.Passwort_Hash:
        _sperre_pruefen(benutzer, jetzt)
        if not sicherheit.passwort_pruefen(benutzer.Passwort_Hash, passwort or ""):
            _fehlversuch(db, benutzer, "Passwort (Mein Konto)", jetzt)
            raise AnmeldeFehler(403, "passwort_falsch")
        return
    sitzung = db.get(Bedienersitzung, zugriff.bedienersitzung_id) if zugriff.bedienersitzung_id else None
    if sitzung is None or sitzung.Methode != "oidc" or jetzt - sitzung.Erstellt_Am > _OIDC_FRISCH:
        raise AnmeldeFehler(403, "oidc_erneut_anmelden")


def passwort_aendern(db: Session, zugriff: Zugriff, alt: str | None, neu: str) -> dict:
    benutzer = _eigener_benutzer(db, zugriff)
    if benutzer.Passwort_Hash:
        _bestaetigen(db, benutzer, alt, zugriff)
    passwort_regeln(neu)
    benutzer.Passwort_Hash = sicherheit.passwort_hash(neu)
    benutzer.Passwort_Aendern = False
    db.commit()
    return ich_benutzer(db, benutzer)


def pin_setzen(db: Session, zugriff: Zugriff, passwort: str | None, pin: str) -> dict:
    if not einstellungen.hole("PIN_ANMELDUNG_ERLAUBT"):
        raise AnmeldeFehler(403, "pin_aus")
    benutzer = _eigener_benutzer(db, zugriff)
    _bestaetigen(db, benutzer, passwort, zugriff)
    pin_regeln(pin)
    benutzer.Pin_Hash = sicherheit.passwort_hash(pin)
    db.commit()
    return ich_benutzer(db, benutzer)


def pin_loeschen(db: Session, zugriff: Zugriff) -> dict:
    benutzer = _eigener_benutzer(db, zugriff)
    benutzer.Pin_Hash = None
    db.commit()
    return ich_benutzer(db, benutzer)


def oidc_trennen(db: Session, zugriff: Zugriff) -> dict:
    benutzer = _eigener_benutzer(db, zugriff)
    if not benutzer.Passwort_Hash:
        raise AnmeldeFehler(409, "kein_passwort")
    benutzer.Oidc_Issuer = benutzer.Oidc_Mandant = benutzer.Oidc_Kennung = None
    db.commit()
    return ich_benutzer(db, benutzer)


# --- Tickets -------------------------------------------------------------------

def ticket(zugriff: Zugriff, pfad: str) -> str:
    """Kurzzeit-Ticket für einen der erlaubten Pfade (ohne /api/v1)."""
    if zugriff.schluessel is not None:
        erlaubt = _TICKET_PFADE_TERMINAL if zugriff.schluessel.bereich == "terminal" else []
    elif zugriff.benutzer is not None:
        erlaubt = _TICKET_PFADE
    elif zugriff.geraet is not None:
        raise AnmeldeFehler(401, "bediener_noetig")
    elif darf_anonym_lesen():
        # Ohne Anmeldung (Übergang bzw. Gastgruppe mit "Alles ansehen"): das Ticket erlaubt nicht mehr als ohne
        erlaubt = _TICKET_PFADE
    elif darf_anonym("kasse.kassieren"):
        # Kasse ohne Anmeldung: nur das Quittungs-PDF
        erlaubt = [muster for muster in _TICKET_PFADE if "quittung" in muster.pattern]
    else:
        raise AnmeldeFehler(401, "anmeldung_noetig")
    if not any(muster.match(pfad) for muster in erlaubt):
        raise AnmeldeFehler(403, "pfad_nicht_erlaubt")
    return ticket_ausstellen(zugriff, pfad)


# --- Start ---------------------------------------------------------------------

def beim_start(db: Session) -> None:
    """Räumt abgelaufene Gerätesitzungen auf und legt bei Bedarf den ersten Admin aus der Umgebung an."""
    jetzt = datetime.now()
    abgelaufen = db.query(Geraetesitzung.ID).filter(Geraetesitzung.Laeuft_Ab < jetzt).all()
    if abgelaufen:
        ids = [a.ID for a in abgelaufen]
        db.query(Bedienersitzung).filter(Bedienersitzung.Geraetesitzung_ID.in_(ids)).delete(synchronize_session=False)
        db.query(Geraetesitzung).filter(Geraetesitzung.ID.in_(ids)).delete(synchronize_session=False)
        db.commit()
        logger.info("%s abgelaufene Gerätesitzungen entfernt", len(ids))

    # Systemrolle und Admin-Gruppe (und bei leerer Tabelle "Mitarbeiter") sicherstellen
    _crud_rechte().standard_anlegen(db)

    benutzername = (os.getenv("ADMIN_BENUTZER") or "").strip()
    passwort = os.getenv("ADMIN_PASSWORT") or ""
    if benutzername and passwort and einrichtung_noetig(db):
        benutzer = Benutzer(Benutzername=benutzername, Anzeigename=benutzername, Aktiv=True,
                            Passwort_Hash=sicherheit.passwort_hash(passwort), Passwort_Aendern=True, Angelegt_Am=jetzt)
        db.add(benutzer)
        db.flush()
        _crud_rechte().zur_admin_gruppe(db, benutzer)
        db.commit()
        logger.info("Erster Admin „%s“ aus ADMIN_BENUTZER angelegt; Passwort muss bei der ersten Anmeldung geändert werden",
                    benutzername)
