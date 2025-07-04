from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.deps import get_db
from app.schemas.kunde import SkiKundeOut, SkiKundeSpeichern
from app.crud import kunde as crud_kunde

router = APIRouter(
    prefix="/kunden",
    tags=["kunden"],
    responses={404: {"description": "Not found"}},
)

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

@router.get("/test")
async def test():
    return {"test": "test"}

@router.get("/suchen", response_model=list[SkiKundeOut])
async def search_kunde(vorname: str = None, nachname: str = None, db: Session = Depends(get_db)):
    if not vorname and not nachname:
        raise HTTPException(status_code=400, detail="Mindestens ein Name muss angegeben werden")
    return crud_kunde.search_kunde(db, vorname or "", nachname or "")

@router.get("/{kunde_id}", response_model= SkiKundeOut)
async def get_kunde(kunde_id: int, db: Session = Depends(get_db)):
    return crud_kunde.get_kunde(db, kunde_id)

@router.put("/{kunde_id}")
async def update_kunde(kunde_id: int, kunde: SkiKundeSpeichern, db: Session = Depends(get_db)):
    existing_kunde = crud_kunde.get_kunde(db, kunde_id)
    if not existing_kunde:
        raise HTTPException(status_code=404, detail="Kunde not found")
    return crud_kunde.update_kunde(db, kunde_id, kunde)

@router.post("/erfassen")
async def erfassen_kunde(kunde: SkiKundeSpeichern, db: Session = Depends(get_db)):
    return crud_kunde.erfassen_kunde(db, kunde)

# TODO Put Route für kunden aktualisieren


# @router.get("/{kunde_id}", response_model=SkiKundeOut)
# async def get_kunde(kunde_id: int, db: Session = Depends(get_db)):
#     return kunde.get_kunde(db, kunde_id)