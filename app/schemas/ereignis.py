from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class EreignisRead(BaseModel):
    id: int
    zeitpunkt: datetime
    art: str
    art_bezeichnung: str
    benutzer_id: Optional[int] = None
    benutzer_name: Optional[str] = None
    geraet: Optional[str] = None
    kunde_id: Optional[int] = None
    auftrag_id: Optional[int] = None
    verleih_id: Optional[int] = None
    quittung_id: Optional[int] = None
    text: str
