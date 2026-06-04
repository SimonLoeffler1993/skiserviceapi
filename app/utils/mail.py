from collections import defaultdict
from fastapi.templating import Jinja2Templates
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.schemas.skiservice import AuftragSchema, SkiSchema
from app.core.config import EmailSettings

templates = Jinja2Templates(directory="app/templates")

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

def sendeFertigMail(auftrag: AuftragSchema):
    ski_zusammenfassung = skizusammenfassen(auftrag.skis)

    total_preis = sum(service["gesamtpreis"] for service in ski_zusammenfassung.values())

    html = templates.get_template("fertig_skiservice_mail.html").render(auftrag=auftrag, skiservices=ski_zusammenfassung, total_preis=total_preis)

    msg = MIMEMultipart()
    msg['From'] = EmailSettings.emailFrom
    msg['To'] = auftrag.kunde.Email
    msg['Subject'] = "Dein Skiservice ist ferttig!"

    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP_SSL(EmailSettings.smtpServer, EmailSettings.smtpPort) as server:
            server.login(EmailSettings.smtpUser, EmailSettings.smtpPassword)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"Fehler beim Senden der E-Mail: {e}")
        return False

