from typing import Optional

from sqlalchemy import Boolean, Integer, String, ForeignKey, Double
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# TODO: Unterscheidung zwischen Kinder und Erwachsenenschuhen

class VerleihSchuhHersteller(Base):
    __tablename__ = "verleihschuhhersteller"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[Optional[str]] = mapped_column(String(100))


class VerleihSchuhModell(Base):
    __tablename__ = "verleihschuhmodell"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Modell: Mapped[Optional[str]] = mapped_column(String(100))
    Jugend: Mapped[Optional[int]] = mapped_column(Integer)

    Hersteller_ID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("verleihschuhhersteller.ID"))
    Hersteller: Mapped[Optional["VerleihSchuhHersteller"]] = relationship(backref="verleihschuhmodell")


class EigenSchuh(Base):
    __tablename__ = "eigenschuh"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Sichtbare Schuh-Nr., z.B. für Inventur-Aufkleber. Standard ist die ID.
    # Verleihe verweisen weiter auf die ID, die Nummer kann sich also ändern.
    SchuhNr: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    Modell_ID: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("verleihschuhmodell.ID"))
    Modell: Mapped[Optional["VerleihSchuhModell"]] = relationship(backref="eigenschuh")

    Groese: Mapped[Optional[float]] = mapped_column(Double)
    # Sohlenlänge in mm (optional), z.B. für die Bindungseinstellung
    Sohle: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    Saison: Mapped[Optional[str]] = mapped_column(String(20))
    VK: Mapped[Optional[float]] = mapped_column(Double)
    EK: Mapped[Optional[float]] = mapped_column(Double)
    # Ausgemustert: nicht mehr verleihbar, bleibt aber für bestehende Verleihe erhalten
    Ausgemustert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")