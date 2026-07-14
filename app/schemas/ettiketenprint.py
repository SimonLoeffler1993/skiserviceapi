from pydantic import BaseModel

class EttiketPrintRequest(BaseModel):
    success: bool
    message: str

class EttiketPrintSkisSchema(BaseModel):
    auftrag_id: int | None = None
    ski_ids: list[int]
