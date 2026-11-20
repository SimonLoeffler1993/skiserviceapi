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

# zahl = ganze Zahl, dezimal = Zahl mit Nachkommastellen (z.B. Euro)
EinstellungTyp = Literal["text", "zahl", "dezimal", "bool", "auswahl", "passwort"]


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
    "bank": "Bankverbindung",
    "drucker": "Etikettendrucker",
    "mail": "E-Mail",
    "lexware": "Lexware Office",
    "verleih": "Verleih",
    "scanner": "Hardware-Scanner",
    "anwendung": "Anwendung",
    "anmeldung": "Benutzer & Anmeldung",
    "oidc": "Anmeldung mit OIDC",
}

# Anbieter für die Anmeldung mit OIDC, siehe app/services/oidc.py
OIDC_ANBIETER_OPTIONEN = ["authentik", "microsoft", "google", "keycloak", "generisch"]

# Startstatus eines neuen Verleihs, getrennt für Saison- und Tagesverleih
VERLEIH_STARTSTATUS_OPTIONEN = ["vorbereitung", "vorbereitet", "unterwegs"]
VERLEIH_STARTSTATUS_TEXT = (
    "In Vorbereitung: Material wird noch hergerichtet. Vorbereitet: Material ist fertig, "
    "wird automatisch gesetzt, sobald alle Bindungen geprüft sind. Unterwegs: gilt als heute abgeholt."
)

