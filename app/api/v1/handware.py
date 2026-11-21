from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import handware as crud_handware
from app.db.deps import get_db
from app.schemas.handware import HandwareCreate, HandwareRead, HandwareUpdate

router = APIRouter(
    prefix="/handware",
    tags=["handware"],
    responses={404: {"description": "Not found"}},
)


def _handware_oder_404(handware):
    if handware is None:
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return handware


@router.get("/", response_model=list[HandwareRead])
def liste_handware(db: Session = Depends(get_db)):
    """Alle Handwarenartikel, sortiert nach Kategorie und Name."""
    return crud_handware.get_handware_liste(db)


@router.post("/", response_model=HandwareRead)
def lege_handware_an(daten: HandwareCreate, db: Session = Depends(get_db)):
    return crud_handware.lege_handware_an(db, daten)


@router.patch("/{handware_id}", response_model=HandwareRead)
def aendere_handware(handware_id: int, daten: HandwareUpdate, db: Session = Depends(get_db)):
    return _handware_oder_404(crud_handware.aendere_handware(db, handware_id, daten))


@router.delete("/{handware_id}")
def loesche_handware(handware_id: int, db: Session = Depends(get_db)):
    if not crud_handware.loesche_handware(db, handware_id):
        raise HTTPException(status_code=404, detail="Artikel nicht gefunden")
    return {"success": True}
