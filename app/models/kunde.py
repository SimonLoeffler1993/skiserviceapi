from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional

from app.db.base import Base
from app.models.ort import Ort


class SkiKunde(Base):
    __tablename__ = "adresse"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Nachname: Mapped[str | None] = mapped_column(String(20))
    Vorname: Mapped[str | None] = mapped_column(String(20))
    Anrede: Mapped[str | None] = mapped_column(String(1), default="f")
    Strasse: Mapped[str | None] = mapped_column(String(250))
    Plz: Mapped[int | None] = mapped_column(Integer, ForeignKey("postleitzahl.Postlz"))
    Ort: Mapped[Optional[Ort]] = relationship(Ort, back_populates="adresse")
    Tel: Mapped[str | None] = mapped_column(String(50))
    Email: Mapped[str | None] = mapped_column(String(50))
    Tel1: Mapped[str | None] = mapped_column(String(50))
    Tel2: Mapped[str | None] = mapped_column(String(50))
    Email1: Mapped[str | None] = mapped_column(String(50))
    Email2: Mapped[str | None] = mapped_column(String(50))
    AusweisNr: Mapped[str | None] = mapped_column(String(15), default="0")
    BDay: Mapped[str | None] = mapped_column(String(15))

    # back_populates von SaisonVerleih
    saisonverleih: Mapped[list["SaisonVerleih"]] = relationship(
        "SaisonVerleih", back_populates="Kunde"
    )