from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.rechte import RECHTE
from app.core.zugriff import recht
from app.crud import rechte as crud
from app.db.deps import get_db
from app.schemas.benutzer import RechtInfo, RolleAendern, RolleAnlegen, RolleRead

router = APIRouter(
    prefix="/rollen",
    tags=["rollen"],
    dependencies=[Depends(recht("benutzer.verwalten"))],
    responses={404: {"description": "Not found"}},
)


def _fehler(e: Exception) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(e, LookupError) else 400, detail=str(e))


@router.get("/rechte", response_model=list[RechtInfo])
def rechte_katalog():
    """Alle Rechte, die einer Rolle gegeben werden können, in fester Reihenfolge nach Bereich."""
    return [{"recht": r, "bereich": bereich, "bezeichnung": text} for r, (bereich, text) in RECHTE.items()]


@router.get("/", response_model=list[RolleRead])
def liste(db: Session = Depends(get_db)):
    return [crud.rolle_read(db, r) for r in crud.rollen(db)]


@router.post("/", response_model=RolleRead)
def anlegen(daten: RolleAnlegen, db: Session = Depends(get_db)):
    try:
        return crud.rolle_read(db, crud.rolle_anlegen(db, daten.name, daten.beschreibung, daten.rechte))
    except ValueError as e:
        raise _fehler(e)


@router.patch("/{rolle_id}", response_model=RolleRead)
def aendern(rolle_id: int, daten: RolleAendern, db: Session = Depends(get_db)):
    try:
        return crud.rolle_read(db, crud.rolle_aendern(db, rolle_id, daten.model_dump(exclude_unset=True)))
    except (LookupError, ValueError) as e:
        raise _fehler(e)


@router.delete("/{rolle_id}")
def loeschen(rolle_id: int, db: Session = Depends(get_db)):
    try:
        crud.rolle_loeschen(db, rolle_id)
    except (LookupError, ValueError) as e:
        raise _fehler(e)
    return {"success": True}
