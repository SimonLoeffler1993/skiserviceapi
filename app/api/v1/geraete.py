from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.zugriff import Zugriff, recht
from app.crud import geraete as crud
from app.db.deps import get_db
from app.schemas.benutzer import (GeraeteschluesselAendern, GeraeteschluesselAnlegen, GeraeteschluesselErzeugt,
                                  GeraeteschluesselRead, GeraetesitzungAendern, GeraetesitzungRead)

router = APIRouter(
    prefix="/geraete",
    tags=["geraete"],
    dependencies=[Depends(recht("geraete.verwalten"))],
    responses={404: {"description": "Not found"}},
)


def _fehler(e: Exception) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(e, LookupError) else 400, detail=str(e))


@router.get("/schluessel", response_model=list[GeraeteschluesselRead])
def schluessel_liste(db: Session = Depends(get_db)):
    return [crud.schluessel_read(s) for s in crud.schluessel_liste(db)]


@router.post("/schluessel", response_model=GeraeteschluesselErzeugt)
def schluessel_anlegen(daten: GeraeteschluesselAnlegen, zugriff: Zugriff = Depends(recht("geraete.verwalten")),
                       db: Session = Depends(get_db)):
    """Der Schlüssel steht nur in dieser Antwort im Klartext."""
    try:
        return crud.schluessel_anlegen(db, daten, zugriff.benutzer.id if zugriff.benutzer else None)
    except ValueError as e:
        raise _fehler(e)


@router.patch("/schluessel/{schluessel_id}", response_model=GeraeteschluesselRead)
def schluessel_aendern(schluessel_id: int, daten: GeraeteschluesselAendern, db: Session = Depends(get_db)):
    try:
        return crud.schluessel_read(crud.schluessel_aendern(db, schluessel_id, daten))
    except (LookupError, ValueError) as e:
        raise _fehler(e)


@router.delete("/schluessel/{schluessel_id}")
def schluessel_loeschen(schluessel_id: int, db: Session = Depends(get_db)):
    try:
        crud.schluessel_loeschen(db, schluessel_id)
    except LookupError as e:
        raise _fehler(e)
    return {"success": True}


@router.get("/sitzungen", response_model=list[GeraetesitzungRead])
def sitzungen(db: Session = Depends(get_db)):
    return crud.sitzungen(db)


@router.patch("/sitzungen/{sitzung_id}")
def sitzung_aendern(sitzung_id: int, daten: GeraetesitzungAendern, db: Session = Depends(get_db)):
    try:
        crud.sitzung_aendern(db, sitzung_id, daten)
    except LookupError as e:
        raise _fehler(e)
    return {"success": True}


@router.delete("/sitzungen/{sitzung_id}")
def sitzung_abmelden(sitzung_id: int, db: Session = Depends(get_db)):
    """Meldet das Gerät ab; beim nächsten Aufruf landet es auf der Anmeldeseite."""
    try:
        crud.sitzung_abmelden(db, sitzung_id)
    except LookupError as e:
        raise _fehler(e)
    return {"success": True}