# Längster Countdown am Hardware-Scanner in Sekunden
SCANNER_COUNTDOWN_MAX = 60

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

    # Bankverbindung (Quittung, GiroCode bei Überweisung)
    EinstellungDefinition("BANK_KONTOINHABER", "bank", "Kontoinhaber",
                          beschreibung="Leer = Firmenname. Höchstens 70 Zeichen (GiroCode)."),
    EinstellungDefinition("BANK_IBAN", "bank", "IBAN",
                          beschreibung="Steht auf der Quittung, bei Überweisung zusätzlich als QR-Code (GiroCode)."),
    EinstellungDefinition("BANK_BIC", "bank", "BIC", beschreibung="Optional."),
    EinstellungDefinition("BANK_NAME", "bank", "Bank", beschreibung="z.B. Sparkasse Bodensee"),

    # Etikettendrucker
    EinstellungDefinition("LABELPRINTERIDENT", "drucker", "Drucker Adresse", standard="tcp://192.168.188.159",
                          beschreibung="z.B. tcp://192.168.1.50"),
    EinstellungDefinition("LABELPRINTERMODEL", "drucker", "Druckermodell", standard="QL-820NWB"),
    EinstellungDefinition("LABELSIZE", "drucker", "Etikettenbreite", standard="62"),
    EinstellungDefinition("LABELFARBE", "drucker", "Etikettenrolle", typ="auswahl", standard="schwarz",
                          optionen=["schwarz", "rotschwarz"],
                          beschreibung="Rot/Schwarz (z.B. DK-22251) gibt es nur in 62 mm. Gedruckt wird in Schwarz."),
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
    EinstellungDefinition("SKISERVICE_FERTIG_MAIL_WANN", "mail", "Skiservice Fertig-Mail senden", typ="auswahl",
                          standard="service", optionen=["service", "service_bindung"],
                          beschreibung="Service: sobald alle Ski fertig sind, offene Bindungsprüfungen egal. "
                                       "Service + Bindung: erst wenn zusätzlich alle beauftragten Bindungschecks geprüft sind."),

    # Lexware
    EinstellungDefinition("LEXWARE_BASEURL", "lexware", "API Adresse", standard="https://api.lexware.io"),
    EinstellungDefinition("LEXWARE_APIKEY", "lexware", "API Key", typ="passwort"),
    EinstellungDefinition("LEXWARE_SYNC", "lexware", "Quittungen synchronisieren", typ="bool", standard=False,
                          beschreibung="Bezahlte Quittungen automatisch an Lexware übertragen."),
    EinstellungDefinition("LEXWARE_MODUS", "lexware", "Übertragung", typ="auswahl", standard="pdf",
                          optionen=["pdf", "rechnung"],
                          beschreibung="PDF: eigene Quittung erstellen und als Beleg mit PDF hochladen. "
                                       "Rechnung: Rechnung direkt in Lexware anlegen, in der Anwendung nur externe Quittung."),

    # Verleih: Auswertung je Materialstück (Material-Details im Center)
    EinstellungDefinition("VERLEIH_ANTEIL_SKI_PROZENT", "verleih", "Anteil Ski in %", typ="zahl", standard=50,
                          beschreibung="Stehen Ski und Schuh in einer Verleihzeile, bekommt der Ski diesen Anteil am Preis, "
                                       "der Schuh den Rest. Ohne Schuh bzw. ohne Ski zählt der ganze Preis. Stöcke zählen nicht."),
    EinstellungDefinition("VERLEIH_SKI_SERVICE_ABZUG", "verleih", "Abzug je Service am Leihski in €", typ="dezimal", standard=0.0,
                          beschreibung="Wird beim Eintragen eines Service am Leihski vorgeschlagen und vom Erwirtschafteten abgezogen. "
                                       "Bereits eingetragene Services ändern sich nicht."),

    # Hardware-Scanner: Countdown im Center, bevor ein Scan gespeichert wird
    EinstellungDefinition("SCANNER_COUNTDOWN_FERTIG", "scanner", "Countdown Fertigstellen in Sekunden", typ="zahl", standard=10,
                          beschreibung="Zeit zum Abbrechen, bevor ein gescannter Ski fertig gestellt wird. "
                                       "0 = sofort ohne Countdown, höchstens 60."),
    EinstellungDefinition("SCANNER_COUNTDOWN_BINDUNG", "scanner", "Countdown Bindung geprüft in Sekunden", typ="zahl", standard=10,
                          beschreibung="Zeit zum Abbrechen, bevor eine gescannte Bindung (Skiservice und Verleih) als geprüft gespeichert wird. "
                                       "0 = sofort ohne Countdown, höchstens 60."),

    # Anwendung
    EinstellungDefinition("HOST", "anwendung", "Öffentliche Adresse", standard="https://ms-skiservice.de",
                          beschreibung="Basis für die QR-Codes auf den Skiservice Etiketten."),
    EinstellungDefinition("KUERZEL_SAISONVERLEIH", "anwendung", "Kürzel Saisonverleih Nummer", standard="SV",
                          beschreibung="Ergibt z.B. 25/26SV12"),
    EinstellungDefinition("KUERZEL_TAGESVERLEIH", "anwendung", "Kürzel Tagesverleih Nummer", standard="TV",
                          beschreibung="Ergibt z.B. 25/26TV3"),
    EinstellungDefinition("KUERZEL_SKISERVICE", "anwendung", "Kürzel Skiservice Nummer", standard="S",
                          beschreibung="Ergibt z.B. 25/26S12"),
    EinstellungDefinition("VERLEIH_STARTSTATUS_SAISON", "anwendung", "Status nach dem Anlegen eines Saisonverleihs",
                          typ="auswahl", standard="vorbereitung", optionen=VERLEIH_STARTSTATUS_OPTIONEN,
                          beschreibung=VERLEIH_STARTSTATUS_TEXT),
    EinstellungDefinition("VERLEIH_STARTSTATUS_TAG", "anwendung", "Status nach dem Anlegen eines Tagesverleihs",
                          typ="auswahl", standard="vorbereitung", optionen=VERLEIH_STARTSTATUS_OPTIONEN,
                          beschreibung=VERLEIH_STARTSTATUS_TEXT),
    EinstellungDefinition("KUERZEL_QUITTUNG", "anwendung", "Kürzel Quittungsnummer", standard="Q",
                          beschreibung="Ergibt z.B. 25/26Q12"),
    EinstellungDefinition("KUNDEN_LETZTE_ANZAHL", "anwendung", "Anzahl letzte Kunden", typ="zahl", standard=5,
                          beschreibung="So viele zuletzt angelegte Kunden werden beim Anlegen von Skiservice und Verleih zur Auswahl angeboten."),

    # Benutzer & Anmeldung
    EinstellungDefinition("ANMELDUNG_ERZWINGEN", "anmeldung", "Anmeldung erzwingen", typ="bool", standard=False,
                          beschreibung="Aus: Center und Kasse funktionieren auch ohne Anmeldung (Übergang). "
                                       "Erst einschalten, wenn alle Geräte angemeldet sind und Terminal und Scanner einen Geräteschlüssel haben."),
    EinstellungDefinition("GERAETESCHLUESSEL_ERZWINGEN", "anmeldung", "Geräteschlüssel erzwingen", typ="bool", standard=False,
                          beschreibung="Aus: Hardware-Scanner und Kundenterminal funktionieren auch ohne Geräteschlüssel. "
                                       "Erst einschalten, wenn unter Verwalten → Hardware-Scanner kein Scanner mehr „ohne Schlüssel“ steht."),
    EinstellungDefinition("BEDIENER_TIMEOUT_MINUTEN", "anmeldung", "Bediener abmelden nach Minuten ohne Aktivität", typ="zahl", standard=10,
                          beschreibung="Danach erscheint wieder die Bedienerauswahl. 0 = nie. Pro Gerät unter Verwalten → Geräte änderbar."),
    EinstellungDefinition("GERAETESITZUNG_TAGE", "anmeldung", "Gerät bleibt angemeldet (Tage)", typ="zahl", standard=180,
                          beschreibung="Gilt ab der letzten Nutzung."),
    EinstellungDefinition("PIN_ANMELDUNG_ERLAUBT", "anmeldung", "Schnellwahl mit PIN erlauben", typ="bool", standard=True,
                          beschreibung="Jeder Benutzer kann sich unter „Mein Konto“ eine PIN festlegen und erscheint dann als Kachel in der Bedienerauswahl."),
    EinstellungDefinition("PIN_MIN_STELLEN", "anmeldung", "PIN mindestens Stellen", typ="zahl", standard=4,
                          beschreibung="4 bis 8 Ziffern."),
    EinstellungDefinition("PASSWORT_MIN_LAENGE", "anmeldung", "Passwort mindestens Zeichen", typ="zahl", standard=8),
    EinstellungDefinition("MAX_FEHLVERSUCHE", "anmeldung", "Sperre nach Fehlversuchen", typ="zahl", standard=5,
                          beschreibung="Falsches Passwort oder falsche PIN, zusammen gezählt."),
    EinstellungDefinition("SPERRE_MINUTEN", "anmeldung", "Sperre in Minuten", typ="zahl", standard=5),
    EinstellungDefinition("ERLAUBTE_URSPRUENGE", "anmeldung", "Adressen von Center, Kasse und Kundenterminal",
                          beschreibung="Mit Komma getrennt, z.B. https://center.example.de,https://kasse.example.de,https://terminal.example.de. "
                                       "Nur diese Seiten dürfen die API aus dem Browser aufrufen (auch das Kundenterminal für die Live-Verbindung) "
                                       "und sind als Rücksprung nach der OIDC-Anmeldung erlaubt. Leer = alle Seiten erlaubt, OIDC-Anmeldung nicht möglich."),

    # Anmeldung mit OIDC (ein Anbieter)
    EinstellungDefinition("OIDC_AKTIV", "oidc", "Anmeldung mit OIDC", typ="bool", standard=False),
    EinstellungDefinition("OIDC_ANBIETER", "oidc", "Anbieter", typ="auswahl", standard="authentik", optionen=OIDC_ANBIETER_OPTIONEN,
                          beschreibung="Bestimmt, wie der Issuer gebildet und der Benutzer erkannt wird."),
    EinstellungDefinition("OIDC_ISSUER", "oidc", "Issuer",
                          beschreibung="Authentik: https://<host>/application/o/<slug>/ · Keycloak: https://<host>/realms/<realm> · "
                                       "Generisch: Issuer des Anbieters. Bei Microsoft und Google leer lassen."),
    EinstellungDefinition("OIDC_MANDANT", "oidc", "Microsoft: Mandant (Tenant-ID)",
                          beschreibung="Verzeichnis-ID (Mandant) aus Entra ID. „organizations“ erlaubt Konten aller Firmen-Mandanten. Nur für Microsoft."),
    EinstellungDefinition("OIDC_ERLAUBTE_MANDANTEN", "oidc", "Microsoft: erlaubte Mandanten",
                          beschreibung="Nur bei Mandant „organizations“: Tenant-IDs mit Komma getrennt. Leer = alle."),
    EinstellungDefinition("OIDC_CLIENT_ID", "oidc", "Client-ID"),
    EinstellungDefinition("OIDC_CLIENT_SECRET", "oidc", "Client-Secret", typ="passwort"),
    EinstellungDefinition("OIDC_SCOPES", "oidc", "Scopes", standard="openid profile email"),
    EinstellungDefinition("OIDC_BUTTON_TEXT", "oidc", "Text auf dem Button",
                          beschreibung="Leer = „Mit <Anbieter> anmelden“."),
    EinstellungDefinition("OIDC_AUTO_FREIGABE", "oidc", "Neue Benutzer automatisch freigeben", typ="bool", standard=False,
                          beschreibung="Aus: Wer sich zum ersten Mal anmeldet, wartet auf die Freigabe durch einen Admin. "
                                       "An: wird sofort als Mitarbeiter freigegeben. Nur einschalten, wenn beim Anbieter ausschließlich eigene Mitarbeiter Zugang haben."),
    EinstellungDefinition("OIDC_API_ADRESSE", "oidc", "Öffentliche Adresse der API",
                          beschreibung="So erreicht der Browser die API, z.B. https://api.example.de. "
                                       "Daraus entsteht die Redirect-URI, die beim Anbieter eingetragen wird."),
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
    if definition.typ == "dezimal":
        try:
            return _dezimal(wert)
        except ValueError:
            return definition.standard
    if definition.typ == "bool":
        return wert.strip().lower() in ("true", "1", "ja")
    return wert


