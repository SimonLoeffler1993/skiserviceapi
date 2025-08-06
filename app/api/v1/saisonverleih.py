from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud import saisonverleih as crud_saisonverleih

router = APIRouter(
    prefix="/saisonverleih",
    tags=["saisonverleih"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Saisonverleih API is working!"}

# TODO Response Shema hinzufügen
@router.get("/preise")
async def get_saisonverleihpreise(db: Session = Depends(get_db)):
    """
    Zeigt alle Saisonverleihpreise an inklusieve der Gültigkeit und Historische.
    """
    preise = crud_saisonverleih.get_saisonverleihpreise(db)
    return {"preise": preise}