"""
Mail-Vorlagen aus der Datenbank.

Der aktuelle Stand jeder Vorlage (Betreff + Inhalt) steht in der Tabelle "mail_vorlagen" und wird im
Skiservice Center unter Verwalten -> Vorlagen bearbeitet. Die Originaltexte liegen unveränderlich in
app/templates/mail_original/<schluessel>.html und in DEFINITIONEN (Betreff), darauf kann jederzeit
zurückgesetzt werden.

Format des Inhalts: HTML-Fragment, wie es der Editor im Center erzeugt.
  Platzhalter: <span data-platzhalter="kunde_name"></span>   (im Betreff: {{kunde_name}})
  Bausteine:   <div data-baustein="preistabelle"></div>      (fertige Blöcke, Aussehen in templates/mail_bausteine/)
Die Platzhalter werden hier selbst ersetzt, der Text der Anwender läuft nie durch Jinja.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import nh3
from fastapi.templating import Jinja2Templates
from markupsafe import escape
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.einstellung import Einstellung
from app.models.mailvorlage import MailVorlage
from app.services import einstellungen
from app.utils.formate import datum, eur

logger = logging.getLogger(__name__)

_ORIGINAL_ORDNER = Path("app/templates/mail_original")

_bausteine_templates = Jinja2Templates(directory="app/templates/mail_bausteine")
_bausteine_templates.env.filters["datum"] = datum
_bausteine_templates.env.filters["eur"] = eur


@dataclass(frozen=True)
class Platzhalter:
    schluessel: str
    bezeichnung: str
    beispiel: str


@dataclass(frozen=True)
class Baustein:
    schluessel: str
    bezeichnung: str
    beschreibung: str
    beispiel: dict


PLATZHALTER = {p.schluessel: p for p in [
    Platzhalter("kunde_name", "Kundenname", "Max Mustermann"),
    Platzhalter("kunde_vorname", "Vorname", "Max"),
    Platzhalter("kunde_nachname", "Nachname", "Mustermann"),
    Platzhalter("gesamtpreis", "Gesamtpreis", "64,00 €"),
    Platzhalter("verleih_name", "Name des Verleihs", "Familie Mustermann"),
    Platzhalter("rueckgabe_datum", "Rückgabedatum", "21.02.2027"),
    Platzhalter("quittung_nummer", "Quittungsnummer", "26/27Q12"),
    Platzhalter("firma_name", "Firmenname", "Skiservice Muster"),
    Platzhalter("firma_telefon", "Telefon der Firma", "01234 56789"),
    Platzhalter("firmenzeile", "Firmenname mit Telefon", "Skiservice Muster · Tel. 01234 56789"),
]}

BAUSTEINE = {b.schluessel: b for b in [
    Baustein("preistabelle", "Preistabelle", "Tabelle mit allen Leistungen des Auftrags und den Preisen.", {
        "leistungen": [
            {"service": "Großer Service", "anzahl": 2, "gesamtpreis": 54.0},
            {"service": "Bindungscheck", "anzahl": 1, "gesamtpreis": 10.0},
        ],
        "gesamt": 64.0,
    }),
    Baustein("materialliste", "Materialliste", "Tabelle mit der Ausrüstung des Verleihs je Skifahrer.", {
        "verleih_name": "Familie Mustermann",
        "material": [
            {"name": "Max", "teile": ["Ski Atomic Redster, 165 cm", "Schuh Salomon S/Pro, Gr. 27,5", "Stöcke"]},
            {"name": "Lena", "teile": ["Ski Head Supershape, 140 cm", "Schuh Nordica Speedmachine, Gr. 24"]},
        ],
    }),
]}

_KUNDE = ("kunde_name", "kunde_vorname", "kunde_nachname")
_FIRMA = ("firmenzeile", "firma_name", "firma_telefon")


@dataclass(frozen=True)
class VorlageDefinition:
    schluessel: str
    bezeichnung: str
    beschreibung: str
    original_betreff: str
    platzhalter: tuple[str, ...]
    bausteine: tuple[str, ...] = ()

    @property
    def original_inhalt(self) -> str:
        return _lade_original(self.schluessel)


DEFINITIONEN = [
    VorlageDefinition(
        "skiservice_fertig", "Skiservice fertig",
        "Geht an den Kunden, wenn alle Ski eines Skiservice-Auftrags fertig sind.",
        "Dein Skiservice ist fertig!",
        _KUNDE + ("gesamtpreis",) + _FIRMA, ("preistabelle",)),
    VorlageDefinition(
        "verleih_abholung", "Verleih abholbereit",
        "Geht an den Kunden, wenn die Leihausrüstung vorbereitet und jede Bindung geprüft ist.",
        "Deine Leihski sind abholbereit!",
        _KUNDE + ("verleih_name",) + _FIRMA, ("materialliste",)),
    VorlageDefinition(
        "verleih_rueckgabe_tag", "Rückgabe Tagesverleih",
        "Erinnerung an die Rückgabe bei einem Tagesverleih mit Enddatum.",
        "Bitte denk an die Rückgabe deiner Leihski",
        _KUNDE + ("verleih_name", "rueckgabe_datum") + _FIRMA, ("materialliste",)),
    VorlageDefinition(
        "verleih_rueckgabe_saison", "Rückgabe Saisonverleih",
        "Erinnerung an die Rückgabe am Ende der Saison (Verleih ohne festes Enddatum).",
        "Bitte denk an die Rückgabe deiner Leihski",
        _KUNDE + ("verleih_name",) + _FIRMA, ("materialliste",)),
    VorlageDefinition(
        "quittung", "Quittung",
        "Begleittext zur Quittung, die als PDF angehängt wird.",
        "Deine Quittung {{quittung_nummer}}",
        ("quittung_nummer",) + _FIRMA),
]

DEFINITION_NACH_SCHLUESSEL = {d.schluessel: d for d in DEFINITIONEN}

# Frühere Einstellungen -> Vorlagen, werden beim ersten Start übernommen und dann gelöscht
_ALTE_BETREFFS = {
    "MAIL_BETREFF_FERTIG": ["skiservice_fertig"],
    "MAIL_BETREFF_VERLEIH_ABHOLUNG": ["verleih_abholung"],
    "MAIL_BETREFF_VERLEIH_RUECKGABE": ["verleih_rueckgabe_tag", "verleih_rueckgabe_saison"],
    "MAIL_BETREFF_QUITTUNG": ["quittung"],
}
_ALTE_SCHLUESSEL = list(_ALTE_BETREFFS) + ["MAIL_FERTIG_INHALT"]

# Was der Editor erzeugen darf, alles andere wird beim Speichern entfernt
_TAGS = {"p", "br", "strong", "em", "u", "s", "h2", "h3", "ul", "ol", "li", "a", "span", "div"}
_ATTRIBUTE = {"a": {"href"}, "span": {"data-platzhalter"}, "div": {"data-baustein"}}
_URL_SCHEMATA = {"http", "https", "mailto", "tel"}

# Mail-Programme kennen keine Stylesheets, deshalb bekommt jedes Element sein Aussehen direkt
_STYLES = {
    "p": "margin: 0 0 16px; font-size: 14px; color: #444; line-height: 1.6;",
    "h2": "margin: 0 0 20px; font-size: 16px; font-weight: bold; color: #111;",
    "h3": "margin: 0 0 12px; font-size: 14px; font-weight: bold; color: #111;",
    "ul": "margin: 0 0 16px; padding-left: 24px; font-size: 14px; color: #444; line-height: 1.6;",
    "ol": "margin: 0 0 16px; padding-left: 24px; font-size: 14px; color: #444; line-height: 1.6;",
    "a": "color: #1a56db;",
}

_PLATZHALTER_HTML = re.compile(r'<span data-platzhalter="([^"]*)">[^<]*</span>')
_BAUSTEIN_HTML = re.compile(r'<div data-baustein="([^"]*)">[^<]*</div>')
_PLATZHALTER_TEXT = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")

_RAHMEN = """<!DOCTYPE html>
<html lang="de">