def _dezimal(wert: Any) -> float:
    """Zahl mit Nachkommastellen, auch mit Dezimalkomma. Wirft ValueError bei ungültiger Eingabe."""
    if isinstance(wert, bool):
        raise ValueError("keine Zahl")
    try:
        zahl = float(str(wert).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("keine Zahl")
    if zahl != zahl or zahl in (float("inf"), float("-inf")):
        raise ValueError("keine Zahl")
    return zahl


def _als_text(definition: EinstellungDefinition, wert: Any) -> str | None:
    if wert is None:
        return None
    if definition.typ == "bool":
        return "true" if wert in (True, "true", "1", 1) else "false"
    if definition.typ == "dezimal" and wert != "":
        return str(_dezimal(wert))
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


def iban_gueltig(iban: str) -> bool:
    """Prüfsumme nach ISO 13616 (Mod 97)."""
    iban = iban.replace(" ", "").upper()
    if not (15 <= len(iban) <= 34) or not iban[:2].isalpha() or not iban[2:4].isdigit() or not iban.isalnum():
        return False
    umgestellt = iban[4:] + iban[:4]
    zahl = "".join(str(int(zeichen, 36)) for zeichen in umgestellt)
    return int(zahl) % 97 == 1


def speichern(db: Session, werte: dict[str, Any]):
    """
    Speichert die übergebenen Einstellungen.
    Unbekannte Schlüssel werden abgelehnt. Leere Passwörter bedeuten "unverändert".
    """
    unbekannt = [s for s in werte if s not in DEFINITION_NACH_SCHLUESSEL]
    if unbekannt:
        raise ValueError(f"Unbekannte Einstellungen: {', '.join(unbekannt)}")

    werte = dict(werte)
    # Bankdaten ohne Leerzeichen und in Großbuchstaben speichern
    for schluessel in ("BANK_IBAN", "BANK_BIC"):
        if isinstance(werte.get(schluessel), str):
            werte[schluessel] = werte[schluessel].replace(" ", "").upper()
    if werte.get("BANK_IBAN") and not iban_gueltig(werte["BANK_IBAN"]):
        raise ValueError("Die IBAN ist ungültig.")
    if werte.get("BANK_BIC") and len(werte["BANK_BIC"]) not in (8, 11):
        raise ValueError("Die BIC muss 8 oder 11 Zeichen lang sein.")
    if isinstance(werte.get("BANK_KONTOINHABER"), str) and len(werte["BANK_KONTOINHABER"].strip()) > 70:
        raise ValueError("Der Kontoinhaber darf höchstens 70 Zeichen lang sein.")

    # Erst alles prüfen, dann schreiben
    for schluessel, wert in werte.items():
        definition = DEFINITION_NACH_SCHLUESSEL[schluessel]
        if definition.typ == "auswahl" and wert not in definition.optionen:
            raise ValueError(f"Ungültiger Wert für {definition.bezeichnung}: {wert}")
        if definition.typ == "zahl" and wert not in (None, ""):
            try:
                int(wert)
            except (TypeError, ValueError):
                raise ValueError(f"{definition.bezeichnung} muss eine ganze Zahl sein.")
        if definition.typ == "dezimal" and wert not in (None, ""):
            try:
                zahl = _dezimal(wert)
            except ValueError:
                raise ValueError(f"{definition.bezeichnung} muss eine Zahl sein.")
            if zahl < 0:
                raise ValueError(f"{definition.bezeichnung} darf nicht negativ sein.")
    anteil = werte.get("VERLEIH_ANTEIL_SKI_PROZENT")
    if anteil not in (None, "") and not 0 <= int(anteil) <= 100:
        raise ValueError("Der Anteil Ski muss zwischen 0 und 100 % liegen.")
    _anmeldung_pruefen(werte)
    for schluessel in ("SCANNER_COUNTDOWN_FERTIG", "SCANNER_COUNTDOWN_BINDUNG"):
        sekunden = werte.get(schluessel)
        if sekunden not in (None, "") and not 0 <= int(sekunden) <= SCANNER_COUNTDOWN_MAX:
            raise ValueError(f"{DEFINITION_NACH_SCHLUESSEL[schluessel].bezeichnung}: 0 bis {SCANNER_COUNTDOWN_MAX} erlaubt.")

    # Spät importiert: ereignisse -> zugriff -> einstellungen
    from app.services import ereignisse
    for schluessel, wert in werte.items():
        definition = DEFINITION_NACH_SCHLUESSEL[schluessel]
        if definition.geheim and (wert is None or wert == ""):
            continue
        eintrag = db.get(Einstellung, schluessel)
        neu = _als_text(definition, wert)
        if (eintrag.Wert if eintrag else None) != neu:
            ereignisse.erfasse(db, "einstellung_geaendert", text=definition.bezeichnung,
                               daten={"schluessel": schluessel, "wert": "geändert" if definition.geheim else neu})
        if eintrag is None:
            db.add(Einstellung(Schluessel=schluessel, Wert=_als_text(definition, wert)))
        else:
            eintrag.Wert = _als_text(definition, wert)

    db.commit()
    cache_leeren()


def _zahl_im_bereich(werte: dict[str, Any], schluessel: str, minimum: int, maximum: int | None = None):
    wert = werte.get(schluessel)
    if wert in (None, ""):
        return
    zahl = int(wert)
    if zahl < minimum or (maximum is not None and zahl > maximum):
        bezeichnung = DEFINITION_NACH_SCHLUESSEL[schluessel].bezeichnung
        bereich = f"{minimum} bis {maximum}" if maximum is not None else f"mindestens {minimum}"
        raise ValueError(f"{bezeichnung}: {bereich} erlaubt.")


def urspruenge(text: str | None = None) -> list[str]:
    """ERLAUBTE_URSPRUENGE als Liste, ohne Schrägstrich am Ende."""
    if text is None:
        text = hole("ERLAUBTE_URSPRUENGE")
    return [u.strip().rstrip("/") for u in (text or "").split(",") if u.strip()]


def _anmeldung_pruefen(werte: dict[str, Any]):
    _zahl_im_bereich(werte, "BEDIENER_TIMEOUT_MINUTEN", 0, 24 * 60)
    _zahl_im_bereich(werte, "GERAETESITZUNG_TAGE", 1, 3650)
    _zahl_im_bereich(werte, "PIN_MIN_STELLEN", 4, 8)
    _zahl_im_bereich(werte, "PASSWORT_MIN_LAENGE", 6, 128)
    _zahl_im_bereich(werte, "MAX_FEHLVERSUCHE", 1, 100)
    _zahl_im_bereich(werte, "SPERRE_MINUTEN", 1, 24 * 60)
    if isinstance(werte.get("ERLAUBTE_URSPRUENGE"), str):
        for ursprung in urspruenge(werte["ERLAUBTE_URSPRUENGE"]):
            teile = ursprung.split("://", 1)
            if len(teile) != 2 or teile[0] not in ("http", "https") or not teile[1] or "/" in teile[1]:
                raise ValueError(f"Ungültige Adresse „{ursprung}“: erwartet z.B. https://center.example.de ohne Pfad.")
    for schluessel in ("OIDC_ISSUER", "OIDC_API_ADRESSE"):
        wert = werte.get(schluessel)
        if isinstance(wert, str) and wert.strip() and not wert.strip().startswith(("http://", "https://")):
            raise ValueError(f"{DEFINITION_NACH_SCHLUESSEL[schluessel].bezeichnung} muss mit http:// oder https:// beginnen.")


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
