from collections import defaultdict
import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.schemas.saisonverleih import SaisonVerleihRead
from app.schemas.skiservice import AuftragSchema, SkiSchema
from app.services import einstellungen, mailprotokoll, mailvorlagen
from app.utils.formate import eur

logger = logging.getLogger(__name__)

def skizusammenfassen(skis: list[SkiSchema]) -> dict:
    zusammenfassung = defaultdict(lambda: {"anzahl": 0, "service": None, "gesamtpreis": 0.0})
    for ski in skis:
        if ski is None:
            continue
        zusammenfassung[ski.service]["anzahl"] += 1
        zusammenfassung[ski.service]["service"] = ski.service
        zusammenfassung[ski.service]["gesamtpreis"] += float(ski.preis)
        if ski.bindung_check:
            zusammenfassung["Bindungscheck"]["anzahl"] += 1
            zusammenfassung["Bindungscheck"]["service"] = "Bindungscheck"
            zusammenfassung["Bindungscheck"]["gesamtpreis"] += float(ski.bindung_preis)
    
    return zusammenfassung

def sendeMail(msg: MIMEMultipart | MIMEText):
    """
    Versendet eine Mail je nach SMTP_MODUS über SSL, STARTTLS oder unverschlüsselt.
    Ist kein Benutzer hinterlegt, wird ohne Anmeldung versendet (z.B. Exchange Relay).
    """
    modus = einstellungen.hole("SMTP_MODUS")
    smtpServer = einstellungen.hole("SMTP_SERVER")
    smtpPort = einstellungen.hole("SMTP_PORT")
    smtpUser = einstellungen.hole("SMTP_USER")
    kontext = ssl.create_default_context()

    if not smtpServer:
        raise ValueError("Kein SMTP Server eingestellt.")
    if not msg['From']:
        msg['From'] = einstellungen.hole("EMAIL_FROM")

    if modus == "ssl":
        server = smtplib.SMTP_SSL(smtpServer, smtpPort, context=kontext, timeout=30)
    else:
        server = smtplib.SMTP(smtpServer, smtpPort, timeout=30)

    with server:
        if modus == "starttls":
            server.ehlo()
            server.starttls(context=kontext)
            server.ehlo()
        if smtpUser:
            server.login(smtpUser, einstellungen.hole("SMTP_PASSWORD"))
        server.send_message(msg)

def _sende_und_protokolliere(msg: MIMEMultipart, vorlage: str, html: str, **bezug) -> bool:
    """
    Versendet eine Kundenmail und hält sie mit dem Ergebnis im Mail-Protokoll fest.
    bezug: kunde_id, auftrag_id, verleih_id, quittung_id. Anhänge werden nicht gespeichert.
    """
    fehler = None
    try:
        sendeMail(msg)
    except Exception as e:
        logger.exception("Fehler beim Senden der Mail \"%s\" an %s", vorlage, msg['To'])
        fehler = mailprotokoll.fehler_text(e)
    mailprotokoll.protokolliere(vorlage, msg['To'], msg['Subject'], html, fehler, **bezug)
    return fehler is None

def _render_fehler(vorlage: str, empfaenger: str, fehler: Exception, **bezug) -> bool:
    """Die Mail ließ sich schon nicht erstellen: als fehlgeschlagen ohne Inhalt festhalten."""
    logger.exception("Mail \"%s\" an %s konnte nicht erstellt werden", vorlage, empfaenger)
    mailprotokoll.protokolliere(vorlage, empfaenger, "", "", mailprotokoll.fehler_text(fehler), **bezug)
    return False

def _kunde_werte(kunde) -> dict[str, str]:
    vorname = (kunde.Vorname or "").strip() if kunde else ""
    nachname = (kunde.Nachname or "").strip() if kunde else ""
    return {
        "kunde_vorname": vorname,
        "kunde_nachname": nachname,
        "kunde_name": " ".join(teil for teil in (vorname, nachname) if teil),
    }

def fertigMail(auftrag: AuftragSchema) -> tuple[str, str]:
    """Betreff und HTML der Fertig-Mail aus der Vorlage "skiservice_fertig"."""
    leistungen = list(skizusammenfassen(auftrag.skis).values())
    gesamt = sum(leistung["gesamtpreis"] for leistung in leistungen)
    werte = {**_kunde_werte(auftrag.kunde), **mailvorlagen.firma_werte(), "gesamtpreis": eur(gesamt)}
    preistabelle = {"leistungen": leistungen, "gesamt": gesamt, "mwst_satz": mailvorlagen.mwst_satz()}
    return mailvorlagen.rendern("skiservice_fertig", werte, {"preistabelle": preistabelle})

def fertigMailHtml(auftrag: AuftragSchema) -> str:
    return fertigMail(auftrag)[1]

