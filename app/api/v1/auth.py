from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.zugriff import Zugriff, benutzer_noetig, hole_zugriff, nur_geraetesitzung
from app.db.deps import get_db
from app.schemas.benutzer import (AnmeldeAntwort, AnmeldenAnfrage, AuthStatus, EigenePin, EigenesPasswort,
                                  EinrichtungAnfrage, GeraetPruefung, IchAntwort, IchBenutzer, Kachel,
                                  OidcEinloesen, OidcUrl, OidcVerknuepfen, PinAnmeldung, TicketAnfrage,
                                  TicketAntwort)
from app.services import anmeldung, oidc
from app.services.anmeldung import AnmeldeFehler

# Öffentlich bzw. je Route geschützt, siehe app/core/zugriff.py
router = APIRouter(prefix="/auth", tags=["auth"])


def _http(e: AnmeldeFehler) -> HTTPException:
    headers = {"X-Gesperrt-Bis": e.zusatz["gesperrt_bis"]} if "gesperrt_bis" in e.zusatz else None
    return HTTPException(status_code=e.status, detail=e.detail, headers=headers)


def _ausfuehren(funktion, *args, **kwargs):
    try:
        return funktion(*args, **kwargs)
    except AnmeldeFehler as e:
        raise _http(e)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status", response_model=AuthStatus)
def status(db: Session = Depends(get_db)):
    """Für Login-Seite und Weiterleitung: Einrichtung nötig? Pflicht an? OIDC-Button?"""
    return anmeldung.status(db)


@router.post("/einrichtung", response_model=AnmeldeAntwort)
def einrichtung(daten: EinrichtungAnfrage, db: Session = Depends(get_db)):
    """Legt den ersten Admin an und meldet das Gerät an. Nur solange es keinen Benutzer gibt."""
    return _ausfuehren(anmeldung.einrichten, db, daten.benutzername, daten.anzeigename, daten.passwort,
                       daten.email, daten.geraet_name, daten.geraet_art)


@router.post("/anmelden", response_model=AnmeldeAntwort)
def anmelden(daten: AnmeldenAnfrage, zugriff: Zugriff = Depends(hole_zugriff), db: Session = Depends(get_db)):
    """
    Benutzername + Passwort. Mit Bearer eines angemeldeten Geräts wird nur der Bediener gewechselt,
    sonst wird zusätzlich eine neue Gerätesitzung angelegt.
    """
    return _ausfuehren(anmeldung.anmelden, db, daten.benutzername, daten.passwort, zugriff,
                       daten.geraet_name, daten.geraet_art)


@router.get("/kacheln", response_model=list[Kachel])
def kacheln(_: Zugriff = Depends(nur_geraetesitzung), db: Session = Depends(get_db)):
    """Benutzer mit selbst gesetzter PIN für die Schnellwahl."""
    return anmeldung.kacheln(db)


@router.post("/pin", response_model=AnmeldeAntwort)
def pin(daten: PinAnmeldung, zugriff: Zugriff = Depends(nur_geraetesitzung), db: Session = Depends(get_db)):
    return _ausfuehren(anmeldung.pin_anmelden, db, daten.benutzer_id, daten.pin, zugriff)


@router.get("/oidc/start")
def oidc_start(ziel: str = Query(max_length=500)):
    """Leitet zum Anbieter weiter. Danach geht es zurück auf ziel?code=… bzw. ziel?fehler=…"""
    try:
        # Zuerst das Ziel: nie auf eine fremde Seite weiterleiten, auch nicht mit Fehler
        oidc.ziel_pruefen(ziel)
    except oidc.OidcFehler as e:
        raise HTTPException(status_code=400, detail=e.text)
    try:
        return RedirectResponse(oidc.start_url(ziel), status_code=302)
    except oidc.OidcFehler as e:
        return RedirectResponse(oidc.ziel_mit(ziel, {"fehler": e.code}), status_code=302)


@router.get("/oidc/callback")
def oidc_callback(code: str | None = None, state: str | None = None, error: str | None = None,
                  db: Session = Depends(get_db)):
    try:
        return RedirectResponse(oidc.callback(db, code, state, error), status_code=302)
    except oidc.OidcFehler as e:
        return HTMLResponse(f"<!doctype html><meta charset='utf-8'><title>Anmeldung</title>"
                            f"<p style='font-family:sans-serif'>{e.text}</p>", status_code=400)


