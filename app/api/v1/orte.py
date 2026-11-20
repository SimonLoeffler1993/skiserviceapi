from fastapi import APIRouter, Depends, HTTPException
from app.core.zugriff import angemeldet, geraet_oder_angemeldet
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.deps import get_db
from app.schemas.ort import OrtOut
from app.crud import ort as crud_ort


router = APIRouter(
    prefix="/orte",
    tags=["orte"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test", dependencies=[Depends(angemeldet)])
async def test():
    return {"test": "test"}

@router.get("/getname", response_model=list[OrtOut], dependencies=[Depends(geraet_oder_angemeldet("terminal"))])
async def getName(plz: str, db: Session = Depends(get_db)):
    if not plz:
        raise HTTPException(status_code=400, detail="Plz is required")
    return crud_ort.get_orte(db, plz)