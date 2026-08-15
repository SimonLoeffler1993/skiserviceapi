from typing import Optional

from sqlalchemy import Integer, String, ForeignKey, Double
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VerleihSkiHersteller(Base):
    __tablename__ = "verleihskihersteller"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[Optional[str]] = mapped_column(String(100))


class SkiArt(Base):
    __tablename__ = "skiart"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Art: Mapped[Optional[str]] = mapped_column(String(100))


class VerleihSkiModell(Base):
    __tablename__ = "verleihskimodell"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Modell: Mapped[Optional[str]] = mapped_column(String(100))

    Art_ID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("skiart.ID"))
    Art: Mapped[Optional["SkiArt"]] = relationship(backref="verleihskimodell")

    Hersteller_ID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("verleihskihersteller.ID"))
    Hersteller: Mapped[Optional["VerleihSkiHersteller"]] = relationship(backref="verleihskimodell")


class EigenSki(Base):
    __tablename__ = "eigenski"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)

    Modell_ID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("verleihskimodell.ID"))
    Modell: Mapped[Optional["VerleihSkiModell"]] = relationship(backref="eigenski")

    Laenge: Mapped[Optional[int]] = mapped_column(Integer)
    VK: Mapped[Optional[float]] = mapped_column(Double)
    EK: Mapped[Optional[float]] = mapped_column(Double)
    Saison: Mapped[Optional[str]] = mapped_column(String(20))
    SkiNr: Mapped[Optional[str]] = mapped_column(String(50), unique=True)