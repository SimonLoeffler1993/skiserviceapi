from sqlalchemy import Column, ForeignKey, Integer, Date, String, Boolean, Double
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date

from app.db.base import Base

# TODO Lex Sync Datum in DB
# Vorne bei Mapped immer Python typen verwenden, hinten bei mapped_column die SQLAlchemy Spaltentypen
class Quittung(Base):
    __tablename__ = "quittungen"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Name: Mapped[str] = mapped_column(String(100))
    AnzAuftrag: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    AnzVerleih: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    Saison_ID: Mapped[int] = mapped_column(Integer)
    Bezahlt_Am: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    Erstellt_Am: Mapped[date] = mapped_column(Date)
    Ueberweisung: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    Karte: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    Bar: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    Bezahlt: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    BuchhaltungSync: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    LexID: Mapped[str | None] = mapped_column(String(150), nullable=True, default=None)
    NurExtern: Mapped[bool] = mapped_column(Boolean, nullable=True, default=False)
    # Relation zu den Artikels, die in dieser Quittung enthalten sind
    artikels: Mapped[list["QuittungArtikel"]] = relationship("QuittungArtikel", back_populates="quittung", cascade="all, delete-orphan")

    @property
    def Nummer(self) -> str:
        """Angezeigte Nummer, z.B. "26/27Q12" oder die Lexware Rechnungsnummer. Altbestand ohne Nummer: die ID."""
        name = (self.Name or "").strip()
        return name if name.lower() not in ("", "quittung", "externer beleg") else str(self.ID)

    @property
    def ManuellZugewiesen(self) -> bool:
        """Lexware-Beleg von Hand zugewiesen (ohne Kasse, ohne Artikel): darf geändert oder aufgehoben werden."""
        return bool(self.NurExtern) and not self.artikels

# mit CACADE werden alle QuittungArtikel gelöscht, wenn die Quittung gelöscht wird.
class QuittungArtikel(Base):
    __tablename__ = "quittung_artikel"
    ID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Quittung_ID: Mapped[int] = mapped_column(Integer, ForeignKey("quittungen.ID", ondelete="CASCADE"), index=True)
    Artikel_ID: Mapped[int] = mapped_column(Integer)
    Artikel_Kategorie: Mapped[str] = mapped_column(String(50))
    Auftrag_ID: Mapped[int] = mapped_column(Integer, nullable=True)
    Verleih_ID: Mapped[int] = mapped_column(Integer, nullable=True)
    # Handware: Kopie zum Verkaufszeitpunkt, damit die Quittung auch nach Ändern/Löschen des Artikels stimmt
    Bezeichnung: Mapped[str | None] = mapped_column(String(100), nullable=True)
    Preis: Mapped[float | None] = mapped_column(Double, nullable=True)
    Menge: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Relation zu der Quittung, in der dieser Artikel enthalten ist
    quittung: Mapped["Quittung"] = relationship("Quittung", back_populates="artikels")