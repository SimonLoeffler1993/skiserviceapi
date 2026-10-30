from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Literal, Optional
from datetime import date

from app.db.deps import get_db
from app.crud import saisonverleih as crud_saisonverleih
from app.schemas.saisonverleih import VerleihBelegung, SaisonVerleihPreisBase, SaisonVerleihPreisRead, SaisonVerleihPreiseListe, SaisonVerleihRead, SaisonVerleihCreate, SaisonVerleihUpdate, SaisonVerleihMaterialBase, SaisonVerleihMaterialUpdate, VerleihStatusAenderung, BindungGeprueftAnfrage, VerleihBenachrichtigtAenderung, VerleihBenachrichtigenAnfrage
from app.utils import skipdf
from app.utils.mail import sendeVerleihMail

router = APIRouter(
    prefix="/saisonverleih",
    tags=["saisonverleih"],
    responses={404: {"description": "Not found"}},
)

@router.get("/test")
async def test():
    return {"message": "Saisonverleih API is working!"}

@router.get("/preise", response_model=SaisonVerleihPreiseListe)
async def get_saisonverleihpreise(db: Session = Depends(get_db)):
    """
    Zeigt alle Saisonverleihpreise an inklusieve der Gültigkeit und Historische.
    """
    preise = crud_saisonverleih.get_saisonverleihpreise(db)
    return {"preise": preise}

@router.post("/preise", response_model=SaisonVerleihPreisRead)
async def erstelle_saisonverleihpreis(preis: SaisonVerleihPreisBase, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Saisonverleihpreis.
    """
    ergebnis = crud_saisonverleih.create_saisonverleihpreis(db, preis)
    return ergebnis

@router.post("/neu")
async def erstelle_saisonverleih(saisonverleih: SaisonVerleihCreate, db: Session = Depends(get_db)):
    """
    Erstellt einen neuen Saisonverleih.
    """

    ergebnis = crud_saisonverleih.create_saisonverleih(db, saisonverleih)
    if ergebnis["success"]:
        # Über das Lese-Schema ausgeben, damit auch Tage und Bezeichnung enthalten sind
        ergebnis["data"] = SaisonVerleihRead.model_validate(ergebnis["data"])
    return ergebnis

# TODO Route für alle Daten aufeinmal abrufen
@router.get("/", response_model=list[SaisonVerleihRead])
async def list_saisonverleih(
        saisonID: Optional[int] = Query(default=None, description="ID der Saison für die Filterung der Verleih-Einträge, keine ist die aktelle Saison"),
        limit: int = Query(default=15, le=100), 
        last_id: Optional[int] = Query(default=None, description="ID des letzten Eintrags der vorherigen Seite für die Pagination"),
        alle: bool = Query(default=False, description="Alle Einträge ohne Pagination zurückgeben"),
        art: Optional[Literal["saison", "tag"]] = Query(default=None, description="Nur Saison- oder Tagesverleih"),
        db: Session = Depends(get_db)
    ):
    """
    Listet alle Saisonverleih-Einträge auf.
    """
    saisonverleih_liste = crud_saisonverleih.get_saisonverleih_liste(db, limit, last_id, saisonID, alle, art)
    return saisonverleih_liste

@router.get("/belegung", response_model=list[VerleihBelegung])
def get_belegung(
        von: date,
        bis: date,
        skinr: Optional[str] = Query(default=None),
        schuhnr: Optional[int] = Query(default=None),
        ausser_id: Optional[int] = Query(default=None, description="Diesen Verleih nicht berücksichtigen"),
        db: Session = Depends(get_db),
    ):
    """
    Prüft, ob Ski und/oder Schuh im Zeitraum von-bis bereits verliehen sind.
    Leere Liste = verfügbar.
    """
    if bis < von:
        raise HTTPException(status_code=400, detail="Das Enddatum darf nicht vor dem Startdatum liegen.")
    return crud_saisonverleih.finde_belegungen(db, von, bis, skinr, schuhnr, ausser_id)


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
def get_saisonverleih_pdf(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Generiert ein PDF für den Saisonverleih.
    Ohne async, damit FastAPI das Rendern in einem Thread ausführt und andere Anfragen nicht blockiert.
    """
    saisonverleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if not saisonverleih:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    
    pdf_bytes = skipdf.generate_Saisonbericht(saisonverleih)

    return Response(content=pdf_bytes, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename=saisonverleih_{saisonverleih_id}.pdf"
    })

