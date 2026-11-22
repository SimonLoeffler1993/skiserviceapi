from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.zugriff import Zugriff, angemeldet, pruefe_recht
from app.db.deps import get_db
from app.models.ereignis import Ereignis
from app.schemas.ereignis import EreignisRead
from app.services.ereignisse import ARTEN

router = APIRouter(
    prefix="/ereignisse",
    tags=["ereignisse"],
    dependencies=[Depends(angemeldet)],
)


@router.get("/", response_model=list[EreignisRead])
def liste(
    auftrag_id: int | None = None,
    verleih_id: int | None = None,
    quittung_id: int | None = None,
    benutzer_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    zugriff: Zugriff = Depends(angemeldet),
    db: Session = Depends(get_db),
):
    """Verlauf zu genau einem Auftrag, Verleih, einer Quittung oder (nur Admin) einem Benutzer, neueste zuerst."""
    filter_werte = {"Auftrag_ID": auftrag_id, "Verleih_ID": verleih_id, "Quittung_ID": quittung_id,
                    "Benutzer_ID": benutzer_id}
    gesetzt = {k: v for k, v in filter_werte.items() if v is not None}
    if len(gesetzt) != 1:
        raise HTTPException(status_code=400, detail="Genau einer von auftrag_id, verleih_id, quittung_id, benutzer_id")
    if benutzer_id is not None:
        pruefe_recht("benutzer.verwalten", zugriff)
    spalte, wert = next(iter(gesetzt.items()))
    eintraege = (db.query(Ereignis)
                 .filter(getattr(Ereignis, spalte) == wert)
                 .order_by(Ereignis.Zeitpunkt.desc(), Ereignis.ID.desc())
                 .limit(limit)
                 .all())
    return [{
        "id": e.ID,
        "zeitpunkt": e.Zeitpunkt,
        "art": e.Art,
        "art_bezeichnung": ARTEN.get(e.Art, e.Art),
        "benutzer_id": e.Benutzer_ID,
        "benutzer_name": e.Benutzer_Name,
        "geraet": e.Geraet,
        "kunde_id": e.Kunde_ID,
        "auftrag_id": e.Auftrag_ID,
        "verleih_id": e.Verleih_ID,
        "quittung_id": e.Quittung_ID,
        "text": e.Text,
    } for e in eintraege]
