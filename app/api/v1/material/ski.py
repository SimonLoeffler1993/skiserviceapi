from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.materialski import EigenSkiRead, EigenSkiBase, EigenSkiUpdate, EigenSkiAenderung
from app.schemas.materialski import (
    SkiArtRead, SkiArtBase, SkiArtUpdate, VerleihSkiHerstellerRead, VerleihSkiHerstellerBase, VerleihSkiHerstellerUpdate,
    VerleihSkiModellBase, VerleihSkiModellRead, VerleihSkiModellUpdate,
)
from app.schemas.materialverwendung import Ausmustern, LoeschErgebnis, StammdatenVerwendung, VerleihVerwendung
from app.models.materialski import SkiArt, VerleihSkiHersteller, VerleihSkiModell
from app.crud import materialski as crud_materialski
from app.crud import materialverwendung
from app.crud.materialverwendung import MaterialKonflikt, MaterialUngueltig

router = APIRouter(
    prefix="/material/ski",
    tags=["Material","Ski"],
    responses={404: {"description": "Not found"}},
)


def _fehler(e: Exception):
    """Fachliche Fehler in HTTP-Fehler umwandeln."""
    if isinstance(e, MaterialKonflikt):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=400, detail=str(e))


def _ski_oder_404(db: Session, ski_id: int):
    ski = crud_materialski.get_eigen_ski_by_id(db, ski_id)
    if ski is None:
        raise HTTPException(status_code=404, detail="Ski nicht gefunden")
    return ski


@router.get("/test")
async def test():
    return {"message": "Materialski API is working!"}

@router.get("/eigen", response_model=list[EigenSkiRead])
def get_eigen_ski(skinr: str, db: Session = Depends(get_db)):
    """
    Gibt die Eigenen Ski anhand der SkiNr zurück. Es reicht ein Teil der SkiNr.
    Ausgemusterte Ski sind enthalten (Feld Ausgemustert), damit das Center darauf hinweisen kann.
    Wenn keine Ski gefunden werden, wird eine leere Liste zurückgegeben.
    """
    return crud_materialski.get_eigen_ski(db, skinr)

@router.get("/liste", response_model=list[EigenSkiRead])
def get_eigen_ski_liste(
        mit_ausgemustert: bool = Query(default=False, description="Auch ausgemusterte Ski zurückgeben"),
        db: Session = Depends(get_db),
    ):
    """
    Gibt alle Eigenen Ski zurück.
    """
    # TODO Paging
    return crud_materialski.get_eigen_ski(db, "", mit_ausgemustert)

@router.post("/anlegen", response_model=EigenSkiRead)
def create_eigen_ski(ski: EigenSkiBase, db: Session = Depends(get_db)):
    """
    Legt ein neues Eigenes Ski Material an. Die Ski-Nr. muss eindeutig sein.
    """
    try:
        return crud_materialski.create_eigen_ski(db, ski)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)

@router.patch("/eigen/{ski_id}", response_model=EigenSkiAenderung)
def aendere_eigen_ski(ski_id: int, daten: EigenSkiUpdate, db: Session = Depends(get_db)):
    """
    Ändert einen Ski. Eine neue Ski-Nr. muss eindeutig sein, bestehende Verleihe werden umgestellt.
    """
    try:
        ski, umgestellt = crud_materialski.aendere_eigen_ski(db, ski_id, daten)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)
    if ski is None:
        raise HTTPException(status_code=404, detail="Ski nicht gefunden")
    return EigenSkiAenderung.model_validate(ski).model_copy(update={"UmgestellteVerleihe": umgestellt})

@router.get("/eigen/{ski_id}/verwendung", response_model=list[VerleihVerwendung])
def verwendung_eigen_ski(ski_id: int, db: Session = Depends(get_db)):
    """
    Verleihe, in denen der Ski steckt.
    """
    return crud_materialski.verwendung_eigen_ski(db, _ski_oder_404(db, ski_id))

@router.patch("/eigen/{ski_id}/ausgemustert", response_model=EigenSkiRead)
def ausmustern_eigen_ski(ski_id: int, daten: Ausmustern, db: Session = Depends(get_db)):
    """
    Mustert einen Ski aus oder stellt ihn wieder her.
    """
    return materialverwendung.setze_ausgemustert(db, _ski_oder_404(db, ski_id), daten.Ausgemustert)

