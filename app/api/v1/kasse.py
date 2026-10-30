from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.services.kassenartikel import KasseService
from app.services.lexware_sync import lexware_modus, quittung_pdf_hochladen_hintergrund
from app.utils.lexware import LexwareFehler
from app.schemas.kasse import KasseBezahlenSchema, KasseHatBezahltSchema, KassenArtikelSchema, KasseEinzelArtikelSchema, KasseArtikelKategorie

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
    elif artikelkategorie == KasseArtikelKategorie.verleih:
        return KasseService(db).get_offene_verleih()
    return KasseService(db).get_handware()

@router.post("/bezahlen", response_model=KasseHatBezahltSchema)
def bezahlen(artikels: KasseBezahlenSchema, hintergrund: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Markiert die angegebenen Artikels als bezahlt.
    Lexware Modus "pdf": die Quittung wird danach im Hintergrund als Beleg mit PDF hochgeladen.
    Lexware Modus "rechnung": die Rechnung wird direkt in Lexware angelegt, schlägt das fehl, wird nichts bezahlt.
    """
    try:
        ergebnis = KasseService(db).bezahlen(artikels)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LexwareFehler as e:
        raise HTTPException(status_code=502, detail=str(e))
    if lexware_modus() == "pdf":
        hintergrund.add_task(quittung_pdf_hochladen_hintergrund, ergebnis.quittung_id)
    return ergebnis