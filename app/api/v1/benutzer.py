from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.zugriff import Zugriff, recht
from app.crud import benutzer as crud
from app.db.deps import get_db
from app.schemas.benutzer import BenutzerAendern, BenutzerAnlegen, BenutzerRead, OidcUebernehmen, PasswortSetzen

router = APIRouter(
    prefix="/benutzer",
    tags=["benutzer"],
    dependencies=[Depends(recht("benutzer.verwalten"))],
    responses={404: {"description": "Not found"}},
)


def _ausfuehren(funktion, db, *args):
    try:
        return crud.benutzer_read(db, funktion(db, *args))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[BenutzerRead])
def liste(db: Session = Depends(get_db)):
    return [crud.benutzer_read(db, b) for b in crud.liste(db)]


@router.post("/", response_model=BenutzerRead)
def anlegen(daten: BenutzerAnlegen, db: Session = Depends(get_db)):
    """Neuer Benutzer mit Startpasswort; das Passwort muss bei der ersten Anmeldung geändert werden."""
    return _ausfuehren(crud.anlegen, db, daten)


@router.patch("/{benutzer_id}", response_model=BenutzerRead)
def aendern(benutzer_id: int, daten: BenutzerAendern, db: Session = Depends(get_db)):
    return _ausfuehren(crud.aendern, db, benutzer_id, daten)


@router.post("/{benutzer_id}/passwort", response_model=BenutzerRead)
def passwort_setzen(benutzer_id: int, daten: PasswortSetzen, db: Session = Depends(get_db)):
    return _ausfuehren(crud.passwort_setzen, db, benutzer_id, daten.passwort)


@router.delete("/{benutzer_id}/pin", response_model=BenutzerRead)
def pin_loeschen(benutzer_id: int, db: Session = Depends(get_db)):
    """Die PIN legt jeder selbst fest; ein Admin kann sie nur löschen."""
    return _ausfuehren(crud.pin_loeschen, db, benutzer_id)


@router.post("/{benutzer_id}/entsperren", response_model=BenutzerRead)
def entsperren(benutzer_id: int, db: Session = Depends(get_db)):
    return _ausfuehren(crud.entsperren, db, benutzer_id)


@router.delete("/{benutzer_id}/oidc", response_model=BenutzerRead)
def oidc_loesen(benutzer_id: int, db: Session = Depends(get_db)):
    return _ausfuehren(crud.oidc_loesen, db, benutzer_id)


@router.post("/{benutzer_id}/oidc-uebernehmen", response_model=BenutzerRead)
def oidc_uebernehmen(benutzer_id: int, daten: OidcUebernehmen, db: Session = Depends(get_db)):
    """Ordnet die OIDC-Anmeldung eines ausstehenden Benutzers einem vorhandenen zu."""
    return _ausfuehren(crud.oidc_uebernehmen, db, benutzer_id, daten.von_benutzer_id)


@router.delete("/{benutzer_id}")
def loeschen(benutzer_id: int, zugriff: Zugriff = Depends(recht("benutzer.verwalten")), db: Session = Depends(get_db)):
    try:
        crud.loeschen(db, benutzer_id, zugriff.benutzer.id if zugriff.benutzer else None)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"success": True}
