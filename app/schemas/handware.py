from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints

# Leerzeichen am Rand werden entfernt, ein leerer Name ist ungültig
HandwareName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class HandwareBase(BaseModel):
    Name: HandwareName
    Beschreibung: Optional[str] = Field(None, max_length=500)
    Kategorie: Optional[str] = Field(None, max_length=50)
    Anzahl: Optional[int] = None
    Preis: float = Field(ge=0)


class HandwareCreate(HandwareBase):
    pass


class HandwareUpdate(BaseModel):
    # Nur gesetzte Felder werden geändert, null leert Beschreibung, Kategorie bzw. Anzahl
    Name: Optional[HandwareName] = None
    Beschreibung: Optional[str] = Field(None, max_length=500)
    Kategorie: Optional[str] = Field(None, max_length=50)
    Anzahl: Optional[int] = None
    Preis: Optional[float] = Field(None, ge=0)


class HandwareRead(HandwareBase):
    ID: int

    model_config = {
        "from_attributes": True
    }
