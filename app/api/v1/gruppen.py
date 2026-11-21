from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.zugriff import recht
from app.crud import rechte as crud
from app.db.deps import get_db
from app.schemas.benutzer import GruppeAendern, GruppeAnlegen, GruppeRead

router = APIRouter(
    prefix="/gruppen",
    tags=["gruppen"],
    dependencies=[Depends(recht("benutzer.verwalten"))],
    responses={404: {"description": "Not found"}},
)


def _fehler(e: Exception) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(e, LookupError) else 400, detail=str(e))


@router.get("/", response_model=list[GruppeRead])
def liste(db: Session = Depends(get_db)):
    return [crud.gruppe_read(db, g) for g in crud.gruppen(db)]


@router.post("/", response_model=GruppeRead)
def anlegen(daten: GruppeAnlegen, db: Session = Depends(get_db)):
    try:
        return crud.gruppe_read(db, crud.gruppe_anlegen(db, daten.name, daten.beschreibung, daten.oidc_gruppe, daten.rollen_ids))
    except ValueError as e:
        raise _fehler(e)


@router.patch("/{gruppe_id}", response_model=GruppeRead)
def aendern(gruppe_id: int, daten: GruppeAendern, db: Session = Depends(get_db)):
    """oidc_gruppe: Name der Gruppe beim OIDC-Anbieter; leer löst die Zuordnung."""
    try:
        return crud.gruppe_read(db, crud.gruppe_aendern(db, gruppe_id, daten.model_dump(exclude_unset=True)))
    except (LookupError, ValueError) as e:
        raise _fehler(e)


@router.delete("/{gruppe_id}")
def loeschen(gruppe_id: int, db: Session = Depends(get_db)):
    try:
        crud.gruppe_loeschen(db, gruppe_id)
    except (LookupError, ValueError) as e:
        raise _fehler(e)
    return {"success": True}
