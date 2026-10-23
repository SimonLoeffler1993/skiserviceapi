from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.materialschuh import (
    EigenSchuhBase, EigenSchuhRead, EigenSchuhUpdate,
    VerleihSchuhHerstellerBase, VerleihSchuhHerstellerRead, VerleihSchuhHerstellerUpdate,
    VerleihSchuhModellBase, VerleihSchuhModellRead, VerleihSchuhModellUpdate,
)
from app.schemas.materialverwendung import Ausmustern, LoeschErgebnis, StammdatenVerwendung, VerleihVerwendung
from app.models.materialschuh import VerleihSchuhHersteller, VerleihSchuhModell
from app.crud import materialschuh as crud_materialschuh
from app.crud import materialverwendung
from app.crud.materialverwendung import MaterialKonflikt, MaterialUngueltig

router = APIRouter(
    prefix="/material/schuh",
    tags=["Material","Schuh"],
    responses={404: {"description": "Not found"}},
)


def _fehler(e: Exception):
    """Fachliche Fehler in HTTP-Fehler umwandeln."""
    if isinstance(e, MaterialKonflikt):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=400, detail=str(e))


def _schuh_oder_404(db: Session, schuh_id: int):
    schuh = crud_materialschuh.get_eigen_schuh_by_id(db, schuh_id)
    if schuh is None:
        raise HTTPException(status_code=404, detail="Schuh nicht gefunden")
    return schuh


@router.get("/test")
async def test():
    return {"message": "Materialschuh API is working!"}

@router.get("/eigen", response_model=EigenSchuhRead)
def get_eigen_schuhe(schuhnr: str, db: Session = Depends(get_db)):
    """
    Sucht einen Schuh anhand der Schuh-Nr. (nicht der internen ID).
    Ausgemusterte Schuhe sind enthalten (Feld Ausgemustert), damit das Center darauf hinweisen kann.
    """
    schuh = crud_materialschuh.get_eigen_schuhe(db, schuhnr)
    if schuh is None:
        raise HTTPException(status_code=404, detail="EigenSchuh nicht gefunden")
    return schuh

@router.post("/eigen", response_model=EigenSchuhRead)
def create_eigen_schuhe(schuh: EigenSchuhBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Eigenen Schuh. Ohne Schuh-Nr. wird die interne ID als Nummer verwendet.
    """
    try:
        return crud_materialschuh.create_eigen_schuhe(db, schuh)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)

@router.get("/eigen/liste", response_model=list[EigenSchuhRead])
def get_eigen_schuhe_liste(
        mit_ausgemustert: bool = Query(default=False, description="Auch ausgemusterte Schuhe zurückgeben"),
        db: Session = Depends(get_db),
    ):
    """
    Gibt alle Eigenen Schuhe zurueck.
    """
    return crud_materialschuh.get_eigen_schuhe_liste(db, mit_ausgemustert)

@router.patch("/eigen/{schuh_id}", response_model=EigenSchuhRead)
def aendere_eigen_schuh(schuh_id: int, daten: EigenSchuhUpdate, db: Session = Depends(get_db)):
    """
    Ändert einen Schuh. Eine neue Schuh-Nr. muss eindeutig sein, leer = interne ID.
    """
    try:
        schuh = crud_materialschuh.aendere_eigen_schuh(db, schuh_id, daten)
    except (MaterialKonflikt, MaterialUngueltig) as e:
        _fehler(e)
    if schuh is None:
        raise HTTPException(status_code=404, detail="Schuh nicht gefunden")
    return schuh

@router.get("/eigen/{schuh_id}/verwendung", response_model=list[VerleihVerwendung])
def verwendung_eigen_schuh(schuh_id: int, db: Session = Depends(get_db)):
    """
    Verleihe, in denen der Schuh steckt.
    """
    return crud_materialschuh.verwendung_eigen_schuh(db, _schuh_oder_404(db, schuh_id))

@router.patch("/eigen/{schuh_id}/ausgemustert", response_model=EigenSchuhRead)
def ausmustern_eigen_schuh(schuh_id: int, daten: Ausmustern, db: Session = Depends(get_db)):
    """
    Mustert einen Schuh aus oder stellt ihn wieder her.
    """
    return materialverwendung.setze_ausgemustert(db, _schuh_oder_404(db, schuh_id), daten.Ausgemustert)

@router.delete("/eigen/{schuh_id}", response_model=LoeschErgebnis)
def loesche_eigen_schuh(schuh_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Schuh endgültig. Nur möglich, wenn er in keinem Verleih steckt.
    """
    try:
        crud_materialschuh.loesche_eigen_schuh(db, _schuh_oder_404(db, schuh_id))
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}


