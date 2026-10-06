from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator,
)
from app.schemas.ort import OrtOut


class SkiKundeBasis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Nachname: str | None = Field(None, max_length=100)
    Vorname: str | None = Field(None, max_length=100)
    Strasse: str | None = Field(None, max_length=250)
    Tel: str | None = Field(None, max_length=50)
    # JSON-Eingabe heißt "Handy", das ORM-Objekt hat die Spalte "Tel1"
    Handy: str | None = Field(
        None, max_length=50, validation_alias=AliasChoices("Handy", "Tel1")
    )
    Email: str | None = Field(None, max_length=50)

    # macht aus leeren Strings None, damit die Datenbank NULL-Werte bekommt
    @field_validator("*", mode="before")
    @classmethod
    def leer_zu_none(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v


class SkiKundeSpeichern(SkiKundeBasis):
    Plz: int | None = None
    Ort: str | None = None

    # mindestens 1 Name (Vor- oder Nachname) und 1 Kontaktmöglichkeit (Tel, Handy, Email)
    @model_validator(mode="after")
    def pruefe_pflichtangaben(self):
        if not (self.Nachname or self.Vorname):
            raise ValueError("Mindestens Vorname oder Nachname angeben")
        if not (self.Tel or self.Handy or self.Email):
            raise ValueError("Mindestens E-Mail, Telefon oder Handy angeben")
        return self


class SkiKundeOut(SkiKundeBasis):
    ID: int
    Ort: OrtOut | None = None


class SkiKundeZuTerminal(BaseModel):
    terminal: str
    kunde_id: int


class SkiKundeTerminal(SkiKundeBasis):
    id: int = Field(validation_alias="ID")
    Plz: str | None = None
    Ort: str | None = None

    @field_validator("Plz", mode="before")
    @classmethod
    def plz_als_text(cls, v):
        return str(v) if v is not None else None

    @field_validator("Ort", mode="before")
    @classmethod
    def ort_name(cls, v):
        # v ist das Ort-Objekt (Relationship) oder None
        return v.Ort if v is not None else None