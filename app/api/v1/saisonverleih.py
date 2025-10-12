from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from typing import Optional

from app.db.deps import get_db
from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.saisonverleih import SaisonVerleihRead, SaisonVerleihCreate
from app.utils import skipdf

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

@router.post("/neu")
async def erstelle_saisonverleih(saisonverleih: SaisonVerleihCreate, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Saisonverleih.
    """

    # print("Erstelle neuen Saisonverleih:")
    # print(saisonverleih)

    # print(saisonverleih)
    ergebnis = crud_saisonverleih.create_saisonverleih(db, saisonverleih)
    return ergebnis

# TODO get Paramter für Saison
@router.get("/", response_model=list[SaisonVerleihRead])
async def list_saisonverleih(saisonID: Optional[int] = None ,db: Session = Depends(get_db)):
    """
    Listet alle Saisonverleih-Einträge auf.
    """
    saisonverleih_liste = crud_saisonverleih.get_saisonverleih_liste(db, saisonID)
    return saisonverleih_liste

@router.get("/{saisonverleih_id}" , response_model=SaisonVerleihRead)
async def get_saisonverleih(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Holt einen Saisonverleih anhand der ID.
    """
    saisonverleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    return saisonverleih

@router.get("/pdf/{saisonverleih_id}")
async def get_saisonverleih_pdf(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Generiert ein PDF für den Saisonverleih.
    """
    saisonverleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    
    pdf_bytes = skipdf.generate_Saisonbericht(saisonverleih)

    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"attachment; filename=saisonverleih_{saisonverleih_id}.pdf"
    })