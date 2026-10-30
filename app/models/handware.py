from sqlalchemy import Double, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Handware(Base):
    """Einfacher Verkaufsartikel für die Kasse (z.B. Wachs, Mützen). Nur Name und Preis sind Pflicht."""
    __tablename__ = "handware"

    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100))
    Beschreibung: Mapped[str | None] = mapped_column(String(500), nullable=True)
    Kategorie: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Nur zur Orientierung, wird beim Verkauf abgezogen (auch ins Minus) und verhindert nie einen Verkauf
    Anzahl: Mapped[int | None] = mapped_column(Integer, nullable=True)
    Preis: Mapped[float] = mapped_column(Double)
