from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session



from app.db.deps import get_db
from app.schemas.materialski import EigenSkiRead, EigenSkiBase
from app.schemas.materialski import SkiArtRead, VerleihSkiHerstellerRead, VerleihSkiHerstellerBase, VerleihSkiModellBase, VerleihSkiModellRead
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

@router.get("/hersteller", response_model=list[VerleihSkiHerstellerRead])
def get_hersteller(db: Session = Depends(get_db)):
    """
    Gibt alle Skihersteller zurück.
    """
    return crud_materialski.get_hersteller(db)

@router.post("/hersteller", response_model=VerleihSkiHerstellerRead)
def create_hersteller(hersteller: VerleihSkiHerstellerBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Skihersteller.
    """
    hersteller = hersteller.Name
    return crud_materialski.create_hersteller(db, hersteller)

@router.get("/art", response_model=list[SkiArtRead])
def get_skiart(db: Session = Depends(get_db)):
    """
    Gibt alle Skiarten zurück.
    """
    return crud_materialski.get_skiart(db)

# @router.post("/art", response_model=SkiArtRead)
# def create_skiart(skiart: SkiArtRead, db: Session = Depends(get_db)):
#     """
#     Erstellt eine neue Skiart.
#     """
#     skiart_name = skiart.Name
#     return crud_materialski.create_skiart(db, skiart_name)

@router.post("/modell", response_model=VerleihSkiModellRead)
def create_ski_modell(modell: VerleihSkiModellBase, db: Session = Depends(get_db)):
    """
    Erstellt ein neues Skimodell.
    """
    modell = modell
    return crud_materialski.create_ski_modell(db, modell)

@router.get("/modell", response_model=list[VerleihSkiModellRead])
def get_ski_modell(db: Session = Depends(get_db)):
    """
    Gibt alle Skimodelle zurück.
    """
    return crud_materialski.get_ski_modell(db)

@router.post("/anlegen", response_model=EigenSkiRead)
def create_eigen_ski(ski: EigenSkiBase, db: Session = Depends(get_db)):
    """
    Legt ein neuen Eigenes Ski Material an.
    """
    return crud_materialski.create_eigen_ski(db, ski)