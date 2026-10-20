"""
Anwendungseinstellungen aus der Datenbank.

Nur die Datenbank-Verbindung kommt noch aus den Umgebungsvariablen (app/core/config.py).
Alle anderen Einstellungen stehen in der Tabelle "einstellungen" und können im Skiservice Center geändert werden.
Ist ein Schlüssel nicht in der Datenbank, wird der Standardwert aus DEFINITIONEN verwendet.

Die Werte werden im Prozess zwischengespeichert. Die API läuft ohnehin nur mit einem Worker.
"""
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.einstellung import Einstellung

logger = logging.getLogger(__name__)

EinstellungTyp = Literal["text", "zahl", "bool", "auswahl", "passwort"]


@dataclass(frozen=True)
class EinstellungDefinition:
    schluessel: str
    gruppe: str
    bezeichnung: str
    typ: EinstellungTyp = "text"
    standard: Any = ""
    beschreibung: str = ""
    optionen: list[str] = field(default_factory=list)

    @property
    def geheim(self) -> bool:
        return self.typ == "passwort"


GRUPPEN = {
    "firma": "Firma",
    "drucker": "Etikettendrucker",
    "mail": "E-Mail",
    "lexware": "Lexware Office",
    "anwendung": "Anwendung",
}

DEFINITIONEN: list[EinstellungDefinition] = [
    # Firma
    EinstellungDefinition("FIRMA_NAME", "firma", "Firmenname", standard="Simons Skiservice",
                          beschreibung="Erscheint auf Quittungen und Etiketten."),
    EinstellungDefinition("FIRMA_STRASSE", "firma", "Straße", standard="Am Anennberg 12"),
    EinstellungDefinition("FIRMA_ORT", "firma", "PLZ und Ort", standard="Fronreute"),
    EinstellungDefinition("FIRMA_TELEFON", "firma", "Telefon", standard="07502/94 27 162"),
    EinstellungDefinition("FIRMA_EMAIL", "firma", "E-Mail", standard="info@ms-skiservice.de"),
    EinstellungDefinition("FIRMA_MWST_SATZ", "firma", "MwSt. Satz in %", typ="zahl", standard=19,
                          beschreibung="0 = keine MwSt. auf der Quittung ausweisen."),
    EinstellungDefinition("FIRMA_KLEINUNTERNEHMER", "firma", "Kleinunternehmer (§ 19 UStG)", typ="bool", standard=False),

    # Etikettendrucker
    EinstellungDefinition("LABELPRINTERIDENT", "drucker", "Drucker Adresse", standard="tcp://192.168.188.159",
                          beschreibung="z.B. tcp://192.168.1.50"),
    EinstellungDefinition("LABELPRINTERMODEL", "drucker", "Druckermodell", standard="QL-820NWB"),
    EinstellungDefinition("LABELSIZE", "drucker", "Etikettenbreite", standard="62"),
    EinstellungDefinition("PRINTSAISONVERLEIHCREATION", "drucker", "Etiketten beim Anlegen eines Verleihs drucken",
                          typ="bool", standard=False),

    # E-Mail
    EinstellungDefinition("SMTP_SERVER", "mail", "SMTP Server", beschreibung="z.B. smtp.office365.com oder exchange.firma.local"),
    EinstellungDefinition("SMTP_MODUS", "mail", "Verschlüsselung", typ="auswahl", standard="starttls",
                          optionen=["ssl", "starttls", "keine"],
                          beschreibung="SSL: meist Port 465. STARTTLS: meist Port 587 (Exchange / Office 365). Keine: interner Relay, meist Port 25."),
    EinstellungDefinition("SMTP_PORT", "mail", "Port", typ="zahl", standard=587),
    EinstellungDefinition("SMTP_USER", "mail", "Benutzer", beschreibung="Leer lassen, wenn der Server ohne Anmeldung versendet (Exchange Relay)."),
    EinstellungDefinition("SMTP_PASSWORD", "mail", "Passwort", typ="passwort"),
    EinstellungDefinition("EMAIL_FROM", "mail", "Absender Adresse"),
    EinstellungDefinition("MAIL_BETREFF_FERTIG", "mail", "Betreff Fertig-Mail", standard="Dein Skiservice ist fertig!"),

    # Lexware
    EinstellungDefinition("LEXWARE_BASEURL", "lexware", "API Adresse", standard="https://api.lexware.io"),
    EinstellungDefinition("LEXWARE_APIKEY", "lexware", "API Key", typ="passwort"),
    EinstellungDefinition("LEXWARE_SYNC", "lexware", "Quittungen synchronisieren", typ="bool", standard=False),

    # Anwendung
    EinstellungDefinition("HOST", "anwendung", "Öffentliche Adresse", standard="https://ms-skiservice.de",
                          beschreibung="Basis für die QR-Codes auf den Skiservice Etiketten."),
    EinstellungDefinition("KUERZEL_SAISONVERLEIH", "anwendung", "Kürzel Saisonverleih Nummer", standard="SV",
                          beschreibung="Ergibt z.B. 25/26SV12"),
    EinstellungDefinition("KUERZEL_TAGESVERLEIH", "anwendung", "Kürzel Tagesverleih Nummer", standard="TV",
                          beschreibung="Ergibt z.B. 25/26TV3"),
    EinstellungDefinition("KUERZEL_SKISERVICE", "anwendung", "Kürzel Skiservice Nummer", standard="S",
                          beschreibung="Ergibt z.B. 25/26S12"),
]

