from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.crud import materialstock as crud_materialstock
from app.crud import materialverwendung
from app.crud.materialverwendung import MaterialKonflikt, MaterialUngueltig
from app.schemas.materialstock import SkiStockOut, SkiStockIn
from app.schemas.materialverwendung import Ausmustern, LoeschErgebnis, VerleihVerwendung
from app.db.deps import get_db

router = APIRouter(
    prefix="/material/stock",
    tags=["Material","Stock"],
    responses={404: {"description": "Not found"}},
)


def _stock_oder_404(db: Session, stock_id: int):
    stock = crud_materialstock.get_skistock(db, stock_id)
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock nicht gefunden")
    return stock


@router.get("/test")
async def test():
    return {"message": "Materialstock API is working!"}

@router.post("", response_model=SkiStockOut)
def create_skistock( Bezeichnung: SkiStockIn, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Skistock.
    """
    return crud_materialstock.create_skistock(db, Bezeichnung.Bezeichnung)

@router.get("/skistocke", response_model=list[SkiStockOut])
def get_skistocke(
        mit_ausgemustert: bool = Query(default=False, description="Auch ausgemusterte Stöcke zurückgeben"),
        db: Session = Depends(get_db),
    ):
    """
    Gibt alle Skistöcke zurück, standardmäßig ohne ausgemusterte.
    """
    return crud_materialstock.get_alle_skistocke(db, mit_ausgemustert)

@router.patch("/{stock_id}", response_model=SkiStockOut)
def aendere_skistock(stock_id: int, daten: SkiStockIn, db: Session = Depends(get_db)):
    try:
        stock = crud_materialstock.aendere_skistock(db, stock_id, daten.Bezeichnung)
    except MaterialUngueltig as e:
        raise HTTPException(status_code=400, detail=str(e))
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock nicht gefunden")
    return stock

@router.get("/{stock_id}/verwendung", response_model=list[VerleihVerwendung])
def verwendung_skistock(stock_id: int, db: Session = Depends(get_db)):
    """
    Verleihe, in denen der Stock steckt.
    """
    return crud_materialstock.verwendung_skistock(db, _stock_oder_404(db, stock_id))

@router.patch("/{stock_id}/ausgemustert", response_model=SkiStockOut)
def ausmustern_skistock(stock_id: int, daten: Ausmustern, db: Session = Depends(get_db)):
    """
    Mustert einen Stock aus oder stellt ihn wieder her.
    """
    return materialverwendung.setze_ausgemustert(db, _stock_oder_404(db, stock_id), daten.Ausgemustert)

@router.delete("/{stock_id}", response_model=LoeschErgebnis)
def loesche_skistock(stock_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Stock endgültig. Nur möglich, wenn er in keinem Verleih steckt.
    """
    try:
        crud_materialstock.loesche_skistock(db, _stock_oder_404(db, stock_id))
    except MaterialKonflikt as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"success": True}
