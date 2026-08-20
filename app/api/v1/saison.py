from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.saison import SaisonErstellen, SaisonsNamen
from app.crud import saison as crud_saison

from app.db.deps import get_db

router = APIRouter(
    prefix="/saison",
    tags=["saison"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"test": "test"}

@router.get("/alle", response_model=list[SaisonsNamen])
async def get_all_saisons(db: Session = Depends(get_db)):
    return crud_saison.get_all_saisons(db)

@router.get("/aktuelle", response_model=SaisonsNamen)
async def get_aktuelle_saison(db: Session = Depends(get_db)):
    return crud_saison.get_AktuelleSaison(db)

@router.post("/erfassen", response_model=SaisonsNamen)
async def erfasse_saison(saison: SaisonErstellen, db: Session = Depends(get_db)):
    # TODO: #16 Auftrags und Saison Nummern reseten 
    return crud_saison.erfasse_saison(db, saison)