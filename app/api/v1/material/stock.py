from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud import materialstock as crud_materialstock
from app.schemas.materialstock import SkiStockOut, SkiStockIn
from app.db.deps import get_db

router = APIRouter(
    prefix="/material/stock",
    tags=["Material","Stock"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Materialstock API is working!"}

@router.post("", response_model=SkiStockOut)
async def create_skistock( Bezeichnung: SkiStockIn, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Skistock.
    """
    return crud_materialstock.create_skistock(db, Bezeichnung.Bezeichnung)

@router.get("/skistocke", response_model=list[SkiStockOut])
async def get_skistocke( db: Session = Depends(get_db)):
    """
    Gibt alle Skistocke zurück.
    """
    return crud_materialstock.get_alle_skistocke(db)