<head>
    <meta charset="UTF-8">
</head>

<body>
{inhalt}
</body>

</html>
"""


def _kompakt(html: str) -> str:
    """Entfernt die Zeilenumbrüche zwischen den Blöcken, so wie der Editor den Inhalt liefert."""
    return re.sub(r">\s+<", "><", html.strip())


_originale: dict[str, str] = {}


def _lade_original(schluessel: str) -> str:
    if schluessel not in _originale:
        text = (_ORIGINAL_ORDNER / f"{schluessel}.html").read_text(encoding="utf-8")
        _originale[schluessel] = _kompakt(text)
    return _originale[schluessel]


def _definition(schluessel: str) -> VorlageDefinition:
    definition = DEFINITION_NACH_SCHLUESSEL.get(schluessel)
    if definition is None:
        raise KeyError(f"Unbekannte Vorlage: {schluessel}")
    return definition


# ---------- Prüfen und Bereinigen ----------

def bereinige_betreff(definition: VorlageDefinition, betreff: str) -> str:
    betreff = " ".join((betreff or "").split())
    if not betreff:
        raise ValueError("Der Betreff darf nicht leer sein.")
    if len(betreff) > 255:
        raise ValueError("Der Betreff ist zu lang (höchstens 255 Zeichen).")
    for name in _PLATZHALTER_TEXT.findall(betreff):
        if name not in definition.platzhalter:
            raise ValueError(f"Der Platzhalter „{name}“ ist in dieser Vorlage nicht verfügbar.")
    return betreff


def bereinige_inhalt(definition: VorlageDefinition, inhalt: str) -> str:
    """Lässt nur übrig, was der Editor erzeugen darf, und prüft Platzhalter und Bausteine."""
    sauber = nh3.clean(inhalt or "", tags=_TAGS, attributes=_ATTRIBUTE, url_schemes=_URL_SCHEMATA, link_rel=None)
    sauber = _kompakt(sauber)
    # Beschriftungen des Editors in den Marken weglassen, damit der Vergleich mit dem Original stimmt
    sauber = _PLATZHALTER_HTML.sub(lambda m: f'<span data-platzhalter="{m.group(1)}"></span>', sauber)
    sauber = _BAUSTEIN_HTML.sub(lambda m: f'<div data-baustein="{m.group(1)}"></div>', sauber)
    if not re.sub(r"<[^>]*>", "", sauber).strip() and "data-" not in sauber:
        raise ValueError("Der Text der Vorlage darf nicht leer sein.")
    for name in re.findall(r'data-platzhalter="([^"]*)"', sauber):
        if name not in definition.platzhalter:
            raise ValueError(f"Der Platzhalter „{name}“ ist in dieser Vorlage nicht verfügbar.")
    for name in re.findall(r'data-baustein="([^"]*)"', sauber):
        if name not in definition.bausteine:
            raise ValueError(f"Der Baustein „{name}“ ist in dieser Vorlage nicht verfügbar.")
    return sauber


# ---------- Rendern ----------

def _rendere_baustein(schluessel: str, daten: dict) -> str:
    return _bausteine_templates.get_template(f"{schluessel}.html").render(**daten)


def _mit_styles(html: str) -> str:
    # Absätze in Listenpunkten (so liefert sie der Editor) ohne eigenen Abstand
    html = html.replace("<li><p>", '<li><p style="margin: 0;">')
    html = html.replace("<p></p>", "<p>&nbsp;</p>")
    return re.sub(r"<(p|h2|h3|ul|ol|a)(?=[ >])(?![^>]*\bstyle=)",
                  lambda m: f'<{m.group(1)} style="{_STYLES[m.group(1)]}"', html)


def rendere_text(definition: VorlageDefinition, betreff: str, inhalt: str,
                 werte: dict[str, str], bausteine: dict[str, dict]) -> tuple[str, str]:
    """Setzt Werte und Bausteine in Betreff und (bereits bereinigten) Inhalt ein -> (Betreff, HTML der Mail)."""
    def wert(name: str) -> str:
        return str(werte.get(name) or "")

    html = _mit_styles(inhalt)
    html = _BAUSTEIN_HTML.sub(
        lambda m: _rendere_baustein(m.group(1), bausteine.get(m.group(1), {})) if m.group(1) in definition.bausteine else "",
        html)
    html = _PLATZHALTER_HTML.sub(lambda m: str(escape(wert(m.group(1)))), html)
    fertiger_betreff = " ".join(_PLATZHALTER_TEXT.sub(lambda m: wert(m.group(1)), betreff).split())
    return fertiger_betreff, _RAHMEN.format(inhalt=html)


def _aktuell(db: Session, definition: VorlageDefinition) -> tuple[str, str]:
    zeile = db.get(MailVorlage, definition.schluessel)
    if zeile is None:
        return definition.original_betreff, definition.original_inhalt
    return zeile.Betreff, zeile.Inhalt


def rendern(schluessel: str, werte: dict[str, str], bausteine: dict[str, dict] | None = None) -> tuple[str, str]:
    """
    Betreff und HTML einer Mail aus der gespeicherten Vorlage.
    Ist die Datenbank nicht erreichbar oder die Vorlage kaputt, wird der Originaltext verwendet.
    """
    definition = _definition(schluessel)
    try:
        with SessionLocal() as db:
            betreff, inhalt = _aktuell(db, definition)
        return rendere_text(definition, betreff, inhalt, werte, bausteine or {})
    except Exception:
        logger.exception("Vorlage %s konnte nicht geladen werden, Original wird verwendet", schluessel)
        return rendere_text(definition, definition.original_betreff, definition.original_inhalt, werte, bausteine or {})


def firma_werte() -> dict[str, str]:
    name = einstellungen.hole("FIRMA_NAME") or ""
    telefon = einstellungen.hole("FIRMA_TELEFON") or ""
    return {
        "firma_name": name,
        "firma_telefon": telefon,
        "firmenzeile": f"{name} · Tel. {telefon}" if telefon else name,
    }


def mwst_satz():
    """MwSt. Satz für die Preistabelle, None bei Kleinunternehmern."""
    if einstellungen.hole("FIRMA_KLEINUNTERNEHMER"):
        return None
    return einstellungen.hole("FIRMA_MWST_SATZ")


def beispiel(definition: VorlageDefinition) -> tuple[dict[str, str], dict[str, dict]]:
    """Beispieldaten für Vorschau und Test-Mail. Die Firmendaten sind die echten, wenn sie eingetragen sind."""
    werte = {name: PLATZHALTER[name].beispiel for name in definition.platzhalter}
    firma = firma_werte()
    if firma["firma_name"]:
        werte.update({name: text for name, text in firma.items() if name in werte})
    bausteine = {name: dict(BAUSTEINE[name].beispiel) for name in definition.bausteine}
    if "preistabelle" in bausteine:
        bausteine["preistabelle"]["mwst_satz"] = mwst_satz()
    return werte, bausteine


def vorschau(schluessel: str, betreff: str, inhalt: str) -> tuple[str, str]:
    """Rendert einen (noch nicht gespeicherten) Stand mit Beispieldaten."""
    definition = _definition(schluessel)
    werte, bausteine = beispiel(definition)
    return rendere_text(definition, bereinige_betreff(definition, betreff),
                        bereinige_inhalt(definition, inhalt), werte, bausteine)


# ---------- Anzeigen und Speichern ----------

def _fuer_anzeige(definition: VorlageDefinition, zeile: MailVorlage | None) -> dict:
    betreff = zeile.Betreff if zeile else definition.original_betreff
    inhalt = zeile.Inhalt if zeile else definition.original_inhalt
    return {
        "schluessel": definition.schluessel,
        "bezeichnung": definition.bezeichnung,
        "beschreibung": definition.beschreibung,
        "betreff": betreff,
        "inhalt": inhalt,
        "original_betreff": definition.original_betreff,
        "original_inhalt": definition.original_inhalt,
        "geaendert": betreff != definition.original_betreff or inhalt != definition.original_inhalt,
        "geaendert_am": zeile.Geaendert_Am if zeile else None,
        "platzhalter": [
            {"schluessel": p.schluessel, "bezeichnung": p.bezeichnung, "beispiel": p.beispiel}
            for p in (PLATZHALTER[name] for name in definition.platzhalter)
        ],
        "bausteine": [
            {"schluessel": b.schluessel, "bezeichnung": b.bezeichnung, "beschreibung": b.beschreibung}
            for b in (BAUSTEINE[name] for name in definition.bausteine)
        ],
    }


def alle_fuer_anzeige(db: Session) -> list[dict]:
    zeilen = {z.Schluessel: z for z in db.query(MailVorlage).all()}
    return [_fuer_anzeige(d, zeilen.get(d.schluessel)) for d in DEFINITIONEN]


def _schreibe(db: Session, definition: VorlageDefinition, betreff: str, inhalt: str, geaendert_am: datetime | None):
    zeile = db.get(MailVorlage, definition.schluessel)
    if zeile is None:
        zeile = MailVorlage(Schluessel=definition.schluessel)
        db.add(zeile)
    zeile.Betreff = betreff
    zeile.Inhalt = inhalt
    zeile.Geaendert_Am = geaendert_am
    return zeile


def speichern(db: Session, schluessel: str, betreff: str, inhalt: str) -> dict:
    definition = _definition(schluessel)
    zeile = _schreibe(db, definition, bereinige_betreff(definition, betreff),
                      bereinige_inhalt(definition, inhalt), datetime.now())
    db.commit()
    return _fuer_anzeige(definition, zeile)


def zuruecksetzen(db: Session, schluessel: str) -> dict:
    """Setzt Betreff und Inhalt wieder auf den Originaltext."""
    definition = _definition(schluessel)
    zeile = _schreibe(db, definition, definition.original_betreff, definition.original_inhalt, None)
    db.commit()
    return _fuer_anzeige(definition, zeile)


def beim_start(db: Session):
    """
    Legt fehlende Vorlagen mit dem Originaltext an. Beim ersten Mal werden die früheren
    Einstellungen (Betreffs, Fertig-Mail mit oder ohne Preise) übernommen und danach gelöscht.
    """
    alt = {e.Schluessel: (e.Wert or "").strip()
           for e in db.query(Einstellung).filter(Einstellung.Schluessel.in_(_ALTE_SCHLUESSEL)).all()}
    betreffs = {}
    for alter_schluessel, vorlagen in _ALTE_BETREFFS.items():
        if alt.get(alter_schluessel):
            # Geschweifte Klammern wären sonst Platzhalter
            text = alt[alter_schluessel].replace("{", "(").replace("}", ")")
            for vorlage in vorlagen:
                betreffs[vorlage] = f"{text} {{{{quittung_nummer}}}}" if vorlage == "quittung" else text

    vorhanden = {z.Schluessel for z in db.query(MailVorlage.Schluessel).all()}
    for definition in DEFINITIONEN:
        if definition.schluessel in vorhanden:
            continue
        betreff = betreffs.get(definition.schluessel, definition.original_betreff)[:255]
        inhalt = definition.original_inhalt
        if definition.schluessel == "skiservice_fertig" and alt.get("MAIL_FERTIG_INHALT") == "fertig":
            # Bisher ohne Preisauflistung eingestellt
            inhalt = inhalt.replace('<div data-baustein="preistabelle"></div>', "<p>Bis bald!</p>")
        geaendert = betreff != definition.original_betreff or inhalt != definition.original_inhalt
        _schreibe(db, definition, betreff, inhalt, datetime.now() if geaendert else None)

    if alt:
        db.query(Einstellung).filter(Einstellung.Schluessel.in_(_ALTE_SCHLUESSEL)).delete(synchronize_session=False)
    db.commit()
    if alt:
        einstellungen.cache_leeren()
