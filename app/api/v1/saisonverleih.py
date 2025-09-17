from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.saisonverleih import SaisonVerleihRead

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

@router.post("/erstllen")
async def erstelle_saisonverleih():
    """
    Erstellt einen neuen Saisonverleih.
    """
    return {"message": "Saisonverleih erstellt!"}

@router.get("/{saisonverleih_id}" , response_model=SaisonVerleihRead)
async def get_saisonverleih(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Holt einen Saisonverleih anhand der ID.
    """
    saisonverleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    return saisonverleih