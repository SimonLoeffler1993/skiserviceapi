from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.mailprotokoll import MailProtokollRead
from app.services import mailprotokoll

router = APIRouter(
    prefix="/mailprotokoll",
    tags=["mailprotokoll"],
)


@router.get("/", response_model=list[MailProtokollRead])
def get_mailprotokoll(
    kunde_id: int | None = Query(None),
    auftrag_id: int | None = Query(None),
    verleih_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Die versendeten Mails eines Kunden, eines Skiservice-Auftrags oder eines Verleihs, neueste zuerst.
    Genau einer der drei Parameter muss angegeben sein.
    Quittungs-Mails erscheinen überall dort, wo die Quittung zugeordnet ist.
    """
    if sum(wert is not None for wert in (kunde_id, auftrag_id, verleih_id)) != 1:
        raise HTTPException(status_code=422, detail="Genau einer von kunde_id, auftrag_id und verleih_id muss angegeben sein.")
    if kunde_id is not None:
        return mailprotokoll.mails_kunde(db, kunde_id)
    if auftrag_id is not None:
        return mailprotokoll.mails_auftrag(db, auftrag_id)
    return mailprotokoll.mails_verleih(db, verleih_id)
