from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.ort import OrtOut


class SkiKundeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ID: int
    Nachname: str | None = None
    Vorname: str | None = None
    Strasse: str | None = None
    Ort: OrtOut | None = None
    Tel: str | None = None
    Handy: str | None = Field(None, validation_alias="Tel1")
    Email: str | None = None


class SkiKundeSpeichern(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    Nachname: str | None = Field(None, max_length=20)
    Vorname: str | None = Field(None, max_length=20)
    Strasse: str | None = Field(None, max_length=250)
    Plz: int | None = None
    Ort: str | None = None
    Tel: str | None = Field(None, max_length=50)
    Handy: str | None = Field(None, max_length=50)
    Email: str | None = Field(None, max_length=50)

    # macht aus leeren Strings None, damit die Datenbank NULL-Werte bekommt
    @field_validator("*", mode="before")
    @classmethod
    def leer_zu_none(cls, v):
        if isinstance(v, str):
            return v.strip() or None
        return v

    # prüft, ob die Pflichtangaben vorhanden sind
    # mindest 1 Name Vor oder Nachema
    # mindestens 1 Kontaktmöglichkeit Tel, Handy oder Email
    @model_validator(mode="after")
    def pruefe_pflichtangaben(self):
        if not (self.Nachname or self.Vorname):
            raise ValueError("Mindestens Vorname oder Nachname angeben")
        if not (self.Tel or self.Handy or self.Email):
            raise ValueError("Mindestens E-Mail, Telefon oder Handy angeben")
        return self

class SkiKundeZuTerminal(BaseModel):
    terminal: str
    kunde_id: int