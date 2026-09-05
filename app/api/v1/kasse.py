from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.services.kassenartikel import KasseService
from app.schemas.kasse import KassenArtikelSchema, KasseEinzelArtikelSchema, KasseArtikelKategorie

router = APIRouter(
    prefix="/kasse",
    tags=["kasse"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"test": "Kasse API is working!"}

@router.get("/artikels", response_model=list[KassenArtikelSchema])
async def artikels(artikelkategorie: KasseArtikelKategorie = KasseArtikelKategorie.auftrag, db: Session = Depends(get_db)):
    if artikelkategorie == KasseArtikelKategorie.auftrag:
        return KasseService(db).get_offene_auftraege()