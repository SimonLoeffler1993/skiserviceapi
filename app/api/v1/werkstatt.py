from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.crud import saison as crud_saison
from app.crud import werkstatt as crud_werkstatt
from app.db.deps import get_db
from app.models.saison import Saison
from app.schemas.werkstatt import WerkstattUebersicht

router = APIRouter(
    prefix="/werkstatt",
    tags=["werkstatt"],
    responses={404: {"description": "Not found"}},
)


@router.get("/uebersicht", response_model=WerkstattUebersicht)
def get_uebersicht(saisonID: Optional[int] = None, db: Session = Depends(get_db)):
    """Werkstatt-Dashboard: offene Ski und Verleihe, Auswertung und Verleih-Zahlen einer Saison."""
    # Ohne Saison ID wird die aktuelle Saison verwendet
    if saisonID is None:
        saison = crud_saison.get_AktuelleSaison(db)
    else:
        saison = db.query(Saison).filter(Saison.ID == saisonID).first()
    if saison is None:
        raise HTTPException(status_code=404, detail="Saison nicht gefunden.")

    return {
        "saison": {"ID": saison.ID, "Name": saison.Name},
        "ski_offen": crud_werkstatt.offene_ski(db, saison.ID),
        "verleih_offen": crud_werkstatt.offene_verleihe(db, saison.ID),
        "auswertung": crud_werkstatt.auswertung(db, saison.ID),
        "verleih": crud_werkstatt.verleih_zahlen(db, saison.ID),
    }
