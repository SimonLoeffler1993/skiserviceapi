import httpx
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.deps import get_db
from app.crud import quittung as crud_quittung
from app.schemas.quittung import QuittungRead
from app.utils.lexware import LexwareAPI

router = APIRouter(
    prefix="/quittungen",
    tags=["quittungen"],
    responses={404: {"description": "Not found"}},
)

lexware_api = LexwareAPI()

@router.get("/lexware/belege")
async def get_lexware_belege(
        page: Optional[int] = Query(default=0, description="Seitenzahl für die Paginierung der Belege von Lexware, beginnend bei 0")
    ):
    """
    Holt die Belege von Lexoffice.
    """
    try:
        # Standardmäßig wird die erste Seite (page=0) abgerufen, wenn kein Wert angegeben ist.
        if page is None:
            page = 0

        belege_data = lexware_api.get_belege(page=page)
        return belege_data
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

@router.get("/lexware/{lex_quittung_id}")
async def get_lexware_quittung(lex_quittung_id: str):
    """
    Holt den Bezahlstatus einer Quittung von Lexoffice anhand der Quittungs-ID.
    """
    try:
        quittung_data = lexware_api.get_bezahlstatus(lex_quittung_id)
        return quittung_data
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    
@router.get("/quittung/{quittung_id}", response_model=QuittungRead)
async def get_quittung(quittung_id: int, bezahlinfo: bool = False, db: Session = Depends(get_db)):
    """
    Holt eine Quittung anhand der ID.
    mir bezahlinfo = True werden die Bezahlinformationen von Lexware mit abgefragt und in die Antwort integriert.
    """
    quittung = crud_quittung.get_quittung(db, quittung_id)
    if not quittung:
        raise HTTPException(status_code=404, detail="Quittung not found")
    if bezahlinfo:
        try:
    
            # TODO Datum für Lex Sync in DB Speichern
            bezahlinfo_data = lexware_api.get_bezahlstatus(quittung.LexID)
            lexBez = False
            print("Bezahlinfo von Lexware:", bezahlinfo_data)
            if bezahlinfo_data["voucherStatus"] == "paid":
                quittung.Bezahlt = True
                # Parse ISO 8601 datetime and convert to date
                if bezahlinfo_data["paidDate"]:
                    paid_date = datetime.fromisoformat(bezahlinfo_data["paidDate"].replace('Z', '+00:00'))
                    quittung.Bezahlt_Am = paid_date.date()
                else:
                    quittung.Bezahlt_Am = None
                db.commit()
                db.refresh(quittung)
                lexBez = True
            else:
                quittung.Bezahlt = False
                quittung.Bezahlt_Am = None
                db.commit()
                db.refresh(quittung)

           

            lexOffenerBetrag = -1
            lexOffenerBetrag = bezahlinfo_data["openAmount"]

            lexBezahltAm = None
            if bezahlinfo_data["paidDate"]:
                # Parse ISO 8601 datetime and convert to date for response
                paid_date = datetime.fromisoformat(bezahlinfo_data["paidDate"].replace('Z', '+00:00'))
                lexBezahltAm = paid_date.date()

            bezInfo = {
                "Bezahlt": lexBez,
                "Bezahlt_Am": lexBezahltAm,
                "Offener_Betrag": lexOffenerBetrag
            }

                # eigenes Response Model mit Bezahlinfo erstellen
            quittungResponse = {
                ** quittung.__dict__,
                "BezahlInfo": bezInfo
            }
            return quittungResponse

        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
    return quittung


@router.get("/test")
async def test():
    return {"test": "hier sind die quittungen"}

