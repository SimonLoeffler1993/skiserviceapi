from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.checkin import CheckinRead, CheckinSchluesselRead, CheckinStatus, CheckinUebernommen
from app.services import checkin as checkin_service
from app.services import checkin_schluessel

router = APIRouter(
    prefix="/checkin",
    tags=["checkin"],
)


def _schluessel_read(eintrag) -> CheckinSchluesselRead:
    return CheckinSchluesselRead(
        schluessel_id=eintrag.schluessel_id,
        public_key=eintrag.public_key,
        erstellt_am=checkin_schluessel.utc(eintrag.erstellt_am),
    )


@router.get("/", response_model=list[CheckinRead])
def liste(db: Session = Depends(get_db)):
    """Offene Check-ins entschlüsselt, neueste zuerst."""
    try:
        return checkin_service.liste(db)
    except checkin_service.CheckinNichtVerfuegbar as fehler:
        raise HTTPException(status_code=503, detail=str(fehler))


# Feste Pfade vor /{checkin_id}
@router.get("/status", response_model=CheckinStatus)
def status(db: Session = Depends(get_db)):
    return checkin_service.status(db)


@router.get("/schluessel", response_model=list[CheckinSchluesselRead])
def schluessel_liste(db: Session = Depends(get_db)):
    """Schlüssel nur mit Public Key, der private Schlüssel verlässt die API nie."""
    return [_schluessel_read(eintrag) for eintrag in checkin_schluessel.liste(db)]


@router.post("/schluessel", response_model=CheckinSchluesselRead)
def schluessel_erzeugen(db: Session = Depends(get_db)):
    """Neues Schlüsselpaar. Der Public Key muss danach von Hand als CHECKIN_PUBLIC_KEY eingetragen werden."""
    return _schluessel_read(checkin_schluessel.erzeugen(db))


@router.post("/{checkin_id}/uebernehmen", response_model=CheckinUebernommen)
def uebernehmen(checkin_id: str, db: Session = Depends(get_db)):
    """Legt den Kunden an und löscht den Check-in aus der Zwischendatenbank."""
    try:
        ergebnis = checkin_service.uebernehmen(db, checkin_id)
    except checkin_service.CheckinNichtVerfuegbar as fehler:
        raise HTTPException(status_code=503, detail=str(fehler))
    except checkin_service.CheckinNichtGefunden:
        raise HTTPException(status_code=404, detail="Der Check-in wurde bereits übernommen oder verworfen.")
    except checkin_service.CheckinNichtLesbar as fehler:
        raise HTTPException(status_code=409, detail=str(fehler))
    except checkin_service.KundeNichtAngelegt:
        raise HTTPException(status_code=500, detail="Der Kunde konnte nicht angelegt werden.")
    return {"kunde": ergebnis.kunde, "warnung": ergebnis.warnung}


@router.delete("/{checkin_id}")
def verwerfen(checkin_id: str):
    """Löscht einen Check-in, z.B. Spam."""
    try:
        checkin_service.verwerfen(checkin_id)
    except checkin_service.CheckinNichtVerfuegbar as fehler:
        raise HTTPException(status_code=503, detail=str(fehler))
    except checkin_service.CheckinNichtGefunden:
        raise HTTPException(status_code=404, detail="Der Check-in wurde bereits übernommen oder verworfen.")
    return {"success": True}
