from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.zugriff import aktueller_benutzer
from app.db.deps import get_db
from app.models.benutzer import Benutzer
from app.schemas.einstellungen import EinstellungRead, EinstellungenSpeichern, TestMail, TestErgebnis
from app.services import einstellungen, oidc
from app.utils.mail import sendeMail
from app.utils.skiEttiket import SkiEttiket
from app.utils.lexware import LexwareAPI

# Nur Admin (in main.py eingebunden mit ADMIN)
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


def _anmeldepflicht_pruefen(db: Session, werte: dict) -> None:
    """
    Anmeldung erzwingen nur, wenn sich danach noch jemand anmelden kann: der Aufrufer ist selbst ein
    angemeldeter Admin und es gibt einen aktiven Admin mit Passwort (Notzugang ohne OIDC).
    """
    if werte.get("ANMELDUNG_ERZWINGEN") not in (True, "true", "1", 1) or einstellungen.hole("ANMELDUNG_ERZWINGEN"):
        return
    benutzer = aktueller_benutzer()
    if benutzer is None or not benutzer.ist_admin:
        raise HTTPException(status_code=409, detail="Anmeldung erzwingen geht nur, wenn du selbst als Admin angemeldet bist.")
    tragend = (db.query(Benutzer.ID)
               .filter(Benutzer.Rolle == "admin", Benutzer.Aktiv.is_(True), Benutzer.Freigabe_Ausstehend.is_(False),
                       Benutzer.Passwort_Hash.is_not(None))
               .first())
    if tragend is None:
        raise HTTPException(status_code=409, detail="Es gibt keinen aktiven Admin mit Passwort.")


@router.put("/", response_model=list[EinstellungRead])
def speichere_einstellungen(daten: EinstellungenSpeichern, db: Session = Depends(get_db)):
    _anmeldepflicht_pruefen(db, daten.werte)
    try:
        einstellungen.speichern(db, daten.werte)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if any(s.startswith("OIDC_") for s in daten.werte):
        oidc.cache_leeren()
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


@router.post("/test/oidc", response_model=TestErgebnis)
def teste_oidc():
    """Ruft die Konfiguration des eingestellten OIDC-Anbieters ab."""
    try:
        info = oidc.testen()
    except oidc.OidcFehler as e:
        return {"success": False, "message": e.text}
    return {"success": True, "message": f"Verbunden mit {info['anbieter']} ({info['issuer']}).", "data": info}
