from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.materialschuh import EigenSchuhRead
from app.crud import materialschuh as crud_materialschuh

router = APIRouter(
    prefix="/material/schuh",
    tags=["materialschuh"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Materialschuh API is working!"}

@router.get("/eigen", response_model=EigenSchuhRead)
async def get_eigen_schuhe(schuhnr: str, db: Session = Depends(get_db)):
    """
    Gibt alle Eigenen Schuhe zurück.
    Wenn keine Schuhe gefunden werden, wird eine leere Liste zurückgegeben.
    """
    # Hier müsste die Logik implementiert werden, um die eigenen Schuhe aus der Datenbank abzurufen.

    schuh = crud_materialschuh.get_eigen_schuhe(db, schuhnr)

    if schuh is None:
        raise HTTPException(status_code=404, detail="EigenSchuh nicht gefunden")
    return schuh