def sendeFertigMail(auftrag: AuftragSchema):
    if not auftrag.kunde or not auftrag.kunde.Email:
        logger.info("Keine E-Mail Adresse beim Kunden hinterlegt, keine Fertig-Mail versendet.")
        return False

    bezug = {"kunde_id": auftrag.kunden_id, "auftrag_id": auftrag.id}
    try:
        betreff, html = fertigMail(auftrag)
    except Exception as e:
        return _render_fehler("skiservice_fertig", auftrag.kunde.Email, e, **bezug)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = auftrag.kunde.Email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    return _sende_und_protokolliere(msg, "skiservice_fertig", html, **bezug)


def _verleih_ende(verleih: SaisonVerleihRead) -> str:
    """Rückgabedatum eines Tagesverleihs, sonst leer."""
    return verleih.Ende_Am.strftime("%d.%m.%Y") if verleih.Art == "tag" and verleih.Ende_Am else ""

def verleih_vorlage(verleih: SaisonVerleihRead, art: str) -> str:
    """Schlüssel der Vorlage für die Abhol- ("abholung") bzw. Rückgabe-Mail ("rueckgabe")."""
    if art == "abholung":
        return "verleih_abholung"
    return "verleih_rueckgabe_tag" if _verleih_ende(verleih) else "verleih_rueckgabe_saison"

def verleihMail(verleih: SaisonVerleihRead, art: str) -> tuple[str, str]:
    """
    Betreff und HTML der Abhol- ("abholung") bzw. Rückgabe-Mail ("rueckgabe") eines Verleihs, mit dem Material.
    Die Rückgabe hat zwei Vorlagen: Tagesverleih mit Enddatum und Saisonverleih.
    """
    material = []
    for nr, m in enumerate(verleih.Material, start=1):
        teile = []
        if m.Ski:
            teile.append(f"Ski {m.Ski.Modell.Hersteller.Name} {m.Ski.Modell.Modell}, {m.Ski.Laenge} cm")
        if m.Schuh:
            teile.append(f"Schuh {m.Schuh.Modell.Hersteller.Name} {m.Schuh.Modell.Modell}, Gr. {f'{m.Schuh.Groese:g}'.replace('.', ',')}")
        if m.Stock:
            teile.append("Stöcke")
        # Zeilen nur mit Preis (ohne Material) weglassen
        if teile:
            material.append({"name": (m.SkiFahrerName or "").strip() or f"Ausrüstung #{nr}", "teile": teile})

    ende_am = _verleih_ende(verleih)
    vorlage = verleih_vorlage(verleih, art)

    werte = {
        **_kunde_werte(verleih.Kunde),
        **mailvorlagen.firma_werte(),
        "verleih_name": verleih.Name or "",
        "rueckgabe_datum": ende_am,
    }
    return mailvorlagen.rendern(vorlage, werte, {"materialliste": {"verleih_name": verleih.Name, "material": material}})

def verleihMailHtml(verleih: SaisonVerleihRead, art: str) -> str:
    return verleihMail(verleih, art)[1]

def sendeVerleihMail(verleih: SaisonVerleihRead, art: str) -> bool:
    """
    Versendet die Abhol- ("abholung") bzw. Rückgabe-Mail ("rueckgabe") eines Verleihs.
    False, wenn keine E-Mail hinterlegt ist oder der Versand fehlschlägt.
    """
    if not verleih.Kunde or not verleih.Kunde.Email:
        logger.info("Keine E-Mail Adresse beim Kunden hinterlegt, keine Verleih-Mail versendet.")
        return False

    vorlage = verleih_vorlage(verleih, art)
    bezug = {"kunde_id": verleih.Kunde_ID, "verleih_id": verleih.ID}
    try:
        betreff, html = verleihMail(verleih, art)
    except Exception as e:
        return _render_fehler(vorlage, verleih.Kunde.Email, e, **bezug)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = verleih.Kunde.Email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    return _sende_und_protokolliere(msg, vorlage, html, **bezug)

def sendeQuittungMail(email: str, nummer: str, pdf: bytes, dateiname: str, quittung_id: int) -> bool:
    """
    Versendet die Quittung als PDF-Anhang an eine Adresse.
    False, wenn der Versand fehlschlägt.
    Im Mail-Protokoll steht nur der Verweis auf die Quittung, das PDF wird nicht noch einmal gespeichert.
    """
    try:
        betreff, html = mailvorlagen.rendern("quittung", {**mailvorlagen.firma_werte(), "quittung_nummer": nummer})
    except Exception as e:
        return _render_fehler("quittung", email, e, quittung_id=quittung_id)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    anhang = MIMEApplication(pdf, _subtype="pdf")
    anhang.add_header("Content-Disposition", "attachment", filename=dateiname)
    msg.attach(anhang)
    return _sende_und_protokolliere(msg, "quittung", html, quittung_id=quittung_id)