@router.delete("/eigen/{ski_id}", response_model=LoeschErgebnis)
def loesche_eigen_ski(ski_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Ski endgültig. Nur möglich, wenn er in keinem Verleih steckt.
    """
    try:
        crud_materialski.loesche_eigen_ski(db, _ski_oder_404(db, ski_id))
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}


# --- Hersteller ---

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
    return crud_materialski.create_hersteller(db, hersteller.Name)

@router.patch("/hersteller/{hersteller_id}", response_model=VerleihSkiHerstellerRead)
def aendere_hersteller(hersteller_id: int, daten: VerleihSkiHerstellerUpdate, db: Session = Depends(get_db)):
    try:
        hersteller = crud_materialski.aendere_hersteller(db, hersteller_id, daten)
    except MaterialUngueltig as e:
        _fehler(e)
    if hersteller is None:
        raise HTTPException(status_code=404, detail="Hersteller nicht gefunden")
    return hersteller

@router.get("/hersteller/{hersteller_id}/verwendung", response_model=StammdatenVerwendung)
def verwendung_hersteller(hersteller_id: int, db: Session = Depends(get_db)):
    return crud_materialski.verwendung_hersteller(db, hersteller_id)

@router.delete("/hersteller/{hersteller_id}", response_model=LoeschErgebnis)
def loesche_hersteller(hersteller_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Hersteller. Nur möglich, wenn kein Modell darauf verweist.
    """
    hersteller = db.get(VerleihSkiHersteller, hersteller_id)
    if hersteller is None:
        raise HTTPException(status_code=404, detail="Hersteller nicht gefunden")
    try:
        crud_materialski.loesche_hersteller(db, hersteller)
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}


# --- Skiart ---

@router.get("/art", response_model=list[SkiArtRead])
def get_skiart(db: Session = Depends(get_db)):
    """
    Gibt alle Skiarten zurück.
    """
    return crud_materialski.get_skiart(db)

@router.post("/art", response_model=SkiArtRead)
def create_skiart(art: SkiArtBase, db: Session = Depends(get_db)):
    """
    Legt eine neue Skiart an. Der Name muss eindeutig sein.
    """
    try:
        return crud_materialski.create_skiart(db, art.Art)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)

@router.patch("/art/{art_id}", response_model=SkiArtRead)
def aendere_skiart(art_id: int, daten: SkiArtUpdate, db: Session = Depends(get_db)):
    try:
        art = crud_materialski.aendere_skiart(db, art_id, daten)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)
    if art is None:
        raise HTTPException(status_code=404, detail="Skiart nicht gefunden")
    return art

@router.get("/art/{art_id}/verwendung", response_model=StammdatenVerwendung)
def verwendung_skiart(art_id: int, db: Session = Depends(get_db)):
    return crud_materialski.verwendung_skiart(db, art_id)

@router.delete("/art/{art_id}", response_model=LoeschErgebnis)
def loesche_skiart(art_id: int, db: Session = Depends(get_db)):
    """
    Löscht eine Skiart. Nur möglich, wenn weder Modelle noch Saisonverleih-Preise darauf verweisen.
    """
    art = db.get(SkiArt, art_id)
    if art is None:
        raise HTTPException(status_code=404, detail="Skiart nicht gefunden")
    try:
        crud_materialski.loesche_skiart(db, art)
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}


# --- Modelle ---

@router.post("/modell", response_model=VerleihSkiModellRead)
def create_ski_modell(modell: VerleihSkiModellBase, db: Session = Depends(get_db)):
    """
    Erstellt ein neues Skimodell.
    """
    return crud_materialski.create_ski_modell(db, modell)

@router.get("/modell", response_model=list[VerleihSkiModellRead])
def get_ski_modell(db: Session = Depends(get_db)):
    """
    Gibt alle Skimodelle zurück.
    """
    return crud_materialski.get_ski_modell(db)

@router.patch("/modell/{modell_id}", response_model=VerleihSkiModellRead)
def aendere_ski_modell(modell_id: int, daten: VerleihSkiModellUpdate, db: Session = Depends(get_db)):
    try:
        modell = crud_materialski.aendere_ski_modell(db, modell_id, daten)
    except MaterialUngueltig as e:
        _fehler(e)
    if modell is None:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    return modell

@router.get("/modell/{modell_id}/verwendung", response_model=StammdatenVerwendung)
def verwendung_ski_modell(modell_id: int, db: Session = Depends(get_db)):
    return crud_materialski.verwendung_ski_modell(db, modell_id)

@router.delete("/modell/{modell_id}", response_model=LoeschErgebnis)
def loesche_ski_modell(modell_id: int, db: Session = Depends(get_db)):
    """
    Löscht ein Skimodell. Nur möglich, wenn kein Ski darauf verweist.
    """
    modell = db.get(VerleihSkiModell, modell_id)
    if modell is None:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    try:
        crud_materialski.loesche_ski_modell(db, modell)
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}
