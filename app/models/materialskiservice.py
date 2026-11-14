from datetime import date

from sqlalchemy import Date, Double, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VerleihSkiService(Base):
    """Ein Service (z.B. Kanten schleifen, Wachsen) an einem eigenen Leihski."""
    __tablename__ = "verleihskiservice"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Bewusst die ID und nicht die Ski-Nr.: die Nummer kann geändert werden
    EigenSki_ID: Mapped[int] = mapped_column(Integer, ForeignKey("eigenski.ID", ondelete="CASCADE"), nullable=False, index=True)
    Datum: Mapped[date] = mapped_column(Date, nullable=False)
    Bezeichnung: Mapped[str] = mapped_column(String(200), nullable=False)
    # Betrag in Euro, der vom Erwirtschafteten des Skis abgezogen wird.
    # Wird beim Eintragen aus den Einstellungen vorbelegt und bleibt danach unverändert.
    Abzug: Mapped[float] = mapped_column(Double, nullable=False, default=0)
