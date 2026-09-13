from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class SkiServicePreiseBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service: str = Field(alias="Service")
    preis: int = Field(alias="Preis")
    bindung: Optional[bool] = Field(default=None, alias="Bindung")


class SkiServicePreiseSchema(SkiServicePreiseBase):
    id: int
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)