DEFINITION_NACH_SCHLUESSEL = {d.schluessel: d for d in DEFINITIONEN}

_cache: dict[str, str | None] | None = None
_lock = threading.Lock()


def _umwandeln(definition: EinstellungDefinition, wert: str | None) -> Any:
    """Wandelt den gespeicherten Text in den passenden Python Typ um."""
    if wert is None or wert == "":
        return definition.standard
    if definition.typ == "zahl":
        try:
            return int(wert)
        except ValueError:
            return definition.standard
    if definition.typ == "bool":
        return wert.strip().lower() in ("true", "1", "ja")
    return wert


def _als_text(definition: EinstellungDefinition, wert: Any) -> str | None:
    if wert is None:
        return None
    if definition.typ == "bool":
        return "true" if wert in (True, "true", "1", 1) else "false"
    return str(wert).strip()


def _lade_cache() -> dict[str, str | None]:
    global _cache
    with _lock:
        if _cache is None:
            db = SessionLocal()
            try:
                _cache = {e.Schluessel: e.Wert for e in db.query(Einstellung).all()}
            finally:
                db.close()
        return _cache


def cache_leeren():
    global _cache
    with _lock:
        _cache = None


def hole(schluessel: str) -> Any:
    """Gibt den Wert einer Einstellung im passenden Typ zurück."""
    definition = DEFINITION_NACH_SCHLUESSEL[schluessel]
    try:
        werte = _lade_cache()
    except Exception:
        # Datenbank nicht erreichbar: Standardwert verwenden, damit z.B. Druck nicht komplett ausfällt
        logger.exception("Einstellungen konnten nicht geladen werden")
        werte = {}
    return _umwandeln(definition, werte.get(schluessel))


def alle_fuer_anzeige() -> list[dict]:
    """Alle Einstellungen für das Center. Geheime Werte werden nie zurückgegeben, nur ob sie gesetzt sind."""
    werte = _lade_cache()
    ergebnis = []
    for d in DEFINITIONEN:
        gespeichert = werte.get(d.schluessel)
        ergebnis.append({
            "schluessel": d.schluessel,
            "gruppe": d.gruppe,
            "gruppe_bezeichnung": GRUPPEN[d.gruppe],
            "bezeichnung": d.bezeichnung,
            "beschreibung": d.beschreibung,
            "typ": d.typ,
            "optionen": d.optionen,
            "wert": None if d.geheim else _umwandeln(d, gespeichert),
            "gesetzt": bool(gespeichert),
        })
    return ergebnis


def speichern(db: Session, werte: dict[str, Any]):
    """
    Speichert die übergebenen Einstellungen.
    Unbekannte Schlüssel werden abgelehnt. Leere Passwörter bedeuten "unverändert".
    """
    unbekannt = [s for s in werte if s not in DEFINITION_NACH_SCHLUESSEL]
    if unbekannt:
        raise ValueError(f"Unbekannte Einstellungen: {', '.join(unbekannt)}")

    # Erst alles prüfen, dann schreiben
    for schluessel, wert in werte.items():
        definition = DEFINITION_NACH_SCHLUESSEL[schluessel]
        if definition.typ == "auswahl" and wert not in definition.optionen:
            raise ValueError(f"Ungültiger Wert für {definition.bezeichnung}: {wert}")
        if definition.typ == "zahl" and wert not in (None, ""):
            try:
                int(wert)
            except (TypeError, ValueError):
                raise ValueError(f"{definition.bezeichnung} muss eine Zahl sein.")

    for schluessel, wert in werte.items():
        definition = DEFINITION_NACH_SCHLUESSEL[schluessel]
        if definition.geheim and (wert is None or wert == ""):
            continue
        eintrag = db.get(Einstellung, schluessel)
        if eintrag is None:
            db.add(Einstellung(Schluessel=schluessel, Wert=_als_text(definition, wert)))
        else:
            eintrag.Wert = _als_text(definition, wert)

    db.commit()
    cache_leeren()


def geheimnis_loeschen(db: Session, schluessel: str):
    definition = DEFINITION_NACH_SCHLUESSEL.get(schluessel)
    if definition is None or not definition.geheim:
        raise ValueError("Nur geheime Einstellungen können geleert werden.")
    eintrag = db.get(Einstellung, schluessel)
    if eintrag is not None:
        eintrag.Wert = None
        db.commit()
    cache_leeren()


def aus_umgebung_uebernehmen():
    """
    Übernimmt beim Start einmalig Werte aus alten Umgebungsvariablen in die Datenbank,
    damit bestehende Installationen nach dem Update unverändert weiterlaufen.
    Bereits gespeicherte Werte werden nie überschrieben.
    """
    db = SessionLocal()
    try:
        vorhanden = {e.Schluessel for e in db.query(Einstellung.Schluessel).all()}
        neu = 0
        for d in DEFINITIONEN:
            if d.schluessel in vorhanden:
                continue
            env_wert = (os.getenv(d.schluessel) or "").strip()
            if d.schluessel == "SMTP_MODUS" and not env_wert and os.getenv("SMTP_SERVER"):
                # Früher wurde immer über SSL versendet
                env_wert = "ssl"
            if not env_wert:
                continue
            db.add(Einstellung(Schluessel=d.schluessel, Wert=_als_text(d, env_wert)))
            neu += 1
        db.commit()
        if neu:
            logger.info("%s Einstellungen aus Umgebungsvariablen übernommen", neu)
    finally:
        db.close()
    cache_leeren()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    aus_umgebung_uebernehmen()
