from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.saison import SaisonsNamen
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