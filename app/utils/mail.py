from collections import defaultdict
import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.schemas.saisonverleih import SaisonVerleihRead
from app.schemas.skiservice import AuftragSchema, SkiSchema
from app.services import einstellungen, mailvorlagen
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

    betreff, html = fertigMail(auftrag)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = auftrag.kunde.Email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    try:
        sendeMail(msg)
        return True
    except Exception:
        logger.exception("Fehler beim Senden der E-Mail")
        return False


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

    ende_am = verleih.Ende_Am.strftime("%d.%m.%Y") if verleih.Art == "tag" and verleih.Ende_Am else ""
    if art == "abholung":
        vorlage = "verleih_abholung"
    else:
        vorlage = "verleih_rueckgabe_tag" if ende_am else "verleih_rueckgabe_saison"

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

    betreff, html = verleihMail(verleih, art)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = verleih.Kunde.Email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    try:
        sendeMail(msg)
        return True
    except Exception:
        logger.exception("Fehler beim Senden der Verleih-Mail")
        return False

def sendeQuittungMail(email: str, nummer: str, pdf: bytes, dateiname: str) -> bool:
    """
    Versendet die Quittung als PDF-Anhang an eine Adresse.
    False, wenn der Versand fehlschlägt.
    """
    betreff, html = mailvorlagen.rendern("quittung", {**mailvorlagen.firma_werte(), "quittung_nummer": nummer})

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = email
    msg['Subject'] = betreff

    msg.attach(MIMEText(html, "html"))
    anhang = MIMEApplication(pdf, _subtype="pdf")
    anhang.add_header("Content-Disposition", "attachment", filename=dateiname)
    msg.attach(anhang)
    try:
        sendeMail(msg)
        return True
    except Exception:
        logger.exception("Fehler beim Senden der Quittungs-Mail an %s", email)
        return False
