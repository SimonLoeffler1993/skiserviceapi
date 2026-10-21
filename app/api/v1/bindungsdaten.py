from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud import bindungsdaten as crud_bindungsdaten
from app.schemas.bindungsdaten import BindungsdatenArchivieren, BindungsdatenListeEintrag, BindungsdatenRead

router = APIRouter(
    tags=["Bindungsdaten"],
    responses={404: {"description": "Not found"}},
)


@router.get("/kunden/{kunde_id}/bindungsdaten", response_model=list[BindungsdatenListeEintrag])
def get_bindungsdaten_kunde(
        kunde_id: int,
        archiviert: bool = Query(default=False, description="Auch archivierte Einträge zurückgeben"),
        db: Session = Depends(get_db),
    ):
    """
    Alle Bindungsdaten eines Kunden, neueste zuerst.
    """
    return crud_bindungsdaten.bindungsdaten_kunde(db, kunde_id, archiviert)


@router.patch("/bindungsdaten/{bindungsdaten_id}", response_model=BindungsdatenRead)
def archiviere_bindungsdaten(bindungsdaten_id: int, daten: BindungsdatenArchivieren, db: Session = Depends(get_db)):
    """
    Archiviert einen Eintrag oder stellt ihn wieder her.
    """
    eintrag = crud_bindungsdaten.setze_archiviert(db, bindungsdaten_id, daten.Archiviert)
    if eintrag is None:
        raise HTTPException(status_code=404, detail="Bindungsdaten nicht gefunden")
    return eintrag
