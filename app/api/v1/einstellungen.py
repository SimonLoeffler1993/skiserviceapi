from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.einstellungen import EinstellungRead, EinstellungenSpeichern, TestMail, TestErgebnis
from app.services import einstellungen
from app.utils.mail import sendeMail
from app.utils.skiEttiket import SkiEttiket
from app.utils.lexware import LexwareAPI

# TODO Auth: Die Einstellungen sind aktuell ohne Anmeldung erreichbar (nur internes Netz)
router = APIRouter(
    prefix="/einstellungen",
    tags=["einstellungen"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[EinstellungRead])
def get_einstellungen():
    """
    Alle Einstellungen. Passwörter werden nie zurückgegeben, nur ob sie gesetzt sind.
    """
    return einstellungen.alle_fuer_anzeige()


@router.put("/", response_model=list[EinstellungRead])
def speichere_einstellungen(daten: EinstellungenSpeichern, db: Session = Depends(get_db)):
    try:
        einstellungen.speichern(db, daten.werte)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return einstellungen.alle_fuer_anzeige()


@router.delete("/{schluessel}", response_model=list[EinstellungRead])
def loesche_geheimnis(schluessel: str, db: Session = Depends(get_db)):
    """
    Leert ein Passwort / einen API Key.
    """
    try:
        einstellungen.geheimnis_loeschen(db, schluessel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return einstellungen.alle_fuer_anzeige()


@router.post("/test/mail", response_model=TestErgebnis)
def teste_mail(daten: TestMail):
    msg = MIMEText("Diese Test-Mail wurde aus dem Skiservice Center gesendet.", "plain", "utf-8")
    msg["To"] = daten.empfaenger
    msg["Subject"] = "Skiservice Test-Mail"
    try:
        sendeMail(msg)
    except Exception as e:
        return {"success": False, "message": f"Mail konnte nicht gesendet werden: {e}"}
    return {"success": True, "message": f"Test-Mail an {daten.empfaenger} gesendet."}


@router.post("/test/drucker", response_model=TestErgebnis)
def teste_drucker():
    try:
        etikett = SkiEttiket()
        etikett.saisonFahererName("Test")
        if not etikett.drucken():
            return {"success": False, "message": f"Drucker {etikett.printerIdentifier} nicht erreichbar."}
    except Exception as e:
        return {"success": False, "message": f"Drucken fehlgeschlagen: {e}"}
    return {"success": True, "message": "Test-Etikett gedruckt."}


@router.post("/test/lexware", response_model=TestErgebnis)
def teste_lexware():
    if not einstellungen.hole("LEXWARE_APIKEY"):
        return {"success": False, "message": "Kein API Key hinterlegt."}
    try:
        profil = LexwareAPI().get_profil()
    except Exception as e:
        return {"success": False, "message": f"Verbindung fehlgeschlagen: {e}"}
    return {"success": True, "message": f"Verbunden mit {profil.get('companyName', 'Lexware Office')}."}