@router.post("/zurueckgeben/{saisonverleih_id}")
async def saisonverleih_zurueckgeben(saisonverleih_id: int, db: Session = Depends(get_db), zurueck: bool = True):
    """
    Markiert einen Saisonverleih als zurückgegeben.
    """
    result = crud_saisonverleih.set_Saisonverleih_Zurueck(db, saisonverleih_id, zurueck)
    if not result:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    return {"message": f"Saisonverleih {saisonverleih_id} wurde als zurückgegeben markiert", "success": True}

@router.patch("/{saisonverleih_id}/status", response_model=SaisonVerleihRead)
def setze_verleih_status(saisonverleih_id: int, daten: VerleihStatusAenderung, db: Session = Depends(get_db)):
    """
    Setzt den Status: vorbereitung -> vorbereitet -> unterwegs (abgeholt) -> zurueck. Auch rückwärts zum Korrigieren.
    """
    status_vorher = _status(db, saisonverleih_id)
    verleih = crud_saisonverleih.setze_status(db, saisonverleih_id, daten.Status)
    if verleih is None:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    return _abhol_mail_nach_wechsel(db, verleih, status_vorher)


@router.post("/{saisonverleih_id}/benachrichtigen", response_model=SaisonVerleihRead)
def benachrichtige_kunde(saisonverleih_id: int, anfrage: VerleihBenachrichtigenAnfrage, db: Session = Depends(get_db)):
    """
    Versendet die Abhol- bzw. Rückgabe-Mail (auch erneut) und setzt danach die Benachrichtigung.
    """
    verleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    if verleih is None:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    if not verleih.Kunde or not verleih.Kunde.Email:
        raise HTTPException(status_code=400, detail="Beim Kunden ist keine E-Mail Adresse hinterlegt.")
    if not sendeVerleihMail(SaisonVerleihRead.model_validate(verleih), anfrage.art):
        raise HTTPException(status_code=502, detail="Die E-Mail konnte nicht versendet werden.")
    return crud_saisonverleih.setze_benachrichtigt(db, saisonverleih_id, anfrage.art)


@router.patch("/{saisonverleih_id}/benachrichtigt", response_model=SaisonVerleihRead)
def setze_benachrichtigt(saisonverleih_id: int, daten: VerleihBenachrichtigtAenderung, db: Session = Depends(get_db)):
    """
    Setzt die Benachrichtigung von Hand ohne Mail, z.B. nach einem Anruf. Jederzeit änderbar.
    """
    verleih = crud_saisonverleih.setze_benachrichtigt(db, saisonverleih_id, daten.Benachrichtigt)
    if verleih is None:
        raise HTTPException(status_code=404, detail="Saisonverleih not found")
    return verleih

# --- Bearbeiten / Löschen ---

def _verleih_oder_404(saisonverleih):
    if saisonverleih is None:
        raise HTTPException(status_code=404, detail="Verleih oder Material nicht gefunden")
    return saisonverleih


def _status(db: Session, saisonverleih_id: int) -> Optional[str]:
    """Status vor einer Änderung, um den Wechsel auf "vorbereitet" zu erkennen."""
    verleih = crud_saisonverleih.get_saisonverleih(db, saisonverleih_id)
    return verleih.Status if verleih else None


