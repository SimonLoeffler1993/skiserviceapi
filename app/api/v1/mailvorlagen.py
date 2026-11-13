from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.einstellungen import TestMail, TestErgebnis
from app.schemas.mailvorlagen import MailVorlageRead, MailVorlageSpeichern, MailVorlageVorschau
from app.services import mailvorlagen
from app.utils.mail import sendeMail

# TODO Auth: Die Vorlagen sind aktuell ohne Anmeldung erreichbar (nur internes Netz)
router = APIRouter(
    prefix="/mailvorlagen",
    tags=["mailvorlagen"],
    responses={404: {"description": "Not found"}},
)


def _pruefe_schluessel(schluessel: str):
    if schluessel not in mailvorlagen.DEFINITION_NACH_SCHLUESSEL:
        raise HTTPException(status_code=404, detail="Vorlage nicht gefunden")


@router.get("/", response_model=list[MailVorlageRead])
def get_mailvorlagen(db: Session = Depends(get_db)):
    """
    Alle Mail-Vorlagen mit aktuellem Stand, Originaltext und den verfügbaren Platzhaltern und Bausteinen.
    """
    return mailvorlagen.alle_fuer_anzeige(db)


@router.put("/{schluessel}", response_model=MailVorlageRead)
def speichere_mailvorlage(schluessel: str, daten: MailVorlageSpeichern, db: Session = Depends(get_db)):
    _pruefe_schluessel(schluessel)
    try:
        return mailvorlagen.speichern(db, schluessel, daten.betreff, daten.inhalt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{schluessel}/zuruecksetzen", response_model=MailVorlageRead)
def setze_mailvorlage_zurueck(schluessel: str, db: Session = Depends(get_db)):
    """
    Setzt die Vorlage auf den Originaltext zurück.
    """
    _pruefe_schluessel(schluessel)
    return mailvorlagen.zuruecksetzen(db, schluessel)


@router.post("/{schluessel}/vorschau", response_model=MailVorlageVorschau)
def vorschau_mailvorlage(schluessel: str, daten: MailVorlageSpeichern):
    """
    Rendert den übergebenen (noch nicht gespeicherten) Stand mit Beispieldaten.
    """
    _pruefe_schluessel(schluessel)
    try:
        betreff, html = mailvorlagen.vorschau(schluessel, daten.betreff, daten.inhalt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"betreff": betreff, "html": html}


@router.post("/{schluessel}/test", response_model=TestErgebnis)
def teste_mailvorlage(schluessel: str, daten: TestMail):
    """
    Sendet die gespeicherte Vorlage mit Beispieldaten an die angegebene Adresse.
    """
    _pruefe_schluessel(schluessel)
    definition = mailvorlagen.DEFINITION_NACH_SCHLUESSEL[schluessel]
    werte, bausteine = mailvorlagen.beispiel(definition)
    betreff, html = mailvorlagen.rendern(schluessel, werte, bausteine)
    msg = MIMEMultipart()
    msg["To"] = daten.empfaenger
    msg["Subject"] = betreff
    msg.attach(MIMEText(html, "html"))
    try:
        sendeMail(msg)
    except Exception as e:
        return {"success": False, "message": f"Mail konnte nicht gesendet werden: {e}"}
    return {"success": True, "message": f"Test-Mail an {daten.empfaenger} gesendet."}
