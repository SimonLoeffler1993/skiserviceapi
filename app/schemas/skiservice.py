from pydantic import BaseModel, field_serializer
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

from app.schemas.kunde import SkiKundeOut


class SkiSchema(BaseModel):
    id: int
    auftrag_id: int
    service: str
    preis: float
    status: Optional[int] = None
    komentar: Optional[str] = None
    dabei: Optional[int] = None
    fertig_date: Optional[str] = None
    bindung_id: int
    bindung_check: bool = False
    bindung_preis: float
    name: Optional[str] = None
    band: int
    sack: int
    bindung_status: bool = False
    gepueft: Optional[date] = None

    model_config = {"from_attributes": True}

class SkiCreateSchema(BaseModel):
    service: str
    preis: float
    komentar: Optional[str] = None
    bindung_preis: float
    bindung_check: bool


class AuftragSchema(BaseModel):
    id: int
    kunden_id: int
    kunde: SkiKundeOut
    start_date: datetime
    ende_date: Optional[str] = None
    wie: Optional[str] = None
    a_ski: Optional[str] = None
    ettiket: Optional[str] = None
    zu: str
    fertig_date: Optional[str] = None
    abhol_date: Optional[str] = None
    anzahlung: Optional[str] = None
    bezahlt: str
    bezahlt_am: Optional[date] = None
    benachrichtigt: str
    abgerechnet: Optional[int] = None
    uberweisung: Optional[int] = None
    name: Optional[str] = None
    anz_leih: Optional[int] = None
    rabat: Optional[float] = None
    rabat_name: Optional[str] = None
    rabat_waerung: Optional[int] = None
    leih_versicherung: Optional[int] = None
    quittung_id: Optional[int] = None

    skis: list[SkiSchema] = []

    model_config = {"from_attributes": True}

    @field_serializer("start_date")
    def serialize_datetime(self, dt: datetime, _info) -> Optional[str]:
        return dt.isoformat() if dt else None

    @field_serializer("bezahlt_am")
    def serialize_date(self, d: date, _info) -> Optional[str]:
        return d.isoformat() if d else None
    
class AuftragSkiFertigSchema(BaseModel):
    id: int
    ski_ids: list[int]

class SkiBindungFertigSchema(BaseModel):
    ski_ids: list[int]

class AuftragCreateSchema(BaseModel):
    kunden_id: int
    abhol_date: Optional[str] = None
    skis: list[SkiCreateSchema]