@router.post("/oidc/einloesen", response_model=AnmeldeAntwort)
def oidc_einloesen(daten: OidcEinloesen, zugriff: Zugriff = Depends(hole_zugriff), db: Session = Depends(get_db)):
    """Tauscht den Einmalcode aus der Rückleitung gegen Sitzungen."""
    return _ausfuehren(anmeldung.oidc_einloesen, db, daten.code, zugriff, daten.geraet_name, daten.geraet_art)


@router.get("/ich", response_model=IchAntwort)
def ich(zugriff: Zugriff = Depends(hole_zugriff), db: Session = Depends(get_db)):
    """Aktueller Bediener und Gerät; beides None ohne Anmeldung."""
    return anmeldung.ich(db, zugriff)


@router.post("/bediener/abmelden")
def bediener_abmelden(zugriff: Zugriff = Depends(hole_zugriff), db: Session = Depends(get_db)):
    """Meldet nur den Bediener ab, das Gerät bleibt angemeldet."""
    anmeldung.bediener_abmelden(db, zugriff)
    return {"success": True}


@router.post("/abmelden")
def abmelden(zugriff: Zugriff = Depends(hole_zugriff), db: Session = Depends(get_db)):
    """Meldet das ganze Gerät ab."""
    anmeldung.geraet_abmelden(db, zugriff)
    return {"success": True}


@router.put("/ich/passwort", response_model=IchBenutzer)
def eigenes_passwort(daten: EigenesPasswort, zugriff: Zugriff = Depends(benutzer_noetig), db: Session = Depends(get_db)):
    return _ausfuehren(anmeldung.passwort_aendern, db, zugriff, daten.alt, daten.neu)


@router.put("/ich/pin", response_model=IchBenutzer)
def eigene_pin(daten: EigenePin, zugriff: Zugriff = Depends(benutzer_noetig), db: Session = Depends(get_db)):
    """Eigene PIN setzen oder ändern (freiwillig), bestätigt mit dem Passwort."""
    return _ausfuehren(anmeldung.pin_setzen, db, zugriff, daten.passwort, daten.pin)


@router.delete("/ich/pin", response_model=IchBenutzer)
def eigene_pin_loeschen(zugriff: Zugriff = Depends(benutzer_noetig), db: Session = Depends(get_db)):
    return _ausfuehren(anmeldung.pin_loeschen, db, zugriff)


@router.post("/ich/oidc/verknuepfen", response_model=OidcUrl)
def eigenes_oidc_verknuepfen(daten: OidcVerknuepfen, zugriff: Zugriff = Depends(benutzer_noetig)):
    """URL zum Anbieter, um das eigene Konto zu verknüpfen. Rückkehr mit ?verknuepft=1 bzw. ?fehler=…"""
    try:
        return {"url": oidc.start_url(daten.ziel, verknuepfen_benutzer_id=zugriff.benutzer.id)}
    except oidc.OidcFehler as e:
        raise HTTPException(status_code=400, detail=e.text)


@router.delete("/ich/oidc", response_model=IchBenutzer)
def eigenes_oidc_trennen(zugriff: Zugriff = Depends(benutzer_noetig), db: Session = Depends(get_db)):
    return _ausfuehren(anmeldung.oidc_trennen, db, zugriff)


@router.post("/ticket", response_model=TicketAntwort)
def ticket(daten: TicketAnfrage, zugriff: Zugriff = Depends(hole_zugriff)):
    """Kurzzeit-Ticket für WebSocket, EventSource oder PDF-Link: ?ticket=… an genau diesen Pfad hängen."""
    ticket_wert = _ausfuehren(anmeldung.ticket, zugriff, daten.pfad)
    return {"ticket": ticket_wert, "gueltig_sekunden": 120}


@router.get("/geraet", response_model=GeraetPruefung)
def geraet(zugriff: Zugriff = Depends(hole_zugriff)):
    """Prüft einen Geräteschlüssel (X-Geraete-Schluessel), z.B. für „API testen“ am Scanner."""
    if zugriff.schluessel is None:
        raise HTTPException(status_code=401, detail="geraeteschluessel_noetig")
    return {"name": zugriff.schluessel.name, "bereich": zugriff.schluessel.bereich}