# --- Hersteller ---

@router.post("/hersteller", response_model=VerleihSchuhHerstellerRead)
def create_hersteller(schuh: VerleihSchuhHerstellerBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Schuhhersteller.
    """
    return crud_materialschuh.create_hersteller(db, schuh)

@router.get("/hersteller", response_model=list[VerleihSchuhHerstellerRead])
def get_hersteller(db: Session = Depends(get_db)):
    """
    Gibt alle Schuhhersteller zurück.
    """
    return crud_materialschuh.get_hersteller(db)

@router.patch("/hersteller/{hersteller_id}", response_model=VerleihSchuhHerstellerRead)
def aendere_hersteller(hersteller_id: int, daten: VerleihSchuhHerstellerUpdate, db: Session = Depends(get_db)):
    try:
        hersteller = crud_materialschuh.aendere_hersteller(db, hersteller_id, daten)
    except MaterialUngueltig as e:
        _fehler(e)
    if hersteller is None:
        raise HTTPException(status_code=404, detail="Hersteller nicht gefunden")
    return hersteller

@router.get("/hersteller/{hersteller_id}/verwendung", response_model=StammdatenVerwendung)
def verwendung_hersteller(hersteller_id: int, db: Session = Depends(get_db)):
    return crud_materialschuh.verwendung_hersteller(db, hersteller_id)

@router.delete("/hersteller/{hersteller_id}", response_model=LoeschErgebnis)
def loesche_hersteller(hersteller_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Schuhhersteller. Nur möglich, wenn kein Modell darauf verweist.
    """
    hersteller = db.get(VerleihSchuhHersteller, hersteller_id)
    if hersteller is None:
        raise HTTPException(status_code=404, detail="Hersteller nicht gefunden")
    try:
        crud_materialschuh.loesche_hersteller(db, hersteller)
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}


# --- Modelle ---

@router.post("/modell", response_model=VerleihSchuhModellRead)
def create_modell(modell: VerleihSchuhModellBase, db: Session = Depends(get_db)):
    """
    Erstelle das Skischuhmodell.
    """
    return crud_materialschuh.create_modell(db, modell)

@router.get("/modelle", response_model=list[VerleihSchuhModellRead])
def get_modelle(db: Session = Depends(get_db)):
    """
    Gibt alle Schuhmodelle zurück
    """
    return crud_materialschuh.get_modelle(db)

@router.patch("/modell/{modell_id}", response_model=VerleihSchuhModellRead)
def aendere_modell(modell_id: int, daten: VerleihSchuhModellUpdate, db: Session = Depends(get_db)):
    try:
        modell = crud_materialschuh.aendere_modell(db, modell_id, daten)
    except MaterialUngueltig as e:
        _fehler(e)
    if modell is None:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    return modell

@router.get("/modell/{modell_id}/verwendung", response_model=StammdatenVerwendung)
def verwendung_modell(modell_id: int, db: Session = Depends(get_db)):
    return crud_materialschuh.verwendung_modell(db, modell_id)

@router.delete("/modell/{modell_id}", response_model=LoeschErgebnis)
def loesche_modell(modell_id: int, db: Session = Depends(get_db)):
    """
    Löscht ein Schuhmodell. Nur möglich, wenn kein Schuh darauf verweist.
    """
    modell = db.get(VerleihSchuhModell, modell_id)
    if modell is None:
        raise HTTPException(status_code=404, detail="Modell nicht gefunden")
    try:
        crud_materialschuh.loesche_modell(db, modell)
    except MaterialKonflikt as e:
        _fehler(e)
    return {"success": True}
