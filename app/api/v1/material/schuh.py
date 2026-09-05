from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.materialschuh import EigenSchuhBase ,EigenSchuhRead, VerleihSchuhHerstellerBase, VerleihSchuhHerstellerRead, VerleihSchuhModellBase, VerleihSchuhModellRead
from app.crud import materialschuh as crud_materialschuh

router = APIRouter(
    prefix="/material/schuh",
    tags=["Material","Schuh"],
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

@router.post("/eigen", response_model=EigenSchuhRead)
async def create_eigen_schuhe(schuh: EigenSchuhBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Eigenen Schuh.
    """
    return crud_materialschuh.create_eigen_schuhe(db, schuh)

@router.get("/eigen/liste", response_model=list[EigenSchuhRead])
async def get_eigen_schuhe_liste(db: Session = Depends(get_db)):
    """
    Gibt alle Eigenen Schuhe zurueck.
    Wenn keine Schuhe gefunden werden, wird eine leere Liste zurueckgegeben.
    """
    return crud_materialschuh.get_eigen_schuhe_liste(db)

@router.post("/hersteller", response_model=VerleihSchuhHerstellerRead)
async def create_hersteller(schuh: VerleihSchuhHerstellerBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Schuhhersteller.
    """
    return crud_materialschuh.create_hersteller(db, schuh)

@router.get("/hersteller", response_model=list[VerleihSchuhHerstellerRead])
async def get_hersteller(db: Session = Depends(get_db)):
    """
    Gibt alle Schuhhersteller zurück.
    """
    return crud_materialschuh.get_hersteller(db)

@router.post("/modell", response_model=VerleihSchuhModellRead)
async def create_modell(modell: VerleihSchuhModellBase, db: Session = Depends(get_db)):
    """
    Erstelle das Skischuhmodell.
    """
    return crud_materialschuh.create_modell(db, modell)

@router.get("/modelle", response_model=list[VerleihSchuhModellRead])
async def get_modelle(db: Session = Depends(get_db)):
    """
    Gibt alle Schuhmodelle zurück
    """
    return crud_materialschuh.get_modelle(db)