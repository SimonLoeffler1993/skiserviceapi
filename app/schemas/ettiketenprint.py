from pydantic import BaseModel

class EttiketPrintRequest(BaseModel):
    success: bool
    message: str