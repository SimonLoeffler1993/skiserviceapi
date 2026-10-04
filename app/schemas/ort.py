from pydantic import BaseModel, ConfigDict

class OrtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    Postlz: int
    Ort: str