def _abhol_mail_nach_wechsel(db: Session, verleih, status_vorher: Optional[str]):
    """
    Wechselt der Verleih von "vorbereitung" auf "vorbereitet", bekommt der Kunde die Abhol-Mail,
    sofern er noch nicht benachrichtigt wurde und eine E-Mail hinterlegt ist.
    """
    if verleih is None or status_vorher != "vorbereitung" or verleih.Status != "vorbereitet" or verleih.Benachrichtigt != "nein":
        return verleih
    if not sendeVerleihMail(SaisonVerleihRead.model_validate(verleih), "abholung"):
        return verleih
    return crud_saisonverleih.setze_benachrichtigt(db, verleih.ID, "abholung")


@router.patch("/{saisonverleih_id}", response_model=SaisonVerleihRead)
def aendere_saisonverleih(saisonverleih_id: int, daten: SaisonVerleihUpdate, db: Session = Depends(get_db)):
    """
    Ändert Kunde, Bemerkung, Art oder Zeitraum. Die Verleihnummer bleibt erhalten.
    Bei bezahlten Verleihen kann nur noch die Bemerkung geändert werden.
    """
    try:
        return _verleih_oder_404(crud_saisonverleih.aendere_saisonverleih(db, saisonverleih_id, daten))
    except crud_saisonverleih.VerleihGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{saisonverleih_id}")
def loesche_saisonverleih(saisonverleih_id: int, db: Session = Depends(get_db)):
    """
    Löscht einen Verleih mit allem Material. Bezahlte Verleihe können nicht gelöscht werden.
    """
    try:
        if not crud_saisonverleih.loesche_saisonverleih(db, saisonverleih_id):
            raise HTTPException(status_code=404, detail="Saisonverleih nicht gefunden")
    except crud_saisonverleih.VerleihGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"success": True}


@router.post("/{saisonverleih_id}/material", response_model=SaisonVerleihRead)
def fuege_material_hinzu(saisonverleih_id: int, material: SaisonVerleihMaterialBase, db: Session = Depends(get_db)):
    try:
        status_vorher = _status(db, saisonverleih_id)
        verleih = _verleih_oder_404(crud_saisonverleih.fuege_material_hinzu(db, saisonverleih_id, material))
        return _abhol_mail_nach_wechsel(db, verleih, status_vorher)
    except crud_saisonverleih.VerleihGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/{saisonverleih_id}/material/{material_id}", response_model=SaisonVerleihRead)
def aendere_material(saisonverleih_id: int, material_id: int, daten: SaisonVerleihMaterialUpdate, db: Session = Depends(get_db)):
    try:
        status_vorher = _status(db, saisonverleih_id)
        verleih = _verleih_oder_404(crud_saisonverleih.aendere_material(db, saisonverleih_id, material_id, daten))
        return _abhol_mail_nach_wechsel(db, verleih, status_vorher)
    except crud_saisonverleih.VerleihGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{saisonverleih_id}/bindung-geprueft", response_model=SaisonVerleihRead)
def bindung_geprueft(saisonverleih_id: int, anfrage: BindungGeprueftAnfrage, db: Session = Depends(get_db)):
    """
    Markiert die Bindungen der Materialzeilen mit Ski als geprüft (ohne material_ids alle).
    Sind danach alle geprüft, wechselt ein Verleih in Vorbereitung auf "vorbereitet" und der Kunde bekommt die Abhol-Mail.
    """
    status_vorher = _status(db, saisonverleih_id)
    verleih = _verleih_oder_404(crud_saisonverleih.pruefe_bindungen(db, saisonverleih_id, anfrage.material_ids))
    return _abhol_mail_nach_wechsel(db, verleih, status_vorher)


@router.delete("/{saisonverleih_id}/material/{material_id}", response_model=SaisonVerleihRead)
def entferne_material(saisonverleih_id: int, material_id: int, db: Session = Depends(get_db)):
    try:
        status_vorher = _status(db, saisonverleih_id)
        verleih = _verleih_oder_404(crud_saisonverleih.entferne_material(db, saisonverleih_id, material_id))
        return _abhol_mail_nach_wechsel(db, verleih, status_vorher)
    except crud_saisonverleih.VerleihGesperrt as e:
        raise HTTPException(status_code=409, detail=str(e))
