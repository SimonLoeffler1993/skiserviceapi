from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session



from app.db.deps import get_db
from app.schemas.materialski import EigenSkiRead
from app.schemas.materialski import SkiArtRead, VerleihSkiHerstellerRead
from app.crud import materialski as crud_materialski

router = APIRouter(
    prefix="/material/ski",
    tags=["Material","Ski"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Materialski API is working!"}

@router.get("/eigen", response_model=list[EigenSkiRead])
async def get_eigen_ski(skinr: str, db: Session = Depends(get_db)):
    """
    Gibt die EIgenen SKi anhander der SkiNr zurück. Es reicht eine Teil der SkiNr zu geben.
    Wenn keine Ski gefunden werden, wird eine leere Liste zurückgegeben.
    """
    return crud_materialski.get_eigen_ski(db,skinr)