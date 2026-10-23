from collections import defaultdict
from fastapi.templating import Jinja2Templates
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.schemas.skiservice import AuftragSchema, SkiSchema
from app.services import einstellungen

templates = Jinja2Templates(directory="app/templates")

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

def fertigMailHtml(auftrag: AuftragSchema) -> str:
    """HTML der Fertig-Mail, je nach Einstellung mit oder ohne Preisauflistung."""
    mit_preisen = einstellungen.hole("MAIL_FERTIG_INHALT") == "preise"
    ski_zusammenfassung = skizusammenfassen(auftrag.skis) if mit_preisen else {}
    total_preis = sum(service["gesamtpreis"] for service in ski_zusammenfassung.values())

    return templates.get_template("fertig_skiservice_mail.html").render(
        auftrag=auftrag, skiservices=ski_zusammenfassung, total_preis=total_preis, mit_preisen=mit_preisen)

def sendeFertigMail(auftrag: AuftragSchema):
    if not auftrag.kunde or not auftrag.kunde.Email:
        logger.info("Keine E-Mail Adresse beim Kunden hinterlegt, keine Fertig-Mail versendet.")
        return False

    html = fertigMailHtml(auftrag)

    msg = MIMEMultipart()
    msg['From'] = einstellungen.hole("EMAIL_FROM")
    msg['To'] = auftrag.kunde.Email
    msg['Subject'] = einstellungen.hole("MAIL_BETREFF_FERTIG")

    msg.attach(MIMEText(html, "html"))
    try:
        sendeMail(msg)
        return True
    except Exception:
        logger.exception("Fehler beim Senden der E-Mail")
        return False
