from pydantic import BaseModel

class EttiketPrintRequest(BaseModel):
    success: bool
    message: str

class EttiketPrintSkisSchema(BaseModel):
    auftrag_id: int | None = None
    ski_ids: list[int]

class VerleihEttiketPrintSchema(BaseModel):
    # Schlüssel wie "12-ski" / "12-schuh", ohne Angabe alle Etiketten des Verleihs
    etiketten: list[str] | None = None

class VerleihEttiketEintrag(BaseModel):
    Schluessel: str
    Name: str
    # SkiFahrerName, None wenn keiner angegeben ist
    Fahrer: str | None = None
    # Fahrer bzw. "Ausrüstung #n" (Zählung der Zeilen ohne Fahrer im Verleih)
    Bezeichnung: str
    Teil: str
