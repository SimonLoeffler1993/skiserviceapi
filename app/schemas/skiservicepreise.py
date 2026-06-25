from pydantic import BaseModel, Field
from typing import Optional


class SkiServicePreiseSchema(BaseModel):
    id: int
    service: str = Field(alias="Service")
    preis: int = Field(alias="Preis")
    bindung: Optional[bool] = Field(default=None, alias="Bindung")

    model_config = {"from_attributes": True, "populate_by_name": True}