from pydantic import BaseModel

class OrtOut(BaseModel):
    Postlz: int
    Ort: str

    class Config:
        orm_mode = True